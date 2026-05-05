"""
测试典型AI感官堆砌模式
"""
import sys
sys.path.insert(0, r"d:\小说\烽火南境\小说生成器")

from ultimate_ai_humanizer import ultimate_humanizer

# 典型AI感官堆砌文本
ai_sensory_text = """
听觉先回来了。

是乌鸦的叫声，沙哑而刺耳，像锈蚀的铁片互相摩擦。翅膀扑棱的声音，沉闷地拍打着空气。

然后是嗅觉。

是腐臭的味道，混着泥土的腥气和某种甜腻的、腐败的气息。像是肉铺里隔夜的砧板，又像是……

接着是触觉。

是冰冷的地面，粗糙的水泥质感，硌着他的后背。有什么东西在爬——是蛆虫？还是别的什么？

最后是味觉。

是血。铁锈一样的血，从嘴角流进嘴里，腥甜腥甜的。

视觉是最后才回来的。

或者说，是被什么东西强行拽回来的。眼前一片模糊，全是灰蒙蒙的色块，没有边界，没有形状。"""

print("=" * 80)
print("【典型AI感官堆砌文本】")
print("=" * 80)
print(ai_sensory_text)
print("\n" + "=" * 80)
print("【破坏AI感官堆砌后】")
print("=" * 80)

destroyed = ultimate_humanizer._destroy_ai_structure(ai_sensory_text)
print(destroyed)

print("\n" + "=" * 80)
print("【完整人类化处理】")
print("=" * 80)

humanized = ultimate_humanizer.humanize(ai_sensory_text, intensity='high')
print(humanized)

print("\n" + "=" * 80)
print("【AI检测结果】")
print("=" * 80)

original_score = ultimate_humanizer.detect_ai_score(ai_sensory_text)
humanized_score = ultimate_humanizer.detect_ai_score(humanized)

print(f"原文AI概率: {original_score['ai_probability']}%")
print(f"人类化后AI概率: {humanized_score['ai_probability']}%")
