# -*- coding: utf-8 -*-
"""AIGC 终检（最后一道闸）：规则层 + 统计层 + 本地检测模型融合。

规则层与阈值来自公开 skill「humanize-chinese v5.0」(brycewang-stanford, MIT)：
- 20+ 规则维度：三段式、机械连接词、空洞宏大词、AI 高频词、模板句式、填充废话、标点滥用、修辞堆砌
- 统计特征：句长 CV、短句占比、段落长度 CV、段内句长 CV、跨段 trigram 重复、逗号密度
- 分档：0-24 LOW / 25-49 MEDIUM / 50-74 HIGH / 75-100 VERY HIGH；改写目标降到 35 以下
- 该 skill 的融合方式是 rule×0.2 + LR×0.8；本模块用统计特征近似 LR，取 rule×0.45 + stat×0.55，
  再与本地 AIGC_detector_zhv3 的模型概率取并集（模型高概率直接判不通过）。
纯 Python，无第三方依赖。
"""
import re

PASS_LINE = 30          # ≤30 视为通过（skill 的目标区间，比 35 更严一点）
ALERT_LINE = 50         # ≥50 HIGH

_CRITICAL = [
    r"首先[，,].{0,40}其次[，,].{0,40}最后", r"一方面[，,].{0,40}另一方面",
    r"第一[，,].{0,30}第二[，,]", r"其一[，,].{0,30}其二",
    r"综上所述", r"不难发现", r"由此可见", r"不言而喻", r"归根结底",
    r"值得注意的是", r"与此同时", r"不仅如此", r"换句话说", r"更重要的是", r"总而言之",
    r"赋能", r"闭环", r"数字化转型", r"协同增效", r"降本增效", r"深度融合", r"多维度", r"系统性",
]
_HIGH = [
    r"助力", r"彰显", r"凸显", r"底层逻辑", r"抓手", r"触达", r"沉淀", r"复盘", r"迭代", r"破圈", r"颠覆",
    r"值得一提的是", r"众所周知", r"毫无疑问", r"具体来说", r"简而言之", r"可以说", r"某种程度上",
    r"随着.{0,12}(?:发展|进步|推进)", r"在当今.{0,8}时代", r"在.{0,12}的背景下",
    r"作为.{0,12}的重要组成部分", r"这不仅.{0,20}更是", r"既.{0,10}也.{0,10}更",
]
_EMPTY_LYRIC = [
    r"复杂的情感|复杂的情绪|百感交集|五味杂陈|思绪万千|心潮澎湃|涌上心头|难以言喻|无可名状",
    r"仿佛一切|时间仿佛静止|一切都已注定|多年以后|殊不知|他不知道的是",
    r"仿佛整个世界|仿佛在诉说着|这一刻，?时间",
]
_SEMI = re.compile(r"[；;]")

_FEATURE_W = {
    "sent_cv": 0.26, "short_ratio": 0.14, "para_cv": 0.16,
    "inner_cv": 0.20, "trigram_rep": 0.14, "comma": 0.10,
}


def _norm(s):
    return re.sub(r"\s+", "", str(s or ""))


def _sents(text):
    return [s.strip() for s in re.findall(r"[^。！？!?…\n]+[。！？!?…]?", str(text or "")) if s.strip()]


def _paras(text):
    return [p.strip() for p in str(text or "").split("\n") if p.strip()]


