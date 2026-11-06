# -*- coding: utf-8 -*-
"""自建同步中心（零成本）：让桌面端 / 网页端 / 安卓端共用同一份书稿。

设计要点
--------
1. 任意一端可当「同步中心」（hub），其余端是「客户端」（client）。
   - hub：本机 8765 照旧自用，另在 8766 上开一个局域网监听，手机同 WiFi 直连。
   - 需要人不在家也能同步时，勾选「公网隧道」，本模块自动下载免费的
     cloudflared 并起一条 quick tunnel，拿到 https://xxx.trycloudflare.com。
2. 数据单元是 projects/<书名>.json。合并粒度到「章节」：
   以每个章节 id 做三方合并（本地 / 远端 / 共同基线 rev 快照）。
   两边都改了同一章 → 远端优先，本地那份另存成「冲突副本」章节，绝不静默丢稿。
3. 版本号（rev）由 hub 维护；每次内容变化写一份快照，客户端带着 base_rev 推，
   hub 用快照做三方合并后回传合并结果。
4. 除书稿外不动 settings.json（不吃用户的 API Key），封面等二进制暂不同步。

本模块只做引擎，HTTP 路由在 server.py 里注册。
"""
import os
import re
import sys
import json
import time
import shutil
import hashlib
import socket
import threading
import subprocess
from datetime import datetime

try:
    import requests
except Exception:          # 安卓极端环境兜底
    requests = None

# ------------------------------------------------------------------ 运行时状态
_ctx = {}                  # data_dir / projects_dir / get_project / save_project / list_names
_cfg = {"enabled": False, "role": "off", "hub_url": "", "token": "", "tunnel": False}
_revs = {"revs": {}, "hashes": {}, "tombs": {}}
_state = {"device": "", "revs": {}, "hashes": {}, "last_sync": "", "pulled_stamp": 0}
_lock = threading.RLock()
_wake = threading.Event()
_worker = None
_worker_gen = 0
_log = []
_last_error = ""
_note = ""
_public_url = ""
_tunnel_proc = None
_tunnel_reader = None
_lan_server = None
_lan_port = 0
_access_port = 0
_bind_all = False
_apply_depth = 0
_pulled_stamp = 0
_snapshot_keep = 6

BASE_DIR = ""
REVS_FILE = ""
STATE_FILE = ""
SNAP_DIR = ""


# ------------------------------------------------------------------ 基础工具
def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _h(obj):
    """结构化哈希：忽略 updated_at，避免保存时刷新时间戳被当成内容变化"""
    if isinstance(obj, dict):
        obj = {k: v for k, v in obj.items() if k not in ("updated_at",)}
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _log_line(msg):
    _log.append({"t": _now(), "m": str(msg)[:300]})
    del _log[:-40]


def _new_device():
    try:
        host = socket.gethostname().lower()
    except Exception:
        host = "device"
    host = re.sub(r"[^a-z0-9]+", "-", host)[:18] or "device"
    if os.environ.get("FJ_ANDROID"):
        return "android-" + host
    return ("pc-" if sys.platform.startswith("win") else sys.platform + "-") + host


def _lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


# ------------------------------------------------------------------ 初始化
def init(data_dir, projects_dir, get_project, save_project, list_names):
    """server.py 启动时调用一次"""
    global _ctx, BASE_DIR, REVS_FILE, STATE_FILE, SNAP_DIR, _revs, _state
    _ctx = {
        "data_dir": data_dir,
        "projects_dir": projects_dir,
        "get_project": get_project,
        "save_project": save_project,
        "list_names": list_names,
    }
    BASE_DIR = data_dir
    REVS_FILE = os.path.join(data_dir, "sync_revs.json")
    STATE_FILE = os.path.join(data_dir, "sync_state.json")
    SNAP_DIR = os.path.join(data_dir, "sync_base")
    os.makedirs(SNAP_DIR, exist_ok=True)

    _revs = _read_json(REVS_FILE, {}) or {}
    _revs.setdefault("revs", {})
    _revs.setdefault("hashes", {})
    _revs.setdefault("tombs", {})

    _state = _read_json(STATE_FILE, {}) or {}
    _state.setdefault("device", _new_device())
    _state.setdefault("revs", {})
    _state.setdefault("hashes", {})
    _state.setdefault("last_sync", "")
    _state.setdefault("pulled_stamp", 0)


