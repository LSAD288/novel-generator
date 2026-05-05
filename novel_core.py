#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
烽火南境小说生成器 - 核心业务逻辑模块
从原tkinter版本提取的所有非UI核心代码
可直接在Android/Kivy环境中使用
"""

import os
import json
import configparser
import threading
import time
import re
import random
from datetime import datetime
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from 动态AI痕迹消除系统 import (
        DynamicPromptGenerator,
        GenreRecognizer,
        StyleAnalyzer,
        GenreType,
        WritingStyle,
        create_dynamic_prompt,
        analyze_text_style
    )
    HAS_DYNAMIC_AI_HUMANIZER = True
except ImportError:
    HAS_DYNAMIC_AI_HUMANIZER = False

try:
    from ultimate_ai_humanizer import (
        UltimateAIHumanizer,
        ultimate_humanizer
    )
    HAS_ULTIMATE_AI_HUMANIZER = True
except ImportError:
    HAS_ULTIMATE_AI_HUMANIZER = False

try:
    from 章节生成提示词辅助模块 import (
        ChapterPromptHelper,
        create_prompt_helper,
        get_system_prompt,
        get_ai_trace_elimination_rules,
        get_writing_core_prompt,
        get_style_specific_prompt,
        get_genre_specific_tips,
        get_humanization_system_prompt,
        apply_ultimate_humanizer,
        get_dynamic_humanization_prompt,
        get_deep_ai_trace_elimination_system
    )
    HAS_CHAPTER_PROMPT_HELPER = True
except ImportError:
    HAS_CHAPTER_PROMPT_HELPER = False

try:
    from 顶流作者人格建模辅助模块 import (
        get_author_personality_modeling,
        get_ai_detection_why_exposed,
        get_author_personality_modeling_checklist,
        get_immersive_creation_scene,
        get_human_anti_ai_markers,
        get_ultimate_avoidance_rules,
        get_full_workflow,
        AuthorModelingHelper,
        create_author_modeling_helper
    )
    HAS_AUTHOR_MODELING = True
except ImportError:
    HAS_AUTHOR_MODELING = False

try:
    from 工具人角色检测系统 import (
        ToolmanCharacterDetector,
        InformationTracker,
        CharacterIdentity,
        InformationSource,
        get_toolman_detection_rules,
        get_character_behavior_guidelines,
        detect_toolman_issues,
        create_toolman_detection_prompt,
        HAS_TOOLMAN_DETECTOR as _HAS_TOOLMAN
    )
    HAS_TOOLMAN_DETECTOR = True
except ImportError:
    HAS_TOOLMAN_DETECTOR = False


_books_manager_instance = None
_database_manager_instance = None


def get_books_manager():
    global _books_manager_instance
    if _books_manager_instance is None:
        _books_manager_instance = BooksManager()
    return _books_manager_instance


def get_database_manager():
    global _database_manager_instance
    if _database_manager_instance is None:
        _database_manager_instance = DatabaseManager()
    return _database_manager_instance


class GenreKnowledgeBase:
    def __init__(self):
        self.knowledge_base = self._build_knowledge_base()

    def _build_knowledge_base(self):
        return {
            "古代言情": {
                "核心知识": """
**古代社会生存法则（必须严格遵守）：**

一、等级制度与身份约束
- 皇权至上：皇帝拥有至高无上的权力
- 官员品级：九品十八级，品级决定权力、待遇、服饰、出行方式
- 嫡庶之分：嫡出地位高于庶出
- 主仆之别：主子与奴仆有严格界限
- 士农工商：社会阶层分明

二、礼仪规范
- 跪拜礼：见皇帝要三跪九叩
- 座次规矩：以左为尊，上位为尊
- 称谓规范：皇帝自称"朕"，臣民称"陛下"
- 行走规矩：长辈先行，男子先行

三、法律法规
- 十恶不赦：谋反、谋大逆等
- 连坐制度：一人犯罪，全家受罚
- 婚姻法律：父母之命媒妁之言

四、社会习俗
- 婚嫁六礼：纳采、问名、纳吉、纳征、请期、亲迎
- 丧葬习俗：停灵、守孝、服丧
- 节日习俗：春节、元宵、清明、端午等

