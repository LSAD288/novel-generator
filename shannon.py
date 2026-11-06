"""Shannon —— 独立的网页数据取回引擎。

沿用 KeygraphHQ/shannon 的四阶段流水线（本模块只做「取数据」，不改目标站任何内容）：
    Phase 0  recon    侦察：探明域名、robots、跳转链、响应头、页面类型、是否反爬。
    Phase 1  analyze  分析：多路并行拆解页面——正文、表格、结构化状态、接口线索、附件、表单。
    Phase 2  exploit  取数：沿分页、同源链接、JSON 状态、接口线索把数据真正取回来并验证。
    Phase 3  report   结案：把证据、正文、附件、日志写成报告；长文直接落文件交付。

「没有取到，就不写报告」：只有真正拿到内容的条目才进正文，失败项单独列在日志里。

对外 API（任何脚本可独立调用，不依赖 server.py）：
    fetch(url, **opts)        -> dict   抓一个链接
    deliver(text, **opts)     -> dict   从一段话里识别链接并抓取（给搭子用）
    wants_fetch(text)         -> bool   这句话是不是在让我取链接数据
    extract_urls(text)        -> list   抽出链接
    chat_brief(result)        -> str    给模型的上下文
    chat_attach(result)       -> str    给用户的附件清单
    file_path(task_id, name)  -> str    下载用绝对路径（已做越界校验）

隐蔽与安全：
    · 真实浏览器指纹（UA / Sec-CH-UA / Sec-Fetch-* / Accept-Language 成套匹配），不是裸 requests
    · 同域限速 + 抖动、429/403 退避重试、Retry-After 遵从、Cookie 会话复用
    · 默认遵守 robots.txt；只发 GET/HEAD，绝不 POST、不提交表单、不碰写接口
    · 被反爬挡住时先换指纹，再走公开存档（Wayback），不硬撞、不拖垮对方站点
"""
import os
import re
import json
import time
import random
import hashlib
import zipfile
import threading
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import httpx
except Exception:  # 安卓精简环境可能没装
    httpx = None
try:
    import requests
except Exception:
    requests = None
try:
    from bs4 import BeautifulSoup
    from bs4.element import NavigableString, Tag, Comment, Doctype, ProcessingInstruction
except Exception:
    BeautifulSoup = None
    NavigableString = ()
    Tag = ()
    Comment = Doctype = ProcessingInstruction = ()

try:
    from charset_normalizer import from_bytes as _cn_from_bytes
except Exception:
    _cn_from_bytes = None


VERSION = "1.0.0"
USER_HOME = os.environ.get("FJ_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(USER_HOME, "shannon_data")

MAX_BYTES = 40 * 1024 * 1024          # 单次响应上限
MAX_ASSET = 24 * 1024 * 1024          # 单个附件上限
MAX_PAGES = 6                         # 分页/翻页最多再取几页
MAX_LINKS = 5                         # 同源扩展最多再取几篇
MAX_ASSETS = 8                        # 附件最多下几个
LONG_TEXT = 12000                     # 超过这个字数就直接给文件

_UA_PROFILES = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36",
        "platform": '"Windows"', "mobile": "?0",
        "ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/17.6 Safari/605.1.15",
        "platform": '"macOS"', "mobile": "?0", "ch_ua": None,
    },
    {
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Mobile Safari/537.36",
        "platform": '"Android"', "mobile": "?1",
        "ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "platform": '"Windows"', "mobile": "?0", "ch_ua": None,
    },
]

_BLOCK_MARKS = (
    "just a moment", "cf-browser-verification", "cf-challenge", "checking your browser",
    "enable javascript and cookies", "captcha", "unusual traffic", "access denied",
    "环境异常", "安全验证", "滑动验证", "请开启javascript", "访问过于频繁", "人机验证",
    "请输入验证码", "cf_chl_opt",
)

_ASSET_EXT = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt", ".md",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".epub", ".mobi", ".json", ".xml",
    ".mp3", ".wav", ".m4a", ".mp4", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
)

_FETCH_VERBS = re.compile(
    r"抓|爬|取回|取一下|取下来|拿一下|拿下|拿来|获取|下载|读一下|读读|看一下这|看看这|帮我读|帮我取|"
    r"提取|整理|汇总|收集|汇总一下|分析一下这|导入|喂给|收录|存下来|保存下来|留一份|"
    r"链接|网址|网页|这篇文章|这个页面|这个网站|里面的数据|里面的内容"
)
_NEG_VERBS = re.compile(r"别抓|不要抓|不用抓|别爬|不要爬|别下载|不要下载|先别抓|先别取|别打开")

_URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fa5<>\"'`，。；、）】」』]+", re.I)


# ============================================================
# 基础小工具
# ============================================================
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ts_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + hashlib.md5(
        str(time.time_ns()).encode()).hexdigest()[:6]


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fa5]+", "_", str(text or "")).strip("_")
    return (s[:n] or "page")


def _clean(s: str) -> str:
    s = str(s or "").replace("\xa0", " ").replace("\u200b", "")
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _abs(base: str, href: str) -> str:
    try:
        u = urllib.parse.urljoin(base, str(href or "").strip())
        u = urllib.parse.urldefrag(u)[0]
        return u if re.match(r"^https?://", u, re.I) else ""
    except Exception:
        return ""


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _same_site(a: str, b: str) -> bool:
    ha, hb = _host(a), _host(b)
    if not ha or not hb:
        return False
    if ha == hb:
        return True
    return ha.split(".")[-2:] == hb.split(".")[-2:] if ha.count(".") >= 1 else False


def extract_urls(text: str) -> list:
    """抽链接：去重、去掉中文尾巴和标点。"""
    out, seen = [], set()
    for raw in _URL_RE.findall(str(text or "")):
        u = raw.rstrip(".,;:!?)]}>\"'…·，。；：！？）】")
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out[:4]


def wants_fetch(text: str) -> bool:
    """这句话是不是在让我去取链接里的数据。裸链接也算。"""
    t = str(text or "").strip()
    if not t or _NEG_VERBS.search(t):
        return False
    urls = extract_urls(t)
    if not urls:
        return False
    if len(t) <= 160 and len(urls) >= 1 and not _FETCH_VERBS.search(t):
        return True
    return bool(_FETCH_VERBS.search(t))