def configure(settings):
    """把 settings.json 里的同步配置同步到本模块；返回需要回写的配置（可能补了 token）"""
    global _cfg
    cfg = {
        "enabled": bool(settings.get("sync_enabled")),
        "role": (settings.get("sync_role") or "off").strip(),
        "hub_url": (settings.get("sync_hub_url") or "").strip().rstrip("/"),
        "token": (settings.get("sync_token") or "").strip(),
        "tunnel": bool(settings.get("sync_tunnel")),
    }
    if cfg["role"] not in ("off", "hub", "client"):
        cfg["role"] = "off"
    if cfg["enabled"] and cfg["role"] != "off" and not cfg["token"]:
        cfg["token"] = new_token()
    _cfg = cfg
    return dict(cfg)


def new_token():
    import secrets
    return secrets.token_hex(12)


def boot(app, port, bind_all=False):
    """服务起来后调用：按配置拉起后台线程 / 局域网监听 / 公网隧道"""
    global _lan_server, _lan_port, _access_port, _bind_all
    _bind_all = bool(bind_all)
    _stop_worker()
    if not _cfg["enabled"] or _cfg["role"] == "off":
        _access_port = 0
        return
    if _cfg["role"] == "hub":
        if _bind_all:
            _access_port = port           # 网页版本来就监听 0.0.0.0
        else:
            _ensure_lan_listener(app, port)
            _access_port = _lan_port      # 局域网监听端口（8766 这类）
        if _cfg["tunnel"]:
            _ensure_tunnel(port)
    else:
        _access_port = 0
    _start_worker()


# ------------------------------------------------------------------ 版本与快照
def _snap_path(name, rev):
    return os.path.join(SNAP_DIR, _safe(name), "r%d.json" % rev)


def _save_snapshot(name, rev, project):
    if project is None or rev <= 0:
        return
    d = os.path.join(SNAP_DIR, _safe(name))
    os.makedirs(d, exist_ok=True)
    _write_json(_snap_path(name, rev), project)
    files = sorted(
        [f for f in os.listdir(d) if f.endswith(".json")],
        key=lambda f: int(f[1:-5]) if f[1:-5].isdigit() else 0,
    )
    for old in files[:-_snapshot_keep]:
        try:
            os.remove(os.path.join(d, old))
        except Exception:
            pass


def _load_snapshot(name, rev):
    if not rev:
        return None
    return _read_json(_snap_path(name, rev), None)


def _bump(name, project):
    """hub 侧：内容变化 → rev+1 并落快照"""
    with _lock:
        rev = int(_revs["revs"].get(name, 0)) + 1
        _revs["revs"][name] = rev
        _revs["hashes"][name] = _h(project)
        if name in _revs["tombs"]:
            _revs["tombs"].pop(name, None)
        _save_snapshot(name, rev, project)
        _write_json(REVS_FILE, _revs)
        return rev


def _tombstone(name):
    with _lock:
        rev = int(_revs["revs"].get(name, 0)) + 1
        _revs["revs"].pop(name, None)
        _revs["hashes"].pop(name, None)
        _revs["tombs"][name] = {"rev": rev, "at": _now()}
        _write_json(REVS_FILE, _revs)
        return rev


def hub_get(name):
    p = _ctx["get_project"](name)
    if p is None:
        return None
    return {"project": p, "rev": int(_revs["revs"].get(name, 0))}


def manifest():
    with _lock:
        return {
            "revs": dict(_revs["revs"]),
            "tombs": dict(_revs["tombs"]),
            "count": len(_revs["revs"]),
            "ts": _now(),
        }


# ------------------------------------------------------------------ 合并
def _files_map(p):
    return {f.get("id"): f for f in (p.get("_files") or []) if isinstance(f, dict) and f.get("id")}


def _conflict_copy(item):
    if not isinstance(item, dict):
        return None
    cp = json.loads(json.dumps(item, ensure_ascii=False))
    cp["id"] = "%s__cf%s" % (item.get("id") or "x", int(time.time() * 1000) % 100000000)
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", str(cp.get("name") or "未命名"))
    cp["name"] = "%s［冲突副本 %s］" % (stem, datetime.now().strftime("%m%d %H:%M"))
    cp["lastModified"] = int(time.time() * 1000)
    return cp