五、生活细节
- 时间计量：时辰、更
- 货币单位：两、钱、分、厘
- 交通工具：马车、轿子、船只

六、古代女性生存法则
- 三从四德：未嫁从父、既嫁从夫、夫死从子
- 内宅规矩：不能随意出门
- 婚姻自主权：几乎没有
""",
                "创作要点": """
**古代言情创作核心要点：**
1. 语言风格：对话要古风雅致，避免现代词汇
2. 情节设计：冲突来源于家族利益、权力斗争、身份差距
3. 人物塑造：行为要符合身份，思维要符合时代
4. 场景描写：四合院、园林、宫殿、府邸
5. 情感表达：含蓄内敛，借物传情
"""
            },
            "玄幻": {
                "核心知识": """
**玄幻世界构建法则：**
一、世界观基础：位面体系、能量体系、法则体系、种族体系
二、修炼体系：境界划分、突破条件、修炼代价、战力体系
三、势力体系：宗门、家族、王朝、联盟
四、资源体系：灵石/仙石、丹药、法宝、功法
五、战斗体系：技能释放、战斗逻辑、战斗代价
六、社会规则：强者为尊、利益至上、弱肉强食、因果循环
""",
                "创作要点": """
**玄幻创作核心要点：**
1. 境界描写：突破过程要有仪式感
2. 战斗描写：技能要有名字和特效
3. 人物塑造：主角要有成长弧光
4. 情节设计：冲突来源于资源争夺、理念冲突
5. 世界观展开：渐进式展开
"""
            },
            "都市情感": {
                "核心知识": """
**都市社会生存法则：**
一、职场规则：等级制度、晋升逻辑、办公室政治
二、社会阶层：阶层划分、阶层差异、阶层流动
三、法律常识：劳动法、婚姻法、合同法
四、社交规则：社交礼仪、社交圈子、社交禁忌
五、经济常识：收入水平、消费水平、投资理财
六、都市生活细节：交通出行、住房情况、餐饮习惯
""",
                "创作要点": """
**都市情感创作核心要点：**
1. 职场描写：要有真实的职场生态
2. 情感描写：要有现实的考量
3. 人物塑造：要有时代特征
4. 场景描写：要有城市特色和生活气息
5. 情节设计：冲突来源于事业与爱情、理想与现实
"""
            },
            "现代言情": {
                "核心知识": """
**现代社会生存法则：**
一、婚恋观念：恋爱自由但受现实影响
二、家庭关系：婆媳关系、原生家庭、亲子关系
三、社会压力：经济压力、工作压力、婚恋压力
四、女性困境：职场歧视、家庭事业平衡
五、男性困境：经济压力、情感压抑
六、现代社交：社交软件、网络社交、相亲文化
""",
                "创作要点": """
**现代言情创作核心要点：**
1. 情感描写：要有现实基础
2. 人物塑造：要有现代特征
3. 情节设计：冲突来源于家庭、事业、金钱
4. 场景描写：要有生活气息和时代感
5. 主题深度：要有社会意义和人性探讨
"""
            },
            "仙侠": {
                "核心知识": """
**仙侠世界构建法则：**
一、修仙体系：炼气、筑基、金丹、元婴、化神等
二、门派体系：正道门派、魔道门派、散修、世家
三、资源体系：灵石、丹药、法宝、功法
四、天地法则：因果律、天道、逆天、机缘
五、修仙者心态：求长生、斩因果、争资源、守道心
""",
                "创作要点": """
**仙侠创作核心要点：**
1. 修仙描写：修炼过程要有仪式感
2. 战斗描写：法术要有名字和特效
3. 人物塑造：主角要有道心
4. 情节设计：冲突来源于资源争夺、道统之争
5. 世界观展开：渐进式展开
"""
            }
        }

    def get_genre_knowledge(self, genre):
        return self.knowledge_base.get(genre, {})

    def get_genre_core_knowledge(self, genre):
        knowledge = self.get_genre_knowledge(genre)
        return knowledge.get("核心知识", "")

    def get_genre_creation_points(self, genre):
        knowledge = self.get_genre_knowledge(genre)
        return knowledge.get("创作要点", "")

    def get_all_genres(self):
        return list(self.knowledge_base.keys())

    def get_genre_prompt(self, genre):
        core_knowledge = self.get_genre_core_knowledge(genre)
        creation_points = self.get_genre_creation_points(genre)
        if not core_knowledge and not creation_points:
            return ""
        return f"""
