"""
烽火南境 — 服务端持久化存储（SQLite）

把原本散落在 projects/*.json 里的数据收进数据库，并支持多账号隔离：
- users / tokens：注册、登录、令牌
- projects：书籍（整本 JSON 存在 data 列，保持原有结构，零迁移成本）
- revisions：自动快照（替代 _backups 目录）
- user_settings：每个账号自己的 AI 配置
"""
import os
import json
import time
import sqlite3
import hashlib
import secrets
import contextlib
import contextvars
from datetime import datetime, timedelta

_CURRENT_USER = contextvars.ContextVar("fj_current_user", default=None)
_DB_PATH = None

# 云端部署时设置 DATABASE_URL（Postgres），本地不设置则继续用 SQLite
_DB_URL = (os.environ.get("DATABASE_URL") or "").strip()
_IS_PG = _DB_URL.lower().startswith(("postgres://", "postgresql://"))

if _IS_PG:
    try:
        import psycopg2
    except ImportError as _e:  # pragma: no cover
        raise RuntimeError("云端模式需要 psycopg2-binary，请先 pip install psycopg2-binary") from _e

    class _PgCursor:
        """把 sqlite3 风格的 '?' 占位符翻译成 psycopg2 的 '%s'"""

        def __init__(self, cur):
            self._cur = cur
            self._last_id = None

        def execute(self, sql, params=None):
            sql = sql.replace("?", "%s")
            self._cur.execute(sql, params or ())
            if "RETURNING" in sql.upper():
                rows = self._cur.fetchall()
                if rows:
                    self._last_id = rows[0][0]
            return self

        def executemany(self, sql, seq):
            sql = sql.replace("?", "%s")
            self._cur.executemany(sql, seq)
            return self

        def fetchone(self):
            return self._cur.fetchone()

        def fetchall(self):
            return self._cur.fetchall()

        @property
        def lastrowid(self):
            return self._last_id

    class _PgConn:
        def __init__(self, raw):
            self._raw = raw

        def cursor(self):
            return _PgCursor(self._raw.cursor())

        def execute(self, sql, params=None):
            return _PgCursor(self._raw.cursor()).execute(sql, params)

        def commit(self):
            self._raw.commit()

        def close(self):
            self._raw.close()


_INTEGRITY_ERRORS = (sqlite3.IntegrityError,) if not _IS_PG else (
    sqlite3.IntegrityError,
    psycopg2.IntegrityError,
)


# ---------------- 用户上下文 ----------------
def set_current_user(uid):
    _CURRENT_USER.set(uid)


def current_user():
    return _CURRENT_USER.get()


_PG_DDL = [
    "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE, pass_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS tokens (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS projects (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(user_id, name))",
    "CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)",
    "CREATE TABLE IF NOT EXISTS revisions (id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_revisions_project ON revisions(project_id)",
    "CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL, updated_at TEXT NOT NULL)",
]


# ---------------- 连接 ----------------
def init(db_path=None):
    global _DB_PATH
    if _IS_PG:
        conn = _conn()
        try:
            cur = conn.cursor()
            for sql in _PG_DDL:
                cur.execute(sql)
            conn.commit()
        finally:
            conn.close()
        print("☁ 数据存储：Postgres（云端）")
        return

    _DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                pass_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, name)
            );
            CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
            CREATE TABLE IF NOT EXISTS revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_revisions_project ON revisions(project_id);
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv (
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _conn():
    if _IS_PG:
        kw = {} if "sslmode" in _DB_URL else {"sslmode": "require"}
        raw = psycopg2.connect(_DB_URL, **kw)
        return _PgConn(raw)
    if not _DB_PATH:
        raise RuntimeError("cloud_store 未初始化")
    conn = sqlite3.connect(_DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=20000")
    return conn


@contextlib.contextmanager
def _db():
    conn = _conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------- 密码 / 令牌 ----------------
def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2$120000${salt}${digest.hex()}"


def _check_password(password, stored):
    try:
        algo, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iters))
        return secrets.compare_digest(calc.hex(), digest)
    except Exception:
        return False


def create_user(username, password, is_admin=False):
    username = (username or "").strip()
    if not username or not password:
        raise ValueError("用户名和密码不能为空")
    with _db() as conn:
        cur = conn.cursor()
        sql = "INSERT INTO users (username, pass_hash, created_at) VALUES (?, ?, ?)"
        if _IS_PG:
            sql += " RETURNING id"
        try:
            cur.execute(sql, (username, _hash_password(password), _now()))
        except _INTEGRITY_ERRORS:
            raise ValueError("用户名已存在")
        return cur.lastrowid


def ensure_admin():
    """首次启动创建管理员，密码写到 DATA_DIR/admin_password.txt，方便用户取"""
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] > 0:
            return None
    password = "fj" + secrets.token_hex(3)
    uid = create_user("admin", password)
    return {"id": uid, "username": "admin", "password": password}


def login(username, password):
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, pass_hash FROM users WHERE username = ?", ((username or "").strip(),))
        row = cur.fetchone()
    if not row or not _check_password(password or "", row[1]):
        return None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with _db() as conn:
        conn.execute(
            "INSERT INTO tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, row[0], _now(), expires),
        )
    return {"token": token, "user_id": row[0], "username": (username or "").strip(), "expires_at": expires}