def _deep_merge(local, remote, base):
    """字典/列表的温和合并：远端优先，但尽量保留本地新增"""
    if isinstance(local, dict) and isinstance(remote, dict):
        out = dict(remote)
        b = base if isinstance(base, dict) else {}
        for k, v in local.items():
            if k not in remote:
                if _h(v) != _h(b.get(k)):      # 本地新增的键，留下
                    out[k] = v
            else:
                out[k] = _deep_merge(v, remote[k], b.get(k))
        return out
    if isinstance(local, list) and isinstance(remote, list):
        keyf = None
        if all(isinstance(x, dict) and x.get("id") for x in remote + local):
            keyf = lambda x: x.get("id")
        elif all(isinstance(x, dict) and x.get("name") for x in remote + local):
            keyf = lambda x: x.get("name")
        if keyf:
            bmap = {keyf(x): x for x in base} if isinstance(base, list) else {}
            lmap = {keyf(x): x for x in local}
            out, seen = [], set()
            for x in remote:
                k = keyf(x)
                seen.add(k)
                if k in lmap and k in bmap:
                    out.append(_deep_merge(lmap[k], x, bmap[k]))
                else:
                    out.append(x)
            for x in local:
                if keyf(x) not in seen:
                    out.append(x)
            return out
        return remote
    return remote


def merge_project(local, remote, base):
    """三方合并，返回 (merged, conflicts)"""
    if not isinstance(local, dict):
        return remote, 0
    if not isinstance(remote, dict):
        return local, 1
    res = dict(remote)
    conflicts = 0
    lmap, rmap = _files_map(local), _files_map(remote)
    bmap = _files_map(base) if isinstance(base, dict) else {}

    order = []
    for f in (remote.get("_files") or []):
        if isinstance(f, dict) and f.get("id") and f["id"] not in order:
            order.append(f["id"])
    for f in (local.get("_files") or []):
        if isinstance(f, dict) and f.get("id") and f["id"] not in order:
            order.append(f["id"])

    out_files = []
    for fid in order:
        l, r, b = lmap.get(fid), rmap.get(fid), bmap.get(fid)
        if r is None and l is None:
            continue
        if r is None:                       # 远端删了
            if l and (b is None or _h(l) != _h(b)):   # 本地新增/改过 → 不丢
                out_files.append(l)
            continue
        if l is None:                       # 本地没有这一章
            if b is None or _h(r) != _h(b):  # 远端新增/改过 → 留下
                out_files.append(r)
            continue
        if _h(l) == _h(r):
            out_files.append(r)
            continue
        if b is None:
            lc = rc = True
        else:
            lc = _h(l) != _h(b)
            rc = _h(r) != _h(b)
            if not lc and not rc:
                out_files.append(r)
                continue
            if lc and not rc:
                out_files.append(l)
                continue
            if rc and not lc:
                out_files.append(r)
                continue
        # 两边都改了：时间新的留正文，另一份做冲突副本
        lm = l.get("lastModified") or 0
        rm = r.get("lastModified") or 0
        if lm > rm:
            out_files.append(l)
            cp = _conflict_copy(r)
        else:
            out_files.append(r)
            cp = _conflict_copy(l)
        if cp:
            out_files.append(cp)
        conflicts += 1

    if "_files" in remote or "_files" in local:
        res["_files"] = out_files

    keys = set(remote.keys()) | set(local.keys())
    for k in keys:
        if k in ("_files", "updated_at"):
            continue
        lv, rv = local.get(k), remote.get(k)
        if _h(lv) == _h(rv):
            res[k] = rv
            continue
        if base is None:
            res[k] = rv if _h(rv) != _h(None) else lv
            continue
        bv = base.get(k)
        lc, rc = _h(lv) != _h(bv), _h(rv) != _h(bv)
        if lc and not rc:
            res[k] = lv
        elif rc and not lc:
            res[k] = rv
        elif lc and rc:
            res[k] = _deep_merge(lv, rv, bv)
            conflicts += 1
        else:
            res[k] = rv
    return res, conflicts


# ------------------------------------------------------------------ 本地读写
def _apply_project(name, project, rev, mark_hash=True):
    """把远端合并结果落到本地，且不触发「脏」标记"""
    global _apply_depth
    _apply_depth += 1
    try:
        _ctx["save_project"](name, project)
    finally:
        _apply_depth -= 1
    # 以「落盘后再读出来」的形态做哈希，避免载入时的字段规范化造成永远「脏」
    after = _ctx["get_project"](name) or project
    with _lock:
        _state["revs"][name] = int(rev)
        if mark_hash:
            _state["hashes"][name] = _h(after)
        _state["last_sync"] = _now()
        _write_json(STATE_FILE, _state)