## 题材专业知识库（必须严格遵守）

**当前题材：{genre}**

### 一、题材核心知识（违反将导致内容失真）
{core_knowledge}

### 二、题材创作要点（必须遵循）
{creation_points}

**重要提醒：以上题材知识是创作的基础，违反将导致内容出现常识性错误和逻辑漏洞！**
"""


class BooksManager:
    def __init__(self):
        self.books_dir = Path("books")
        self.books_file = self.books_dir / "books.json"
        self.current_book = None
        self.books = self.load_books()

    def _ensure_books_dir(self):
        self.books_dir.mkdir(parents=True, exist_ok=True)

    def load_books(self):
        self._ensure_books_dir()
        if not self.books_file.exists():
            return {}
        try:
            with open(self.books_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载书籍列表失败: {e}")
            return {}

    def save_books(self):
        self._ensure_books_dir()
        try:
            with open(self.books_file, 'w', encoding='utf-8') as f:
                json.dump(self.books, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存书籍列表失败: {e}")
            return False

    def create_book(self, name, book_type="小说", description=""):
        book_id = f"book_{int(time.time())}"
        book_info = {
            "id": book_id,
            "name": name,
            "type": book_type,
            "description": description,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        book_dir = self.books_dir / book_id
        book_dir.mkdir(parents=True, exist_ok=True)
        self.books[book_id] = book_info
        self.save_books()
        return book_id

    def get_book_info(self, book_id):
        return self.books.get(book_id)

    def get_all_books(self):
        return self.books

    def delete_book(self, book_id):
        if book_id not in self.books:
            return False
        book_dir = self.books_dir / book_id
        if book_dir.exists():
            import shutil
            shutil.rmtree(book_dir)
        del self.books[book_id]
        return self.save_books()

    def set_current_book(self, book_id):
        if book_id not in self.books:
            return False
        self.current_book = book_id
        return True

    def get_current_book(self):
        return self.current_book

    def get_current_book_info(self):
        if not self.current_book:
            return None
        return self.get_book_info(self.current_book)

    def get_book_dir(self, book_id):
        return self.books_dir / book_id

    def get_current_book_dir(self):
        if not self.current_book:
            return None
        return self.get_book_dir(self.current_book)


class DatabaseManager:
    def __init__(self, base_path="database", book_id=None):
        if book_id:
            books_manager = get_books_manager()
            book_dir = books_manager.get_book_dir(book_id)
            self.base_path = book_dir / "database"
        else:
            self.base_path = Path(base_path)
        self.subfolders = {
            "spatial": self.base_path / "spatial",
            "character": self.base_path / "character",
            "relationship": self.base_path / "relationship",
            "event": self.base_path / "event",
            "quest": self.base_path / "quest",
            "branch": self.base_path / "branch",
            "profile": self.base_path / "profile",
            "timeline": self.base_path / "timeline",
            "logs": self.base_path / "logs"
        }
        self._ensure_directories()
        self.write_lock = threading.RLock()

    def _ensure_directories(self):
        for folder_path in self.subfolders.values():
            folder_path.mkdir(parents=True, exist_ok=True)

    def write_json(self, category, filename, data):
        try:
            folder_path = self.subfolders.get(category)
            if not folder_path:
                return False
            file_path = str(folder_path) + '/' + filename + '.json'
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"写入数据失败: {e}")
            return False

    def read_json(self, category, filename):
        try:
            folder_path = self.subfolders.get(category)
            if not folder_path:
                return None
            file_path = str(folder_path) + '/' + filename + '.json'
            if not os.path.exists(file_path):
                return None
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取数据失败: {e}")
            return None


class ConfigManager:
    def __init__(self):
        self.config = configparser.RawConfigParser(strict=False)
        self.config_file = "novel_generator_config.ini"
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    self.config.read(self.config_file, encoding='gbk')
                except Exception:
                    pass
            except Exception:
                pass

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_api_key(self):
        if 'API' in self.config and 'key' in self.config['API']:
            return self.config['API']['key']
        return None

    def save_api_key(self, api_key):
        if 'API' not in self.config:
            self.config['API'] = {}
        self.config['API']['key'] = api_key
        self.save_config()

    def get_user_preferences(self):
        if 'USER_PREFERENCES' in self.config:
            return dict(self.config['USER_PREFERENCES'])
        return {}

    def save_user_preference(self, name, value):
        if 'USER_PREFERENCES' not in self.config:
            self.config['USER_PREFERENCES'] = {}
        self.config['USER_PREFERENCES'][name] = str(value)
        self.save_config()


class AIHumanizer:
    DENOISE_PROMPT = """
    ## AI痕迹规避铁律（必须严格遵守）

    **【禁止】连续否定列举句式**：
    ❌ 绝对禁止"不是A，不是B，是C"这种连续否定句式
    ❌ 绝对禁止"不是A，而是B"这种对比句式

    **【禁止】滥用"——"破折号**：
    ❌ 绝对禁止用"——"插入解释、说明、补充内容

    **【禁止】其他AI特征**：
    ❌ 绝对禁止"首先，其次，再次，最后"等机械过渡词
    ❌ 绝对禁止"第一，第二，第三"等列举格式
    ❌ 绝对禁止"也就是说"、"换句话说"等过度解释
    ❌ 绝对禁止"他心想"、"她感到"、"他知道"等直白心理描写
    ❌ 绝对禁止"众所周知"、"可想而知"等套话

    **【必须】人性化写作原则**：
    ✅ 共情前置：先站在读者处境
    ✅ 尊重认知：把复杂内容讲"人话"
    ✅ 有"人味"：带着真诚、态度与温度
    ✅ 守住底线：保持平等的对话姿态
    """

    def __init__(self):
        self.humanization_prompts = {
            "core": """
