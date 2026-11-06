# -*- coding: utf-8 -*-
"""给搭子大脑投喂：GitHub 周榜前三、公开写作技法文章、公版小说片段。

注意：
- 只抓公开可访问内容；公版/开放许可文本入库，受版权保护的作品只存"技法规则"与短摘要。
- GitHub 只读 README/SKILL.md 等文档并提炼规则，不下载、不执行任何第三方代码。
"""
import os
import re
import json
import time
import base64
import requests

import brain

UA = {"User-Agent": "FengHuoBrain/1.0 (+local writing assistant)"}


def _decode(resp):
    """按内容猜编码：先 utf-8，坏了再 gb18030（老站点多是 GBK）"""
    raw = resp.content or b""
    for enc in ("utf-8", "gb18030"):
        try:
            t = raw.decode(enc)
        except Exception:
            continue
        bad = t.count("\ufffd")
        if bad <= max(2, len(t) // 2000):
            return t
    return raw.decode("utf-8", "ignore")


def _get(url, timeout=30, raw=False):
    r = requests.get(url, headers=UA, timeout=timeout)
    if r.status_code >= 400:
        return ""
    return _decode(r)


def _plain(html):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", "\n", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
         .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---------------- GitHub 周榜 ----------------
def github_weekly(n=3):
    """抓 GitHub 周趋势前三（只取仓库名，不下载代码）"""
    try:
        html = _get("https://github.com/trending?since=weekly")
    except Exception:
        return []
    repos = re.findall(
        r'<h2[^>]*class="[^"]*h3[^"]*"[^>]*>\s*<a[^>]*href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"',
        html)
    if not repos:
        repos = re.findall(r'<article[^>]*>[\s\S]{0,600}?href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', html)
    seen, out = set(), []
    for r in repos:
        if r.count("/") != 1 or r in seen:
            continue
        seen.add(r)
        out.append(r)
        if len(out) >= n:
            break
    return out


def repo_readme(repo):
    """取 README 原文（GitHub API，raw）"""
    try:
        r = requests.get("https://api.github.com/repos/%s/readme" % repo,
                         headers=dict(UA, Accept="application/vnd.github.raw"), timeout=30)
        if r.status_code < 400 and len(r.text) > 200:
            return r.text[:40000]
    except Exception:
        pass
    for name in ("README.md", "readme.md", "README.rst"):
        try:
            t = _get("https://raw.githubusercontent.com/%s/HEAD/%s" % (repo, name))
            if t and len(t) > 200:
                return t[:40000]
        except Exception:
            continue
    return ""


def repo_skill(repo):
    """如果仓库带 SKILL.md（技能说明），一并读进来（只读文档，不执行代码）"""
    for name in ("SKILL.md", "skills/SKILL.md", "docs/SKILL.md"):
        try:
            t = _get("https://raw.githubusercontent.com/%s/HEAD/%s" % (repo, name))
            if t and len(t) > 200:
                return t[:40000]
        except Exception:
            continue
    return ""


def ingest_repo(repo, ai_call=None):
    """把一个仓库的知识（README + SKILL.md）消化进大脑"""
    readme = repo_readme(repo)
    skill = repo_skill(repo)
    text = (readme + "\n\n" + skill).strip()
    if len(text) < 200:
        return {"repo": repo, "docs": 0, "rules": 0, "ok": False}
    title = "%s · GitHub 周榜" % repo
    doc_id = brain.add_doc(title, text, source="github", url="https://github.com/" + repo,
                           license="见仓库 LICENSE", kind="github",
                           summary=_plain(readme)[:200])
    n = 0
    if ai_call and doc_id:
        n = brain.digest_with_ai(text, ai_call, source="github:" + repo)
    return {"repo": repo, "docs": 1 if doc_id else 0, "rules": n, "ok": bool(doc_id)}


def sync_github(ai_call=None, n=3):
    repos = github_weekly(n)
    out = []
    for r in repos:
        try:
            out.append(ingest_repo(r, ai_call))
        except Exception as e:
            out.append({"repo": r, "ok": False, "err": str(e)[:80]})
        time.sleep(0.6)
    return {"repos": repos, "result": out}


# ---------------- 公开写作文章 ----------------
_GENRE_KEYS = [
    ("悬疑", "悬疑"), ("推理", "悬疑"), ("科幻", "悬疑"), ("惊悚", "悬疑"),
    ("武侠", "东方玄幻"), ("玄幻", "东方玄幻"), ("仙侠", "东方玄幻"), ("奇幻", "东方玄幻"),
    ("历史", "历史"), ("军事", "历史"), ("战争", "历史"),
    ("言情", "言情"), ("爱情", "言情"), ("婚恋", "言情"),
    ("都市", "都市"), ("现实", "都市"), ("职场", "都市"),
]
_GUTENBERG_GENRE = {
    "23962": "东方玄幻",   # 西遊記
    "24264": "言情",       # 紅樓夢
    "23863": "历史",       # 水滸傳
    "25328": "历史",       # 豆棚閒話
}


def _genre_of(title, url):
    """按标题/URL 猜题材，猜不到记通用（去 AI 味时按题材取样本）"""
    text = "%s %s" % (title or "", url or "")
    for key, g in _GENRE_KEYS:
        if key in text:
            return g
    m = re.search(r"/pg(\d{4,6})", str(url or ""))
    if m and m.group(1) in _GUTENBERG_GENRE:
        return _GUTENBERG_GENRE[m.group(1)]
    return "通用"


def ingest_url(url, ai_call=None, kind="article", title=""):
    try:
        html = _get(url, timeout=40)
    except Exception as e:
        return {"url": url, "ok": False, "err": str(e)[:80]}
    text = _plain(html)
    text = re.sub(r"\n{3,}", "\n\n", text)[:40000]
    if len(text) < 300:
        return {"url": url, "ok": False, "err": "正文太短"}
    t = title or url.split("/")[-1][:60]
    doc_id = brain.add_doc(t, text, source="web",
                           url=url, license="公开网页（仅存摘要与规则）", kind=kind,
                           summary=text[:200])
    n = brain.digest_with_ai(text, ai_call, source=url) if (ai_call and doc_id) else 0
    st = brain.add_style(t, text, source=url, genre=_genre_of(t, url)) if doc_id else 0
    return {"url": url, "ok": bool(doc_id), "docs": 1 if doc_id else 0, "rules": n,
            "styles": 1 if st else 0}


def ingest_text(title, text, ai_call=None, source="manual", kind="doc", url=""):
    """手动投喂一段文本（用户粘贴的文章/小说片段）"""
    text = _plain(text) if "<" in text[:200] else str(text or "")
    doc_id = brain.add_doc(title, text, source=source, url=url,
                           license="用户投喂", kind=kind, summary=text[:200])
    n = brain.digest_with_ai(text, ai_call, source=source) if (ai_call and doc_id) else 0
    st = brain.add_style(title, text, source=source, genre=_genre_of(title, url)) if doc_id else 0
    return {"ok": bool(doc_id), "docs": 1 if doc_id else 0, "rules": n,
            "styles": 1 if st else 0}


# ---------------- 每日语料（公版书 + 每天现抓的优质文章） ----------------
DAILY_SOURCES = [
    # 古登堡计划：公版中文长篇小说（作者逝世逾 50 年，已进入公有领域）
    "https://www.gutenberg.org/cache/epub/23962/pg23962.txt",  # 西遊記
    "https://www.gutenberg.org/cache/epub/24264/pg24264.txt",  # 紅樓夢
    "https://www.gutenberg.org/cache/epub/23863/pg23863.txt",  # 水滸傳
    "https://www.gutenberg.org/cache/epub/25328/pg25328.txt",  # 豆棚閒話
    # 公开网络文章：写作技法/评论
    "https://www.chinawriter.com.cn/n1/2019/0203/c404030-30611662.html",
]

# 每天去这些页面找新文章（首页 + 小说/评论频道）
LIST_PAGES = [
    "https://www.chinawriter.com.cn/",
    "https://www.chinawriter.com.cn/404087/index.html",
    "https://www.chinawriter.com.cn/404029/index.html",
    "https://www.chinawriter.com.cn/404018/index.html",
]
_ARTICLE_RE = re.compile(r"https?://www\.chinawriter\.com\.cn/n1/\d{4}/\d{4}/c\d+-\d+\.html")


def discover_articles(n=6, pages=None):
    """抓列表页，找出还没入库的文章链接（新的在前）"""
    seen, out = set(), []
    for page in (pages or LIST_PAGES):
        try:
            html = _get(page, timeout=30)
        except Exception:
            continue
        for u in _ARTICLE_RE.findall(html or ""):
            if u in seen:
                continue
            seen.add(u)
            if brain.has_url(u):
                continue
            out.append(u)
            if len(out) >= n * 3:
                break
        time.sleep(0.3)
    # 链接大体按站点顺序，越靠前越新；取前 n 条
    return out[:n]


def backfill_styles(limit=10):
    """之前入库但还没抽"文风样本"的文章，补抽一下（不调模型，纯本地）"""
    n = 0
    try:
        c = brain._conn()
        rows = c.execute("SELECT id,title,url FROM docs ORDER BY id DESC LIMIT 300").fetchall()
        have = set()
        for r in c.execute("SELECT title FROM styles"):
            have.add(r[0])
        for r in rows:
            if n >= limit:
                break
            title = r["title"] or ""
            if title in have:
                continue
            chunks = c.execute("SELECT text FROM chunks WHERE doc_id=? ORDER BY seq LIMIT 8",
                               (r["id"],)).fetchall()
            text = "\n".join(x["text"] for x in chunks)
            if len(text) < 200:
                continue
            if brain.add_style(title, text, source=r["url"] or "backfill",
                               genre=_genre_of(title, r["url"])):
                n += 1
    except Exception:
        pass
    return n


def daily(ai_call=None, limit=2, articles=4):
    """每天投喂：公版书补库 + 现抓几篇没读过的优质文章，切成知识与文风样本"""
    out = []
    picked = 0
    for url in DAILY_SOURCES:
        if limit is not None and picked >= limit:
            break
        try:
            if brain.has_url(url):
                out.append({"url": url, "ok": True, "skip": "已入库"})
                continue
            out.append(ingest_url(url, ai_call))
            picked += 1
        except Exception as e:
            out.append({"url": url, "ok": False, "err": str(e)[:80]})
        time.sleep(0.4)
    # 每天现抓的新文章（这部分保证"每天都有新东西"）
    try:
        fresh = discover_articles(articles)
    except Exception:
        fresh = []
    for url in fresh:
        try:
            out.append(ingest_url(url, ai_call))
        except Exception as e:
            out.append({"url": url, "ok": False, "err": str(e)[:80]})
        time.sleep(0.5)
    return {"items": out, "fresh": len(fresh), "stats": brain.stats()}