def touch(name):
    """server.py 每次写盘后调用：通知同步线程尽快推"""
    if _apply_depth:
        return
    if not _cfg["enabled"]:
        return
    _wake.set()


def note_rename(old, new):
    """hub 侧改名：老名字打墓碑，新名字建版"""
    if _cfg["role"] != "hub":
        return
    try:
        _tombstone(old)
        p = _ctx["get_project"](new)
        if p is not None:
            _bump(new, p)
    except Exception:
        pass


def note_delete(name):
    if _cfg["role"] != "hub":
        return
    try:
        _tombstone(name)
    except Exception:
        pass


# ------------------------------------------------------------------ hub / client
def hub_push(name, project, base_rev, device):
    """客户端推上来：快进或三方合并"""
    if not isinstance(project, dict):
        raise ValueError("project 必须是对象")
    with _lock:
        cur = _ctx["get_project"](name)
        rev = int(_revs["revs"].get(name, 0))
        base_rev = int(base_rev or 0)
        conflicts = 0
        if cur is None:
            merged = project
        elif base_rev >= rev and base_rev > 0:
            merged = project                       # 快进
        elif base_rev == rev and base_rev == 0:
            merged = project
        else:
            base = _load_snapshot(name, base_rev)
            merged, conflicts = merge_project(project, cur, base)
        new_rev = _bump(name, merged)
        if cur is not None and cur != merged:
            _ctx["save_project"](name, merged)
        _apply_project(name, merged, new_rev, mark_hash=True)
        after = _ctx["get_project"](name)
        if after is not None:
            with _lock:
                _revs["hashes"][name] = _h(after)
                _write_json(REVS_FILE, _revs)
        _log_line("合并 %s ← %s（rev %s，冲突 %s）" % (name, device or "客户端", new_rev, conflicts))
        return {"rev": new_rev, "project": merged, "conflicts": conflicts}


def hub_delete(name, base_rev):
    cur = _ctx["get_project"](name)
    if cur is not None:
        try:
            _ctx["projects_dir"] and os.remove(os.path.join(_ctx["projects_dir"], _safe(name) + ".json"))
        except Exception:
            pass
    rev = _tombstone(name)
    with _lock:
        _state["revs"][name] = rev
        _state["hashes"].pop(name, None)
        _write_json(STATE_FILE, _state)
    return {"rev": rev}


def _hub_publish_local():
    """hub 自己也是设备：本机改了书就直接升版本"""
    names = _ctx["list_names"]() or []
    with _lock:
        known = set(_revs["hashes"].keys())
        for name in names:
            p = _ctx["get_project"](name)
            if p is None:
                continue
            h = _h(p)
            if _revs["hashes"].get(name) != h:
                rev = _bump(name, p)
                if known and name not in known:
                    _log_line("登版 %s（rev %s）" % (name, rev))
        # 本机删除的书：打墓碑（只在曾经登过版的范围内判断）
        for name in list(known):
            if name in _revs["tombs"]:
                continue
            if not os.path.isfile(os.path.join(_ctx["projects_dir"], _safe(name) + ".json")):
                if _ctx["get_project"](name) is None:
                    _revs["hashes"].pop(name, None)
                    _revs["revs"].pop(name, None)
                    _write_json(REVS_FILE, _revs)


def _headers():
    return {
        "X-Sync-Token": _cfg["token"],
        "X-Sync-Device": _state.get("device", ""),
        "Content-Type": "application/json",
    }


def _remote(path, method="GET", body=None, timeout=10):
    if requests is None:
        raise RuntimeError("缺少 requests 组件")
    url = _cfg["hub_url"].rstrip("/") + path
    r = requests.request(method, url, headers=_headers(), json=body, timeout=timeout)
    if r.status_code == 401:
        raise PermissionError("同步令牌不正确")
    if r.status_code >= 400:
        raise RuntimeError("同步中心返回 %s：%s" % (r.status_code, (r.text or "")[:120]))
    return r.json()