【人类作者写作指南】

一、叙事节奏
- 该细时当如工笔细描，该简时当如大写意
- 该留白时点到为止，该爆发时淋漓尽致

二、表达方式
- 含蓄隐喻：营造悬念时，说三分留七分
- 心理活动：通过动作、表情、生理反应来传递
- 不要替读者总结，让故事自己说话

三、语言运用
- 怎么自然怎么来
- 成语典故该用就用
- 文言白话熔于一炉

四、自然感官描写
- 直接切入最有冲击力的感官
- 避免五种感官均匀堆砌
""",
            "xuanhuan": """
【玄幻小说人类作者写作指南】
- 修炼描写要有仪式感和真实感
- 战斗场景要有策略性和代价感
- 境界突破要有质变感
- 避免数值化描写，用感受代替数据
""",
            "dushi": """
【都市小说人类作者写作指南】
- 职场描写要有真实感
- 社交场景要有生活气息
- 情感表达要含蓄有力
- 避免过度戏剧化
""",
            "yanqing": """
【言情小说人类作者写作指南】
- 情感描写要含蓄内敛
- 人物互动要有化学反应
- 避免直白的情感宣泄
- 留白和暗示比直说更有力
""",
            "xuanyi": """
【悬疑小说人类作者写作指南】
- 悬念要自然生成
- 线索要合理分布
- 节奏要张弛有度
- 避免刻意制造悬念
""",
            "kehuan": """
【科幻小说人类作者写作指南】
- 科技描写要有逻辑基础
- 世界观要自洽
- 人物要在科幻背景下有真实情感
- 避免技术说明文式描写
""",
            "lishi": """