def _cv(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return 0.0
    avg = sum(vals) / len(vals)
    if not avg:
        return 0.0
    var = sum((x - avg) ** 2 for x in vals) / len(vals)
    return (var ** 0.5) / avg


def _trigram_rep(paras):
    """跨段 trigram 重复率：AI 长文常用同一套句式起头"""
    if len(paras) < 3:
        return 0.0
    heads = []
    for p in paras:
        t = _norm(p)
        heads += [t[i:i + 3] for i in range(0, max(1, min(len(t) - 2, 24)))]
    if not heads:
        return 0.0
    return 1 - (len(set(heads)) / len(heads))


def _rule_score(text):
    raw = str(text or "")
    hits = []
    score = 0.0
    for pat in _CRITICAL:
        n = len(re.findall(pat, raw))
        if n:
            hits.append("三段式/机械连接")
            score += min(16, 7 * n)
    for pat in _HIGH:
        n = len(re.findall(pat, raw))
        if n:
            hits.append("AI 高频词")
            score += min(12, 3.5 * n)
    for pat in _EMPTY_LYRIC:
        n = len(re.findall(pat, raw))
        if n:
            hits.append("空泛抒情")
            score += min(22, 5 * n)
    n = len(_SEMI.findall(raw))
    if n >= 3:
        hits.append("分号过多")
        score += min(8, n * 1.2)
    # 同一个词反复出现（AI 词汇贫乏）
    words = re.findall(r"[\u4e00-\u9fa5]{2,3}", _norm(raw))
    freq = {}
    for w in words:
        if w in ("什么", "自己", "一个", "没有", "起来", "之后", "时候"):
            continue
        freq[w] = freq.get(w, 0) + 1
    if freq:
        top = max(freq.values())
        if top >= 6 and len(words) >= 60:
            hits.append("用词重复")
            score += min(8, (top - 5) * 1.5)
    return min(100.0, score), list(dict.fromkeys(hits))


def _stat_score(text):
    raw = str(text or "")
    sents = _sents(raw)
    paras = _paras(raw)
    lens = [len(_norm(s)) for s in sents] or [0]
    cv = _cv(lens)
    short = sum(1 for x in lens if x <= 10) / max(1, len(lens))
    para_cv = _cv([len(_norm(p)) for p in paras]) if len(paras) >= 3 else 0.55
    inner = _cv([_cv([len(_norm(s)) for s in _sents(p)]) for p in paras if len(_sents(p)) >= 2]) if len(paras) >= 2 else 0.5
    tri = _trigram_rep(paras)
    chars = max(1, len(_norm(raw)))
    comma = raw.count("，") * 100.0 / chars

    def low_bad(v, good, bad):
        """v 越接近 bad 越像 AI，返回 0~1"""
        if good == bad:
            return 0.0
        return max(0.0, min(1.0, (v - good) / (bad - good)))

    feats = {
        "sent_cv": low_bad(cv, 0.55, 0.18),
        "short_ratio": low_bad(short, 0.32, 0.05),
        "para_cv": low_bad(para_cv, 0.5, 0.12),
        "inner_cv": low_bad(inner, 0.45, 0.10),
        "trigram_rep": max(0.0, min(1.0, (tri - 0.25) / 0.4)),
        "comma": max(0.0, min(1.0, (comma - 5.0) / 4.0)),
    }
    score = sum(feats[k] * w for k, w in _FEATURE_W.items()) / sum(_FEATURE_W.values()) * 100
    return min(100.0, score), {k: round(v, 2) for k, v in feats.items()}


def explain():
    """把检测方式讲清楚，直接喂给改写模型"""
    return ("【终检怎么打分】规则层×0.45 + 统计层×0.55，≤%d 分算通过。\n"
            "规则层：三段式/机械连接每次 7 分、AI 高频词 3.5 分、空泛抒情 5 分、分号过多、用词重复。\n"
            "统计层权重：句长变异 0.26、短句占比 0.14、段落长度变异 0.16、段内句长变异 0.20、"
            "跨段 trigram 重复 0.14、逗号密度 0.10；句长越均匀、短句越少、段落越齐，分越高。\n"
            "字数够长时再叠加本地检测模型概率，模型判 AI 会直接拉高总分。"
            % PASS_LINE)


def advice(text):
    """按当前失分项给出针对性的改法，让模型照着改"""
    s = score(text)
    f = s["feats"]
    hits = s["hits"]
    tips = []
    if f.get("sent_cv", 0) >= 0.35:
        tips.append("句长太齐：把相邻长句拆出一两个 5-8 字短句，再留一个长句，别句句一样长。")
    if f.get("short_ratio", 0) >= 0.35:
        tips.append("几乎没有短句")
    if f.get("para_cv", 0) >= 0.35:
        tips.append("段落长度太匀：让有的段只有一两句，有的四五句，别切豆腐块。")
    if f.get("inner_cv", 0) >= 0.35:
        tips.append("段内句长太接近：一长一短错开，长句负责铺，短句负责落。")
    if f.get("trigram_rep", 0) >= 0.3:
        tips.append("段首/跨段重复多：换开头，别每段都用同一套起手式。")
    if f.get("comma", 0) >= 0.35:
        tips.append("逗号太密：长句在转折处用句号断开。")
    if "空泛抒情" in hits:
        tips.append("删掉空泛抒情套话（复杂的情感/难以言喻/仿佛一切/时间仿佛静止），换成具体的动作、物件或画面；注意别把优美的比喻、形容词也一起删了。")
    if "三段式/机械连接" in hits:
        tips.append("去掉首先/其次/最后/总之/值得注意的是这类连接语，让话直接接上。")
    if "AI 高频词" in hits:
        tips.append("换掉助力/彰显/维度/底层逻辑/闭环这类词。")
    if "用词重复" in hits:
        tips.append("同一个词反复出现，换同义说法。")
    if "分号过多" in hits:
        tips.append("少用分号，改成句号断开。")
    if not tips:
        tips.append("整体已接近：继续把抽象句换成具体动作、物件和光线。")
    return {"score": s["score"], "level": s["level"], "hits": hits,
            "feats": f, "tips": tips}


def suspects(text, k=3):
    """最可疑的几段（给改写模型点名）"""
    rows = para_scores(text)
    rows.sort(key=lambda r: -r["score"])
    return [{"index": r["index"], "score": r["score"], "text": r["text"][:80]} for r in rows[:k]]


def level_of(score):
    s = float(score or 0)
    if s <= 24:
        return "LOW"
    if s < ALERT_LINE:
        return "MEDIUM"
    if s < 75:
        return "HIGH"
    return "VERY HIGH"


def score(text):
    """返回规则+统计的 0~100 AIGC 分、命中原因、特征"""
    r, hits = _rule_score(text)
    st, feats = _stat_score(text)
    total = r * 0.45 + st * 0.55
    return {"score": int(round(min(100, max(0, total)))), "rule": int(round(r)),
            "stat": int(round(st)), "hits": hits, "feats": feats,
            "level": level_of(total)}


def para_scores(text):
    """逐段打分，用于定位需要补改的段落"""
    out = []
    for i, p in enumerate(_paras(text), 1):
        if len(_norm(p)) < 20:
            continue
        s = score(p)
        out.append({"index": i, "score": s["score"], "hits": s["hits"], "text": p})
    return out


def check(text, model_p=None):
    """终检：规则统计分 + 本地模型概率。pass 才算通过"""
    s = score(text)
    sc = s["score"]
    why = list(s["hits"])
    if model_p is not None:
        mp = int(round(model_p * 100))
        sc = max(sc, int(round(sc * 0.6 + mp * 0.4)))
        if model_p >= 0.75:
            why.append("检测模型判为 AI（%d%%）" % mp)
        elif model_p >= 0.55:
            why.append("检测模型偏高（%d%%）" % mp)
    passed = sc <= PASS_LINE and (model_p is None or model_p < 0.6)
    return {
        "pass": bool(passed),
        "score": int(sc),
        "level": level_of(sc),
        "rule": s["rule"],
        "stat": s["stat"],
        "hits": list(dict.fromkeys(why)),
        "feats": s["feats"],
        "model_p": None if model_p is None else round(float(model_p), 3),
        "line": PASS_LINE,
    }