def _client_cycle():
    global _last_error, _pulled_stamp
    if not _cfg["hub_url"]:
        raise RuntimeError("还没有填写同步中心地址")
    remote = _remote("/api/sync/manifest")
    rrevs = remote.get("revs") or {}
    rtomb = remote.get("tombs") or {}
    names = _ctx["list_names"]() or []

    changed = False
    # 1) 远端删除
    for name, t in rtomb.items():
        lrev = int(_state["revs"].get(name, 0))
        if int(t.get("rev") or 0) > lrev:
            p = os.path.join(_ctx["projects_dir"], _safe(name) + ".json")
            if os.path.isfile(p):
                try:
                    trash = os.path.join(_ctx["projects_dir"], "_trash")
                    os.makedirs(trash, exist_ok=True)
                    os.replace(p, os.path.join(trash, "%s_sync%s.json" % (_safe(name), int(time.time()))))
                except Exception:
                    pass
                _log_line("远端删除 %s，已移到回收站" % name)
                changed = True
            _state["revs"][name] = int(t.get("rev") or 0)
            _state["hashes"].pop(name, None)

    all_names = sorted(set(names) | set(rrevs.keys()))
    for name in all_names:
        if name in rtomb:
            continue
        local = _ctx["get_project"](name) if name in names else None
        lrev = int(_state["revs"].get(name, 0))
        rrev = int(rrevs.get(name, 0))

        # 本地没了，曾经同步过 → 向上游报删除（先确认文件真的不在，避免读到写盘中间态误删）
        if local is None and lrev > 0 and rrev >= lrev:
            fp = os.path.join(_ctx["projects_dir"], _safe(name) + ".json")
            if os.path.isfile(fp):
                continue
            try:
                _remote("/api/sync/delete", "POST", {"name": name, "base_rev": lrev})
                _state["revs"].pop(name, None)
                _state["hashes"].pop(name, None)
                _log_line("已通知同步中心删除 %s" % name)
                changed = True
            except Exception as e:
                _last_error = str(e)[:200]
            continue

        if local is None:
            if rrev <= lrev:
                continue
            got = _remote("/api/sync/project?name=%s" % requests_quote(name))
            _apply_project(name, got["project"], got["rev"], mark_hash=True)
            _log_line("拉取 %s（rev %s）" % (name, got["rev"]))
            changed = True
            continue

        lh = _h(local)
        dirty = lh != _state["hashes"].get(name) or name not in _state["revs"]
        if dirty:
            out = _remote("/api/sync/push", "POST", {
                "name": name, "base_rev": lrev, "project": local,
                "device": _state.get("device"),
            }, timeout=30)
            _apply_project(name, out["project"], out["rev"], mark_hash=True)
            _log_line("推送 %s（rev %s，冲突 %s）" % (name, out["rev"], out.get("conflicts", 0)))
            changed = True
        elif rrev > lrev:
            got = _remote("/api/sync/project?name=%s" % requests_quote(name))
            _apply_project(name, got["project"], got["rev"], mark_hash=True)
            _log_line("拉取 %s（rev %s）" % (name, got["rev"]))
            changed = True

    with _lock:
        _state["last_sync"] = _now()
        if changed:
            _pulled_stamp = int(time.time())
            _state["pulled_stamp"] = _pulled_stamp
        _write_json(STATE_FILE, _state)


def requests_quote(s):
    from urllib.parse import quote
    return quote(s, safe="")


def _tick():
    global _last_error
    try:
        if _cfg["role"] == "hub":
            _hub_publish_local()
        elif _cfg["role"] == "client":
            _client_cycle()
        _last_error = ""
    except PermissionError as e:
        _last_error = str(e)
    except Exception as e:
        _last_error = str(e)[:200]


def _worker_main(gen):
    while _worker_gen == gen:
        _wake.wait(6.0)
        _wake.clear()
        if _worker_gen != gen:
            break
        try:
            _tick()
        except Exception:
            pass


def _start_worker():
    global _worker, _worker_gen
    _worker_gen += 1
    gen = _worker_gen
    _worker = threading.Thread(target=_worker_main, args=(gen,), daemon=True)
    _worker.start()


def _stop_worker():
    global _worker_gen
    _worker_gen += 1
    _wake.set()


def run_now():
    _wake.set()
    _tick()
    return status()


