# -*- coding: utf-8 -*-
"""搭子的大脑：本地知识库（SQLite + FTS5 全文检索）。

存两类东西：
1) docs/chunks：优质文章、公版小说片段、写作技法长文（切块后可检索）
2) rules：从文章里消化出来的写作/编辑规则（短句、可复用、带出处）

所有数据都在数据目录 brain/brain.db，不联网也能用。
"""
import os
import re
import json
import sqlite3
import hashlib
import time
import threading

BASE = os.environ.get("FJ_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.join(BASE, "brain")
DB_PATH = os.path.join(BRAIN_DIR, "brain.db")

_INITED = set()
# 后台同步线程和接口会同时写库，SQLite 同一时刻只允许一个写者；
# 用进程内锁排队，避免互相等 busy timeout（会拖成十几秒甚至卡住启动）。
_W_LOCK = threading.RLock()


def _conn():
    os.makedirs(BRAIN_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    if DB_PATH not in _INITED:
        with _W_LOCK:
            if DB_PATH not in _INITED:
                try:
                    c.execute("PRAGMA journal_mode=WAL")
                except Exception:
                    pass
                _init(c)
                _INITED.add(DB_PATH)
    return c


def _init(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS docs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT, source TEXT, url TEXT, license TEXT, kind TEXT,
      summary TEXT, chars INTEGER, created_at INTEGER, hash TEXT UNIQUE
    );
    CREATE TABLE IF NOT EXISTS chunks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      doc_id INTEGER, seq INTEGER, text TEXT, charset TEXT
    );
    CREATE TABLE IF NOT EXISTS rules(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT, rule TEXT, example TEXT, source TEXT,
      created_at INTEGER, hash TEXT UNIQUE
    );
    CREATE TABLE IF NOT EXISTS styles(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT, source TEXT, genre TEXT, excerpt TEXT,
      metrics TEXT, created_at INTEGER, hash TEXT UNIQUE
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
    CREATE INDEX IF NOT EXISTS idx_rules_cat ON rules(category);
    CREATE INDEX IF NOT EXISTS idx_styles_genre ON styles(genre);
    """)
    try:
        c.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id');
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
          INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
          INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
        END;
        """)
    except Exception:
        pass
    c.commit()


def _h(s):
    return hashlib.sha1(str(s or "").encode("utf-8", "ignore")).hexdigest()


def _clean(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", str(s or ""), flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
         .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _split(text, size=360):
    paras = [p.strip() for p in str(text or "").split("\n") if p.strip()]
    out, cur = [], ""
    for p in paras:
        if len(cur) + len(p) <= size:
            cur += ("" if not cur else "\n") + p
        else:
            if cur:
                out.append(cur)
            while len(p) > size:
                out.append(p[:size])
                p = p[size:]
            cur = p
    if cur:
        out.append(cur)
    return out[:200]


def add_doc(title, text, source="", url="", license="", kind="doc", summary=""):
    """投喂一篇：自动切块入 chunks；重复（同 url 或同内容）直接跳过"""
    body = _clean(text)
    if len(body) < 30:
        return 0
    key = _h(url or body[:2000])
    with _W_LOCK:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO docs(title,source,url,license,kind,summary,chars,created_at,hash) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (str(title or "")[:200], str(source or "")[:80], str(url or "")[:500],
                 str(license or "")[:60], str(kind or "doc")[:20], str(summary or "")[:300],
                 len(body), int(time.time()), key))
            doc_id = c.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
            for i, ch in enumerate(_split(body)):
                c.execute("INSERT INTO chunks(doc_id,seq,text,charset) VALUES(?,?,?,?)",
                          (doc_id, i, ch, ""))
            c.commit()
            return doc_id
        except sqlite3.IntegrityError:
            c.rollback()
            return 0
        except Exception:
            c.rollback()
            return 0
        finally:
            c.close()


def add_rule(rule, category="写作", example="", source=""):
    """投喂一条写作/编辑规则（已消化过的短句）"""
    r = re.sub(r"\s+", "", str(rule or ""))
    if len(r) < 6:
        return 0
    with _W_LOCK:
        c = _conn()
        try:
            c.execute("INSERT INTO rules(category,rule,example,source,created_at,hash) VALUES(?,?,?,?,?,?)",
                      (str(category or "写作")[:20], r[:160], str(example or "")[:200],
                       str(source or "")[:120], int(time.time()), _h(r)))
            c.commit()
            return c.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        except sqlite3.IntegrityError:
            c.rollback()
            return 0
        except Exception:
            c.rollback()
            return 0
        finally:
            c.close()


def _pick_excerpt(body, size=220):
    """从一篇里挑一段最像"好文笔"的片段：有对话、有动作、不空泛"""
    flat = re.sub(r"\s*\n\s*", "", str(body or ""))
    sents = [s.strip() for s in re.split(r"(?<=[。！？!?…])", flat) if len(s.strip()) >= 6]
    if not sents:
        return ""
    best, best_s = "", -1e9
    i = 0
    while i < len(sents):
        cur, j = "", i
        while j < len(sents) and len(cur) < size:
            cur += sents[j]
            j += 1
        if len(cur) >= 80:
            dlg = cur.count("“") + cur.count("「") + cur.count('"')
            abstract = len(re.findall(r"难以言喻|五味杂陈|仿佛|似乎|不由得|心中|情绪|感受|氛围", cur))
            avg = len(cur) / max(1, j - i)
            s = dlg * 2.0 - abstract * 1.2 - abs(avg - 16) * 0.15
            if s > best_s:
                best_s, best = s, cur
        i += max(1, (j - i) // 2)
    return best[:size].strip()


def add_style(title, text, source="", genre="通用"):
    """把一篇里最见笔法的一段存进"文风样本"库，给去 AI 味当参照"""
    body = _clean(text)
    if len(body) < 200:
        return 0
    # 中文语料才收：英文 README 当不了中文小说的文笔参照
    cn = len(re.findall(r"[\u4e00-\u9fa5]", body))
    if cn < 200:
        return 0
    ex = _pick_excerpt(body)
    if len(ex) < 80:
        return 0
    sents = [s for s in re.split(r"[。！？!?…]", ex) if s.strip()]
    lens = [len(s) for s in sents] or [0]
    dlg = sum(1 for s in sents if ("“" in s or "「" in s or '"' in s))
    metrics = {"sents": len(sents), "avg": round(sum(lens) / len(lens), 1),
               "dlg": round(dlg / max(1, len(sents)), 2)}
    with _W_LOCK:
        c = _conn()
        try:
            c.execute("INSERT INTO styles(title,source,genre,excerpt,metrics,created_at,hash) "
                      "VALUES(?,?,?,?,?,?,?)",
                      (str(title or "")[:160], str(source or "")[:120], str(genre or "通用")[:20],
                       ex[:400], json.dumps(metrics, ensure_ascii=False), int(time.time()), _h(ex)))
            c.commit()
            return c.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        except sqlite3.IntegrityError:
            c.rollback()
            return 0
        except Exception:
            c.rollback()
            return 0
        finally:
            c.close()


def style_samples(genre="", k=3):
    """按题材取文风样本（先取同题材，不够再补通用的）"""
    c = _conn()
    out = []
    try:
        if genre:
            rows = c.execute("SELECT excerpt,title,genre FROM styles WHERE genre=? ORDER BY id DESC LIMIT ?",
                             (str(genre)[:20], k)).fetchall()
            out = [dict(r) for r in rows]
        if len(out) < k:
            rows = c.execute("SELECT excerpt,title,genre FROM styles WHERE genre<>? ORDER BY id DESC LIMIT ?",
                             (str(genre or ""), k - len(out))).fetchall()
            out += [dict(r) for r in rows]
    except Exception:
        out = []
    return out[:k]


def _kw(q):
    return re.findall(r"[\u4e00-\u9fa5]{2,6}|[A-Za-z]{2,}", str(q or ""))[:8]


def search(q, k=4):
    """检索文章片段：先 FTS，退化为 LIKE"""
    c = _conn()
    out = []
    words = _kw(q)
    if not words:
        return []
    try:
        expr = " OR ".join('"%s"' % w for w in words)
        rows = c.execute(
            "SELECT c.text, d.title, d.source, d.url FROM chunks_fts f "
            "JOIN chunks c ON c.id=f.rowid JOIN docs d ON d.id=c.doc_id "
            "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?", (expr, k)).fetchall()
        out = [dict(r) for r in rows]
    except Exception:
        out = []
    if not out:
        like = " OR ".join(["c.text LIKE ?"] * len(words))
        args = ["%%%s%%" % w for w in words]
        rows = c.execute(
            "SELECT c.text, d.title, d.source, d.url FROM chunks c JOIN docs d ON d.id=c.doc_id "
            "WHERE %s LIMIT ?" % like, args + [k]).fetchall()
        out = [dict(r) for r in rows]
    return out


def rules(q, k=5):
    """检索写作/编辑规则"""
    c = _conn()
    words = _kw(q)
    if not words:
        rows = c.execute("SELECT rule,category,source FROM rules ORDER BY id DESC LIMIT ?", (k,)).fetchall()
        return [dict(r) for r in rows]
    cond = " OR ".join(["rule LIKE ? OR example LIKE ?"] * len(words))
    args = []
    for w in words:
        args += ["%%%s%%" % w, "%%%s%%" % w]
    rows = c.execute(
        "SELECT rule,category,source FROM rules WHERE %s LIMIT ?" % cond, args + [k]).fetchall()
    return [dict(r) for r in rows]


def has_url(url):
    """这篇是不是已经喂过了"""
    try:
        c = _conn()
        row = c.execute("SELECT 1 FROM docs WHERE url=? LIMIT 1", (str(url or "")[:500],)).fetchone()
        return bool(row)
    except Exception:
        return False


def stats():
    c = _conn()
    d = c.execute("SELECT COUNT(*) c, COALESCE(SUM(chars),0) s FROM docs").fetchone()
    r = c.execute("SELECT COUNT(*) c FROM rules").fetchone()
    try:
        st = c.execute("SELECT COUNT(*) c FROM styles").fetchone()["c"]
    except Exception:
        st = 0
    last = c.execute("SELECT title,source,created_at FROM docs ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "docs": int(d["c"]), "chars": int(d["s"]), "rules": int(r["c"]), "styles": int(st),
        "last": (dict(last) if last else None),
        "db": DB_PATH,
    }


def digest_with_ai(text, ai_call, source=""):
    """让模型把一篇长文消化成写作规则（返回新增条数）"""
    prompt = (
        "下面是写作/小说相关的材料。请提炼成最多 6 条可直接照做的写作或编辑规则，"
        "每条一句，不超过 40 字，具体、可执行，不要空话。\n"
        "只输出 JSON 数组，元素形如 {\"category\":\"写作|编辑|节奏|对话|描写|结构\","
        "\"rule\":\"...\",\"example\":\"...\"}。\n\n材料：\n" + str(text)[:6000]
    )
    try:
        raw = ai_call(prompt)
    except Exception:
        return 0
    m = re.search(r"\[[\s\S]*\]", str(raw or ""))
    if not m:
        return 0
    try:
        items = json.loads(m.group(0))
    except Exception:
        return 0
    n = 0
    for it in items[:6]:
        if not isinstance(it, dict):
            continue
        if add_rule(it.get("rule") or "", it.get("category") or "写作",
                    it.get("example") or "", source):
            n += 1
    return n
