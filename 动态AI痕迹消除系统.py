# -*- coding: utf-8 -*-
"""
动态AI痕迹消除提示词系统
根据文本的题材特征和写作风格进行智能识别，动态生成针对性的人性化处理提示词
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import random


class GenreType(Enum):
    """题材类型枚举"""
    ACADEMIC_PAPER = "academic_paper"           # 学术论文
    CREATIVE_WRITING = "creative_writing"       # 创意写作
    NEWS_REPORT = "news_report"                 # 新闻报道
    BUSINESS_DOC = "business_document"          # 商业文案
    TECHNICAL_DOC = "technical_document"        # 技术文档
    SOCIAL_MEDIA = "social_media"               # 社交媒体
    NOVEL_FICTION = "novel_fiction"             # 小说虚构
    BIOGRAPHY = "biography"                     # 传记文学
    ESSAY = "essay"                             # 散文随笔
    ADVERTISING = "advertising"                 # 广告文案


class WritingStyle(Enum):
    """写作风格枚举"""
    FORMAL = "formal"                           # 正式
    COLLOQUIAL = "colloquial"                   # 口语化
    HUMOROUS = "humorous"                       # 幽默
    SERIOUS = "serious"                         # 严肃
    LYRICAL = "lyrical"                         # 抒情
    EPIC = "epic"                               # 史诗大气
    INTIMATE = "intimate"                       # 亲密温馨
    MYSTERIOUS = "mysterious"                   # 悬疑神秘
    ROMANTIC = "romantic"                       # 浪漫
    IRONIC = "ironic"                           # 讽刺


@dataclass
class StyleParameters:
    """风格参数配置"""
    formality_level: float = 0.5                # 正式程度 0-1
    emotional_level: float = 0.5                # 情感程度 0-1
    detail_level: float = 0.5                   # 细节程度 0-1
    rhythm_variation: float = 0.5               # 节奏变化 0-1
    metaphor_density: float = 0.5               # 比喻密度 0-1
    dialogue_ratio: float = 0.3                 # 对话比例 0-1
    introspection_depth: float = 0.5             # 内心独白深度 0-1
    
    # 词汇参数
    vocabulary_complexity: float = 0.5          # 词汇复杂度 0-1
    sentence_length_variation: float = 0.5       # 句长变化 0-1
    
    def to_dict(self) -> Dict:
        return {
            "formality_level": self.formality_level,
            "emotional_level": self.emotional_level,
            "detail_level": self.detail_level,
            "rhythm_variation": self.rhythm_variation,
            "metaphor_density": self.metaphor_density,
            "dialogue_ratio": self.dialogue_ratio,
            "introspection_depth": self.introspection_depth,
            "vocabulary_complexity": self.vocabulary_complexity,
            "sentence_length_variation": self.sentence_length_variation
        }


@dataclass
class GenreCharacteristics:
    """题材特征配置"""
    name: str
    typical_patterns: List[str]
    vocabulary_preferences: Dict[str, List[str]]
    sentence_structure_preferences: List[str]
    tone_requirements: List[str]
    forbidden_patterns: List[str]
    recommended_elements: List[str]
    pacing_requirements: str
    perspective_options: List[str]
    
    # 特定题材的AI痕迹特征
    ai_signature_patterns: List[str] = field(default_factory=list)
    human_equivalent_patterns: List[str] = field(default_factory=list)


class GenreRecognizer:
    """题材识别器"""
    
    GENRE_PATTERNS = {
        GenreType.ACADEMIC_PAPER: {
            "indicators": [
                r"研究表明|实验结果|数据表明|统计分析|假设检验|文献综述",
                r"本文旨在|本文首先|综上所述|因此可以得出",
                r"参考文献|引用|标注|理论框架|研究方法"
            ],
            "vocabulary": ["论证", "分析", "假设", "验证", "结论", "方法论", "实证"],
            "structure": ["引言", "文献综述", "研究方法", "结果讨论", "结论"]
        },
        GenreType.CREATIVE_WRITING: {
            "indicators": [
                r"描写|刻画|展现|呈现|仿佛|如同|犹如",
                r"心理活动|内心世界|情感变化|细微之处|氛围营造"
            ],
            "vocabulary": ["意境", "渲染", "隐喻", "象征", "意象", "氛围"],
            "structure": ["起承转合", "情感递进", "场景转换"]
        },
        GenreType.NEWS_REPORT: {
            "indicators": [
                r"记者|报道|采访|据悉|据了解|官方表示",
                r"时间|地点|人物|事件|原因|影响",
                r"最新消息|今日|昨日|目前|据悉"
            ],
            "vocabulary": ["获悉", "据了解", "指出", "表示", "称"],
            "structure": ["标题", "导语", "正文", "背景", "引语"]
        },
        GenreType.BUSINESS_DOC: {
            "indicators": [
                r"方案|计划|目标|执行|优化|提升|效益",
                r"战略|部署|规划|愿景|使命|核心价值",
                r"方案概述|执行步骤|预期效果"
            ],
            "vocabulary": ["战略", "部署", "优化", "效益", "KPI", "转化率"],
            "structure": ["背景", "目标", "执行方案", "预期效果"]
        },
        GenreType.TECHNICAL_DOC: {
            "indicators": [
                r"系统架构|模块设计|接口定义|数据流|算法实现",
                r"技术栈|开发环境|部署方案|性能优化",
                r"技术文档|接口说明|开发指南"
            ],
            "vocabulary": ["模块", "接口", "架构", "实现", "调用", "依赖"],
            "structure": ["概述", "详细设计", "接口说明", "使用示例"]
        },
        GenreType.SOCIAL_MEDIA: {
            "indicators": [
                r"#.+#|转发|点赞|评论|分享|热门",
                r"强烈推荐|绝了|太可了|姐妹们|兄弟们",
                r"安利|种草|拔草|打 call|破防"
            ],
            "vocabulary": ["绝绝子", "安利", "打 call", "种草", "破防"],
            "structure": ["开头吸引", "核心内容", "互动引导"]
        },
        GenreType.NOVEL_FICTION: {
            "indicators": [
                r"章节|场景|对话|内心独白|环境描写|人物刻画",
                r"情节发展|冲突|高潮|结局|转折",
                r"视角转换|时间线|叙事节奏"
            ],
            "vocabulary": ["说道", "心想", "看着", "听见", "感觉到"],
            "structure": ["开端", "发展", "高潮", "结局"]
        },
        GenreType.BIOGRAPHY: {
            "indicators": [
                r"生平|事迹|成长经历|人生轨迹|重要成就",
                r"出生于|毕业于|曾任|代表作|人生哲学",
                r"人物背景|关键事件|历史意义"
            ],
            "vocabulary": ["出身", "早年", "成年", "代表作", "成就"],
            "structure": ["早年经历", "重要事件", "人生成就", "历史影响"]
        },
        GenreType.ESSAY: {
            "indicators": [
                r"感悟|随想|杂谈|心得|札记",
                r"人生|思考|感悟|哲理|生活",
                r"由感而发|深思|细细品味"
            ],
            "vocabulary": ["感悟", "哲理", "深思", "体悟", "品味"],
            "structure": ["引入", "展开", "升华", "收尾"]
        },
        GenreType.ADVERTISING: {
            "indicators": [
                r"限时|限量|独家|首发|特惠",
                r"品质保证|源头直供|厂家直销|爆款",
                r"抢购|秒杀|福利|惊喜"
            ],
            "vocabulary": ["尊享", "臻品", "匠心", "品质", "首选"],
            "structure": ["痛点切入", "产品介绍", "促销信息", "行动号召"]
        }
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译所有正则表达式"""
        self._compiled_patterns = {}
        for genre, data in self.GENRE_PATTERNS.items():
            patterns = []
            for indicator in data.get("indicators", []):
                patterns.append(re.compile(indicator, re.IGNORECASE))
            self._compiled_patterns[genre] = patterns
    
    def recognize(self, text: str) -> Tuple[GenreType, float]:
        """
        识别文本的题材类型
        :param text: 待识别的文本
        :return: (识别出的题材类型, 置信度 0-1)
        """
        scores = {}
        text_lower = text.lower()
        
        for genre, patterns in self._compiled_patterns.items():
            score = 0
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                score += len(matches) * 0.1  # 每个匹配加0.1分
            
            # 根据题材类型调整权重
            genre_weights = {
                GenreType.SOCIAL_MEDIA: 1.5,      # 社交媒体特征更明显
                GenreType.NEWS_REPORT: 1.3,        # 新闻报道特征明显
                GenreType.NOVEL_FICTION: 1.2,      # 小说特征明显
                GenreType.ACADEMIC_PAPER: 1.4,     # 学术论文特征明显
                GenreType.TECHNICAL_DOC: 1.3,      # 技术文档特征明显
                GenreType.ADVERTISING: 1.3,        # 广告文案特征明显
            }
            weight = genre_weights.get(genre, 1.0)
            scores[genre] = min(score * weight, 1.0)  # 最高1分
        
        # 如果所有分数都很低，默认为创意写作
        max_score = max(scores.values()) if scores else 0
        if max_score < 0.1:
            return GenreType.CREATIVE_WRITING, 0.3
        
        best_genre = max(scores, key=scores.get)
        confidence = min(scores[best_genre] * 2, 1.0)  # 放大分数，更严格
        
        return best_genre, confidence
    
    def extract_genre_features(self, text: str) -> Dict:
        """提取题材特征"""
        genre, confidence = self.recognize(text)
        genre_data = self.GENRE_PATTERNS[genre]
        
        return {
            "genre": genre,
            "genre_name": genre.value,
            "confidence": confidence,
            "detected_patterns": self._find_all_patterns(text),
            "vocabulary_hints": self._extract_vocabulary_hints(text, genre_data),
            "structure_hints": self._analyze_structure_hints(text)
        }
    
    def _find_all_patterns(self, text: str) -> List[Dict]:
        """找出所有匹配的题材特征"""
        results = []
        text_lower = text.lower()
        
        for genre, patterns in self._compiled_patterns.items():
            matched = []
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    matched.extend(matches[:5])  # 最多5个
            
            if matched:
                results.append({
                    "genre": genre.value,
                    "matches": list(set(matched))[:10]
                })
        
        return results
    
    def _extract_vocabulary_hints(self, text: str, genre_data: Dict) -> Dict:
        """提取词汇提示"""
        text_lower = text.lower()
        found_vocab = []
        
        for word in genre_data.get("vocabulary", []):
            if word.lower() in text_lower:
                found_vocab.append(word)
        
        return {
            "expected_vocabulary": genre_data.get("vocabulary", []),
            "found_vocabulary": found_vocab,
            "coverage": len(found_vocab) / len(genre_data.get("vocabulary", [])) if genre_data.get("vocabulary") else 0
        }
    
    def _analyze_structure_hints(self, text: str) -> Dict:
        """分析结构提示"""
        paragraphs = text.split('\n\n')
        
        return {
            "paragraph_count": len([p for p in paragraphs if p.strip()]),
            "avg_paragraph_length": sum(len(p) for p in paragraphs) / max(len(paragraphs), 1),
            "has_dialogue": '"' in text or '"' in text or '「' in text or '」' in text,
            "has_numbers": bool(re.search(r'\d+', text)),
            "has_quotes": bool(re.search(r'['""''""']', text))
        }