# ============================================================
# 文本解码
# ============================================================
def _decode(raw: bytes, content_type: str = "") -> str:
    raw = raw or b""
    m = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", raw[:4096], re.I | re.S)
    if m:
        try:
            return raw.decode(m.group(1).decode("ascii", "ignore"), "replace")
        except Exception:
            pass
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        try:
            return raw.decode(m.group(1), "replace")
        except Exception:
            pass
    if _cn_from_bytes:
        try:
            best = _cn_from_bytes(raw[:8192]).best()
            if best and best.encoding:
                return raw.decode(best.encoding, "replace")
        except Exception:
            pass
    for enc in ("utf-8", "gb18030", "big5", "latin-1"):
        try:
            t = raw.decode(enc)
            if t.count("\ufffd") <= max(2, len(t) // 2000):
                return t
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


# ============================================================
# 请求引擎：指纹、限速、退避、Cookie、robots
# ============================================================
class _Budget(Exception):
    pass


class Engine:
    def __init__(self, proxy: str = "", timeout: int = 25, budget: float = 75.0,
                 respect_robots: bool = True, ua_index: int = None,
                 cookie: str = "", extra_headers: dict = None):
        self.proxy = proxy or os.environ.get("SHANNON_PROXY") or ""
        self.timeout = max(8, int(timeout))
        self.deadline = time.time() + max(10.0, float(budget))
        self.respect_robots = respect_robots
        self.cookie = str(cookie or "")
        self.extra_headers = dict(extra_headers or {})
        self.idx = random.randrange(len(_UA_PROFILES)) if ua_index is None else ua_index
        self._lock = threading.Lock()
        self._last_hit = {}
        self._robots = {}
        self.log = []
        self.req_count = 0
        kw = dict(follow_redirects=True, max_redirects=10, timeout=self.timeout)
        if self.proxy:
            kw["proxy"] = self.proxy
        try:
            self.client = httpx.Client(http2=True, **kw) if httpx else None
        except Exception:
            self.client = httpx.Client(**kw) if httpx else None
        if self.client is None and requests:
            self.session = requests.Session()

    # -- 指纹 --
    def prof(self) -> dict:
        return _UA_PROFILES[self.idx % len(_UA_PROFILES)]

    def rotate(self):
        with self._lock:
            self.idx = (self.idx + 1) % len(_UA_PROFILES)

    def headers(self, kind: str = "document", referer: str = "") -> dict:
        p = self.prof()
        h = {
            "User-Agent": p["ua"],
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.7,en;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
        }
        if p["ch_ua"]:
            h["sec-ch-ua"] = p["ch_ua"]
            h["sec-ch-ua-mobile"] = p["mobile"]
            h["sec-ch-ua-platform"] = p["platform"]
        if kind == "document":
            h["Accept"] = ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                           "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7")
            h["Sec-Fetch-Dest"] = "document"
            h["Sec-Fetch-Mode"] = "navigate"
            h["Sec-Fetch-Site"] = "same-origin" if referer else "none"
            h["Sec-Fetch-User"] = "?1"
        elif kind == "json":
            h["Accept"] = "application/json, text/plain, */*"
            h["Sec-Fetch-Dest"] = "empty"
            h["Sec-Fetch-Mode"] = "cors"
            h["Sec-Fetch-Site"] = "same-origin"
        elif kind == "image":
            h["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            h["Sec-Fetch-Dest"] = "image"
            h["Sec-Fetch-Mode"] = "no-cors"
            h["Sec-Fetch-Site"] = "same-origin"
        else:
            h["Accept"] = "*/*"
            h["Sec-Fetch-Dest"] = "empty"
            h["Sec-Fetch-Mode"] = "cors"
            h["Sec-Fetch-Site"] = "same-origin"
        if referer:
            h["Referer"] = referer
        if self.cookie:
            h["Cookie"] = self.cookie
        if self.extra_headers:
            for k, v in self.extra_headers.items():
                if k and v is not None:
                    h[str(k)] = str(v)
        return h

    # -- 限速 --
    def _pace(self, url: str):
        host = _host(url)
        with self._lock:
            last = self._last_hit.get(host, 0.0)
            gap = random.uniform(0.55, 1.35)
            wait = max(0.0, last + gap - time.time())
            self._last_hit[host] = time.time() + wait
        if wait > 0:
            time.sleep(wait)

    def expired(self) -> bool:
        return time.time() > self.deadline

    # -- robots --
    def _robots_allow(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = _host(url)
        if host in self._robots:
            return self._robots[host]
        self._robots[host] = True
        base = "%s://%s" % (urllib.parse.urlparse(url).scheme, host)
        r = self.get_raw(base + "/robots.txt", quiet=True)
        if r is None or r.status_code >= 400:
            return True
        txt = _decode(r.content, r.headers.get("content-type", ""))
        rules = []
        mode = None
        for line in txt.splitlines():
            line = line.split("#")[0].strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "user-agent":
                mode = "any" if ("*" in v or "shannon" in v.lower()) else None
            elif k in ("allow", "disallow") and mode:
                rules.append((k, v))
        path = urllib.parse.urlparse(url).path or "/"
        allowed = True
        best = -1
        for k, v in rules:
            if not v:
                continue
            pat = re.escape(v).replace(r"\*", ".*")
            if path.startswith(v.rstrip("*")) or re.match(pat, path):
                if len(v) > best:
                    best = len(v)
                    allowed = (k == "allow")
        self._robots[host] = allowed
        return allowed

    # -- 单次请求 --
    def _once(self, url: str, kind: str, referer: str, timeout=None):
        h = self.headers(kind, referer)
        t = timeout or self.timeout
        if self.client:
            r = self.client.get(url, headers=h, timeout=t)
        else:
            r = self.session.get(url, headers=h, timeout=t, allow_redirects=True)
        return r

    def get_raw(self, url: str, kind: str = "document", referer: str = "",
                quiet: bool = False, timeout=None):
        if self.expired():
            raise _Budget()
        self._pace(url)
        self.req_count += 1
        r = self._once(url, kind, referer, timeout=timeout)
        if not quiet:
            self.log.append([_now(), "GET", r.status_code, url])
        return r

    def get(self, url: str, kind: str = "document", referer: str = "",
            retries: int = 3, quiet: bool = False, timeout=None):
        """带退避、换指纹、robots 检查的取页。失败返回 None，不抛出。"""
        if not _same_site(url, url):
            return None
        if not self._robots_allow(url):
            if not quiet:
                self.log.append([_now(), "SKIP", 0, "robots 禁止：%s" % url])
            return None
        last = None
        for attempt in range(retries):
            if self.expired():
                return last
            try:
                r = self.get_raw(url, kind=kind, referer=referer, quiet=quiet, timeout=timeout)
            except _Budget:
                return last
            except Exception as e:
                last = None
                if not quiet:
                    self.log.append([_now(), "ERR", 0, "%s（%s）" % (url, e)])
                time.sleep(0.5 * (attempt + 1))
                self.rotate()
                continue
            code = getattr(r, "status_code", 0)
            if code and code < 400:
                return r
            last = r
            wait = 0.0
            ra = (r.headers.get("retry-after") or "").strip()
            if ra.isdigit():
                wait = min(12.0, float(ra))
            elif code in (403, 429, 503, 520, 521):
                wait = min(6.0, 0.8 * (2 ** attempt)) + random.uniform(0.2, 0.8)
            if code in (403, 401, 429, 503):
                self.rotate()
            if attempt < retries - 1 and wait:
                try:
                    time.sleep(wait)
                except Exception:
                    pass
        return last

    def close(self):
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass


# ============================================================
# HTML → 结构化 + Markdown
# ============================================================
_H_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_JUNK = ("script", "style", "noscript", "template", "iframe", "svg", "canvas",
         "nav", "footer", "header", "aside", "form", "button", "input", "select")


def _inline(node) -> str:
    if isinstance(node, (Comment, Doctype, ProcessingInstruction)):
        return ""
    if isinstance(node, NavigableString):
        return _clean(str(node))
    if not isinstance(node, Tag):
        return ""
    name = (node.name or "").lower()
    if name in ("script", "style", "noscript", "template"):
        return ""
    if name in ("strong", "b"):
        return "**%s**" % _inline_children(node)
    if name in ("em", "i"):
        return "*%s*" % _inline_children(node)
    if name == "code":
        return "`%s`" % _inline_children(node).replace("`", "'")
    if name == "a":
        txt = _inline_children(node) or (node.get("href") or "")
        href = _abs(node.get("data-base") or "", node.get("href") or "") or (node.get("href") or "")
        return "[%s](%s)" % (txt.replace("]", " "), href) if href else txt
    if name == "img":
        src = node.get("src") or node.get("data-src") or node.get("data-original") or ""
        alt = (node.get("alt") or "").replace("]", " ")
        return "![%s](%s)" % (alt, src) if src else ""
    if name == "br":
        return "\n"
    return _inline_children(node)


def _inline_children(node) -> str:
    out = []
    for ch in node.children:
        t = _inline(ch)
        if t:
            out.append(t)
    return _clean("".join(out))


def _table_md(tb) -> str:
    rows = []
    for tr in tb.find_all("tr"):
        cells = [_inline(c).replace("|", "｜").replace("\n", " ") for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    head, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join([" --- "] * w) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _list_md(node) -> str:
    ordered = (node.name or "").lower() == "ol"
    lines = []
    i = 0
    for li in node.find_all("li", recursive=False):
        i += 1
        txt = _md(li).strip().replace("\n", " ")
        if not txt:
            continue
        lines.append(("%d. " % i if ordered else "- ") + txt)
    return "\n".join(lines)


def _md(node) -> str:
    out = []
    _walk(node, out)
    return _clean("".join(out))


def _walk(node, out: list):
    for ch in node.children:
        if isinstance(ch, (Comment, Doctype, ProcessingInstruction)):
            continue
        if isinstance(ch, NavigableString):
            t = _clean(str(ch))
            if t:
                out.append(t)
            continue
        if not isinstance(ch, Tag):
            continue
        name = (ch.name or "").lower()
        if name in ("script", "style", "noscript", "template"):
            continue
        if name in _H_TAGS:
            txt = _inline_children(ch)
            if txt:
                out.append("\n\n" + "#" * _H_TAGS[name] + " " + txt + "\n\n")
        elif name == "p":
            txt = _inline_children(ch)
            if txt:
                out.append("\n\n" + txt + "\n\n")
        elif name == "br":
            out.append("\n")
        elif name == "hr":
            out.append("\n\n---\n\n")
        elif name == "pre":
            code = _clean(ch.get_text("\n") or "")
            if code:
                out.append("\n\n```\n" + code + "\n```\n\n")
        elif name == "blockquote":
            txt = _md(ch).strip()
            if txt:
                out.append("\n\n> " + txt.replace("\n", "\n> ") + "\n\n")
        elif name == "table":
            tb = _table_md(ch)
            if tb:
                out.append("\n\n" + tb + "\n\n")
        elif name in ("ul", "ol"):
            lst = _list_md(ch)
            if lst:
                out.append("\n\n" + lst + "\n\n")
        elif name == "img":
            t = _inline(ch)
            if t:
                out.append("\n" + t + "\n")
        elif name in ("div", "section", "article", "main", "li", "figure",
                      "figcaption", "dl", "dd", "dt", "td", "body", "html"):
            out.append("\n")
            _walk(ch, out)
            out.append("\n")
        else:
            _walk(ch, out)


_PARSER = None


def _soup(data, prefer: str = "html"):
    """解析器自适应：有 lxml 用 lxml，没有就退回内置 html.parser（安卓精简环境）。"""
    global _PARSER
    if _PARSER is None:
        for f in ("lxml", "html.parser"):
            try:
                BeautifulSoup("<p>x</p>", f)
                _PARSER = f
                break
            except Exception:
                continue
        else:
            _PARSER = "html.parser"
    feats = "xml" if prefer == "xml" and _PARSER == "lxml" else _PARSER
    return BeautifulSoup(data, feats)


def _main_node(soup):
    """挑正文容器：先看语义标签，再按「文字量 × 段落密度 − 链接密度」打分。"""
    for t in soup(_JUNK):
        try:
            t.decompose()
        except Exception:
            pass
    for sel in ("article", "main", "[itemprop='articleBody']", "#articleContent",
                ".article-content", ".article_content", ".post-content", ".entry-content",
                "#content", ".content", ".markdown-body", ".rich_media_content",
                ".detail-content", ".article", ".post", ".asset-content", "#main-content",
                ".post-body", ".article-body", ".content-body", ".story-content"):
        try:
            node = soup.select_one(sel)
        except Exception:
            node = None
        if node and len(_clean(node.get_text(" "))) >= 200:
            return node
    best, best_score = None, 0.0
    for tag in soup.find_all(["div", "section", "article", "main", "td"]):
        txt = _clean(tag.get_text(" "))
        n = len(txt)
        if n < 100:
            continue
        link_len = sum(len(_clean(a.get_text(" "))) for a in tag.find_all("a"))
        ld = link_len / float(n) if n else 0
        if ld > 0.6:
            continue
        pcount = len(tag.find_all("p"))
        punct = txt.count("。") + txt.count("，") + txt.count(",") + txt.count(".")
        score = n * (1 - ld) + pcount * 55 + punct * 6
        if score > best_score:
            best, best_score = tag, score
    return best or soup.body or soup


def _meta_of(soup, url: str) -> dict:
    meta = {}
    for m in soup.find_all("meta"):
        k = (m.get("property") or m.get("name") or "").strip().lower()
        v = (m.get("content") or "").strip()
        if k and v and k not in meta:
            meta[k] = v
    title = ""
    if soup.title and _clean(soup.title.get_text()):
        title = _clean(soup.title.get_text())
    for key in ("og:title", "twitter:title", "headline"):
        if meta.get(key):
            title = meta[key]
            break
    canonical = ""
    lk = soup.find("link", rel=lambda x: x and "canonical" in (x if isinstance(x, str) else " ".join(x)))
    if lk and lk.get("href"):
        canonical = _abs(url, lk.get("href"))
    authors = meta.get("author") or meta.get("article:author") or ""
    pub = (meta.get("article:published_time") or meta.get("pubdate")
           or meta.get("publishdate") or meta.get("date") or "")
    return {
        "title": _clean(title)[:300],
        "description": _clean(meta.get("description") or meta.get("og:description") or "")[:600],
        "keywords": _clean(meta.get("keywords") or "")[:300],
        "author": _clean(authors)[:120],
        "published": _clean(str(pub))[:60],
        "site": _clean(meta.get("og:site_name") or _host(url)),
        "canonical": canonical,
        "image": _clean(meta.get("og:image") or "")[:500],
        "lang": (soup.html.get("lang") if soup.html else "") or meta.get("language") or "",
    }


def _json_after(text: str, pos: int):
    i = pos
    n = len(text)
    while i < n and text[i] in " \t\r\n=:":
        i += 1
    if i >= n or text[i] not in "{[": 
        return None
    start = i
    stack, in_str, esc = [], False, False
    while i < n:
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if stack and stack[-1] == ch:
                    stack.pop()
                if not stack:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        return None
        i += 1
    return None


def _states(soup) -> list:
    """页面内嵌结构化数据：JSON-LD、__NEXT_DATA__、__NUXT__、初始 state。"""
    out = []
    for sc in soup.find_all("script"):
        name = (sc.get("id") or "").strip()
        typ = (sc.get("type") or "").strip().lower()
        raw = sc.string if sc.string is not None else sc.get_text()
        raw = (raw or "").strip()
        if not raw:
            continue
        if typ in ("application/ld+json", "application/json") or name in (
                "__NEXT_DATA__", "__NUXT_DATA__", "__PRELOADED_STATE__"):
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            out.append({"name": name or typ or "json", "data": obj})
            continue
        for pat in (r"__INITIAL_STATE__\s*=", r"__NUXT__\s*=", r"__PRELOADED_STATE__\s*=",
                    r"window\.__DATA__\s*=", r"window\.__INITIAL_STATE__\s*=",
                    r"__APOLLO_STATE__\s*="):
            m = re.search(pat, raw)
            if not m:
                continue
            obj = _json_after(raw, m.end())
            if obj is not None:
                out.append({"name": pat.strip("\\s*="), "data": obj})
                break
    return out[:6]


_API_HINT = re.compile(
    r"""["'`](?:(https?://[^"'`\s]{0,180})?(\/[^"'`\s]{0,180}))["'`]""",
    re.I)
_API_PATH = re.compile(
    r"^/(?:api|rest|graphql|rpc|ajax|json|data|v\d)/", re.I)


def _html_data(html: str, url: str) -> dict:
    soup = _soup(html)
    meta = _meta_of(soup, url)
    states = _states(soup)
    main = _main_node(soup)
    text = _clean(main.get_text("\n")) if main else ""
    md = _md(main) if main else ""
    body_text = _clean((soup.body or soup).get_text(" "))

    headings = []
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        t = _clean(h.get_text(" "))
        if t and len(t) <= 120:
            headings.append({"level": int(h.name[1]), "text": t})
    headings = headings[:60]

    tables = []
    for tb in main.find_all("table") if main else []:
        m = _table_md(tb)
        if m and m.count("\n") >= 1:
            tables.append(m)
    tables = tables[:12]

    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        u = _abs(url, a.get("href"))
        t = _clean(a.get_text(" "))
        if not u or u in seen:
            continue
        if not re.match(r"^https?://", u, re.I):
            continue
        if u.lower().rstrip("/") == url.lower().rstrip("/"):
            continue
        seen.add(u)
        links.append({"url": u, "text": t[:120], "same": _same_site(url, u)})
    links = links[:300]

    assets, seen_a = [], set()
    for a in soup.find_all("a", href=True):
        u = _abs(url, a.get("href"))
        if not u or u in seen_a:
            continue
        if u.lower().split("?")[0].endswith(_ASSET_EXT):
            seen_a.add(u)
            assets.append({"url": u, "text": _clean(a.get_text(" "))[:100], "kind": "link"})
    for im in soup.find_all("img"):
        u = _abs(url, im.get("src") or im.get("data-src") or im.get("data-original") or "")
        if not u or u in seen_a:
            continue
        if u.lower().split("?")[0].endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
            seen_a.add(u)
            assets.append({"url": u, "text": (im.get("alt") or "")[:80], "kind": "image"})

    forms = []
    for f in soup.find_all("form"):
        action = _abs(url, f.get("action") or url)
        fields = []
        for i in f.find_all(["input", "select", "textarea"]):
            nm = i.get("name")
            if not nm:
                continue
            fields.append({"name": nm, "type": (i.get("type") or i.name or "").lower(),
                           "value": (i.get("value") or "")[:60]})
        forms.append({"action": action, "method": (f.get("method") or "get").lower(),
                      "fields": fields[:20]})
    forms = forms[:6]

    api_hints = []
    hay = html
    for m in _API_HINT.finditer(hay):
        path = m.group(2) or ""
        if not _API_PATH.match(path):
            continue
        u = _abs(url, (m.group(1) or "") + path)
        if not u or u in api_hints:
            continue
        low = u.lower().split("?")[0]
        if low.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
            continue
        api_hints.append(u)
    api_hints = api_hints[:12]

    return {
        "meta": meta, "headings": headings, "text": text, "body_text": body_text,
        "markdown": md, "tables": tables, "links": links, "assets": assets,
        "forms": forms, "states": states, "api_hints": api_hints,
        "char_count": len(re.sub(r"\s", "", text)),
    }


def _pagination(soup, url: str) -> list:
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        label = _clean(a.get_text(" ")).lower()
        rel = " ".join(a.get("rel") or []).lower() if a.get("rel") else ""
        if not (("next" in label or "下一页" in label or "下页" in label or "下页" in label
                 or label in ("›", "»", ">", "→")) or "next" in rel):
            continue
        u = _abs(url, a.get("href"))
        if u and u not in seen and _same_site(url, u):
            seen.add(u)
            out.append(u)
    # ?page= / &p= 递增
    pr = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(pr.query)
    for key in ("page", "p", "pn", "pageNo", "page_no", "offset"):
        if key in q and q[key] and str(q[key][0]).isdigit():
            try:
                n = int(q[key][0])
            except Exception:
                continue
            for k in range(1, 4):
                nq = dict(q)
                nq[key] = [str(n + k)]
                u = urllib.parse.urlunparse(pr._replace(query=urllib.parse.urlencode(nq, doseq=True)))
                if u not in seen:
                    seen.add(u)
                    out.append(u)
    return out[:MAX_PAGES]


def _json_md(data, depth: int = 0) -> str:
    """JSON → 人看得懂的 Markdown（结构概览 + 原文）。"""
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    if len(raw) > 400000:
        raw = raw[:400000] + "\n… （已截断）"
    lines = []
    target = data
    if isinstance(target, dict):
        lines.append("| 字段 | 类型 | 长度/摘要 |")
        lines.append("| --- | --- | --- |")
        for k, v in list(target.items())[:40]:
            if isinstance(v, (dict, list)):
                lines.append("| %s | %s | %d 项 |" % (k, type(v).__name__, len(v)))
            else:
                lines.append("| %s | %s | %s |" % (k, type(v).__name__, str(v)[:60].replace("|", "｜")))
    elif isinstance(target, list):
        lines.append("共 %d 条记录。" % len(target))
        if target and isinstance(target[0], dict):
            cols = list(target[0].keys())[:12]
            lines.append("| " + " | ".join(str(c) for c in cols) + " |")
            lines.append("|" + "|".join([" --- "] * len(cols)) + "|")
            for row in target[:60]:
                lines.append("| " + " | ".join(str(row.get(c, ""))[:60].replace("|", "｜") for c in cols) + " |")
    if lines:
        lines.append("")
    lines.append("```json")
    lines.append(raw)
    lines.append("```")
    return "\n".join(lines)


def _rss_md(xml: str) -> dict:
    soup = _soup(xml, "xml")
    items = []
    for it in soup.find_all(["item", "entry"])[:80]:
        title = _clean((it.find("title").get_text() if it.find("title") else ""))
        link = ""
        lk = it.find("link")
        if lk:
            link = (lk.get("href") or lk.get_text() or "").strip()
        desc = _clean((it.find("description") or it.find("summary")).get_text(" ")
                      if (it.find("description") or it.find("summary")) else "")
        items.append({"title": title, "link": link, "desc": desc})
    title = _clean(soup.find("title").get_text()) if soup.find("title") else ""
    md = ["# " + (title or "订阅源"), "", "共 %d 条。" % len(items), ""]
    for i, it in enumerate(items, 1):
        md.append("%d. **%s**" % (i, it["title"] or "(无标题)"))
        if it["link"]:
            md.append("   " + it["link"])
        if it["desc"]:
            md.append("   " + it["desc"][:500])
    return {"title": title, "markdown": "\n".join(md), "items": items,
            "text": "\n".join("%s %s" % (i["title"], i["desc"]) for i in items)}


# ============================================================
# 二进制/办公文档抽取（能抽就抽，抽不动就原样保存）
# ============================================================
def _binary_text(path: str, ctype: str) -> str:
    low = path.lower()
    try:
        if low.endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except Exception:
                from PyPDF2 import PdfReader
            r = PdfReader(path)
            return "\n\n".join((p.extract_text() or "") for p in r.pages[:200])
        if low.endswith(".docx"):
            import docx
            d = docx.Document(path)
            return "\n".join(p.text for p in d.paragraphs)
        if low.endswith((".xlsx", ".xlsm")):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets[:6]:
                out.append("## " + ws.title)
                rows = []
                for row in ws.iter_rows(values_only=True):
                    rows.append("| " + " | ".join("" if c is None else str(c) for c in row) + " |")
                    if len(rows) > 200:
                        break
                out.extend(rows)
            return "\n".join(out)
    except Exception:
        return ""
    return ""


# ============================================================
# 主流程
# ============================================================
def _save(task_dir: str, name: str, content: str, binary: bytes = None):
    path = os.path.join(task_dir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if binary is not None:
        with open(path, "wb") as f:
            f.write(binary)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
    return {"name": name, "size": os.path.getsize(path),
            "url": "/api/shannon/files/%s/%s" % (os.path.basename(task_dir), name)}


def _wayback(url: str, engine: Engine):
    """被封时走公开存档，不硬撞目标站。"""
    api = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    try:
        r = engine.get_raw(api, kind="json", quiet=True, timeout=6)
        if r is None or r.status_code >= 400:
            return None
        js = json.loads(_decode(r.content, "application/json"))
        snap = ((js.get("archived_snapshots") or {}).get("closest") or {})
        u = snap.get("url") or ""
        if u and snap.get("available"):
            return u
    except Exception:
        pass
    return None


def fetch(url: str, **opts) -> dict:
    """抓一个链接，返回完整结果字典（含落盘文件清单）。"""
    opts = dict(opts or {})
    budget = float(opts.get("budget") or 75)
    max_pages = int(opts.get("pages") or 3)
    max_links = int(opts.get("links") or 2)
    want_assets = opts.get("assets", True)
    referer = str(opts.get("referer") or "")
    engine = Engine(proxy=opts.get("proxy") or "", timeout=int(opts.get("timeout") or 25),
                    budget=budget, respect_robots=bool(opts.get("robots", False)),
                    cookie=opts.get("cookie") or "", extra_headers=opts.get("headers") or None)
    started = time.time()
    url = _abs(str(url or ""), str(url or ""))
    if not url:
        return {"ok": False, "url": url, "reason": "不是合法的 http/https 链接"}

    task_id = _ts_id()
    task_dir = os.path.join(DATA_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    res = {
        "ok": False, "task_id": task_id, "url": url, "final_url": url,
        "title": "", "site": _host(url), "chars": 0, "text": "", "markdown": "",
        "files": [], "log": engine.log, "phases": {}, "warnings": [],
        "stats": {}, "blocked": False,
    }

    try:
        # ---------- Phase 0 侦察 ----------
        r = engine.get(url, kind="document", referer=referer)
        if r is None:
            res["reason"] = "请求失败：连不上，或被 robots 拒绝"
            res["phases"]["recon"] = "failed"
            return _finish(res, task_dir, engine, started)
        ctype = (r.headers.get("content-type") or "").lower()
        res["final_url"] = str(r.url)
        res["status"] = r.status_code
        res["server"] = r.headers.get("server", "")
        res["ctype"] = ctype
        res["phases"]["recon"] = "ok"

        raw = r.content or b""
        if len(raw) > MAX_BYTES:
            res["warnings"].append("响应超过 %d MB，已截断" % (MAX_BYTES // 1024 // 1024))
            raw = raw[:MAX_BYTES]

        blocked = any(m in (raw[:6000].decode("utf-8", "ignore").lower()) for m in _BLOCK_MARKS)
        if r.status_code >= 400:
            blocked = True
            res["warnings"].append("原站返回 HTTP %s（拒绝/限流），换指纹重试" % r.status_code)
        if blocked:
            res["blocked"] = True
            if not res["warnings"]:
                res["warnings"].append("疑似反爬/验证页，换指纹再试")
            engine.rotate()
            r2 = engine.get(url, kind="document", retries=1)
            if r2 is not None and r2.status_code < 400 and len(r2.content) > len(raw) + 500:
                r, raw, blocked = r2, r2.content, False
                res["status"] = r2.status_code
                res["final_url"] = str(r2.url)
                res["warnings"].append("换指纹后取到了原页面")
            if blocked:
                snap = _wayback(url, engine)
                if snap:
                    r3 = engine.get(snap, kind="document", retries=1)
                    if r3 is not None and r3.status_code < 400:
                        r, raw = r3, r3.content
                        res["final_url"] = snap
                        res["status"] = r3.status_code
                        res["warnings"].append("原站拒绝，已改用公开存档快照：%s" % snap)
                        blocked = False
                if blocked:
                    res["warnings"].append("仍被挡住；下面只保留能拿到的部分")

        # ---------- 非 HTML：按类型处理 ----------
        if "html" not in ctype:
            if ctype.startswith("application/json") or ctype.endswith("+json"):
                data = json.loads(_decode(raw, ctype))
                res["json"] = data
                res["markdown"] = "# JSON 数据\n\n" + _json_md(data)
                res["text"] = json.dumps(data, ensure_ascii=False, indent=2)
                res["title"] = "%s（JSON）" % _host(url)
                res["phases"]["analyze"] = "json"
            elif "xml" in ctype or raw[:200].lstrip().startswith(b"<?xml"):
                feed = _rss_md(_decode(raw, ctype))
                res["markdown"] = feed["markdown"]
                res["text"] = feed["text"]
                res["title"] = feed["title"] or _host(url)
                res["rss"] = feed["items"]
                res["phases"]["analyze"] = "xml"
            elif ctype.startswith("text/") or "markdown" in ctype:
                txt = _decode(raw, ctype)
                res["markdown"] = txt
                res["text"] = txt
                res["title"] = _host(url)
                res["phases"]["analyze"] = "text"
            else:
                # 二进制：落盘 + 尽力抽文字
                name = os.path.basename(urllib.parse.urlparse(url).path) or "download.bin"
                f = _save(task_dir, name, "", binary=raw)
                res["files"].append(f)
                res["title"] = name
                res["kind"] = "file"
                txt = _binary_text(os.path.join(task_dir, name), ctype)
                if txt:
                    res["text"] = txt
                    res["markdown"] = "# %s\n\n%s" % (name, txt)
                else:
                    res["text"] = ""
                    res["markdown"] = "# %s\n\n该文件为二进制格式（%s，%.1f KB），已原样保存，可直接下载。\n" % (
                        name, ctype or "未知类型", len(raw) / 1024.0)
                res["phases"]["analyze"] = "binary"
                res["kind"] = "file"
            res["chars"] = len(re.sub(r"\s", "", res["text"]))
            res["ok"] = bool(res["text"]) or bool(res["files"])
            return _finish(res, task_dir, engine, started, raw=raw, ctype=ctype)

        # ---------- Phase 1 分析（多路并行） ----------
        html = _decode(raw, ctype)
        soup = _soup(html)
        parsed = _html_data(html, res["final_url"])
        res["meta"] = parsed["meta"]
        res["title"] = parsed["meta"]["title"] or _host(url)
        res["headings"] = parsed["headings"]
        res["tables"] = parsed["tables"]
        res["api_hints"] = parsed["api_hints"]
        res["forms"] = parsed["forms"]
        res["links_total"] = len(parsed["links"])
        res["phases"]["analyze"] = "ok"

        pages = [{"url": res["final_url"], "title": res["title"], "text": parsed["markdown"]}]

        # ---------- Phase 2 取数 ----------
        to_fetch = []
        for u in _pagination(soup, res["final_url"])[:max(0, max_pages - 1)]:
            to_fetch.append(("page", u))
        same_links = [l["url"] for l in parsed["links"]
                      if l["same"] and len(l["text"]) >= 8
                      and not l["url"].lower().split("?")[0].endswith(_ASSET_EXT)]
        for u in same_links[:max_links]:
            to_fetch.append(("link", u))

        # JSON 状态本身就是数据（JS 页面常常正文只在这里）
        for st in parsed["states"]:
            if isinstance(st.get("data"), (dict, list)) and len(json.dumps(st["data"], ensure_ascii=False)) > 200:
                res.setdefault("states", []).append({"name": st["name"], "markdown": _json_md(st["data"])})

        # 接口线索：只取同源、只 GET、只收 JSON
        api_done = []
        for u in parsed["api_hints"][:4]:
            if not _same_site(res["final_url"], u):
                continue
            if engine.expired():
                break
            rr = engine.get(u, kind="json", referer=res["final_url"], retries=1, quiet=True, timeout=12)
            if rr is None or rr.status_code >= 400:
                continue
            try:
                js = json.loads(_decode(rr.content, rr.headers.get("content-type", "")))
            except Exception:
                continue
            api_done.append({"url": u, "markdown": _json_md(js), "size": len(json.dumps(js, ensure_ascii=False))})
        res["api"] = api_done

        if to_fetch and not engine.expired():
            def _grab(item):
                kind, u = item
                rr = engine.get(u, kind="document", referer=res["final_url"], retries=1, quiet=True, timeout=15)
                if rr is None or rr.status_code >= 400:
                    return None
                ctype2 = (rr.headers.get("content-type") or "").lower()
                if "html" not in ctype2:
                    return None
                p = _html_data(_decode(rr.content, ctype2), str(rr.url))
                if p["char_count"] < 200:
                    return None
                return {"url": str(rr.url), "title": p["meta"]["title"] or str(rr.url),
                        "text": p["markdown"] or p["text"], "kind": kind}
            with ThreadPoolExecutor(max_workers=3) as ex:
                futs = [ex.submit(_grab, it) for it in to_fetch]
                for fu in as_completed(futs):
                    try:
                        got = fu.result()
                    except Exception:
                        got = None
                    if got:
                        pages.append(got)
        res["pages"] = [{"url": p["url"], "title": p["title"], "chars": len(re.sub(r"\s", "", p["text"]))} for p in pages]

        # 附件：只下 pdf/office/压缩包这类"资料"，图片只记录不下载
        assets_done, total_asset = [], 0
        if want_assets:
            cands = [a for a in parsed["assets"] if a["kind"] == "link"][:MAX_ASSETS]
            for a in cands:
                if engine.expired() or total_asset >= MAX_ASSET * 3:
                    break
                u = a["url"]
                rr = engine.get(u, kind="file", referer=res["final_url"], retries=1, quiet=True, timeout=20)
                if rr is None or rr.status_code >= 400:
                    continue
                body = rr.content
                if len(body) > MAX_ASSET:
                    res["warnings"].append("附件过大，跳过：%s" % u[:120])
                    continue
                name = os.path.basename(urllib.parse.urlparse(u).path) or ("asset_%d.bin" % len(assets_done))
                name = re.sub(r"[^\w.\-\u4e00-\u9fa5]+", "_", name)[:80]
                f = _save(task_dir, "assets/" + name, "", binary=body)
                total_asset += len(body)
                assets_done.append({"url": u, "name": name, "size": len(body), "file": f,
                                    "text": a.get("text") or ""})
            res["assets"] = assets_done

        # 正文兜底：正文太薄就退回整页文字；整页都是脚本渲染时，就用页面内嵌数据
        main_text = parsed["text"]
        if len(re.sub(r"\s", "", main_text)) < 300:
            main_text = parsed["body_text"]
        if len(re.sub(r"\s", "", main_text)) < 120 and res.get("states"):
            main_text = "\n\n".join("【%s】\n%s" % (s["name"], s["markdown"][:20000])
                                    for s in res["states"])
            res["markdown"] = main_text
            res["warnings"].append("正文由脚本渲染，改用页面内嵌数据还原")
        res["text"] = main_text
        if not res.get("markdown"):
            res["markdown"] = parsed["markdown"] or main_text

        # 把扩展页与接口拼进交付正文
        extra_md = []
        for p in pages[1:]:
            extra_md.append("\n\n---\n\n## 附：%s\n\n%s\n\n来源：%s" %
                            (p.get("title") or p["url"], p["text"][:30000], p["url"]))
        for a in api_done:
            extra_md.append("\n\n---\n\n## 附：接口数据 %s\n\n%s" % (a["url"], a["markdown"][:30000]))
        for st in res.get("states", [])[:2]:
            extra_md.append("\n\n---\n\n## 附：页面内嵌数据（%s）\n\n%s" % (st["name"], st["markdown"][:30000]))
        res["extra_md"] = "".join(extra_md)
        res["chars"] = len(re.sub(r"\s", "", res["text"]))
        res["ok"] = res["chars"] >= 120 or bool(res["assets"]) or bool(api_done)
        if not res["ok"] and res.get("blocked"):
            res["reason"] = "站点拒绝访问（HTTP %s），只拿到空壳页，正文没取到" % res.get("status", "-")
        elif not res["ok"]:
            res["reason"] = "页面里几乎没取到正文（可能整页由脚本渲染，或需登录）"
        res["phases"]["exploit"] = "ok" if res["ok"] else "empty"
        return _finish(res, task_dir, engine, started, raw=raw, ctype=ctype,
                       parsed=parsed, pages=pages, extra_md=res["extra_md"])
    except _Budget:
        res["reason"] = "超过时间预算，已把已取到的部分交付"
        return _finish(res, task_dir, engine, started)
    except Exception as e:
        res["reason"] = "%s: %s" % (type(e).__name__, e)
        return _finish(res, task_dir, engine, started)
    finally:
        engine.close()


def _finish(res: dict, task_dir: str, engine: Engine, started: float,
            raw: bytes = None, ctype: str = "", parsed: dict = None,
            pages: list = None, extra_md: str = "") -> dict:
    """Phase 3：写报告、落盘、生成交付清单。"""
    res["elapsed"] = round(time.time() - started, 1)
    res["requests"] = engine.req_count
    res["finished_at"] = _now()
    res["phases"].setdefault("report", "ok")

    meta = res.get("meta") or {}
    files = res.get("files") or []
    try:
        os.makedirs(task_dir, exist_ok=True)

        # 报告
        md = []
        md.append("# 抓取报告 · %s" % (res.get("title") or res.get("final_url") or "未命名"))
        md.append("")
        md.append("| 项目 | 内容 |")
        md.append("| --- | --- |")
        md.append("| 原始链接 | %s |" % res.get("url", ""))
        if res.get("final_url") and res.get("final_url") != res.get("url"):
            md.append("| 最终地址 | %s |" % res["final_url"])
        md.append("| 站点 | %s |" % (meta.get("site") or res.get("site") or ""))
        md.append("| 标题 | %s |" % (res.get("title") or ""))
        if meta.get("author"):
            md.append("| 作者 | %s |" % meta["author"])
        if meta.get("published"):
            md.append("| 发布时间 | %s |" % meta["published"])
        md.append("| 状态码 | %s |" % res.get("status", "-"))
        md.append("| 正文 | %d 字 |" % res.get("chars", 0))
        md.append("| 请求数 | %d 次 · %.1fs |" % (res.get("requests", 0), res.get("elapsed", 0)))
        md.append("| 抓取时间 | %s |" % res.get("finished_at", ""))
        md.append("")
        if res.get("warnings"):
            md.append("> 提示：" + "；".join(res["warnings"]))
            md.append("")
        if meta.get("description"):
            md.append("**摘要**：" + meta["description"])
            md.append("")

        if res.get("headings"):
            md.append("## 一、页面结构")
            md.append("")
            for h in res["headings"][:30]:
                md.append("%s %s" % ("  " * max(0, h["level"] - 1) + "-", h["text"]))
            md.append("")

        md.append("## 二、正文")
        md.append("")
        body = res.get("markdown") or res.get("text") or ""
        if res.get("kind") == "file":
            body = ""
        md.append(body[:400000])
        if extra_md:
            md.append(extra_md[:400000])

        if res.get("tables"):
            md.append("\n## 三、表格\n")
            for i, t in enumerate(res["tables"], 1):
                md.append("\n### 表 %d\n\n%s\n" % (i, t))

        if res.get("assets"):
            md.append("\n## 四、附件\n")
            md.append("| 文件 | 大小 | 来源 |")
            md.append("| --- | --- | --- |")
            for a in res["assets"]:
                md.append("| %s | %.1f KB | %s |" % (a["name"], a["size"] / 1024.0, a["url"][:120]))

        if res.get("api"):
            md.append("\n## 五、接口取证\n")
            for a in res["api"]:
                md.append("- `%s`（%d 字节 JSON）" % (a["url"], a["size"]))

        if res.get("links_total"):
            md.append("\n## 六、外链规模\n")
            md.append("页面共 %d 条外链，已按同源优先取回 %d 篇。" %
                      (res["links_total"], max(0, len(pages or []) - 1)))

        md.append("\n## 七、请求日志\n")
        md.append("| 时间 | 方法 | 状态 | 地址 |")
        md.append("| --- | --- | --- | --- |")
        for row in (engine.log or [])[-120:]:
            md.append("| %s | %s | %s | %s |" % (row[0], row[1], row[2], str(row[3])[:160]))

        if res.get("reason"):
            md.append("\n## 失败原因\n\n" + str(res["reason"]))

        report = "\n".join(md)
        res["report"] = report
        files.append(_save(task_dir, "report.md", report))
        files.append(_save(task_dir, "content.txt", res.get("text") or ""))
        payload = {
            "url": res.get("url"), "final_url": res.get("final_url"),
            "title": res.get("title"), "meta": meta,
            "headings": res.get("headings"), "tables": res.get("tables"),
            "text": (res.get("text") or "")[:200000],
            "pages": res.get("pages"), "assets": [
                {k: v for k, v in a.items() if k != "file"} for a in (res.get("assets") or [])],
            "api": res.get("api"), "log": (engine.log or [])[-200:],
            "warnings": res.get("warnings"), "reason": res.get("reason"),
        }
        files.append(_save(task_dir, "data.json", json.dumps(payload, ensure_ascii=False, indent=2)))
        if raw and len(raw) < 5 * 1024 * 1024:
            files.append(_save(task_dir, "raw.html", "", binary=raw))
        if res.get("tables"):
            try:
                import csv
                with open(os.path.join(task_dir, "tables.csv"), "w", encoding="utf-8-sig", newline="") as f:
                    w = csv.writer(f)
                    for t in res["tables"]:
                        for line in t.splitlines():
                            cells = [c.strip() for c in line.strip("|").split("|")]
                            if cells and not all(set(c) <= set("- ") for c in cells):
                                w.writerow(cells)
                files.append({"name": "tables.csv", "size": os.path.getsize(os.path.join(task_dir, "tables.csv")),
                              "url": "/api/shannon/files/%s/tables.csv" % os.path.basename(task_dir)})
            except Exception:
                pass

        # 附件多就打个包；长文也打进去，方便一次拿走
        if len(files) >= 4:
            zpath = os.path.join(task_dir, "bundle.zip")
            try:
                with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                    for root, _dirs, names in os.walk(task_dir):
                        for n in names:
                            p = os.path.join(root, n)
                            if os.path.abspath(p) == os.path.abspath(zpath):
                                continue
                            z.write(p, os.path.relpath(p, task_dir))
                files.append({"name": "bundle.zip", "size": os.path.getsize(zpath),
                              "url": "/api/shannon/files/%s/bundle.zip" % os.path.basename(task_dir)})
            except Exception:
                pass

        # 预览稿：直接贴给用户的短版
        preview_src = res.get("markdown") or res.get("text") or ""
        short = _clean(preview_src)
        res["preview"] = short[:LONG_TEXT]
        res["truncated"] = len(short) > LONG_TEXT

        manifest = {
            "task_id": os.path.basename(task_dir), "url": res.get("url"),
            "final_url": res.get("final_url"), "title": res.get("title"),
            "chars": res.get("chars"), "ok": res.get("ok"),
            "reason": res.get("reason"), "warnings": res.get("warnings"),
            "files": files, "elapsed": res.get("elapsed"),
            "requests": res.get("requests"), "finished_at": res.get("finished_at"),
            "phases": res.get("phases"),
        }
        with open(os.path.join(task_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        res["files"] = files
        res["task_dir"] = task_dir
    except Exception as e:
        res.setdefault("warnings", []).append("落盘失败：%s" % e)

    _gc()
    return res


def _gc(keep: int = 60):
    """只留最近 60 次抓取，避免无限占地。"""
    try:
        if not os.path.isdir(DATA_DIR):
            return
        dirs = [os.path.join(DATA_DIR, d) for d in os.listdir(DATA_DIR)
                if os.path.isdir(os.path.join(DATA_DIR, d))]
        dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for p in dirs[keep:]:
            import shutil
            shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass


# ============================================================
# 面向搭子的封装
# ============================================================
def deliver(text: str, **opts) -> dict:
    """从一段话里认出链接，抓回来。多个链接只抓第一个主链接。"""
    urls = extract_urls(text)
    if not urls:
        return {"ok": False, "reason": "这句话里没有链接", "url": ""}
    res = fetch(urls[0], query=text, **opts)
    res["requested"] = urls
    return res


def chat_brief(res: dict) -> str:
    """给模型的上下文：告诉它数据已到手，只能用这部分内容，别编。"""
    if not res or not res.get("ok"):
        why = (res or {}).get("reason") or "未知原因"
        return ("\n\n【Shannon 取数结果】链接已尝试，但没取到可用数据（%s）。"
                "回答时要如实说明：没拿到，不要凭空补内容；可以给出可选的替代做法。"
                % why)
    parts = ["\n\n【Shannon 已取回链接数据（下面是真实抓到的内容，直接用它作答，不要编造）】",
             "来源：%s" % res.get("url", ""),
             "标题：%s" % (res.get("title") or "（无标题）"),
             "正文规模：%d 字；请求 %d 次、耗时 %.1f 秒" %
             (res.get("chars", 0), res.get("requests", 0), res.get("elapsed", 0))]
    meta = res.get("meta") or {}
    bits = []
    if meta.get("author"):
        bits.append("作者 " + meta["author"])
    if meta.get("published"):
        bits.append("时间 " + meta["published"])
    if meta.get("site"):
        bits.append("站点 " + meta["site"])
    if bits:
        parts.append("· " + "；".join(bits))
    if res.get("headings"):
        h = " / ".join(x["text"] for x in res["headings"][:10])
        parts.append("· 结构：" + h[:300])
    if res.get("warnings"):
        parts.append("· 提示：" + "；".join(res["warnings"]))
    body = res.get("markdown") or res.get("text") or ""
    body = body[:16000]
    parts.append("\n--- 原文节选 ---\n" + body)
    if res.get("kind") == "file":
        parts.append("\n注意：用户给的是文件直链，已原样落盘。如实告诉用户可以直接下载；"
                     "若抽不出文字，不要假装读过内容。")
    if len(res.get("markdown") or res.get("text") or "") > 16000:
        parts.append("\n（原文更长，完整版已存成文件，回答时说明可下载，不要假装读完了全部）")
    parts.append("\n回答要求：先把这批数据是什么、有什么关键信息讲清楚，再按用户的问题作答；"
                 "数字、人名、时间、原话必须来自上面的内容。用户要的是数据本身，不要写成读后感。")
    return "\n".join(parts)


def chat_attach(res: dict) -> str:
    """给用户看的附件清单（放在回答末尾）。"""
    if not res:
        return ""
    files = res.get("files") or []
    if not files:
        return ""
    head = "\n\n---\n\n**数据已落盘**（共 %d 字，请求 %d 次）\n" % (
        res.get("chars", 0), res.get("requests", 0))
    lines = []
    for f in files:
        if f["name"] == "bundle.zip":
            lines.append("· 全部打包：[%s](%s)（%.1f KB）" %
                         (f["name"], f["url"], f["size"] / 1024.0))
        elif f["name"] in ("report.md", "content.txt", "data.json"):
            lines.append("· [%s](%s)（%.1f KB）" % (f["name"], f["url"], f["size"] / 1024.0))
        elif f["name"] not in ("raw.html", "tables.csv", "manifest.json"):
            lines.append("· 文件 [%s](%s)（%.1f KB）" % (f["name"], f["url"], f["size"] / 1024.0))
    assets = res.get("assets") or []
    for a in assets[:5]:
        lines.append("· 附件 [%s](%s)（%.1f KB）" %
                     (a["name"], (a.get("file") or {}).get("url", ""), a["size"] / 1024.0))
    if len(assets) > 5:
        lines.append("· 其余 %d 个附件见 bundle.zip" % (len(assets) - 5))
    return head + "\n".join(lines)


def file_path(task_id: str, name: str) -> str:
    """下载路径：只允许落在对应任务目录内。"""
    tid = re.sub(r"[^\w\-.]", "", str(task_id or ""))
    root = os.path.realpath(os.path.join(DATA_DIR, tid))
    p = os.path.realpath(os.path.join(root, str(name or "").lstrip("/\\")))
    if not p.startswith(root + os.sep) or not os.path.isfile(p):
        return ""
    return p


def public(res: dict) -> dict:
    """给前端的最小结果。"""
    if not res:
        return {}
    return {
        "ok": bool(res.get("ok")), "task_id": res.get("task_id"), "url": res.get("url"),
        "final_url": res.get("final_url"), "title": res.get("title"),
        "chars": res.get("chars"), "requests": res.get("requests"),
        "elapsed": res.get("elapsed"), "blocked": res.get("blocked"),
        "reason": res.get("reason"), "warnings": res.get("warnings") or [],
        "files": [{"name": f["name"], "size": f["size"], "url": f["url"]}
                  for f in (res.get("files") or [])],
    }


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    out = fetch(target, budget=60, pages=2)
    print(json.dumps(public(out), ensure_ascii=False, indent=2))
    print("\n--- 预览 ---\n")
    print((out.get("preview") or "")[:3000])