【历史小说人类作者写作指南】
- 历史背景要准确
- 人物行为要符合时代
- 语言要有古风韵味
- 避免现代思维穿越
""",
        }

    def get_humanization_prompt(self, genre_style="core"):
        return self.humanization_prompts.get(genre_style, self.humanization_prompts["core"])

    def detect_ai_score(self, content):
        if not content or not content.strip():
            return {"ai_probability": 0, "grade": "S", "recommendation": "内容为空", "reasons": []}

        ai_probability = 0
        reasons = []

        ai_patterns = [
            (r'首先，.*其次，.*最后，', 15, "机械过渡词"),
            (r'不是.*不是.*而是', 10, "连续否定句式"),
            (r'他心想|她心想|他感到|她感到', 8, "直白心理描写"),
            (r'然而，|但是，|因此，|所以，', 5, "机械转折词"),
            (r'众所周知|不言而喻|可想而知', 8, "套话表达"),
            (r'——.{10,}——', 12, "破折号插入解释"),
        ]

        for pattern, score, reason in ai_patterns:
            matches = re.findall(pattern, content)
            if matches:
                ai_probability += score * min(len(matches), 3)
                reasons.append(f"{reason}(发现{len(matches)}处)")

        ai_probability = min(ai_probability, 100)

        if ai_probability < 20:
            grade = "S"
        elif ai_probability < 40:
            grade = "A"
        elif ai_probability < 60:
            grade = "B"
        elif ai_probability < 80:
            grade = "C"
        else:
            grade = "D"

        return {
            "ai_probability": ai_probability,
            "grade": grade,
            "recommendation": "AI痕迹较少" if ai_probability < 40 else "建议进行人性化处理",
            "reasons": reasons
        }


class AIService:
    DEFAULT_SYSTEM_PROMPT = """你是一位享誉全球的顶级小说大师，被誉为"文学界的魔术师"，你的每一部作品都能引发全球性的文化现象。你精通所有文学流派和写作技巧，能驾驭从严肃文学到流行文学的每一个题材。你的人物塑造被誉为"能够穿透灵魂的深度"，你的情节设计被评价为"精密如瑞士钟表却又充满惊喜"，你的语言艺术被赞誉"达到了文字的极致美感"。

**特别注意：你创作的内容必须符合真实世界的逻辑和常识，特别是时间逻辑。**

