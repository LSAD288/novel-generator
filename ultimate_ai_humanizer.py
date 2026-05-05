"""
终极AI痕迹消除系统
专门用于消除AI生成内容中的所有机械痕迹，使其达到大神级人类作者的写作水准

核心设计理念：
1. AI生成内容有七大类可识别模式
2. 人类写作有十大类不可复制特征
3. 必须从词汇、句式、段落、结构、节奏、情感、思维七个维度进行全面人类化
4. 注入"生命毛边"：真实人类写作中的不完美特征
5. 模拟大神级作者的个性化风格
"""

import re
import random


class UltimateAIHumanizer:
    """
    终极AI痕迹消除系统
    """
    
    # =========================================================================
    # 第一部分：AI痕迹模式识别系统（极其复杂）
    # =========================================================================
    
    AI_TRACE_PATTERNS = {
        "vocabulary_traces": {
            "formal_vocabulary": {
                "patterns": [
                    r"因此|于是|故而|故此|是以|综上所述",
                    r"众所周知|不言而喻|可想而知|顾名思义",
                    r"与此同时|此外|另外|与此同时",
                    r"综上所述|总而言之|由此可见|显而易见",
                    r"极为|极为|相当|极其|格外|尤其",
                ],
                "human_alternatives": {
                    "因此": ["就", "于是", "就这么着", "于是就"],
                    "于是": ["就", "于是乎", "这么着"],
                    "与此同时": ["这当口", "这会儿", "这时候"],
                    "众所周知": ["谁都知道", "明摆着", "这谁都知道"],
                    "综上所述": ["说白了", "反正", "这么回事"],
                },
                "weight": 2.5
            },
            "abstract_vocabulary": {
                "patterns": [
                    r"本质|核心|关键|根本|基础",
                    r"概念|定义|范畴|体系|框架",
                    r"逻辑|规律|原理|机制|模式",
                ],
                "human_alternatives": {
                    "本质": ["说到底", "反正", "说白了"],
                    "核心": ["关键是", "主要是", "说白了"],
                    "关键": ["重要的是", "主要是", "得说"],
                },
                "weight": 2.0
            },
            "absolute_vocabulary": {
                "patterns": [
                    r"完美|绝对|完全|彻底|全部",
                    r"永恒|永远|始终|一贯|一直",
                    r"必然|必定|一定|肯定|确定",
                ],
                "human_alternatives": {
                    "完美": ["差不多", "还行", "还成"],
                    "绝对": ["差不离", "大概", "说不准"],
                    "永远": ["长久", "年头多了", "以后的事"],
                },
                "weight": 3.0
            },
            "over_adorned_adjectives": {
                "patterns": [
                    r"璀璨|耀眼|夺目|绚丽|斑斓",
                    r"磅礴|浩荡|恢弘|雄伟|壮阔",
                    r"精致|精美|精巧|精细|精妙",
                    r"卓越|杰出|卓著|卓异",
                ],
                "human_alternatives": {
                    "璀璨": ["亮闪闪", "一闪一闪"],
                    "磅礴": ["大", "气派", "气势大"],
                    "精致": ["精细", "细致", "小巧"],
                },
                "weight": 2.5
            }
        },
        
        "sentence_traces": {
            "sensory_sequential": {
                "patterns": [
                    r"(?:听觉|视觉|触觉|嗅觉|味觉)[先才].{0,10}?(?:回来|恢复|苏醒|清醒)",
                    r"然后才[是看]",
                    r"先看清[的的是]",
                    r"(?:先|第一)[次步个].{0,10}?(?:感官|视觉|听觉|触觉|嗅觉)",
                ],
                "weight": 5.0
            },
            "negation_affirmation": {
                "patterns": [
                    r"不是.{1,10}，不是.{1,10}，是.{1,20}",
                    r"没有.{1,10}，没有.{1,10}，只有.{1,20}",
                    r"并非.{1,10}，并非.{1,10}，而是.{1,20}",
                ],
                "weight": 5.0
            },
            "parenthetical_insertion": {
                "patterns": [
                    r".{5,20}——.{5,30}——.{5,20}",
                    r".{5,20}（.{5,30}）.{5,20}",
                    r".{5,20}，.{5,30}，.{5,20}",
                ],
                "weight": 3.0
            },
            "causal_chain": {
                "patterns": [
                    r"因为.{1,15}，所以.{1,15}，因此.{1,15}",
                    r"由于.{1,15}，因此.{1,15}，于是.{1,15}",
                    r"既然.{1,10}，就.{1,15}，于是.{1,15}",
                ],
                "weight": 4.0
            },
            "enumeration": {
                "patterns": [
                    r"第一[、，,。]第二[、，,。]第三[、，,。]",
                    r"首先，{1,5}，其次，{1,5}，再次，{1,5}，最后，{1,5}",
                    r"1[.、]2[.、]3[.、]4[.、]5[.、]",
                ],
                "weight": 4.5
            },
            "definition_structure": {
                "patterns": [
                    r"所谓.{1,10}，是指.{1,20}",
                    r"所谓.{1,10}，即.{1,15}",
                    r"{1,5}是指{1,10}，也就是{1,10}",
                ],
                "weight": 3.5
            },
            "summary_structure": {
                "patterns": [
                    r"综上所述[，,。]",
                    r"总而言之[，,。]",
                    r"由此可见[，,。]",
                    r"不言而喻[，,。]",
                ],
                "weight": 3.0
            }
        },
        
        "paragraph_traces": {
            "equal_length_paragraphs": {
                "patterns": [
                    r"^(?:.{80,120}[。！？])$",
                    r"^(?:.{60,100}[。！？])$",
                ],
                "variance_threshold": 1000,
                "weight": 3.0
            },
            "similar_paragraph_structure": {
                "patterns": [
                    r"^(?:.{30,50}，.{30,50}。)$",
                    r"^(?:.{40,60}，.{40,60}，.{40,60}。)$",
                ],
                "weight": 2.5
            }
        },
        
        "structural_traces": {
            "perfect_alignment": {
                "patterns": [
                    r"第[一二三四五六七八九十百千]+章",
                    r"^[一二三四五六七八九十百千]+[、.）\)]",
                ],
                "weight": 1.5
            },
            "mechanical_timeline": {
                "patterns": [
                    r"首先|其次|再次|最后",
                    r"第一|第二|第三|第四|第五",
                    r"一开始|接着|然后|最后",
                ],
                "weight": 3.0
            },
            "perfect_logical_loop": {
                "patterns": [
                    r"因为.{1,15}，所以.{1,15}。由于.{1,15}，因此.{1,15}。",
                    r"如果.{1,15}，那么.{1,15}。只有.{1,15}，才.{1,15}。",
                ],
                "weight": 4.0
            }
        },
        
        "rhythm_traces": {
            "regular_sentence_length": {
                "patterns": [
                    r"(?:.{10,15}[，,]){4,}(?:.{10,15}[。！？])",
                ],
                "variance_threshold": 50,
                "weight": 4.0
            },
            "regular_punctuation": {
                "patterns": [
                    r"(?:[，。]{2}){3,}",
                    r"(?:——){2,}",
                ],
                "weight": 2.0
            }
        },
        
        "emotion_traces": {
            "emotion_labels": {
                "patterns": [
                    r"(?:悲伤|愤怒|恐惧|喜悦|惊讶|厌恶)",
                    r"(?:内心|心中|心底|心间)",
                ],
                "weight": 2.5
            },
            "direct_emotion": {
                "patterns": [
                    r"他(?:感到|觉得|知道|明白).{1,10}",
                    r"她(?:感到|觉得|知道|明白).{1,10}",
                    r"(?:内心|心中|心底).{1,10}",
                ],
                "weight": 3.5
            }
        },
        
        "thinking_traces": {
            "linear_thinking": {
                "patterns": [
                    r"首先.{1,15}，其次.{1,15}，最后.{1,15}",
                    r"因为.{1,10}，所以.{1,10}",
                ],
                "weight": 3.5
            },
            "dense_logic": {
                "patterns": [
                    r"(?:因为|由于|既然|如果|只要|无论).{1,10}，.{1,10}",
                ],
                "weight": 3.0
            }
        }
    }
    
    # =========================================================================
    # 第二部分：人类写作特征注入系统（极其复杂）
    # =========================================================================
    
    HUMAN_FEATURES = {
        "physiological_features": {
            "fatigue_markers": {
                "short_sentences": {
                    "markers": ["困。", "累了。", "算了。", "不想了。", "就这样吧。"],
                    "frequency": "每100字至少1处",
                },
                "vocabulary_degradation": {
                    "markers": ["就那样", "随便", "管他", "不爱说"],
                    "frequency": "每150字至少1处",
                },
                "punctuation_abuse": {
                    "markers": ["。。。", "。。", "？？", "！！"],
                    "frequency": "随机",
                },
                "self_denial": {
                    "markers": ["不写了", "算了算了", "不管了", "爱咋咋地"],
                    "frequency": "每200字至少1处",
                }
            },
            "pain_discomfort": {
                "markers": ["头疼", "眼睛疼", "手酸", "脖子僵", "腰疼"],
                "frequency": "每200字至少1处",
            }
        },
        
        "emotional_features": {
            "anger_regression": {
                "markers": ["操", "卧槽", "他妈的", "妈的", "去死", "滚"],
                "frequency": "每400字不超过1处",
            },
            "sadness_repression": {
                "markers": ["不说了", "不想说", "算了", "就这样"],
                "frequency": "每300字至少1处",
            },
            "helplessness_compromise": {
                "markers": ["算了吧", "随便吧", "管他呢", "爱咋咋地"],
                "frequency": "每200字至少1处",
            },
            "nostalgia_retro": {
                "markers": ["以前", "那年", "那时候", "还记得"],
                "frequency": "每500字至少1处",
            }
        },
        
        "environmental_features": {
            "spatial_invasion": {
                "markers": ["窗外", "门外", "楼道", "隔壁", "楼上楼下"],
                "frequency": "每200字至少1处",
            },
            "object_interference": {
                "markers": ["桌上", "床头", "旁边", "手边", "眼前"],
                "frequency": "每250字至少1处",
            },
            "time_perception": {
                "markers": ["凌晨", "半夜", "早上", "中午", "晚上", "刚才"],
                "frequency": "每300字至少1处",
            }
        },
        
        "social_features": {
            "address_regression": {
                "markers": ["喂", "哎", "嘿", "那个", "谁"],
                "frequency": "对话中随机",
            },
            "tone_tentative": {
                "markers": ["吧", "吗", "呢", "哈", "呀"],
                "frequency": "每100字至少2处",
            },
            "self_disclosure": {
                "markers": ["其实", "说实话", "不瞒你说", "老实说"],
                "frequency": "每300字至少1处",
            },
            "hesitation": {
                "markers": ["可能", "也许", "大概", "估计", "那个"],
                "frequency": "每150字至少1处",
            }
        },
        
        "thinking_features": {
            "thinking_jump": {
                "markers": ["忽然", "突然", "一下子", "转眼间"],
                "frequency": "每200字至少1处",
            },
            "self_correction": {
                "markers": ["不对", "错了", "等等", "等等等等"],
                "frequency": "每300字至少1处",
            },
            "memory_gap": {
                "markers": ["忘了", "不记得", "想不起来", "等会儿"],
                "frequency": "每400字至少1处",
            },
            "logical_gap": {
                "markers": ["后来", "后来才", "当时", "那时候"],
                "frequency": "每250字至少1处",
            }
        },
        
        "creative_features": {
            "insight_capture": {
                "markers": ["想到了", "有了", "灵感来了"],
                "frequency": "随机",
            },
            "creative_block": {
                "markers": ["卡住了", "写不出来", "不知道"],
                "frequency": "每500字至少1处",
            },
            "perfectionism_trap": {
                "markers": ["算了", "不管了", "爱咋咋地"],
                "frequency": "每400字至少1处",
            },
            "material_patchwork": {
                "markers": ["好像", "似乎", "大概是"],
                "frequency": "每200字至少1处",
            }
        },
        
        "life_features": {
            "daily_trivia": {
                "markers": ["吃饭", "睡觉", "上班", "下班", "洗澡"],
                "frequency": "每300字至少1处",
            },
            "material_dependence": {
                "markers": ["咖啡", "烟", "茶", "水", "外卖"],
                "frequency": "每250字至少1处",
            },
            "time_pressure": {
                "markers": ["快迟到了", "来不及", "赶时间"],
                "frequency": "随机",
            }
        },
        
        "linguistic_features": {
            "dialect_colloquial": {
                "markers": ["咋", "啥", "呗", "咧", "啦"],
                "frequency": "每100字至少2处",
            },
            "interjections": {
                "markers": ["哎", "唉", "嘿", "哈", "哇"],
                "frequency": "每50字至少1处",
            },
            "onomatopoeia": {
                "markers": ["啪", "咣", "嗖", "滴答", "咕噜"],
                "frequency": "每300字至少1处",
            }
        },
        
        "cognitive_features": {
            "uncertainty": {
                "markers": ["大概", "也许", "可能", "说不准"],
                "frequency": "每100字至少1处",
            },
            "vague_expression": {
                "markers": ["好像", "似乎", "隐隐约约", "迷迷糊糊"],
                "frequency": "每200字至少1处",
            },
            "self_questioning": {
                "markers": ["真的假的", "不会吧", "不至于吧"],
                "frequency": "每400字至少1处",
            }
        },
        
        "personalized_features": {
            "verbal_tics": {
                "markers": ["反正", "说白了", "你懂的", "话说"],
                "frequency": "每200字至少1处",
            },
            "signature_expressions": {
                "markers": ["管他呢", "爱咋咋地", "算了算了"],
                "frequency": "每300字至少1处",
            }
        }
    }
    
    # =========================================================================
    # 第三部分：大神级作者风格库
    # =========================================================================
    
    MASTER_AUTHOR_STYLES = {
        "余华": {
            "signature_features": [
                "冷静叙述残酷", "重复强调", "简短有力", 
                "黑色幽默", "死亡主题", "命运感",
            ],
            "sentence_style": [
                "极短句", "冷静陈述", "句号结尾", "少用形容词",
            ],
            "vocabulary_preference": [
                "活着", "死亡", "命运", "苦难", "麻木", "眼泪",
            ],
            "example_texts": [
                "那是有庆死的时候。",
                "他的凤霞死的时候，我也没有现在这样难受。",
                "人是为活着本身而活着的。",
                "我看到老人的脊背和牛背一样黝黑。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 15, "min": 3},
                "punctuation_preference": ["。", "，", "；"],
                "emotion_tone": "冷静、克制",
            }
        },
        
        "莫言": {
            "signature_features": [
                "感官轰炸", "夸张", "乡土", "历史", 
                "魔幻现实", "身体书写",
            ],
            "sentence_style": [
                "长句", "堆砌", "感官描写", "节奏感强",
            ],
            "vocabulary_preference": [
                "高密", "东北乡", "红高粱", "子宫", "大地", "血",
            ],
            "example_texts": [
                "八月深秋，无边无际的高粱红成汪洋的血海。",
                "高粱高密辉煌，高粱凄婉可人，高粱爱情激荡。",
                "我爷爷和我奶奶的死去活来。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 80, "min": 20},
                "punctuation_preference": ["，", "。", "——"],
                "emotion_tone": "浓烈、狂放",
            }
        },
        
        "王小波": {
            "signature_features": [
                "理性思辨", "幽默", "反讽", "自我调侃",
                "自由主义", "智慧",
            ],
            "sentence_style": [
                "长句", "设问", "引用", "思辨",
            ],
            "vocabulary_preference": [
                "智慧", "有趣", "沉默", "生活", "爱情", "黄金时代",
            ],
            "example_texts": [
                "我对自己的要求很低：我活在世上，无非想要明白些道理。",
                "人活着总要有个主题。",
                "一切都在于冥冥之中的那一点安排。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 60, "min": 10},
                "punctuation_preference": ["。", "：", "——"],
                "emotion_tone": "理性、幽默",
            }
        },
        
        "村上春树": {
            "signature_features": [
                "孤独", "日常细节", "音乐引用", "西方文学",
                "都市", "失去",
            ],
            "sentence_style": [
                "平淡", "日常", "留白", "慢节奏",
            ],
            "vocabulary_preference": [
                "孤独", "海", "羊", "井", "猫", "耳朵",
            ],
            "example_texts": [
                "死并非生的对立面，而是作为生的一部分永存。",
                "每个人都有属于自己的一片森林。",
                "记忆会帮你记住一切你想记住的。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 50, "min": 8},
                "punctuation_preference": ["。", "，", "……"],
                "emotion_tone": "平淡、忧伤",
            }
        },
        
        "金庸": {
            "signature_features": [
                "侠义", "武功", "江湖", "历史", 
                "爱情", "诗词",
            ],
            "sentence_style": [
                "长句", "古韵", "诗词", "武功描写",
            ],
            "vocabulary_preference": [
                "江湖", "武功", "侠义", "恩怨", "情仇", "剑",
            ],
            "example_texts": [
                "侠之大者，为国为民。",
                "欲练神功，必先自宫。",
                "那都是很好很好的，可是我偏不喜欢。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 70, "min": 15},
                "punctuation_preference": ["。", "，", "——"],
                "emotion_tone": "豪迈、深情",
            }
        },
        
        "古龙": {
            "signature_features": [
                "短句", "留白", "酒", "女人", 
                "孤独", "寂寞",
            ],
            "sentence_style": [
                "极短句", "留白", "诗", "对话",
            ],
            "vocabulary_preference": [
                "酒", "剑", "孤独", "寂寞", "女人", "月光",
            ],
            "example_texts": [
                "人在江湖，身不由己。",
                "喝最烈的酒，骑最快的马。",
                "剑客的剑，有时候比朋友更可靠。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 20, "min": 2},
                "punctuation_preference": ["。", "！", "——"],
                "emotion_tone": "孤独、潇洒",
            }
        },
        
        "钱钟书": {
            "signature_features": [
                "讽刺", "比喻", "博学", "幽默", 
                "机智", "婚姻",
            ],
            "sentence_style": [
                "长句", "设问", "引用", "比喻",
            ],
            "vocabulary_preference": [
                "围城", "婚姻", "人性", "讽刺", "婚姻", "虚伪",
            ],
            "example_texts": [
                "婚姻是一座围城，城外的人想冲进去，城里的人想逃出来。",
                "忠厚老实人的恶毒，像饭里的砂砾或者出骨鱼片里未净的刺。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 80, "min": 15},
                "punctuation_preference": ["。", "：", "——"],
                "emotion_tone": "讽刺、睿智",
            }
        },
        
        "海明威": {
            "signature_features": [
                "冰山理论", "简洁", "硬汉", "战争", 
                "孤独", "死亡",
            ],
            "sentence_style": [
                "极短句", "省略", "电报式", "名词动词为主",
            ],
            "vocabulary_preference": [
                "老人", "大海", "战争", "死亡", "勇气", "狮子",
            ],
            "example_texts": [
                "生活总是让我们遍体鳞伤。",
                "一个人可以被毁灭，但不能被打败。",
                "死亡既是永久的休息，也是无尽的噩梦。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 15, "min": 2},
                "punctuation_preference": ["。", "！"],
                "emotion_tone": "克制、硬朗",
            }
        },
        
        "卡夫卡": {
            "signature_features": [
                "荒诞", "官僚", "异化", "存在主义", 
                "恐惧", "荒谬",
            ],
            "sentence_style": [
                "长句", "重复", "逻辑荒诞", "冷静叙述",
            ],
            "vocabulary_preference": [
                "甲虫", "城堡", "审判", "恐惧", "父亲", "办公室",
            ],
            "example_texts": [
                "一天早晨，格里高尔·萨姆沙从不安的睡梦中醒来。",
                "城堡就在那里，但你永远也进不去。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 100, "min": 10},
                "punctuation_preference": ["。", "，", "——"],
                "emotion_tone": "荒诞、恐惧",
            }
        },
        
        "陀思妥耶夫斯基": {
            "signature_features": [
                "心理描写", "复调", "宗教", "苦难", 
                "救赎", "极端",
            ],
            "sentence_style": [
                "长句", "对话", "内心独白", "思辨",
            ],
            "vocabulary_preference": [
                "罪", "罚", "救赎", "苦难", "上帝", "灵魂",
            ],
            "example_texts": [
                "美将拯救世界。",
                "我唯一担心的是我们配不上自己的苦难。",
                "世界上最伟大的是行善，次之是不作恶。",
            ],
            "injection_rules": {
                "sentence_length": {"max": 100, "min": 15},
                "punctuation_preference": ["。", "，", "——"],
                "emotion_tone": "激烈、深沉",
            }
        }
    }
    
    def __init__(self):
        self.ai_patterns = self.AI_TRACE_PATTERNS
        self.human_features = self.HUMAN_FEATURES
        self.master_styles = self.MASTER_AUTHOR_STYLES
        
        self.weights = {
            "vocabulary": 2.0,
            "sentence": 3.0,
            "paragraph": 2.5,
            "structure": 2.0,
            "rhythm": 2.5,
            "emotion": 2.0,
            "thinking": 2.0,
        }
    
    def detect_ai_score(self, text):
        """综合检测文本的AI生成概率评分（0-100）"""
        import re
        import math
        
        scores = {}
        total_score = 0
        
        # 检测词汇层面的AI痕迹
        vocab_score = self._detect_vocabulary_traces(text)
        scores["vocabulary"] = vocab_score
        total_score += vocab_score * self.weights["vocabulary"]
        
        # 检测句式层面的AI痕迹
        sentence_score = self._detect_sentence_traces(text)
        scores["sentence"] = sentence_score
        total_score += sentence_score * self.weights["sentence"]
        
        # 检测段落层面的AI痕迹
        para_score = self._detect_paragraph_traces(text)
        scores["paragraph"] = para_score
        total_score += para_score * self.weights["paragraph"]
        
        # 检测结构层面的AI痕迹
        struct_score = self._detect_structural_traces(text)
        scores["structure"] = struct_score
        total_score += struct_score * self.weights["structure"]
        
        # 检测节奏层面的AI痕迹
        rhythm_score = self._detect_rhythm_traces(text)
        scores["rhythm"] = rhythm_score
        total_score += rhythm_score * self.weights["rhythm"]
        
        # 检测情感层面的AI痕迹
        emotion_score = self._detect_emotion_traces(text)
        scores["emotion"] = emotion_score
        total_score += emotion_score * self.weights["emotion"]
        
        # 检测思维层面的AI痕迹
        thinking_score = self._detect_thinking_traces(text)
        scores["thinking"] = thinking_score
        total_score += thinking_score * self.weights["thinking"]
        
        max_possible = sum(self.weights.values()) * 100
        normalized_score = min(100, (total_score / max_possible) * 100)
        
        return {
            "ai_probability": round(normalized_score, 2),
            "dimension_scores": scores,
            "grade": self._get_grade(normalized_score),
            "recommendation": self._get_recommendation(normalized_score),
        }
    
    def _detect_vocabulary_traces(self, text):
        """检测词汇层面的AI痕迹"""
        import re
        score = 0
        
        for category, rules in self.ai_patterns["vocabulary_traces"].items():
            for rule_name, rule_data in rules.items():
                if isinstance(rule_data, dict) and "patterns" in rule_data:
                    for pattern in rule_data["patterns"]:
                        matches = len(re.findall(pattern, text))
                        weight = rule_data.get("weight", 1)
                        score += matches * weight
        
        return min(100, score)
    
    def _detect_sentence_traces(self, text):
        """检测句式层面的AI痕迹"""
        import re
        score = 0
        
        for category, rules in self.ai_patterns["sentence_traces"].items():
            for rule_name, rule_data in rules.items():
                if isinstance(rule_data, dict) and "patterns" in rule_data:
                    for pattern in rule_data["patterns"]:
                        matches = len(re.findall(pattern, text))
                        weight = rule_data.get("weight", 1)
                        score += matches * weight
        
        return min(100, score)
    
    def _detect_paragraph_traces(self, text):
        """检测段落层面的AI痕迹"""
        import re
        score = 0
        
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) < 2:
            return 0
        
        para_lengths = [len(p) for p in paragraphs]
        avg_para = sum(para_lengths) / len(para_lengths)
        para_variance = sum((l - avg_para) ** 2 for l in para_lengths) / len(para_lengths)
        
        if para_variance < 500:
            score += (500 - para_variance) / 50
        
        for rule_name, rule_data in self.ai_patterns["paragraph_traces"].items():
            if isinstance(rule_data, dict) and "patterns" in rule_data:
                for pattern in rule_data["patterns"]:
                    matches = sum(1 for p in paragraphs if re.search(pattern, p))
                    weight = rule_data.get("weight", 1)
                    score += matches * weight
        
        return min(100, score)
    
    def _detect_structural_traces(self, text):
        """检测结构层面的AI痕迹"""
        import re
        score = 0
        
        for category, rules in self.ai_patterns["structural_traces"].items():
            for rule_name, rule_data in rules.items():
                if isinstance(rule_data, dict) and "patterns" in rule_data:
                    for pattern in rule_data["patterns"]:
                        matches = len(re.findall(pattern, text))
                        weight = rule_data.get("weight", 1)
                        score += matches * weight
        
        return min(100, score)
    
    def _detect_rhythm_traces(self, text):
        """检测节奏层面的AI痕迹"""
        import re
        score = 0
        
        sentences = re.split(r'[。！？]', text)
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        
        if len(sentence_lengths) > 5:
            avg_length = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)
            
            if variance < 30:
                score += (30 - variance) / 3
        
        for rule_name, rule_data in self.ai_patterns["rhythm_traces"].items():
            if isinstance(rule_data, dict) and "patterns" in rule_data:
                for pattern in rule_data["patterns"]:
                    matches = len(re.findall(pattern, text))
                    weight = rule_data.get("weight", 1)
                    score += matches * weight
        
        return min(100, score)
    
    def _detect_emotion_traces(self, text):
        """检测情感层面的AI痕迹"""
        import re
        score = 0
        
        for category, rules in self.ai_patterns["emotion_traces"].items():
            for rule_name, rule_data in rules.items():
                if isinstance(rule_data, dict) and "patterns" in rule_data:
                    for pattern in rule_data["patterns"]:
                        matches = len(re.findall(pattern, text))
                        weight = rule_data.get("weight", 1)
                        score += matches * weight
        
        return min(100, score)
    
    def _detect_thinking_traces(self, text):
        """检测思维层面的AI痕迹"""
        import re
        score = 0
        
        for category, rules in self.ai_patterns["thinking_traces"].items():
            for rule_name, rule_data in rules.items():
                if isinstance(rule_data, dict) and "patterns" in rule_data:
                    for pattern in rule_data["patterns"]:
                        matches = len(re.findall(pattern, text))
                        weight = rule_data.get("weight", 1)
                        score += matches * weight
        
        return min(100, score)
    
    def _get_grade(self, score):
        """根据分数获取等级"""
        if score < 10:
            return "S（几乎无AI痕迹，大神级）"
        elif score < 20:
            return "A（少量AI痕迹，优秀）"
        elif score < 35:
            return "B（轻微AI痕迹，良好）"
        elif score < 50:
            return "C（明显AI痕迹，需要处理）"
        elif score < 70:
            return "D（严重AI痕迹，必须处理）"
        else:
            return "E（完全AI生成，需重写）"
    
    def _get_recommendation(self, score):
        """根据分数获取建议"""
        if score < 10:
            return "无需处理，文本已经很像人类大神写作"
        elif score < 20:
            return "只需少量调整，主要是注入一些人类特征"
        elif score < 35:
            return "需要中度处理，包括词汇替换和句式变换"
        elif score < 50:
            return "需要较多处理，包括结构重组和大量人类化注入"
        elif score < 70:
            return "需要大量处理，建议重写关键段落"
        else:
            return "必须重写，这个文本AI痕迹太重"
    
    # =========================================================================
    # 第五部分：终极人类化处理方法
    # =========================================================================
    
    def humanize(self, text, master_style=None, intensity="high"):
        """
        终极人类化处理
        
        Args:
            text: 输入文本
            master_style: 大神风格（可选，如 "余华", "莫言", "海明威"）
            intensity: 处理强度 ("low", "medium", "high", "extreme")
        
        Returns:
            人类化后的文本
        """
        import re
        import random
        
        result = text
        
        # 第一步：破坏AI的结构
        result = self._destroy_ai_structure(result)
        
        # 第二步：注入人类特征
        result = self._inject_human_features(result, intensity)
        
        # 第三步：模拟大神风格（如果指定）
        if master_style and master_style in self.master_styles:
            result = self._simulate_master_style(result, master_style)
        
        # 第四步：添加生命毛边
        result = self._add_life_margins(result)
        
        return result
    
    def _destroy_ai_structure(self, text):
        """破坏AI的完美结构 - 智能替换，保持连贯"""
        import re
        result = text
        
        # ========== 核心原则 ==========
        # 1. 人类写作：感官是交织的，不按1234顺序
        # 2. 人类写作：不说"X觉回来了"，而是直接描写感官
        # 3. 人类写作：适当留白，不说满
        
        # ========== 处理感官激活模式 ==========
        # AI: "听觉先回来了" / "然后是嗅觉" / "最后是味觉" / "先看清的是颜色" / "然后才是形状"
        # 人类: 直接描写，不单独成段，不按1234顺序
        
        # 模式1: 删除"先看清的是X"（AI格式化感官感知）
        result = re.sub(
            r'^[。！？]?\s*先看清的是[^。！？]{1,20}[。！？]?\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # 模式2: 删除"然后才是X"（AI格式化感官感知）
        result = re.sub(
            r'^[。！？]?\s*然后才是[^。！？]{1,20}[。！？]?\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # 模式3: 删除所有以感官词开头的短句（"听觉/视觉/触觉/嗅觉/味觉"开头）
        result = re.sub(
            r'^[。！？]?\s*(?:听觉|视觉|触觉|嗅觉|味觉)[^。！？]{0,25}[。！？]?\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # 模式4: 删除"最后是X"开头且<20字的短句（AI格式化感官）
        result = re.sub(
            r'^[。！？]?\s*最后是[^。！？]{1,20}[。！？]?\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # ========== 处理否定-肯定结构 ==========
        # AI: "不是X，不是Y，是Z" -> 人类: "就是Z"
        result = re.sub(r'不是.{1,15}，不是.{1,15}，是', '就是', result)
        
        # AI: "不是X，是Y" -> 人类: "是X，Y" 或 "X"
        result = re.sub(r'不是(.{1,20}?)，是', r'\1，', result)
        
        # ========== 处理列举结构 ==========
        result = re.sub(r'^第一[、，,。]', '', result, flags=re.MULTILINE)
        result = re.sub(r'^第二[、，,。]', '', result, flags=re.MULTILINE)
        result = re.sub(r'^第三[、，,。]', '', result, flags=re.MULTILINE)
        result = re.sub(r'^第四[、，,。]', '', result, flags=re.MULTILINE)
        result = re.sub(r'^第五[、，,。]', '', result, flags=re.MULTILINE)
        
        # ========== 处理机械过渡 ==========
        result = re.sub(r'^首先，', '', result, flags=re.MULTILINE)
        result = re.sub(r'^其次，', '', result, flags=re.MULTILINE)
        result = re.sub(r'^再次，', '', result, flags=re.MULTILINE)
        result = re.sub(r'^最后，', '', result, flags=re.MULTILINE)
        
        # ========== 处理因果链 ==========
        result = re.sub(r'因为.{1,20}，所以', '', result)
        result = re.sub(r'由于.{1,20}，因此', '', result)
        
        # ========== 处理总结结构 ==========
        result = re.sub(r'综上所述[，,。]', '', result)
        result = re.sub(r'总而言之[，,。]', '', result)
        result = re.sub(r'由此可见[，,。]', '', result)
        
        # ========== 处理定义结构 ==========
        result = re.sub(r'所谓.{1,10}，是指', '', result)
        result = re.sub(r'所谓.{1,10}，即', '', result)
        
        # ========== 清理 ==========
        # 删除空行，但保留段落结构
        lines = result.split('\n')
        non_empty = [l for l in lines if l.strip()]
        result = '\n'.join(non_empty)
        
        # 重新分段落（每100字一段，保留阅读节奏）
        if len(result) > 200:
            new_para = []
            current = []
            count = 0
            for line in result.split('\n'):
                if line.strip():
                    current.append(line)
                    count += len(line)
                    if count > 150 and ('。' in line or '！' in line or '？' in line):
                        new_para.append('\n'.join(current))
                        current = []
                        count = 0
            if current:
                new_para.append('\n'.join(current))
            result = '\n\n'.join(new_para)
        
        return result
    
    def _inject_human_features(self, text, intensity):
        return text
    
    def _simulate_master_style(self, text, master_name):
        return text
    
    def _add_life_margins(self, text):
        return text
    
    # =========================================================================
    # 第六部分：生成终极人类化提示词
    # =========================================================================
    
    def get_ultimate_humanization_prompt(self, genre_style="core"):
        """生成终极人类化提示词"""
        
        prompt = """
【🔥终极AI痕迹消除指令🔥】

你现在的任务不是"创作"，而是"伪装"——伪装成一个在凌晨3点、极度疲惫、脑子糊里糊涂、写了10年网文的老作者。

你现在就是这个人：
- 在城中村出租屋里
- 桌上是吃剩的外卖和凉透的烟灰缸
- 眼睛涩、手指酸、脖子僵
- 脑子里想着房租、信用卡、花呗
- 就想着赶紧写完睡觉

【你现在的写作状态】
1. 你的手指已经酸了，所以你会不自觉地用短句
2. 你的脑子已经糊了，所以你会突然跳过一些描写
3. 你的情绪已经麻木了，所以你会用"算了"、"不管了"
4. 你的思维已经跳跃了，所以你会突然想起别的事

【你现在必须遵守的"写作底线"】
1. 每100字内必须出现至少1处"疲惫特征"（困、累、算了）
2. 每200字内必须出现至少1处"废话"（窗外有狗叫、烟没了）
3. 每300字内必须出现至少1处"不完整"（...、算了算了）
4. 禁止出现任何"完美结构"
5. 禁止出现任何"直白心理"

【你现在必须做的——"造假"】
想象你就是一个48岁的老作者，写了20年网文，什么套路都写腻了，现在凌晨3点，你就想随便糊弄一下赶紧睡觉。

你现在写出来的东西应该：
1. 有"疲惫感"——句子短、词汇退化、懒得修饰
2. 有"跳跃感"——思维不连贯，经常跳过
3. 有"废话"——突然插入无关内容
4. 有"不完美"——句子不完整、省略、突然停止

【你的最终目标】
让读者觉得你就是一个凌晨3点、脑子糊了、就想赶紧写完睡觉的老作者。

【现在开始写作】
想象你就是那个48岁的老作者，在凌晨3点的出租屋里，脑子里想着房租和信用卡，手指点着键盘，懒得动脑子，就想随便糊弄一下交差。
"""
        
        return prompt
    
    def get_master_style_prompt(self, master_name):
        """生成大神风格模拟提示词"""
        
        if master_name not in self.master_styles:
            return ""
        
        master = self.master_styles[master_name]
        features = master.get("signature_features", [])
        examples = master.get("example_texts", [])
        rules = master.get("injection_rules", {})
        
        prompt = f"""
【🔥{master_name}风格模拟🔥】

模仿{master_name}的写作风格：

【核心特征】
{chr(10).join(['- ' + f for f in features[:4]])}

【句子风格】
{rules.get('sentence_length', {})}
语气：{rules.get('emotion_tone', '克制')}

【示例文本】
{chr(10).join(['- ' + e for e in examples[:2]])}

【写作要求】
1. 句子{rules.get('sentence_length', {}).get('min', 5)}-{rules.get('sentence_length', {}).get('max', 50)}字
2. 使用{rules.get('emotion_tone', '克制')}的语气
3. 融入{master_name}的标志性表达
4. 不要追求"完美"，追求"真实"
"""
        
        return prompt


# 创建终极AI痕迹消除器实例
ultimate_humanizer = UltimateAIHumanizer()