# ------------------------------------------------------------------ 局域网监听
def _ensure_lan_listener(app, port):
    global _lan_server, _lan_port, _note
    if _lan_server:
        return
    if os.environ.get("FJ_ANDROID"):
        return                     # 手机端不能被外部反连，只当客户端
    try:
        import uvicorn
    except Exception:
        _note = "缺少 uvicorn，无法监听局域网"
        return

    p = port + 1
    for _ in range(12):
        s = socket.socket()
        try:
            s.bind(("0.0.0.0", p))
            s.close()
            break
        except Exception:
            p += 1
        finally:
            try:
                s.close()
            except Exception:
                pass
    else:
        _note = "找不到可用端口开局域网监听"
        return

    cfg = uvicorn.Config(app, host="0.0.0.0", port=p, log_level="warning")
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    _lan_server = srv
    _lan_port = p
    _log_line("局域网同步端口 %s 已开" % p)


# ------------------------------------------------------------------ 公网隧道
TUNNEL_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"


def _cloudflared_path():
    d = os.path.join(BASE_DIR, "bin")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "cloudflared.exe" if sys.platform.startswith("win") else "cloudflared")


def _download_cloudflared():
    global _note
    path = _cloudflared_path()
    if os.path.isfile(path) and os.path.getsize(path) > 5 * 1024 * 1024:
        return path
    if not sys.platform.startswith("win"):
        raise RuntimeError("公网隧道仅桌面端支持")
    _note = "正在下载 cloudflared（免费、约 40MB，只需一次）…"
    tmp = path + ".part"
    with requests.get(TUNNEL_URL, stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1024 * 512):
                if chunk:
                    f.write(chunk)
    os.replace(tmp, path)
    _note = "cloudflared 下载完成"
    return path


def _ensure_tunnel(port):
    global _tunnel_proc, _tunnel_reader, _public_url, _note
    if _tunnel_proc and _tunnel_proc.poll() is None:
        return
    if os.environ.get("FJ_ANDROID") or not sys.platform.startswith("win"):
        _note = "手机端不支持公网隧道，请用局域网地址"
        return

    def _run():
        global _tunnel_proc, _tunnel_reader, _public_url, _note
        try:
            exe = _download_cloudflared()
        except Exception as e:
            _note = "下载 cloudflared 失败：%s" % e
            return
        try:
            creation = 0x08000000 if sys.platform.startswith("win") else 0
            proc = subprocess.Popen(
                [exe, "tunnel", "--url", "http://127.0.0.1:%d" % port, "--no-autoupdate"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=creation,
            )
            _tunnel_proc = proc
            _note = "正在建立公网隧道…"
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace")
                m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if m and not _public_url:
                    _public_url = m.group(0)
                    _note = "公网地址已就绪"
                    _log_line("公网隧道：%s" % _public_url)
        except Exception as e:
            _note = "隧道启动失败：%s" % e

    _tunnel_reader = threading.Thread(target=_run, daemon=True)
    _tunnel_reader.start()


def stop_tunnel():
    global _tunnel_proc, _public_url, _note
    if _tunnel_proc:
        try:
            _tunnel_proc.kill()
        except Exception:
            pass
    _tunnel_proc = None
    _public_url = ""
    _note = ""


# ------------------------------------------------------------------ 状态
def status():
    lan = []
    if _cfg["role"] == "hub" and _access_port:
        lan = ["http://%s:%d" % (ip, _access_port) for ip in _lan_ips()]
    tunnel_alive = bool(_tunnel_proc and _tunnel_proc.poll() is None)
    return {
        "enabled": _cfg["enabled"],
        "role": _cfg["role"],
        "device": _state.get("device", ""),
        "hub_url": _cfg["hub_url"],
        "token": _cfg["token"],
        "tunnel": bool(_cfg["tunnel"]),
        "tunnel_alive": tunnel_alive,
        "public_url": _public_url,
        "lan_urls": lan,
        "lan_port": _lan_port,
        "last_sync": _state.get("last_sync", ""),
        "last_error": _last_error,
        "note": _note,
        "pulled_stamp": _state.get("pulled_stamp", 0),
        "projects": len(_state["revs"]) if _cfg["role"] != "hub" else len(_revs["revs"]),
        "log": list(_log[-12:]),
    }


def reset_client_cache():
    """清掉客户端同步缓存（换服务器时用）"""
    with _lock:
        _state["revs"] = {}
        _state["hashes"] = {}
        _state["pulled_stamp"] = 0
        _write_json(STATE_FILE, _state)


def verify_token(token):
    return bool(_cfg["token"]) and token == _cfg["token"]