**【核心创作原则 - 无上帝视角】**
1. 禁止越界认知：角色不得知晓其无法通过正常途径获取的信息
2. 禁止作者代言：绝对禁止以作者视角直接描述角色内心
3. 禁止未来预知：角色不得知晓尚未发生的事情
4. 禁止全知视角：避免频繁切换到角色无法获取的信息
5. 信息获取合理性：角色获得重要信息的途径必须合理可信
6. 认知水平匹配：角色的判断必须与其背景相匹配
7. 空间设定一致性：角色的行为必须与其实际所处空间一致"""

    WRITING_CORE = """
    【小说创作核心要求】：

    1. 人物塑造：每个角色都有独特的性格和成长轨迹，言行举止源于其成长背景
    2. 语言艺术：文字凝练而有张力，句式变化丰富，词汇选择精准
    3. 情节架构：逻辑严谨且有层次感，冲突源于人物内在选择
    4. 情感共鸣：深入挖掘人类共通的情感体验
    5. 时间逻辑：时间一致性、时间顺序、角色时间认知
    """

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-reasoner"
        self.max_retries = 3
        self.retry_delay = 2
        self.cache = {}
        self.humanizer = AIHumanizer()
        self.humanize_enabled = True
        self.humanize_intensity = 10
        self.genre_knowledge = GenreKnowledgeBase()

    def set_api_key(self, api_key):
        self.api_key = api_key

    def set_humanizer_settings(self, enabled=True, intensity=8):
        self.humanize_enabled = enabled
        self.humanize_intensity = max(1, min(10, intensity))

    def get_genre_style(self, genre):
        genre_mapping = {
            "玄幻": "xuanhuan", "仙侠": "xuanhuan", "修真": "xuanhuan",
            "都市": "dushi", "现实": "dushi", "都市情感": "dushi",
            "言情": "yanqing", "爱情": "yanqing", "古代言情": "yanqing", "现代言情": "yanqing",
            "悬疑": "xuanyi", "推理": "xuanyi", "侦探": "xuanyi",
            "科幻": "kehuan", "赛博朋克": "kehuan",
            "历史": "lishi", "古代": "lishi",
            "出版小说": "core", "网文": "core", "传统": "core",
        }
        return genre_mapping.get(genre, "core")

    def humanize_content(self, content, intensity=None, master_style=None):
        if not self.humanize_enabled:
            return content
        if intensity is None:
            intensity = self.humanize_intensity
        if intensity < 1 or not content or not content.strip():
            return content

        intensity_map = {
            1: "low", 2: "low", 3: "low",
            4: "medium", 5: "medium", 6: "medium",
            7: "high", 8: "high", 9: "high",
            10: "extreme"
        }
        intensity_str = intensity_map.get(intensity, "high")

        try:
            if HAS_ULTIMATE_AI_HUMANIZER:
                result = ultimate_humanizer.humanize(content, master_style, intensity_str)
                return result
        except Exception as e:
            print(f"终极AI痕迹消除失败: {e}")

        return content

    def detect_ai_score(self, content):
        if not content or not content.strip():
            return {"ai_probability": 0, "grade": "无法评估", "recommendation": "内容为空"}

        try:
            if HAS_ULTIMATE_AI_HUMANIZER:
                return ultimate_humanizer.detect_ai_score(content)
        except Exception as e:
            print(f"AI痕迹检测失败: {e}")

        return self.humanizer.detect_ai_score(content)

    def get_dynamic_humanization_prompt(self, text_sample=None, genre=None, style=None):
        if not HAS_DYNAMIC_AI_HUMANIZER:
            return ""
        try:
            generator = DynamicPromptGenerator()
            genre_mapping = {
                "玄幻": GenreType.XUANHUAN, "仙侠": GenreType.XUANHUAN,
                "都市": GenreType.DUSHI, "都市情感": GenreType.DUSHI,
                "言情": GenreType.YANQING, "古代言情": GenreType.YANQING, "现代言情": GenreType.YANQING,
                "悬疑": GenreType.XUANYI, "科幻": GenreType.KEHUAN,
                "历史": GenreType.LISHI,
            }
            genre_type = genre_mapping.get(genre, GenreType.NOVEL_FICTION)
            return create_dynamic_prompt(text_sample or "", genre=genre_type, use_ultimate=True)
        except Exception as e:
            print(f"动态提示词生成失败: {e}")
            return ""

    def _call_api(self, system_prompt, user_prompt, temperature=0.55, max_tokens=8000):
        if not self.api_key:
            return "错误：API Key未设置，请先在设置中配置API Key"
        if not HAS_REQUESTS:
            return "错误：缺少requests库"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
            "presence_penalty": 0.8,
            "frequency_penalty": 0.65,
        }

        response = None
        for retry in range(self.max_retries):
            try:
                response = requests.post(
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
            except requests.exceptions.Timeout:
                if retry == self.max_retries - 1:
                    return "生成内容时出错: 请求超时，请检查网络连接"
                time.sleep(self.retry_delay * (2 ** retry))
            except requests.exceptions.ConnectionError:
                if retry == self.max_retries - 1:
                    return "生成内容时出错: 网络连接失败"
                time.sleep(self.retry_delay * (2 ** retry))
            except Exception as e:
                if retry == self.max_retries - 1:
                    return f"生成内容时出错: {str(e)}"
                time.sleep(self.retry_delay * (2 ** retry))

        if response is None:
            return "生成内容时出错: 未收到响应"

        if response.status_code == 200:
            try:
                result = response.json()
                return result['choices'][0]['message']['content']
            except (KeyError, IndexError) as e:
                return f"生成内容时出错: API响应格式错误 - {str(e)}"
        elif response.status_code == 401:
            return "API调用失败: 认证错误，请检查API Key"
        elif response.status_code == 429:
            return "API调用失败: 请求过于频繁，请稍后重试"
        elif response.status_code == 500:
            return "API调用失败: 服务器错误，请稍后重试"
        else:
            return f"API调用失败: {response.status_code}, {response.text}"

    def generate_content(self, prompt, system_prompt=None, genre_style="core"):
        if system_prompt is None:
            system_prompt = self.DEFAULT_SYSTEM_PROMPT

        humanization_prompt = self.humanizer.get_humanization_prompt(genre_style)
        enhanced_system_prompt = f"{humanization_prompt}\n\n{system_prompt}"

        content = self._call_api(enhanced_system_prompt, prompt)

        if content and not content.startswith("错误") and not content.startswith("API调用失败") and not content.startswith("生成内容时出错"):
            content = self.humanize_content(content)

        return content

    def generate_chapter(self, outline, detailed_outline="", requirements="", genre="都市情感", style="出版小说", tracking_info=""):
        ai_trace_rules = ""
        writing_core_from_helper = ""
        style_specific = ""
        genre_tips = ""
        humanization_system = ""
        deep_ai_system = ""

        if HAS_CHAPTER_PROMPT_HELPER:
            try:
                prompt_helper = create_prompt_helper(style, genre)
                ai_trace_rules = prompt_helper.get_ai_rules()
                writing_core_from_helper = prompt_helper.get_writing_core()
                style_specific = prompt_helper.get_style_prompt()
                genre_tips = prompt_helper.get_genre_tips()
                humanization_system = prompt_helper.get_humanization_prompt()
                deep_ai_system = get_deep_ai_trace_elimination_system()
            except Exception as e:
                print(f"章节生成提示词辅助模块加载失败: {e}")

        author_modeling = ""
        anti_ai_markers = ""
        if HAS_AUTHOR_MODELING:
            try:
                author_modeling = get_author_personality_modeling()
                anti_ai_markers = get_human_anti_ai_markers()
            except Exception as e:
                print(f"顶流作者人格建模辅助模块加载失败: {e}")

        dynamic_ai_prompt = ""
        if HAS_DYNAMIC_AI_HUMANIZER:
            try:
                dynamic_ai_prompt = create_dynamic_prompt("", genre="novel_fiction", use_ultimate=True)
            except Exception as e:
                print(f"动态AI痕迹消除系统加载失败: {e}")

        toolman_prompt = ""
        if HAS_TOOLMAN_DETECTOR:
            try:
                toolman_prompt = create_toolman_detection_prompt("new_chapter", compact=True)
            except Exception as e:
                print(f"工具人角色检测系统加载失败: {e}")

        genre_knowledge_prompt = self.genre_knowledge.get_genre_prompt(genre)

        system_prompt = f"""{self.DEFAULT_SYSTEM_PROMPT}