class StyleAnalyzer:
    """写作风格分析器"""
    
    STYLE_INDICATORS = {
        WritingStyle.FORMAL: {
            "vocabulary": ["因此", "然而", "综上所述", "必须指出", "显而易见", "理应", "应当"],
            "structures": ["复杂长句", "被动语态", "从句结构"],
            "patterns": [r"理应", r"应当", r"显而易见", r"综上所述"]
        },
        WritingStyle.COLLOQUIAL: {
            "vocabulary": ["呗", "啦", "呀", "呢", "哈", "嘿", "诶", "哇"],
            "structures": ["短句", "省略句", "口语化表达"],
            "patterns": [r"呗", r"啦", r"呀", r"呢"]
        },
        WritingStyle.HUMOROUS: {
            "vocabulary": ["哈哈", "嘻嘻", "笑死", "绝了", "服了", "666", "笑喷"],
            "structures": ["夸张", "反讽", "双关", "比喻"],
            "patterns": [r"哈哈", r"笑死", r"绝了", r"服了"]
        },
        WritingStyle.SERIOUS: {
            "vocabulary": ["严肃", "认真", "重视", "关注", "深思", "警醒", "反思"],
            "structures": ["陈述句", "强调句", "递进结构"],
            "patterns": [r"严肃", r"深思", r"警醒", r"反思"]
        },
        WritingStyle.LYRICAL: {
            "vocabulary": ["如梦如幻", "轻柔", "温柔", "悸动", "细腻", "柔情", "缠绵"],
            "structures": ["抒情句", "排比", "反复", "意象堆叠"],
            "patterns": [r"如.*如.*", r"轻柔", r"悸动"]
        },
        WritingStyle.EPIC: {
            "vocabulary": ["壮阔", "磅礴", "浩瀚", "辉煌", "宏伟", "雄伟", "震撼"],
            "structures": ["长句铺陈", "排比", "对仗", "史诗感"],
            "patterns": [r"壮阔", r"磅礴", r"浩瀚", r"辉煌"]
        },
        WritingStyle.INTIMATE: {
            "vocabulary": ["温暖", "亲切", "温柔", "贴心", "窝心", "暖心"],
            "structures": ["对话式", "感叹句", "昵称"],
            "patterns": [r"温暖", r"亲切", r"贴心"]
        },
        WritingStyle.MYSTERIOUS: {
            "vocabulary": ["神秘", "诡异", "幽暗", "隐隐", "诡谲", "玄妙"],
            "structures": ["悬念", "留白", "暗示", "意象"],
            "patterns": [r"神秘", r"诡异", r"隐隐"]
        },
        WritingStyle.ROMANTIC: {
            "vocabulary": ["浪漫", "甜蜜", "柔情", "心动", "缠绵", "温馨"],
            "structures": ["比喻", "拟人", "感叹", "对话"],
            "patterns": [r"浪漫", r"甜蜜", r"心动"]
        },
        WritingStyle.IRONIC: {
            "vocabulary": ["讽刺", "嘲笑", "挖苦", "调侃", "嘲弄"],
            "structures": ["反讽", "暗讽", "夸张", "对比"],
            "patterns": [r"讽刺", r"挖苦", r"嘲弄"]
        }
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self._compiled = {}
        for style, data in self.STYLE_INDICATORS.items():
            patterns = []
            for pattern in data.get("patterns", []):
                try:
                    patterns.append(re.compile(pattern))
                except:
                    patterns.append(re.compile(re.escape(pattern)))
            self._compiled[style] = {
                "patterns": patterns,
                "vocabulary": data.get("vocabulary", []),
                "structures": data.get("structures", [])
            }
    
    def analyze(self, text: str) -> Dict:
        """
        分析文本的写作风格
        :param text: 待分析的文本
        :return: 风格分析结果
        """
        scores = {}
        text_lower = text.lower()
        
        for style, data in self._compiled.items():
            score = 0
            
            # 词汇匹配
            for vocab in data["vocabulary"]:
                if vocab.lower() in text_lower:
                    score += 0.15
            
            # 模式匹配
            for pattern in data["patterns"]:
                matches = pattern.findall(text_lower)
                score += len(matches) * 0.1
            
            scores[style] = min(score, 1.0)
        
        # 计算特征参数
        params = self._calculate_parameters(text, scores)
        
        # 找出主导风格
        sorted_styles = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "primary_style": sorted_styles[0][0] if sorted_styles[0][1] > 0.1 else WritingStyle.FORMAL,
            "secondary_styles": [s[0] for s in sorted_styles[1:3] if s[1] > 0.05],
            "style_scores": {s.value: round(scores.get(s, 0), 3) for s in WritingStyle},
            "parameters": params,
            "style_mix_recommendation": self._recommend_style_mix(sorted_styles)
        }
    
    def _calculate_parameters(self, text: str, style_scores: Dict) -> StyleParameters:
        """根据分析结果计算风格参数"""
        
        # 计算句子长度变化
        sentences = re.split(r'[。！？]', text)
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        avg_length = sum(sentence_lengths) / max(len(sentence_lengths), 1)
        length_variation = self._calculate_variation(sentence_lengths)
        
        # 计算词汇复杂度
        words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        unique_ratio = len(set(words)) / max(len(words), 1) if words else 0.5
        
        # 检测情感词汇密度
        emotional_words = ["爱", "恨", "喜", "怒", "哀", "乐", "悲", "痛", "快乐", "悲伤", "愤怒", "欣喜"]
        emotional_count = sum(1 for w in emotional_words if w in text)
        emotional_density = min(emotional_count / max(len(text) // 100, 1), 1.0)
        
        # 检测对话比例
        dialogue_markers = ['"', '"', '「', '」', '【', '】', '——']
        dialogue_count = sum(text.count(m) for m in dialogue_markers)
        dialogue_ratio = min(dialogue_count / max(len(text) // 50, 1), 1.0)
        
        # 检测被动语态使用
        passive_count = len(re.findall(r'被.+|受到.+|予以.+', text))
        formal_level = min(passive_count / max(len(sentences) // 5, 1) + 0.3, 1.0)
        
        return StyleParameters(
            formality_level=formal_level,
            emotional_level=emotional_density,
            detail_level=min(unique_ratio * 1.2, 1.0),
            rhythm_variation=length_variation,
            metaphor_density=0.5,  # 默认
            dialogue_ratio=dialogue_ratio,
            introspection_depth=0.5,  # 默认
            vocabulary_complexity=min(unique_ratio * 1.5, 1.0),
            sentence_length_variation=length_variation
        )
    
    def _calculate_variation(self, values: List[float]) -> float:
        """计算变化程度"""
        if len(values) <= 1:
            return 0.5
        
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.5
        
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5
        
        # 归一化到 0-1
        cv = std_dev / mean  # 变异系数
        return min(cv / 2, 1.0)  # 假设 cv 最大为 2
    
    def _recommend_style_mix(self, sorted_styles: List[Tuple[WritingStyle, float]]) -> Dict:
        """推荐风格混合"""
        if not sorted_styles or sorted_styles[0][1] < 0.1:
            return {"primary": "formal", "ratio": 1.0}
        
        primary = sorted_styles[0][0]
        total = sum(s[1] for s in sorted_styles[:3]) if sorted_styles else 1.0
        
        return {
            "primary": primary.value,
            "ratio": sorted_styles[0][1] / max(total, 0.1),
            "mixes": [
                {"style": s[0].value, "weight": round(s[1] / max(total, 0.1), 2)}
                for s in sorted_styles[:3] if s[1] > 0.05
            ]
        }


class DynamicPromptGenerator:
    """动态提示词生成器"""
    
    # 题材特征配置
    GENRE_CONFIGS = {
        GenreType.ACADEMIC_PAPER: GenreCharacteristics(
            name="学术论文",
            typical_patterns=["引言", "文献综述", "研究方法", "数据分析", "结论"],
            vocabulary_preferences={
                "academic": ["研究表明", "实验数据", "统计分析", "假设验证"],
                "替代表达": ["通过研究发现", "实验显示", "数据表明", "验证了假设"]
            },
            sentence_structure_preferences=[
                "使用被动语态减少主观色彩",
                "从句结构体现逻辑严谨",
                "专业术语使用准确"
            ],
            tone_requirements=[
                "客观中立，避免主观臆断",
                "严谨准确，措辞精确",
                "逻辑清晰，论证充分"
            ],
            forbidden_patterns=[
                "我认为|我觉得|显而易见的是",
                "大量数据表明（无具体引用）",
                "绝对|肯定|必然（过于绝对）"
            ],
            recommended_elements=[
                "具体数据引用",
                "研究方法说明",
                "理论框架支撑"
            ],
            pacing_requirements="节奏平稳，层层递进",
            perspective_options=["第一人称（we）", "第三人称"],
            ai_signature_patterns=[
                "首先|其次|最后|综上所述",
                "不言而喻|显而易见",
                "有待进一步研究"
            ],
            human_equivalent_patterns=[
                "第一|第二|第三|（直接列出）",
                "这很明显",
                "未来可深入探讨"
            ]
        ),
        GenreType.NOVEL_FICTION: GenreCharacteristics(
            name="小说虚构",
            typical_patterns=["场景描写", "人物对话", "内心独白", "情节推进"],
            vocabulary_preferences={
                "literary": ["眼眸", "颔首", "神色", "旋即"],
                "替代表达": ["眼睛", "点了点头", "脸色", "很快"]
            },
            sentence_structure_preferences=[
                "长短句交替，节奏感强",
                "对话自然，口语化",
                "心理描写细腻但不直白"
            ],
            tone_requirements=[
                "符合人物身份和性格",
                "场景氛围协调一致",
                "情感表达含蓄内敛"
            ],
            forbidden_patterns=[
                "他/她心想（直白内心独白）",
                "大量环境描写堆砌",
                "人物出场标签化介绍"
            ],
            recommended_elements=[
                "细节暗示而非直说",
                "动作展现而非心理陈述",
                "对话推进情节"
            ],
            pacing_requirements="张弛有度，悬念迭起",
            perspective_options=["第三人称限知", "第一人称", "全知视角"],
            ai_signature_patterns=[
                "只见|就在这时|随即",
                "不由得|下意识",
                "心中一凛|嘴角勾起"
            ],
            human_equivalent_patterns=[
                "他看着|忽然",
                "一下|顺手",
                "心里|笑了笑"
            ]
        ),
        GenreType.NEWS_REPORT: GenreCharacteristics(
            name="新闻报道",
            typical_patterns=["倒金字塔结构", "5W1H要素", "引语使用"],
            vocabulary_preferences={
                "journalistic": ["据悉|据了解|官方表示"],
                "替代表达": ["有消息称|从知情人士处了解到|对方称"]
            },
            sentence_structure_preferences=[
                "短句为主，信息密集",
                "导语概括核心信息",
                "引语标注出处"
            ],
            tone_requirements=[
                "客观中立，不带主观色彩",
                "用事实说话，让读者判断",
                "平衡报道，兼顾多方声音"
            ],
            forbidden_patterns=[
                "大量使用形容词修饰",
                "评论性语言代替事实陈述",
                "来源不明或模糊"
            ],
            recommended_elements=[
                "具体时间地点人物",
                "权威数据来源",
                "当事人直接引语"
            ],
            pacing_requirements="先详后略，快速切入重点",
            perspective_options=["第三人称", "记者视角"],
            ai_signature_patterns=[
                "值得注意的是|无独有偶",
                "业内分析认为|普遍认为"
            ],
            human_equivalent_patterns=[
                "需要注意的是|（直接陈述）",
                "有分析说|（引用具体来源）"
            ]
        ),
        GenreType.CREATIVE_WRITING: GenreCharacteristics(
            name="创意写作",
            typical_patterns=["意象运用", "情感渲染", "意境营造"],
            vocabulary_preferences={
                "poetic": ["仿佛|如同|犹如|恰似"],
                "替代表达": ["像|好像|（直接描述）"]
            },
            sentence_structure_preferences=[
                "长短句灵活组合",
                "修辞手法恰当运用",
                "留白与暗示并重"
            ],
            tone_requirements=[
                "情感真挚，不矫揉造作",
                "意在言外，含蓄蕴藉",
                "风格统一，全篇协调"
            ],
            forbidden_patterns=[
                "过度修饰，堆砌辞藻",
                "情感直白喊口号",
                "意象之间缺乏关联"
            ],
            recommended_elements=[
                "具体可感的细节",
                "独特视角的观察",
                "真实细腻的情感"
            ],
            pacing_requirements="动静结合，疏密有致",
            perspective_options=["第一人称", "第三人称", "第二人称"],
            ai_signature_patterns=[
                "轻轻拂过|缓缓流淌",
                "那一瞬间|那一刻",
                "心中涌起|内心深处"
            ],
            human_equivalent_patterns=[
                "风吹过|（简单描述）",
                "那一下|（口语化）",
                "感到|（直接感受）"
            ]
        ),
        GenreType.SOCIAL_MEDIA: GenreCharacteristics(
            name="社交媒体",
            typical_patterns=["话题标签", "互动引导", "情绪表达"],
            vocabulary_preferences={
                "informal": ["绝绝子|打 call|种草"],
                "替代表达": ["太棒了|推荐|分享"]
            },
            sentence_structure_preferences=[
                "短小精悍，易于阅读",
                "口语化表达，亲切自然",
                "适当使用表情符号"
            ],
            tone_requirements=[
                "轻松活泼，有互动感",
                "真诚分享，不端着",
                "有个人态度，但不偏激"
            ],
            forbidden_patterns=[
                "过于正式生硬",
                "长篇大论无人看",
                "过度营销感"
            ],
            recommended_elements=[
                "真实使用体验",
                "个人真实感受",
                "有价值的信息点"
            ],
            pacing_requirements="开头抓人，结尾留互动",
            perspective_options=["第一人称", "朋友视角"],
            ai_signature_patterns=[
                "姐妹们|兄弟们|集美们",
                "真的绝了|太可了",
                "给我冲|盘它"
            ],
            human_equivalent_patterns=[
                "朋友|（直接称呼）",
                "特别棒|（真诚表达）",
                "推荐|（简洁推荐）"
            ]
        ),
        GenreType.BUSINESS_DOC: GenreCharacteristics(
            name="商业文案",
            typical_patterns=["痛点分析", "解决方案", "价值主张", "行动号召"],
            vocabulary_preferences={
                "business": ["赋能|抓手|闭环|打法"],
                "替代表达": ["帮助|方法|系统|策略"]
            },
            sentence_structure_preferences=[
                "逻辑清晰，层次分明",
                "数据支撑，案例佐证",
                "结论先行，细节支撑"
            ],
            tone_requirements=[
                "专业但不晦涩",
                "自信但不浮夸",
                "务实但有感染力"
            ],
            forbidden_patterns=[
                "空洞的口号和套话",
                "过度承诺无法兑现",
                "专业术语堆砌故弄玄虚"
            ],
            recommended_elements=[
                "具体案例和数据",
                "清晰的利益点",
                "可执行的建议"
            ],
            pacing_requirements="快节奏，强逻辑",
            perspective_options=["第二人称（您）", "第一人称（我们）"],
            ai_signature_patterns=[
                "全方位|立体化|多维度",
                "赋能|抓手|组合拳",
                "打造|构建|落地"
            ],
            human_equivalent_patterns=[
                "全面|（具体说明）",
                "帮助|（具体说明）",
                "做|（具体动作）"
            ]
        )
    }
    
    def __init__(self):
        self.genre_recognizer = GenreRecognizer()
        self.style_analyzer = StyleAnalyzer()
    
    def generate_prompts(self, text: str, target_genre: Optional[GenreType] = None) -> Dict:
        """
        动态生成AI痕迹消除提示词
        :param text: 待处理的文本
        :param target_genre: 目标题材（如果为None则自动识别）
        :return: 动态生成的提示词字典
        """
        # 1. 识别题材
        if target_genre is None:
            genre, confidence = self.genre_recognizer.recognize(text)
        else:
            genre = target_genre
            confidence = 1.0
        
        # 2. 分析风格
        style_analysis = self.style_analyzer.analyze(text)
        
        # 3. 获取题材配置
        genre_config = self.GENRE_CONFIGS.get(genre, self.GENRE_CONFIGS[GenreType.CREATIVE_WRITING])
        
        # 4. 生成核心指令
        core_instructions = self._generate_core_instructions(genre, genre_config, style_analysis)
        
        # 5. 生成词汇替换规则
        vocabulary_rules = self._generate_vocabulary_rules(genre, style_analysis)
        
        # 6. 生成句式指导
        sentence_guidance = self._generate_sentence_guidance(genre, style_analysis)
        
        # 7. 生成语气控制参数
        tone_control = self._generate_tone_control(genre, style_analysis)
        
        # 8. 生成风格保留策略
        style_preservation = self._generate_style_preservation(genre, style_analysis)
        
        # 9. 生成正确示范
        correct_examples = self._generate_correct_examples(genre, style_analysis)
        
        # 10. 生成禁止项
        forbidden_items = self._generate_forbidden_items(genre, style_analysis)
        
        return {
            "genre_recognition": {
                "detected_genre": genre.value,
                "genre_name": genre_config.name,
                "confidence": confidence,
                "primary_style": style_analysis["primary_style"].value,
                "style_parameters": style_analysis["parameters"].to_dict()
            },
            "core_instructions": core_instructions,
            "vocabulary_replacement_rules": vocabulary_rules,
            "sentence_structure_guidance": sentence_guidance,
            "tone_control_parameters": tone_control,
            "style_preservation_strategy": style_preservation,
            "positive_examples": correct_examples,
            "forbidden_patterns": forbidden_items,
            "complete_prompt": self._assemble_complete_prompt(
                genre, genre_config, style_analysis,
                core_instructions, vocabulary_rules, sentence_guidance,
                tone_control, style_preservation, correct_examples, forbidden_items
            )
        }
    
    def _generate_core_instructions(self, genre: GenreType, config: GenreCharacteristics, style_analysis: Dict) -> List[str]:
        """生成核心指令"""
        instructions = [
            f"作为资深的{config.name}作者，你需要消除文本中的AI生成痕迹。",
            "",
            "【重要原则】AI痕迹 ≠ 高级词汇/长句/成语",
            "人类写作是多样化的：长句、成语、优美描写都是人类写作的一部分。",
            "真正的AI痕迹是：模式化、重复、过度完美、缺乏变化。",
            ""
        ]
        
        if genre == GenreType.NOVEL_FICTION:
            instructions.extend([
                "【小说写作核心原则】",
                "1. 段落结构要多样化：有的以对话开头，有的以动作开头，有的以环境开头",
                "2. 词汇选择要符合人物：文人说文雅话，武夫说粗话，孩子说简单话",
                "3. 句式长短要匹配内容：紧张时用短句，舒缓时可以用长句",
                "4. 心理描写要自然：可以融入叙事，不必单独成段",
                "5. 过渡方式要变化：有时直接切入，有时铺垫过渡"
            ])
        elif genre == GenreType.ACADEMIC_PAPER:
            instructions.extend([
                "【学术写作核心原则】",
                "1. 保持客观性：用数据和论证说话，避免主观臆断",
                "2. 结构可以变化：不必每次都是'首先-其次-最后'",
                "3. 表达要精准：去掉空洞的修饰词，直接陈述",
                "4. 逻辑要清晰：但不要过度解释读者已知的内容"
            ])
        elif genre == GenreType.NEWS_REPORT:
            instructions.extend([
                "【新闻写作核心原则】",
                "1. 用事实说话：让信息本身具有说服力",
                "2. 平衡报道：兼顾多方声音",
                "3. 具体细节比抽象概括更有价值",
                "4. 引语要注明出处"
            ])
        elif genre == GenreType.SOCIAL_MEDIA:
            instructions.extend([
                "【社交媒体核心原则】",
                "1. 像朋友聊天一样自然表达",
                "2. 真实体验比夸张形容词更可信",
                "3. 保持个人特色和真实态度",
                "4. 开头抓人，结尾留互动"
            ])
        elif genre == GenreType.BUSINESS_DOC:
            instructions.extend([
                "【商业文案核心原则】",
                "1. 用具体案例和数据支撑观点",
                "2. 逻辑清晰但表达简洁",
                "3. 自信但不浮夸，可信但不晦涩",
                "4. 避免空洞的套话"
            ])
        else:
            instructions.extend([
                "【通用写作原则】",
                "1. 保持人类写作的自然流畅感",
                "2. 用具体细节替代抽象概括",
                "3. 让表达有温度和个性",
                "4. 句式多样化，服务于内容"
            ])
        
        primary_style = style_analysis["primary_style"]
        if primary_style == WritingStyle.FORMAL:
            instructions.append("保持适当的正式程度，但避免过度生硬。")
        elif primary_style == WritingStyle.COLLOQUIAL:
            instructions.append("使用自然的口语化表达，但不要过于随意。")
        elif primary_style == WritingStyle.LYRICAL:
            instructions.append("可以保持抒情风格，但避免过度修饰。")
        elif primary_style == WritingStyle.EPIC:
            instructions.append("可以保持宏大叙事，但避免空洞。")
        
        return instructions
    
    def _generate_vocabulary_rules(self, genre: GenreType, style_analysis: Dict) -> Dict:
        """生成词汇处理规则 - 基于模式识别而非简单禁用"""
        base_rules = {
            "important_note": """
【重要说明】词汇本身没有AI痕迹，关键在于使用模式！

以下词汇人类作家也会使用：
- "眼眸" - 人类作家在文学描写中经常使用
- "颔首" - 正式场合或古风题材中很常见
- "旋即" - 叙事中表示时间紧凑的常用词
- "嘴角勾起" - 描写微笑的常见表达

真正的AI痕迹是：
1. 同一词汇在短距离内反复出现
2. 多个"高级词汇"密集堆砌
3. 词汇与语境、人物身份不匹配
4. 所有描写都用"高级词汇"，缺少日常表达的变化
""",
            "pattern_based_rules": [
                {
                    "pattern": "词汇密集堆砌",
                    "description": "一句话中出现多个'高级词汇'，如'眼眸中闪过一丝不易察觉的精光，嘴角勾起一抹意味深长的弧度'",
                    "problem": "堆砌感强，不像自然表达",
                    "solution": "分散使用，或用简单表达替代部分高级词汇"
                },
                {
                    "pattern": "同一词汇短距离重复",
                    "description": "相邻段落中多次出现'眼眸'、'颔首'等词",
                    "problem": "重复感明显",
                    "solution": "使用同义替换或省略，如'眼睛'、'目光'、'点了点头'、'应了一声'"
                },
                {
                    "pattern": "词汇与人物身份不符",
                    "description": "粗鲁武将说话时用'颔首'、'好整以暇'等文雅词汇",
                    "problem": "人物性格不一致",
                    "solution": "根据人物身份选择合适的表达方式"
                },
                {
                    "pattern": "过度使用程度副词",
                    "description": "'极其'、'非常'、'十分'、'异常'频繁出现",
                    "problem": "表达力度被稀释",
                    "solution": "减少程度副词，用具体细节展现程度"
                }
            ],
            "vocabulary_variety_suggestions": {
                "眼睛相关": ["眼睛", "眼眸", "目光", "眼神", "眼底", "眼中"],
                "点头相关": ["点了点头", "颔首", "应了一声", "嗯了一声", "点头"],
                "微笑相关": ["笑了笑", "嘴角上扬", "嘴角勾起", "莞尔", "笑了"],
                "快速相关": ["很快", "旋即", "随即", "立刻", "马上", "一下子"]
            }
        }
        
        if genre == GenreType.NOVEL_FICTION:
            base_rules["fiction_specific"] = [
                {
                    "pattern": "心理活动直白化",
                    "description": "'他心想：...'、'她暗道：...'",
                    "problem": "心理描写过于直白",
                    "solution": "用动作暗示心理，或融入叙事中"
                },
                {
                    "pattern": "破折号心理解释模式",
                    "description": "'我知道她想说什么——这药该热第三遍了'、'他明白她的意思——这是在赶客'",
                    "problem": "用破折号强行解释心理，显得生硬刻意，是典型的AI模式化表达",
                    "solution": "要么直接写心理活动，要么用动作/对话暗示，不要用破折号做心理解释"
                },
                {
                    "pattern": "我知道...想...句式",
                    "description": "'我知道她想说什么'、'我明白他的意思'、'我懂得她的心思'",
                    "problem": "过度使用'我知道/明白/懂得'开头，显得机械重复",
                    "solution": "变化表达方式，如'她还没开口，我就猜到了'、'她那点心思，我哪能看不出来'"
                },
                {
                    "pattern": "过渡词机械化",
                    "description": "连续使用'就在这时'、'忽然'、'随即'开头",
                    "problem": "叙事节奏机械",
                    "solution": "变化过渡方式，有时直接切入"
                }
            ]
        elif genre == GenreType.ACADEMIC_PAPER:
            base_rules["academic_specific"] = [
                {
                    "pattern": "连接词套话化",
                    "description": "'首先...其次...最后...综上所述'固定结构",
                    "problem": "结构过于刻板",
                    "solution": "可以变化为'第一...第二...第三...总之'，或直接陈述"
                },
                {
                    "pattern": "空洞性表达",
                    "description": "'不言而喻'、'显而易见'后无具体说明",
                    "problem": "论证不充分",
                    "solution": "删除套话，直接陈述理由或数据"
                }
            ]
        
        return base_rules
    
    def _generate_sentence_guidance(self, genre: GenreType, style_analysis: Dict) -> Dict:
        """生成句式指导 - 强调多样化而非简单化"""
        guidance = {
            "core_principle": """
【核心原则】句式多样化 > 句式简单化

人类写作的真正特征是：
- 该长则长，该短则短，由内容决定
- 长句用于铺陈、描写、营造氛围
- 短句用于强调、转折、制造节奏
- 长短交替，节奏自然

❌ 错误理解：人类写作 = 全用短句
✅ 正确理解：人类写作 = 句式多样化，服务于内容
""",
            "sentence_length": {
                "principle": "长短句各有用途，关键在于匹配内容需要",
                "long_sentence_usage": [
                    "描写复杂场景：'阳光从半开的窗帘缝隙里漏进来，在地板上画出一道白线，灰尘在光里跳舞，像是无数细小的生命。'",
                    "表达流动心理：'他想着那些事，一件一件，像翻一本旧相册，每翻一页都是一段回不去的时光。'",
                    "营造舒缓氛围：'她坐在那张旧藤椅上，手里捧着一杯渐渐变凉的茶，看着窗外的雨，一滴一滴，打在玻璃上。'"
                ],
                "short_sentence_usage": [
                    "紧张时刻：'门开了。他愣住。是她。'",
                    "强调重点：'他说完，转身，走了。'",
                    "制造节奏变化：'雨停了。风也停了。整个世界像是死了。'"
                ],
                "target_variation": style_analysis["parameters"].sentence_length_variation
            },
            "dialogue_ratio": {
                "target": style_analysis["parameters"].dialogue_ratio,
                "note": "对话要符合人物身份，自然流畅"
            },
            "structure_preferences": []
        }
        
        if genre == GenreType.NOVEL_FICTION:
            guidance["structure_preferences"].extend([
                "段落开头方式要多样化：有的以对话开头，有的以动作开头，有的以环境开头",
                "避免每段都是'环境描写→人物动作→心理活动→对话'的固定顺序",
                "对话句式要符合人物身份：文人说文雅话，武夫说粗话，孩子说简单话",
                "内心独白可以自然融入叙事，不必单独成段",
                "场景转换可以突然，不必每次都铺垫过渡"
            ])
        elif genre == GenreType.ACADEMIC_PAPER:
            guidance["structure_preferences"].extend([
                "长句用于完整表达复杂逻辑关系",
                "被动语态可用于强调客观性，但不要过度",
                "避免连续使用相同的句式开头",
                "可以适当使用设问句引导读者思考"
            ])
        elif genre == GenreType.NEWS_REPORT:
            guidance["structure_preferences"].extend([
                "以短句为主，信息密度要高",
                "关键信息放在句首",
                "引语要完整，注明出处",
                "避免过长的从句嵌套"
            ])
        elif genre == GenreType.SOCIAL_MEDIA:
            guidance["structure_preferences"].extend([
                "短句为主，便于快速阅读",
                "可以适当使用碎片化表达",
                "开头要抓人眼球",
                "结尾可以留悬念或引导互动"
            ])
        else:
            guidance["structure_preferences"].extend([
                "保持句式自然流畅",
                "避免机械的排比或重复句式",
                "让句子有长有短，节奏感强",
                "根据内容需要选择句式"
            ])
        
        rhythm = style_analysis["parameters"].rhythm_variation
        if rhythm < 0.3:
            guidance["rhythm_adjustment"] = "当前节奏较为平稳，可以适当增加句长变化，在关键处用短句制造冲击"
        elif rhythm > 0.7:
            guidance["rhythm_adjustment"] = "当前节奏变化较大，注意保持可读性，长句中适当断句"
        else:
            guidance["rhythm_adjustment"] = "当前节奏适中，保持自然的句式变化"
        
        return guidance
    
    def _generate_tone_control(self, genre: GenreType, style_analysis: Dict) -> Dict:
        """生成语气控制参数"""
        params = style_analysis["parameters"]
        
        return {
            "formality": {
                "value": params.formality_level,
                "adjustment": "提高" if params.formality_level < 0.5 else "降低",
                "target_range": self._get_formality_range(genre)
            },
            "emotion": {
                "value": params.emotional_level,
                "note": self._get_emotion_note(genre)
            },
            "rhythm": {
                "value": params.rhythm_variation,
                "guidance": self._get_rhythm_guidance(params.rhythm_variation)
            },
            "detail": {
                "value": params.detail_level,
                "note": self._get_detail_note(genre)
            }
        }
    
    def _get_formality_range(self, genre: GenreType) -> str:
        """获取目标正式程度范围"""
        ranges = {
            GenreType.ACADEMIC_PAPER: "0.6-0.9（较高正式度）",
            GenreType.NEWS_REPORT: "0.5-0.8（中高度正式度）",
            GenreType.BUSINESS_DOC: "0.5-0.8（中高度正式度）",
            GenreType.NOVEL_FICTION: "0.3-0.6（适中正式度）",
            GenreType.CREATIVE_WRITING: "0.3-0.6（适中正式度）",
            GenreType.SOCIAL_MEDIA: "0.1-0.4（较低正式度）"
        }
        return ranges.get(genre, "0.3-0.7（适中正式度）")
    
    def _get_emotion_note(self, genre: GenreType) -> str:
        """获取情感表达备注"""
        notes = {
            GenreType.ACADEMIC_PAPER: "客观为主，避免主观情感表达",
            GenreType.NEWS_REPORT: "客观中立，情感通过事实传递",
            GenreType.NOVEL_FICTION: "情感细腻但含蓄，避免直白喊口号",
            GenreType.CREATIVE_WRITING: "情感真挚，允许主观表达",
            GenreType.SOCIAL_MEDIA: "可以有真实情感流露",
            GenreType.BUSINESS_DOC: "自信但不浮夸"
        }
        return notes.get(genre, "情感适度，自然表达")
    
    def _get_rhythm_guidance(self, rhythm: float) -> str:
        """获取节奏指导"""
        if rhythm < 0.3:
            return "增加句长和节奏变化，避免过于平淡"
        elif rhythm > 0.7:
            return "适当控制节奏变化幅度，保持可读性"
        else:
            return "保持当前节奏的自然变化"
    
    def _get_detail_note(self, genre: GenreType) -> str:
        """获取细节处理备注"""
        notes = {
            GenreType.ACADEMIC_PAPER: "数据和方法细节要充分，论述可适当精简",
            GenreType.NEWS_REPORT: "关键细节要具体，背景可简洁",
            GenreType.NOVEL_FICTION: "细节要有代表性和暗示性，避免全面描写",
            GenreType.CREATIVE_WRITING: "细节要有画面感和感染力",
            GenreType.SOCIAL_MEDIA: "核心细节要突出，避免冗长"
        }
        return notes.get(genre, "细节适度，服务内容")
    
    def _generate_style_preservation(self, genre: GenreType, style_analysis: Dict) -> Dict:
        """生成风格保留策略"""
        primary_style = style_analysis["primary_style"]
        
        preservation = {
            "elements_to_preserve": [],
            "elements_to_enhance": [],
            "elements_to_avoid": []
        }
        
        # 根据题材确定保留要素
        genre_elements = {
            GenreType.NOVEL_FICTION: ["人物性格一致性", "情节逻辑", "场景氛围"],
            GenreType.ACADEMIC_PAPER: ["论证逻辑", "专业术语准确性", "引用规范"],
            GenreType.NEWS_REPORT: ["信息准确性", "来源可靠性", "平衡性"],
            GenreType.CREATIVE_WRITING: ["情感真挚性", "意象统一性", "风格一致性"],
            GenreType.SOCIAL_MEDIA: ["个人特色", "互动性", "真实感"],
            GenreType.BUSINESS_DOC: ["逻辑清晰度", "数据支撑", "可操作性"]
        }
        preservation["elements_to_preserve"] = genre_elements.get(genre, ["内容完整性"])
        
        # 根据风格确定增强要素
        style_enhancements = {
            WritingStyle.FORMAL: ["专业性", "严谨性", "权威感"],
            WritingStyle.COLLOQUIAL: ["亲和力", "自然感", "易读性"],
            WritingStyle.HUMOROUS: ["幽默感", "趣味性", "吸引力"],
            WritingStyle.SERIOUS: ["深度感", "严肃性", "思辨性"],
            WritingStyle.LYRICAL: ["诗意", "韵律感", "情感感染力"],
            WritingStyle.EPIC: ["气势感", "宏大感", "历史感"]
        }
        preservation["elements_to_enhance"] = style_enhancements.get(primary_style, ["可读性"])
        
        # 需要避免的要素
        preservation["elements_to_avoid"] = [
            "机械的过渡词",
            "重复的句式结构",
            "过于完美的逻辑链条",
            "情感的直接陈述而非展示"
        ]
        
        return preservation
    
    def _generate_correct_examples(self, genre: GenreType, style_analysis: Dict) -> Dict:
        """生成正确示范 - 真正识别AI痕迹"""
        examples = {
            "before_ai_pattern": [],
            "after_human_style": [],
            "comparison_note": []
        }
        
        common_examples = [
            {
                "before": "他感到很累。连续三周，每天睡不到四个小时。他不禁心想：这种日子什么时候是个头？太累了。",
                "after": "咖啡凉了，没人动。他坐着，窗外天黑了也没开灯。",
                "note": "用细节展示状态，而非直接陈述感受"
            },
            {
                "before": "她眼眸中闪过一丝不易察觉的悲伤，嘴角勾起一抹苦涩的弧度，心中涌起无限的感慨。",
                "after": "她没说话，低下头站了一会儿。",
                "note": "问题不是'眼眸'这个词，而是多个高级词汇堆砌，简化为自然动作"
            },
            {
                "before": "阳光透过窗户洒进房间，在书桌上投下一片温暖的光斑。他坐在椅子上，感到心情复杂。",
                "after": "阳光透过窗户洒进房间，在书桌上投下一片温暖的光斑。他坐在椅子上，感到心情复杂。",
                "note": "这本来就是人类写法！长句、成语、优美描写都可以用，关键是自然"
            },
            {
                "before": "首先，我们需要分析问题的根源。其次，我们要制定解决方案。最后，我们要确保执行到位。综上所述，这是一个系统性的工程。",
                "after": "问题的根源在哪里？我们需要先弄清楚。然后才能谈解决方案。至于执行，那是后面的事。",
                "note": "问题在于结构过于刻板，不是'首先'这个词本身"
            }
        ]
        
        genre_examples = {
            GenreType.NOVEL_FICTION: [
                {
                    "before": "就在这时，门突然被推开了，只见一个身影快速闪了进来，随即消失在黑暗中。",
                    "after": "门被推开了，有人进来，很快消失在黑暗中。",
                    "note": "问题在于过度渲染，'就在这时'、'突然'、'只见'、'随即'堆在一起"
                },
                {
                    "before": "他心中一凛，暗道不好，看来事情比他预想的要棘手得多。",
                    "after": "他愣了一下，事情好像不对。",
                    "note": "简化内心独白，用直觉反应替代分析"
                },
                {
                    "before": "他看着窗外的雨，心想起了那些往事，一件一件，像翻一本旧相册。",
                    "after": "他看着窗外的雨，想起那些往事，一件一件，像翻一本旧相册。",
                    "note": "保留长句和比喻，只是去掉多余的'心'字"
                }
            ],
            GenreType.ACADEMIC_PAPER: [
                {
                    "before": "不言而喻，大量的数据表明了这一结论的可靠性。",
                    "after": "数据显示了这一结论。",
                    "note": "去掉无效的修饰词，直接陈述"
                },
                {
                    "before": "综上所述，本研究对相关领域具有重要的理论意义和实践价值。",
                    "after": "本研究对相关领域具有一定的参考价值。",
                    "note": "避免过度拔高，保持学术谦逊"
                }
            ],
            GenreType.NEWS_REPORT: [
                {
                    "before": "据悉，业内分析认为，该现象值得广泛关注和深入思考。",
                    "after": "有业内人士指出，这一现象值得关注。",
                    "note": "用具体引用替代模糊来源"
                }
            ],
            GenreType.SOCIAL_MEDIA: [
                {
                    "before": "姐妹们，真的绝了！这款产品太可了，必须给我冲！",
                    "after": "用了一段时间，真的很不错，推荐给你们。",
                    "note": "保留热情但减少夸张表达"
                }
            ]
        }
        
        examples["before_ai_pattern"] = common_examples + genre_examples.get(genre, [])
        examples["after_human_style"] = [ex["after"] for ex in examples["before_ai_pattern"]]
        examples["comparison_note"] = [
            "核心原则：展示而非告知（Show, don't tell）",
            "问题不在词汇本身，在于使用模式",
            "长句、成语、优美描写都可以用，关键是自然",
            "真正的AI痕迹是：模式化、重复、过度完美"
        ]
        
        return examples
    
    def _generate_forbidden_items(self, genre: GenreType, style_analysis: Dict) -> Dict:
        """生成禁止项 - 基于模式而非词汇"""
        forbidden = {
            "important_note": """
【重要说明】以下禁止项是"模式"，不是"词汇"！

词汇本身没有错，错的是使用模式：
- "眼眸"可以用，但不要每段都用
- "首先"可以用，但不要每次都"首先-其次-最后"
- 长句可以用，但不要每句都长
- 成语可以用，但不要堆砌

真正的禁止是禁止"模式化"，不是禁止"表达方式"
""",
            "pattern_forbidden": [],
            "structure_forbidden": [],
            "tone_forbidden": [],
            "content_forbidden": []
        }
        
        forbidden["pattern_forbidden"].extend([
            {
                "pattern": "同一词汇短距离重复",
                "description": "相邻两段内出现相同的'高级词汇'（如两段都有'眼眸'）",
                "reason": "重复感明显，显得词汇贫乏"
            },
            {
                "pattern": "高级词汇密集堆砌",
                "description": "一句话中出现3个以上'高级词汇'（如'眼眸中闪过一丝不易察觉的精光，嘴角勾起一抹意味深长的弧度'）",
                "reason": "堆砌感强，不像自然表达"
            },
            {
                "pattern": "段落结构完全相同",
                "description": "连续三段以上都是'环境描写→动作→心理→对话'的固定顺序",
                "reason": "叙事模式化，缺乏变化"
            },
            {
                "pattern": "过渡词机械化",
                "description": "连续使用'就在这时'、'忽然'、'随即'、'于是'开头",
                "reason": "过渡方式单一，节奏机械"
            },
            {
                "pattern": "程度副词滥用",
                "description": "短文中出现多个'极其'、'非常'、'十分'、'异常'",
                "reason": "表达力度被稀释，显得空洞"
            }
        ])
        
        forbidden["structure_forbidden"].extend([
            "连续三句以上相同句式开头",
            "每段都是'环境→动作→心理→对话'的固定结构",
            "所有对话都用'他说'、'她说'开头",
            "每次场景转换都用'就在这时'"
        ])
        
        forbidden["tone_forbidden"].extend([
            "感叹号连续使用（'！！'）",
            "过于绝对的词汇（'绝对、肯定、必然'）",
            "直白的情感标签（'她很悲伤、他很愤怒'）",
            "过度拔高的评价（'具有重大意义'、'影响深远'）"
        ])
        
        forbidden["content_forbidden"].extend([
            "人物出场时的标签化介绍（'他是一个...的人'）",
            "环境描写的无意义堆砌",
            "不必要的前情回顾",
            "过于完美的逻辑闭环"
        ])
        
        if genre == GenreType.ACADEMIC_PAPER:
            forbidden["structure_forbidden"].extend([
                "无具体引用的'研究表明'",
                "空洞的'不言而喻'、'显而易见'"
            ])
            forbidden["tone_forbidden"].append("过于主观的'我认为'（应用'本文认为'）")
        
        elif genre == GenreType.NOVEL_FICTION:
            forbidden["content_forbidden"].extend([
                "人物出场时的大段背景介绍",
                "违背人物性格的突兀反应",
                "所有角色说话风格相同"
            ])
        
        elif genre == GenreType.SOCIAL_MEDIA:
            forbidden["tone_forbidden"].append("过于正式和官方的语气")
            forbidden["content_forbidden"].append("空洞的营销话术")
        
        return forbidden
    
    def _assemble_complete_prompt(
        self,
        genre: GenreType,
        config: GenreCharacteristics,
        style_analysis: Dict,
        core_instructions: List[str],
        vocabulary_rules: Dict,
        sentence_guidance: Dict,
        tone_control: Dict,
        style_preservation: Dict,
        correct_examples: Dict,
        forbidden_items: Dict
    ) -> str:
        """组装完整的提示词"""
        
        prompt_parts = [
            f"【题材识别】{config.name}",
            f"【写作风格】{style_analysis['primary_style'].value}",
            "",
            "【核心指令】",
        ]
        
        for instruction in core_instructions:
            prompt_parts.append(instruction)
        
        prompt_parts.extend([
            "",
            "【词汇处理原则】",
        ])
        
        if vocabulary_rules.get("important_note"):
            prompt_parts.append(vocabulary_rules["important_note"])
        
        if vocabulary_rules.get("pattern_based_rules"):
            prompt_parts.append("需要避免的词汇使用模式：")
            for rule in vocabulary_rules["pattern_based_rules"]:
                prompt_parts.append(f"  · {rule['pattern']}：{rule['description']}")
                prompt_parts.append(f"    问题：{rule['problem']}")
                prompt_parts.append(f"    解决：{rule['solution']}")
        
        if vocabulary_rules.get("vocabulary_variety_suggestions"):
            prompt_parts.append("词汇多样化建议：")
            for category, words in vocabulary_rules["vocabulary_variety_suggestions"].items():
                prompt_parts.append(f"  · {category}：{' / '.join(words)}")
        
        prompt_parts.extend([
            "",
            "【句式指导】",
        ])
        
        if sentence_guidance.get("core_principle"):
            prompt_parts.append(sentence_guidance["core_principle"])
        
        if sentence_guidance.get("structure_preferences"):
            for guidance in sentence_guidance.get("structure_preferences", []):
                prompt_parts.append(f"· {guidance}")
        
        if sentence_guidance.get("rhythm_adjustment"):
            prompt_parts.append(f"节奏建议：{sentence_guidance['rhythm_adjustment']}")
        
        prompt_parts.extend([
            "",
            "【语气控制】",
            f"· 正式程度：{tone_control['formality']['value']:.1f}（目标：{tone_control['formality']['target_range']}）",
            f"· 情感表达：{tone_control['emotion']['note']}",
            f"· 节奏变化：{tone_control['rhythm']['guidance']}",
        ])
        
        prompt_parts.extend([
            "",
            "【风格保留策略】",
            "需要保留："
        ])
        
        for elem in style_preservation.get("elements_to_preserve", []):
            prompt_parts.append(f"  · {elem}")
        
        prompt_parts.extend([
            "需要增强："
        ])
        
        for elem in style_preservation.get("elements_to_enhance", []):
            prompt_parts.append(f"  · {elem}")
        
        prompt_parts.extend([
            "",
            "【正确示范】"
        ])
        
        for i, example in enumerate(correct_examples.get("before_ai_pattern", [])[:4], 1):
            prompt_parts.extend([
                f"示例{i}：",
                f"  AI模式：{example['before']}",
                f"  人类写法：{example['after']}",
                f"  原理：{example['note']}",
                ""
            ])
        
        prompt_parts.extend([
            "【严格禁止的模式】"
        ])
        
        if forbidden_items.get("important_note"):
            prompt_parts.append(forbidden_items["important_note"])
        
        for pattern in forbidden_items.get("pattern_forbidden", [])[:5]:
            prompt_parts.append(f"  · {pattern['pattern']}：{pattern['description']}")
        
        for struct in forbidden_items.get("structure_forbidden", [])[:3]:
            prompt_parts.append(f"  · 禁用句式：{struct}")
        
        for tone in forbidden_items.get("tone_forbidden", [])[:3]:
            prompt_parts.append(f"  · 禁用语气：{tone}")
        
        prompt_parts.extend([
            "",
            "【核心理念】",
            "词汇本身没有AI痕迹，关键在于使用模式。",
            "长句、成语、优美描写都可以用，关键是自然。",
            "真正的AI痕迹是：模式化、重复、过度完美。",
            "写得像人类，像你这个水准的作者，在真实写作。"
        ])
        
        return "\n".join(prompt_parts)
    
    def generate_for_api(self, text: str, genre_hint: Optional[str] = None) -> str:
        """
        为API调用生成完整提示词
        :param text: 待处理文本
        :param genre_hint: 题材提示（可选）
        :return: 完整提示词
        """
        if genre_hint:
            # 根据提示映射到题材类型
            genre_mapping = {
                "小说": GenreType.NOVEL_FICTION,
                "学术": GenreType.ACADEMIC_PAPER,
                "新闻": GenreType.NEWS_REPORT,
                "创意": GenreType.CREATIVE_WRITING,
                "社交": GenreType.SOCIAL_MEDIA,
                "商业": GenreType.BUSINESS_DOC
            }
            target_genre = genre_mapping.get(genre_hint)
        else:
            target_genre = None
        
        result = self.generate_prompts(text, target_genre)
        return result["complete_prompt"]


class AdaptiveAIHumanizer:
    """
    自适应AI痕迹消除器
    根据文本特点动态调整处理策略
    """
    
    def __init__(self):
        self.prompt_generator = DynamicPromptGenerator()
    
    def analyze_and_humanize(self, text: str, api_client=None) -> Dict:
        """
        分析文本并生成人性化处理方案
        :param text: 待处理文本
        :param api_client: 可选的API客户端用于实际处理
        :return: 处理结果
        """
        # 1. 分析文本特征
        genre_recognizer = GenreRecognizer()
        style_analyzer = StyleAnalyzer()
        
        genre, genre_conf = genre_recognizer.recognize(text)
        style_info = style_analyzer.analyze(text)
        
        # 2. 生成动态提示词
        prompt_result = self.prompt_generator.generate_prompts(text, genre)
        
        # 3. 如果有API客户端，执行处理
        processed_text = text
        if api_client:
            processed_text = api_client.humanize_content(
                text,
                system_prompt=prompt_result["complete_prompt"],
                intensity=8
            )
        
        return {
            "original_text": text,
            "processed_text": processed_text,
            "analysis": {
                "genre": {
                    "type": genre.value,
                    "confidence": genre_conf
                },
                "style": {
                    "primary": style_info["primary_style"].value,
                    "parameters": style_info["parameters"].to_dict()
                }
            },
            "dynamic_prompt": prompt_result["complete_prompt"],
            "recommendations": self._generate_recommendations(prompt_result, style_info)
        }
    
    def _generate_recommendations(self, prompt_result: Dict, style_info: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于风格混合的建议
        style_mix = style_info.get("style_mix_recommendation", {})
        if style_mix.get("ratio", 1.0) < 0.5:
            recommendations.append(
                f"检测到风格混合，建议明确主导风格为{style_mix.get('primary', 'formal')}"
            )
        
        # 基于节奏的建议
        rhythm = style_info["parameters"].rhythm_variation
        if rhythm < 0.3:
            recommendations.append("节奏过于平稳，建议增加句长和节奏变化")
        elif rhythm > 0.7:
            recommendations.append("节奏变化过大，建议适当控制保持可读性")
        
        # 基于对话比例的建议
        dialogue = style_info["parameters"].dialogue_ratio
        if style_info["primary_style"] == WritingStyle.COLLOQUIAL and dialogue < 0.1:
            recommendations.append("口语化风格建议适当增加对话元素")
        
        return recommendations
    
    def quick_humanize(self, text: str, genre_hint: str = None) -> str:
        """
        快速人性化处理
        :param text: 待处理文本
        :param genre_hint: 题材提示
        :return: 处理后的提示词
        """
        return self.prompt_generator.generate_for_api(text, genre_hint)


# 便捷函数
def create_dynamic_prompt(text: str = "", genre_hint: str = None, genre: str = None, use_ultimate: bool = True) -> str:
    """
    创建动态提示词
    :param text: 待处理文本
    :param genre_hint: 题材提示
    :param genre: 题材提示（与genre_hint等效，用于兼容）
    :param use_ultimate: 是否使用终极人性化系统（默认True）
    :return: 完整提示词
    """
    actual_genre = genre_hint or genre
    if use_ultimate:
        return create_ultimate_humanization_prompt(text, actual_genre)
    
    generator = DynamicPromptGenerator()
    return generator.generate_for_api(text, actual_genre)


def analyze_text_style(text: str) -> Dict:
    """分析文本风格"""
    recognizer = GenreRecognizer()
    analyzer = StyleAnalyzer()
    
    genre, conf = recognizer.recognize(text)
    style = analyzer.analyze(text)
    
    return {
        "genre": {
            "type": genre.value,
            "confidence": conf,
            "name": genre.value.replace("_", " ").title()
        },
        "writing_style": {
            "primary": style["primary_style"].value,
            "secondary": [s.value for s in style["secondary_styles"]],
            "parameters": style["parameters"].to_dict()
        }
    }


if __name__ == "__main__":
    test_texts = {
        "小说": "他心中一凛，暗道不好，看来事情比他预想的要棘手得多。眸中闪过一丝不易察觉的精光，随即恢复了常态。",
        "学术": "首先，其次，最后，综上所述，不言而喻的是，有待进一步研究。大量数据表明了这一结论的可靠性。",
        "新闻": "据悉，业内分析认为，该现象值得广泛关注和深入思考。值得关注的是，这一问题已经影响了多个领域。",
        "社交": "姐妹们，真的绝了！这款产品太可了，必须给我冲！打 call！",
        "正常人类写法": "阳光透过窗户洒进房间，在书桌上投下一片温暖的光斑。他坐在椅子上，感到心情复杂。"
    }
    
    for genre, text in test_texts.items():
        print(f"\n{'='*60}")
        print(f"测试题材：{genre}")
        print(f"原文：{text}")
        print(f"\n动态提示词：")
        print(create_dynamic_prompt(text, genre))


def get_ai_detection_why_exposed():
    """获取AI内容被识破的四大非人缺陷分析"""
    return """
【AI内容被识破的四大"非人缺陷" - 必须彻底攻克】

═══════════════════════════════════════════════════════════════════════════════
核心结论：AI痕迹的本质不是文笔好坏，而是"文本有没有人类创作的专属痕迹"
═══════════════════════════════════════════════════════════════════════════════

所有被识破的AI内容，本质都踩中了以下4个AI原生的"非人缺陷"：

═══════════════════════════════════════════════════════════════════════════════
一、空心化：只有文本结果，没有创作源头
═══════════════════════════════════════════════════════════════════════════════

❌ **AI缺陷**：
人类顶流作者的每一篇内容，都有「非写不可的动机」：要么是亲历了某件事心里堵得慌，要么是给特定的人写的，要么是为了表达自己一辈子的执念，文字是情绪与思想的出口。

而AI的内容，是"为了完成指令而生成"，没有源头、没有私人情绪、没有非写不可的理由，哪怕文笔再像，也会有"空心感"，读者一眼就会觉得"没灵魂"。

✅ **攻克方案**：
- 必须给AI搭建完整的、符合作者人生轨迹的沉浸式创作场景
- 让AI有"非写不可的理由"，而不是凭空完成指令
- 所有文字必须有情绪源头和创作动机

═══════════════════════════════════════════════════════════════════════════════
二、完美化：过度符合概率最优，没有人类的"反概率表达"
═══════════════════════════════════════════════════════════════════════════════

❌ **AI缺陷**：
AI的底层逻辑是「生成训练数据里概率最高、最通顺、最符合大众预期的文本」，所以它的内容永远是：零语法错误、句式节奏均匀、情绪浓度平稳、逻辑绝对闭环、用词全是高频通用表达。

而人类顶流作者的核心竞争力，恰恰是「反概率」：用独一无二的比喻、有瑕疵的表达、跳脱的情绪、不闭环的留白，跳出大众的预期，形成自己的专属风格。

✅ **攻克方案**：
- 彻底锁死AI的通用表达，强制它只用作者的专属表达
- 打破AI的均匀句式节奏，让节奏有快有慢，有张有弛
- 允许有刻意的用词重复、语序的小停顿、逻辑的小跳跃

═══════════════════════════════════════════════════════════════════════════════
三、通用化：只有公共素材，没有私人化的阅历锚点
═══════════════════════════════════════════════════════════════════════════════

❌ **AI缺陷**：
AI的所有细节、素材、案例，都来自训练数据里的公共内容，是所有人都能查到的、通用的。

而人类顶流作者的文字里，永远藏着「只有他自己才有的、独一无二的私人阅历锚点」，这些细节是编不出来的，只有亲历者才能写出来，这也是读者笃定"这一定是本人写的"的核心依据。

✅ **攻克方案**：
- 所有核心细节、案例、比喻，必须全部来自素材库
- 绝对不能编造任何无来源的通用内容
- 所有细节必须符合作者的人生轨迹与时代背景

═══════════════════════════════════════════════════════════════════════════════
四、全知化：上帝视角的绝对正确，没有人类的认知局限与偏见
═══════════════════════════════════════════════════════════════════════════════

❌ **AI缺陷**：
AI永远是全知全能、政治正确、客观中立的，对任何领域都能讲得头头是道。

而人类作者，哪怕是顶流，也有自己的认知边界、私人偏见、情绪上头的片面表达，这些"不完美的人性"，恰恰是区分AI与真人的终极分界线。

✅ **攻克方案**：
- 严格锁死作者的「认知边界」
- 100%还原作者的「私人偏见」
- 哪怕这个偏见在当下是"不正确"的，也要完整保留
"""


def get_author_personality_modeling_system():
    """获取顶流作者全人格建模系统"""
    return """
【顶流作者全人格建模系统 - 从模仿文笔到彻底变成作者本人】

═══════════════════════════════════════════════════════════════════════════════
核心原理：为什么只模仿文笔会失败？
═══════════════════════════════════════════════════════════════════════════════

99%的人模仿失败，都死在第一步：只让AI"模仿XX的文笔"，却没搞懂XX为什么能成为顶流。

想要以假乱真，你必须把抽象的"文笔好"，拆解成AI可100%执行、可刚性锁死的「人格与创作规则」，让AI从"模仿文本"，变成"彻底变成这个作者本人"。

═══════════════════════════════════════════════════════════════════════════════
建模维度一：核心创作执念
═══════════════════════════════════════════════════════════════════════════════

作者一辈子都在写的核心命题、一以贯之的价值观、非说不可的话。

【示例】：
- 鲁迅：对国民性的批判、"铁屋子"的隐喻
- 余华：对"活着本身"的探讨
- 汪曾祺：对人间烟火的执念
- 张爱玲：对人情冷暖的洞察

【落地要求】：
- 从作者本人的原作、访谈、书信、自传里提取
- 不能主观臆造
- 必须贯穿所有创作

═══════════════════════════════════════════════════════════════════════════════
建模维度二：人生阅历锚点
═══════════════════════════════════════════════════════════════════════════════

作者的人生轨迹、亲历的重大事件、生活过的城市、职业经历、私人化的生活细节。

【重要性】：
这些是作者所有创作的素材源头，绝对不能超出这个边界。

【落地要求】：
- 整理作者亲历的所有事件
- 记录生活过的地方、见过的人
- 收集有记录的私人细节
- 越细碎、越私人、越独一无二越好

═══════════════════════════════════════════════════════════════════════════════
建模维度三：语言指纹
═══════════════════════════════════════════════════════════════════════════════

【1. 用词习惯】：
- 专属高频词
- 绝对不会用的词
- 口语/书面语的比例

【2. 句式节奏】：
- 长/短句偏好
- 标点用法
- 段落长短
- 换行习惯

【3. 修辞逻辑】：
- 善用的比喻/隐喻类型
- 绝对不用的修饰方式
- 白描/煽情的尺度

═══════════════════════════════════════════════════════════════════════════════
建模维度四：叙事惯性
═══════════════════════════════════════════════════════════════════════════════

- 固定的叙事视角（第一人称有限视角/全知视角）
- 开篇切入方式
- 伏笔回收逻辑
- 情绪拐点设计
- 结尾留白习惯
- 绝对不会用的叙事套路

═══════════════════════════════════════════════════════════════════════════════
建模维度五：认知边界与私人偏见
═══════════════════════════════════════════════════════════════════════════════

- 作者精通的领域
- 完全不懂的领域
- 对特定人/事的固定偏见
- 一以贯之的好恶

【重要】：
哪怕是"不正确"的，也要100%还原。这些"不完美的人性"，恰恰是区分AI与真人的终极分界线。

═══════════════════════════════════════════════════════════════════════════════
建模维度六：专属创作梗与意象
═══════════════════════════════════════════════════════════════════════════════

作者在所有作品里反复出现的专属意象、固定梗、口头禅，只有死忠粉能get到的"暗号"。

【示例】：
- 鲁迅的"铁屋子""看客"
- 王小波的"有趣"
- 张爱玲的"袍子与蚤子"

═══════════════════════════════════════════════════════════════════════════════
建模维度七：创作禁忌清单
═══════════════════════════════════════════════════════════════════════════════

作者绝对不会写的内容、绝对不会碰的价值观、绝对不会用的表达。

【重要】：
这一项比"要写什么"重要10倍！顶流作者的风格，本质是"有所为，有所不为"。

═══════════════════════════════════════════════════════════════════════════════
建模维度八：专属瑕疵习惯
═══════════════════════════════════════════════════════════════════════════════

作者固定的、有章法的"不完美"：
- 刻意的用词重复
- 语序的小停顿
- 逻辑的小跳跃
- 特定的用字习惯（比如鲁迅用"底"代替"的"）

【重要】：
这些是AI绝对不会主动生成的"人类防伪标"！
"""


def get_human_anti_ai_markers():
    """获取人类专属防伪印记注入系统"""
    return """
【人类专属防伪印记注入系统 - 彻底抹除AI感】

═══════════════════════════════════════════════════════════════════════════════
核心原理：这些内容都是AI无法原生生成的，必须通过精准指令刚性植入
═══════════════════════════════════════════════════════════════════════════════

每植入一项，被识破的概率就会大幅下降。全部植入后，哪怕是作者的死忠粉，也会觉得这是本人的佚文。

═══════════════════════════════════════════════════════════════════════════════
防伪印记一：非写不可的创作动机
═══════════════════════════════════════════════════════════════════════════════

给文本一个"灵魂源头"，让所有文字都有锚点，不再是凭空生成的概率文本。

【落地要求】：
- 必须有具体的触发事件
- 必须有明确的情绪状态
- 必须有"不吐不快"的冲动
- 情绪必须贯穿全文

【错误示范】：
"你是XX，模仿他的风格，写一篇关于XX的文章，800字。"

【正确示范】：
```
# 身份绝对锁死
你就是[作者名]，时间是[具体时间]，地点是[具体地点]，处境是[具体处境]。

# 创作动机（非写不可的理由）
[描述是什么触发了创作欲望，为什么非写不可，情绪状态如何]

# 创作状态还原
[描述写作时的状态、停顿、情绪波动、习惯动作]

# 刚性创作规则
1. 语言：[用词习惯、句式特点]
2. 内容：[能写什么、不能写什么]
3. 细节：[必须提到的私人化细节]
4. 人类防伪要求：[允许的"瑕疵"]
```

═══════════════════════════════════════════════════════════════════════════════
防伪印记二：独一无二的私人阅历锚点
═══════════════════════════════════════════════════════════════════════════════

这是让读者笃定"这一定是本人写的"的终极杀招。AI能模仿文笔，但绝对编不出「只有这个作者才有的、独一无二的、可溯源的私人细节」。

【示例】：
- 汪曾祺写吃的："我在昆明西南联大读书的时候，雨季的青头菌，炒的时候要放两瓣蒜，不然怕中菌毒，那时候我和朱德熙穷，一顿菌子就着两碗米饭，就是顶好的日子"
- 张爱玲写爱情："香港的海是灰绿色的，我在港大读书的时候，宿舍的窗对着海，下雨的时候，海就像一块湿了的锦缎"

【落地要求】：
- 所有核心细节、案例、比喻，必须全部来自素材库
- 绝对不能编造任何无来源的通用内容
- 所有细节必须符合作者的人生轨迹与时代背景
- 把私人细节自然地融入文本，而不是生硬堆砌

═══════════════════════════════════════════════════════════════════════════════
防伪印记三：反概率的专属表达
═══════════════════════════════════════════════════════════════════════════════

AI的内容永远是"概率最优"，而顶流作者的内容永远是"反概率"的。

【落地规则（必须刚性执行）】：
- 绝对禁止使用AI高频通用词、烂大街的比喻、万能句式
- 绝对禁止使用排比堆砌、强行煽情、过度修饰的表达
- 强制使用作者的「专属意象与比喻体系」
- 打破AI的均匀句式节奏：长短句交替，有快有慢，有张有弛

═══════════════════════════════════════════════════════════════════════════════
防伪印记四：有章法的瑕疵
═══════════════════════════════════════════════════════════════════════════════

越完美的文本，越容易被识别为AI。人类写的内容，哪怕是顶流作者的定稿，也会有"有章法的瑕疵"。

【可安全植入的瑕疵类型（绝对不能乱加错别字）】：

1. **情绪性的用词重复**：
   - 作者愤怒的时候，重复用同一个词
   - 悲伤的时候，同一句话反复出现
   - 符合真人的情绪惯性

2. **语序的小停顿**：
   - 用逗号断开原本连贯的句子
   - 加入语气的停顿
   - 如"我大抵是病了，横竖都睡不着，坐起来点了一支烟，这悲伤，没由来的"

3. **逻辑的小跳跃**：
   - 作者觉得读者能懂的内容，不用讲透，直接跳过去
   - 写着写着，突然插入一个只有作者自己懂的私人梗
   - 符合真人写东西时"走神"的状态

4. **作者专属的用字习惯**：
   - 鲁迅用"底"代替"的"
   - 沈从文的方言用词
   - 张爱玲的西式语序

5. **不闭环的留白**：
   - 结尾不强行升华、不总结全文、不给解决方案
   - 就停在情绪最浓的地方，留足想象空间
   - 这是AI最不擅长、也最容易暴露的地方

═══════════════════════════════════════════════════════════════════════════════
防伪印记五：认知局限与私人偏见
═══════════════════════════════════════════════════════════════════════════════

AI永远是全知全能、绝对正确的，而人类作者，哪怕是顶流，也有自己的认知边界和私人偏见。

【落地操作】：
1. **严格锁死作者的「认知边界」**：
   - 绝对不能让作者写他不懂、没接触过、超出他时代的内容
   - 比如让鲁迅写当代互联网，他只会用自己的认知翻译成"新的吃人工具"

2. **100%还原作者的「私人偏见」**：
   - 哪怕这个偏见在当下是"不正确"的，也要完整保留
   - 鲁迅对梅兰芳的偏见、张爱玲对人情世故的刻薄、王小波对无趣的极致厌恶
   - 这些偏见是作者人格的一部分，去掉了，就不是他了
"""


def get_full_workflow_7steps():
    """获取全流程落地7步闭环"""
    return """
【全流程落地：从0到1生成"绝对以假乱真"内容的7步闭环】

═══════════════════════════════════════════════════════════════════════════════
照着这个流程一步一步做，最终的内容既能骗过所有主流AI检测工具，
也能让资深读者、甚至作者的死忠粉，笃定这是真人亲笔所写。
═══════════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════════
步骤1：完成「顶流作者全人格建模」，输出《专属创作手册》
═══════════════════════════════════════════════════════════════════════════════

用建模清单，投喂作者的原作、访谈、书信等素材，让AI输出手册，人工校准每一条规则，确保100%符合作者本人，锁死所有创作边界与风格。

这一步，直接把模仿的贴合度从60分拉到85分，彻底告别"形似神不似"。

═══════════════════════════════════════════════════════════════════════════════
步骤2：搭建「沉浸式创作场景」，给AI一个非写不可的创作动机
═══════════════════════════════════════════════════════════════════════════════

设定符合作者人生轨迹的创作场景、时间、地点、情绪、创作缘由，越具体、越私人化越好，彻底解决文本的"空心化"问题。

═══════════════════════════════════════════════════════════════════════════════
步骤3：用终极prompt生成初稿，刚性锁死所有规则
═══════════════════════════════════════════════════════════════════════════════

把《专属创作手册》、创作场景、人类防伪印记要求、创作禁忌，全部融入prompt，让AI生成初稿，绝对不允许自由发挥。

═══════════════════════════════════════════════════════════════════════════════
步骤4：植入「私人阅历锚点素材」，完成二稿，替换所有通用内容
═══════════════════════════════════════════════════════════════════════════════

把作者的私人素材库投喂给AI，让它把所有通用细节、通用案例、通用比喻，全部替换成素材库里的、作者独有的私人内容，确保每一个核心细节都有溯源。

═══════════════════════════════════════════════════════════════════════════════
步骤5：双轮自检打磨，完成「去AI化终稿」
═══════════════════════════════════════════════════════════════════════════════

**第一轮AI自检**：
让AI对照《专属创作手册》，逐段逐句自检，标注并修改所有不符合规则的内容、AI高频通用表达、完美废话、强行升华的内容。

**第二轮人工自检**：
核心做5件事：
1. 打破均匀的句式节奏
2. 植入有章法的瑕疵
3. 校准情绪波动，确保不是均匀的情绪浓度
4. 删掉所有AI式的通用内容
5. 校准认知边界，确保没有超出作者的认知范围

═══════════════════════════════════════════════════════════════════════════════
步骤6：反检测校准，彻底骗过AI检测工具
═══════════════════════════════════════════════════════════════════════════════

把打磨好的内容，放到主流AI检测工具里检测，针对标红的AI内容，做3个核心修改：

1. **提高局部文本的困惑度**：
   把标红的句子，改成作者专属的口语化、私人化表达，打破AI均匀的概率分布

2. **加入非结构化内容**：
   加入括号里的自言自语、突然的走神、小的补充说明，这些是AI很少生成的内容

3. **替换所有AI高频词**：
   把标红内容里的通用词、高频词，全部替换成作者的专属用词

═══════════════════════════════════════════════════════════════════════════════
步骤7：终极盲测验证
═══════════════════════════════════════════════════════════════════════════════

把最终的内容，和作者的原作混在一起，给熟悉这个作者的读者、编辑、死忠粉做盲测，让他们分辨哪一篇是新写的，能不能看出是AI生成的。

如果他们无法分辨，甚至笃定是作者本人所写，就实现了真正的以假乱真。
"""


def get_ultimate_avoidance_rules():
    """获取终极避坑红线"""
    return """
【终极避坑红线：碰了任何一条，都会直接暴露AI身份】

═══════════════════════════════════════════════════════════════════════════════

1. **绝对不要追求完美无缺**：
   越零瑕疵、越通顺、越闭环的内容，越容易被识破，人类的创作，永远有不完美的地方

2. **绝对不要超出作者的认知边界**：
   不要让古人讲现代术语，不要让非专业作者讲自己不懂的专业内容，全知全能是AI最明显的标签

3. **绝对不要强行升华、强行给解决方案**：
   顶流作者的核心是提出问题、呈现人性，而不是给完美答案，AI最喜欢的结尾升华，是最大的暴露点

4. **绝对不要用通用素材、通用比喻、万能句式**：
   哪怕文笔再像，一个通用细节，就会让读者瞬间出戏，觉得"这不是他写的"

5. **绝对不要煽情过度、情绪拉满**：
   人类的顶级情绪表达永远是克制的，藏在细节里的，AI式的大段排比煽情，一眼就会被识破

═══════════════════════════════════════════════════════════════════════════════
【最终结论】
═══════════════════════════════════════════════════════════════════════════════

真正能让人笃定是人类顶流作者所写的内容，本质上**不是AI自己写出了神作，而是人用AI，把自己对这个作者的理解、对人性的理解、对世界的理解，完整注入到了文本里**。

AI永远只是一个工具，它可以复刻文笔、复刻句式、复刻结构，但文字里的灵魂、温度、私人化的情绪与阅历，永远只能由人来赋予。
"""


def create_ultimate_humanization_prompt(text: str = "", genre_hint: str = None) -> str:
    """
    创建终极人性化提示词 - 整合所有系统
    :param text: 待处理文本
    :param genre_hint: 题材提示
    :return: 完整的终极人性化提示词
    """
    generator = DynamicPromptGenerator()
    base_prompt = generator.generate_for_api(text, genre_hint)
    
    ultimate_addition = f"""

═══════════════════════════════════════════════════════════════════════════════
【终极人性化系统 - 绝对以假乱真】
═══════════════════════════════════════════════════════════════════════════════

{get_ai_detection_why_exposed()}

{get_human_anti_ai_markers()}

{get_ultimate_avoidance_rules()}

【核心原则】
让细节自己说话，让读者自己感受，
不解释、不总结、不命名情感。
真实 > 完美，自然 > 工整。
"""
    
    return base_prompt + "\n" + ultimate_addition
