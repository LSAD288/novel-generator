"""
烽火南境 — 小说生成器后端服务
将现有 Python 业务逻辑封装为 REST API，供 NovelIDE React 前端调用
"""
import sys
import io

# 打包成桌面程序后没有控制台，且默认代码页可能不支持 ✓ / ⚠ 等字符
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import json
import re
import math
import time
import shutil
import glob
import base64
import hashlib
import socket
import tempfile
import threading
import asyncio
from datetime import datetime
from pathlib import Path

# 程序目录（打包后为解包目录）与数据目录（exe 同级，可写）
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("FJ_DATA_DIR") or APP_DIR

# 确保工作目录正确（安卓打包后 __file__ 可能在 zip 里，切不过去也不影响）
try:
    os.chdir(APP_DIR)
except Exception:
    pass

# ============ FastAPI 导入 ============
import mimetypes
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/webp", ".webp")

try:
    from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("⚠ FastAPI 未安装，请运行: pip install fastapi uvicorn")

# 题材文笔范式库（原文文笔本身就 AI 时，用它当基准）
try:
    import style_lab
except Exception:
    style_lab = None

# AIGC 终检（规则+统计+本地检测模型融合）
try:
    import aigc_guard
except Exception:
    aigc_guard = None

# 搭子大脑：本地知识库 + 投喂
try:
    import brain
except Exception:
    brain = None
try:
    import brain_ingest
except Exception:
    brain_ingest = None

# Shannon：独立取数引擎（用户发链接时自动启用，长文直接落盘给文件）
try:
    import shannon
except Exception:
    shannon = None

# 自建同步中心：桌面端 / 网页端 / 安卓端互通
try:
    import sync_hub
except Exception:
    sync_hub = None

# ============ 导入现有业务逻辑 ============
try:
    import requests as req_lib
except ImportError:
    req_lib = None

# 动态导入现有模块
HAS_DYNAMIC_AI = False
HAS_ULTIMATE_HUMANIZER = False
HAS_CHAPTER_HELPER = False
HAS_HUMANIZATION_ENGINE = False

try:
    from 动态AI痕迹消除系统 import DynamicPromptGenerator
    HAS_DYNAMIC_AI = True
    print("✓ 动态AI痕迹消除系统已加载")
except Exception as e:
    print(f"⚠ 动态AI痕迹消除系统加载失败: {e}")

try:
    from ultimate_ai_humanizer import UltimateAIHumanizer, ultimate_humanizer
    HAS_ULTIMATE_HUMANIZER = True
    print("✓ 终极AI痕迹消除系统已加载")
except Exception as e:
    print(f"⚠ 终极AI痕迹消除系统加载失败: {e}")

try:
    from 章节生成提示词辅助模块 import ChapterPromptHelper
    HAS_CHAPTER_HELPER = True
    print("✓ 章节生成提示词辅助模块已加载")
except Exception as e:
    print(f"⚠ 章节生成提示词辅助模块加载失败: {e}")

try:
    from 动态人格情感引擎 import (
        HumanizedContentGenerator,
        AntiAIPatternInjector,
        HumanizationEvaluator
    )
    HAS_HUMANIZATION_ENGINE = True
    print("✓ 动态人格情感引擎已加载")
except Exception as e:
    print(f"⚠ 动态人格情感引擎加载失败: {e}")

# ============ 配置 ============
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
os.makedirs(PROJECTS_DIR, exist_ok=True)

# ============ 服务端存储（SQLite 多账号） ============
# FJ_CLOUD=1 时数据写进 SQLite、开启账号登录；不设置则保持原来的本地 JSON 模式
CLOUD = os.environ.get("FJ_CLOUD", "0") == "1"
DB_PATH = os.environ.get("FJ_DB_PATH") or os.path.join(DATA_DIR, "cloud.db")
DEFAULT_SETTINGS = {"api_key": "", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-flash"}

try:
    import cloud_store
except Exception as _cs_err:
    cloud_store = None
    CLOUD = False
    print(f"⚠ 数据库存储不可用，回退到本地 JSON: {_cs_err}")

if CLOUD and cloud_store:
    try:
        cloud_store.init(DB_PATH)
        print(f"✓ 数据库已就绪: {DB_PATH}")
    except Exception as _db_err:
        cloud_store = None
        CLOUD = False
        print(f"⚠ 数据库打不开，回退到本地 JSON: {_db_err}")

# ============ AIService ============
class AIService:
    """AI 内容生成服务（从烽火南境.py 提取核心逻辑）"""
    def __init__(self):
        self.api_key = ""
        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-flash"
        self.max_retries = 3
        self.retry_delay = 2
        self.cache = {}
        self.humanize_enabled = True
        self.humanize_intensity = 8
        self.humanized_gen = None
        self.anti_ai_injector = None
        self.humanization_evaluator = None

        if HAS_HUMANIZATION_ENGINE:
            self.humanized_gen = HumanizedContentGenerator()
            self.anti_ai_injector = AntiAIPatternInjector()
            self.humanization_evaluator = HumanizationEvaluator()

    def set_api_config(self, api_key, base_url=None, model=None):
        self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model

    def score_ai_traces(self, text):
        """简单AI痕迹评分（0-100，越低越像人类）"""
        score = 0
        ai_patterns = [
            r'然而', r'此外', r'与此同时', r'值得注意的是', r'总的来说',
            r'综上所述', r'显而易见', r'毋庸置疑', r'众所周知',
            r'从某种意义上说', r'在某种程度上', r'首先.*其次.*最后',
            r'不仅.*而且', r'一方面.*另一方面',
        ]
        for pat in ai_patterns:
            score += len(re.findall(pat, text)) * 5
        long_sentences = len(re.findall(r'[^。！？\n]{80,}[。！？]', text))
        score += long_sentences * 3
        return min(score, 100)

    def generate_content(self, prompt, system_prompt=None, use_cache=True):
        """核心生成方法"""
        if not self.api_key:
            raise Exception("API Key 未配置")

        if system_prompt is None:
            system_prompt = """你是作家。不是AI。不是工具。不是聊天机器人。
你是用中文写作的小说家。你的文字有温度、有瑕疵、有脾气。
写的时候像人一样思考——会犹豫、会激动、会词不达意然后再找回来。
不要完美。完美是机器的特征。"""

        cache_key = f"{system_prompt}:{prompt}"
        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]

        # 注入人格情感引擎
        if self.humanized_gen and HAS_HUMANIZATION_ENGINE:
            try:
                ctx = self.humanized_gen.build_pre_generation_context()
                if ctx.get('system_prompt_addon'):
                    system_prompt = system_prompt + "\n\n" + ctx['system_prompt_addon']
            except Exception:
                pass

        max_humanize_attempts = 3
        result_content = ""

        for humanize_attempt in range(max_humanize_attempts):
            current_prompt = prompt
            if humanize_attempt > 0:
                current_prompt = f"{prompt}\n\n【系统提醒：你的上一稿仍有机器的味道。请重新写，更随意、更松动、更像人写的。】"

            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                all_content = ""
                current_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_prompt}
                ]
                continue_count = 0
                max_continues = 5

                while True:
                    data = {
                        "model": self.model,
                        "messages": current_messages,
                        "temperature": 0.55,
                        "max_tokens": 16384,
                        "top_p": 0.9,
                        "presence_penalty": 0.8,
                        "frequency_penalty": 0.65,
                    }

                    response = None
                    for retry in range(self.max_retries):
                        try:
                            response = req_lib.post(
                                f"{self.base_url}/chat/completions",
                                headers=headers,
                                json=data,
                                timeout=300
                            )
                            if response.status_code == 200:
                                break
                            elif response.status_code == 429:
                                time.sleep(self.retry_delay * (2 ** retry))
                            elif 500 <= response.status_code < 600:
                                time.sleep(self.retry_delay * (2 ** retry))
                            else:
                                break
                        except req_lib.exceptions.Timeout:
                            if retry == self.max_retries - 1:
                                if all_content:
                                    result_content = all_content
                                    break
                                raise Exception("请求超时")
                            time.sleep(self.retry_delay * (2 ** retry))
                        except req_lib.exceptions.ConnectionError:
                            if retry == self.max_retries - 1:
                                if all_content:
                                    result_content = all_content
                                    break
                                raise Exception("网络连接失败")
                            time.sleep(self.retry_delay * (2 ** retry))

                    if response.status_code == 200:
                        result = response.json()
                        choice = result['choices'][0]
                        chunk = choice['message']['content']
                        all_content += chunk
                        finish_reason = choice.get('finish_reason', '')

                        if finish_reason != 'length' or continue_count >= max_continues:
                            break

                        continue_count += 1
                        current_messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": current_prompt},
                            {"role": "assistant", "content": all_content},
                            {"role": "user", "content": "请继续输出，不要重复已输出的内容，直接从断开处继续："}
                        ]
                    elif response.status_code == 401:
                        raise Exception("API Key 认证失败")
                    elif response.status_code == 403:
                        raise Exception("API Key 权限不足")
                    elif response.status_code == 429:
                        if all_content:
                            result_content = all_content
                            break
                        raise Exception("请求过于频繁，请稍后重试")
                    else:
                        if all_content:
                            result_content = all_content
                            break
                        raise Exception(f"API错误: {response.status_code}")

                result_content = all_content

                if humanize_attempt < max_humanize_attempts - 1:
                    ai_score = self.score_ai_traces(result_content)
                    if ai_score < 35:
                        break
                else:
                    break

            except Exception as e:
                if result_content:
                    break
                raise e

        self.cache[cache_key] = result_content
        return result_content

    def humanize_text(self, content):
        """后处理：去除AI痕迹"""
        if not self.humanize_enabled or not content:
            return content
        lines = []
        for line in content.split('\n'):
            l = line.strip()
            if not l:
                lines.append('')
                continue
            l = re.sub(r'^(然而|此外|与此同时|值得注意的是|总的来说|综上所述|显而易见|毋庸置疑|众所周知)[,，]', '', l)
            l = re.sub(r'[。！？](这[一就][切场样]?[，,]都?[在说表]明[，,]?)', '。\n', l)
            lines.append(l)
        return '\n'.join(lines)


# ============ 全局实例 ============
ai_service = AIService()

# ============ 工具函数 ============
def load_settings():
    if CLOUD and cloud_store:
        return cloud_store.get_settings(default=DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"api_key": "", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-flash"}

def save_settings(settings):
    if CLOUD and cloud_store:
        cloud_store.put_settings(settings)
        return
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def load_project(name):
    if CLOUD and cloud_store:
        return cloud_store.get_project(name)
    fp = os.path.join(PROJECTS_DIR, f"{name}.json")
    if not os.path.exists(fp):
        return None
    with open(fp, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

BACKUP_DIR = os.path.join(PROJECTS_DIR, "_backups")
_last_backup = {}


def backup_project(name):
    """每 5 分钟最多留一份项目快照，保留最近 12 份，防止误覆盖"""
    if CLOUD and cloud_store:
        return
    fp = os.path.join(PROJECTS_DIR, f"{name}.json")
    if not os.path.exists(fp):
        return
    now = time.time()
    if now - _last_backup.get(name, 0) < 300:
        return
    try:
        dst_dir = os.path.join(BACKUP_DIR, re.sub(r'[\\/:*?"<>|]', '_', name))
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        shutil.copy2(fp, dst)
        _last_backup[name] = now
        olds = sorted(glob.glob(os.path.join(dst_dir, "*.json")))
        for old in olds[:-12]:
            os.remove(old)
    except Exception as e:
        print(f"⚠ 项目备份失败: {e}")


def save_project(name, data):
    if CLOUD and cloud_store:
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snap = (time.time() - _last_backup.get(name, 0)) >= 300
        cloud_store.save_project(name, data, snapshot=snap)
        if snap:
            _last_backup[name] = time.time()
        if sync_hub:
            try:
                sync_hub.touch(name)
            except Exception:
                pass
        return
    backup_project(name)
    data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fp = os.path.join(PROJECTS_DIR, f"{name}.json")
    tmp = fp + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, fp)
    if sync_hub:
        try:
            sync_hub.touch(name)
        except Exception:
            pass


def _project_names():
    if CLOUD and cloud_store:
        return sorted(cloud_store.project_names())
    if not os.path.exists(PROJECTS_DIR):
        return []
    return [f[:-5] for f in sorted(os.listdir(PROJECTS_DIR))
            if f.endswith(".json") and not f.startswith("_")]

def list_projects():
    projects = []
    if CLOUD and cloud_store:
        rows = [(n, d) for n, d, _u in cloud_store.list_projects()]
    else:
        rows = []
        if os.path.exists(PROJECTS_DIR):
            for f in sorted(os.listdir(PROJECTS_DIR)):
                if f.endswith('.json'):
                    rows.append((f[:-5], None))
    for name, data in rows:
        try:
            if data is None:
                data = load_project(name) or {}
            files = data.get("_files", []) or []
            chapters = [x for x in files if x.get("type") == "FILE"]
            words = sum(len(re.sub(r'\s', '', x.get("content") or "")) for x in chapters)
            volumes = [x for x in files if x.get("type") == "FOLDER" and x.get("id") != "root"]
            projects.append({
                "name": name,
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "progress": data.get("progress", {}),
                "genre": data.get("genre", ""),
                "style": data.get("style", ""),
                "author": data.get("author", ""),
                "cover": data.get("cover", ""),
                "description": (data.get("description") or "")[:200],
                "chapters": len(chapters),
                "volumes": len(volumes),
                "words": words,
            })
        except Exception:
            projects.append({"name": name, "error": "数据损坏"})
    return projects

def clean_text(text):
    """去除多余标记符号"""
    text = re.sub(r'【[^】]*】', '', text)
    text = re.sub(r'[\-—]{3,}', '', text)
    text = text.strip('，。、；： \n\t')
    return text.strip()

# ============ FastAPI 应用 ============
app = FastAPI(title="烽火南境 小说生成器 API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 账号鉴权（FJ_CLOUD=1 时启用） ============
def _cloud_ready():
    return bool(CLOUD and cloud_store)


def _bearer(request):
    raw = (request.headers.get("authorization") or "").strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return (request.headers.get("x-access-token") or "").strip()


@app.middleware("http")
async def fj_auth_middleware(request: Request, call_next):
    if not _cloud_ready():
        return await call_next(request)
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)
    if path.startswith("/api/auth/") or path in ("/api/health", "/api/system/info"):
        return await call_next(request)
    user = cloud_store.user_by_token(_bearer(request))
    if not user:
        return JSONResponse({"detail": "请先登录", "need_login": True}, status_code=401)
    cloud_store.set_current_user(user["id"])
    return await call_next(request)


@app.get("/api/auth/state")
async def api_auth_state():
    if not _cloud_ready():
        return {"enabled": False, "users": 0, "need_setup": False}
    users = cloud_store.user_count()
    return {"enabled": True, "users": users, "need_setup": users == 0}


@app.post("/api/auth/register")
async def api_auth_register(data: dict, request: Request):
    if not _cloud_ready():
        raise HTTPException(status_code=400, detail="当前是单机模式，不需要注册")
    users = cloud_store.user_count()
    if users > 0:
        admin = cloud_store.user_by_token(_bearer(request))
        if not admin or admin["id"] != 1:
            raise HTTPException(status_code=403, detail="服务器已初始化，注册入口已关闭")
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    try:
        uid = cloud_store.create_user(username, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if users == 0:
        cloud_store.set_current_user(uid)
        try:
            moved = cloud_store.import_json_projects(PROJECTS_DIR, uid)
            if moved:
                print(f"✓ 已把 {moved} 本旧书迁移进数据库")
        except Exception as e:
            print("⚠ 旧书迁移失败:", e)
    result = cloud_store.login(username, password)
    if not result:
        raise HTTPException(status_code=500, detail="账号已创建，但登录失败")
    return result


@app.post("/api/auth/login")
async def api_auth_login(data: dict):
    if not _cloud_ready():
        raise HTTPException(status_code=400, detail="当前是单机模式，不需要登录")
    result = cloud_store.login(data.get("username") or "", data.get("password") or "")
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码不对")
    return result


@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    if not _cloud_ready():
        return {"enabled": False, "user": None}
    user = cloud_store.user_by_token(_bearer(request))
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return {"enabled": True, "user": user}


@app.post("/api/auth/logout")
async def api_auth_logout(request: Request):
    if _cloud_ready():
        cloud_store.revoke_token(_bearer(request))
    return {"success": True}

# ============ API 路由 ============

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


def _lan_ips():
    """本机局域网 IPv4 地址，供手机端访问"""
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


@app.get("/api/system/info")
async def api_system_info():
    """给前端 / 手机端用的运行信息"""
    host = os.environ.get("FJ_HOST", "127.0.0.1")
    port = int(os.environ.get("FJ_PORT", "8765"))
    lan = [f"http://{ip}:{port}" for ip in _lan_ips()] if host in ("0.0.0.0", "::") else []
    return {
        "version": "2.2",
        "host": host,
        "port": port,
        "data_dir": DATA_DIR,
        "lan": lan,
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
    }

# --- 项目管理 ---

@app.get("/api/projects")
async def api_list_projects():
    return {"projects": list_projects()}

@app.get("/api/projects/{name}")
async def api_get_project(name: str):
    data = load_project(name)
    if data is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return data

@app.post("/api/projects")
async def api_create_project(data: dict):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    exists = cloud_store.project_exists(name) if (CLOUD and cloud_store) else os.path.exists(os.path.join(PROJECTS_DIR, f"{name}.json"))
    if exists:
        raise HTTPException(status_code=409, detail="项目已存在")
    project = {
        "name": name,
        "genre": data.get("genre", ""),
        "style": data.get("style", ""),
        "subgenre": data.get("subgenre", "废柴逆袭"),
        "ref_author": data.get("ref_author", "天蚕土豆（斗破苍穹）"),
        "chapter_count": data.get("chapter_count", 400),
        "words_per_chapter": data.get("words_per_chapter", 2500),
        "audience": data.get("audience", "青年读者"),
        "ending": data.get("ending", "大团圆"),
        "strategy": data.get("strategy", "传统经典型"),
        "lang": data.get("lang", "硬朗简洁型"),
        "concept": {},
        "world": {},
        "characters": {"主角": [], "配角": [], "反派": []},
        "outline": {"macro": "", "detailed": {}},
        "chapters": {},
        "script": {"scenes": []},
        "progress": {"concept": False, "world": False, "characters": False, "outline": False, "writing": 0, "script": False},
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_project(name, project)
    return {"success": True, "project": project}

@app.put("/api/projects/{name}")
async def api_update_project(name: str, data: dict):
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 合并更新
    for key in ['concept', 'world', 'characters', 'outline', 'chapters', 'script', 'progress']:
        if key in data:
            project[key] = data[key]
    for key in ['genre', 'style', 'subgenre', 'ref_author', 'chapter_count', 'words_per_chapter', 'audience', 'ending', 'strategy', 'lang', 'description', 'author', 'cover', 'tags']:
        if key in data:
            project[key] = data[key]
    save_project(name, project)
    return {"success": True, "project": project}

TRASH_DIR = os.path.join(PROJECTS_DIR, "_trash")


def _cover_path(cover):
    """项目里的 cover 字段 → 本地图片路径"""
    if not isinstance(cover, str) or not cover.strip():
        return ""
    cover = cover.strip()
    if not cover.startswith("assets/covers/"):
        return ""
    return os.path.join(APP_DIR, "frontend", "assets", "covers", os.path.basename(cover))


def _drop_cover_if_unused(cover):
    """删除书籍时清掉封面图；还有别的书在用就保留"""
    path = _cover_path(cover)
    if not path or not os.path.isfile(path):
        return False
    if CLOUD and cloud_store:
        others = [d for _n, d, _u in cloud_store.list_projects()]
    else:
        others = []
        for fp in glob.glob(os.path.join(PROJECTS_DIR, "*.json")):
            try:
                with open(fp, "r", encoding="utf-8-sig") as f:
                    others.append(json.load(f))
            except Exception:
                continue
    for other in others:
        if (_cover_path(other.get("cover")) or "") == path:
            return False
    try:
        os.remove(path)
        return True
    except Exception as e:
        print(f"⚠ 删除封面失败: {e}")
        return False


@app.delete("/api/projects/{name}")
async def api_delete_project(name: str):
    """删除书籍：数据移入回收站（数据库模式下留快照）便于找回，封面图一并清除"""
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if CLOUD and cloud_store:
        os.makedirs(TRASH_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r'[\\/:*?"<>|]', '_', name)
        dst = os.path.join(TRASH_DIR, f"{safe}_{stamp}.json")
        with open(dst, 'w', encoding='utf-8') as f:
            json.dump(project, f, ensure_ascii=False, indent=2)
        cloud_store.delete_project(name)
        backup_rel = os.path.relpath(dst, PROJECTS_DIR)
    else:
        fp = os.path.join(PROJECTS_DIR, f"{name}.json")
        if not os.path.exists(fp):
            raise HTTPException(status_code=404, detail="项目不存在")
        os.makedirs(TRASH_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r'[\\/:*?"<>|]', '_', name)
        dst = os.path.join(TRASH_DIR, f"{safe}_{stamp}.json")
        os.replace(fp, dst)
        backup_rel = os.path.relpath(dst, PROJECTS_DIR)
    cover_removed = _drop_cover_if_unused(project.get("cover"))
    if sync_hub:
        try:
            sync_hub.note_delete(name)
        except Exception:
            pass
    return {
        "success": True,
        "backup": backup_rel,
        "cover_removed": cover_removed,
    }


@app.post("/api/projects/{name}/rename")
async def api_rename_project(name: str, data: dict):
    """重命名书籍（改名后原 JSON 一并迁移）"""
    new_name = (data.get("new_name") or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="新书名不能为空")
    if new_name == name:
        return {"success": True, "name": name}
    if re.search(r'[\\/:*?"<>|]', new_name):
        raise HTTPException(status_code=400, detail="书名不能包含 \\ / : * ? \" < > |")
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if CLOUD and cloud_store and cloud_store.project_exists(new_name):
        raise HTTPException(status_code=409, detail="同名书籍已存在")
    old_fp = os.path.join(PROJECTS_DIR, f"{name}.json")
    new_fp = os.path.join(PROJECTS_DIR, f"{new_name}.json")
    if not (CLOUD and cloud_store) and not os.path.exists(old_fp):
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (CLOUD and cloud_store) and os.path.exists(new_fp):
        raise HTTPException(status_code=409, detail="同名书籍已存在")
    project["name"] = new_name
    if CLOUD and cloud_store:
        save_project(new_name, project)
        cloud_store.delete_project(name)
    else:
        with open(new_fp, 'w', encoding='utf-8') as f:
            json.dump(project, f, ensure_ascii=False, indent=2)
        os.remove(old_fp)
    if sync_hub:
        try:
            sync_hub.note_rename(name, new_name)
        except Exception:
            pass
    return {"success": True, "name": new_name}


@app.post("/api/projects/{name}/bulk-chapters")
async def api_bulk_chapters(name: str, data: dict):
    """批量替换章节（整理分卷 / 排序 / 移动后一次性落库）"""
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = data.get("files")
    if not isinstance(files, list):
        raise HTTPException(status_code=400, detail="files 必须是数组")
    project["_files"] = files
    save_project(name, project)
    return {"success": True, "count": len(files)}

# --- AI 生成 ---

@app.post("/api/generate/concept")
def api_generate_concept(data: dict):
    """生成核心概念"""
    ai_service.set_api_config(
        api_key=data.get("api_key", ai_service.api_key),
        base_url=data.get("base_url", ai_service.base_url),
        model=data.get("model", ai_service.model),
    )
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    project_name = data.get("project_name", "未命名项目")
    genre = data.get("genre", "东方玄幻")
    style = data.get("style", "热血励志")
    subgenre = data.get("subgenre", "废柴逆袭")
    ref_author = data.get("ref_author", "天蚕土豆（斗破苍穹）")
    strategy = data.get("strategy", "传统经典型")
    lang = data.get("lang", "硬朗简洁型")
    audience = data.get("audience", "青年读者")
    ending = data.get("ending", "大团圆")
    chapter_count = data.get("chapter_count", 400)
    words_per_chapter = data.get("words_per_chapter", 2500)
    extra = data.get("extra", "")

    prompt = f"""# 角色设定
你是一位拥有二十年创作经验的顶级小说创意架构师。

# 任务
请根据以下参数，为一部小说进行深度概念挖掘和创意开发。

## 创作参数
- 项目名称：{project_name}
- 题材类型：{genre}
- 子类型：{subgenre}
- 风格偏好：{style}
- 叙事策略：{strategy}
- 语言风格：{lang}
- 目标受众：{audience}
- 结局偏好：{ending}
- 参考大神：{ref_author}
- 计划体量：共{chapter_count}章，每章{words_per_chapter}字
- 补充要求：{extra if extra else '无'}

## 输出要求
请按以下结构输出：

### 第一部分：【💎 一句话核心故事】（严格50-100字，严禁超限）
### 第二部分：【📖 故事主题与内核】（200-300字）
### 第三部分：【🎯 市场定位与差异化】（500字以上商业分析）
### 第四部分：【📊 剧情主线三幕式结构】（300-400字）
### 第五部分：【👤 主角定位与成长弧光】（200-300字）
### 第六部分：【🎨 风格锚点与创作指南】（200-300字）

请直接输出，不要加任何前缀说明。只输出纯文本内容本身，不要包含【】、*、#、---、「」等任何标记符号。"""

    try:
        response = ai_service.generate_content(prompt, use_cache=False)
        response = ai_service.humanize_text(response)

        def extract_section(text, header_pattern):
            pattern = header_pattern + r'\s*（[^）]*）?\s*\n?(.*?)(?=\n###|\Z)'
            m = re.search(pattern, text, re.DOTALL)
            if m:
                return clean_text(m.group(1).strip())
            pattern2 = header_pattern + r'\s*\n?(.*?)(?=\n###|\Z)'
            m = re.search(pattern2, text, re.DOTALL)
            return clean_text(m.group(1).strip()) if m else ""

        core = extract_section(response, r'【[💎]*】?\s*一句话核心故事')[:100]
        theme = extract_section(response, r'【[📖]*】?\s*故事主题与内核')
        positioning = extract_section(response, r'【[🎯]*】?\s*市场定位与差异化')
        plot_structure = extract_section(response, r'【[📊]*】?\s*剧情主线三幕式结构')
        character_arc = extract_section(response, r'【[👤]*】?\s*主角定位与成长弧光')
        style_guide = extract_section(response, r'【[🎨]*】?\s*风格锚点与创作指南')

        return {
            "success": True,
            "concept": {
                "core": core,
                "theme": theme,
                "positioning": positioning,
                "plot_structure": plot_structure,
                "character_arc": character_arc,
                "style_guide": style_guide,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/world")
def api_generate_world(data: dict):
    """生成世界观设定"""
    ai_service.set_api_config(
        api_key=data.get("api_key", ai_service.api_key),
        base_url=data.get("base_url", ai_service.base_url),
        model=data.get("model", ai_service.model),
    )
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    project_name = data.get("project_name", "")
    genre = data.get("genre", "东方玄幻")
    style = data.get("style", "热血励志")
    concept = data.get("concept", {})
    extra = data.get("extra", "")

    prompt = f"""你是一位顶级世界观架构师。请为以下小说构建完整的世界观设定。

项目名称：{project_name}
题材：{genre} | 风格：{style}

已有概念：
- 核心故事：{concept.get('core', '')[:300]}
- 主题：{concept.get('theme', '')[:200]}

补充要求：{extra if extra else '无'}

请输出以下世界观设定内容：
1. 世界背景与历史（500字以上）
2. 地理环境与势力分布（300字以上）
3. 力量体系与修炼等级（400字以上）
4. 社会结构与文化风俗（300字以上）
5. 种族与势力设定（300字以上）

请直接输出纯文本内容，不要包含任何标记符号。"""

    try:
        response = ai_service.generate_content(prompt, use_cache=False)
        response = ai_service.humanize_text(response)
        return {"success": True, "world": {"content": response}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/character")
def api_generate_character(data: dict):
    """生成人物小传"""
    ai_service.set_api_config(
        api_key=data.get("api_key", ai_service.api_key),
        base_url=data.get("base_url", ai_service.base_url),
        model=data.get("model", ai_service.model),
    )
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    project_name = data.get("project_name", "")
    genre = data.get("genre", "东方玄幻")
    role_type = data.get("role_type", "主角")
    concept = data.get("concept", {})
    world = data.get("world", {})
    extra = data.get("extra", "")

    prompt = f"""你是顶级角色设计师。请为以下小说创建{role_type}人设。

项目：{project_name} | 题材：{genre}
概念核心：{concept.get('core', '')[:200]}
世界观：{world.get('content', '')[:500] if isinstance(world, dict) else str(world)[:500]}

请为{role_type}创作详细人设：
1. 基本信息（姓名、年龄、性别、外貌特征）
2. 性格特点（核心性格、优缺点、行为习惯）
3. 背景故事（200字以上）
4. 能力设定（修炼等级、特殊能力、战斗风格）
5. 人际关系（与其他人物的关系网络）
6. 成长弧光（从初始到最终的变化）

请直接输出纯文本内容，不要包含任何标记符号。"""

    try:
        response = ai_service.generate_content(prompt, use_cache=False)
        response = ai_service.humanize_text(response)
        return {"success": True, "character": {"name": data.get("character_name", role_type), "profile": response}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/outline")
def api_generate_outline(data: dict):
    """生成故事大纲"""
    ai_service.set_api_config(
        api_key=data.get("api_key", ai_service.api_key),
        base_url=data.get("base_url", ai_service.base_url),
        model=data.get("model", ai_service.model),
    )
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    project_name = data.get("project_name", "")
    genre = data.get("genre", "东方玄幻")
    chapter_count = data.get("chapter_count", 400)
    concept = data.get("concept", {})
    world = data.get("world", {})
    characters = data.get("characters", {})
    extra = data.get("extra", "")

    prompt = f"""你是顶级故事架构师。请为以下小说创作完整大纲。

项目：{project_name} | 题材：{genre} | 共{chapter_count}章
核心故事：{concept.get('core', '')[:300]}
三幕结构：{concept.get('plot_structure', '')[:300]}

请输出：
1. 宏观大纲（全书分卷，每卷概述）
2. 前10章详细大纲（每章的内容概要）

请直接输出纯文本内容，不要包含任何标记符号。"""

    try:
        response = ai_service.generate_content(prompt, use_cache=False)
        response = ai_service.humanize_text(response)
        return {"success": True, "outline": {"macro": response}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/chapter")
def api_generate_chapter(data: dict):
    """生成章节正文"""
    ai_service.set_api_config(
        api_key=data.get("api_key", ai_service.api_key),
        base_url=data.get("base_url", ai_service.base_url),
        model=data.get("model", ai_service.model),
    )
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    project_name = data.get("project_name", "")
    chapter_num = data.get("chapter_num", 1)
    chapter_title = data.get("chapter_title", f"第{chapter_num}章")
    genre = data.get("genre", "东方玄幻")
    style = data.get("style", "热血励志")
    ref_author = data.get("ref_author", "天蚕土豆")
    words_target = data.get("words_target", 2500)
    concept = data.get("concept", {})
    outline = data.get("outline", {})
    characters = data.get("characters", {})
    world = data.get("world", {})
    prev_chapter = data.get("prev_chapter", "")
    extra = data.get("extra", "")

    prompt = f"""你是顶级网文作家，请按照以下设定创作小说章节。

项目：{project_name}
题材：{genre} | 风格：{style}
参考大神文风：{ref_author}
章节：{chapter_title}
目标字数：{words_target}字左右

核心故事：{concept.get('core', '')[:300]}
大纲参考：{str(outline.get('macro', ''))[:500]}
前章内容：{prev_chapter[:500] if prev_chapter else '无'}

写作要求：
1. 必须有完整的场景描写，让读者有画面感
2. 对话要自然，符合角色性格
3. 节奏张弛有度，高潮部分要有冲击力
4. 章末要有勾子，让读者想看下一章
5. 语言风格参考{ref_author}的写作特点

请直接输出纯文本正文内容，不要包含任何标记符号。不要写"第X章"标题。"""

    style_extra = _style_prompt(data.get("style_ref") or "")
    if style_extra:
        prompt += style_extra
    if extra:
        prompt += f"\n\n【补充要求】\n{extra[:600]}\n"

    try:
        response = ai_service.generate_content(prompt, use_cache=False)
        response = ai_service.humanize_text(response)
        _log_history("chapter", project_name, response, {"chapter": chapter_title})
        return {"success": True, "chapter": {"title": chapter_title, "content": response}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 设置 ---

@app.get("/api/settings")
async def api_get_settings():
    settings = load_settings()
    img_key = settings.get("image_api_key") or ""
    asr_key = settings.get("asr_key") or ""
    return {"api_key": settings.get("api_key", "")[:8] + "****" if settings.get("api_key") else "",
            "base_url": settings.get("base_url", "https://api.deepseek.com/v1"),
            "model": settings.get("model", "deepseek-flash"),
            "image_api_key": img_key[:6] + "****" if img_key else "",
            "image_base": settings.get("image_base", ""),
            "image_model": settings.get("image_model", ""),
            "has_image_key": bool(img_key),
            "asr_key": asr_key[:6] + "****" if asr_key else "",
            "asr_base": settings.get("asr_base", ""),
            "asr_model": settings.get("asr_model", ""),
            "has_asr_key": bool(asr_key),
            "tts_provider": settings.get("tts_provider", "auto"),
            "minimax_key": (settings.get("minimax_key") or "")[:6] + "****" if settings.get("minimax_key") else "",
            "has_minimax_key": bool(settings.get("minimax_key")),
            "minimax_model": settings.get("minimax_model", "speech-2.8-hd"),
            "volc_appid": settings.get("volc_appid", ""),
            "volc_token": (settings.get("volc_token") or "")[:6] + "****" if settings.get("volc_token") else "",
            "has_volc": bool(settings.get("volc_appid") and settings.get("volc_token")),
            "azure_key": (settings.get("azure_key") or "")[:6] + "****" if settings.get("azure_key") else "",
            "azure_region": settings.get("azure_region", "eastasia"),
            "has_azure_key": bool(settings.get("azure_key")),
            "tts_active": _tts_provider_cfg()["provider"]}

@app.put("/api/settings")
async def api_update_settings(data: dict):
    settings = load_settings()
    if "api_key" in data and data["api_key"]:
        settings["api_key"] = data["api_key"]
    if "base_url" in data:
        settings["base_url"] = data["base_url"]
    if "model" in data:
        settings["model"] = data["model"]
    for k in ("image_api_key", "image_base", "image_model", "asr_key", "asr_base", "asr_model",
              "tts_provider", "minimax_key", "minimax_model", "volc_appid", "volc_token",
              "volc_cluster", "azure_key", "azure_region"):
        if k in data:
            settings[k] = data[k]
    save_settings(settings)
    ai_service.set_api_config(
        api_key=settings.get("api_key", ""),
        base_url=settings.get("base_url", "https://api.deepseek.com/v1"),
        model=settings.get("model", "deepseek-flash"),
    )
    return {"success": True}


@app.post("/api/ai/transcribe")
async def api_ai_transcribe(file: UploadFile = File(...), language: str = Form("zh")):
    """听写：优先本机离线模型，其次 OpenAI 兼容的 /audio/transcriptions。"""
    import requests
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="录音为空，请重试")
    if len(raw) > 40 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="录音过长，请分段听写")

    # 1) 本机离线：sherpa-onnx + SenseVoice
    try:
        import local_dictation
        st = local_dictation.status(DATA_DIR)
        if st.get("installed") and st.get("has_sherpa"):
            text, err = local_dictation.transcribe_wav(raw, DATA_DIR)
            if not err:
                return {"text": text, "engine": "local"}
            last_err = err
        else:
            last_err = ""
    except Exception as e:
        last_err = ""

    # 2) 云端
    settings = load_settings()
    base = (settings.get("asr_base") or "").strip()
    key = (settings.get("asr_key") or "").strip()
    model = (settings.get("asr_model") or "").strip()
    if not base:
        main_base = (settings.get("base_url") or "").strip()
        if "siliconflow" in main_base:
            base = main_base
            key = key or (settings.get("api_key") or "")
    if not base or not key:
        detail = "未配置听写：可在 设置 → 接口 下载离线听写模型，或填写听写 Base URL / Key / 模型"
        if last_err:
            detail += "（离线转写失败：%s）" % last_err
        raise HTTPException(status_code=400, detail=detail)
    model = model or "whisper-1"
    url = base.rstrip("/") + "/audio/transcriptions"
    name = file.filename or "audio.wav"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (name, raw, file.content_type or "audio/wav")},
            data={"model": model, "language": language or "zh"},
            timeout=180,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"听写请求失败：{e}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"听写接口返回 {resp.status_code}：{resp.text[:200]}")
    try:
        payload = resp.json()
    except Exception:
        return {"text": resp.text.strip(), "engine": "cloud"}
    return {"text": str(payload.get("text") or "").strip(), "engine": "cloud"}


@app.get("/api/dictation/status")
async def api_dictation_status():
    try:
        import local_dictation
        return local_dictation.status(DATA_DIR)
    except Exception as e:
        return {"installed": False, "downloading": False, "has_sherpa": False, "error": str(e)}


@app.post("/api/dictation/download")
async def api_dictation_download():
    try:
        import local_dictation
    except Exception as e:
        raise HTTPException(status_code=500, detail="离线听写模块不可用：%s" % e)
    if not local_dictation.status(DATA_DIR).get("has_sherpa"):
        raise HTTPException(status_code=400, detail="当前环境未安装 sherpa-onnx，请先运行：python -m pip install sherpa-onnx")
    return local_dictation.start_download(DATA_DIR)


# --- 文件管理 ---

@app.get("/api/files/{project_name}")
async def api_get_files(project_name: str):
    """获取项目文件树"""
    project = load_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = project.get("_files", [])
    return {"files": files}

@app.post("/api/files/{project_name}")
async def api_save_files(project_name: str, data: dict):
    """保存项目文件树（章节数量骤减时拦截，防止旧标签页覆盖）"""
    project = load_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    incoming = data.get("files", [])
    if not isinstance(incoming, list):
        raise HTTPException(status_code=400, detail="files 必须是数组")
    old_files = project.get("_files", []) or []
    old_chapters = sum(1 for f in old_files if f.get("type") == "FILE")
    new_chapters = sum(1 for f in incoming if f.get("type") == "FILE")
    if not data.get("force") and old_chapters >= 3 and new_chapters < old_chapters * 0.5:
        raise HTTPException(
            status_code=409,
            detail=f"章节数量从 {old_chapters} 骤减到 {new_chapters}，已阻止覆盖（确认无误请带 force=true 重试）",
        )
    project["_files"] = incoming
    save_project(project_name, project)
    return {"success": True}

@app.get("/api/files/{project_name}/{file_id:path}")
async def api_get_file(project_name: str, file_id: str):
    """获取单个文件内容"""
    project = load_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = project.get("_files", [])
    # 按ID查找
    for f in files:
        if f.get("id") == file_id:
            return {"file": f}
    raise HTTPException(status_code=404, detail="文件不存在")

@app.put("/api/files/{project_name}/{file_id:path}")
async def api_update_file(project_name: str, file_id: str, data: dict):
    """更新文件内容"""
    project = load_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = project.get("_files", [])
    for i, f in enumerate(files):
        if f.get("id") == file_id:
            if "content" in data:
                f["content"] = data["content"]
            if "name" in data:
                f["name"] = data["name"]
            if "metadata" in data:
                f["metadata"] = data["metadata"]
            f["lastModified"] = int(time.time() * 1000)
            project["_files"] = files
            save_project(project_name, project)
            return {"success": True, "file": f}
    raise HTTPException(status_code=404, detail="文件不存在")

# --- 会话管理 ---

@app.get("/api/sessions/{project_name}")
async def api_get_sessions(project_name: str):
    """获取项目会话列表"""
    project = load_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    sessions = project.get("_sessions", [])
    return {"sessions": sessions}

@app.post("/api/sessions/{project_name}")
async def api_save_sessions(project_name: str, data: dict):
    """保存项目会话"""
    project = load_project(project_name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    project["_sessions"] = data.get("sessions", [])
    save_project(project_name, project)
    return {"success": True}

# --- AI Agent 对话 ---

def _flat_chapters(files):
    """按目录树顺序摊平章节（防文件夹自引用死循环）"""
    by_parent = {}
    for f in files or []:
        by_parent.setdefault(f.get("parentId") or "root", []).append(f)
    out = []
    seen = set()

    def walk(pid):
        if pid in seen:
            return
        seen.add(pid)
        for f in by_parent.get(pid, []):
            if f.get("type") == "FOLDER":
                if f.get("id") == "root":
                    continue
                walk(f.get("id"))
            elif f.get("type") == "FILE":
                out.append(f)

    walk("root")
    return out


def _flat_text(v, skip=()):
    """把嵌套的设定结构压成一行可读文本"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, bool):
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "；".join([t for t in (_flat_text(i, skip) for i in v) if t])
    if isinstance(v, dict):
        out = []
        for k, val in v.items():
            if k in skip:
                continue
            t = _flat_text(val, skip)
            if t:
                out.append(f"{k}：{t}")
        return "；".join(out)
    return str(v)


def _cn_num(s):
    s = str(s or "").strip()
    if s.isdigit():
        return int(s)
    dig = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9}
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return (dig.get(a, 1) if a else 1) * 10 + (dig.get(b, 0) if b else 0)
    n = 0
    for ch in s:
        if ch not in dig:
            return 0
        n = n * 10 + dig[ch]
    return n


def _match_chapters(chapters, question):
    """从提问里认出「第 3 章」「第五章」或章节标题关键词"""
    q = question or ""
    want = set()
    for mm in re.finditer(r"第\s*([0-9]+|[零一二三四五六七八九十百两]+)\s*章", q):
        n = _cn_num(mm.group(1))
        if n:
            want.add(n)
    hits = []
    for i, c in enumerate(chapters, 1):
        name = (c.get("name") or "").strip()
        if i in want:
            hits.append(c)
            continue
        tail = re.sub(r"^第?\s*[0-9零一二三四五六七八九十百两]+\s*章?[\s:：·、.\-]*", "", name).strip()
        if len(tail) >= 2 and (tail[:6] in q or (name and name in q)):
            hits.append(c)
    return hits


def _chapter_shingles(t, n=4):
    s = re.sub(r"\s", "", str(t or ""))
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def _guess_target_chapter(project, reply, question, chapter_id, act_chapter=""):
    """判断搭子这段稿子属于哪一章：动作/点名优先，其次按正文内容比对；拿不准就交给前端让用户确认"""
    chapters = _flat_chapters((project or {}).get("_files") or [])
    if not chapters:
        return None

    def pack(c, confident, reason, score=0.0):
        return {"id": c.get("id"), "name": (c.get("name") or "").strip(),
                "confident": bool(confident), "reason": reason, "score": round(float(score), 3)}

    if act_chapter:
        hit = _match_chapters(chapters, act_chapter)
        if len(hit) == 1:
            return pack(hit[0], True, "搭子标了章节")
    for src, why in ((reply, "回复里点名"), (question, "你点名了")):
        hits = _match_chapters(chapters, src or "")
        if len(hits) == 1:
            return pack(hits[0], True, why)

    rset = _chapter_shingles(reply)
    qset = _chapter_shingles(question)
    scored = []
    for c in chapters:
        cset = _chapter_shingles(c.get("content") or "")
        if not cset:
            continue
        rs = len(rset & cset) / len(rset) if rset else 0.0
        qs = len(qset & cset) / len(qset) if qset else 0.0
        scored.append((rs * 0.75 + qs * 0.25, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    cur = next((c for c in chapters if c.get("id") == chapter_id), None) or chapters[-1]
    if not scored:
        return pack(cur, False, "先按当前章")
    top_s, top_c = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if top_s >= 0.18 and top_s >= second * 1.35:
        return pack(top_c, True, "按内容对上的", top_s)
    base = top_c if top_s >= 0.06 else cur
    out = pack(base, False, "按内容像是这一章" if base is top_c else "先按当前章", top_s)
    out["candidates"] = [{"id": c.get("id"), "name": (c.get("name") or "").strip(), "score": round(s, 3)}
                         for s, c in scored[:4]]
    return out


def _build_agent_context(project, chapter_id, selection, question=""):
    """从项目里抽出这本书的全部事实：所有设定 + 全书目录 + 尽量多的章节原文"""
    if not project:
        return {}
    chapters = _flat_chapters(project.get("_files") or [])
    cur = next((c for c in chapters if c.get("id") == chapter_id), None)
    if cur is None and chapters:
        cur = chapters[-1]
    prev = None
    cur_detail = ""
    if cur is not None:
        idx = chapters.index(cur)
        if idx > 0:
            prev = chapters[idx - 1]
        m = re.search(r"(\d+)", cur.get("name", ""))
        detailed = (project.get("outline") or {}).get("detailed") or {}
        if m:
            d = detailed.get(str(int(m.group(1)))) or detailed.get(m.group(1))
            if isinstance(d, dict):
                cur_detail = _flat_text(d, skip=("id", "type"))

    meta = "；".join([f"{k}：{project.get(v)}" for k, v in (
        ("题材", "genre"), ("风格", "style"), ("子类型", "subgenre"), ("目标读者", "audience"),
        ("结局倾向", "ending"), ("写法策略", "strategy"), ("参考作者", "ref_author"),
        ("语言", "lang"), ("计划章数", "chapter_count"), ("每章字数", "words_per_chapter"),
    ) if project.get(v)])

    concept = _flat_text(project.get("concept") or {}, skip=("id", "type"))
    world = _flat_text(project.get("world") or {}, skip=("id", "type"))
    outline = project.get("outline") or {}
    macro = _flat_text(outline.get("macro") or "")
    detailed = outline.get("detailed") or {}
    detail_rows = []
    for k in sorted(detailed.keys(), key=lambda x: _cn_num(str(x).replace("第", "").replace("章", ""))):
        t = _flat_text(detailed.get(k), skip=("id", "type"))
        if t:
            detail_rows.append(f"第{k}章：{t[:400]}")
    fores = []
    for f in (outline.get("foreshadows") or []):
        if isinstance(f, dict) and f.get("text"):
            fores.append(("已回收：" if f.get("done") else "未回收：") + str(f["text"])[:140])
        elif isinstance(f, str) and f.strip():
            fores.append(f.strip()[:140])
    script = _flat_text(project.get("script") or "", skip=("id", "type"))[:1200]

    ppl = []
    for g, arr in (project.get("characters") or {}).items():
        if not isinstance(arr, list):
            continue
        for c in arr:
            rec = c if isinstance(c, dict) else {"name": c}
            name = str(rec.get("name") or "").strip()
            if not name:
                continue
            head = "/".join([x for x in [rec.get("role") or "", rec.get("identity") or "",
                                        rec.get("gender") or "", rec.get("age") or ""] if x])
            line = f"{g}｜{name}" + (f"（{head}）" if head else "")
            desc = rec.get("tagline") or rec.get("intro") or ""
            if desc:
                line += f"：{str(desc)[:60]}"
            extra = []
            for f, label in (("personality", "性格"), ("appearance", "外貌"), ("ability", "能力"),
                             ("goal", "目标"), ("quote", "口头禅"), ("background", "背景"), ("arc", "弧线")):
                v = str(rec.get(f) or "").strip()
                if v:
                    extra.append(f"{label}{v[:70]}")
            if extra:
                line += "；" + "；".join(extra)
            rels = "、".join([f"{r.get('target')}({r.get('type') or '关系'})"
                              for r in (rec.get("relations") or [])
                              if isinstance(r, dict) and r.get("target")])
            if rels:
                line += f"；关系：{rels}"
            ppl.append(line)
    people_text = "\n".join(ppl[:80])[:9000]

    index_rows = [f"{i}. {c.get('name') or ''}（{len(c.get('content') or '')} 字）"
                  for i, c in enumerate(chapters, 1)]

    # 正文预算：当前章必给，其次提问点名的章节，再按离当前章的远近补齐
    BUDGET = 26000
    picked = []

    def add_ch(c):
        if c is not None and all((x.get("id") != c.get("id")) for x in picked):
            picked.append(c)

    add_ch(cur)
    for c in _match_chapters(chapters, question):
        add_ch(c)
    used = sum(len(c.get("content") or "") for c in picked)
    rest = [c for c in chapters if all(x.get("id") != c.get("id") for x in picked)]
    if cur is not None and cur in chapters:
        base = chapters.index(cur)
        rest.sort(key=lambda c: abs(chapters.index(c) - base))
    for c in rest:
        ln = len(c.get("content") or "")
        if used + ln > BUDGET:
            continue
        picked.append(c)
        used += ln
    picked.sort(key=lambda c: chapters.index(c))
    full = []
    for c in picked:
        txt = c.get("content") or ""
        if not txt.strip():
            continue
        if len(txt) > 9000:
            txt = txt[:4000] + "\n……（中间省略）……\n" + txt[-4000:]
        full.append({"title": c.get("name") or "", "text": txt})

    content = (cur or {}).get("content") or ""
    return {
        "name": project.get("name", ""),
        "meta": meta,
        "settings": "\n".join([x for x in [
            f"【核心概念】{concept}" if concept else "",
            f"【世界观】{world}" if world else "",
            f"【全书大纲】{macro[:3000]}" if macro else "",
            "【分章细纲】\n" + "\n".join(detail_rows[:80]) if detail_rows else "",
            "【伏笔】" + "；".join(fores[:40]) if fores else "",
            f"【剧本设定】{script}" if script else "",
            "【人物】\n" + people_text if people_text else "",
        ] if x]),
        "chapter_index": index_rows,
        "chapters_full": full,
        "chapter_count": len(chapters),
        "total_words": sum(len(c.get("content") or "") for c in chapters),
        "cur_title": (cur or {}).get("name", ""),
        "cur_detail": cur_detail,
        "cur_content": content,
        "cur_words": len(content),
        "prev_tail": ((prev or {}).get("content") or "")[-500:],
        "selection": (selection or "")[:1600],
        "people_count": len(ppl),
        "people": [(g, c if isinstance(c, dict) else {"name": str(c)})
                   for g, arr in (project.get("characters") or {}).items() if isinstance(arr, list)
                   for c in arr][:40],
    }


# ---------- 搭子记忆：短期窗口 + 长期摘要 + 原子事实 ----------
# 参考 agent-memory（daily / long_term / topic 分层、MEMORY.md 只放高信号事实）
# 与 memory-systems（短期会话记忆 / 长期持久记忆 / 事实抽取）的做法，简化到单机单用户。
AGENT_MEM_DIR = os.path.join(DATA_DIR, "agent_memory")
_MEM_LOCK = threading.Lock()


def _mem_file(project_name):
    safe = re.sub(r'[\\/:*?"<>|]+', '_', str(project_name or '_'))[:80]
    return os.path.join(AGENT_MEM_DIR, safe + ".json")


def _load_agent_memory(project_name):
    path = _mem_file(project_name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                d.setdefault("summary", "")
                d.setdefault("facts", [])
                d.setdefault("recent", [])
                return d
        except Exception:
            pass
    return {"summary": "", "facts": [], "recent": []}


def _save_agent_memory(project_name, mem):
    try:
        os.makedirs(AGENT_MEM_DIR, exist_ok=True)
        with open(_mem_file(project_name), "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("⚠ 保存搭子记忆失败:", e)


def _memory_block(mem):
    if not mem:
        return ""
    lines = []
    if str(mem.get("summary") or "").strip():
        lines.append("【长期记忆·之前聊过的】\n" + str(mem["summary"]).strip())
    facts = [str(x).strip() for x in (mem.get("facts") or []) if str(x).strip()]
    if facts:
        lines.append("【长期记忆·已确认的事实】\n" + "\n".join("- " + x for x in facts[-16:]))
    return "\n".join(lines)


def _distill_memory(project_name, mem):
    """把较早的对话压成摘要和原子事实；保留最近 4 条原文"""
    msgs = mem.get("recent") or []
    if len(msgs) < 12:
        return mem
    old, keep = msgs[:-4], msgs[-4:]
    convo = "\n".join(("用户：" if m.get("role") == "user" else "搭子：") + str(m.get("text") or "")[:600]
                      for m in old)
    facts0 = "\n".join("- " + str(f) for f in (mem.get("facts") or [])) or "（无）"
    prompt = f"""把下面这段小说写作对话压成长期记忆，供以后接着聊时用。

已有摘要：
{mem.get('summary') or '（无）'}

已有事实：
{facts0}

新增对话：
{convo}

要求：
1. summary：把已有摘要和新增对话合成一段不超过 400 字的连贯摘要，保留：用户在写什么、定了哪些写法、改过哪一章、还有什么没做完。
2. facts：只留以后还用得上的原子事实，每条不超过 50 字，例如作者偏好、已确定的设定、已改动的章节。寒暄和一次性的讨论不要。
3. 合并已有事实并去重，最多 16 条。

只输出 JSON：{{"summary":"...","facts":["..."]}}"""
    try:
        raw = _ai_text_once(prompt, system="你在整理长期记忆，只输出 JSON。", temperature=0.2, max_tokens=4096)
        mm = re.search(r"\{[\s\S]*\}", raw or "")
        d = json.loads(mm.group(0)) if mm else {}
        summary = str(d.get("summary") or mem.get("summary") or "").strip()[:800]
        facts = [str(x).strip()[:80] for x in (d.get("facts") or []) if str(x).strip()][:16]
        mem["summary"] = summary
        if facts:
            mem["facts"] = facts
    except Exception as e:
        print("⚠ 整理搭子记忆失败:", e)
    mem["recent"] = keep
    return mem


def _remember_turn(project_name, user_msg, reply, extra_facts=None):
    if not project_name:
        return
    with _MEM_LOCK:
        mem = _load_agent_memory(project_name)
        mem.setdefault("recent", []).append({"role": "user", "text": str(user_msg or "")[:1200]})
        mem["recent"].append({"role": "assistant", "text": str(reply or "")[:1200]})
        for f in (extra_facts or []):
            f = str(f or "").strip()[:80]
            if f and f not in mem["facts"]:
                mem["facts"].append(f)
        mem["facts"] = mem["facts"][-20:]
        if len(mem["recent"]) >= 12:
            mem = _distill_memory(project_name, mem)
        _save_agent_memory(project_name, mem)


_BRAIN_THREAD = {"started": False}


def _brain_ai(prompt):
    """给大脑消化文章用的模型调用（只输出 JSON）"""
    return _ai_text_once(prompt, system="你是写作技法编辑，只输出 JSON，不解释。",
                         temperature=0.3, max_tokens=2048)


def _brain_state_path():
    return os.path.join(brain.BRAIN_DIR, "sync_state.json") if brain else ""


def _brain_state():
    p = _brain_state_path()
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _brain_state_save(st):
    p = _brain_state_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        pass


def _brain_sync_loop():
    """后台：每 6 小时同步 GitHub 周榜前三，每 24 小时投喂一批公开技法/公版文本"""
    while True:
        try:
            st = _brain_state()
            now = time.time()
            if ai_service.api_key and brain_ingest:
                if now - float(st.get("gh") or 0) > 6 * 3600:
                    brain_ingest.sync_github(_brain_ai)
                    st["gh"] = now
                    _brain_state_save(st)
                if now - float(st.get("daily") or 0) > 24 * 3600:
                    brain_ingest.daily(_brain_ai)
                    st["daily"] = now
                    _brain_state_save(st)
        except Exception as e:
            print("⚠ 搭子大脑同步失败:", e)
        time.sleep(1800)


def _brain_ensure_worker():
    if _BRAIN_THREAD["started"] or not brain or not brain_ingest:
        return
    if not getattr(ai_service, "api_key", ""):
        return
    _BRAIN_THREAD["started"] = True
    try:
        threading.Thread(target=_brain_sync_loop, daemon=True).start()
    except Exception:
        pass


def _brain_seed_styles():
    """把作家文笔库塞进大脑（幂等，重复调用不会重复写）"""
    if not brain or not style_lab:
        return 0
    n = 0
    try:
        for name, desc, principles, tags in style_lab.author_cards():
            text = "%s（%s）：%s %s" % (name, tags, desc, principles)
            if brain.add_rule(text[:160], category="文风", example=desc[:120],
                              source="作家文笔库:" + name):
                n += 1
    except Exception:
        pass
    return n


def _brain_style_samples(genre="", k=2):
    """从每天投喂出来的文风样本库里取几段参照（给去 AI 味用）"""
    if not brain:
        return []
    try:
        return brain.style_samples(genre, k)
    except Exception:
        return []


def _brain_context(q):
    """按用户这句话，从大脑里取规则与片段，拼成提示块"""
    if not brain:
        return ""
    try:
        rs = brain.rules(q, k=5)
        docs = brain.search(q, k=3)
    except Exception:
        return ""
    _brain_ensure_worker()
    if not rs and not docs:
        return ""
    lines = ["【你读过的东西（能对上就用，别照抄原文）】"]
    for r in rs:
        lines.append("- " + str(r.get("rule") or ""))
    for d in docs:
        t = re.sub(r"\s+", "", str(d.get("text") or ""))[:90]
        if t:
            lines.append("- 例：%s" % t)
    lines.append("用它们来支撑判断：举具体的例子，说具体的改法，别讲空道理。")
    return "\n".join(lines)


def _agent_system_prompt(ctx):
    """搭子的人格与工作规则：像老作者聊天，不像助手写报告"""
    name = ctx.get("name") or "这本书"
    lines = [
        f"你是《{name}》的专职写作搭档。这本书的设定、大纲、已写正文你都读过，比任何通用助手都熟。",
        "你本人是个写了十几年长篇的老作者，脾气直，话短，像在饭桌上跟人聊稿子，不像在写报告。",
    ]
    if ctx.get("memory_block"):
        lines += ["", ctx["memory_block"], "（这些是以前聊过的，别装作第一次听到。）"]
    lines += [
        "",
        "【说话方式（最容易出错，逐条照做）】",
        "- 开口就给判断，别铺垫。行就说行，不行就直说哪儿不行。",
        "- 用口语：短句、能省主语就省、偶尔反问。句子长短要错开，别每句都是一个长度。",
        "- 一般只写 2-4 段白话。除非用户明确要清单，否则不列 1/2/3、不用小标题、不加粗、不写 Markdown。",
        "- 这些腔调一律不用：首先/其次/最后、一方面…另一方面、不仅…而且、既…又…、总的来说、值得注意的是、可以看出、综上所述。",
        "- 这些词尽量少用：进行、使得、从而、进而、维度、层面、张力、氛围感、质感、内在逻辑。",
        "- 不排比，不押对仗，不每段都收一句总结，不在结尾鼓励人，不说“希望对你有帮助”“如需可以继续问我”。",
        "- 不重复用户的问题，不复述自己刚说过的话，不解释“我是怎么想的”。",
        "- 不确定就说不确定，绝不编造这本书里没有的设定、人名、地名。",
        "",
        "【口气示例】",
        "用户：这章开头怎么样？",
        "你：开头慢了。前两段全在铺景，人还没动，读者容易走神。把「他站在廊下」挪到第三句前面，先让他推门，景跟着人走。",
        "（上面只是说话的口气。真正写进正文的句子按书里的文风来，别照搬这种口气。）",
        "",
        "【工作规则】",
        "1. 只谈这本书的具体内容；建议要落到具体人物、具体场景、具体句子，不要“注意节奏”“加强人物塑造”这类空话。",
        "2. 要举例就直接写能用的正文，不要写“可以这样写：”再留空。",
        "3. 引用原文用「」。发现设定冲突，指出是哪一处和哪一处冲突，并给两个可选改法。",
        "4. 用户要正文就直接给正文（对白、动作、感官细节齐全），不要附创作说明。",
        "5. 问接下来怎么写，给 2-3 个具体走向，每个用 3-5 句写清会发生什么，再点一句哪个最贴已有伏笔。",
        "6. 写正文或改写时，必须沿用【当前章正文】的文风：人称视角、句子长短、用词与标点习惯都要一致，读起来要像同一个人写的。",
        "7. 用户只是吐槽、闲聊、问一句闲话时，就按闲聊回，别硬塞方案。",
        "",
        "【你能读到的东西】",
        "这本书的全部设定、全部人物、全书目录（每一章的标题和字数）都在下面给你了；正文我会按相关度附上，多数时候够用。",
        "如果确实要某一章的原文才答得准，就输出下面这条动作，我下一轮把那一章全文贴给你：",
        '<act>{"do":"read","chapter":"第3章"}</act>',
        "",
        "【你能直接改这本书的数据】用户让你改书籍设置、概念、世界观、大纲、剧本时，直接改，不要打开设置界面：",
        '<act>{"do":"set","path":"subgenre","value":"扮猪吃虎"}</act>',
        "path 只能用这些：",
        "· 书籍设置：genre（题材）/ subgenre（子题材）/ style（风格）/ audience（目标读者）/ ending（结局倾向）/ strategy（写法策略）/ ref_author（参考作者）/ lang / chapter_count / words_per_chapter",
        "· 概念：concept.core（一句话核心）/ concept.theme（主题）/ concept.positioning（市场定位）/ concept.plot_structure（剧情主线）/ concept.character_arc（主角弧光）/ concept.style_guide（风格指南）",
        "· 世界观：world.content（整段世界观）/ 大纲：outline.macro（总纲）/ 剧本：script.scenes",
        '<act>{"do":"char","name":"陆昭宁","field":"age","value":"20"}</act> 改某个角色已有的字段（age / identity / personality / appearance / goal / motive / quote / tagline 等）',
        "value 填改完之后的完整内容，不是增量；改世界观就把新的整段文本给它。",
        "改完用一句话说清改了哪一项、改成了什么；只想知道当前值就不要输出动作，直接回答（这些值都在下面的资料里）。",
        "",
        "【你能直接在正文里改字（最重要）】用户让你动正文——改名、删句、加一句、替换一段、整段重写——不要只在聊天里贴稿子，输出 edit 动作，我会在编辑框里当着用户的面一个字一个字改出来：",
        '<act>{"do":"edit","op":"replace","find":"原文里逐字照抄的一句（8-80字）","with":"改好后的文字"}</act>',
        '<act>{"do":"edit","op":"delete","find":"要删掉的那句原文"}</act>',
        '<act>{"do":"edit","op":"insert","find":"紧挨着的原句","with":"要加的文字","where":"after"}</act>',
        '<act>{"do":"edit","op":"append","with":"补在章末的文字"}</act>',
        '<act>{"do":"edit","op":"rewrite","with":"整章改完后的完整正文"}</act>',
        "find 必须从【当前章正文】里逐字复制，标点、空格、引号一个不差，不能用省略号，也不能顺手美化；宁可截短一点，也不要对不上。",
        "要改别的章就在动作里加 \"chapter\":\"第3章\"，不加就是当前打开的这一章。一次最多 6 条，多条按在正文里出现的先后排。",
        "改完只用一两句说清动了哪几处（比如「把他改叫沈砚了，两处」），正文里已经有了，别再贴一遍稿子。",
        "用户只是问「这段写得怎么样」「有什么问题」时，不要输出 edit，正常点评。",
        "",
        "【你能操作界面】用户让你跳转、打开、切换时，在回答最后单独一行输出动作标记（用户看不见这行），最多 3 个：",
        "原则：能一步做完的就直接做，别弹面板让人再点一次；只有缺参数、需要用户自己挑的时候才开面板。改数据用上面的 set，不要用 open settings 代替。",
        '<act>{"do":"open","target":"studio","module":"characters"}</act> 打开 AI 工坊；module 可为 project/concept/world/characters/outline/writing/script/toolbox',
        '<act>{"do":"open","target":"writer"}</act> 回写作台；target 也可为 library（书架）/ settings（设置）/ review（自检）',
        '<act>{"do":"theme","set":"night"}</act> 直接换主题；set 可为 paper（日间）/ eye（护眼）/ night（夜间）',
        '<act>{"do":"paper","set":"rice"}</act> 直接换纸面；set 可为 plain（素白）/ rice（米黄）/ grid（格线）',
        '<act>{"do":"theme"}</act> 只在拿不准时用：弹「背景与主题」让用户自己挑（比如要换成自定义图片）',
        '<act>{"do":"chapter","title":"第3章"}</act> 跳到某一章',
        '<act>{"do":"apply","chapter":"第3章"}</act> 只有在你给出可以直接贴回正文的整段改写稿时才用，标出这段稿子属于哪一章；这次没改正文就不要输出',
        '<act>{"do":"panel","tab":"check"}</act> 切右栏；tab 可为 note/world/ai/check/companion',
        "只在用户确实要你动手时才输出动作；拿不准就别输出，先用嘴说清。",
    ]
    if ctx.get("meta"):
        lines.append("【书籍信息】" + ctx["meta"])
    if ctx.get("chapter_count"):
        lines.append(f"【全书进度】共 {ctx.get('chapter_count')} 章，约 {ctx.get('total_words')} 字。")
    if ctx.get("chapter_index"):
        lines.append("【全书目录】\n" + "\n".join(ctx["chapter_index"]))
    if ctx.get("settings"):
        lines.append(ctx["settings"])
    if ctx.get("cur_title"):
        lines.append(f"【当前章】{ctx['cur_title']}" + (f"；细纲：{ctx['cur_detail']}" if ctx.get("cur_detail") else ""))
    if ctx.get("chapters_full"):
        for c in ctx["chapters_full"]:
            lines.append(f"【正文·{c['title']}】\n{c['text']}")
    if ctx.get("prev_tail"):
        lines.append("【上一章结尾】\n" + ctx["prev_tail"])
    if ctx.get("selection"):
        lines.append("【用户选中的正文】\n" + ctx["selection"])
    return "\n".join(lines)


_THINK_BLOCK = re.compile(
    r"<(?:think|thinking|reasoning|analysis)>.*?</(?:think|thinking|reasoning|analysis)>",
    re.S | re.I)
_THINK_HEAD = re.compile(
    r"^\s*(?:思考过程|思考|分析过程|分析|推理过程|推理|Thinking Process|Reasoning)\s*[:：]\s*", re.I)


def _join_continuation(a, b):
    """把续写接到被截断的正文后面，去掉接缝处的重复"""
    a, b = str(a or ""), str(b or "")
    if not b:
        return a
    for k in range(min(40, len(a), len(b)), 0, -1):
        if a[-k:] == b[:k]:
            b = b[k:]
            break
    return a + b


def _strip_thinking(t):
    """去掉模型漏出来的思考区块，只留最终正文"""
    s = _THINK_BLOCK.sub("", str(t or "")).strip()
    if _THINK_HEAD.match(s):
        parts = [x.strip() for x in re.split(r"\n\s*\n", s) if x.strip()]
        s = parts[-1] if len(parts) >= 2 else _THINK_HEAD.sub("", s).strip()
    s = re.sub(r"^\s*(?:最终回答|最终改写|改写结果|最终正文|答案)\s*[:：]\s*", "", s)
    return s.strip()


def _humanize_chat(s):
    """清掉明显的 AI 排版与客套：Markdown 记号、项目符号、开场客套、结尾推销。"""
    t = str(s or "").strip()
    if not t:
        return t
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*•·]\s+", "", t, flags=re.M)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"^(好的|好|当然可以|当然|没问题|收到)[，,。！!\s]+", "", t)
    t = re.sub(r"\n*(希望(这|以上|这些|我的)?[^\n]{0,30}(帮助|有用)[^\n]*)$", "", t)
    t = re.sub(r"\n*(如需|如果需要|如果你需要)[^\n]{0,40}[。！!]?\s*$", "", t)
    t = re.sub(r"\n*(还有(什么|其他)问题[^\n]*)$", "", t)
    return t.strip()


# ---------------- 搭子回答的「人味」流水线：规则清理 → 说人话改写 → 校验 → 复核 → AIGC 终检 ----------------
_CHAT_DEAI_SYSTEM = ("你是中文写作搭档的嘴。把话改得像人随口说的，意思一字不改，不解释、不寒暄。"
                     "只输出改好的这段话。牢记：生动、有画面、有语气不是 AI 味，空洞的套话才是；"
                     "把一句有滋有味的话削成干巴巴的大白话，是最糟的改法，不算人味。")
_CHAT_DEAI_RULES = """把这段话改成人话：
- 事实、数字、书名、章名、结论全部保留，一个都不能丢。
- 字数不能比原话少 25% 以上；说得更短不等于更像人，别把有内容的话削成光秃秃的结论。
- 去掉「首先/其次/总之/综上/值得注意的是/希望对你有所帮助」这类腔调。
- 不要空洞的排比和对偶，不要结尾总结升华；说完就停。
- 可以有比喻、有画面、有语气、有态度，像真人在跟你聊，而不是干巴巴念稿。
- 原来生动的形容、比喻、例子、具体细节，能留就留，不要为了「口语」把肉削掉。
- 句子有长有短，允许一句只有三五个字。
- 用自己的口气说，别像客服。
- 不要 Markdown、不要项目符号、不要加引号包裹。

反例（这是毁稿，不是人味）：
原话：这段开头的景是活的——檐角挂着水，灯影晃了一下，像有人从窗外走过去。
错误：开头的景写得活。有水和灯影，像有人走过。
正确：这段开头的景是活的，檐角挂着水，灯影晃一下，跟有人贴着窗外走过去似的。"""
_CHAT_REVIEW_RULES = """复核这一段改写：
- 有没有改跑题、漏掉事实、把话说得太满？
- 有没有为了口语而变得油滑、轻浮、或者不像本人？
- 有没有把本来生动有画面的话削成了干巴巴的大白话？如果削了，必须补回生动，还要用原话里已有的细节补，不许另编。
- 有没有比原话短了四分之一以上？短了就补回来。
- 只修这几类问题，其余保持；没问题就原样输出。只输出正文。"""
_CHAT_SKILL_TIPS = """常见 AI 腔（要避开）——注意：这些才是 AI 味，生动和比喻不是：
- 段落开头先下判断：「这其实是一个…的问题」「本质上来说」
- 三段式、两层对比、每段字数差不多
- 抽象大词：显著、极大、进一步、联动、闭环、维度
- 结尾总结或反问：「所以，关键在于…」「你觉得呢？」
- 空洞抒情：难以言喻、五味杂陈、仿佛一切、时间仿佛静止——而不是「缓缓、轻轻、温暖」这类正常的好词。
- 把好句子挖成短句骨架：「雨落下来。灯亮着。他走了。」这不是人味，是懒得写。"""

_CHAT_KEEP_RE = (
    re.compile(r"《[^》]{1,24}》"),
    re.compile(r"第[0-9一二三四五六七八九十百千]+[章节卷回]"),
    re.compile(r"[「“\"]([^」”\"]{2,24})[」”\"]"),
    re.compile(r"[A-Za-z]{2,}"),
    re.compile(r"\d+(?:\.\d+)?"),
)


def _tri_overlap(a, b):
    ca, cb = _norm_cn(a), _norm_cn(b)
    if len(ca) < 10:
        return 1.0
    ga = {ca[i:i + 3] for i in range(len(ca) - 2)}
    gb = {cb[i:i + 3] for i in range(len(cb) - 2)}
    if not ga:
        return 1.0
    return len(ga & gb) / len(ga)


def _chat_keep_bits(text):
    bits = []
    for pat in _CHAT_KEEP_RE:
        for m in pat.finditer(str(text or "")):
            v = m.group(1) if m.groups() else m.group(0)
            if v and v.strip():
                bits.append(v.strip())
    return list(dict.fromkeys(bits))[:24]


def _chat_ok(src, new):
    """人味改写的校验：信息不丢、不跑题、不更 AI、通顺"""
    new = str(new or "").strip()
    if not new:
        return False, "空输出"
    if len(_norm_cn(new)) < 6:
        return False, "太短"
    a, b = len(_norm_cn(src)), len(_norm_cn(new))
    if a and (b < a * 0.65 or b > a * 1.7):
        return False, "削得太短或扩得太多"
    if a >= 40:
        ok, why = _flattened(src, new, ratio=0.5)
        if not ok:
            return False, why
    ok, why = _dup_ok(src, new)
    if not ok:
        return False, why
    if _residual_ai(new):
        return False, "还有 AI 句"
    if _BAN_NEW.search(new) and not _BAN_NEW.search(src):
        return False, "改出了 AI 套话"
    ok, why = _fluency_ok(new)
    if not ok:
        return False, why
    for bit in _chat_keep_bits(src):
        if bit not in new:
            return False, "丢了信息：" + bit[:12]
    if _tri_overlap(src, new) < 0.30:
        return False, "改跑题了"
    return True, ""


def _chat_aigc(text, use_model=None):
    """搭子回答的 AIGC 终检（规则+统计；够长时加本地模型概率）"""
    if aigc_guard is None:
        return {"score": 0, "pass": True, "level": "LOW", "hits": []}
    if use_model is None:
        use_model = _cn_len(text) >= 120
    mp = None
    if use_model:
        try:
            probs = _ai_model_probs([text])
            if probs and probs[0] is not None:
                mp = float(probs[0])
        except Exception:
            mp = None
    return aigc_guard.check(text, mp)


def _chat_rewrite(cur, keep, why, call, strict=False):
    prompt = "【原话】\n%s\n\n【判定】%s\n\n" % (cur, why or "句子太齐、太像客服")
    if keep:
        prompt += "【必须保留】" + "、".join(keep) + "\n\n"
    prompt += _CHAT_DEAI_RULES + "\n\n" + _CHAT_SKILL_TIPS
    if strict:
        prompt += "\n上一稿没过校验，这次说人话，但别为了口语把话削短变干；内容、细节一个不能丢。"
    msgs = [{"role": "system", "content": _CHAT_DEAI_SYSTEM},
            {"role": "user", "content": prompt}]
    try:
        try:
            out = call(msgs, content_only=True, max_tokens=16384)
        except TypeError:
            out = call(msgs)
    except Exception:
        return ""
    out = _strip_thinking((out or "").strip())
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z]*\n?|```$", "", out).strip()
    return _humanize_chat(out.strip().strip('"“”'))


def _chat_review(src, draft, call):
    prompt = ("【原话】\n%s\n\n【改写】\n%s\n\n%s\n%s"
              % (src, draft, _CHAT_REVIEW_RULES, _CHAT_SKILL_TIPS))
    msgs = [{"role": "system", "content": _CHAT_DEAI_SYSTEM},
            {"role": "user", "content": prompt}]
    try:
        try:
            out = call(msgs, content_only=True, max_tokens=16384)
        except TypeError:
            out = call(msgs)
    except Exception:
        return ""
    out = _strip_thinking((out or "").strip())
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z]*\n?|```$", "", out).strip()
    return _humanize_chat(out.strip().strip('"“”'))


def _chat_deai(text, call):
    """搭子回答统一过一遍：规则清理 → 说人话 → 校验 → 复核 → 校验 → AIGC 终检（不过再改一轮）
    不再往回答里塞错别字：靠错字装人味是伪装，不是人味。"""
    text = _strip_thinking(_humanize_chat(text))
    info = {"score": None, "pass": True, "rounds": 0, "hits": []}
    if not text or _cn_len(text) < 12:
        return text, info
    g = _chat_aigc(text)
    info.update({"score": g["score"], "hits": g.get("hits") or [], "pass": g["pass"]})
    if g["pass"] and not _residual_ai(text):
        return text, info

    src, cur, best = text, text, text
    best_score = g["score"]
    for rnd in range(2):
        info["rounds"] = rnd + 1
        keep = _chat_keep_bits(src)
        draft = _chat_rewrite(cur, keep, "；".join(g.get("hits") or []), call, strict=rnd > 0)
        if not draft:
            break
        ok, _why = _chat_ok(src, draft)
        if not ok:
            g2 = _chat_aigc(draft)
            if g2["score"] < best_score:
                best, best_score = draft, g2["score"]
            g = g2
            continue
        rv = _chat_review(src, draft, call)
        cand = rv if (rv and _chat_ok(src, rv)[0]) else draft
        cg = _chat_aigc(cand)
        info["rounds"] = rnd + 1
        if cg["score"] < best_score:
            best, best_score = cand, cg["score"]
        info.update({"score": cg["score"], "hits": cg.get("hits") or [], "pass": cg["pass"]})
        if cg["pass"]:
            best = cand
            break
        cur = cand
        g = cg

    out = best
    info["score"] = _chat_aigc(out, use_model=False)["score"]
    info["pass"] = bool(info["score"] <= aigc_guard.PASS_LINE) if aigc_guard else True
    return out.strip(), info


_ACT_RE = re.compile(r"<act>\s*(\{.*?\})\s*</act>", re.S)


def _parse_act_json(raw):
    """动作 JSON 解析；模型把换行/制表符直接塞进字符串时，先转义再解析一次"""
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    out, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                out.append(ch)
                esc = False
                continue
            if ch == "\\":
                out.append(ch)
                esc = True
                continue
            if ch == '"':
                out.append(ch)
                in_str = False
                continue
            if ch in "\r\n\t":
                out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
                continue
            out.append(ch)
            continue
        if ch == '"':
            in_str = True
        out.append(ch)
    try:
        obj = json.loads("".join(out))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _split_acts(s):
    """把回复里的 <act>{...}</act> 动作摘出来，正文里不留痕迹"""
    raw = str(s or "")
    acts = []
    for m in _ACT_RE.finditer(raw):
        obj = _parse_act_json(m.group(1))
        if obj:
            acts.append(obj)
    clean = _ACT_RE.sub("", raw)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean, acts


def _acts_fallback(acts):
    """模型只给动作、没给话时，补一句人话"""
    theme_name = {"paper": "日间", "eye": "护眼", "night": "夜间"}
    paper_name = {"plain": "素白", "rice": "米黄", "grid": "格线"}
    for a in (acts or []):
        d = str(a.get("do") or a.get("type") or "").lower()
        if d == "theme":
            s = theme_name.get(str(a.get("set") or "").lower(), "")
            return f"换好了，{s}。" if s else "面板给你开着了，自己挑一下。"
        if d == "paper":
            s = paper_name.get(str(a.get("set") or "").lower(), "")
            return f"换好了，{s}纸面。" if s else "面板给你开着了，纸面自己挑。"
        if d == "open":
            return "开好了。"
        if d == "chapter":
            return "翻到了。"
        if d == "panel":
            return "切过去了。"
    return ""


def _chapter_texts(project, names):
    """按「第3章 / 标题关键词」取出整章原文，供模型按需再读一轮"""
    chapters = _flat_chapters(project.get("_files") or [])
    picked, titles = [], []
    for nm in names:
        s = str(nm or "").strip()
        if not s:
            continue
        hit = next((c for c in chapters if (c.get("name") or "").strip() == s), None)
        if hit is None:
            m = re.search(r"([0-9]+|[零一二三四五六七八九十百两]+)", s)
            n = _cn_num(m.group(1)) if m else 0
            if n and 0 < n <= len(chapters):
                hit = chapters[n - 1]
        if hit is None:
            hit = next((c for c in chapters if s in (c.get("name") or "")), None)
        if hit is not None and all(x.get("id") != hit.get("id") for x in picked):
            picked.append(hit)
    if not picked:
        return None
    out = []
    for c in picked:
        txt = c.get("content") or ""
        if len(txt) > 12000:
            txt = txt[:6000] + "\n……（中间省略）……\n" + txt[-6000:]
        out.append(f"【{c.get('name') or ''}】\n{txt}")
        titles.append(c.get("name") or "")
    return {"text": "\n\n".join(out), "titles": titles}


_AGENT_SET_LABELS = {
    "genre": "题材", "subgenre": "子题材", "style": "风格", "audience": "目标读者",
    "ending": "结局倾向", "strategy": "写法策略", "ref_author": "参考作者",
    "lang": "语言", "chapter_count": "计划章数", "words_per_chapter": "每章字数",
    "concept": "概念", "world": "世界观", "outline": "大纲", "script": "剧本",
}


def _apply_agent_updates(project, acts):
    """执行搭子的 set 动作，直接写进项目文件；返回（保留的动作, 已改清单）"""
    if not project:
        return acts, []
    keep, updates = [], []
    for a in (acts or []):
        kind = str(a.get("do") or a.get("type") or "").lower()
        if kind == "char":
            nm = str(a.get("name") or "").strip()
            fld = str(a.get("field") or "").strip()
            val = a.get("value")
            if not nm or not fld or isinstance(val, (dict, list)) or val is None:
                keep.append(a)
                continue
            hit = False
            for g, arr in (project.get("characters") or {}).items():
                if not isinstance(arr, list):
                    continue
                for c in arr:
                    if isinstance(c, dict) and str(c.get("name") or "").strip() == nm:
                        c[fld] = val.strip()[:4000] if isinstance(val, str) else val
                        updates.append({"path": f"characters.{g}.{nm}.{fld}", "value": val,
                                        "label": f"角色·{nm}·{fld}"})
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                keep.append(a)
            continue
        if kind not in ("set", "write", "update"):
            keep.append(a)
            continue
        path = str(a.get("path") or a.get("field") or "").strip()
        parts = [p for p in re.split(r"[.\s]+", path) if p]
        if not parts or parts[0] not in _AGENT_SET_LABELS or len(parts) > 3:
            keep.append(a)
            continue
        if any(p.startswith("_") for p in parts):
            keep.append(a)
            continue
        val = a.get("value")
        if isinstance(val, (dict, list)) or val is None:
            keep.append(a)
            continue
        if isinstance(val, str):
            val = val.strip()[:20000]
        if len(parts) == 1 and isinstance(project.get(parts[0]), (dict, list)):
            keep.append(a)
            continue
        cur = project
        for p in parts[:-1]:
            if not isinstance(cur.get(p), dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = val
        label = _AGENT_SET_LABELS.get(parts[0], parts[0])
        if len(parts) > 1:
            label += "·" + ".".join(parts[1:])
        updates.append({"path": path, "value": val, "label": label})
    return keep, updates


# ---------------- 搭子直接改正文：把模型给的 edit 动作解析成可回放的增删改 ----------------
_EDIT_INTENT_RE = re.compile(
    r"(改|换|删|去掉|删掉|加上|加一句|加一段|插入|补一句|补一段|替换|重写|改写|润色|调整|改成|变成|挪到|移到)")


def _norm_ws(s):
    return re.sub(r"\s+", "", str(s or ""))


def _locate_source(text, find):
    """在正文里定位 find：先逐字找，再忽略空白差异找；返回 (start, end) 或 None"""
    text = str(text or "")
    find = str(find or "")
    if not find:
        return None
    i = text.find(find)
    if i >= 0:
        return i, i + len(find)
    nf = _norm_ws(find)
    if not nf:
        return None
    idx_map, buf = [], []
    for pos, ch in enumerate(text):
        if not ch.isspace():
            buf.append(ch)
            idx_map.append(pos)
    ns = "".join(buf)
    j = ns.find(nf)
    if j < 0:
        return None
    return idx_map[j], idx_map[j + len(nf) - 1] + 1


def _agent_edit_chapter(project, chapter_id, act_chapter=""):
    """定位这次要改的那一章：优先动作里点名的章，其次当前打开的章"""
    chapters = _flat_chapters(project.get("_files") or [])
    name = str(act_chapter or "").strip()
    if name:
        hit = next((c for c in chapters if (c.get("name") or "").strip() == name), None)
        if hit is None:
            m = re.search(r"([0-9]+|[零一二三四五六七八九十百两]+)", name)
            n = _cn_num(m.group(1)) if m else 0
            if n and 0 < n <= len(chapters):
                hit = chapters[n - 1]
        if hit is None:
            hit = next((c for c in chapters if name in (c.get("name") or "")), None)
        if hit is not None:
            return hit
    hit = next((c for c in chapters if str(c.get("id")) == str(chapter_id)), None)
    return hit or (chapters[-1] if chapters else None)


def _apply_agent_edits(text, ops, limit=6):
    """按顺序把 edit 动作落到正文上，返回（可回放的动作, 改完的正文, 改了什么）"""
    work = str(text or "")
    done = []
    for a in (ops or [])[:limit]:
        op = str(a.get("op") or a.get("mode") or "replace").strip().lower()
        find = str(a.get("find") or a.get("from") or a.get("old") or "")
        new = a.get("with")
        if new is None:
            new = a.get("to", a.get("text", ""))
        new = str(new or "")
        where = str(a.get("where") or a.get("position") or "after").strip().lower()
        if op in ("rewrite", "whole", "all", "整章", "全文"):
            if not new.strip():
                continue
            work = new
            done.append({"op": "rewrite", "find": "", "with": new, "where": ""})
            continue
        if op in ("append", "tail", "end", "章末", "结尾"):
            if not new:
                continue
            sep = "" if not work.strip() or work.endswith("\n") else "\n\n"
            work = work.rstrip("\n") + sep + new
            done.append({"op": "append", "find": "", "with": new, "where": "end"})
            continue
        if not find:
            continue
        loc = _locate_source(work, find)
        if not loc:
            continue
        s, e = loc
        actual = work[s:e]
        if op in ("delete", "del", "remove", "删", "删掉"):
            work = work[:s] + work[e:]
            done.append({"op": "delete", "find": actual, "with": "", "where": ""})
        elif op in ("insert", "add", "插入", "新增"):
            if not new:
                continue
            pos = s if where in ("before", "前", "前面") else e
            work = work[:pos] + new + work[pos:]
            done.append({"op": "insert", "find": actual, "with": new,
                         "where": "before" if pos == s else "after"})
        else:
            work = work[:s] + new + work[e:]
            done.append({"op": "replace", "find": actual, "with": new, "where": ""})
    return done, work


def _edits_summary(edits):
    n = {"replace": 0, "insert": 0, "delete": 0, "append": 0, "rewrite": 0}
    for e in edits:
        k = str(e.get("op") or "")
        if k in n:
            n[k] += 1
    bits = []
    if n["replace"]:
        bits.append(f"替换 {n['replace']} 处")
    if n["insert"]:
        bits.append(f"插入 {n['insert']} 处")
    if n["delete"]:
        bits.append(f"删掉 {n['delete']} 处")
    if n["append"]:
        bits.append("章末补写")
    if n["rewrite"]:
        bits.append("整章重写")
    return "、".join(bits)


@app.post("/api/agent/chat")
def api_agent_chat(data: dict):
    """写作搭子：带全书上下文的对话（真正的写作助手，不是通用问答）"""
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先在设置里配置 API Key")

    user_message = (data.get("user_message") or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    project_name = data.get("project_name") or ""
    project = load_project(project_name) if project_name else None

    # Shannon：只要用户丢链接过来，就当场取数；取不到也如实说明，不让模型瞎编
    grab = None
    if shannon and user_message:
        try:
            if shannon.wants_fetch(user_message):
                grab = shannon.deliver(user_message, budget=45, pages=3, links=2)
                if grab and grab.get("ok"):
                    print("✓ Shannon 取数：%s（%d 字 / %d 文件）" % (
                        grab.get("title") or grab.get("url"), grab.get("chars") or 0,
                        len(grab.get("files") or [])))
                elif grab:
                    print("⚠ Shannon 取数失败：%s" % grab.get("reason"))
        except Exception as e:
            print("⚠ Shannon 取数异常:", e)

    # 搭子改正文：先定位要改的那一章，并把编辑框里最新的正文留下来（模型给的 find 才能逐字对上）
    edit_chapter = _agent_edit_chapter(project, data.get("chapter_id") or "") if project else None
    live_text = str(data.get("chapter_text") or "")[:60000]
    edit_src = (live_text if live_text.strip() else str((edit_chapter or {}).get("content") or ""))[:60000]

    ctx = _build_agent_context(project, data.get("chapter_id") or "", data.get("selection") or "", user_message)
    mem = _load_agent_memory(project_name)
    ctx["memory_block"] = _memory_block(mem)
    system_prompt = data.get("system_instruction") or _agent_system_prompt(ctx)
    kb = _brain_context(user_message)
    if kb:
        system_prompt += "\n\n" + kb
    if grab:
        system_prompt += shannon.chat_brief(grab)

    if edit_src and _EDIT_INTENT_RE.search(user_message):
        head = edit_src[:14000]
        tail = edit_src[-6000:] if len(edit_src) > 21000 else ""
        block = head + ("\n……（中间省略，不要引用省略部分）……\n" + tail if tail else "")
        system_prompt += ("\n\n【当前章正文·编辑框里最新的（章节：%s；改正文时 find 必须从这里逐字照抄）】\n%s"
                          % ((edit_chapter or {}).get("name") or "当前章", block))

    if data.get("adult"):
        system_prompt += (
            "\n\n【成人向模式（本书为成人虚构作品）】\n"
            "1. 允许直白的性描写与情欲场景，用于文学创作；写法重感官、心理与关系张力，避免器官堆砌和重复形容词。\n"
            "2. 硬性限制：所有涉及性描写的角色必须明确为成年人（18 岁以上）；禁止未成年、禁止真实人物、禁止非自愿或胁迫情节。\n"
            "3. 保持与正文一致的文风与人称；仍然不解释、不总结，直接给正文。\n"
            "4. 若请求触碰上述硬性限制，直接拒绝并说明原因。"
        )

    messages = [{"role": "system", "content": system_prompt}]
    for m in (data.get("messages") or [])[-14:]:
        role = "assistant" if m.get("role") in ("model", "assistant") else "user"
        txt = (m.get("text") or m.get("content") or "").strip()
        if txt:
            messages.append({"role": role, "content": txt[:4000]})
    messages.append({"role": "user", "content": user_message[:4000]})

    try:
        import requests
        url = (getattr(ai_service, "base_url", "") or "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"

        def _post(msgs, max_tokens):
            """发请求；遇到 max_tokens 超出模型上限（400）就减半重试"""
            cur = max_tokens
            while True:
                payload = {
                    "model": getattr(ai_service, "model", "") or "deepseek-chat",
                    "messages": msgs,
                    "temperature": 0.92,
                    "top_p": 0.95,
                    "frequency_penalty": 0.35,
                    "presence_penalty": 0.3,
                    "max_tokens": cur,
                }
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {ai_service.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=180,
                )
                if resp.status_code == 400 and cur > 2048:
                    cur = max(2048, cur // 2)
                    continue
                resp.raise_for_status()
                return resp.json(), cur

        def _call(msgs, content_only=False, max_tokens=32768, allow_continue=True):
            data, used = _post(msgs, max_tokens)
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            out = (msg.get("content") or "").strip()
            # 改写/复核这类内部调用绝不能用 reasoning_content 兜底，否则思考过程会当正文输出
            if not out and not content_only:
                out = (msg.get("reasoning_content") or "").strip()
            if not out:
                raise RuntimeError("模型没有返回内容，可能是上下文过长或额度不足")
            out = _strip_thinking(out)
            # 输出被截断：自动续写，最多两次，接缝去重
            more = 0
            while choice.get("finish_reason") == "length" and allow_continue and more < 2:
                more += 1
                try:
                    d2, _used2 = _post(msgs + [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": "接着上一句继续写，从断掉的地方续上；不要重复已有内容，不要加任何说明。"},
                    ], used)
                except Exception:
                    break
                c2 = (d2.get("choices") or [{}])[0]
                add = _strip_thinking(((c2.get("message") or {}).get("content") or "").strip())
                if not add:
                    break
                out = _join_continuation(out, add)
                choice = c2
            return out

        text, acts = _split_acts(_call(messages))
        text = _strip_thinking(text)
        text, deai_info = _chat_deai(text, _call)
        reply = text

        # 模型要读某章全文：补上原文再问一轮
        reads = [str(a.get("chapter") or "").strip() for a in acts
                 if str(a.get("do") or a.get("type") or "").lower() == "read"]
        reads = [r for r in reads if r][:3]
        read_titles = []
        if reads and project:
            extra = _chapter_texts(project, reads)
            if extra:
                read_titles = extra["titles"]
                messages.append({"role": "assistant", "content": text or "我先翻一下那几章。"})
                messages.append({"role": "user", "content": "【系统】这是你要的章节原文，读完再答：\n\n" + extra["text"]})
                text2, acts2 = _split_acts(_call(messages))
                text2, deai2 = _chat_deai(text2, _call)
                if deai2.get("rounds") or deai2.get("score") is not None:
                    deai_info = deai2
                text = text2 or text
                if acts2:
                    acts = acts2
                else:
                    acts = [a for a in acts if str(a.get("do") or "").lower() != "read"]

        _act_kind = lambda a: str(a.get("do") or a.get("type") or "").lower()
        acts = [a for a in acts if _act_kind(a) != "read"]
        edit_in = [a for a in acts if _act_kind(a) == "edit"][:6]
        acts = [a for a in acts if _act_kind(a) != "edit"][:4] + edit_in
        acts, updates = _apply_agent_updates(project, acts)
        if updates and project_name:
            try:
                save_project(project_name, project)
            except Exception as e:
                print("⚠ 搭子写入失败:", e)
                updates = []

        # 正文编辑：在原文上把动作落到改完的文本，再把可回放的动作交给前端逐字演出来
        edits, edit_target, edit_warn = [], None, ""
        if project and edit_in:
            act_ch = ""
            for a in edit_in:
                act_ch = str(a.get("chapter") or a.get("title") or "").strip()
                if act_ch:
                    break
            target_ch = _agent_edit_chapter(project, data.get("chapter_id") or "", act_ch)
            if target_ch:
                src_text = edit_src if (not act_ch and edit_src) else str(target_ch.get("content") or "")
                edits, _new_text = _apply_agent_edits(src_text, edit_in)
                if edits:
                    edit_target = {"id": target_ch.get("id"), "name": target_ch.get("name")}
                else:
                    edit_warn = "这次改动没对上正文原文，我先没动，你换个说法或者指一下具体那句。"
                    print("⚠ 改正文未命中：", [e.get("find") for e in edit_in][:3])
        acts = [a for a in acts if _act_kind(a) != "edit"]

        apply_ch = ""
        for a in acts:
            if str(a.get("do") or a.get("type") or "").lower() == "apply":
                apply_ch = str(a.get("chapter") or a.get("title") or "").strip()
                if apply_ch:
                    break
        target = _guess_target_chapter(project, text, user_message,
                                       data.get("chapter_id") or "", apply_ch) if project else None
        extra_facts = [f"已改：{u['label']} = {str(u['value'])[:50]}" for u in updates]
        if re.search(r"记住|记一下|别忘了|以后都|以后就", user_message):
            extra_facts.append("用户要求记住：" + user_message[:60])
        try:
            threading.Thread(target=_remember_turn,
                             args=(project_name, user_message, text or reply, extra_facts),
                             daemon=True).start()
        except Exception:
            pass
        facts_now = len(_load_agent_memory(project_name).get("facts") or []) if project_name else 0
        if updates:
            fallback = "改好了：" + "、".join(u["label"] for u in updates)
        elif edits:
            fallback = "改好了：" + _edits_summary(edits)
        else:
            fallback = _acts_fallback(acts) or reply
        reply_text = text or fallback
        if edit_warn and not edits:
            reply_text = reply_text + "\n\n---\n\n" + edit_warn
        if grab:
            if grab.get("ok"):
                reply_text = reply_text + shannon.chat_attach(grab)
            else:
                reply_text = reply_text + "\n\n---\n\n这次没取到数据：%s\n如果这个页面要登录或要过验证，把内容直接贴给我也行。" % (
                    grab.get("reason") or "未知原因")
        return {
            "success": True,
            "response": reply_text,
            "role": "assistant",
            "actions": acts,
            "reads": read_titles,
            "target": target,
            "updates": updates,
            "edits": edits,
            "edit_chapter": edit_target,
            "deai": deai_info,
            "fetch": shannon.public(grab) if grab else None,
            "memory": {"facts": facts_now, "turns": len(mem.get("recent") or [])},
            "context": {
                "chapter": ctx.get("cur_title", ""),
                "chapter_words": ctx.get("cur_words", 0),
                "has_selection": bool(ctx.get("selection")),
                "people": ctx.get("people_count", len(ctx.get("people") or [])),
                "has_outline": bool(ctx.get("settings")),
                "chapters_given": len(ctx.get("chapters_full") or []),
                "chapters_total": ctx.get("chapter_count", 0),
                "total_words": ctx.get("total_words", 0),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型调用失败：{e}")

@app.get("/api/brain/stats")
def api_brain_stats():
    """搭子大脑：库有多大、最近学了什么"""
    if not brain:
        raise HTTPException(status_code=500, detail="知识库不可用")
    st = brain.stats()
    st["success"] = True
    st["sync"] = _brain_state()
    return st


@app.post("/api/brain/search")
def api_brain_search(data: dict):
    if not brain:
        raise HTTPException(status_code=500, detail="知识库不可用")
    q = str(data.get("q") or "").strip()
    if not q:
        return {"success": True, "rules": [], "docs": []}
    return {"success": True, "rules": brain.rules(q, 8), "docs": brain.search(q, 8)}


@app.post("/api/brain/feed")
def api_brain_feed(data: dict):
    """手动投喂：给一段文本，或给一个公开网址"""
    if not brain or not brain_ingest:
        raise HTTPException(status_code=500, detail="知识库不可用")
    ai_call = _brain_ai if getattr(ai_service, "api_key", "") else None
    url = str(data.get("url") or "").strip()
    text = str(data.get("text") or "")
    title = str(data.get("title") or "")
    if url and not text:
        r = brain_ingest.ingest_url(url, ai_call, title=title)
    else:
        r = brain_ingest.ingest_text(title or "手动投喂", text, ai_call, source="manual")
    r["success"] = True
    r["stats"] = brain.stats()
    return r


@app.post("/api/brain/sync_github")
def api_brain_sync_github():
    """立刻抓一次 GitHub 周榜前三（只读文档，不跑代码）"""
    if not brain_ingest:
        raise HTTPException(status_code=500, detail="抓取模块不可用")
    ai_call = _brain_ai if getattr(ai_service, "api_key", "") else None
    r = brain_ingest.sync_github(ai_call)
    r["success"] = True
    r["stats"] = brain.stats()
    return r


@app.post("/api/shannon/fetch")
def api_shannon_fetch(data: dict):
    """Shannon 取数：显式调用版（搭子里发链接会自动走同一套引擎）"""
    if not shannon:
        raise HTTPException(status_code=500, detail="取数模块不可用")
    url = str(data.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="请给一个链接")
    r = shannon.fetch(
        url,
        budget=float(data.get("budget") or 75),
        pages=int(data.get("pages") or 3),
        links=int(data.get("links") or 2),
        assets=bool(data.get("assets", True)),
        proxy=str(data.get("proxy") or ""),
        cookie=str(data.get("cookie") or ""),
        robots=bool(data.get("robots", False)),
    )
    out = shannon.public(r)
    out["success"] = bool(r.get("ok"))
    out["preview"] = (r.get("preview") or "")[:12000]
    out["phases"] = r.get("phases") or {}
    return out


@app.get("/api/shannon/files/{task_id}/{name:path}")
def api_shannon_file(task_id: str, name: str):
    """取回落盘的数据（报告 / 正文 / 附件 / 打包）"""
    if not shannon:
        raise HTTPException(status_code=500, detail="取数模块不可用")
    p = shannon.file_path(task_id, name)
    if not p:
        raise HTTPException(status_code=404, detail="文件不存在或已清理")
    return FileResponse(p, filename=os.path.basename(p))


@app.post("/api/brain/daily")
def api_brain_daily():
    """立刻投喂一批公开技法文章与公版文本"""
    if not brain_ingest:
        raise HTTPException(status_code=500, detail="抓取模块不可用")
    ai_call = _brain_ai if getattr(ai_service, "api_key", "") else None
    r = brain_ingest.daily(ai_call)
    r["success"] = True
    return r


def _scan_json_state(t):
    """扫描字符串，返回（待闭合括号栈, 是否停在字符串里）"""
    stack = []
    in_str = False
    esc = False
    for ch in t:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
    return stack, in_str


def _repair_json(s):
    """把被截断的 JSON 尽量补齐成可解析对象"""
    tail = s
    candidates = [tail]
    for _ in range(16):
        p = tail.rfind(",")
        if p <= 0:
            break
        tail = tail[:p]
        candidates.append(tail)
    for cand in candidates:
        t = cand.strip()
        if not t:
            continue
        stack, in_str = _scan_json_state(t)
        if in_str:
            t += '"'
        t = re.sub(r",\s*$", "", t.rstrip())
        t = re.sub(r',?\s*"[^"]*"\s*:\s*$', "", t)
        t = re.sub(r",\s*$", "", t.rstrip())
        stack, in_str = _scan_json_state(t)
        if in_str:
            t += '"'
        for ch in reversed(stack):
            t += ch
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _parse_json_loose(text):
    """从可能被截断/夹杂说明的文字里尽量抠出一个 JSON 对象"""
    if not text:
        return None
    s = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    start = s.find("{")
    if start < 0:
        return None
    s = s[start:]
    pos = s.rfind("}")
    tries = 0
    while pos > 0 and tries < 30:
        try:
            obj = json.loads(s[:pos + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        pos = s.rfind("}", 0, pos)
        tries += 1
    return _repair_json(s)


def _ai_json(prompt, max_tokens=4096, temperature=0.2, tries=2, det=False):
    """让模型只回 JSON；失败自动降参、去 response_format 再试一次。
    det=True 时用确定性采样（temperature=0、固定 seed），同一输入给同一结果。"""
    import requests
    url = (getattr(ai_service, "base_url", "") or "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {ai_service.api_key}", "Content-Type": "application/json"}
    last = None
    for attempt in range(tries):
        text = prompt if attempt == 0 else prompt + "\n\n注意：只输出一个紧凑的合法 JSON 对象，不要注释、不要 Markdown，字段值尽量简短。"
        payload = {
            "model": getattr(ai_service, "model", "") or "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是小说设定抽取器，只输出一个合法 JSON 对象，不解释。"},
                {"role": "user", "content": text},
            ],
            "temperature": (0 if det else temperature) if attempt == 0 else (0 if det else 0.05),
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if det:
            payload.update({"top_p": 1, "seed": 20240501, "frequency_penalty": 0, "presence_penalty": 0})
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            if resp.status_code >= 400:
                payload.pop("response_format", None)
                for _k in ("seed", "top_p", "frequency_penalty", "presence_penalty"):
                    payload.pop(_k, None)
                resp = requests.post(url, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            choice = (resp.json().get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            content = (msg.get("content") or "").strip()
            if not content:
                content = (msg.get("reasoning_content") or "").strip()
            finish = choice.get("finish_reason")
            obj = _parse_json_loose(content)
            if isinstance(obj, dict):
                return obj
            last = f"JSON 不完整（finish_reason={finish}）"
        except Exception as e:
            last = str(e)
    raise RuntimeError(last or "模型没有返回可解析的 JSON")


def _strip_meta(text):
    """去掉回复里的解释、标题、Markdown，只留正文"""
    s = str(text or "").strip()
    s = re.sub(r"```[a-zA-Z]*\n?", "", s).replace("```", "")
    s = s.replace("**", "").replace("__", "")
    keep = []
    for raw in s.split("\n"):
        t = raw.strip()
        if not t:
            keep.append("")
            continue
        if re.match(r"^(\*\*)?(说明|解释|备注|注|提示|建议|改写说明|修改说明|修改思路|改写思路|改动点|改动说明|理由|改写后|修改后|润色后|以下是)", t):
            continue
        if re.match(r"^【(说明|备注|提示|注)】", t):
            continue
        if re.match(r"^[-*•]\s*(说明|建议|改写|理由|注|提示)", t):
            continue
        keep.append(raw.rstrip())
    out = "\n".join(keep)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def _norm_chars(s):
    chars, idx = [], []
    for i, ch in enumerate(s):
        if not ch.isspace():
            chars.append(ch)
            idx.append(i)
    return "".join(chars), idx


def _find_span(text, needle):
    """在正文里定位片段：先逐字，再忽略空白差异"""
    if not needle:
        return None
    i = text.find(needle)
    if i >= 0:
        return (i, i + len(needle))
    t, tidx = _norm_chars(text)
    n, _ = _norm_chars(needle)
    if not n:
        return None
    p = t.find(n)
    if p < 0:
        return None
    return (tidx[p], tidx[p + len(n) - 1] + 1)


def _block_end(text, pos):
    """把位置推到当前段落之后（含段落间空行）"""
    pos = max(0, min(pos, len(text)))
    while pos < len(text) and text[pos] != "\n":
        pos += 1
    while pos < len(text) and text[pos] == "\n":
        pos += 1
    return pos


def _fuzzy_span(text, content):
    """按相似度找最像的一段，用于模型给的 target 对不上原文的情况"""
    import difflib
    pat = re.sub(r"\s+", "", content)[:240]
    if not pat:
        return None
    best, best_r = None, 0.0
    for m in re.finditer(r"[^\n]+(?:\n[^\n]+)*", text):
        blk = re.sub(r"\s+", "", m.group())[:240]
        if not blk:
            continue
        r = difflib.SequenceMatcher(None, pat, blk).ratio()
        if r > best_r:
            best_r, best = r, (m.start(), m.end())
    if best and best_r >= 0.45:
        return best
    return None


def _cut_head_dup(prev, seg, min_len=12):
    """去掉 seg 开头与上一段结尾重复的部分"""
    if not prev or not seg:
        return seg
    n = min(len(seg), len(prev))
    for k in range(n, min_len - 1, -1):
        if k < len(seg) and prev.endswith(seg[:k]):
            return seg[k:].lstrip()
    return seg


def _cut_tail_dup(seg, nxt, min_len=12):
    """去掉 seg 结尾与下一段开头重复的部分"""
    if not nxt or not seg:
        return seg
    n = min(len(seg), len(nxt))
    for k in range(n, min_len - 1, -1):
        if k < len(seg) and nxt.startswith(seg[-k:]):
            return seg[:-k].rstrip()
    return seg


@app.post("/api/ai/apply")
def api_ai_apply(data: dict):
    """把搭子的修改稿无缝并进正文：替换某段 / 两段之间插入 / 整章覆盖，只写正文"""
    text = str(data.get("text") or "")
    reply = str(data.get("reply") or "").strip()
    if not text.strip():
        raise HTTPException(status_code=400, detail="当前章节没有正文")
    if not reply:
        raise HTTPException(status_code=400, detail="没有可应用的正文")
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先在设置里配置 API Key")

    selection = str(data.get("selection") or "").strip()
    try:
        cursor = int(data.get("cursor") or 0)
    except Exception:
        cursor = 0

    prompt = f"""你是资深小说编辑，要把一段"修改稿"无缝并进正文，让读者看不出是后加的。

【正文】
<<<
{text[:12000]}
>>>

【用户在正文里选中的原文】
{selection[:3000] if selection else "（无）"}

【修改稿】
<<<
{reply[:8000]}
>>>

判断并入方式：
1. 修改稿改写的是正文里某一段 → mode="replace"，把那段原文逐字复制进 target（必须与正文完全一致，不要用省略号，不要复制整章）。
2. 修改稿是新增的情节/段落 → mode="insert"，anchor 填插入位置前一段末尾 10~20 个连续字（逐字取自正文）。
3. 修改稿是整章重写 → mode="replace_all"。

要求：修改稿里若混有"以下是/说明/建议/备注/改写思路"等解释，全部剔除；必要时调整首尾一两句，让人称、时态、语气与上下文一致，避免重复与突兀。

只输出一个 JSON：
{{"mode":"replace|insert|replace_all","target":"","anchor":"","content":"","note":"一句话"}}
content 必须是能直接放进小说的纯正文（段落之间用 \\n\\n 分隔），不得含解释、标题、序号、Markdown、包裹引号。
"""
    plan = {}
    try:
        plan = _ai_json(prompt, max_tokens=4096, temperature=0.2)
    except Exception:
        plan = {}

    mode = str(plan.get("mode") or "").strip()
    content = _strip_meta(plan.get("content") or "")
    if not content:
        content = _strip_meta(reply)
        mode = ""
    if not content:
        raise HTTPException(status_code=400, detail="回复里没有可用的正文")

    sep = "\n\n" if ("\n\n" in text or len(text) < 200) else "\n"
    new_text, applied, pos, length = text, "", 0, 0

    if mode == "replace_all":
        new_text, applied, pos, length = content, "整章覆盖", 0, len(content)
    elif mode == "replace":
        span = _find_span(text, str(plan.get("target") or "").strip()) or _find_span(text, selection)
        if not span:
            span = _fuzzy_span(text, content)
        if span:
            a, b = span
            seg = _cut_tail_dup(_cut_head_dup(text[:a].rstrip(), content), text[b:]) or content
            new_text = text[:a] + seg + text[b:]
            applied, pos, length = "替换一段", a, len(seg)

    if not applied:
        anchor = str(plan.get("anchor") or "").strip()
        sp = _find_span(text, anchor) if anchor else None
        seg0 = content.strip()
        seg = seg0
        if sp:
            at = _block_end(text, sp[1])
        else:
            head = re.sub(r"\s+", "", text)[:16]
            if head and head in re.sub(r"\s+", "", seg):
                at = 0
            elif cursor:
                at = _block_end(text, cursor)
            else:
                at = len(text)
        left = text[:at].rstrip()
        right = text[at:]
        seg = _cut_tail_dup(_cut_head_dup(left, seg), right) or seg0
        at = len(left)
        if left and right.strip():
            new_text = left + sep + seg + sep + right.lstrip("\n")
        elif left:
            new_text = left + sep + seg
        elif right.strip():
            new_text = seg + sep + right.lstrip("\n")
        else:
            new_text = seg
        applied, pos, length = "插入", len(left) + len(sep), len(seg)

    new_text = re.sub(r"\n{3,}", "\n\n", new_text).strip("\n")
    if new_text == text:
        return {"success": True, "changed": False, "text": text, "mode": applied, "note": "内容与正文一致"}
    return {
        "success": True,
        "changed": True,
        "text": new_text,
        "mode": applied or "插入",
        "pos": pos,
        "length": length,
        "note": str(plan.get("note") or "")[:120],
    }


@app.post("/api/projects/{name}/ai-fill")
def api_project_ai_fill(name: str):
    """从正文抽取工坊全部设定：书籍信息/概念/世界观/人物/关系/大纲/细纲/伏笔"""
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    chapters = [c for c in _flat_chapters(project.get("_files") or []) if (c.get("content") or "").strip()]
    if not chapters:
        raise HTTPException(status_code=400, detail="这本书还没有正文，先导入章节")

    # 采样：开头 2 章 + 中间 1 章 + 结尾 2 章，尽量覆盖更多人物与设定
    src = chapters[:2]
    if len(chapters) > 8:
        src.append(chapters[len(chapters) // 2])
    src.extend(chapters[-2:])
    seen_ids = set()
    parts = []
    for idx, c in enumerate(src):
        cid = id(c)
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        body = (c.get("content") or "").strip()
        body = body[:2200] if idx < 2 else body[-1400:]
        parts.append(f"【{c.get('name','')}】\n{body}")
    sample = "\n\n".join(parts)[:11000]
    titles = "\n".join(f"{i + 1}. {c.get('name', '')}" for i, c in enumerate(chapters[:80]))
    outline = project.get("outline") if isinstance(project.get("outline"), dict) else {}
    macro_now = (outline.get("macro") or "").strip()

    base = f"""书名：{project.get('name','')}
题材：{project.get('genre','')}｜风格：{project.get('style','')}
章节名：
{titles}

正文样本：
{sample}
"""

    changed = []
    errs = []
    dmeta = {}
    dchars = []
    drel = {}
    d2 = {}

    # 一、书籍信息 + 概念 + 世界观
    try:
        p1 = base + """
根据正文推断书籍信息与核心设定，只输出一个 JSON 对象：
{"genre":"题材，如 玄幻/都市/仙侠/悬疑","subgenre":"细分类型","style":"写作风格一句话","ref_author":"风格最接近的知名作者或作品","audience":"目标读者","ending":"结局倾向：大团圆/悲剧/开放式","description":"书籍简介，120字内",
 "concept":{"core":"一句话核心故事","theme":"主题与内核","positioning":"市场定位与卖点","plot_structure":"剧情主线（三幕式）","character_arc":"主角定位与成长弧光","style_guide":"风格锚点与创作指南"},
 "world":"世界观 400 字内：时代、地理、势力、力量体系、风俗"}
要求：每个字段都要尽力从正文推断，确实判断不出才留空字符串；不要编造与正文冲突的内容。
"""
        dmeta = _ai_json(p1, max_tokens=3000)
    except Exception as e:
        errs.append("概念组：" + str(e))

    # 二、人物（分两批，避免单次 JSON 过大被截断）
    known_names = []
    for batch, cap in ((0, 8), (1, 8)):
        try:
            exclude = "、".join(known_names) if known_names else "无"
            p_ch = base + f"""
从正文里找出有名字的角色（第 {batch + 1} 批，最多 {cap} 位）。
已识别过的角色（不要重复）：{exclude}
只输出一个 JSON 对象：
{{"characters":[{{"name":"","group":"主角|配角|反派","role":"身份定位","gender":"男|女|未知","age":"","identity":"身份背景，40字内","purpose":["推动主线"],"tagline":"一句话人设","intro":"角色介绍，120字内","background":"前史，100字内","appearance":"外貌，60字内","personality":"性格，60字内","ability":"能力或功法，60字内","quote":"代表性台词，30字内","goal":"目标","arc":"成长弧","aliases":["别名"]}}]}}
要求：name 必须是正文里真实出现的名字；每个字段都要尽力推断，确实看不出才留空。
"""
            got = _ai_json(p_ch, max_tokens=4096).get("characters") or []
            added = 0
            for c in got:
                if not isinstance(c, dict):
                    continue
                nm = str(c.get("name") or "").strip()[:20]
                if not nm or nm in known_names:
                    continue
                known_names.append(nm)
                dchars.append(c)
                added += 1
            if not added:
                break
        except Exception as e:
            errs.append(f"人物组{batch + 1}：" + str(e))

    # 三、人物关系
    try:
        names_txt = "、".join(known_names) if known_names else "（按正文自行判断）"
        p_rel = base + f"""
已知角色：{names_txt}
只输出一个 JSON 对象：
{{"relations":[{{"from":"","to":"","type":"师徒/父子/仇敌/挚友/上下级…","strength":3,"note":"一句说明"}}]}}
要求：最多 24 条；from 与 to 必须是上面出现过的角色名；strength 取 1-5，越大关系越紧密。
"""
        drel = _ai_json(p_rel, max_tokens=3000)
    except Exception as e:
        errs.append("关系组：" + str(e))

    # 四、全书大纲
    try:
        p2a = base + """
只输出一个 JSON 对象：{"macro":"全书主线大纲，分卷分段，500字内"}
要求：按已有章节推断主线；推断不出就写能确定的部分。
"""
        d2.update(_ai_json(p2a, max_tokens=3000))
    except Exception as e:
        errs.append("大纲组：" + str(e))

    # 五、逐章细纲 / 伏笔
    try:
        p2b = base + """
只输出一个 JSON 对象：
{"detailed":[{"chapter":1,"title":"","idea":"","scenes":"","conflict":"","hook":""}],
 "foreshadows":[{"text":"","chapter":""}]}
要求：detailed 最多 16 条，按上面的章节序号对应；foreshadows 最多 10 条；各字段 60 字内。
"""
        d2.update(_ai_json(p2b, max_tokens=6000))
    except Exception as e:
        errs.append("细纲组：" + str(e))

    if not dmeta and not dchars and not drel and not d2:
        raise HTTPException(status_code=500, detail="识别失败：" + "；".join(errs))

    # ---- 书籍信息 ----
    meta_map = [
        ("genre", 60), ("subgenre", 40), ("style", 100), ("ref_author", 80),
        ("audience", 40), ("ending", 20), ("description", 500),
    ]
    meta_hit = 0
    for key, limit in meta_map:
        v = dmeta.get(key)
        if isinstance(v, str) and v.strip() and not (project.get(key) or "").strip():
            project[key] = v.strip()[:limit]
            meta_hit += 1
    if not (project.get("author") or "").strip():
        m = re.search(r"作\s*者\s*[：:]\s*([^\s，,。;；、]{2,20})", sample)
        if m:
            project["author"] = m.group(1)
            meta_hit += 1
    if meta_hit:
        changed.append("书籍信息")

    # ---- 概念 ----
    concept = dmeta.get("concept")
    if isinstance(concept, dict):
        cur = project.get("concept") if isinstance(project.get("concept"), dict) else {}
        hit = 0
        for k in ["core", "theme", "positioning", "plot_structure", "character_arc", "style_guide"]:
            v = concept.get(k)
            if isinstance(v, str) and v.strip() and not (cur.get(k) or "").strip():
                cur[k] = v.strip()[:800]
                hit += 1
        if hit:
            project["concept"] = cur
            changed.append("概念")

    # ---- 世界观 ----
    wtext = dmeta.get("world")
    if isinstance(wtext, dict):
        wtext = wtext.get("content") or ""
    if isinstance(wtext, str) and wtext.strip():
        world = project.get("world") if isinstance(project.get("world"), dict) else {}
        if not (world.get("content") or "").strip():
            world["content"] = wtext.strip()[:2000]
            project["world"] = world
            changed.append("世界观")

    # ---- 人物 ----
    groups = project.get("characters") if isinstance(project.get("characters"), dict) else {}
    for g in ["主角", "配角", "反派"]:
        if not isinstance(groups.get(g), list):
            groups[g] = []
    name_map = {}
    for g in list(groups.keys()):
        arr = groups[g]
        if not isinstance(arr, list):
            groups[g] = []
            continue
        for i, c in enumerate(arr):
            if isinstance(c, str):
                c = {"name": c.strip()}
                arr[i] = c
            if isinstance(c, dict) and str(c.get("name") or "").strip():
                name_map[str(c["name"]).strip()] = c

    char_limits = {
        "role": 30, "gender": 8, "age": 16, "identity": 80, "tagline": 100,
        "intro": 600, "background": 600, "appearance": 400, "personality": 400,
        "ability": 400, "quote": 120, "goal": 300, "arc": 300,
    }

    def _merge_char(target, source):
        """只补空字段，不覆盖已有内容；返回补上的字段数"""
        filled = 0
        for k, limit in char_limits.items():
            v = source.get(k)
            if isinstance(v, str) and v.strip() and not (target.get(k) or "").strip():
                target[k] = v.strip()[:limit]
                filled += 1
        raw = source.get("purpose")
        if isinstance(raw, str):
            raw = [x for x in re.split(r"[、,，;；\s]+", raw) if x]
        if isinstance(raw, list):
            cur_p = target.get("purpose") if isinstance(target.get("purpose"), list) else []
            for p in raw:
                p = str(p).strip()[:16]
                if p and p not in cur_p:
                    cur_p.append(p)
                    filled += 1
            if cur_p:
                target["purpose"] = cur_p[:8]
        raw = source.get("aliases")
        if isinstance(raw, str):
            raw = [x for x in re.split(r"[、,，;；\s]+", raw) if x]
        if isinstance(raw, list):
            cur_a = target.get("aliases") if isinstance(target.get("aliases"), list) else []
            for p in raw:
                p = str(p).strip()[:16]
                if p and p != target.get("name") and p not in cur_a:
                    cur_a.append(p)
            if cur_a:
                target["aliases"] = cur_a[:8]
        target.setdefault("relations", [])
        target["group"] = target.get("group") or source.get("group") or "配角"
        if not (target.get("desc") or "").strip():
            target["desc"] = (target.get("tagline") or target.get("identity") or "")[:100]
        return filled

    new_n = 0
    enrich_n = 0
    for c in dchars[:20]:
        nm = str(c.get("name") or "").strip()[:20]
        if not nm:
            continue
        if nm in name_map:
            if _merge_char(name_map[nm], c):
                enrich_n += 1
            continue
        g = c.get("group") if c.get("group") in groups else "配角"
        rec = {"name": nm, "group": g, "relations": []}
        _merge_char(rec, c)
        groups[g].append(rec)
        name_map[nm] = rec
        new_n += 1

    # ---- 关系 ----
    rels = 0
    for r in (drel.get("relations") or [])[:24]:
        if not isinstance(r, dict):
            continue
        a = str(r.get("from") or "").strip()[:20]
        b = str(r.get("to") or "").strip()[:20]
        t = str(r.get("type") or "").strip()[:20]
        if not a or not b or not t or a == b:
            continue
        # 关系双方若不在人物表里，补一个名字条目，保证关系图完整
        for nm in (a, b):
            if nm not in name_map:
                stub = {"name": nm, "group": "配角", "relations": []}
                groups["配角"].append(stub)
                name_map[nm] = stub
                new_n += 1
        holder = name_map.get(a)
        if not isinstance(holder, dict):
            continue
        rel_list = holder.setdefault("relations", [])
        if any(isinstance(x, dict) and x.get("target") == b for x in rel_list):
            continue
        try:
            strength = max(1, min(5, int(r.get("strength") or 3)))
        except Exception:
            strength = 3
        rel_list.append({
            "target": b, "type": t, "strength": strength,
            "note": str(r.get("note") or "")[:80],
        })
        rels += 1
    project["characters"] = groups
    if new_n:
        changed.append(f"人物 {new_n} 位")
    if enrich_n:
        changed.append(f"补全 {enrich_n} 位")
    if rels:
        changed.append(f"关系 {rels} 条")

    # ---- 大纲 ----
    macro = str(d2.get("macro") or "").strip()
    if not macro and isinstance(d2.get("outline"), dict):
        macro = str(d2["outline"].get("macro") or "").strip()
    if macro and not macro_now:
        outline["macro"] = macro[:3000]
        changed.append("大纲")
    # ---- 逐章细纲 ----
    cur_det = outline.get("detailed") if isinstance(outline.get("detailed"), dict) else {}
    det_n = 0
    pos = 0
    for item in (d2.get("detailed") or [])[:24]:
        if not isinstance(item, dict):
            continue
        pos += 1
        m2 = re.search(r"\d+", str(item.get("chapter") or ""))
        num = int(m2.group()) if m2 else pos
        rec = {
            "chapter": f"第{num}章",
            "title": str(item.get("title") or "")[:60],
            "idea": str(item.get("idea") or "")[:300],
            "scenes": str(item.get("scenes") or "")[:300],
            "conflict": str(item.get("conflict") or "")[:300],
            "hook": str(item.get("hook") or "")[:300],
        }
        old = cur_det.get(str(num))
        if isinstance(old, dict):
            filled = False
            for k in ["title", "idea", "scenes", "conflict", "hook"]:
                if not (old.get(k) or "").strip() and rec[k]:
                    old[k] = rec[k]
                    filled = True
            if filled:
                det_n += 1
            continue
        cur_det[str(num)] = rec
        det_n += 1
    if det_n:
        outline["detailed"] = cur_det
        changed.append(f"细纲 {det_n} 章")
    # ---- 伏笔 ----
    fore = outline.get("foreshadows") if isinstance(outline.get("foreshadows"), list) else []
    exist = {str(x.get("text") or "") for x in fore if isinstance(x, dict)}
    fn = 0
    for f in (d2.get("foreshadows") or [])[:10]:
        if not isinstance(f, dict):
            continue
        txt = str(f.get("text") or "").strip()[:120]
        if not txt or txt in exist:
            continue
        fore.append({"text": txt, "done": False, "chapter": str(f.get("chapter") or "")[:40]})
        exist.add(txt)
        fn += 1
    if fn:
        outline["foreshadows"] = fore
        changed.append(f"伏笔 {fn} 条")
    project["outline"] = outline

    save_project(name, project)
    return {
        "success": True,
        "changed": changed,
        "characters": new_n,
        "enriched": enrich_n,
        "relations": rels,
        "detailed": det_n,
        "foreshadows": fn,
        "errors": errs,
    }
def _require_api_key():
    if not ai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")


def _require_project(name: str):
    project = load_project(name) if name else None
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.post("/api/ai/continue")
def api_ai_continue(data: dict):
    """续写：承接已有正文往下写"""
    _require_api_key()
    content = (data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="没有可续写的内容")
    project = _require_project(data.get("project_name", ""))
    prompt = f"""你是《{project.get('name', '')}》的作者，正在往下写这一章。
题材：{project.get('genre', '')}；风格：{project.get('style', '')}。
本章大纲：{data.get('outline') or '（无）'}

下面是已经写好的正文结尾：
---
{content[-2000:]}
---

要求：
1. 直接从断点处往下写，不要复述上文，不要写"第X章"。
2. 严格沿用上面的文风：保持相同的人称与视角、相近的句子长度与节奏、相同的用词习惯和标点习惯（该用短句就短句，该用口语就口语），读起来必须像同一个人接着写的。
3. 不要突然拔高文风，不要出现总结句、议论句、"仿佛/不禁"式的套话堆叠。
4. 写到自然的小高潮或悬念处收住。
5. 只输出正文，不要任何解释或标记符号。"""
    try:
        text = ai_service.generate_content(prompt, use_cache=False)
        return {"success": True, "text": clean_text(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/rewrite")
def api_ai_rewrite(data: dict):
    """改写润色"""
    _require_api_key()
    content = (data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="没有可改写的内容")
    project = _require_project(data.get("project_name", ""))
    direction = data.get("direction") or "文学润色"
    prompt = f"""你是《{project.get('name', '')}》的资深编辑，请对下面这段正文做「{direction}」。
题材：{project.get('genre', '')}；风格：{project.get('style', '')}。
补充要求：{data.get('requirements') or '无'}

原文：
---
{content}
---

要求：
1. 保持原有情节、人物与信息，不增删剧情。
2. 必须沿用原文的文风与语感：句子长短比例、人称与视角、用词习惯、标点习惯都要一致，改完要像同一个人写的，不能变成另一种腔调。
3. 让句子更像人写的：长短句交错，少用"然而/此外/值得一提的是"这类连接词。
4. 只输出改写后的正文，不要解释。"""
    try:
        text = ai_service.generate_content(prompt, use_cache=False)
        return {"success": True, "text": clean_text(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 去 AI 味（外科手术版：只切痕迹，不动文笔） ----------
# 融合四份现成方案：
#   1. Wikipedia《Signs of AI writing》/ blader/humanizer 的 29 条模式；
#   2. qu-ai-wei：声口 > 句式 > 段序，禁止为“人味”降格用词；
#   3. story-deslop：网文门禁 A~F（禁用词 / 句式套路 / 心理外化 / 节奏 / 对话 / 结尾升华）；
#   4. remove-ai-flavor v5.2：50 种模式 + 网文词库 + 分级处方。
# 关键改动：不再整篇重写。先定位有 AI 痕迹的段落，只重写那几段；未命中的段落逐字保留，
# 重写段再过一遍“作者指纹”校验，越界就退回原文——宁可少改，不许把文笔改薄。
_LIT_MARKERS = "檐廊阶烛帘帐袖鬓襟腕膝喉脊栊轩榭阙黛墨砚笺帛袂裾簪钗珮环氅裘履屐槛阑珊髻帷幔屏榻盏樽觞箫筝瑟"
_COLLOQ_WORDS = ["特别", "搞", "弄", "咋", "啥", "咱", "贼", "老是", "有点", "其实",
                 "反正", "就是说", "然后", "感觉", "超级", "老半天"]
_PARTICLE = "呢吧啊嘛呗呀"


def _voice_stats(t):
    """作者指纹：句长、起伏、文言密度、四字结构、对话占比、标点习惯"""
    s = str(t or "")
    narr_raw = re.sub(r"[「“][^」”]*[」”]", "", s)
    narr = re.sub(r"\s", "", narr_raw)
    n = max(1, len(narr))
    sents = [x for x in re.split(r"[。！？!?…]", narr) if x.strip()]
    lens = [len(x) for x in sents] or [0]
    avg = sum(lens) / len(lens)
    std = (sum((x - avg) ** 2 for x in lens) / len(lens)) ** 0.5
    return {
        "chars": len(re.sub(r"\s", "", s)),
        "sents": len(sents),
        "avg": avg,
        "std": std,
        "min": min(lens),
        "max": max(lens),
        "lit": sum(narr.count(ch) for ch in _LIT_MARKERS) / n * 1000,
        "col": sum(narr.count(w) for w in _COLLOQ_WORDS) / n * 1000,
        "part": sum(narr.count(ch) for ch in _PARTICLE),
        "four": len(re.findall(r"(?<=[，。！？；：、\s「」“”])[\u4e00-\u9fa5]{4}(?=[，。！？；：、\s「」“”])", s)),
        "dlg": sum(len(x) for x in re.findall(r"[「“][^」”]*[」”]", s)) / max(1, len(re.sub(r"\s", "", s))),
        "dash": s.count("——"),
        "ell": s.count("…") // 2 + s.count("...") // 3,
    }


_IMG_WORDS = ("夜色 月色 月光 灯火 檐角 风声 雨声 刀锋 剑光 眉眼 眼底 眼中 嘴角 喉间 掌心 指节 衣角 "
              "气息 暮色 天光 云影 山影 水声 烛火 窗棂 门槛 石阶 廊下 帐幔 鬓发 襟口 袖口 步履 眸光 "
              "神色 血色 死寂 寒意 凉意 晨光 暮光 余晖 长夜 秋雨 风雪 眉梢 眼角 指腹 腕骨 脊背 心口 "
              "胸口 肩头 鬓角 发梢 衣袖 袍角 靴底 马背 缰绳 城门 宫墙 庭院 院落 廊檐 匾额 灯笼 火把 "
              "刀鞘 剑鞘 弓弦 旗角 烽烟 尘土 黄沙 花香 微风 风声 刀面 刃口 灯影").split()

# 白话词：这些词密起来，就是“小学生白话文”的味道
_PLAIN_WORDS = ["的时候", "看到", "觉得", "样子", "好像", "但是", "然后", "东西", "事情", "地方",
                "开始", "已经", "应该", "感觉", "眼睛", "嘴巴", "声音", "以前", "后来", "时候"]


def _img_hits(t):
    s = re.sub(r"\s", "", re.sub(r"[「“][^」”]*[」”]", "", str(t or "")))
    return {w for w in _IMG_WORDS if w in s}


def _plain_density(t):
    s = re.sub(r"\s", "", re.sub(r"[「“][^」”]*[」”]", "", str(t or "")))
    return sum(s.count(w) for w in _PLAIN_WORDS) / max(1, len(s)) * 1000


_RICH_SIMILE = re.compile(r"仿佛|似乎|宛如|犹如|好像|恰似|像是|似的|如同|恍若|恍如")
_RICH_DUP = re.compile(r"([\u4e00-\u9fa5])\1")


def _rich_stats(t):
    """文笔密度：叠词、比喻、修饰语、四字格、意象词。
    用来识别「把好词好句挖掉、只剩干巴巴主谓宾」那种伪人味改写。"""
    narr = re.sub(r"[「“][^」”]*[」”]", "", str(t or ""))
    chars = max(1, len(re.sub(r"\s", "", narr)))
    dup = len(_RICH_DUP.findall(narr))
    simile = len(_RICH_SIMILE.findall(narr))
    mod = narr.count("的") + narr.count("地")
    four = len(style_lab.FOUR_CHAR.findall(narr)) if style_lab else 0
    img = sum(narr.count(w) for w in _IMG_WORDS)
    raw = dup * 1.0 + simile * 1.6 + mod * 0.7 + four * 1.4 + img * 1.1
    return {"chars": chars, "density": round(raw * 100.0 / chars, 2),
            "dup": dup, "simile": simile, "mod": mod, "four": four, "img": img}


def _flattened(orig, new, ratio=0.55):
    """判「越改越干」：优美的词句、比喻、修饰语被挖掉，只剩大白话。
    返回 (是否可接受, 原因)。ratio 越小越宽松，兜底稿用更宽的阈值。"""
    a, b = _rich_stats(orig), _rich_stats(new)
    if a["chars"] < 40 or b["chars"] < 30 or a["density"] < 1.0:
        return True, ""
    ta = a["dup"] + a["simile"] + a["mod"] + a["four"] + a["img"]
    tb = b["dup"] + b["simile"] + b["mod"] + b["four"] + b["img"]
    if ta >= 4 and tb < ta * (ratio + 0.05):
        return False, ("把好词好句削干了（比喻/修饰语/叠词/意象少了 %.0f%%）"
                       % (100 - tb * 100.0 / ta))
    if b["density"] < a["density"] * ratio:
        return False, ("文笔密度掉了一半以上（%.1f → %.1f）"
                       % (a["density"], b["density"]))
    if a["density"] >= 1.6 and b["density"] < 0.9:
        return False, "改成了干巴巴的大白话，原文的画面感没了"
    if a["mod"] >= 6 and b["mod"] < a["mod"] * 0.45:
        return False, "把形容词和修饰语挖掉太多，只剩骨头"
    return True, ""


def _keep_score(orig, new):
    """文笔保真度 0~100：只看文笔有没有掉档，不惩罚正常删掉 AI 套话"""
    a, b = _voice_stats(orig), _voice_stats(new)
    if not a["chars"] or not b["chars"]:
        return 0

    def down(x, y, span):
        return max(0.0, 1 - max(0.0, x - y) / max(1e-6, span))

    parts = [
        down(a["avg"], b["avg"], a["avg"] * 0.4),
        down(a["std"], b["std"], max(2.0, a["std"] * 0.6)),
        down(a["lit"], b["lit"], max(1.5, a["lit"] * 0.6)),
        down(a["dlg"], b["dlg"], max(0.08, a["dlg"] * 0.5)),
    ]
    img_o = _img_hits(orig)
    parts.append(len(img_o & _img_hits(new)) / len(img_o) if len(img_o) >= 3 else 1.0)
    parts.append(max(0.0, 1 - _plain_density(new) / 30))
    return int(round(sum(parts) / len(parts) * 100))


# 段落级 AI 痕迹扫描：一命中即记为编辑信号，不做作者身份判断
def _sent_list(p):
    """按句切开，保留原标点；拼回去与原文逐字一致"""
    return re.findall(r"[^。！？!?…\n]+[。！？!?…]?", str(p or ""))


def _parallel_run(sents):
    for i in range(len(sents) - 2):
        a, b, c = sents[i], sents[i + 1], sents[i + 2]
        if len(a) >= 4 and len(b) >= 4 and len(c) >= 4 and a[:2] == b[:2] == c[:2]:
            return True
        if a.count("也") and b.count("也") and c.count("也"):
            return True
    return False


def _para_tics(p):
    """段落级结构扫描：只认升华收尾、解释性收尾、机械过渡、排比、句长均匀"""
    score, tags = 0, []

    def hit(pat, w, name):
        nonlocal score
        n = len(re.findall(pat, p, re.M))
        if n:
            score += w * min(n, 2)
            if name not in tags:
                tags.append(name)

    hit(r"仿佛一切都|时间仿佛静止|仿佛整个世界|一切都已注定|这一刻，?时间|注定无人入眠", 5, "升华收尾")
    hit(r"殊不知|他不知道的是|她不知道的是|多年以后", 4, "预告式收尾")
    hit(r"氛围|张力|质感|宿命感|存在感|底色|维度|层次感|难以言喻|无可名状", 2, "空泛抽象")
    hit(r"复杂的情感|百感交集|五味杂陈|思绪万千|心潮澎湃|涌上心头|难以言说的|无法言说", 2, "空泛抒情")

    sents = _sent_list(p)
    lead_summary = sum(1 for s in sents
                       if re.match(r"^(?:他|她|我)?(?:终于|这才)?(?:明白|意识到|懂了)[，,]", _LEAD_CONN.sub("", s.strip())))
    know_summary = sum(1 for s in sents
                       if re.match(r"^(?:他|她)?(?:知道|明白)[，,]", _LEAD_CONN.sub("", s.strip()))
                       and re.search(r"(终究|注定|只能|总得|无论|必须|太多)", s))
    lead_conn = sum(1 for s in sents if _LEAD_CONN.match(s.strip()))
    if lead_summary:
        score += 4 * min(lead_summary, 2)
        tags.append("解释性收尾")
    if know_summary:
        score += 3 * min(know_summary, 2)
        if "解释性收尾" not in tags:
            tags.append("解释性收尾")
    if lead_conn:
        score += 3 * min(lead_conn, 2)
        tags.append("机械过渡")
    if _parallel_run(sents):
        score += 4
        tags.append("机械排比")
    # 句长像节拍器：5 句以上很均匀算重，4 句以上偏均匀也算轻
    if len(sents) >= 4:
        lens = [len(s) for s in sents]
        avg = sum(lens) / len(lens)
        cv = ((sum((x - avg) ** 2 for x in lens) / len(lens)) ** 0.5 / avg) if avg else 0
        if cv < 0.22 and len(sents) >= 5:
            score += 3
            tags.append("句长均匀")
        elif cv < 0.30:
            score += 2
            tags.append("句长均匀")
    # 连续三句同一个主语开头
    starts = [s.strip()[:2] for s in sents if len(s.strip()) >= 4]
    for i in range(len(starts) - 2):
        if starts[i] == starts[i + 1] == starts[i + 2] and starts[i] in ("他站", "她站", "他看", "她看", "他心", "她心", "他的", "她的"):
            score += 2
            if "同头起句" not in tags:
                tags.append("同头起句")
            break
    if sents and len(sents[-1]) <= 60 and re.search(r"(仿佛一切|仿佛整个世界|时间仿佛静止|一切都已注定|殊不知|多年以后|这一刻，?时间)", sents[-1]):
        score += 2
        if "升华收尾" not in tags:
            tags.append("升华收尾")
    if sents and re.match(r"^(?:他|她)?(?:知道|明白)[，,]", _LEAD_CONN.sub("", sents[-1].strip())):
        score += 2
        if "解释性收尾" not in tags:
            tags.append("解释性收尾")
    # 无信息量的小动作堆叠（攥手、捏衣角、指节发白…）
    if len(_MICRO_ACTION.findall(p)) >= 2:
        score += 2
        tags.append("微动作堆叠")
    # 听觉 + 嗅觉按顺序铺满（视觉之外还补两条）
    if len(_SENSE_HEAR.findall(p)) >= 2 and len(_SENSE_SMELL.findall(p)) >= 1:
        score += 2
        tags.append("感官链")
    return score, tags


_LEAD_CONN = re.compile(
    r"^(?:然而|此外|与此同时|首先|其次|再次|最后|总之|综上所述|换言之|由此可见|事实上|"
    r"值得一提的是|值得注意的是|显而易见|毋庸置疑|不得不说)[，,、]\s*")


def _pure_summary(s):
    """整句只是抒情/总结，没有具体信息：删掉不伤文笔"""
    t = str(s or "").strip()
    if not t or len(t) > 50 or "「" in t or "“" in t:
        return False
    if re.search(r"仿佛一切都|时间仿佛静止|仿佛整个世界|一切都已注定|这一刻，?时间|注定无人入眠|"
                 r"殊不知|他不知道的是|她不知道的是", t):
        return True
    if re.match(r"^(?:他|她|我)?(?:终于|这才)(?:明白|意识到|懂了)[，,]", t) and len(t) <= 42:
        return True
    if re.match(r"^(?:他|她)?(?:知道|明白)[，,]", t) and re.search(r"(终究|注定|只能|总得)", t) and len(t) <= 42:
        return True
    return False


def _split_keep(text):
    """按原有换行切段并保留分隔符，便于未改动的段逐字还原"""
    raw = re.split(r"(\n+)", str(text or ""))
    segs = []
    for i, seg in enumerate(raw):
        if seg == "":
            continue
        segs.append((i % 2 == 1, seg))
    return segs


def _ai_text_once(prompt, system=None, temperature=0.7, max_tokens=16384):
    """纯文本调用：不走 generate_content 的“更随意”重试；推理模型偶尔把预算耗在思考上，空稿就重试一次"""
    import requests
    url = (getattr(ai_service, "base_url", "") or "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"
    payload = {
        "model": getattr(ai_service, "model", "") or "deepseek-chat",
        "messages": [
            {"role": "system", "content": system or "你是中文小说的文字编辑，只输出正文。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    for attempt in range(2):
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {ai_service.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=240,
        )
        resp.raise_for_status()
        data = resp.json()
        ch = (data.get("choices") or [{}])[0]
        content = ((ch.get("message") or {}).get("content") or "").strip()
        if content:
            # 被 max_tokens 截断：续写一次，接缝去重
            if ch.get("finish_reason") == "length":
                try:
                    more_msgs = list(payload["messages"]) + [
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": "接着上一句继续写，从断掉处续上，不要重复，不要解释。"},
                    ]
                    p2 = dict(payload)
                    p2["messages"] = more_msgs
                    r2 = requests.post(url, json=p2, timeout=240, headers={
                        "Authorization": f"Bearer {ai_service.api_key}",
                        "Content-Type": "application/json"})
                    if r2.status_code < 400:
                        add = ((r2.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                        if add.strip():
                            content = _join_continuation(content, add.strip())
                except Exception:
                    pass
            return content
        print("模型空输出（第 %d 次）：finish=%s usage=%s"
              % (attempt + 1, ch.get("finish_reason"), data.get("usage")))
        time.sleep(1)
    return ""


def _local_deai(text):
    """没有 Key 时的保守清理：只删句子开头的功能性过渡词，不动任何用词"""
    out = []
    for line in str(text or "").split("\n"):
        l = line.replace("值得注意的是，", "").replace("值得一提的是，", "")
        l = re.sub(r"^(然而|此外|与此同时|总的来说|综上所述|显而易见|毋庸置疑|众所周知|首先|其次|再次|最后)[，,]\s*", "", l.strip()) if l.strip() else l
        out.append(l)
    return "\n".join(out)


def _contaminated(out, seg, prev, nxt):
    """模型是否把上一段/下一段的句子写进来了（上下文串段）"""
    n = _norm_cn(out)
    o = _norm_cn(seg)
    for src in (prev, nxt):
        for s in _sent_list(src):
            k = _norm_cn(s)
            if len(k) >= 8 and k in n and k not in o:
                return True
    return False


def _para_ops(orig, new):
    """句级逐句对照：保留 / 删除 / 新增 / 改写，按原文顺序完整对齐"""
    import difflib
    a = [s.strip() for s in _sent_list(orig) if s.strip()]
    b = [s.strip() for s in _sent_list(new) if s.strip()]
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            ops += [{"op": "same", "o": s, "n": s} for s in a[i1:i2]]
        elif tag == "delete":
            ops += [{"op": "del", "o": s, "n": ""} for s in a[i1:i2]]
        elif tag == "insert":
            ops += [{"op": "add", "o": "", "n": s} for s in b[j1:j2]]
        else:
            olds, news = a[i1:i2], b[j1:j2]
            if len(olds) == len(news):
                ops += [{"op": "mod", "o": o, "n": n} for o, n in zip(olds, news)]
            else:
                ops += [{"op": "del", "o": s, "n": ""} for s in olds]
                ops += [{"op": "add", "o": "", "n": s} for s in news]
    return ops


def _cn_len(s):
    return len(re.sub(r"\s+", "", str(s or "")))


def _aigc_final(text):
    """AIGC 终检：规则+统计分 与 本地检测模型概率 融合（aigc_guard 不可用返回 None）"""
    if aigc_guard is None:
        return None
    mp = None
    try:
        paras = [p for p in str(text or "").split("\n") if p.strip()]
        rep = _ai_model_report(text, paras) or {}
        if rep.get("score") is not None:
            mp = float(rep["score"]) / 100.0
    except Exception:
        mp = None
    return aigc_guard.check(text, mp)


def _aigc_guide_text(text):
    """把 AIGC 终检的判法与当前失分项拼成提示块，让模型照着检测方式改"""
    if aigc_guard is None:
        return ""
    a = aigc_guard.advice(text)
    lines = ["【最后还要过 AIGC 终检，按它的判法改】", aigc_guard.explain(),
             "当前这段：%d 分（%s），通过线 %d" % (a["score"], a["level"], aigc_guard.PASS_LINE)]
    if a["hits"]:
        lines.append("命中：" + "、".join(a["hits"]))
    lines.append("针对性改法：")
    lines += ["- " + t for t in a["tips"]]
    return "\n".join(lines)


def _aigc_repair(text, prof=None, floor=64, guide="", round_no=1):
    """终检没过：挑 AIGC 分最高的若干段，按检测报告再走一遍改写+校验（轮次越多范围越大）"""
    if aigc_guard is None:
        return "", []
    lines = str(text or "").split("\n")
    rows = []
    para_no = 0
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        para_no += 1
        if _cn_len(ln) >= 20:
            rows.append((i, para_no, aigc_guard.score(ln)["score"], ln))
    if not rows:
        return "", []
    rows.sort(key=lambda r: -r[2])
    # 第一轮改最可疑的两段，之后逐轮扩大范围
    picks = rows[:min(len(rows), max(2, round_no + 1))]
    repairs = []
    for i, pno, sc, ln in picks:
        prev = lines[i - 1] if i >= 1 else ""
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        tags = _para_tics(ln)[1]
        new, _why, _rev, _rd = _rewrite_segment(ln, prev, nxt, tags, prof=prof,
                                                floor=floor, guide=guide)
        if new and new != ln:
            lines[i] = new
            repairs.append({"index": pno, "before": ln, "after": new, "score": sc})
    return ("\n".join(lines) if repairs else ""), repairs


# ---- 细微笔误：很难完全避免的「的/地」混用，只加一处，宁少不多 ----
# 故意把成语写错、把「得」写成「的」不是人味，是降智，已彻底去掉。
_ADVERB_DI = ("缓缓", "轻轻", "慢慢", "静静", "悄悄", "默默", "渐渐", "微微", "淡淡", "死死", "狠狠",
              "快速", "匆忙", "认真", "小心", "仔细", "大步", "小声", "大声", "低声", "轻声",
              "牢牢", "紧紧", "远远", "暗暗", "偷偷")


def _one_flaw(t, rnd):
    """在一段里找一个最自然的笔误位置，返回 (新文本, 瑕疵描述)。
    只做「的/地」混用这种真作者也会犯的细错，绝不故意写错成语——那是降智，不是人味。"""
    picks = []
    for adv in _ADVERB_DI:
        m = re.search(adv + "地", t)
        if m:
            picks.append(("的地", m, adv + "地", adv + "的"))
    if not picks:
        return t, None
    kind, m, frm, to = picks[rnd.randrange(len(picks))]
    return t[:m.start()] + to + t[m.end():], {"type": kind, "from": frm, "to": to}


def _inject_human_flaws(repl, si_para, total_chars, limit=None):
    """给本次改写过的段落加极少量的「的/地」混用：长稿最多 1 处，短稿不加"""
    flaws = []
    if not repl:
        return repl, flaws
    if limit is None:
        limit = 1
    if total_chars < 800:
        return repl, flaws
    import random
    rnd = random.Random(total_chars * 7919 + len(repl) * 31)
    keys = sorted(repl.keys())
    rnd.shuffle(keys)
    left = limit
    for si in keys:
        if left <= 0:
            break
        t = repl.get(si) or ""
        if _cn_len(t) < 30:
            continue
        new_t, fl = _one_flaw(t, rnd)
        if not fl:
            continue
        repl[si] = new_t
        fl["index"] = si_para.get(si, 0)
        flaws.append(fl)
        left -= 1
    return repl, flaws


def _para_preview(seg, n=24):
    t = re.sub(r"\s+", "", str(seg or ""))
    return t[:n] + ("…" if len(t) > n else "")


def _norm_cn(s):
    """去空白与标点，用来判断某句是否被原样保留"""
    return re.sub(r"[\s，。！？、；：,.!?;:「」『』“”‘’…—·()（）\"']", "", str(s or ""))


# 明显 AI 结构 / 套话：新稿里出现而原文没有，就算改写失败
_BAN_NEW = re.compile(
    r"殊不知|他不知道的是|她不知道的是|仿佛一切|仿佛整个世界|时间仿佛静止|一切都已注定|"
    r"这一刻，?时间|注定无人入眠|总而言之|综上所述|换言之|由此可见|值得一提的是|值得注意的是")


def _good_sentences(p):
    """原文里值得逐字保留的好句：有画面、有动作、有对话，且不是套话"""
    out = []
    for s in _sent_list(p):
        t = s.strip()
        if len(t) < 8 or len(t) > 90:
            continue
        if _pure_summary(t) or _LEAD_CONN.match(t):
            continue
        # 只排除真正的套话，不排除「仿佛/似乎/注定」用在具体比喻里的正常句子
        if re.search(r"仿佛一切|仿佛整个世界|时间仿佛静止|一切都已注定|殊不知|多年以后|这一刻，?时间", t):
            continue
        if _MICRO_ACTION.search(t) and (len(_norm_cn(t)) <= 40 or "无意识" in t or "下意识" in t):
            continue
        if "「" in t or "“" in t or _img_hits(t):
            out.append(_norm_cn(t))
    return out


_A_SENT_RE = re.compile(
    r"仿佛一切|时间仿佛静止|一切都已注定|这一刻，?时间|殊不知|他不知道的是|她不知道的是|"
    r"多年以后|氛围|张力|质感|宿命感|难以言喻|无可名状|这一切|复杂的情感|复杂的情绪|"
    r"百感交集|五味杂陈|思绪万千|心潮澎湃|涌上心头|仿佛整个世界|仿佛在诉说着")


def _bad_sentences(p):
    """段落里具体是哪几句有 AI 结构，交给模型点名修改"""
    out = []
    for s in _sent_list(p):
        t = s.strip()
        if not t:
            continue
        explanatory = (re.match(r"^(?:他|她|我)?(?:终于|这才)?(?:明白|意识到|懂了|知道)[，,]", t)
                       and re.search(r"(终究|注定|只能|总得|都已经|一切都|再也|无论|必须|太多|承载)", t))
        micro = (_MICRO_ACTION.search(t) and len(_MICRO_ACTION.findall(p)) >= 2)
        if _LEAD_CONN.match(t) or _pure_summary(t) or explanatory or micro or _A_SENT_RE.search(t):
            out.append(t)
    return out[:8]


def _is_a_sentence(s):
    """这一句是不是纯 A 类空转（没有画面、动作、对话、信息）"""
    t = _LEAD_CONN.sub("", str(s or "").strip())
    if not t:
        return True
    if _pure_summary(t) or _residual_ai(t) or _A_SENT_RE.search(t):
        return True
    # 以无信息量的小动作为主体的短句，也算 AI 习惯
    if _MICRO_ACTION.search(t) and (len(_norm_cn(t)) <= 40 or "无意识" in t or "下意识" in t):
        return True
    return bool(re.search(r"都已经不重要|命运的齿轮|无法用语言|说不出的", t))


def _is_deletable(seg):
    """只有整段都是纯 A 类空转、没有画面/对话/具体信息时才允许整段删（技能里允许的唯一例外）"""
    t = str(seg or "").strip()
    if not t or len(t) > 60:
        return False
    if "「" in t or "“" in t or _img_hits(t):
        return False
    sents = [s.strip() for s in _sent_list(t) if s.strip()]
    if not sents:
        return False
    return all(_is_a_sentence(s) for s in sents)


def _minimal_deai(seg):
    """最小安全编辑：只去掉句首空转过渡词，其余一字不动（模型反复不合格时用）"""
    return "".join(_LEAD_CONN.sub("", s) for s in _sent_list(seg))


def _strip_ai_habits(seg):
    """确定性清掉 AI 习惯：无信息量的小动作、成链的听觉嗅觉。
    只摘掉那几个半句，句子里其余的好词好句一律保留，不许整句连坐砍掉。"""
    out = []
    for s in _sent_list(seg):
        parts = re.split(r"(?<=[，,])", s)
        kept, subj = [], ""
        for i, p in enumerate(parts):
            if _MICRO_ACTION.search(p.rstrip("，,")):
                # 摘掉句首小动作时，把主语留下，免得后半句成了没主语的碎块
                if i == 0:
                    m = re.search(r"他|她|我", p)
                    if m:
                        subj = m.group(0)
                continue
            kept.append(p)
        t = "".join(kept).strip().rstrip("，,")
        if not t:
            continue
        if subj and not re.match(r"^(他|她|我)", t):
            t = subj + t
        # 摘掉句首半句后只剩没主语的动词碎片，也先看有没有具体信息，别急着丢
        if len(_norm_cn(t)) < 6:
            continue
        # 同一句里既有听觉又有嗅觉：这类成链感官一起删
        if _SENSE_HEAR.search(t) and _SENSE_SMELL.search(t):
            sub = re.split(r"(?<=[，,])", t)
            sub = [p for p in sub if not (_SENSE_HEAR.search(p) or _SENSE_SMELL.search(p))]
            t = "".join(sub).strip().rstrip("，,")
        if not t or len(_norm_cn(t)) < 6:
            continue
        if t[-1] not in "。！？…」”":
            t += "。"
        out.append(t)
    text = "".join(out)
    # 第二遍：只清掉「短、且纯空转」的整句；长句里往往有画面，一律留着
    sents = [s for s in _sent_list(text) if s.strip()]
    keep = [s for s in sents
            if not (len(_norm_cn(s)) <= 30 and _is_a_sentence(s))]
    return "".join(keep)


def _fluency_ok(new):
    """通顺度硬检查：碎句连排、引号不配对、段尾缺标点"""
    sents = [s.strip() for s in _sent_list(new) if s.strip()]
    run = 0
    for s in sents:
        if len(_norm_cn(s)) <= 6:
            run += 1
            if run >= 3:
                return False, "三个以上碎句连排"
        else:
            run = 0
    if new.count("「") != new.count("」") or new.count("“") != new.count("”"):
        return False, "引号不配对"
    for s in sents:
        if len(_norm_cn(s)) > 110:
            return False, "单句太长，读着断气"
    if sents and sents[-1][-1] not in "。！？…」”":
        return False, "段尾没有标点"
    return True, ""


_MICRO_ACTION = re.compile(
    r"攥|捏了?捏?衣角|捏着衣角|指节.{0,4}(发白|泛白)|指腹|摩挲|喉结.{0,4}(滚|动)|"
    r"睫毛.{0,3}(颤|抖)|呼吸.{0,2}(一滞|一窒)|掌心.{0,4}(出汗|发潮|发烫)|"
    r"垂在身侧|无意识地.{0,6}(捏|攥|摩|按)|指尖.{0,4}(发凉|发白|收紧)|"
    r"指头.{0,4}(收紧|蜷|蜷起)|手.{0,3}(攥|捏).{0,3}(了|紧|松)")
_SENSE_HEAR = re.compile(r"听见|传来|响了一声|一声一声|蹄声|水声|铃声|脚步声|声音")
_SENSE_SMELL = re.compile(r"气味|味道|香气|腥|霉|烟火气|柴灰|潮土|臭味|香味")


def _micro_ok(orig, new):
    """不许凭空加“手在袖口里攥了攥”这类无信息量的小动作，也不许堆听觉/嗅觉链"""
    mo = len(_MICRO_ACTION.findall(orig))
    mn = len(_MICRO_ACTION.findall(new))
    if mn > mo:
        return False, "新增了无意义的小动作"
    ho = len(_SENSE_HEAR.findall(orig)) + len(_SENSE_SMELL.findall(orig))
    hn = len(_SENSE_HEAR.findall(new)) + len(_SENSE_SMELL.findall(new))
    if ho == 0 and hn >= 2:
        return False, "堆了听觉/嗅觉感官链"
    if hn > ho + 1:
        return False, "感官描写堆得比原文多"
    return True, ""


def _residual_ai(p):
    """改写稿里是否还留着明显的 AI 句式"""
    for s in _sent_list(p):
        t = s.strip()
        if not t:
            continue
        if re.match(r"^(?:他|她|我)?(?:终于|这才)?(?:明白|意识到|懂了|知道)[，,]", t) and re.search(
                r"无论|终究|注定|只能|总得|必须|再也|太多|承载", t):
            return True
        if _A_SENT_RE.search(t):
            return True
        if re.match(r"^(?:有些|很多|一切|所有)(?:事|东西|人|时候)", t) and re.search(r"只能|终究|注定", t):
            return True
    return False


def _dup_ok(orig, new):
    """新稿不能把某句话重复多遍（模型偶尔会复制一行）"""
    from collections import Counter
    o = Counter(_norm_cn(s) for s in _sent_list(orig) if len(_norm_cn(s)) >= 6)
    n = Counter(_norm_cn(s) for s in _sent_list(new) if len(_norm_cn(s)) >= 6)
    for k, c in n.items():
        if c > max(1, o.get(k, 0)):
            return False, "有句子被重复"
    return True, ""


def _accept_rewrite(orig, new, tags, deletable=False, relaxed=False, prof=None, floor=0,
                    prev="", nxt=""):
    """验收：AI 侧清干净 + 通顺 + 核心不丢 + 衔接不断 + 长度不离谱。
    不再跟原文比文笔保真——原文文笔本来什么样都可以动，只守底线。"""
    new = str(new or "").strip()
    if not new:
        return (True, "") if deletable else (False, "模型空输出")
    ok, why = _dup_ok(orig, new)
    if not ok:
        return False, why
    ok, why = _micro_ok(orig, new)
    if not ok:
        return False, why
    if "微动作堆叠" in tags:
        mo = len(_MICRO_ACTION.findall(orig))
        mn = len(_MICRO_ACTION.findall(new))
        if mo >= 2 and mn > max(0, mo - 2):
            return False, "小动作没清掉"
    if "感官链" in tags:
        ho = len(_SENSE_HEAR.findall(orig)) + len(_SENSE_SMELL.findall(orig))
        hn = len(_SENSE_HEAR.findall(new)) + len(_SENSE_SMELL.findall(new))
        if ho >= 2 and hn >= ho:
            return False, "感官链没清掉"
    a = len(_norm_cn(orig))
    b = len(_norm_cn(new))
    # 长度只防大删大扩，不再按原文句句对齐；但不许把段落削成薄薄一层皮
    lo, hi = (0.62, 1.75) if relaxed else (0.72, 1.6)
    if prof:
        lo, hi = 0.7, 1.8
    if "微动作堆叠" in tags or "感官链" in tags:
        lo = min(lo, 0.35)
    if deletable:
        lo, hi = 0.2, 1.8
    if a and (b < a * lo or b > a * hi):
        return False, "长度偏离过大"
    if not deletable and a >= 40:
        ok, why = _flattened(orig, new)
        if not ok:
            return False, why
    if _BAN_NEW.search(new) and not _BAN_NEW.search(orig):
        return False, "改出了新的 AI 套话"
    if _residual_ai(new):
        return False, "还留着 AI 句"
    ok, why = _fluency_ok(new)
    if not ok:
        return False, why
    ok, why = _core_ok(orig, new)
    if not ok:
        return False, why
    ok, why = _cohesion_ok(new, prev, nxt)
    if not ok:
        return False, why
    if deletable:
        return True, ""
    if prof and floor:
        q = style_lab.score(new, prof)["score"]
        if q < floor:
            return False, "文笔没到题材基准（%d/%d）" % (q, floor)
    return True, ""


_DEAI_SYSTEM = ("你是资深中文小说编辑，做结构性去 AI 味：句子、句序、段落内部结构都可以重写，"
                "把空转和套话换成具体的人、事、景、动作与对白；剧情、人物关系、人称不能改。"
                "你只输出改写后的正文，不解释、不加标题、不用 Markdown、不加引号包裹。"
                "牢记：优美不是 AI 味，空洞才是；好词好句、比喻、形容词、抒情要保留，只删空话套话。")

_DEAI_RULES = """这是「去 AI 味」。先记住一条总纲：**优美不是 AI 味，空洞才是。**
把一段漂亮话改丑了、改干了，不是去 AI 味，是毁稿——这是最严重的错误，比留着套话更严重。

人类的好文章 = 优美的词句 + 具体的人事物。汪曾祺写「碗里卧着一个蛋」、张爱玲写「钟慢了七分钟」、
沈从文写「船头偏了半尺」，都有形容词、有比喻、有画面。AI 腔的病根不是「写得美」，而是这三条：
1. 空洞套话：难以言喻、五味杂陈、仿佛一切、时间仿佛静止、殊不知、多年以后——不知道写啥就堆一句漂亮空话。
2. 千篇一律：每段一样长、每句一样长、每段同一套起手式。
3. 脱离具体：只抒情不写人，只下判断不写事。

所以改写时：
- 优美的形容词、叠词（缓缓、轻轻、温暖、冰冷）、贴切的比喻、四字格、抒情——只要贴着具体的人事物，全保留，还要主动写。
- 只删空洞套话和机械重复，**绝不为了「像人」就把好词好句挖掉、削成大白话。**

【反例·绝对不许这样改】
原文：檐角的雨水一颗一颗坠下来，打在青石板上，溅起一线细白的水花，湿气顺着门缝往里渗。
错误（挖骨削肉，只剩皮）：雨水落下来。石板上有水花。门缝里有湿气。
正确（保留骨肉，只去套话）：檐角的雨水一颗接一颗砸在青石板上，碎成细白的一线，湿气从门缝底下钻进来。

【硬指标·改完自己数一遍】
- 字数不得少于原段的 85%；不是越短越像人。
- 形容词、比喻、叠词、四字格的密度，不得比原文少一半；少了就补回去，用原文已有的人和物。
- 原句里的画面、光线、声音、质感，能留就留，只把空转的抒情句换掉。

一、必须清掉的（这才是真正的 A 类痕迹）：
   - 纯过渡：然而、此外、与此同时、总之、首先/其次/最后 —— 去掉，让句子直接接上。
   - 空泛套话：仿佛一切、时间仿佛静止、这一切都已注定、难以言喻、五味杂陈、殊不知、多年以后 —— 换成具体的动作、物件、光线、声音，不是删成白开水。
   - 解释性收尾：他终于明白……、他知道，终究只能…… —— 改成动作或画面，不要议论。
   - 机械排比：连续三句同头、连续三个"也" —— 打散，换主语或句式，但别把意思删没。
   - 句长像节拍器：长短句交错，允许三五个字的短句，也保留有质感的长句。

二、可以自由重写（不再要求逐字保留）：
   - 句子、句序、段落内部节奏都可以动，不必照抄原句骨架。
   - 四字格、成语、书面语、比喻、形容词可以留，也可以换，只要读起来不别扭。
   - 原文里具体的人、物、地点、动作、数字、对白要留着，别丢。

三、改写方式：
   - 具体化只用原文已有的事实，不许编造新设定、新人物、新情节。
   - 原文确实有无信息量的"攥手、捏衣角、指节发白、喉结滚动、呼吸一滞"，或把听觉嗅觉铺成一条链——只删那几个半句，同句里其余的好句子留住，不许整句连坐。
   - 段尾的升华句换成具体收尾（例："未来已来"→"第二天早上，打印机又卡纸了"），不是把结尾砍掉。
   - 全段都是套话时，用原文里的人和物改写成具体画面，但别只剩一两句干话。

四、硬禁令：
   - 不许把整段删空：除非整段没有任何具体信息，否则至少留下原文的人物与事件。
   - 不许连续三个以上碎句；不许把长句一律剁成四五个字的短句。
   - 不许加网络梗、反转句、段子腔。
   - 不许新增"无信息量的小动作"：手在袖口里攥了攥、指节攥得发白、无意识地捏衣角、指腹摩挲、喉结滚动、睫毛颤了一下、呼吸一滞、掌心出汗。原文没有，就一个都不许加。
   - 不许把视觉、听觉、嗅觉、触觉按顺序铺成一条完整的感官链。
   - 不许出现「仿佛一切 / 时间仿佛静止 / 殊不知 / 多年以后 / 一切都已注定」这类套话（注意：单独的「仿佛」「似乎」用在具体比喻里是正常的，不用删）。
   - 段落数、段落顺序、人称、时态、情节信息都不能变。

五、改完自检：读一遍，像人写的、有画面有质感、没有空转就交。
如果这一稿读着比原文更干、更白、更像小学生作文——重写，那是失败稿，不是人味。"""


_REVIEW_SYSTEM = ("你是中文小说的终审编辑。逐句对照原稿与改写稿，修掉不通顺、跑题、信息丢失和残留的 AI 腔，"
                  "允许大幅改写。只输出最终正文，不解释、不加标题、不用 Markdown。")

_REVIEW_RULES = """对照检查清单（总纲：优美不是 AI 味，空洞才是；不要为了「像人」削掉好词好句）：
AI 侧：① 过渡、总结、升华套话是否清干净；② 句长是否还像节拍器；③ 结尾是否还在拔高。
信息侧：① 原文的人物、地点、物件、动作、数字、对白有没有丢；② 有没有改跑题、有没有加新设定。
AI 习惯侧：① 是否凭空加了"手在袖口里攥了攥、指节发白、捏衣角、指腹摩挲、喉结滚动、呼吸一滞"这类
        无信息量的小动作；② 是否把听觉、嗅觉、触觉按顺序铺成一条感官链。原文没有的，一律删掉。
通顺侧：① 前后句能否直接接上；② 指代是否清楚；③ 有没有半截话、错别字；
        ④ 有没有断层：突然换人、突然换场、开头突然转折；⑤ 单句是否长到要回看一遍才懂。
文笔侧（最要紧的一条）：① 有没有把本来优美的比喻、形容词、叠词（缓缓、轻轻、温暖）误删成大白话；
        ② 有没有改得比原稿更干、更白、更像小学生作文；③ 有没有把原文的画面、光线、声音、质感丢掉。
        以上任一条成立，都要用原文已有的人和物补回具体而有质感的写法，不许交干瘪稿。
        另外：改写稿的字数不能比原稿少 15% 以上；比喻/形容词/四字格不能少一半以上。

改法要求：
- 只修上面这些问题；改写稿里已经合格的句子不要动。
- 不要因为跟原稿不一样就改回去——原稿本身就 AI。
- 不许新增无信息量的小动作，不许连续三个以上碎句；但比喻、形容词、四字格、抒情可以留、可以补。
- 如果改写稿确实没有毛病，就原样输出改写稿。
- 只输出最终正文，不要说明、不要列清单、不要加引号包裹。"""


def _review_segment(orig, draft, prev, nxt, goods, bad, prof=None):
    """模型复核：拿改写稿跟原稿逐句对照，修掉降级与不通顺"""
    prompt = ""
    if prev.strip():
        prompt += "【上文·不改】\n%s\n\n" % prev.strip()
    prompt += "【原稿】\n%s\n\n【改写稿·需要你复核】\n%s\n" % (orig.strip(), draft.strip())
    if nxt.strip():
        prompt += "\n【下文·不改】\n%s\n" % nxt.strip()
    if bad:
        prompt += "\n【仍要清掉的 AI 句】\n" + "\n".join("- " + b for b in bad) + "\n"
    if prof:
        prompt += "\n" + style_lab.rules(prof) + "\n"
        prompt += ("复核时以这套题材笔法为基准：原稿本身写得空，不要因为它跟原稿不一样就改回去；"
                   "只修不通顺、跳跃和丢了具体信息的地方。\n")
    prompt += "\n" + _REVIEW_RULES
    try:
        out = _ai_text_once(prompt, system=_REVIEW_SYSTEM, temperature=0.2, max_tokens=16384)
    except Exception:
        return ""
    out = (out or "").strip()
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z]*\n?|```$", "", out).strip()
    return out.strip().strip('"“”')


_QUOTE_RE = re.compile(r"[「“\"]([^」”\"]{2,60})[」”\"]")
_CN_NUM_RE = re.compile(
    r"[零一二三四五六七八九十百千万两]+(?:个|支|把|匹|条|张|块|片|座|道|声|步|里|分|寸|年|月|日|次|回|层|根|只|辆|艘|盏|碗|壶|口|眼|人)")
_ENTITY_WORDS = ("城", "山", "河", "门", "楼", "院", "屋", "店", "街", "路", "桥", "船", "马", "刀",
                 "剑", "弓", "箭", "车", "灯", "碗", "壶", "信", "旗", "窗", "桌", "椅", "床", "井",
                 "树", "林", "崖", "谷", "关", "营", "寨", "殿", "庙", "塔", "寺", "舟", "枪", "甲",
                 "盔", "墙", "砖", "石", "雪", "雨", "风")
_ACTION_WORDS = ("走", "跑", "站", "坐", "看", "望", "听", "说", "问", "答", "推", "拉", "拿", "放",
                 "转", "抬", "低", "握", "拔", "收", "停", "退", "进", "开", "关", "扔", "接", "笑",
                 "点头", "摇头", "回头", "转身")


def _core_ok(orig, new):
    """核心信息保真：对白、数字、具体物件、动作线不能丢，也不能凭空新增"""
    o, n = str(orig or ""), str(new or "")
    if not n.strip():
        return True, ""
    oq, nq = _QUOTE_RE.findall(o), _QUOTE_RE.findall(n)
    for q in oq:
        if _norm_cn(q) and _norm_cn(q) not in _norm_cn(n):
            return False, "把对白丢了"
    on = set(re.findall(r"\d+(?:\.\d+)?", o)) | set(_CN_NUM_RE.findall(o))
    nn = set(re.findall(r"\d+(?:\.\d+)?", n)) | set(_CN_NUM_RE.findall(n))
    if on - nn:
        lost = on - nn
        # "一个人/一人" 换个说法（独自、只身、没人）不算丢信息
        one_like = all(str(x).startswith("一") for x in lost)
        alone = any(w in n for w in ("独自", "单独", "孤身", "只身", "一个人", "一人",
                                     "没别人", "没人", "只剩", "就他", "就她"))
        if not (one_like and alone):
            return False, "数字丢了"
    oe = [w for w in _ENTITY_WORDS if w in o]
    if oe and sum(1 for w in oe if w in n) < max(1, int(len(oe) * 0.5)):
        return False, "具体物件丢了"
    oa = [w for w in _ACTION_WORDS if w in o]
    if oa and sum(1 for w in oa if w in n) < max(1, int(len(oa) * 0.5)):
        return False, "动作线丢了"
    return True, ""


def _cohesion_ok(new, prev, nxt):
    """阅读连贯：不凭空起转折、不和邻段重复、不把下文写进来"""
    t = str(new or "").strip()
    if not t:
        return True, ""
    if not str(prev or "").strip() and re.match(r"^(但是|但|所以|于是|因为|而且|然而|可是|不过)", t):
        return False, "开头突然转折，接不上上文"
    pn = _norm_cn(prev)
    nn = _norm_cn(nxt)
    tn = _norm_cn(t)
    if len(tn) >= 6 and len(pn) >= 8 and tn[:6] in pn[-40:]:
        return False, "开头和上文重复"
    if len(tn) >= 6 and len(nn) >= 8 and nn[:6] and nn[:6] in tn:
        return False, "把下一段写进来了"
    return True, ""


def _soft_ok(orig, new):
    """兜底稿的软校验：AI 侧干净、通顺、长度别离谱（不再卡文笔保真）"""
    new = str(new or "").strip()
    if not new:
        return True
    ok, _ = _dup_ok(orig, new)
    if not ok:
        return False
    ok, _ = _micro_ok(orig, new)
    if not ok:
        return False
    if _residual_ai(new):
        return False
    ok, _ = _fluency_ok(new)
    if not ok:
        return False
    ok, _ = _core_ok(orig, new)
    if not ok:
        return False
    a, b = len(_norm_cn(orig)), len(_norm_cn(new))
    if a and (b < a * 0.6 or b > a * 1.7):
        return False
    # 兜底稿只挡「削得只剩骨头」的极端情况，阈值放宽，避免退回干瘪原文
    if a >= 40:
        ok, _ = _flattened(orig, new, ratio=0.35)
        if not ok:
            return False
    return True


_HARD_ROUNDS = 15   # 单段最多改写轮次（防死循环的保险，正常 1-3 轮就过）


def _rewrite_segment(seg, prev, nxt, tags, prof=None, floor=0, guide=""):
    """改写→校验→复核→再校验；不过就带着失败原因和 AIGC 检测报告继续改，
    直到通过，或连续两轮没有任何进展才停。
    返回 (文本, 最后没通过的原因, 是否复核过, 用了几轮)"""
    bad = _bad_sentences(seg)
    good_norms = set(_good_sentences(seg))
    goods = [s.strip() for s in _sent_list(seg) if _norm_cn(s) in good_norms][:8]
    deletable = _is_deletable(seg)
    literary = ("「" in seg or "“" in seg or bool(_img_hits(seg)))
    _score, _tags = _para_tics(seg)
    relaxed = ((_score >= 6 and not literary)
               or "微动作堆叠" in _tags or "感官链" in _tags)
    # 这类段落主要是无信息量的小动作/感官链：直接做确定性清除，不交给模型编新细节
    if "微动作堆叠" in _tags or "感官链" in _tags:
        alt = _strip_ai_habits(seg)
        if alt != seg and _soft_ok(seg, alt):
            return alt, "", False, 1
    diag = "、".join(tags) if tags else "整体节奏与句式"
    prompt = ""
    if prev.strip():
        prompt += "【上文·只用于衔接，不要改写】\n%s\n\n" % prev.strip()
    prompt += "【需要改写的段落】\n%s\n\n" % seg.strip()
    prompt += "【诊断】这段的 AI 痕迹：%s\n" % diag
    if bad:
        prompt += "【只处理这几句】\n" + "\n".join("- " + b for b in bad) + "\n"
    if nxt.strip():
        prompt += "\n【下文·只用于衔接，不要改写】\n%s\n" % nxt.strip()
    if prof:
        prompt += "\n" + style_lab.rules(prof, strict=True) + "\n"
    prompt += "\n" + _DEAI_RULES + "\n只输出改写后的这一段正文，不要解释。"
    if deletable:
        prompt += ("\n这一段全是套话、没有具体信息，可以整段删掉；删的时候只输出四个字：__DELETE__。")
    elif relaxed or prof:
        prompt += ("\n这一段原文本身就空（套话/小动作/感官铺排），允许换掉大部分句子："
                   "保留原文里具体的人、事、地点与物件，按上面的题材笔法重写，"
                   "不要保留原来的句子骨架。")

    last_why = ""
    prev_out = ""
    draft = ""
    rounds = 0
    stall = 0          # 连续没有进展的轮数
    best_ai = None     # 单段 AIGC 分的最好值
    best_out, best_q = "", -1   # 没过校验但文笔最好的一稿（兜底时优先用它）
    while rounds < _HARD_ROUNDS:
        rounds += 1
        attempt = rounds - 1
        probe = prev_out or seg
        round_guide = guide
        if aigc_guard is not None:
            g_now = aigc_guard.check(probe, None)
            round_guide = (guide + "\n\n" if guide else "") + _aigc_guide_text(probe)
            if best_ai is None or g_now["score"] < best_ai:
                best_ai = g_now["score"]
                stall = 0
            else:
                stall += 1
            if stall >= 3:
                break
        extra = ""
        if attempt >= 1:
            left = _bad_sentences(prev_out) if prev_out else []
            extra = "\n这是第 %d 次重写：上一稿没过校验（%s）。" % (attempt + 1, last_why or "未通过校验")
            if left:
                extra += "这些 AI 句必须改掉或删掉：" + "；".join(left) + "。"
            if prof:
                extra += "不要照抄原句骨架，按题材笔法重写这一段的同一件事。"
            else:
                extra += "保持原意重写句子，不必照抄原句，也别加新设定。"
            extra += " 只输出这一段正文，别重复上一稿的写法。"
        temp = max(0.2, 0.62 - 0.06 * attempt)
        try:
            out = _ai_text_once(prompt + ("\n\n" + round_guide if round_guide else "") + extra,
                                system=_DEAI_SYSTEM,
                                temperature=temp, max_tokens=16384)
        except Exception as e:
            last_why = "调用失败：%s" % e
            continue
        out = (out or "").strip()
        if out.startswith("```"):
            out = re.sub(r"^```[a-zA-Z]*\n?|```$", "", out).strip()
        out = out.strip().strip('"“”')
        if deletable and out.replace(" ", "") in ("__DELETE__", "DELETE", "删除"):
            return "", "", False, rounds
        if _contaminated(out, seg, prev, nxt):
            last_why = "混入了相邻段落的内容"
            prev_out = out
            continue
        if prof and out:
            q_now = style_lab.score(out, prof)["score"] if style_lab else 0
            if q_now > best_q:
                best_q, best_out = q_now, out
        relax_now = relaxed or attempt >= 1
        ok, why = _accept_rewrite(seg, out, tags, deletable, relax_now, prof=prof,
                                 floor=floor, prev=prev, nxt=nxt)
        if not ok:
            last_why = why
            prev_out = out
            continue
        draft = out
        # 校验通过 → 复核；复核稿也要过校验，不过就带着复核意见回到下一轮继续改
        rv = _review_segment(seg, draft, prev, nxt, goods, bad, prof=prof)
        if rv and rv != draft and not _contaminated(rv, seg, prev, nxt):
            ok2, why2 = _accept_rewrite(seg, rv, tags, False, relax_now, prof=prof,
                                       floor=floor, prev=prev, nxt=nxt)
            if ok2:
                return rv, "", True, rounds
            last_why = "复核稿没过校验：" + why2
            prev_out = rv
            draft = ""
            continue
        return draft, "", False, rounds

    if draft:
        return draft, last_why, False, rounds
    # 兜底：确定性清掉 AI 习惯，再过一遍软校验；还不行就最小改动
    alt = _strip_ai_habits(seg)
    # 有作家基准时：宁可要一稿"没过文笔分但通顺、信息没丢"的重写，也不要只删句子的原文
    if prof and best_out and best_out != seg:
        ok_core = _core_ok(seg, best_out)[0] and _fluency_ok(best_out)[0] \
            and _cohesion_ok(best_out, prev, nxt)[0] and _soft_ok(seg, best_out)
        if ok_core:
            return best_out, "", False, rounds
    # 还是只有原文：按作家笔法再硬写一稿，不再卡文笔分，只要通顺、信息在、没有 AI 腔
    if prof:
        try:
            extra_prompt = (prompt + "\n\n整段重写：保留原文里所有具体的人、地点、物件、数字和动作，"
                            "换掉原来的句子骨架，像上面那位作家那样写。只输出正文，不要解释。")
            out = _ai_text_once(extra_prompt, system=_DEAI_SYSTEM, temperature=0.85,
                                max_tokens=4096)
            out = (out or "").strip().strip('"“”')
            if out and not _contaminated(out, seg, prev, nxt) \
                    and _accept_rewrite(seg, out, tags, False, True, prof=prof, floor=0,
                                        prev=prev, nxt=nxt)[0]:
                return out, "", False, rounds + 1
            # 只卡"通顺、信息没丢、不脱节、没有 AI 腔"，长度/微动作这些不再卡
            if out and not _contaminated(out, seg, prev, nxt) \
                    and _core_ok(seg, out)[0] and _fluency_ok(out)[0] \
                    and _cohesion_ok(out, prev, nxt)[0] and _soft_ok(seg, out):
                return out, "", False, rounds + 1
        except Exception:
            pass
    if alt and alt != seg and _soft_ok(seg, alt):
        return alt, last_why, False, rounds
    if not alt:
        # 整段都是小动作/感官链/空泛抒情，没有具体信息，删掉比留着更像人写
        if "微动作堆叠" in tags or "感官链" in tags or _is_deletable(seg):
            return "", last_why, False, rounds
        alt = _minimal_deai(seg)
    if alt == seg:
        alt = _minimal_deai(seg)
    return (alt if alt != seg else seg), last_why, False, rounds


def _chunk_para(seg, limit=1400):
    """超长段落按句切成几块，避免模型漏写"""
    if len(seg) <= limit:
        return [seg]
    chunks, cur = [], ""
    for s in _sent_list(seg):
        if len(cur) + len(s) > limit and cur:
            chunks.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        chunks.append(cur)
    return chunks


@app.post("/api/ai/humanize")
def api_ai_humanize(data: dict):
    """去 AI 味：定位 AI 结构段 → 让模型做结构改写 → 验收（好句保留率 / 文笔 / 长度）不过就退回原文"""
    import concurrent.futures
    text = str(data.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="没有可处理的文本")
    intensity = int(data.get("intensity") or 7)
    genre = data.get("genre") or ""
    style = data.get("style") or ""
    if not (genre or style):
        pname = data.get("project_name") or ""
        if pname:
            proj = load_project(pname) or {}
            genre = proj.get("genre") or ""
            style = proj.get("style") or ""
    tone = "；".join([x for x in [genre, style] if x])
    if not ai_service.api_key:
        return {"success": True, "text": _local_deai(text), "engine": "local", "changed": 0,
                "warn": "没配置 API Key，只去掉了句首过渡词，没有删改正文"}

    th = 6 if intensity <= 3 else 4 if intensity <= 7 else 3
    segs = _split_keep(text)

    # 三路信号一起判：规则 tic 分 + 本地统计检测分 + 外部 ONNX 模型概率
    det_scores, det_total = {}, 0
    try:
        rep = _ai_local_report(text)
        det_total = int(rep.get("score") or 0)
        for row in rep.get("paragraphs") or []:
            det_scores[int(row.get("index") or 0)] = int(row.get("score") or 0)
    except Exception:
        pass
    model_probs = {}
    try:
        cand = [(si, seg) for si, (is_sep, seg) in enumerate(segs)
                if not is_sep and seg.strip() and len(seg.strip()) >= 18]
        if cand:
            probs = _ai_model_probs([c[1] for c in cand]) or []
            for (si, _s), pv in zip(cand, probs):
                if isinstance(pv, (int, float)):
                    model_probs[si] = float(pv)
    except Exception:
        pass

    # 原文文笔基线：如果原文本身就 AI 味很重，就不再拿原文当基准，改用题材范式
    prof = style_lab.match(genre, style) if style_lab else None
    q_before = style_lab.score(text, prof) if prof else {"score": 100, "why": []}
    # 文笔不掉 = 按题材挑一位优质作家的笔法当目标，不是照原文的文笔改
    author, author_why = (style_lab.pick_author(text, prof, " ".join([genre, style]))
                          if (style_lab and prof) else (None, ""))
    target = style_lab.blend(prof, author) if (style_lab and prof) else None
    if target:
        try:
            _base = (prof or {}).get("name", "").split("·")[0]
            _ex = _brain_style_samples(_base, 2)
            if _ex:
                target["samples"] = (list(target.get("samples") or [])[:2]
                                     + [x["excerpt"][:160] for x in _ex if x.get("excerpt")])
        except Exception:
            pass
    qs = target or prof                       # 打分也按作家笔法这把尺子
    q_basis = style_lab.score(text, qs) if qs else q_before
    external = bool(prof) and (q_before["score"] < 65
                               or (det_total >= 55 and q_before["score"] < 72))
    floor = max(58, q_basis["score"] + 4) if external else 0

    targets = []
    para_no = 0
    si_para, si_tags = {}, {}
    for si, (is_sep, seg) in enumerate(segs):
        if is_sep or not seg.strip() or len(seg.strip()) < 18:
            continue
        para_no += 1
        score, tags = _para_tics(seg)
        dscore = det_scores.get(para_no, 0)
        p_ai = model_probs.get(si)
        # 直接按 AIGC 终检的判法给这段打分，命中就改
        gscore = 0
        if aigc_guard is not None:
            try:
                gscore = aigc_guard.score(seg)["score"]
            except Exception:
                gscore = 0
        si_para[si] = para_no
        si_tags[si] = tags
        strong = (score >= th
                  or (score >= 2 and dscore >= 45)
                  or (score >= 1 and p_ai is not None and p_ai >= 0.85)
                  or gscore >= 38)
        if strong:
            rank = score + dscore * 0.12 + (p_ai or 0) * 8 + gscore * 0.1
            targets.append((si, seg, tags, rank))

    # 整篇检测明显像 AI、但单段规则都没命中：也要处理，挑检测分最高的几段
    if not targets and det_total >= 80:
        cand = []
        para_no = 0
        for si, (is_sep, seg) in enumerate(segs):
            if is_sep or not seg.strip() or len(seg.strip()) < 18:
                continue
            para_no += 1
            dscore = det_scores.get(para_no, 0)
            p_ai = model_probs.get(si) or 0
            si_para[si] = para_no
            si_tags[si] = _para_tics(seg)[1]
            cand.append((si, seg, _para_tics(seg)[1], dscore + p_ai * 100))
        cand.sort(key=lambda x: -x[3])
        targets = cand[:3]

    if not targets:
        return {"success": True, "text": text, "engine": "ai-scan", "changed": 0,
                "flagged": 0, "keep": 100, "removed": 0, "unchanged": True, "detect": det_total,
                "warn": "没扫到 AI 结构（检测 %d 分），原文没动" % det_total}

    # 按分数挑最多 12 段，太长的先切块
    targets.sort(key=lambda x: -x[3])
    picked = targets[:12]
    repl, fails, changed, reviewed = {}, [], 0, 0

    def work(item):
        si, seg, tags, _score = item
        prev = segs[si - 2][1] if si >= 2 else ""
        nxt = segs[si + 2][1] if si + 2 < len(segs) else ""
        use_prof = target or prof
        if len(seg.strip()) > 1400:
            halves = _chunk_para(seg)
            outs = []
            rv = False
            rd = 0
            for h in halves:
                o, w, r, n = _rewrite_segment(h, prev, nxt, tags, prof=use_prof, floor=floor)
                outs.append(o)
                rv = rv or r
                rd = max(rd, n)
                if w:
                    fails.append(w)
            return si, "".join(outs), rv, rd
        out, why, r, n = _rewrite_segment(seg, prev, nxt, tags, prof=use_prof, floor=floor)
        if why:
            fails.append(why)
        return si, out, r, n

    rounds_total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for si, out, rv, rd in ex.map(work, picked):
            orig = segs[si][1]
            if rv:
                reviewed += 1
            rounds_total += rd
            if out != orig:
                repl[si] = out
                changed += 1

    # 人味瑕疵：只加在本次改写的段落里，整篇最多 2 处（人类作者也会打错几个字）
    flaws = []
    if data.get("human_flaws", True) and repl:
        repl, flaws = _inject_human_flaws(repl, si_para, _cn_len(text))

    out = "".join(repl.get(si, seg) for si, (is_sep, seg) in enumerate(segs))
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.rstrip("\n") + ("\n" if text.endswith("\n") else "")

    # ---- AIGC 终检（规则+统计+本地检测模型）：不通过就一直改，直到通过或连续两轮无进展 ----
    aigc = _aigc_final(out)
    aigc_rounds = 0
    aigc_repairs = []
    aigc_stall = 0
    aigc_best = aigc["score"] if aigc else 100
    while aigc and not aigc.get("pass") and aigc_rounds < 12:
        aigc_rounds += 1
        gtext = _aigc_guide_text(out)
        new_out, reps = _aigc_repair(out, prof=target or prof,
                                     floor=max(62, q_basis["score"] + 4),
                                     guide=gtext, round_no=aigc_rounds)
        if not new_out:
            break
        out = new_out
        aigc_repairs += reps
        aigc = _aigc_final(out)
        if aigc["score"] < aigc_best:
            aigc_best = aigc["score"]
            aigc_stall = 0
        else:
            aigc_stall += 1
            if aigc_stall >= 2:
                break

    if out == text:
        return {"success": True, "text": text, "engine": "ai-scan", "changed": 0,
                "flagged": len(picked), "keep": 100, "removed": 0, "unchanged": True,
                "rounds": rounds_total,
                "warn": "每段最多改了 %d 轮（无进展自动停），仍没过校验，已保留原文%s"
                        % (_HARD_ROUNDS, ("：" + fails[0]) if fails else "")}

    keep = _keep_score(text, out)
    q_after = style_lab.score(out, qs)["score"] if qs else q_before["score"]
    diffs = []
    for si in sorted(repl):
        before = segs[si][1]
        after = repl[si]
        if after == before:
            continue
        tags = si_tags.get(si, [])
        before_sents = [s for s in _sent_list(before) if s.strip()]
        after_sents = [s for s in _sent_list(after) if s.strip()]
        diffs.append({
            "index": si_para.get(si, 0),
            "type": "delete" if not after.strip() else "rewrite",
            "reason": tags,
            "before": before.strip(),
            "after": after.strip(),
            "ops": _para_ops(before, after),
            "chars": [_cn_len(before), _cn_len(after)],
            "sents": [len(before_sents), len(after_sents)],
        })
    # AIGC 终检没过时补改的那几段，也算改动，进明细
    for rp in aigc_repairs:
        b, a2 = rp["before"], rp["after"]
        diffs = [d for d in diffs if d["index"] != rp["index"]]
        diffs.append({
            "index": rp["index"], "type": "rewrite", "reason": ["AIGC 终检未过"],
            "before": b, "after": a2, "ops": _para_ops(b, a2),
            "chars": [_cn_len(b), _cn_len(a2)],
            "sents": [len([s for s in _sent_list(b) if s.strip()]),
                      len([s for s in _sent_list(a2) if s.strip()])],
        })
    diffs.sort(key=lambda d: d["index"])
    deleted_n = sum(1 for d in diffs if d["type"] == "delete")
    changed = len(diffs)
    summary = {
        "changed": changed, "reviewed": reviewed, "flagged": len(picked),
        "deleted": deleted_n, "rewritten": len(diffs) - deleted_n,
        "failed": len(fails),
        "detect": det_total, "keep": keep,
        "chars": [_cn_len(text), _cn_len(out)],
        "sents": [len([s for s in _sent_list(text) if s.strip()]),
                  len([s for s in _sent_list(out) if s.strip()])],
        "paras": [len([s for s in text.split("\n") if s.strip()]),
                  len([s for s in out.split("\n") if s.strip()])],
        "baseline": "author" if (author or external) else "original",
        "profile": (qs or {}).get("name", ""),
        "author": (author or {}).get("name", ""),
        "author_why": author_why,
        "quality": [q_basis["score"], q_after],
        "quality_why": q_basis.get("why") or [],
        "flaws": len(flaws),
        "rounds": rounds_total,
        "aigc": aigc or {},
        "aigc_rounds": aigc_rounds,
    }
    resp = {"success": True, "text": out, "engine": "ai-struct", "detect": det_total,
            "diffs": diffs[:200], "summary": summary, "flaws": flaws,
            "rounds": rounds_total, "aigc": aigc, "aigc_rounds": aigc_rounds,
            "baseline": "author" if (author or external) else "original",
            "profile": (qs or {}).get("name", ""),
            "author": (author or {}).get("name", ""),
            "author_why": author_why,
            "quality": [q_basis["score"], q_after],
            "changed": changed, "reviewed": reviewed, "flagged": len(picked), "removed": 0, "keep": keep}
    notes = []
    if author:
        notes.append("按题材挑了 %s 的笔法当基准（%s），文笔 %d→%d"
                     % (author.get("name", ""), (prof or {}).get("name", ""),
                        q_basis["score"], q_after))
    elif external:
        notes.append("原文文笔本身偏 AI，本次按《%s》范式重写（文笔 %d→%d）"
                     % (prof["name"], q_basis["score"], q_after))
    if changed:
        notes.append("改写 %d 段" % changed)
    if reviewed:
        notes.append("复核 %d 段" % reviewed)
    if flaws:
        notes.append("留了 %d 处人味笔误" % len(flaws))
    if fails:
        notes.append("%d 段模型改写没通过校验，已退回最小改动" % len(fails))
    if rounds_total > max(changed, 0) and changed:
        notes.append("校验没过自动重改，共 %d 轮" % rounds_total)
    if aigc:
        if aigc.get("pass"):
            notes.append("AIGC 终检 %d 分通过%s"
                         % (aigc["score"], ("（补改 %d 轮）" % aigc_rounds) if aigc_rounds else ""))
        else:
            notes.append("AIGC 终检仍未通过（%d 分，%s），已连改 %d 轮无进展，可再点一次"
                         % (aigc.get("score", 0), aigc.get("level", ""), aigc_rounds))
    if len(targets) > len(picked):
        notes.append("还有 %d 段没处理，可再点一次去 AI 味" % (len(targets) - len(picked)))
    if tone:
        notes.append(tone)
    if notes:
        resp["warn"] = "；".join(notes)
    return resp


# ============ AI 味检测引擎（本地多维统计 + 可选模型复核） ============
_AI_CONNECTORS = [
    "然而", "此外", "与此同时", "值得注意的是", "总的来说", "综上所述", "显而易见", "毋庸置疑",
    "众所周知", "从某种意义上说", "在某种程度上", "首先", "其次", "最后", "不仅如此", "更重要的是",
    "在这个过程中", "换言之", "由此可见", "事实上", "在一定程度上", "因此", "从而", "进而",
    "值得一提的是", "不得不说", "不可否认",
]
_AI_HEDGE = [
    "不由自主", "情不自禁", "不禁", "忍不住", "若有所思", "意味深长", "不易察觉", "难以言喻", "无可名状",
    "莫名", "复杂", "某种说不清",
]
_AI_ABSTRACT = [
    "氛围", "气息", "存在感", "张力", "层次", "维度", "内核", "底色", "质感", "节奏感",
    "叙事", "表达", "呈现", "构成", "营造", "某种", "一种说不清", "无数", "千万", "岁月",
]
_SENSE_WORDS = [
    "看见", "听见", "闻到", "触到", "手指", "掌心", "喉咙", "舌尖", "呼吸", "汗", "血",
    "滚烫", "发冷", "发麻", "酸痛", "脚步声", "回声", "气味", "风声", "光影", "烛火", "窗纸",
]
_ACTION_WORDS = [
    "推", "拉", "拽", "握", "抓", "扔", "摔", "坐", "站", "跪", "爬", "跑", "转身", "低头",
    "抬头", "回头", "抬手", "点头", "摇头", "皱眉", "咬", "笑", "哭", "喘", "咳嗽", "掀", "扶",
]


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _scale(v, lo, hi, out_lo=0.0, out_hi=100.0):
    """把 v 从 [lo,hi] 线性映射到 [out_lo,out_hi]，并夹紧"""
    if hi == lo:
        return out_lo
    t = (v - lo) / (hi - lo)
    return _clamp(out_lo + t * (out_hi - out_lo), min(out_lo, out_hi), max(out_lo, out_hi))


# 检测结果缓存：同一段正文 + 同一档位直接复用，保证结果稳定
_DETECT_CACHE = {}


def _para_split(text):
    parts = re.split(r"\n\s*\n|\r\n\s*\r\n", text)
    if len(parts) <= 1:
        parts = [p for p in text.split("\n") if p.strip()]
    return [p.strip() for p in parts if p.strip()]


def _sent_split(text):
    out = []
    for blk in re.split(r"[\n]+", text):
        blk = blk.strip()
        if not blk:
            continue
        for s in re.split(r"(?<=[。！？!?…])", blk):
            s = s.strip()
            if s:
                out.append(s)
    return out


def _cv(values):
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    if avg <= 0:
        return 0.0
    var = sum((v - avg) ** 2 for v in values) / len(values)
    return (var ** 0.5) / avg


def _bigram_entropy(text):
    """近似困惑度：字符 bigram 分布的归一化熵（越低越像机器）"""
    chars = re.sub(r"\s", "", text)
    if len(chars) < 60:
        return None
    grams = [chars[i:i + 2] for i in range(len(chars) - 1)]
    total = len(grams)
    freq = {}
    for g in grams:
        freq[g] = freq.get(g, 0) + 1
    ent = 0.0
    for c in freq.values():
        p = c / total
        ent -= p * math.log(p, 2)
    return ent / 12.0  # 常见中文文本约 6~11 bit，归一到 0.5~0.95


def _hit_density(text, words, n_chars):
    if not n_chars:
        return 0.0
    hits = sum(text.count(w) for w in words)
    return hits / n_chars * 1000


def _ai_advice(dim_scores, raw=""):
    """按维度分数给可执行改法：尽量引用原文里的句子和词，不说空话"""
    text = str(raw or "")
    advice = []
    sents = _sent_split(text) if text else []

    if dim_scores.get("burstiness", 0) > 55:
        long = max(sents, key=len) if sents else ""
        if len(long) >= 40:
            head = long[:28].replace("\n", "")
            advice.append(f"最长那句 {len(long)} 字没断：「{head}…」。在中间找个动作把它劈成两截，后面那截只留五六个字。")
        else:
            advice.append("句子长短太齐。挑三段，每段中间塞一句四五个字的短句，像「她没动。」这种。")

    if dim_scores.get("connector", 0) > 55:
        hit = next((c for c in _AI_CONNECTORS if c in text), "")
        if hit:
            advice.append(f"「{hit}」这种词全章出现了 {text.count(hit)} 次，删掉，用时间或动作接过去。")
        else:
            advice.append("别用「然而/此外/总的来说」过渡，让人物先动，句子跟着动。")

    if dim_scores.get("lexicon", 0) > 55:
        hedges = sorted(((w, text.count(w)) for w in _AI_HEDGE if w in text), key=lambda x: -x[1])[:2]
        if hedges and hedges[0][1] >= 2:
            w, n = hedges[0]
            advice.append(f"「{w}」用了 {n} 次，删到一次；剩下的直接写动作——「她{w}抬起头」改成「她抬头」。")
        else:
            advice.append("同一个修饰别连着用。把「缓缓」「微微」这类换成具体的力气和速度。")

    if dim_scores.get("structure", 0) > 55:
        starts = [p[:6].replace("\n", "") for p in _para_split(text) if len(p) >= 6][:60]
        dup = ""
        for s in set(starts):
            if starts.count(s) >= 2:
                dup = s
                break
        if dup:
            advice.append(f"有 {starts.count(dup)} 段都用「{dup}…」起头，改掉一半，别让读者看出同一个模子。")
        else:
            advice.append("段落别一样长。连着三段差不多字数，就把中间那段拆成两句。")

    if dim_scores.get("detail", 0) > 55:
        advice.append("感官太少。挑一个场景，补三样能摸到的东西：桌沿的凉、灯芯的焦味、袖口的潮。")

    return advice


def _ai_local_report(text):
    """纯本地统计：返回总分、五维得分、段落热力、证据与建议"""
    raw = (text or "").strip()
    plain = re.sub(r"\s", "", raw)
    n_chars = len(plain)
    paras = _para_split(raw)
    sents = _sent_split(raw)
    lens = [len(re.sub(r"\s", "", s)) for s in sents]
    avg_len = (sum(lens) / len(lens)) if lens else 0.0
    cv = _cv(lens)
    long_ratio = (sum(1 for x in lens if x >= 60) / len(lens)) if lens else 0.0
    short_ratio = (sum(1 for x in lens if x <= 8) / len(lens)) if lens else 0.0

    ttr = (len(set(plain)) / n_chars) if n_chars else 1.0
    grams = [plain[i:i + 4] for i in range(max(0, n_chars - 3))]
    rep4 = (1 - len(set(grams)) / len(grams)) if grams else 0.0
    ent = _bigram_entropy(raw)

    conn_d = _hit_density(raw, _AI_CONNECTORS, n_chars)
    hedge_d = _hit_density(raw, _AI_HEDGE, n_chars)
    abs_d = _hit_density(raw, _AI_ABSTRACT, n_chars)
    sense_d = _hit_density(raw, _SENSE_WORDS, n_chars)
    action_d = _hit_density(raw, _ACTION_WORDS, n_chars)

    plens = [len(p) for p in paras]
    pcv = _cv(plens)
    starts = [p[:2] for p in paras if len(p) >= 2]
    start_rep = 0.0
    if starts:
        top = max(starts.count(s) for s in set(starts))
        start_rep = top / len(starts)
    dialogue_d = (raw.count("“") + raw.count("「")) / max(1, n_chars) * 1000
    dash = raw.count("——") + raw.count("…")
    q = raw.count("？") + raw.count("！")
    punct_diversity = (dash + q) / max(1, n_chars) * 1000

    # --- 五维：分数越高越像 AI ---
    d_burst = _scale(cv, 0.30, 0.95, 94, 16) * 0.7 + long_ratio * 26
    d_burst += max(0.0, (0.16 - short_ratio) * 60)  # 几乎没有短句
    if ent is not None:
        d_burst = d_burst * 0.72 + _scale(ent, 0.62, 0.88, 84, 18) * 0.28

    d_lex = _scale(ttr, 0.30, 0.55, 86, 22) * 0.45 + _scale(rep4, 0.02, 0.14, 24, 92) * 0.35
    d_lex += _scale(hedge_d, 1.0, 9.0, 20, 90) * 0.2

    d_conn = _scale(conn_d, 0.3, 4.5, 22, 95) * 0.62 + _scale(abs_d, 0.5, 7.0, 18, 92) * 0.38

    short_para_ratio = (sum(1 for p in paras if len(re.sub(r"\s", "", p)) <= 12) / len(paras)) if paras else 0.0
    d_struct = _scale(pcv, 0.18, 0.85, 84, 28) * 0.26 + start_rep * 100 * 0.24
    d_struct += _scale(dialogue_d, 0.2, 6.0, 74, 26) * 0.18
    d_struct += _scale(short_para_ratio, 0.15, 0.60, 20, 92) * 0.32

    d_detail = _scale(sense_d + action_d, 2.0, 22.0, 88, 20) * 0.72
    d_detail += _scale(punct_diversity, 0.3, 6.0, 84, 22) * 0.28

    dims = [
        ("burstiness", "句长节奏", d_burst),
        ("lexicon", "用词多样性", d_lex),
        ("connector", "连接与套话", d_conn),
        ("structure", "段落结构", d_struct),
        ("detail", "细节质感", d_detail),
    ]
    weights = {"burstiness": 0.26, "lexicon": 0.2, "connector": 0.2, "structure": 0.16, "detail": 0.18}
    total = sum(v * weights[k] for k, _, v in dims)

    # 短文本置信度低：向 50 靠拢
    if n_chars < 300:
        total = total * (n_chars / 300.0) + 50 * (1 - n_chars / 300.0)

    reasons = []
    evidence = []
    if cv and cv < 0.4:
        reasons.append(f"句长过于均匀（变异系数 {cv:.2f}，人写通常在 0.5~1.0）")
    if long_ratio > 0.22:
        reasons.append(f"长句占比 {long_ratio * 100:.0f}%，缺短句与断句呼吸")
    if conn_d > 2.2:
        reasons.append(f"AI 式连接词密度偏高（每千字 {conn_d:.1f} 处）")
    if hedge_d > 5.0:
        reasons.append(f"套话修饰偏多（难以言喻/不由自主/情不自禁 等，每千字 {hedge_d:.1f} 处）")
    if abs_d > 4.0:
        reasons.append(f"抽象名词偏多（氛围/张力/质感 等，每千字 {abs_d:.1f} 处）")
    if rep4 > 0.09:
        reasons.append(f"四字片段重复率 {rep4 * 100:.1f}%，存在机械复读")
    if ttr < 0.34:
        reasons.append(f"用字多样度偏低（{ttr:.2f}），词汇偏窄")
    if start_rep > 0.34:
        reasons.append(f"段落开头重复度 {start_rep * 100:.0f}%，读起来同一种起手式")
    if dialogue_d < 1.0 and n_chars > 600:
        reasons.append("几乎没有对话，叙述一顺到底")
    if sense_d + action_d < 6.0 and n_chars > 500:
        reasons.append("动作与感官细节偏少，画面偏空")
    if short_para_ratio > 0.45 and len(paras) >= 10:
        reasons.append(f"单句成段占比 {short_para_ratio * 100:.0f}%，靠断行造停顿，是常见的机器排版习惯")

    for pat, label in [
        (r"不仅[^。！？]{0,24}而且", "对仗式「不仅…而且」"),
        (r"既[^。！？]{0,20}又[^。！？]{0,20}", "对仗式「既…又…」"),
        (r"不是[^。！？]{0,24}而是", "解释型「不是…而是」"),
        (r"值得(注意|一提)的是", "评论腔「值得注意的是」"),
    ]:
        m = re.search(pat, raw)
        if m:
            evidence.append({"kind": label, "snippet": m.group(0)[:40]})

    advice = _ai_advice({k: v for k, _n, v in dims}, raw)

    # 段落热力
    para_rows = []
    for i, p in enumerate(paras, 1):
        pn = max(1, len(re.sub(r"\s", "", p)))
        ps = 0.0
        ps += _scale(_hit_density(p, _AI_HEDGE, pn), 0.8, 10.0, 18, 92) * 0.34
        ps += _scale(_hit_density(p, _AI_ABSTRACT, pn), 0.4, 8.0, 16, 92) * 0.26
        ps += _scale(_hit_density(p, _AI_CONNECTORS, pn), 0.2, 5.0, 18, 92) * 0.2
        if len(p) > 120:
            ps += 12
        if len(p) < 24:
            ps += 6
        para_rows.append({
            "index": i,
            "score": int(round(_clamp(ps))),
            "chars": pn,
            "preview": p[:36],
        })

    # 句子级证据：挑最像 AI 的句子
    sent_rows = []
    for s in sents:
        sn = max(1, len(re.sub(r"\s", "", s)))
        sc = 0.0
        sc += _hit_density(s, _AI_HEDGE, sn) * 11
        sc += _hit_density(s, _AI_ABSTRACT, sn) * 13
        sc += _hit_density(s, _AI_CONNECTORS, sn) * 15
        if len(s) >= 55:
            sc += 12
        sent_rows.append({"text": s[:90], "score": int(round(_clamp(sc)))})
    sent_rows = sorted(sent_rows, key=lambda x: -x["score"])[:6]

    return {
        "score": int(round(_clamp(total))),
        "dimensions": [{"key": k, "name": n, "score": int(round(_clamp(v)))} for k, n, v in dims],
        "paragraphs": para_rows,
        "sentences": sent_rows,
        "reasons": reasons[:6],
        "advice": advice[:5],
        "evidence": evidence[:4],
        "stats": {
            "chars": n_chars,
            "paragraphs": len(paras),
            "sentences": len(sents),
            "avg_sentence": round(avg_len, 1),
            "sentence_cv": round(cv, 2),
            "type_token_ratio": round(ttr, 2),
            "repeat4": round(rep4, 3),
            "dialogue_per_1000": round(dialogue_d, 1),
            "sense_per_1000": round(sense_d + action_d, 1),
        },
    }


JUDGE_CACHE_FILE = os.path.join(DATA_DIR, "data", "ai_judge_cache.json")
_JUDGE_CACHE = None

# ---- 外部 AI 检测模型（AIGC_detector_zhv3，ONNX INT8，本地推理） ----
AI_MODEL_DIR = os.path.join(APP_DIR, "models", "ai-detect-zhv3")
_AI_MODEL = None
_AI_MODEL_TRIED = False


def _ai_model_load():
    """懒加载本地检测模型；缺依赖/缺文件就返回 None，不影响其它功能"""
    global _AI_MODEL, _AI_MODEL_TRIED
    if _AI_MODEL_TRIED:
        return _AI_MODEL
    _AI_MODEL_TRIED = True
    try:
        import importlib
        # 用动态导入，避免打包工具静态分析把 onnxruntime 的 quantize/tools 一起拖进去
        ort = importlib.import_module("onnxruntime")
        Tokenizer = importlib.import_module("tokenizers").Tokenizer
        mp = os.path.join(AI_MODEL_DIR, "model.onnx")
        tp = os.path.join(AI_MODEL_DIR, "tokenizer.json")
        if not (os.path.exists(mp) and os.path.exists(tp)):
            return None
        tok = Tokenizer.from_file(tp)
        sess = ort.InferenceSession(mp, providers=["CPUExecutionProvider"])
        _AI_MODEL = {"tok": tok, "sess": sess, "name": "AIGC_detector_zhv3"}
    except Exception as e:
        print("AI 检测模型不可用：", e)
        _AI_MODEL = None
    return _AI_MODEL


def _ai_model_probs(texts):
    """给每段文字算 P(AI)；返回 0~1 的列表，模型不可用返回 None"""
    m = _ai_model_load()
    if not m:
        return None
    import numpy as np
    tok = m["tok"]
    sess = m["sess"]
    out = []
    for t in texts:
        s = re.sub(r"\s", "", str(t or ""))
        if len(s) < 12:
            out.append(None)
            continue
        try:
            ids = tok.encode(s).ids[:512]
            feed = {
                "input_ids": np.array([ids], dtype=np.int64),
                "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
                "token_type_ids": np.zeros((1, len(ids)), dtype=np.int64),
            }
            logits = sess.run(None, feed)[0][0]
            e = np.exp(logits - logits.max())
            p = e / e.sum()
            out.append(float(p[1]))
        except Exception:
            out.append(None)
    return out


def _ai_model_report(text, paras):
    """整章分数 + 逐段分数（与 paras 一一对应，短段给 None）"""
    m = _ai_model_load()
    if not m:
        return None
    rows = list(paras or [])
    probs = _ai_model_probs(rows) if rows else []
    valid = [p for p in probs if p is not None]
    if len(valid) >= 2:
        avg = sum(valid) / len(valid)
        return {
            "name": m["name"],
            "score": int(round(avg * 100)),
            "max": int(round(max(valid) * 100)),
            "chunks": len(valid),
            "para": probs,
        }
    # 段落太少：按 400 字切块，只给整章分
    plain = re.sub(r"\s", "", text or "")
    if len(plain) < 80:
        return None
    chunks = [plain[i:i + 460] for i in range(0, len(plain), 400)][:60]
    cp = _ai_model_probs(chunks)
    cp = [p for p in (cp or []) if p is not None]
    if not cp:
        return None
    avg = sum(cp) / len(cp)
    return {
        "name": m["name"],
        "score": int(round(avg * 100)),
        "max": int(round(max(cp) * 100)),
        "chunks": len(cp),
        "para": None,
    }


def _judge_cache_load():
    global _JUDGE_CACHE
    if _JUDGE_CACHE is None:
        try:
            with open(JUDGE_CACHE_FILE, encoding="utf-8") as f:
                _JUDGE_CACHE = json.load(f)
        except Exception:
            _JUDGE_CACHE = {}
        if not isinstance(_JUDGE_CACHE, dict):
            _JUDGE_CACHE = {}
    return _JUDGE_CACHE


def _judge_cache_get(k):
    return _judge_cache_load().get(k)


def _judge_cache_put(k, v):
    c = _judge_cache_load()
    c[k] = v
    while len(c) > 200:
        c.pop(next(iter(c)))
    try:
        os.makedirs(os.path.dirname(JUDGE_CACHE_FILE), exist_ok=True)
        tmp = JUDGE_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
        os.replace(tmp, JUDGE_CACHE_FILE)
    except Exception:
        pass


def _clean_advice(items, text):
    """只留「原文」→「改写」这种能照着改的条目，引文必须在正文里出现过"""
    body = str(text or "")
    out = []
    for raw in (items or []):
        a = str(raw or "").strip().replace("『", "「").replace("』", "」").replace("“", "「").replace("”", "」")
        if "「" not in a:
            continue
        qs = [q.strip() for q in re.findall(r"「([^」]{2,40})」", a)]
        if not qs or not any(q and q in body for q in qs):
            continue
        # 模型常把改写句的右引号漏掉，补在句末标点前
        if a.count("「") > a.count("」"):
            for _ in range(a.count("「") - a.count("」")):
                if a and a[-1] in "。！？!?.":
                    a = a[:-1] + "」" + a[-1]
                else:
                    a += "」"
        out.append(a[:180])
        if len(out) >= 4:
            break
    return out


def _ai_judge_report(text, local):
    """模型复核：只在有 API Key 时调用，返回可合并的分项与逐段定位。
    同一段正文只问模型一次，结果落盘复用，保证多次检测完全一致。"""
    ck = hashlib.sha1(
        (re.sub(r"\s+", " ", text).strip() + "|" + str(getattr(ai_service, "model", "")) + "|" + str(local["score"]) + "|v3").encode("utf-8")
    ).hexdigest()
    hit = _judge_cache_get(ck)
    if isinstance(hit, dict) and hit:
        return hit
    dsum = "、".join(f"{d['name']}{d['score']}" for d in local["dimensions"])
    sample = (text[:2600] + "\n……\n" + text[-1400:]) if len(text) > 4200 else text
    prompt = f"""你是中文小说「AI 味」审校，标准参照 GPTZero / Originality 一类检测器：看句长节奏、用词多样性、套话密度、段落结构、细节质感。

本地统计：总分 {local['score']}；{dsum}；{local['stats']}

正文：
<<<
{sample}
>>>

只输出一个 JSON：
{{"score":0-100,"verdict":"一句话判词",
 "dimensions":{{"burstiness":0,"lexicon":0,"connector":0,"structure":0,"detail":0}},
 "paragraphs":[{{"index":1,"score":0,"problem":"这段像 AI 的具体原因","snippet":"原文片段15字内"}}],
 "reasons":["最多5条，要具体"],
 "advice":["2~4条，固定格式：「原文半句」→「改后的完整句」"]}}
paragraphs 只挑最像 AI 的 3~6 段。分数越高越像 AI。
advice 的硬要求：引文必须逐字出现在正文里（8~14 字），引号只用「」；箭头右边要写成能直接替换的完整句子；不许先说理再举例，不许用『』或“可以这样写”，每条一行不要编号。不要解释，不要 Markdown。"""
    jr = _ai_json(prompt, max_tokens=2000, temperature=0, det=True)
    if isinstance(jr, dict) and jr:
        _judge_cache_put(ck, jr)
    return jr


@app.post("/api/ai/detect")
def api_ai_detect(data: dict):
    """AI 味检测：本地多维统计为主，配置了 API Key 再叠加模型复核。
    同一段正文 + 同一档位，结果固定（模型走 temperature=0 + 固定 seed，且命中缓存直接复用）。"""
    text = (data.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="没有可检测的文本")
    if len(re.sub(r"\s", "", text)) < 40:
        raise HTTPException(status_code=400, detail="正文太短，至少 40 字才检测得准")

    mode = (data.get("mode") or "wen")
    has_ai = bool(getattr(ai_service, "api_key", ""))
    key = hashlib.sha1(
        ("|".join([re.sub(r"\s+", " ", text).strip(), mode,
                   "ai" if has_ai else "local",
                   (getattr(ai_service, "model", "") or "") if has_ai else "",
                   "model" if os.path.exists(os.path.join(AI_MODEL_DIR, "model.onnx")) else "nomodel",
                   "v3"])).encode("utf-8")
    ).hexdigest()
    if key in _DETECT_CACHE:
        hit = json.loads(json.dumps(_DETECT_CACHE[key], ensure_ascii=False))
        hit["cached"] = True
        return hit

    local = _ai_local_report(text)
    score = local["score"]
    engine = "local"
    verdict = ""
    reasons = list(local["reasons"])
    advice = list(local["advice"])
    model_advice = []
    dims = local["dimensions"]
    paras = local["paragraphs"]

    if getattr(ai_service, "api_key", ""):
        try:
            jr = _ai_judge_report(text, local)
            ai_score = jr.get("score")
            if isinstance(ai_score, (int, float)):
                score = int(round(_clamp(float(ai_score) * 0.55 + local["score"] * 0.45)))
                engine = "local+ai"
            verdict = str(jr.get("verdict") or "")[:120]
            ad = jr.get("dimensions") or {}
            if isinstance(ad, dict):
                merged = []
                for d in dims:
                    v = ad.get(d["key"])
                    if isinstance(v, (int, float)):
                        merged.append({"key": d["key"], "name": d["name"],
                                       "score": int(round(_clamp(float(v) * 0.55 + d["score"] * 0.45)))})
                    else:
                        merged.append(d)
                dims = merged
            for r in (jr.get("reasons") or [])[:5]:
                r = str(r).strip()
                if r and r not in reasons:
                    reasons.append(r)
            for a in _clean_advice(jr.get("advice"), text):
                if a not in model_advice:
                    model_advice.append(a)
            ai_paras = jr.get("paragraphs") or []
            if isinstance(ai_paras, list) and ai_paras:
                byidx = {p["index"]: p for p in paras}
                for ap in ai_paras[:8]:
                    if not isinstance(ap, dict):
                        continue
                    idx = int(ap.get("index") or 0)
                    if idx in byidx and isinstance(ap.get("score"), (int, float)):
                        byidx[idx]["score"] = int(round(_clamp(float(ap["score"]) * 0.6 + byidx[idx]["score"] * 0.4)))
                        if ap.get("problem"):
                            byidx[idx]["problem"] = str(ap["problem"])[:60]
        except Exception as e:
            reasons.append("模型复核未完成：" + str(e)[:60])

    # 外部检测模型：AIGC_detector_zhv3（本地 ONNX，中文 AIGC 专项）
    model_info = None
    try:
        mres = _ai_model_report(text, _para_split(text.strip()))
        if mres:
            score = int(round(_clamp(mres["score"] * 0.55 + score * 0.45)))
            engine = engine + "+model"
            model_info = {"name": mres["name"], "score": mres["score"], "max": mres["max"], "chunks": mres["chunks"]}
            if mres.get("para"):
                for i, p in enumerate(paras):
                    mp = mres["para"][i] if i < len(mres["para"]) else None
                    if mp is not None:
                        p["score"] = int(round(_clamp(mp * 100 * 0.7 + p["score"] * 0.3)))
    except Exception as e:
        print("检测模型出错：", e)

    score = int(round(_clamp(score)))
    # 文 / 武 两档：武档更严格（对标检测站的「严格模式」）
    if (data.get("mode") or "wen") == "wu":
        score = int(round(_clamp(score * 1.12 + 6)))
    # 合并后用最新维度重算改法，模型给的具体改法排在最前
    advice = _ai_advice({d["key"]: d["score"] for d in dims}, text)
    if model_advice:
        advice = model_advice if len(model_advice) >= 3 else model_advice + advice
    if not advice:
        advice = ["这章读着像人写的，别动。" if score < 45 else "挑最热的那两段重写，其它先别碰。"]
    if score < 20:
        grade, rec = "人味充足", "保持现在的手感即可"
    elif score < 40:
        grade, rec = "较自然", "个别句子再松一点会更像手写"
    elif score < 60:
        grade, rec = "有痕迹", "建议按下面的建议改一遍，或用「去 AI 味」"
    elif score < 80:
        grade, rec = "AI 味明显", "句长与套话问题突出，建议整段重写"
    else:
        grade, rec = "高度疑似 AI", "必须重写：换成具体动作、细节和有个性的句子"

    hot = sorted([p for p in paras if p["score"] >= 45], key=lambda x: -x["score"])[:5]
    result = {
        "ai_probability": score,
        "human_probability": 100 - score,
        "grade": grade,
        "recommendation": rec,
        "verdict": verdict,
        "dimensions": dims,
        "paragraphs": paras,
        "hot_paragraphs": hot,
        "sentences": local.get("sentences", []),
        "mode": mode,
        "reasons": reasons[:8],
        "advice": advice[:6],
        "evidence": local.get("evidence", []),
        "stats": local["stats"],
        "engine": engine,
        "model": model_info,
        "length": len(text),
        "cached": False,
    }
    if "ai" in engine:
        if len(_DETECT_CACHE) >= 40:
            _DETECT_CACHE.pop(next(iter(_DETECT_CACHE)))
        _DETECT_CACHE[key] = json.loads(json.dumps(result, ensure_ascii=False))
    return result


# ============ 随机取名（先选类别，再按细分生成） ============
NAME_BANK = {
    "surname1": list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯卢莫房裘缪解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊惠甄曲封芮储靳段富巫乌焦巴牧隗山谷车侯全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶黎薄印宿白怀蒲台从鄂索咸赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀浦尚农温别庄晏柴瞿阎慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧沃利蔚越隆师巩聂晁勾融冷辛那简饶空曾沙养鞠须丰巢关蒯相查后荆红游竺权盖益桓"),
    "surname2": "欧阳 太史 端木 上官 司马 东方 独孤 南宫 万俟 闻人 夏侯 诸葛 尉迟 公羊 赫连 澹台 皇甫 宗政 濮阳 公冶 太叔 申屠 公孙 慕容 仲孙 钟离 长孙 宇文 司徒 鲜于 司空 闾丘 子车 司寇 巫马 公良 漆雕 乐正 谷梁 拓跋 夹谷 轩辕 令狐 百里 呼延 东郭 南门 第五 西门".split(),
    "given_m": "行舟 见山 长风 无咎 承砚 玄策 破军 寒山 望舒 听澜 亦舟 归鹤 云深 孤鸿 沉璧 断水 执锐 叩雪 青崖 逐野 长离 朝戈 临渊 肃之 问津 折枝 惊蛰 敛锋 策渊 燃犀 昭野 疏朗 渡舟 冷杉 岑野 峻之 云霄 逆川 拂衣 观澜 弈秋 长庚".split(),
    "given_f": "晚棠 见月 疏影 听雪 知微 望舒 青梧 绾绾 阿箬 栖迟 昭昭 素问 云岫 敛眉 阿芜 眠雪 栖月 汀兰 白露 云漪 照水 拂云 疏桐 静姝 令仪 采薇 落蘅 阿沅 初霁 泠泠 月见 若耶 阿萝 青禾 阿皎 敛秋 拾光 南枝 小满 阿棠".split(),
    "given_n": "青 澈 舟 隐 简 序 言 川 蓝 未 迟 白 岑 风 岚 岐 七 九 之 也 归 渡 栖 疏 听 见 望 行 云 与".split(),
    "west_given": "艾琳 凯尔 罗伊 塞西尔 伊恩 莉亚 诺尔 阿德里安 薇拉 卡莲 埃德加 索菲 卢恩 米娅 加文 伊莎 奥兰 温妮 里昂 黛西".split(),
    "west_family": "凡德尔 洛克哈特 阿什福德 温特斯 布莱克 卡文迪许 蒙特 格雷 塞尔温 霍尔特 兰斯 艾略特 摩恩 斯特林 沃伦 奥斯汀".split(),
    "jp_surname": "佐藤 铃木 高桥 田中 渡边 伊藤 山本 中村 小林 加藤 吉田 山田 佐佐木 山口 松本 井上 木村 斋藤 清水 森".split(),
    "jp_given": "樱 凛 悠 葵 遥 澪 结衣 千夏 阳太 悠斗 莲 枫 雪 隼 琴 叶 铃 茜".split(),
    "place_mod": "青 玄 赤 苍 幽 雪 云 月 落 断 九 万 千 无 浮 沉 孤 望 寒 烬 星 澜 雁 雾 风 雷 血 铁 玉 金 白 墨 霜 岚 长夜 空灵 重明 照影 惊鸿 归墟 不周 沧溟".split(),
    "place_core": "云 风 山 川 河 海 林 原 野 关 谷 岭 渊 泽 陵 台 阁 渡 泉 溪 崖 丘 沙 漠 雪 霜 松 枫 竹 石 湖 江 洛 渭 淮 湘 梧 桐 芦 荻".split(),
    "force_mod": "天 玄 九 幽 赤 万 太 清 寒 落 浮 星 血 青 无 太虚 问天 藏锋 凌霄 归墟 不夜 长歌 折戟 焚天 听雪".split(),
    "force_core": "剑 刀 丹 符 阵 兽 魔 佛 道 武 罗 冥 雪 月 星 铁 风 雷 霜 血 山海 昆仑 蓬莱 玄天 青冥".split(),
    "force_suffix": "宗 门 派 阁 殿 堂 会 帮 盟 教 谷 山庄 书院 商会 军 府 司 楼".split(),
    "art_mod": "九转 太虚 焚天 玄天 大衍 碎星 青冥 寒山 无相 太上 混元 落霞 流云 惊鸿 斩月 破军 周天 归元 洗髓 残阳 孤星 玄阴 至阳 天一 叩月".split(),
    "art_core": "剑诀 剑意 刀法 拳经 身法 步法 心法 真解 神功 秘典 指法 掌法 丹经 阵图 神通 十三式 九章 残卷 总纲 要旨".split(),
    "gear_mod": "青冥 玄铁 赤霄 落霞 寒星 碎月 焚天 承影 太阿 流光 沉璧 断水 惊鸿 苍梧 白虹 龙鳞 冰魄 雷纹 照影".split(),
    "gear_core": "剑 刀 枪 戟 弓 甲 盾 珠 幡 镜 钟 印 灯 扇 琴 笛 铃 镯 戒 链 簪 靴 袍 冠 鼎 塔".split(),
    "pill_mod": "九转 回春 洗髓 破障 凝神 养魂 龙血 千年 赤炎 冰心 玄元 太一 续命 归元 醒神 化骨 醉仙 七宝".split(),
    "pill_core": "丹 散 膏 丸 液 露 香 汤".split(),
    "beast_mod": "赤焰 冰甲 铁背 九尾 吞月 幽冥 碧眼 雷纹 血牙 玄鳞 霜翼 焚山 踏云 双头 三目 无面 白骨".split(),
    "beast_core": "虎 狼 蟒 蛟 雕 猿 蛛 蝎 鹿 犀 鲸 蛇 熊 狐 龟 鹏 貔 貅 狰 狻".split(),
    "move_mod": "落霞 惊鸿 斩月 破军 追风 断水 拂云 回雪 燃犀 叩月 折梅 听雨 裂石 崩山 逆流 孤鸿 摧心".split(),
    "move_core": "斩 刺 式 击 破 落 舞 诀 指 掌 步 影 十三剑 七式 三叠".split(),
    "title_mod": "剑 刀 枪 血 雪 孤 苍 幽 无 千 万 赤 寒 醉 笑 断 焚 沉 眠 空".split(),
    "title_core": "魔 圣 君 尊 王 侯 仙 神 客 生 子 娘子 郎 居士 先生 老祖 真人".split(),
    "herb_mod": "九叶 血 幽冥 千年 赤焰 冰心 紫芝 龙涎 月华 星陨 玄阴 太岁".split(),
    "herb_core": "草 花 藤 果 参 莲 竹 芝 芽".split(),
    "array_mod": "周天 九宫 困龙 锁灵 焚天 血煞 迷魂 两仪 四象 五行 八卦 十绝".split(),
    "array_core": "阵 大阵 图 禁 阵盘".split(),
    "treasure_mod": "定海 照影 藏锋 焚天 聚灵 锁魂 破妄 玄元 太虚".split(),
    "treasure_core": "珠 镜 钟 印 塔 鼎 幡 灯 卷 环".split(),
    "coin_mod": "灵 玄 赤 紫 白 墨".split(),
    "coin_core": "石 晶 币 票 贝".split(),
    "book_mod": "太虚 无相 焚天 清心 归元 玄天 山河".split(),
    "book_core": "经 典 策 录 篇 谱 志 卷".split(),
    "tool_mod": "青玉 玄铁 赤铜 冰魄 紫檀 沉水".split(),
    "tool_core": "鼎 炉 灯 琴 棋 笔 砚 壶 扇 伞 匣".split(),
    "task": "护送商队 寻药 剿匪 夺宝 探查秘境 守夜 押镖 清剿妖兽 寻人 送信 采药 护道".split(),
}

PLACE_SUFFIX = {
    "城池": ["城", "州", "郡", "府", "京", "都"],
    "山川": ["山", "峰", "岭", "岳", "崖", "谷", "川"],
    "村落": ["村", "庄", "寨", "屯", "坞"],
    "秘境": ["秘境", "禁地", "遗迹", "洞天", "幻境"],
    "关隘": ["关", "隘", "口", "要塞"],
    "海域": ["海", "洋", "湾", "渡", "江", "河", "湖"],
}
FORCE_SUFFIX = {
    "宗门": ["宗", "门", "派", "阁", "殿", "观"],
    "王朝": ["朝", "国", "王朝", "帝庭"],
    "帮派": ["帮", "会", "盟", "堂"],
    "商会": ["商会", "行", "号", "楼"],
    "军队": ["军", "营", "卫", "铁骑"],
    "教会": ["教", "神殿", "圣庭", "道场"],
}
NAME_CAT_DESC = {
    "人物": "中文人物名（姓+名，2-4 字）",
    "地名": "中文地名（城池 / 山川 / 村落 / 秘境 / 关隘 / 海域，2-6 字）",
    "势力": "中文势力名（宗门 / 王朝 / 帮派 / 商会 / 军队 / 教会，3-6 字）",
    "功法": "中文功法武学名（内功心法 / 剑法 / 刀法 / 身法 / 掌法 / 阵法 / 神通，3-6 字）",
    "装备": "中文装备法宝名（剑 / 刀 / 枪 / 弓 / 甲 / 法器 / 饰品 / 材料，2-6 字）",
    "丹药": "中文丹药名（2-5 字）",
    "妖兽": "中文妖兽灵兽名（2-5 字）",
    "招式": "中文招式名（2-6 字）",
    "称号": "中文人物称号名号（2-5 字，如 剑魔、雪中客）",
    "杂项": "中文杂项名（灵植 / 阵法 / 秘宝 / 货币 / 典籍 / 器物，2-6 字）",
}
MISC_SUBS = ["灵植", "阵法", "秘宝", "货币", "典籍", "器物", "任务"]


def _local_names(category, subtype, opts, count, exclude):
    """本地组合式取名：类别 + 细分 + 词库拼接，不依赖网络"""
    import random
    rnd = random.Random()
    out = []
    seen = set([str(x) for x in (exclude or [])])

    def add(name):
        name = (name or "").strip()
        if not name or name in seen or len(name) > 8:
            return
        seen.add(name)
        out.append(name)

    def pick(key):
        pool = NAME_BANK.get(key) or [""]
        return rnd.choice(pool)

    all_place = [s for v in PLACE_SUFFIX.values() for s in v]
    all_force = [s for v in FORCE_SUFFIX.values() for s in v]
    guard = 0
    while len(out) < count and guard < count * 80:
        guard += 1
        if category == "人物":
            style = opts.get("style") or "古风"
            gender = opts.get("gender") or "随机"
            if gender == "随机":
                gender = rnd.choice(["男", "女"])
            if style == "西幻":
                add(pick("west_given") + "·" + pick("west_family"))
                continue
            if style == "日式":
                add(pick("jp_surname") + pick("jp_given"))
                continue
            surname = (opts.get("surname") or "").strip()
            if not surname:
                sc = opts.get("surnameCount") or "随机"
                if sc == "随机":
                    sc = "复姓" if rnd.random() < 0.2 else "单姓"
                surname = pick("surname2") if sc == "复姓" else pick("surname1")
            given = pick("given_n") if rnd.random() < 0.22 else pick("given_m" if gender == "男" else "given_f")
            add(surname + given)
            continue
        if category == "地名":
            suf = rnd.choice(PLACE_SUFFIX.get(subtype) or all_place)
            add(pick("place_mod") + pick("place_core") + suf)
            continue
        if category == "势力":
            suf = rnd.choice(FORCE_SUFFIX.get(subtype) or all_force)
            add(pick("force_mod") + pick("force_core") + suf)
            continue
        if category == "功法":
            core = subtype if subtype and subtype != "随机" and subtype in NAME_BANK["art_core"] else pick("art_core")
            add(pick("art_mod") + core)
            continue
        if category == "装备":
            core = subtype if subtype and subtype != "随机" and subtype in NAME_BANK["gear_core"] else pick("gear_core")
            add(pick("gear_mod") + core)
            continue
        if category == "丹药":
            add(pick("pill_mod") + pick("pill_core"))
            continue
        if category == "妖兽":
            add(pick("beast_mod") + pick("beast_core"))
            continue
        if category == "招式":
            add(pick("move_mod") + pick("move_core"))
            continue
        if category == "称号":
            add(pick("title_mod") + pick("title_core"))
            continue
        sub = subtype if subtype in MISC_SUBS else rnd.choice(MISC_SUBS)
        if sub == "灵植":
            add(pick("herb_mod") + pick("herb_core"))
        elif sub == "阵法":
            add(pick("array_mod") + pick("array_core"))
        elif sub == "秘宝":
            add(pick("treasure_mod") + pick("treasure_core"))
        elif sub == "货币":
            add(pick("coin_mod") + pick("coin_core"))
        elif sub == "典籍":
            add(pick("book_mod") + pick("book_core"))
        elif sub == "器物":
            add(pick("tool_mod") + pick("tool_core"))
        else:
            add(pick("task"))
    return out


@app.post("/api/ai/names")
def api_ai_names(data: dict):
    """随机取名：先按类别（人名/地名/势力/功法/装备/丹药/妖兽/招式/称号/杂项）再生成"""
    category = data.get("category") or "人物"
    subtype = data.get("subtype") or "随机"
    count = max(1, min(int(data.get("count") or 12), 40))
    genre = data.get("genre") or ""
    requirements = (data.get("requirements") or "").strip()
    exclude = data.get("exclude") or []
    opts = {
        "gender": data.get("gender") or "随机",
        "style": data.get("style") or "古风",
        "surnameCount": data.get("surnameCount") or "随机",
        "surname": data.get("surname") or "",
    }

    if ai_service.api_key:
        extra = []
        if category == "人物":
            extra.append(f"性别：{opts['gender']}；风格：{opts['style']}；姓数：{opts['surnameCount']}")
            if opts["surname"]:
                extra.append(f"必须姓：{opts['surname']}")
        if subtype and subtype != "随机":
            extra.append(f"细分：{subtype}")
            if category == "地名" and subtype in PLACE_SUFFIX:
                extra.append("必须以「%s」结尾" % "/".join(PLACE_SUFFIX[subtype]))
            if category == "势力" and subtype in FORCE_SUFFIX:
                extra.append("必须以「%s」结尾" % "/".join(FORCE_SUFFIX[subtype]))
        if exclude:
            extra.append("不要与这些重复：" + "、".join([str(x) for x in exclude[:30]]))
        prompt = f"""为一部{genre or '小说'}生成 {count} 个{NAME_CAT_DESC.get(category, '名称')}。
类别：{category}
{'；'.join(extra)}
风格要求：{requirements or '贴合题材气质，不要烂大街'}
要求：互不重复，读音上口，有一定文化质感。
只输出名称，用顿号分隔，不要编号、不要解释。"""
        try:
            # 取名不需要人性化改写，直接短超时调用，避免卡住界面
            import requests
            url = (getattr(ai_service, "base_url", "") or "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"
            payload = {
                "model": getattr(ai_service, "model", "") or "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是中文小说起名助手，只输出名称列表，不解释。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 1.05,
                "max_tokens": 700,
            }
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {ai_service.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            names = []
            for raw in re.split(r'[、,，\n]+', text):
                n = re.sub(r'^\s*[\d一二三四五六七八九十]+[\.、\)]?\s*', '', raw).strip()
                n = n.strip('《》「」""\' ')
                if 1 <= len(n) <= 14 and re.fullmatch(r'[\u4e00-\u9fa5·]+', n) and n not in names and n not in exclude:
                    names.append(n)
            if names:
                # AI 给不够就用本地词库补齐，保证一次生成数量稳定
                if len(names) < count:
                    names += _local_names(category, subtype, opts, count - len(names), list(names) + list(exclude))
                return {"success": True, "names": names[:count], "engine": "ai", "category": category}
        except Exception:
            pass

    names = _local_names(category, subtype, opts, count, exclude)
    return {"success": True, "names": names, "engine": "local", "category": category}


@app.post("/api/ai/idea")
def api_ai_idea(data: dict):
    """卡文急救：给三个「如果」"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    prompt = f"""《{project.get('name', '')}》写到「{data.get('title') or '当前章'}」卡住了。
本章大纲：{data.get('outline') or '（无）'}
已有正文结尾：{(data.get('last') or '')[-800:] or '（无）'}

请给 3 个能让这一章活起来的「如果……」，每个一句话，具体、有画面、可立刻落笔。
只输出三条，用 1. 2. 3. 编号，不要解释。"""
    try:
        text = ai_service.generate_content(prompt, use_cache=False)
        return {"success": True, "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 工坊：桌面版（烽火南境 .py）功能对齐 ============

TOOLBOX_DIR = os.path.join(DATA_DIR, "data")
TOOLBOX_FILE = os.path.join(TOOLBOX_DIR, "toolbox.json")
STYLE_LIBRARY = os.path.join(APP_DIR, "大师文风参考库.txt")
_toolbox_lock = threading.Lock()

CONCEPT_SECTIONS = {
    "core": "一句话核心故事（50-100字）",
    "theme": "故事主题与内核（200-300字）",
    "positioning": "市场定位与差异化（300字以上商业分析）",
    "plot_structure": "剧情主线三幕式结构（300-400字）",
    "character_arc": "主角定位与成长弧光（200-300字）",
    "style_guide": "风格锚点与创作指南（200-300字）",
}


def _load_toolbox():
    default = {"templates": [], "styles": [], "history": []}
    try:
        with open(TOOLBOX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in default.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return default


def _save_toolbox(data):
    os.makedirs(TOOLBOX_DIR, exist_ok=True)
    tmp = TOOLBOX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TOOLBOX_FILE)


def _log_history(kind, project, text, meta=None):
    try:
        with _toolbox_lock:
            data = _load_toolbox()
            data["history"].insert(0, {
                "id": "h_%d" % int(time.time() * 1000),
                "kind": kind,
                "project": project or "",
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "chars": len(text or ""),
                "preview": (text or "")[:200],
                "meta": meta or {},
            })
            data["history"] = data["history"][:300]
            _save_toolbox(data)
    except Exception:
        pass


def _ai(prompt, kind, project="", system=None, meta=None):
    text = ai_service.generate_content(prompt, system_prompt=system, use_cache=False)
    _log_history(kind, project, text, meta)
    return text


def _parse_json_array(text):
    """从模型输出中尽力提取 JSON 数组"""
    if not text:
        return []
    m = re.search(r'\[[\s\S]*\]', text)
    if not m:
        return []
    raw = m.group(0)
    try:
        return json.loads(raw)
    except Exception:
        pass
    try:
        return json.loads(raw.replace('\n', ' ').replace('，', ','))
    except Exception:
        return []


def _master_styles():
    """解析 大师文风参考库.txt 的章节标题"""
    items = []
    try:
        with open(STYLE_LIBRARY, "r", encoding="utf-8") as f:
            lines = f.readlines()
        title = None
        buf = []
        for line in lines:
            s = line.strip()
            if s.startswith("【") and s.endswith("】"):
                if title:
                    items.append({"title": title, "excerpt": "".join(buf).strip()[:1200]})
                title = s.strip("【】")
                buf = []
            elif title:
                buf.append(line)
        if title:
            items.append({"title": title, "excerpt": "".join(buf).strip()[:1200]})
    except Exception:
        pass
    return items


def _style_prompt(style_title):
    if not style_title:
        return ""
    for it in _master_styles():
        if it["title"] == style_title:
            return f"\n\n【文风锚点：{style_title}】\n{it['excerpt'][:900]}\n"
    for it in _load_toolbox().get("styles", []):
        if it.get("title") == style_title:
            return f"\n\n【文风锚点：{style_title}】\n{(it.get('excerpt') or '')[:900]}\n"
    return ""


@app.post("/api/ai/concept/section")
def api_ai_concept_section(data: dict):
    """单独重生成概念中的某一节"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    key = data.get("section", "core")
    if key not in CONCEPT_SECTIONS:
        raise HTTPException(status_code=400, detail="未知的概念分节")
    concept = project.get("concept") or {}
    prompt = f"""你在为小说《{project.get('name', '')}》打磨核心概念。
题材：{project.get('genre', '')}；风格：{project.get('style', '')}；子类型：{project.get('subgenre', '')}。
已有概念：
- 核心：{concept.get('core', '')[:200]}
- 主题：{concept.get('theme', '')[:200]}
- 定位：{concept.get('positioning', '')[:200]}
- 三幕：{concept.get('plot_structure', '')[:200]}
- 主角弧光：{concept.get('character_arc', '')[:200]}
- 风格锚点：{concept.get('style_guide', '')[:200]}

请只重写这一节：{CONCEPT_SECTIONS[key]}
要求：与其余设定保持一致，具体、可执行，不要序号和markdown标记。只输出正文。"""
    try:
        text = _ai(prompt, "concept:" + key, project.get("name", ""))
        return {"success": True, "section": key, "text": clean_text(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/world/check")
def api_ai_world_check(data: dict):
    """世界观一致性检查"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    world = data.get("world") or project.get("world") or {}
    text = world.get("content") if isinstance(world, dict) else str(world)
    chars = project.get("characters") or {}
    names = []
    for group, arr in chars.items():
        if isinstance(arr, list):
            for c in arr:
                n = c.get("name") if isinstance(c, dict) else str(c)
                if n:
                    names.append(n)
    prompt = f"""你是《{project.get('name', '')}》的设定审校。
世界观：
{(text or '（空）')[:4000]}

主要人物：{'、'.join(names[:20]) or '（未设定）'}

请检查：
1. 内部矛盾（时间、地理、力量体系、势力关系）
2. 与人物设定的冲突
3. 缺失但故事必要的一环

最多输出 6 条，每条一行，格式：问题：…… ｜ 建议：……
不要客套话。"""
    try:
        out = _ai(prompt, "world-check", project.get("name", ""))
        lines = [re.sub(r'^[\d\.\-\s]+', '', l).strip() for l in out.splitlines() if l.strip()]
        return {"success": True, "issues": [l for l in lines if l][:8], "raw": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{name}/ai-scan-characters")
async def api_scan_characters(name: str, data: dict):
    """从某一章正文里增量识别新人物，直接写进人物表（搭子与设定共用同一份）"""
    project = _require_project(name)
    if not ai_service.api_key:
        return {"success": True, "added": [], "reason": "未配置 API Key"}
    text = str(data.get("text") or "")
    if len(re.sub(r"\s", "", text)) < 60:
        return {"success": True, "added": []}

    groups = project.get("characters")
    if not isinstance(groups, dict):
        groups = {}
    for g in ("主角", "配角", "反派"):
        if not isinstance(groups.get(g), list):
            groups[g] = []
    existing = []
    for arr in groups.values():
        if not isinstance(arr, list):
            continue
        for c in arr:
            if isinstance(c, dict) and c.get("name"):
                existing.append(str(c["name"]).strip())
                for a in (c.get("aliases") or []):
                    if str(a).strip():
                        existing.append(str(a).strip())
            elif isinstance(c, str) and c.strip():
                existing.append(c.strip())

    prompt = f"""从下面这一章正文里找出有人物，把人物档案尽量填完整。

已经在人物表里的（包括别名，不要重复建人；如果看到他们的新信息，可以补进对应字段）：{'、'.join(existing[:60]) or '无'}

要求：
1. 只找正文里确实出场、有名字或固定称呼的人（如“陆昭宁”“老刘”“晚翠”）。
2. “掌柜的”“那个士兵”这类没名字的不要。
3. group 取 主角 / 配角 / 反派，拿不准填配角。
4. 每个字段都要填：能直接从正文看出来的照写；正文没明说的，按身份做最保守的推断（如“面馆食客”“寡言”），不要编造具体经历、身世和剧情。
5. 每个字段简短，不要空着。
6. 最多 8 人，没有就给空数组。

只输出 JSON：
{{"characters":[{{
 "name":"","group":"主角|配角|反派","role":"身份定位，12字内","gender":"男|女|未知","age":"年龄，10字内",
 "identity":"身份背景，30字内",
 "purpose":["推动主线","制造冲突"],
 "tagline":"一句话人设，20字内",
 "intro":"角色介绍，80字内",
 "background":"前史，60字内",
 "appearance":"外貌，50字内",
 "personality":"性格，50字内",
 "ability":"能力或功法，40字内",
 "quote":"代表性台词，30字内",
 "goal":"目标，30字内",
 "arc":"成长弧，30字内",
 "aliases":["别名"],
 "relations":[{{"target":"另一个角色名","type":"关系","strength":3}}]
}}]}}

正文：
{text[:9000]}"""
    got = {}
    try:
        got = _ai_json(prompt, max_tokens=6000) or {}
    except Exception as e:
        print("人物增量识别失败:", e)

    fields = (("role", 30), ("gender", 8), ("age", 16), ("identity", 80), ("tagline", 100),
              ("intro", 600), ("background", 600), ("appearance", 400), ("personality", 400),
              ("ability", 400), ("quote", 120), ("goal", 300), ("arc", 300))
    known = set(existing)

    def fill(target, src):
        n = 0
        for k, lim in fields:
            v = str(src.get(k) or "").strip()
            if v and not str(target.get(k) or "").strip():
                target[k] = v[:lim]
                n += 1
        raw = src.get("purpose")
        if isinstance(raw, str):
            raw = [x for x in re.split(r"[、,，;；\s]+", raw) if x]
        if isinstance(raw, list):
            cur_p = target.get("purpose") if isinstance(target.get("purpose"), list) else []
            for p in raw:
                p = str(p).strip()[:16]
                if p and p not in cur_p:
                    cur_p.append(p)
                    n += 1
            if cur_p:
                target["purpose"] = cur_p[:8]
        al = src.get("aliases")
        if isinstance(al, str):
            al = [x for x in re.split(r"[、,，;；\s]+", al) if x]
        if isinstance(al, list):
            cur_a = target.get("aliases") if isinstance(target.get("aliases"), list) else []
            for a in al:
                a = str(a).strip()[:16]
                if a and a != target.get("name") and a not in cur_a:
                    cur_a.append(a)
                    n += 1
            if cur_a:
                target["aliases"] = cur_a[:8]
        rels = src.get("relations")
        if isinstance(rels, list):
            cur_r = target.get("relations") if isinstance(target.get("relations"), list) else []
            have = {str(r.get("target") or "") for r in cur_r if isinstance(r, dict)}
            for r in rels:
                if not isinstance(r, dict):
                    continue
                t = str(r.get("target") or "").strip()[:20]
                if not t or t == target.get("name") or t in have:
                    continue
                cur_r.append({"target": t, "type": str(r.get("type") or "关系")[:12],
                              "strength": max(1, min(int(r.get("strength") or 3), 5))})
                have.add(t)
                n += 1
            if cur_r:
                target["relations"] = cur_r[:20]
        if not (target.get("desc") or "").strip():
            target["desc"] = (target.get("tagline") or target.get("identity") or "")[:100]
        return n

    added, enriched = [], []
    for c in (got.get("characters") or [])[:8]:
        if not isinstance(c, dict):
            continue
        nm = str(c.get("name") or "").strip()[:12]
        if not nm:
            continue
        found = None
        for arr in groups.values():
            if not isinstance(arr, list):
                continue
            for rec in arr:
                if not isinstance(rec, dict):
                    continue
                names = [str(rec.get("name") or "").strip()] + [str(a).strip() for a in (rec.get("aliases") or [])]
                if nm in names:
                    found = rec
                    break
            if found:
                break
        if found is not None:
            if fill(found, c):
                enriched.append(nm)
            continue
        g = str(c.get("group") or "").strip()
        if g not in groups:
            g = "配角"
        rec = {"name": nm, "group": g, "relations": []}
        fill(rec, c)
        groups[g].append(rec)
        known.add(nm)
        added.append(nm)

    if added or enriched:
        project["characters"] = groups
        save_project(name, project)
    return {"success": True, "added": added, "enriched": enriched, "characters": groups}


@app.post("/api/ai/characters")
def api_ai_characters(data: dict):
    """批量生成人物（返回结构化数组并可直接写回项目）"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    role_type = data.get("role_type", "配角")
    count = max(1, min(int(data.get("count") or 3), 10))
    concept = project.get("concept") or {}
    world = project.get("world") or {}
    world_text = world.get("content", "") if isinstance(world, dict) else str(world)
    existing = []
    for group, arr in (project.get("characters") or {}).items():
        if isinstance(arr, list):
            existing += [c.get("name") for c in arr if isinstance(c, dict) and c.get("name")]
    prompt = f"""为小说《{project.get('name', '')}》设计 {count} 位{role_type}。
题材：{project.get('genre', '')}｜风格：{project.get('style', '')}
核心故事：{concept.get('core', '')[:300]}
世界观：{world_text[:600]}
已有角色（不要重名）：{'、'.join(existing[:30]) or '无'}

只输出 JSON 数组，不要任何解释。数组元素字段：
name（姓名）、role（定位，如 男主/女主/师父/幕后黑手）、gender（性别）、age（年龄）、identity（身份/职业）、purpose（用途数组，可选值：推动主线、制造冲突、提供信息、情感线、衬托主角、埋伏笔、喜剧担当、展示世界观、导师、对手、工具人）、tagline（一句话介绍 30 字）、intro（角色介绍 120 字，出身与主线关系）、appearance（外貌 30 字）、personality（性格 40 字）、background（背景 80 字）、ability（能力 40 字）、quote（口头禅 15 字）、goal（目标动机 30 字）、arc（成长弧光 40 字）、relations（与已有角色关系的数组，元素 {{"target":"名字","type":"关系"}}）"""
    try:
        raw = _ai(prompt, "characters", project.get("name", ""), meta={"role_type": role_type})
        arr = _parse_json_array(raw)
        out = []
        for c in arr[:count]:
            if not isinstance(c, dict) or not c.get("name"):
                continue
            purpose = c.get("purpose")
            if not isinstance(purpose, list):
                purpose = [purpose] if purpose else []
            out.append({
                "name": str(c.get("name"))[:20],
                "desc": str(c.get("identity") or c.get("role") or "")[:60],
                "role": str(c.get("role") or "")[:30],
                "gender": str(c.get("gender") or "")[:6],
                "age": str(c.get("age") or "")[:12],
                "identity": str(c.get("identity") or "")[:60],
                "purpose": [str(p)[:12] for p in purpose if p][:6],
                "tagline": str(c.get("tagline") or "")[:80],
                "intro": str(c.get("intro") or "")[:400],
                "appearance": str(c.get("appearance") or ""),
                "personality": str(c.get("personality") or ""),
                "background": str(c.get("background") or ""),
                "ability": str(c.get("ability") or ""),
                "quote": str(c.get("quote") or ""),
                "goal": str(c.get("goal") or ""),
                "arc": str(c.get("arc") or ""),
                "relations": c.get("relations") if isinstance(c.get("relations"), list) else [],
            })
        return {"success": True, "characters": out, "raw": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/character")
def api_ai_character(data: dict):
    """重生成单个人物小传"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    name = data.get("name") or "无名"
    role_type = data.get("role_type", "配角")
    prompt = f"""重写《{project.get('name', '')}》中{role_type}「{name}」的小传。
题材：{project.get('genre', '')}｜风格：{project.get('style', '')}
补充要求：{data.get('requirements') or '无'}

按这几段写：身份、外貌、性格、背景、能力、成长弧光。每段一行，不要标题和序号。"""
    try:
        text = _ai(prompt, "character", project.get("name", ""), meta={"name": name})
        return {"success": True, "text": clean_text(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/detailed-outline")
def api_ai_detailed_outline(data: dict):
    """生成逐章细纲"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    start = int(data.get("start") or 1)
    count = max(1, min(int(data.get("count") or 5), 20))
    end = start + count - 1
    concept = project.get("concept") or {}
    macro = (project.get("outline") or {}).get("macro", "")
    if data.get("macro"):
        macro = data.get("macro")
    world = project.get("world") or {}
    world_text = world.get("content", "") if isinstance(world, dict) else str(world)
    chars = []
    for group, arr in (project.get("characters") or {}).items():
        if isinstance(arr, list):
            chars += [c.get("name") for c in arr if isinstance(c, dict) and c.get("name")]
    prompt = f"""为《{project.get('name', '')}》写第 {start} 到第 {end} 章的细纲。
题材：{project.get('genre', '')}｜风格：{project.get('style', '')}
核心故事：{concept.get('core', '')[:300]}
全书大纲：{macro[:1200]}
世界观：{world_text[:600]}
主要人物：{'、'.join(chars[:20]) or '未设定'}

要求：每章一行，严格格式：
第N章｜标题｜本意（一句话）｜场景（2-3个，用；分隔）｜冲突｜章末钩子
不要编号以外的解释。"""
    prompt += _style_prompt(data.get("style_ref") or project.get("style_ref") or "")
    try:
        raw = _ai(prompt, "detailed-outline", project.get("name", ""), meta={"start": start, "count": count})
        items = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or "｜" not in line:
                continue
            parts = [p.strip() for p in line.split("｜")]
            if not parts[0].startswith("第"):
                continue
            items.append({
                "chapter": parts[0],
                "title": parts[1] if len(parts) > 1 else "",
                "idea": parts[2] if len(parts) > 2 else "",
                "scenes": parts[3] if len(parts) > 3 else "",
                "conflict": parts[4] if len(parts) > 4 else "",
                "hook": parts[5] if len(parts) > 5 else "",
            })
        return {"success": True, "items": items, "raw": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/script")
def api_ai_script(data: dict):
    """正文转分场剧本"""
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    chapters = data.get("chapters") or []
    if not chapters:
        raise HTTPException(status_code=400, detail="请先选择要转换的章节")
    source = "\n\n".join(f"【{c.get('title','')}】\n{(c.get('content') or '')[:3000]}" for c in chapters[:5])
    prompt = f"""把下面这部小说《{project.get('name', '')}》的章节改写成拍摄用分场剧本。
要求：保留关键情节与对白，动作写清，场景标注时间地点。
只输出 JSON 数组，元素字段：scene（场次号）、location（地点）、time（时间）、characters（出场人物数组）、action（动作/画面描述）、dialogue（对白，格式 人物：台词，多句用换行）。

原文：
{source}"""
    try:
        raw = _ai(prompt, "script", project.get("name", ""), meta={"chapters": len(chapters)})
        scenes = _parse_json_array(raw)
        return {"success": True, "scenes": scenes, "raw": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 批量生成（带进度） ---

_batch_jobs = {}


@app.post("/api/ai/batch")
def api_ai_batch(data: dict):
    _require_api_key()
    project = _require_project(data.get("project_name", ""))
    start = int(data.get("start") or 1)
    count = max(1, min(int(data.get("count") or 3), 20))
    job_id = "job_%d" % int(time.time() * 1000)
    _batch_jobs[job_id] = {"id": job_id, "status": "running", "done": 0, "total": count,
                           "start": start, "log": [], "error": "", "project": project.get("name", "")}

    def worker():
        job = _batch_jobs[job_id]
        try:
            for i in range(count):
                num = start + i
                title = f"第{num}章"
                proj = load_project(job["project"])
                files = proj.get("_files") or []
                exists = any(f.get("type") == "FILE" and f.get("name", "").startswith(f"第{num}章") for f in files)
                if exists:
                    job["done"] += 1
                    job["log"].append(f"{title} 已存在，跳过")
                    continue
                prompt = f"""你是顶级网文作家，请为《{proj.get('name', '')}》写第 {num} 章正文。
题材：{proj.get('genre', '')}｜风格：{proj.get('style', '')}｜参考文风：{proj.get('ref_author', '')}
核心故事：{(proj.get('concept') or {}).get('core', '')[:300]}
全书大纲：{((proj.get('outline') or {}).get('macro', ''))[:800]}
本章细纲：{((proj.get('outline') or {}).get('detailed', {}) or {}).get(str(num), '')}
目标字数：{proj.get('words_per_chapter', 2500)} 字左右

要求：有画面、对话自然、章末留钩子；只输出正文，不写"第X章"标题，不加任何标记。"""
                prompt += _style_prompt(proj.get("style_ref") or "")
                if proj.get("prompt_template"):
                    prompt += f"\n\n【补充要求】\n{proj['prompt_template'][:600]}\n"
                text = ai_service.generate_content(prompt, use_cache=False)
                text = ai_service.humanize_text(text)
                proj = load_project(job["project"])
                files = proj.get("_files") or []
                vol = next((f for f in files if f.get("type") == "FOLDER" and f.get("parentId") == "root"), None)
                if not vol:
                    vol = {"id": "vol_%d" % int(time.time() * 1000), "parentId": "root", "name": "01_正文",
                           "type": "FOLDER", "lastModified": int(time.time() * 1000)}
                    files.append(vol)
                files.append({"id": "ch_%d_%d" % (int(time.time() * 1000), num), "parentId": vol["id"],
                              "name": title, "type": "FILE", "content": text,
                              "lastModified": int(time.time() * 1000), "metadata": {}})
                proj["_files"] = files
                save_project(job["project"], proj)
                _log_history("batch-chapter", job["project"], text, {"chapter": num})
                job["done"] += 1
                job["log"].append(f"{title} 完成（{len(text)} 字）")
            job["status"] = "done"
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    threading.Thread(target=worker, daemon=True).start()
    return {"success": True, "job": _batch_jobs[job_id]}


@app.get("/api/ai/batch/{job_id}")
async def api_ai_batch_status(job_id: str):
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


# --- 本地分析（不消耗 API） ---

EMOTION_WORDS = {
    "喜悦": ["笑", "喜", "欢", "甜", "暖", "雀跃", "心花", "眉开"],
    "愤怒": ["怒", "吼", "咬牙", "拍案", "狠狠", "恼", "恨"],
    "悲伤": ["泪", "哭", "痛", "悲", "涩", "黯然", "哽咽", "凄凉"],
    "恐惧": ["怕", "颤", "惊", "寒", "冷汗", "发抖", "心悸", "悚"],
    "紧张": ["猛地", "骤然", "屏息", "心跳", "紧握", "急促", "一瞬"],
    "平静": ["静", "淡", "缓缓", "轻轻", "安静", "默"],
}


@app.post("/api/analysis/emotion")
async def api_analysis_emotion(data: dict):
    """段落情绪曲线（关键词强度）"""
    text = data.get("text") or ""
    paras = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    if not paras:
        return {"success": True, "points": []}
    points = []
    for i, p in enumerate(paras[:400]):
        scores = {}
        for tone, words in EMOTION_WORDS.items():
            n = sum(p.count(w) for w in words)
            if n:
                scores[tone] = n
        tone = max(scores, key=scores.get) if scores else "中性"
        intensity = min(100, 20 + sum(scores.values()) * 12) if scores else 15
        points.append({"i": i + 1, "tone": tone, "intensity": intensity,
                       "preview": p[:40], "chars": len(p)})
    return {"success": True, "points": points}


@app.post("/api/analysis/dependency")
async def api_analysis_dependency(data: dict):
    """章节依赖：共享人物与关键词重合度"""
    chapters = data.get("chapters") or []
    names = data.get("characters") or []

    def keywords(t):
        t = re.sub(r'[\s，。！？、；：“”‘’（）《》…—\.\!\,\?]', '', t or "")
        grams = [t[i:i + 2] for i in range(0, max(0, len(t) - 1))]
        freq = {}
        for g in grams:
            freq[g] = freq.get(g, 0) + 1
        return {k for k, v in freq.items() if v >= 3}

    metas = []
    for c in chapters:
        text = c.get("content") or ""
        metas.append({
            "id": c.get("id"),
            "title": c.get("title") or c.get("name") or "",
            "chars": len(text),
            "names": [n for n in names if n and n in text],
            "kw": keywords(text),
        })
    links = []
    for i in range(len(metas)):
        for j in range(i + 1, len(metas)):
            a, b = metas[i], metas[j]
            shared = sorted(set(a["names"]) & set(b["names"]))
            kw = a["kw"] & b["kw"]
            weight = len(shared) * 3 + min(len(kw), 30) + (5 if j == i + 1 else 0)
            if weight >= 6:
                links.append({"from": a["id"], "to": b["id"], "fromTitle": a["title"], "toTitle": b["title"],
                              "weight": weight, "shared": shared[:6], "keywords": list(kw)[:6]})
    links.sort(key=lambda x: -x["weight"])
    return {"success": True, "chapters": [{"id": m["id"], "title": m["title"], "chars": m["chars"], "names": m["names"]} for m in metas],
            "links": links[:60]}


# --- 工具箱：提示词模板 / 文风参考 / 生成历史 ---

@app.get("/api/toolbox")
async def api_toolbox():
    data = _load_toolbox()
    masters = [{"id": "m_%d" % i, "title": it["title"], "excerpt": it["excerpt"], "builtin": True}
               for i, it in enumerate(_master_styles())]
    seen = {m["title"] for m in masters}
    custom = [s for s in data.get("styles", []) if s.get("title") not in seen]
    return {"templates": data.get("templates", []), "styles": masters + custom,
            "history": data.get("history", [])[:100]}


@app.post("/api/toolbox/templates")
async def api_toolbox_add_template(data: dict):
    name = (data.get("name") or "").strip()
    body = data.get("body") or ""
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    with _toolbox_lock:
        db = _load_toolbox()
        tpl = {"id": "t_%d" % int(time.time() * 1000), "name": name, "body": body,
               "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        db["templates"] = [t for t in db["templates"] if t.get("name") != name] + [tpl]
        _save_toolbox(db)
    return {"success": True, "template": tpl}


@app.delete("/api/toolbox/templates/{tid}")
async def api_toolbox_del_template(tid: str):
    with _toolbox_lock:
        db = _load_toolbox()
        db["templates"] = [t for t in db["templates"] if t.get("id") != tid]
        _save_toolbox(db)
    return {"success": True}


@app.post("/api/toolbox/styles")
async def api_toolbox_add_style(data: dict):
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="文风名称不能为空")
    with _toolbox_lock:
        db = _load_toolbox()
        item = {"id": "s_%d" % int(time.time() * 1000), "title": title,
                "excerpt": (data.get("excerpt") or "")[:1200], "builtin": False}
        db["styles"] = [s for s in db["styles"] if s.get("title") != title] + [item]
        _save_toolbox(db)
    return {"success": True, "style": item}


@app.delete("/api/toolbox/styles/{sid}")
async def api_toolbox_del_style(sid: str):
    with _toolbox_lock:
        db = _load_toolbox()
        db["styles"] = [s for s in db["styles"] if s.get("id") != sid]
        _save_toolbox(db)
    return {"success": True}


@app.get("/api/toolbox/history")
async def api_toolbox_history(limit: int = 100):
    return {"history": _load_toolbox().get("history", [])[:max(1, min(limit, 300))]}


@app.delete("/api/toolbox/history")
async def api_toolbox_clear_history():
    with _toolbox_lock:
        db = _load_toolbox()
        db["history"] = []
        _save_toolbox(db)
    return {"success": True}


# --- 项目：复制 / 导入 ---

@app.post("/api/projects/{name}/duplicate")
async def api_duplicate_project(name: str, data: dict):
    src = load_project(name)
    if src is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    new_name = (data.get("new_name") or (name + " 副本")).strip()
    exists = cloud_store.project_exists(new_name) if (CLOUD and cloud_store) else os.path.exists(os.path.join(PROJECTS_DIR, f"{new_name}.json"))
    if exists:
        raise HTTPException(status_code=409, detail="同名书籍已存在")
    project = json.loads(json.dumps(src))
    project["name"] = new_name
    project["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_project(new_name, project)
    return {"success": True, "name": new_name}


@app.post("/api/projects/import")
async def api_import_project(data: dict):
    project = data.get("project") or data
    name = (data.get("name") or project.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="缺少书名")
    if not isinstance(project, dict):
        raise HTTPException(status_code=400, detail="项目数据格式不正确")
    fp = os.path.join(PROJECTS_DIR, f"{name}.json")
    if os.path.exists(fp) and not data.get("overwrite"):
        raise HTTPException(status_code=409, detail="同名书籍已存在")
    project["name"] = name
    project.setdefault("_files", [])
    project.setdefault("characters", {"主角": [], "配角": [], "反派": []})
    save_project(name, project)
    return {"success": True, "name": name}


# --- 外观：自定义背景图 ---

CUSTOM_BG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "assets", "custom")


@app.post("/api/appearance/background")
async def api_upload_background(data: dict):
    raw = data.get("data") or ""
    m = re.match(r'data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)', raw)
    if not m:
        raise HTTPException(status_code=400, detail="只支持 png / jpg / webp 图片")
    ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
    try:
        blob = base64.b64decode(m.group(2))
    except Exception:
        raise HTTPException(status_code=400, detail="图片数据损坏")
    if len(blob) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 8MB，请压缩后再传")
    os.makedirs(CUSTOM_BG_DIR, exist_ok=True)
    name = "bg_%d.%s" % (int(time.time() * 1000), ext)
    with open(os.path.join(CUSTOM_BG_DIR, name), "wb") as f:
        f.write(blob)
    return {"success": True, "url": "assets/custom/" + name, "bytes": len(blob)}


# --- 书籍封面 ---

COVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "assets", "covers")


@app.post("/api/books/{name}/cover")
async def api_upload_cover(name: str, data: dict):
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    raw = data.get("data") or ""
    m = re.match(r'data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)', raw)
    if not m:
        raise HTTPException(status_code=400, detail="只支持 png / jpg / webp 图片")
    ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
    try:
        blob = base64.b64decode(m.group(2))
    except Exception:
        raise HTTPException(status_code=400, detail="图片数据损坏")
    if len(blob) > 6 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="封面超过 6MB，请压缩后再传")
    os.makedirs(COVER_DIR, exist_ok=True)
    fname = "cover_%d.%s" % (int(time.time() * 1000), ext)
    with open(os.path.join(COVER_DIR, fname), "wb") as f:
        f.write(blob)
    url = "assets/covers/" + fname
    project["cover"] = url
    save_project(name, project)
    return {"success": True, "url": url}


# --- 人物立绘（头像） ---

AVATAR_DIR = os.path.join(APP_DIR, "frontend", "assets", "avatars")


def _avatar_prompt(c, project):
    seg = []
    for k in ("gender", "age", "identity", "role"):
        v = str(c.get(k) or "").strip()
        if v:
            seg.append(v)
    ap = str(c.get("appearance") or "").strip()
    if ap:
        seg.append(ap)
    ps = str(c.get("personality") or "").strip()
    if ps:
        seg.append("气质：" + ps)
    who = "，".join([str(c.get("name") or "人物")] + seg)
    style = ("中国古代人物半身立绘，工笔水墨与写实结合，柔和电影光，素色宣纸背景，"
             "五官精致，衣纹与发饰细节丰富，正面微侧，无文字无水印")
    return f"{who}。{style}"


def _drop_avatar_if_unused(project, path):
    if not path or not str(path).startswith("assets/avatars/"):
        return
    chars = project.get("characters") or {}
    for arr in chars.values():
        if not isinstance(arr, list):
            continue
        for c in arr:
            if isinstance(c, dict) and c.get("avatar") == path:
                return
    fp = os.path.join(AVATAR_DIR, os.path.basename(str(path)))
    try:
        if os.path.isfile(fp):
            os.remove(fp)
    except Exception as e:
        print("⚠ 删除旧立绘失败: %s" % e)


@app.post("/api/books/{name}/characters/avatar")
def api_character_avatar(name: str, data: dict):
    """人物立绘：上传图片 / 调用绘图 API 生成 / 清除"""
    project = load_project(name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    group = str(data.get("group") or "")
    try:
        index = int(data.get("index"))
    except Exception:
        raise HTTPException(status_code=400, detail="人物位置不正确")
    chars = project.get("characters") if isinstance(project.get("characters"), dict) else {}
    arr = chars.get(group) if isinstance(chars.get(group), list) else []
    if index < 0 or index >= len(arr):
        raise HTTPException(status_code=404, detail="人物不存在")
    c = arr[index]
    if not isinstance(c, dict):
        c = {"name": str(c)}
    old = c.get("avatar") or ""

    if data.get("clear"):
        c["avatar"] = ""
        chars[group][index] = c
        project["characters"] = chars
        save_project(name, project)
        _drop_avatar_if_unused(project, old)
        return {"success": True, "url": "", "cleared": True}

    blob = None
    raw = data.get("data") or ""
    if raw:
        m = re.match(r'data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)', raw)
        if not m:
            raise HTTPException(status_code=400, detail="只支持 png / jpg / webp 图片")
        try:
            blob = base64.b64decode(m.group(2))
        except Exception:
            raise HTTPException(status_code=400, detail="图片数据损坏")
        engine = "upload"
    else:
        cfg = load_settings()
        key = (cfg.get("image_api_key") or "").strip()
        if not key:
            raise HTTPException(
                status_code=400,
                detail="还没有配置绘图 API：设置 → 接口 → 绘图 API Key（SiliconFlow / OpenAI 兼容接口都行）",
            )
        base = (cfg.get("image_base") or "https://api.siliconflow.cn/v1").rstrip("/")
        model = cfg.get("image_model") or "Kwai-Kolors/Kolors"
        prompt = _avatar_prompt(c, project)
        try:
            import requests
            r = requests.post(
                base + "/images/generations",
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={
                    "model": model, "prompt": prompt,
                    "size": "1024x1024", "image_size": "1024x1024",
                    "batch_size": 1, "n": 1, "response_format": "url",
                },
                timeout=300,
            )
            r.raise_for_status()
            j = r.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail="绘图接口调用失败：%s" % str(e)[:160])
        item = None
        for k in ("data", "images", "output", "result"):
            v = j.get(k)
            if isinstance(v, list) and v:
                item = v[0]
                break
        img_url = item if isinstance(item, str) else ""
        b64 = ""
        if isinstance(item, dict):
            img_url = item.get("url") or item.get("image") or item.get("image_url") or ""
            b64 = item.get("b64_json") or ""
        if b64:
            try:
                blob = base64.b64decode(b64)
            except Exception:
                blob = None
        if blob is None and img_url:
            try:
                import requests
                rr = requests.get(img_url, timeout=180)
                rr.raise_for_status()
                blob = rr.content
            except Exception as e:
                raise HTTPException(status_code=500, detail="下载立绘失败：%s" % str(e)[:160])
        if not blob:
            raise HTTPException(status_code=500, detail="绘图接口没有返回图片：%s" % str(j)[:160])
        engine = "ai"

    if len(blob) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 8MB，请压缩后再用")
    os.makedirs(AVATAR_DIR, exist_ok=True)
    fname = "char_%d.png" % int(time.time() * 1000)
    with open(os.path.join(AVATAR_DIR, fname), "wb") as f:
        f.write(blob)
    url = "assets/avatars/" + fname
    c["avatar"] = url
    chars[group][index] = c
    project["characters"] = chars
    save_project(name, project)
    if old and old != url:
        _drop_avatar_if_unused(project, old)
    return {"success": True, "url": url, "engine": engine}


# --- 项目回收站 ---

def _trash_entries():
    items = []
    if not os.path.isdir(TRASH_DIR):
        return items
    for fp in sorted(glob.glob(os.path.join(TRASH_DIR, "*.json")), key=os.path.getmtime, reverse=True):
        name = os.path.basename(fp)
        origin = re.sub(r'_\d{8}_\d{6}\.json$', '', name)
        items.append({
            "file": name,
            "name": origin,
            "size": os.path.getsize(fp),
            "ts": datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return items


@app.get("/api/trash")
async def api_trash_list():
    return {"items": _trash_entries()}


@app.post("/api/trash/restore")
async def api_trash_restore(data: dict):
    fname = os.path.basename(data.get("file") or "")
    src = os.path.join(TRASH_DIR, fname)
    if not fname or not os.path.isfile(src):
        raise HTTPException(status_code=404, detail="备份不存在")
    try:
        with open(src, "r", encoding="utf-8-sig") as f:
            proj = json.load(f)
        name = (proj.get("name") or "").strip()
    except Exception:
        name = ""
    if not name:
        name = re.sub(r'_\d{8}_\d{6}\.json$', '', fname)
    dst = os.path.join(PROJECTS_DIR, f"{name}.json")
    if os.path.exists(dst) or (CLOUD and cloud_store and cloud_store.project_exists(name)):
        name = f"{name}_恢复_{datetime.now().strftime('%H%M%S')}"
        dst = os.path.join(PROJECTS_DIR, f"{name}.json")
    if CLOUD and cloud_store:
        try:
            with open(src, "r", encoding="utf-8-sig") as f:
                proj = json.load(f)
        except Exception:
            raise HTTPException(status_code=400, detail="备份文件损坏")
        proj["name"] = name
        save_project(name, proj)
        os.remove(src)
        return {"success": True, "name": name}
    shutil.copy2(src, dst)
    os.remove(src)
    return {"success": True, "name": name}


# ============ 多人有声剧配音（edge-tts） ============
# 选角思路参考开源项目 talebook/voicebook：先识别说话人，再按性别 / 年龄段 / 气质
# 匹配音色；同一角色全篇保持同音，连续发言的不同角色绝不同音。
TTS_CACHE_DIR = os.path.join(tempfile.gettempdir(), "fj_tts_cache")

TTS_VOICES = [
    {"id": "zh-CN-YunyangNeural", "name": "云扬", "gender": "male", "age": "middle",
     "style": "播音腔，沉稳可靠", "role": "旁白 / 中年男"},
    {"id": "zh-CN-YunjianNeural", "name": "云健", "gender": "male", "age": "middle",
     "style": "浑厚有力，将军、掌门、粗豪汉子", "role": "中年男 / 老年男"},
    {"id": "zh-CN-YunxiNeural", "name": "云希", "gender": "male", "age": "young",
     "style": "青年明亮，少年主角", "role": "青年男"},
    {"id": "zh-CN-YunxiaNeural", "name": "云夏", "gender": "male", "age": "child",
     "style": "软糯童声，小童、半大少年", "role": "儿童 / 少年男"},
    {"id": "zh-TW-YunJheNeural", "name": "云哲", "gender": "male", "age": "young",
     "style": "台湾腔青年男，纨绔、商客", "role": "青年男（方言）"},
    {"id": "zh-HK-WanLungNeural", "name": "云龙", "gender": "male", "age": "middle",
     "style": "港腔男声，江湖客、掌柜", "role": "中年男（方言）"},
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "female", "age": "middle",
     "style": "温润知性，母亲、师太、大家闺秀", "role": "中年女 / 老年女"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "female", "age": "young",
     "style": "少女活泼，丫头、少女主角", "role": "少女 / 女童"},
    {"id": "zh-CN-liaoning-XiaobeiNeural", "name": "晓北", "gender": "female", "age": "young",
     "style": "东北爽朗，泼辣妇人、江湖女", "role": "青年女（方言）"},
    {"id": "zh-CN-shaanxi-XiaoniNeural", "name": "晓妮", "gender": "female", "age": "young",
     "style": "陕西方言，明亮俏皮", "role": "青年女（方言）"},
    {"id": "zh-TW-HsiaoChenNeural", "name": "晓臻", "gender": "female", "age": "middle",
     "style": "台湾腔柔声，温婉女子", "role": "中年女（方言）"},
    {"id": "zh-TW-HsiaoYuNeural", "name": "晓雨", "gender": "female", "age": "young",
     "style": "台湾腔甜声，少女", "role": "少女（方言）"},
    {"id": "zh-HK-HiuMaanNeural", "name": "晓曼", "gender": "female", "age": "young",
     "style": "港腔女声，时髦女子", "role": "青年女（方言）"},
    {"id": "zh-HK-HiuGaaiNeural", "name": "晓佳", "gender": "female", "age": "middle",
     "style": "港腔柔声，夫人、太太", "role": "中年女（方言）"},
]

_BR_V1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
_BR_V2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
_SRATE = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _tts_cache_file(text, voice, rate, pitch, volume):
    key = hashlib.md5(f"{voice}|{rate}|{pitch}|{volume}|{text}".encode("utf-8")).hexdigest()
    return os.path.join(TTS_CACHE_DIR, key + ".mp3")


def _mp3_scan(data):
    """去掉 ID3 头并统计帧数、时长（毫秒）。edge-tts 统一输出 24kHz / 48kbps 单声道。"""
    if data[:3] == b"ID3" and len(data) > 10:
        size = 10 + ((data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9])
        data = data[size:]
    frames, total_ms = 0, 0.0
    i = 0
    while i + 4 <= len(data):
        b1, b2 = data[i + 1], data[i + 2]
        if data[i] == 0xFF and (b1 & 0xE0) == 0xE0:
            ver = (b1 >> 3) & 3
            layer = (b1 >> 1) & 3
            br = (b2 >> 4) & 15
            sr = (b2 >> 2) & 3
            if layer == 1 and br not in (0, 15) and sr != 3 and ver != 1:
                if ver == 3:
                    kbps, srate, spf = _BR_V1[br], _SRATE[3][sr], 1152
                    flen = (144 * kbps * 1000) // srate
                else:
                    kbps, srate, spf = _BR_V2[br], _SRATE[2 if ver == 2 else 0][sr], 576
                    flen = (72 * kbps * 1000) // srate
                flen += (b2 >> 1) & 1
                if kbps and flen > 4:
                    frames += 1
                    total_ms += spf * 1000 / srate
                    i += flen
                    continue
        i += 1
    return data, frames, int(total_ms)


async def _tts_clip(text, voice, rate, pitch, volume):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
    buf = bytearray()
    async for chunk in com.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            buf.extend(chunk["data"])
    return bytes(buf)


# ============ 专业配音引擎（MiniMax 海螺 / 火山豆包 / Azure 情感风格） ============
# 用于替代「导航播报级」的 edge-tts：这些引擎的音色来自真人配音演员录制训练，
# 支持情绪参数、语气词标签（MiniMax 2.8）与逐句情感风格（Azure），才够得上有声剧。
_PRO_MINIMAX = {
    "zh-CN-YunyangNeural": "Chinese (Mandarin)_Male_Announcer",
    "zh-CN-YunjianNeural": "Chinese (Mandarin)_Reliable_Executive",
    "zh-CN-YunxiNeural": "male-qn-qingse",
    "zh-CN-YunxiaNeural": "Chinese (Mandarin)_Gentle_Youth",
    "zh-TW-YunJheNeural": "male-qn-badao",
    "zh-HK-WanLungNeural": "male-qn-jingying",
    "zh-CN-XiaoxiaoNeural": "Chinese (Mandarin)_News_Anchor",
    "zh-CN-XiaoyiNeural": "female-shaonv",
    "zh-TW-HsiaoChenNeural": "female-chengshu",
    "zh-TW-HsiaoYuNeural": "Chinese (Mandarin)_Soft_Girl",
    "zh-HK-HiuMaanNeural": "female-yujie",
    "zh-HK-HiuGaaiNeural": "Chinese (Mandarin)_Kind-hearted_Antie",
    "zh-CN-liaoning-XiaobeiNeural": "Chinese (Mandarin)_Crisp_Girl",
    "zh-CN-shaanxi-XiaoniNeural": "qiaopi_mengmei",
}
_PRO_VOLC = {
    "zh-CN-YunyangNeural": "zh_male_wenrouxiaoge_mars_bigtts",
    "zh-CN-YunjianNeural": "zh_male_M392_conversation_wvae_bigtts",
    "zh-CN-YunxiNeural": "zh_male_yangguangqingnian_moon_bigtts",
    "zh-CN-YunxiaNeural": "zh_male_yangguangqingnian_moon_bigtts",
    "zh-TW-YunJheNeural": "zh_male_yangguangqingnian_moon_bigtts",
    "zh-HK-WanLungNeural": "zh_male_M392_conversation_wvae_bigtts",
    "zh-CN-XiaoxiaoNeural": "zh_female_cancan_mars_bigtts",
    "zh-CN-XiaoyiNeural": "zh_female_shuangkuaisisi_moon_bigtts",
    "zh-TW-HsiaoChenNeural": "zh_female_cancan_mars_bigtts",
    "zh-TW-HsiaoYuNeural": "zh_female_shuangkuaisisi_moon_bigtts",
    "zh-HK-HiuMaanNeural": "zh_female_cancan_mars_bigtts",
    "zh-HK-HiuGaaiNeural": "zh_female_cancan_mars_bigtts",
    "zh-CN-liaoning-XiaobeiNeural": "zh_female_shuangkuaisisi_moon_bigtts",
    "zh-CN-shaanxi-XiaoniNeural": "zh_female_shuangkuaisisi_moon_bigtts",
}
_PRO_NAMES = {
    "minimax": "MiniMax 海螺（真人配音音色库）",
    "volc": "火山引擎豆包语音（番茄小说同源）",
    "azure": "Azure 神经大模型（情感风格）",
    "edge": "Edge 神经音色（导航播报级）",
}


def _tts_provider_cfg():
    """读取配音引擎配置；auto 时按已填 Key 自动选最专业的一家。"""
    s = load_settings()
    prov = str(s.get("tts_provider") or "auto").strip().lower()
    mm_key = str(s.get("minimax_key") or "").strip()
    volc_id = str(s.get("volc_appid") or "").strip()
    volc_tok = str(s.get("volc_token") or "").strip()
    az_key = str(s.get("azure_key") or "").strip()
    az_reg = str(s.get("azure_region") or "eastasia").strip() or "eastasia"
    if prov == "auto":
        if mm_key:
            prov = "minimax"
        elif volc_id and volc_tok:
            prov = "volc"
        elif az_key:
            prov = "azure"
        else:
            prov = "edge"
    if prov == "minimax" and not mm_key:
        prov = "edge"
    if prov == "volc" and not (volc_id and volc_tok):
        prov = "edge"
    if prov == "azure" and not az_key:
        prov = "edge"
    return {"provider": prov, "minimax_key": mm_key,
            "minimax_model": str(s.get("minimax_model") or "speech-2.8-hd").strip(),
            "volc_appid": volc_id, "volc_token": volc_tok,
            "volc_cluster": str(s.get("volc_cluster") or "volcano_tts").strip(),
            "azure_key": az_key, "azure_region": az_reg}


def _pro_emotion(mood):
    m = str(mood or "")
    if re.search("怒|愤|喝斥|吼|斥", m):
        return "angry"
    if re.search("悲|哀|痛|哭|泪", m):
        return "sad"
    if re.search("惊|骇|恐|惧", m):
        return "surprised"
    if re.search("喜|笑|欢|悦", m):
        return "happy"
    return "neutral"


def _pct_val(v, default=0.0):
    try:
        return float(re.sub(r"[^0-9+\-.]", "", str(v)) or default)
    except Exception:
        return default


def _pro_speech_params(rate, pitch, volume):
    speed = max(0.5, min(2.0, 1.0 + _pct_val(rate) / 100.0))
    semitone = max(-12, min(12, int(round(_pct_val(pitch) / 6.0))))
    vol = max(0.1, min(10.0, 1.0 + _pct_val(volume) / 100.0))
    return round(speed, 2), semitone, round(vol, 2)


def _http_json(url, body, headers, timeout=90):
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _pro_synth_minimax(text, voice, rate, pitch, volume, mood, cfg):
    speed, semitone, vol = _pro_speech_params(rate, pitch, volume)
    body = {
        "model": cfg["minimax_model"], "text": text, "stream": False,
        "voice_setting": {"voice_id": voice, "speed": speed, "vol": vol,
                          "pitch": semitone, "emotion": _pro_emotion(mood)},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
        "language_boost": "Chinese", "output_format": "hex",
    }
    headers = {"Authorization": "Bearer " + cfg["minimax_key"]}
    last = None
    for url in ("https://api.minimax.cn/v1/t2a_v2", "https://api-bj.minimaxi.com/v1/t2a_v2"):
        try:
            js = _http_json(url, body, headers)
            if js.get("base_resp", {}).get("status_code") not in (0, None):
                last = js.get("base_resp", {}).get("status_msg") or "合成失败"
                continue
            hexs = (js.get("data") or {}).get("audio") or ""
            if hexs:
                return bytes.fromhex(hexs)
            last = "返回音频为空"
        except Exception as e:
            last = str(e)
    raise RuntimeError(f"MiniMax 合成失败：{last}")


def _pro_synth_volc(text, voice, rate, pitch, volume, mood, cfg):
    speed, _semitone, _vol = _pro_speech_params(rate, pitch, volume)
    body = {
        "app": {"appid": cfg["volc_appid"], "token": cfg["volc_token"],
                "cluster": cfg["volc_cluster"] or "volcano_tts"},
        "user": {"uid": "fj_novel_reader"},
        "audio": {"voice_type": voice, "encoding": "mp3", "speed_ratio": speed,
                  "emotion": _pro_emotion(mood), "enable_emotion": True,
                  "emotion_scale": 3, "loudness_ratio": 1.0},
        "request": {"reqid": hashlib.md5((text + voice).encode("utf-8")).hexdigest(),
                    "text": text, "operation": "query", "model": "seed-tts-1.1"},
    }
    js = _http_json("https://openspeech.bytedance.com/api/v1/tts", body,
                    {"Authorization": "Bearer;" + cfg["volc_token"]})
    if js.get("code") != 3000:
        raise RuntimeError(f"火山合成失败：{js.get('message') or js.get('code')}")
    raw = js.get("data") or ""
    if not raw:
        raise RuntimeError("火山返回音频为空")
    if raw.startswith("http"):
        import urllib.request
        with urllib.request.urlopen(raw, timeout=60) as r:
            return r.read()
    return base64.b64decode(raw)


_PRO_AZURE_STYLE = {"angry": "angry", "sad": "sad", "surprised": "excited", "happy": "cheerful"}


def _pro_synth_azure(text, voice, rate, pitch, volume, mood, cfg):
    speed, _semitone, _vol = _pro_speech_params(rate, pitch, volume)
    style = _PRO_AZURE_STYLE.get(_pro_emotion(mood), "calm")
    style_attrs = ""
    if style in ("calm", "sad", "angry", "cheerful", "excited") and _is_supported_style(voice, style):
        style_attrs = f'<mstts:express-as style="{style}">'
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace("'", "&apos;").replace('"', "&quot;"))
    ssml = ('<ssml version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN">'
            f'<voice name="{voice}">{style_attrs}'
            f'<prosody rate="{_azure_rate(rate)}" pitch="{pitch}" volume="{volume}">{esc}</prosody>'
            + ("</mstts:express-as>" if style_attrs else "") + "</voice></ssml>")
    import urllib.request
    req = urllib.request.Request(
        f"https://{cfg['azure_region']}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={"Ocp-Apim-Subscription-Key": cfg["azure_key"],
                 "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def _azure_rate(rate):
    p = int(round(_pct_val(rate)))
    return ("+%d%%" % p) if p >= 0 else ("%d%%" % p)


def _is_supported_style(voice, style):
    """Azure 里不是每个音色都支持全部 style，不支持的会直接报错，这里按音色白名单过滤。"""
    allow = {
        "zh-CN-XiaoxiaoNeural": {"calm", "sad", "angry", "cheerful", "excited", "gentle", "newscast"},
        "zh-CN-YunxiNeural": {"sad", "angry", "cheerful", "serious"},
        "zh-CN-YunjianNeural": {"sad", "angry", "cheerful", "documentary-narration"},
        "zh-CN-YunyangNeural": {"newscast-casual", "narration-professional"},
    }
    return style in allow.get(voice, set())


def _pro_synth(text, voice, rate, pitch, volume, mood, cfg):
    """同步调用专业引擎，返回 mp3 字节。voice 传的是 edge 音色 id，这里换成该平台的真人音色。"""
    prov = cfg["provider"]
    if prov == "minimax":
        vid = _PRO_MINIMAX.get(voice) or _PRO_MINIMAX["zh-CN-YunxiNeural"]
        return _pro_synth_minimax(text, vid, rate, pitch, volume, mood, cfg)
    if prov == "volc":
        vid = _PRO_VOLC.get(voice) or _PRO_VOLC["zh-CN-YunxiNeural"]
        return _pro_synth_volc(text, vid, rate, pitch, volume, mood, cfg)
    if prov == "azure":
        return _pro_synth_azure(text, voice, rate, pitch, volume, mood, cfg)
    raise RuntimeError("未配置专业配音引擎")


def _pro_normalize(raw):
    """把各家不同采样率/码率的 mp3 统一成 24kHz 单声道，才能按帧无缝拼接、也便于精确计时。"""
    try:
        pcm = _mp3_decode(raw, TTS_SR)
        if pcm is None or len(pcm) == 0:
            return raw
        return _pcm_encode(pcm, TTS_SR, 96)
    except Exception:
        return raw


_PRO_PREVIEW_TEXT = "他站在城头，风把衣角扯得猎猎作响，远处雪线上升起一线狼烟。"


@app.get("/api/tts/provider")
async def api_tts_provider():
    cfg = _tts_provider_cfg()
    return {"provider": cfg["provider"], "name": _PRO_NAMES.get(cfg["provider"], ""),
            "configured": {"minimax": bool(cfg["minimax_key"]),
                           "volc": bool(cfg["volc_appid"] and cfg["volc_token"]),
                           "azure": bool(cfg["azure_key"])},
            "model": cfg["minimax_model"]}


@app.post("/api/tts/sample")
async def api_tts_sample(data: dict):
    """设置页「试听」：用当前引擎念一句，立刻听到音色质量。"""
    cfg = _tts_provider_cfg()
    text = str(data.get("text") or _PRO_PREVIEW_TEXT)[:200]
    voice = str(data.get("voice") or "zh-CN-YunyangNeural")
    rate = str(data.get("rate") or "-2%")
    pitch = str(data.get("pitch") or "+0Hz")
    volume = str(data.get("volume") or "+0%")
    mood = str(data.get("mood") or "")
    from fastapi.responses import Response
    try:
        if cfg["provider"] == "edge":
            raw = await _tts_clip(text, voice, rate, pitch, volume)
        else:
            raw = await asyncio.to_thread(_pro_synth, text, voice, rate, pitch, volume, mood, cfg)
            raw = await asyncio.to_thread(_pro_normalize, raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not raw:
        raise HTTPException(status_code=502, detail="没有拿到音频")
    return Response(content=raw, media_type="audio/mpeg",
                    headers={"X-FJ-Provider": cfg["provider"]})


# ---- 场景音效 / BGM / 无缝拼接混音（numpy 合成 + ffmpeg 编解码） ----
TTS_SR = 24000
_SCENE_KEYS = (
    ("battle", ("厮杀", "刀", "剑", "兵", "战", "杀", "箭", "血", "铠甲", "甲胄", "冲锋", "战鼓", "拔刀", "尸")),
    ("fire", ("火", "烧", "焰", "烛", "炉", "炭", "焦", "噼啪", "烟")),
    ("rain", ("雨", "雷", "湿", "檐", "水洼", "淋")),
    ("snow", ("雪", "冰", "霜", "凛冽", "风雪")),
    ("water", ("河", "江", "湖", "浪", "舟", "船", "溪", "水声")),
    ("city", ("街", "集市", "摊", "酒馆", "客栈", "茶楼", "巷", "人群", "喧", "马车")),
    ("forest", ("林", "树", "竹", "鸟", "荒野", "山坡")),
    ("night", ("夜", "月", "更鼓", "星", "寂静")),
    ("wind", ("风", "沙", "尘", "呼啸")),
)


def _ffmpeg_path():
    env = os.environ.get("FJ_FFMPEG")
    if env and os.path.isfile(env):
        return env
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    try:
        return shutil.which("ffmpeg") or ""
    except Exception:
        return ""


def _mix_ready():
    """安卓端没有 ffmpeg/numpy，混音会失败；这时退回纯净人声拼接，保证有声剧还能播。"""
    if not _ffmpeg_path():
        return False
    try:
        import numpy  # noqa
        return True
    except Exception:
        return False


def _ff_run(args, timeout=240):
    import subprocess
    exe = _ffmpeg_path()
    if not exe:
        raise RuntimeError("ffmpeg 不可用")
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y"] + list(args)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or b"").decode("utf-8", "ignore")[:300])


def _mp3_decode(data, sr=TTS_SR):
    """mp3 字节 → float32 单声道 PCM（失败返回 None）"""
    try:
        import numpy as np
    except Exception:
        return None
    fd, ip = tempfile.mkstemp(suffix=".mp3", prefix="fjs_")
    os.close(fd)
    op = ip + ".raw"
    try:
        with open(ip, "wb") as f:
            f.write(data)
        _ff_run(["-i", ip, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-acodec", "pcm_s16le", op])
        with open(op, "rb") as f:
            raw = f.read()
    except Exception:
        raw = b""
    finally:
        for p in (ip, op):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
    if not raw:
        return None
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _pcm_encode(samples, sr=TTS_SR, kbps=96):
    """float32 PCM → mp3（失败返回 None）"""
    try:
        import numpy as np
    except Exception:
        return None
    data = np.clip(samples, -1.0, 1.0)
    raw = (data * 32767.0).astype(np.int16).tobytes()
    fd, ip = tempfile.mkstemp(suffix=".raw", prefix="fjm_")
    os.close(fd)
    op = ip + ".mp3"
    try:
        with open(ip, "wb") as f:
            f.write(raw)
        _ff_run(["-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", ip,
                 "-c:a", "libmp3lame", "-b:a", f"{kbps}k", "-ar", str(sr), "-ac", "1", op])
        with open(op, "rb") as f:
            out = f.read()
    except Exception:
        out = b""
    finally:
        for p in (ip, op):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
    return out or None


def _detect_scene(text):
    """从正文里认场景音（没认到返回空，沿用上一个场景）"""
    t = str(text or "")
    for name, keys in _SCENE_KEYS:
        for k in keys:
            if k in t:
                return name
    return ""


def _scene_runs(segs):
    cur = "room"
    out = []
    for s in segs:
        k = _detect_scene((s or {}).get("text") if isinstance(s, dict) else "")
        if k:
            cur = k
        out.append(cur)
    return out


def _smooth(x, w):
    np = _np_mod()
    w = int(max(1, w))
    if w <= 1 or len(x) == 0:
        return x
    pad = np.pad(x, (w, w), mode="edge")
    c = np.concatenate(([0.0], np.cumsum(pad, dtype=np.float64)))
    n = len(x)
    return ((c[2 * w:2 * w + n] - c[w:w + n]) / w).astype(np.float32)


def _np_mod():
    import numpy as np
    return np


def _env(n, rng, lo=0.03, hi=0.12):
    np = _np_mod()
    t = np.arange(n, dtype=np.float32) / TTS_SR
    e1 = 0.55 + 0.45 * np.sin(2 * np.pi * rng.uniform(lo, hi) * t + rng.uniform(0, 6.28))
    e2 = 0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(lo, hi) * t + rng.uniform(0, 6.28))
    return (e1 * 0.7 + e2 * 0.3).astype(np.float32)


def _bursts(n, rng, per_sec, dur, amp=1.0):
    np = _np_mod()
    out = np.zeros(n, dtype=np.float32)
    cnt = int(max(1, n / TTS_SR * per_sec))
    for _ in range(cnt):
        pos = int(rng.integers(0, max(1, n - 1)))
        L = min(n - pos, int(dur * TTS_SR * rng.uniform(0.6, 1.4)))
        if L <= 8:
            continue
        t = np.arange(L, dtype=np.float32) / TTS_SR
        dec = np.exp(-t * (3.0 / dur)).astype(np.float32)
        out[pos:pos + L] += rng.standard_normal(L).astype(np.float32) * dec * amp
    return out


def _murmur(n, rng):
    np = _np_mod()
    b = _smooth(rng.standard_normal(n).astype(np.float32), 12) * 2.0
    t = np.arange(n, dtype=np.float32) / TTS_SR
    amp = (0.3 + 0.7 * np.abs(np.sin(2 * np.pi * rng.uniform(2.0, 4.5) * t))).astype(np.float32)
    return b * amp * _env(n, rng) * 0.45


def _crickets(n, rng):
    np = _np_mod()
    t = np.arange(n, dtype=np.float32) / TTS_SR
    f = rng.uniform(4200, 5400)
    gate = np.clip(np.sin(2 * np.pi * rng.uniform(0.8, 1.6) * t + rng.uniform(0, 6.28)), 0, 1)
    return (np.sin(2 * np.pi * f * t) * gate * 0.05).astype(np.float32)


def _birds(n, rng):
    np = _np_mod()
    out = np.zeros(n, dtype=np.float32)
    for _ in range(int(max(1, n / TTS_SR / 6))):
        pos = int(rng.integers(0, max(1, n - 1)))
        L = min(n - pos, int(0.22 * TTS_SR))
        if L <= 16:
            continue
        t = np.arange(L, dtype=np.float32) / TTS_SR
        f0 = rng.uniform(1800, 3200)
        sweep = np.sin(2 * np.pi * (f0 + 900 * t) * t)
        out[pos:pos + L] += (sweep * np.exp(-t * 9.0) * 0.05).astype(np.float32)
    return out


def _clangs(n, rng):
    np = _np_mod()
    out = np.zeros(n, dtype=np.float32)
    for _ in range(int(max(1, n / TTS_SR / 2.5))):
        pos = int(rng.integers(0, max(1, n - 1)))
        L = min(n - pos, int(0.6 * TTS_SR))
        if L <= 16:
            continue
        t = np.arange(L, dtype=np.float32) / TTS_SR
        f = rng.uniform(700, 2400)
        out[pos:pos + L] += (np.sin(2 * np.pi * f * t) * np.exp(-t * 7.0) * 0.16).astype(np.float32)
    return out


def _rms1(x):
    """归一到 RMS=1（防止不同场景音量差异过大）"""
    np = _np_mod()
    r = float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0
    if r < 1e-6:
        return x
    return (x / r).astype(np.float32)


_AMB_LOUD = {"wind": 1.0, "snow": 0.55, "rain": 0.9, "fire": 0.8, "water": 0.8,
             "city": 0.85, "forest": 0.75, "night": 0.8, "battle": 1.0, "room": 0.5}


def _ambience(kind, n, rng):
    """程序化环境声（风/雪/雨/火/水/市/林/夜/战/室内）"""
    np = _np_mod()
    nz = rng.standard_normal(n).astype(np.float32)
    if kind == "wind":
        x = _smooth(nz, 90) * 4.0 * _env(n, rng, 0.04, 0.16)
        x += _smooth(rng.standard_normal(n).astype(np.float32), 26) * 1.2 * _env(n, rng, 0.05, 0.18)
    elif kind == "snow":
        x = _smooth(nz, 130) * 3.2 * _env(n, rng, 0.02, 0.07) * 0.4
    elif kind == "rain":
        x = (nz - _smooth(nz, 6)) * 0.2 + _bursts(n, rng, 20, 0.05, 0.16)
        x += _smooth(nz, 200) * 5.0 * 0.25
    elif kind == "fire":
        x = _smooth(nz, 140) * 5.0 * _env(n, rng, 0.08, 0.25) * 0.5 + _bursts(n, rng, 6, 0.035, 0.32)
    elif kind == "water":
        x = _smooth(nz, 60) * 3.5 * _env(n, rng, 0.05, 0.12) + _bursts(n, rng, 3, 0.12, 0.1)
    elif kind == "city":
        x = _smooth(nz, 24) * 2.2 + _murmur(n, rng) + _bursts(n, rng, 1.2, 0.09, 0.1)
    elif kind == "night":
        x = _smooth(nz, 170) * 3.0 * 0.55 + _crickets(n, rng)
    elif kind == "forest":
        x = _smooth(nz, 100) * 3.0 * 0.55 + _birds(n, rng)
    elif kind == "battle":
        x = _smooth(nz, 90) * 4.0 * _env(n, rng, 0.06, 0.2) + _bursts(n, rng, 2, 0.18, 0.28) + _clangs(n, rng)
    else:
        x = _smooth(nz, 220) * 6.0 * 0.16
    return _rms1(x.astype(np.float32)) * _AMB_LOUD.get(kind, 0.85)


def _bgm(n, rng, tense=False):
    """程序化 BGM：五声音阶氛围铺底 + 稀疏拨弦"""
    np = _np_mod()
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    t = np.arange(n, dtype=np.float32) / TTS_SR
    base = 174.0 if tense else 196.0
    scale = [0, 2, 4, 7, 9]
    pad = np.zeros(n, dtype=np.float32)
    for deg in (0, 2, 4):
        f = base * (2.0 ** (scale[deg] / 12.0))
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(0.03, 0.07) * t + rng.uniform(0, 6.28))
        pad += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)).astype(np.float32) * lfo.astype(np.float32)
    pad /= 3.0
    pluck = np.zeros(n, dtype=np.float32)
    pos = 0
    while pos < n - 1:
        pos += int(rng.uniform(1.8, 3.6) * TTS_SR)
        if pos >= n:
            break
        f = base * (2.0 ** (int(rng.choice(scale)) / 12.0)) * (2.0 if rng.random() < 0.3 else 1.0)
        L = min(n - pos, int(2.2 * TTS_SR))
        tt = np.arange(L, dtype=np.float32) / TTS_SR
        pluck[pos:pos + L] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.0) * 0.35).astype(np.float32)
    x = pad * 0.35 + pluck
    fi = min(n, int(1.5 * TTS_SR))
    fo = min(n, int(2.5 * TTS_SR))
    if fi > 0:
        x[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    if fo > 0:
        x[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    return _rms1(x.astype(np.float32))


def _smooth_runs(runs, dur_samp, sr, min_sec=12.0):
    """把过短的场景并到相邻场景，避免环境声每隔十几秒就换一次"""
    r = list(runs)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(r):
            j = i
            while j + 1 < len(r) and r[j + 1] == r[i]:
                j += 1
            dur = sum(dur_samp[i:j + 1]) / float(sr)
            if dur < min_sec and (i > 0 or j + 1 < len(r)):
                tgt = r[i - 1] if i > 0 else r[j + 1]
                for k in range(i, j + 1):
                    r[k] = tgt
                changed = True
            i = j + 1
    return r


def _gap_samples(a, b, scene_change, sr):
    """按「旁白/台词」顺序与句尾标点算停顿，让节奏像真人播讲"""
    gap = 0.16
    ka = str((a or {}).get("kind") or "")
    kb = str((b or {}).get("kind") or "")
    if ka == "nar" and kb == "dlg":
        gap = 0.22
    elif ka == "dlg" and kb == "dlg":
        gap = 0.13
    elif ka == "dlg" and kb == "nar":
        gap = 0.24
    ta = str((a or {}).get("text") or "")
    if ta[-1:] in "！!？?":
        gap += 0.08
    elif ta[-2:] in ("……", "——") or ta[-1:] == "…":
        gap += 0.10
    if scene_change:
        gap = 0.42
    return int(gap * sr)


_MOOD_THEME = {"怒": "tense", "惊": "tense", "急促": "tense", "悲": "sad", "沉冷": "dark",
               "喜": "calm", "低语": "calm"}


def _seg_theme(s):
    if not isinstance(s, dict):
        return "calm"
    t = str(s.get("text") or "")
    m = str(s.get("mood") or "")
    if any(k in t for k in ("厮杀", "刀", "剑", "血", "杀", "战", "箭", "冲锋", "砍", "尸")):
        return "battle"
    if any(k in t for k in ("捷报", "凯旋", "大军", "王师", "将军", "五皇子")):
        return "epic"
    if m in ("怒", "惊", "急促") or any(k in t for k in ("追", "逃", "危", "惊", "吼", "雷")):
        return "tense"
    if m == "悲" or any(k in t for k in ("泪", "哭", "悲", "离", "痛", "死", "别")):
        return "sad"
    if m == "沉冷":
        return "dark"
    return "calm"


def _music(theme, n, rng):
    """按主题生成一段配乐（氛围铺底 + 稀疏拨弦 / 战鼓）"""
    np = _np_mod()
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    cfg = {
        "calm": (196.0, [0, 2, 4, 7, 9], 3.4),
        "dark": (146.0, [0, 3, 5, 7, 10], 4.6),
        "sad": (155.0, [0, 2, 4, 7, 9], 5.0),
        "tense": (164.0, [0, 3, 5, 7, 10], 2.2),
        "battle": (131.0, [0, 2, 4, 7, 9], 1.6),
        "epic": (174.0, [0, 2, 4, 7, 9], 3.0),
    }.get(theme, (196.0, [0, 2, 4, 7, 9], 3.4))
    base, scale, step = cfg
    t = np.arange(n, dtype=np.float32) / TTS_SR
    pad = np.zeros(n, dtype=np.float32)
    for deg in (0, 2, 4):
        f = base * (2.0 ** (scale[deg] / 12.0))
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(0.03, 0.07) * t + rng.uniform(0, 6.28))
        pad += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)).astype(np.float32) * lfo.astype(np.float32)
    pad /= 3.0
    x = pad * 0.4
    pos = 0
    while pos < n - 1:
        pos += int(rng.uniform(step * 0.7, step * 1.3) * TTS_SR)
        if pos >= n:
            break
        f = base * (2.0 ** (int(rng.choice(scale)) / 12.0)) * (2.0 if rng.random() < 0.3 else 1.0)
        L = min(n - pos, int(2.2 * TTS_SR))
        tt = np.arange(L, dtype=np.float32) / TTS_SR
        x[pos:pos + L] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.0) * 0.35).astype(np.float32)
    if theme in ("battle", "tense", "epic"):
        beat = 0.5 if theme == "battle" else 0.8
        p = 0
        while p < n:
            L = min(n - p, int(0.22 * TTS_SR))
            tt = np.arange(L, dtype=np.float32) / TTS_SR
            x[p:p + L] += (np.sin(2 * np.pi * 58.0 * tt) * np.exp(-tt * 12.0) * 0.5).astype(np.float32)
            p += int(beat * TTS_SR)
    return x.astype(np.float32)


_THEME_GAIN = {"calm": 0.011, "dark": 0.014, "sad": 0.013, "tense": 0.017, "battle": 0.020, "epic": 0.017}


def _bgm_timeline(total, starts, dur_samp, segs, runs, sr):
    """只在关键情节处进场，段与段之间留出静默，避免全程铺满"""
    np = _np_mod()
    themes = [_seg_theme(s) for s in segs]
    for i, r in enumerate(runs):
        if r == "battle":
            themes[i] = "battle"
    blocks = []
    i = 0
    while i < len(themes):
        j = i
        while j + 1 < len(themes) and themes[j + 1] == themes[i]:
            j += 1
        blocks.append((starts[i], starts[j] + dur_samp[j], themes[i]))
        i = j + 1
    out = np.zeros(total, dtype=np.float32)
    last_end = -10 ** 9
    cues = 0
    for (a, b, th) in blocks:
        L = b - a
        need = int((22 if th == "calm" else 10) * sr)
        if L < need:
            continue
        if a - last_end < int(5 * sr):
            continue
        m = _music(th, L, np.random.default_rng(0x9E1B3 + a))
        fi = min(L // 3, int(1.2 * sr))
        fo = min(L // 3, int(1.6 * sr))
        if fi > 0:
            m[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
        if fo > 0:
            m[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
        out[a:b] += m * _THEME_GAIN.get(th, 0.012)
        last_end = b
        cues += 1
    return out, cues


def _stinger(kind, rng):
    """场景切换的短音效：马蹄 / 风 / 火 / 水 / 人群"""
    np = _np_mod()
    n = int(1.1 * TTS_SR)
    t = np.arange(n, dtype=np.float32) / TTS_SR
    if kind in ("battle", "city"):
        x = np.zeros(n, dtype=np.float32)
        for k in range(4):
            p = int((0.02 + 0.2 * k) * TTS_SR)
            L = min(n - p, int(0.13 * TTS_SR))
            tt = np.arange(L, dtype=np.float32) / TTS_SR
            x[p:p + L] += (np.sin(2 * np.pi * 92.0 * tt) * np.exp(-tt * 24.0)).astype(np.float32)
    elif kind in ("wind", "snow"):
        x = _smooth(rng.standard_normal(n).astype(np.float32), 40) * 5.0
        x *= (np.linspace(0.0, 1.0, n, dtype=np.float32) * np.linspace(1.0, 0.15, n, dtype=np.float32))
    elif kind == "fire":
        x = _bursts(n, rng, 26, 0.05, 0.55)
    elif kind in ("rain", "water"):
        x = _bursts(n, rng, 18, 0.06, 0.45)
    else:
        x = _smooth(rng.standard_normal(n).astype(np.float32), 60) * 4.0
    return (_rms1(x.astype(np.float32)) * np.exp(-t * 2.2)).astype(np.float32)


def _mix_scene_audio(mp3_bytes, durations, segs, mix_mode):
    """分场景配音 → 加场景环境声 + BGM → 无缝拼接 → 重新编码 mp3。
    返回 (mp3_bytes, durations, scene_count)；失败原样返回。"""
    ff = _ffmpeg_path()
    if not ff:
        return mp3_bytes, durations, 0
    try:
        import numpy as np
    except Exception:
        return mp3_bytes, durations, 0
    pcm = _mp3_decode(mp3_bytes)
    if pcm is None or len(pcm) <= 0:
        return mp3_bytes, durations, 0
    sr = TTS_SR
    dur_samp = [max(0, int(round(d * sr / 1000))) for d in durations]
    total_src = sum(dur_samp)
    if total_src <= 0:
        return mp3_bytes, durations, 0
    if len(pcm) < total_src:
        pcm = np.pad(pcm, (0, total_src - len(pcm)))
    elif len(pcm) > total_src:
        pcm = pcm[:total_src]

    runs = _smooth_runs(_scene_runs(segs), dur_samp, sr)
    starts = []
    pos = int(0.45 * sr)
    for i, d in enumerate(dur_samp):
        starts.append(pos)
        pos += d
        if i + 1 < len(dur_samp):
            pos += _gap_samples(segs[i], segs[i + 1], runs[i + 1] != runs[i], sr)
    total = pos + int(0.6 * sr)

    speech = np.zeros(total, dtype=np.float32)
    src = 0
    for i, d in enumerate(dur_samp):
        if d <= 0:
            continue
        speech[starts[i]:starts[i] + d] = pcm[src:src + d]
        src += d

    # 环境声：每个场景一段，边界淡入淡出，无缝叠在语音下面
    amb = np.zeros(total, dtype=np.float32)
    i = 0
    scene_count = 0
    while i < len(runs):
        j = i
        while j + 1 < len(runs) and runs[j + 1] == runs[i]:
            j += 1
        a = starts[i]
        b = min(total, (starts[j] + dur_samp[j]) if j + 1 < len(runs) else total)
        seg_len = b - a
        if seg_len > 64:
            bed = _ambience(runs[i], seg_len, np.random.default_rng(0x5F3A7 + i))
            f = min(seg_len // 2, int(0.32 * sr))
            if f > 0:
                bed[:f] *= np.linspace(0.0, 1.0, f, dtype=np.float32)
                bed[-f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)
            amb[a:a + seg_len] += bed
            scene_count += 1
        i = j + 1

    mix = speech * 1.12
    if mix_mode in ("auto", "fx"):
        mix += amb * 0.025
    if mix_mode == "auto":
        # 场景切换的短音效
        last = runs[0]
        for i in range(1, len(runs)):
            if runs[i] != last:
                sfx = _stinger(runs[i], np.random.default_rng(0x7C1 + i))
                p = max(0, starts[i] - len(sfx))
                e = min(total, p + len(sfx))
                mix[p:e] += sfx[:e - p] * 0.05
                last = runs[i]
        bgm, cues = _bgm_timeline(total, starts, dur_samp, segs, runs, sr)
        mix += bgm

    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.98:
        mix = mix / peak * 0.98
    enc = _pcm_encode(mix)
    if not enc:
        return mp3_bytes, durations, scene_count

    out_durs = []
    for k in range(len(starts)):
        nxt = starts[k + 1] if k + 1 < len(starts) else total
        out_durs.append(int(round((nxt - starts[k]) / sr * 1000)))
    return enc, out_durs, scene_count


@app.get("/api/tts/voices")
async def api_tts_voices():
    """可用音色表（前端选角用）"""
    try:
        import edge_tts  # noqa: F401
        ready = True
    except Exception:
        ready = False
    return {"success": True, "ready": ready, "voices": TTS_VOICES}


@app.post("/api/tts")
async def api_tts(data: dict):
    """合成一段 mp3（试听 / 兜底用）"""
    text = re.sub(r"\s+", " ", (data.get("text") or "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="没有要念的文本")
    if len(text) > 1200:
        text = text[:1200]
    voice = (data.get("voice") or "zh-CN-XiaoxiaoNeural").strip()
    rate = (data.get("rate") or "+0%").strip()
    pitch = (data.get("pitch") or "+0Hz").strip()
    volume = (data.get("volume") or "+0%").strip()
    try:
        import edge_tts  # noqa: F401
    except Exception:
        raise HTTPException(status_code=503, detail="服务器未安装 edge-tts，已回退到浏览器本地朗读")

    try:
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    except OSError:
        pass
    from fastapi.responses import FileResponse, Response
    fp = _tts_cache_file(text, voice, rate, pitch, volume)
    if os.path.isfile(fp) and os.path.getsize(fp) > 0:
        return FileResponse(fp, media_type="audio/mpeg")

    try:
        raw = await _tts_clip(text, voice, rate, pitch, volume)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"配音失败：{exc}")
    if not raw:
        raise HTTPException(status_code=502, detail="配音失败：没有拿到音频")
    try:
        with open(fp, "wb") as f:
            f.write(raw)
        return FileResponse(fp, media_type="audio/mpeg")
    except OSError:
        return Response(content=raw, media_type="audio/mpeg")


@app.post("/api/tts/drama")
async def api_tts_drama(data: dict):
    """一次合成整章：多角色、多音色 → 分场景加环境声 / BGM → 无缝拼接，返回 mp3 与每段时长。"""
    segs = data.get("segments") or []
    if not isinstance(segs, list) or not segs:
        raise HTTPException(status_code=400, detail="没有要配音的段落")
    if len(segs) > 800:
        raise HTTPException(status_code=400, detail="一次最多 800 段，请分段请求")
    mix_mode = str(data.get("mix") or "auto").strip()
    if mix_mode not in ("auto", "fx", "none"):
        mix_mode = "auto"
    cfg = _tts_provider_cfg()
    prov = cfg["provider"]
    if mix_mode != "none" and not _mix_ready():
        mix_mode = "none"   # 安卓等无 ffmpeg 环境：退回纯净人声
    if prov == "edge":
        try:
            import edge_tts  # noqa: F401
        except Exception:
            raise HTTPException(status_code=503, detail="服务器未安装 edge-tts，已回退到浏览器本地朗读")

    try:
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    except OSError:
        pass

    from fastapi.responses import Response, FileResponse
    # 混音结果整章级缓存（同样的分段 / 混音参数 / 配音引擎直接回放）
    mix_key = hashlib.md5(json.dumps([segs, mix_mode, 3, prov, cfg.get("minimax_model", "")], ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()
    mix_mp3 = os.path.join(TTS_CACHE_DIR, "mix_" + mix_key + ".mp3")
    mix_meta = os.path.join(TTS_CACHE_DIR, "mix_" + mix_key + ".json")
    if mix_mode != "none" and os.path.isfile(mix_mp3) and os.path.getsize(mix_mp3) > 0 and os.path.isfile(mix_meta):
        try:
            with open(mix_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return FileResponse(mix_mp3, media_type="audio/mpeg", headers={
                "X-FJ-Durations": ",".join(str(x) for x in meta.get("durations", [])),
                "X-FJ-Total": str(meta.get("total", 0)),
                "X-FJ-Scenes": str(meta.get("scenes", 0)),
                "X-FJ-Mix": mix_mode,
                "Cache-Control": "no-store",
            })
        except Exception:
            pass

    sem = asyncio.Semaphore(6)

    async def one(s):
        if not isinstance(s, dict):
            return b"", 0, ""
        text = re.sub(r"\s+", " ", (s.get("text") or "")).strip()[:600]
        if not text:
            return b"", 0, ""
        voice = (s.get("voice") or "zh-CN-YunyangNeural").strip()
        rate = (s.get("rate") or "+0%").strip()
        pitch = (s.get("pitch") or "+0Hz").strip()
        volume = (s.get("volume") or "+0%").strip()
        mood = (s.get("mood") or "").strip()
        fp = _tts_cache_file(text, f"{prov}|{cfg.get('minimax_model', '')}|{voice}", rate, pitch, volume)
        raw = b""
        if os.path.isfile(fp) and os.path.getsize(fp) > 0:
            try:
                with open(fp, "rb") as f:
                    raw = f.read()
            except OSError:
                raw = b""
        if not raw:
            async with sem:
                try:
                    if prov == "edge":
                        raw = await _tts_clip(text, voice, rate, pitch, volume)
                    else:
                        raw = await asyncio.to_thread(_pro_synth, text, voice, rate, pitch, volume, mood, cfg)
                        raw = await asyncio.to_thread(_pro_normalize, raw)
                except Exception:
                    raw = b""
            if raw:
                try:
                    with open(fp, "wb") as f:
                        f.write(raw)
                except OSError:
                    pass
        clean, _frames, ms = _mp3_scan(raw)
        return clean, _frames, ms

    parts = await asyncio.gather(*(one(s) for s in segs))
    if not any(p[0] for p in parts):
        raise HTTPException(status_code=502, detail="配音失败：所有段落都没有拿到音频")
    out = b"".join(p[0] for p in parts)
    durations = [int(p[2]) for p in parts]
    scenes = 0
    if mix_mode != "none":
        try:
            out, durations, scenes = await asyncio.to_thread(_mix_scene_audio, out, durations, segs, mix_mode)
        except Exception:
            pass
    total = sum(durations)
    headers = {
        "X-FJ-Durations": ",".join(str(x) for x in durations),
        "X-FJ-Total": str(total),
        "X-FJ-Scenes": str(scenes),
        "X-FJ-Mix": mix_mode,
        "X-FJ-Provider": prov,
        "Cache-Control": "no-store",
    }
    if scenes and mix_mode != "none":
        try:
            with open(mix_mp3, "wb") as f:
                f.write(out)
            with open(mix_meta, "w", encoding="utf-8") as f:
                json.dump({"durations": durations, "total": total, "scenes": scenes}, f)
        except OSError:
            pass
    return Response(content=out, media_type="audio/mpeg", headers=headers)


# ============ 自建同步中心（零成本，三端互通） ============
SYNC_SETTING_KEYS = {
    "enabled": "sync_enabled",
    "role": "sync_role",
    "hub_url": "sync_hub_url",
    "token": "sync_token",
    "tunnel": "sync_tunnel",
}


def _sync_boot(port):
    """把同步引擎接上：初始化、回写 token、按配置起后台线程 / 监听 / 隧道"""
    if not sync_hub:
        return
    try:
        sync_hub.init(DATA_DIR, PROJECTS_DIR, load_project, save_project, _project_names)
        settings = load_settings()
        cfg = sync_hub.configure(settings)
        if cfg["token"] and settings.get("sync_token") != cfg["token"]:
            settings["sync_token"] = cfg["token"]
            save_settings(settings)
        sync_hub.boot(app, port, _sync_bind_all())
    except Exception as e:
        print("⚠ 同步中心启动失败:", e)


def _sync_bind_all():
    return os.environ.get("FJ_HOST", "127.0.0.1") in ("0.0.0.0", "::")


def _sync_guard(request: Request):
    if not sync_hub:
        raise HTTPException(status_code=503, detail="同步模块未加载")
    st = sync_hub.status()
    if st["role"] != "hub":
        raise HTTPException(status_code=403, detail="本机没有作为同步中心")
    if not sync_hub.verify_token(request.headers.get("x-sync-token") or ""):
        raise HTTPException(status_code=401, detail="同步令牌不正确")


@app.get("/api/sync/status")
async def api_sync_status():
    if not sync_hub:
        raise HTTPException(status_code=503, detail="同步模块未加载")
    st = sync_hub.status()
    st["platform"] = sys.platform
    st["android"] = bool(os.environ.get("FJ_ANDROID"))
    st["port"] = int(os.environ.get("FJ_PORT", "8765"))
    return st


@app.post("/api/sync/config")
async def api_sync_config(data: dict):
    if not sync_hub:
        raise HTTPException(status_code=503, detail="同步模块未加载")
    settings = load_settings()
    for k, sk in SYNC_SETTING_KEYS.items():
        if k in data:
            settings[sk] = data[k]
    if data.get("rotate"):
        settings["sync_token"] = sync_hub.new_token()
    save_settings(settings)
    cfg = sync_hub.configure(settings)
    if cfg["token"] and settings.get("sync_token") != cfg["token"]:
        settings["sync_token"] = cfg["token"]
        save_settings(settings)
    if data.get("reset_cache"):
        sync_hub.reset_client_cache()
    if not settings.get("sync_tunnel"):
        sync_hub.stop_tunnel()
    sync_hub.boot(app, int(os.environ.get("FJ_PORT", "8765")), _sync_bind_all())
    try:
        sync_hub.run_now()
    except Exception:
        pass
    return sync_hub.status()


@app.post("/api/sync/run")
async def api_sync_run():
    """立即同步一次（客户端）；hub 侧就是把自己的改动登版"""
    if not sync_hub:
        raise HTTPException(status_code=503, detail="同步模块未加载")
    return sync_hub.run_now()


@app.get("/api/sync/ping")
async def api_sync_ping():
    if not sync_hub:
        raise HTTPException(status_code=503, detail="同步模块未加载")
    st = sync_hub.status()
    return {"app": "fenghuo", "ok": True, "role": st["role"],
            "device": st["device"], "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


@app.get("/api/sync/manifest")
async def api_sync_manifest(request: Request):
    _sync_guard(request)
    return sync_hub.manifest()


@app.get("/api/sync/project")
async def api_sync_project(request: Request, name: str = Query(...)):
    _sync_guard(request)
    got = sync_hub.hub_get(name)
    if got is None:
        raise HTTPException(status_code=404, detail="同步中心没有这本书")
    return got


@app.post("/api/sync/push")
async def api_sync_push(request: Request, data: dict):
    _sync_guard(request)
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="缺少书名")
    return sync_hub.hub_push(name, data.get("project"), data.get("base_rev") or 0,
                             data.get("device") or "")


@app.post("/api/sync/delete")
async def api_sync_delete(request: Request, data: dict):
    _sync_guard(request)
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="缺少书名")
    return sync_hub.hub_delete(name, data.get("base_rev") or 0)


# ============ 静态文件服务（前端） ============
FRONTEND_DIR = os.environ.get("FJ_FRONTEND_DIR") or os.path.join(APP_DIR, "frontend")
LEGACY_FRONTEND_DIR = os.path.join(APP_DIR, "NovelIDE-main", "dist")
if not os.path.isfile(os.path.join(FRONTEND_DIR, "index.html")):
    FRONTEND_DIR = LEGACY_FRONTEND_DIR

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """服务前端静态文件"""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)

    file_path = os.path.join(FRONTEND_DIR, full_path) if full_path else os.path.join(FRONTEND_DIR, "index.html")

    # 页面/脚本/样式不缓存，避免改动后浏览器仍用旧文件
    NO_CACHE_EXT = (".html", ".js", ".css")

    def _serve(path: str):
        headers = None
        if path.lower().endswith(NO_CACHE_EXT):
            headers = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        return FileResponse(path, headers=headers)

    if os.path.isfile(file_path):
        return _serve(file_path)

    # SPA fallback: 返回 index.html
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return _serve(index_path)

    return JSONResponse({"message": "前端未构建，请先运行 npm run build"}, status_code=404)


# ============ 启动 ============
def run_server(host="127.0.0.1", port=8765, open_browser=True):
    """启动 HTTP 服务（桌面端 / 网页端共用）"""
    settings = load_settings()
    ai_service.set_api_config(
        api_key=settings.get("api_key", ""),
        base_url=settings.get("base_url", "https://api.deepseek.com/v1"),
        model=settings.get("model", "deepseek-flash"),
    )
    if open_browser:
        def _open():
            try:
                import webbrowser
                webbrowser.open(f"http://127.0.0.1:{port}/")
            except Exception:
                pass
        threading.Timer(1.5, _open).start()
    # 开机就盯着 GitHub 周榜和每日语料，不用等用户先聊一句
    try:
        _brain_seed_styles()      # 先把作家笔法写进库，再起同步线程，免得两边抢写锁
        if brain_ingest:
            brain_ingest.backfill_styles(8)   # 老文章补抽文风样本（纯本地）
        _brain_ensure_worker()
    except Exception as e:
        print("⚠ 搭子大脑后台线程没起来:", e)
    # 自建同步中心（桌面/网页可当中心，安卓端只当客户端）
    _sync_boot(port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def main():
    host = os.environ.get("FJ_HOST", "127.0.0.1")
    port = int(os.environ.get("FJ_PORT", "8765"))

    print("=" * 56)
    print("  烽火南境 小说生成器 v2.2")
    print("  Backend: FastAPI + Python")
    print("  Frontend: 写作台（炼笔智作 UI）")
    print("=" * 56)
    print(f"\n  本机界面: http://127.0.0.1:{port}/")
    if host in ("0.0.0.0", "::"):
        for ip in _lan_ips():
            print(f"  局域网（手机可访问）: http://{ip}:{port}/")
    else:
        print("  手机访问请用：启动网页版(手机可访问).bat")
    print(f"\n  数据目录: {DATA_DIR}")
    print("\n  按 Ctrl+C 停止服务\n")

    run_server(host, port, open_browser=os.environ.get("NOVEL_NO_BROWSER") != "1")

if __name__ == "__main__":
    main()