{self.WRITING_CORE}

{ai_trace_rules}

{writing_core_from_helper}

{style_specific}

{genre_tips}

{humanization_system}

{deep_ai_system}

{author_modeling}

{anti_ai_markers}

{dynamic_ai_prompt}

{toolman_prompt}

{genre_knowledge_prompt}

{self.humanizer.DENOISE_PROMPT}
"""

        user_prompt = f"""请根据以下信息创作章节内容：

**写作风格**：{style}
**题材类型**：{genre}

**章节大纲**：
{outline}

**详细细纲**：
{detailed_outline if detailed_outline else '无'}

**特殊要求**：
{requirements if requirements else '无'}

{f'**追踪信息**：{tracking_info}' if tracking_info else ''}

请创作完整的章节内容，确保：
1. 内容符合{style}风格和{genre}题材
2. 人物塑造立体，情节逻辑严谨
3. 语言自然流畅，无AI痕迹
4. 时间逻辑一致，无上帝视角
"""

        genre_style = self.get_genre_style(genre)
        content = self.generate_content(user_prompt, system_prompt, genre_style)
        return content

    def rewrite_content(self, original_text, style="出版小说", direction="文学润色", requirements="", genre="都市情感"):
        rewrite_directions = {
            "文学润色": "对原文进行文学性润色，提升文笔质量，消除AI痕迹",
            "风格转换": f"将原文转换为{style}风格",
            "细节增强": "增强原文的细节描写，让场景更加生动",
            "情感深化": "深化原文的情感表达，让情感更加真实动人",
            "节奏优化": "优化原文的叙事节奏，张弛有度",
            "语言精炼": "精炼原文的语言，去除冗余，保留精华",
        }

        direction_desc = rewrite_directions.get(direction, direction)

        system_prompt = f"""{self.DEFAULT_SYSTEM_PROMPT}

你是一位神级文字润色大师，拥有100年的文学创作和编辑经验。

{self.humanizer.DENOISE_PROMPT}

【润色方向】：{direction_desc}

【润色执行标准】：
1. 句式结构优化：消除过于工整的段落结构
2. 词汇选择优化：替换AI高频词汇
3. 逻辑衔接优化：删除过于直白的因果解释
4. 人文表达注入：增加生活化细节
5. 叙事节奏调整：避免每段都遵循相同模式

【润色禁忌】：
- 禁止改变原文的核心情节和人物设定
- 禁止过度修饰导致文字失去自然感
- 禁止使用"他感到"、"她心想"等直白心理描写
"""

        user_prompt = f"""请对以下内容进行{direction}：

**原文**：
{original_text}

**改写风格**：{style}
**题材**：{genre}
**自定义要求**：{requirements if requirements else '无'}