def user_by_token(token):
    if not token:
        return None
    with _db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT u.id, u.username FROM tokens t JOIN users u ON u.id = t.user_id "
            "WHERE t.token = ? AND t.expires_at > ?",
            (token, _now()),
        )
        row = cur.fetchone()
    return {"id": row[0], "username": row[1]} if row else None


def revoke_token(token):
    with _db() as conn:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))


def user_count():
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ---------------- 书籍 ----------------
def _uid(uid=None):
    return uid or current_user() or 1


def list_projects(uid=None):
    """返回 [(name, data_dict, updated_at)]"""
    with _db() as conn:
        rows = conn.execute(
            "SELECT name, data, updated_at FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
            (_uid(uid),),
        ).fetchall()
    out = []
    for name, raw, updated in rows:
        try:
            out.append((name, json.loads(raw), updated))
        except Exception:
            out.append((name, {"_broken": True}, updated))
    return out


def get_project(name, uid=None):
    if not name:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT data FROM projects WHERE user_id = ? AND name = ?",
            (_uid(uid), name),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def project_exists(name, uid=None):
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM projects WHERE user_id = ? AND name = ?",
            (_uid(uid), name),
        ).fetchone()
    return bool(row)


def save_project(name, data, uid=None, snapshot=False):
    uid = _uid(uid)
    data.setdefault("updated_at", _now())
    raw = json.dumps(data, ensure_ascii=False)
    now = _now()
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, created_at FROM projects WHERE user_id = ? AND name = ?", (uid, name))
        row = cur.fetchone()
        if row:
            pid = row[0]
            cur.execute(
                "UPDATE projects SET data = ?, updated_at = ? WHERE id = ?",
                (raw, data.get("updated_at") or now, pid),
            )
        else:
            insert_sql = (
                "INSERT INTO projects (user_id, name, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
            )
            if _IS_PG:
                insert_sql += " RETURNING id"
            cur.execute(
                insert_sql,
                (uid, name, raw, data.get("created_at") or now, data.get("updated_at") or now),
            )
            pid = cur.lastrowid
        if snapshot:
            cur.execute(
                "INSERT INTO revisions (project_id, data, created_at) VALUES (?, ?, ?)",
                (pid, raw, now),
            )
            cur.execute(
                "DELETE FROM revisions WHERE project_id = ? AND id NOT IN "
                "(SELECT id FROM revisions WHERE project_id = ? ORDER BY id DESC LIMIT 12)",
                (pid, pid),
            )
    return pid


def rename_project(old, new, uid=None):
    uid = _uid(uid)
    with _db() as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE user_id = ? AND name = ?", (uid, new)
        ).fetchone()
        if row:
            raise ValueError("同名书籍已存在")
        conn.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE user_id = ? AND name = ?",
            (new, _now(), uid, old),
        )


def delete_project(name, uid=None):
    uid = _uid(uid)
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE user_id = ? AND name = ?", (uid, name))
        row = cur.fetchone()
        if not row:
            return False
        cur.execute("DELETE FROM revisions WHERE project_id = ?", (row[0],))
        cur.execute("DELETE FROM projects WHERE id = ?", (row[0],))
    return True


def project_names(uid=None):
    with _db() as conn:
        rows = conn.execute("SELECT name FROM projects WHERE user_id = ?", (_uid(uid),)).fetchall()
    return [r[0] for r in rows]


def revisions(name, uid=None):
    with _db() as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE user_id = ? AND name = ?", (_uid(uid), name)
        ).fetchone()
        if not row:
            return []
        rows = conn.execute(
            "SELECT id, created_at, length(data) FROM revisions WHERE project_id = ? ORDER BY id DESC",
            (row[0],),
        ).fetchall()
    return [{"id": r[0], "created_at": r[1], "size": r[2]} for r in rows]


# ---------------- 设置 ----------------
def get_settings(uid=None, default=None):
    uid = _uid(uid)
    with _db() as conn:
        row = conn.execute("SELECT data FROM user_settings WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        return dict(default or {})
    try:
        return json.loads(row[0])
    except Exception:
        return dict(default or {})


def put_settings(data, uid=None):
    uid = _uid(uid)
    raw = json.dumps(data, ensure_ascii=False)
    with _db() as conn:
        conn.execute(
            "INSERT INTO user_settings (user_id, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (uid, raw, _now()),
        )


# ---------------- 键值（内部杂项） ----------------
def kv_get(key, default=None):
    with _db() as conn:
        row = conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except Exception:
        return row[0]


def kv_put(key, value):
    raw = json.dumps(value, ensure_ascii=False)
    with _db() as conn:
        conn.execute(
            "INSERT INTO kv (k, v, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(k) DO UPDATE SET v = excluded.v, updated_at = excluded.updated_at",
            (key, raw, _now()),
        )


# ---------------- 迁移 ----------------
def import_json_projects(projects_dir, uid=None):
    """把旧的 projects/*.json 导入数据库（只补缺失，不覆盖）"""
    uid = _uid(uid)
    if not os.path.isdir(projects_dir):
        return 0
    imported = 0
    for fn in sorted(os.listdir(projects_dir)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        name = fn[:-5]
        if project_exists(name, uid):
            continue
        try:
            with open(os.path.join(projects_dir, fn), "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            save_project(name, data, uid)
            imported += 1
        except Exception as e:
            print(f"⚠ 迁移 {name} 失败: {e}")
    return imported
