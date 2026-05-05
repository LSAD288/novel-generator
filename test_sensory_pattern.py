"""
测试新的感官序列破坏逻辑
"""
import sys
sys.path.insert(0, r"d:\小说\烽火南境\小说生成器")

from ultimate_ai_humanizer import ultimate_humanizer

test_text = """意识先回来了。

或者说，是被什么东西强行拽回来的。不是苏醒，不是清醒。像沉在深海里的人被什么东西抓住了脚踝，硬生生拖向水面。

窒息感。

林默猛地睁开眼睛，肺部像被灌满了铁砂，每一次收缩都带着粗糙的磨砺感。他张开嘴，想要呼吸，吸进去的却是黏稠的、带着金属锈蚀味的东西。

不是会议室空调送出的那种金属锈蚀。

是别的。

更腥，更厚，混着某种甜腻的、腐败的气息。像铁锈，又不是铁锈。像肉铺里隔夜的砧板。

喉咙里涌上来一股灼热的液体。他偏过头，剧烈的呕吐。

胃里是空的，吐出来的只有黄绿色的胆汁，混着唾液，在眼前溅开。

视野模糊，全是水雾。眼球像泡在盐水里，每一次转动都带来尖锐的刺痛。他眨了几下眼，睫毛黏在一起，分开时扯着皮肤。

先看清的是颜色。

灰的。暗红的。深褐的。

大面积铺开，没有边界，糊成一团。像是有人用劣质的、发霉的颜料随意泼洒在画布上，干涸后裂开细密的纹路。

然后才是形状。

一条胳膊。从手肘处断开，断口不平整，白森森的骨头刺出来，周围挂着暗红色的、已经发黑的碎肉。手指蜷曲，指甲缝里塞满了黑色的泥土。

不是玩具，不是道具。

是真的。

林默盯着那条胳膊，脑子里一片空白。他试着理解眼前的东西，用尽所有认知资源去分析：材质、颜色、比例、光影。但所有的分析都撞在一堵无形的墙上，弹回来，碎成粉末。

那条胳膊旁边，是一件破破烂烂的、沾满泥浆和暗红斑块的粗布衣服。衣服下面压着一截肠子，青灰色的，像放久了的猪大肠，表面结着一层黏糊糊的、半透明的膜。

林默的胃又开始痉挛。

他挣扎着想坐起来，手撑在地上。

触觉回来了。"""

print("=" * 80)
print("【原文 - 感官序列AI模式测试】")
print("=" * 80)
print(test_text)
print("\n" + "=" * 80)
print("【破坏AI感官序列后】")
print("=" * 80)

destroyed = ultimate_humanizer._destroy_ai_structure(test_text)
print(destroyed)

print("\n" + "=" * 80)
print("【完整人类化处理】")
print("=" * 80)

humanized = ultimate_humanizer.humanize(test_text, intensity='high')
print(humanized)

print("\n" + "=" * 80)
print("【AI检测结果】")
print("=" * 80)

original_score = ultimate_humanizer.detect_ai_score(test_text)
humanized_score = ultimate_humanizer.detect_ai_score(humanized)

print(f"原文AI概率: {original_score['ai_probability']}%")
print(f"人类化后AI概率: {humanized_score['ai_probability']}%")
print(f"检测详情: {original_score.get('details', {})}")