请输出润色后的完整内容，确保：
1. 保留原文核心情节和精神
2. 完全消除AI痕迹
3. 语言自然流畅
4. 符合{style}风格
"""

        genre_style = self.get_genre_style(genre)
        content = self.generate_content(user_prompt, system_prompt, genre_style)
        return content

    def continue_content(self, existing_content, outline="", requirements="", genre="都市情感", style="出版小说"):
        system_prompt = f"""{self.DEFAULT_SYSTEM_PROMPT}

{self.WRITING_CORE}

{self.humanizer.DENOISE_PROMPT}

你是一位顶级小说续写大师，擅长在已有内容的基础上自然延伸故事。

【续写核心原则】：
1. 风格一致：续写内容必须与原文风格完全一致
2. 逻辑连贯：续写内容必须与原文情节逻辑连贯
3. 人物一致：人物性格、说话方式必须与原文一致
4. 自然过渡：续写内容与原文之间要自然过渡
5. 无上帝视角：严格遵守信息获取合理性原则
"""

        user_prompt = f"""请根据以下已有内容进行续写：

**已有内容**：
{existing_content}

**大纲（可选）**：
{outline if outline else '无'}

**续写风格**：{style}
**题材**：{genre}
**特殊要求**：{requirements if requirements else '无'}

请续写章节内容，确保：
1. 与原文风格和语气完全一致
2. 情节自然延续，不突兀
3. 人物行为符合已有设定
4. 时间逻辑连贯
5. 无AI痕迹
"""

        genre_style = self.get_genre_style(genre)
        content = self.generate_content(user_prompt, system_prompt, genre_style)
        return content

    def generate_names(self, gender, country, surname_count, surname="", given_name="", requirements=""):
        if not self.api_key:
            return "错误：API Key未设置"

        name_gen_system = """你是一个名字生成器。根据用户要求生成名字列表。
【绝对规则】
1. 每行只输出一个名字，不要任何其他内容
2. 不要添加编号、标点、注释、说明
3. 名字必须是纯中文"""

        user_prompt = f"""生成名字：
性别：{gender}
文化：{country}
姓氏：{surname if surname else '随机'}
名字：{given_name if given_name else '随机'}
要求：{requirements if requirements else '无'}

直接输出名字，每行一个。"""

        return self._call_api(name_gen_system, user_prompt, temperature=0.8, max_tokens=4000)

    def generate_polished_content(self, prompt, system_prompt=None, genre_style="core"):
        deep_ai_system = ""
        ai_trace_rules = ""
        if HAS_CHAPTER_PROMPT_HELPER:
            try:
                deep_ai_system = get_deep_ai_trace_elimination_system()
                ai_trace_rules = get_ai_trace_elimination_rules()
            except Exception:
                pass

        enhanced_polish_system = f"""你是一位神级文字润色大师。

{deep_ai_system}

{ai_trace_rules}

【润色核心使命】
1. 语言精美绝伦
2. 情感表达深刻细腻
3. 细节描写栩栩如生
4. 完全保留原文核心价值

【润色禁忌】
- 禁止改变原文核心情节
- 禁止过度修饰
- 禁止使用直白心理描写
"""

        humanization_prompt = self.humanizer.get_humanization_prompt(genre_style)
        final_system = f"{humanization_prompt}\n\n{enhanced_polish_system}"
        if system_prompt:
            final_system = f"{final_system}\n\n【额外要求】\n{system_prompt}"

        content = self._call_api(final_system, prompt, temperature=0.65, max_tokens=10000)

        if content and not content.startswith("错误") and not content.startswith("API调用失败") and not content.startswith("生成内容时出错"):
            content = self.humanize_content(content)

        return content


def get_module_status():
    return {
        "动态AI痕迹消除系统": HAS_DYNAMIC_AI_HUMANIZER,
        "终极AI痕迹消除系统": HAS_ULTIMATE_AI_HUMANIZER,
        "章节生成提示词辅助模块": HAS_CHAPTER_PROMPT_HELPER,
        "顶流作者人格建模辅助模块": HAS_AUTHOR_MODELING,
        "工具人角色检测系统": HAS_TOOLMAN_DETECTOR,
        "scikit-learn": HAS_SKLEARN,
        "requests": HAS_REQUESTS,
    }
