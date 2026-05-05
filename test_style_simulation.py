"""
大神风格模拟测试 - 长文本
"""
import sys
sys.path.insert(0, r"d:\小说\烽火南境\小说生成器")

from ultimate_ai_humanizer import ultimate_humanizer

# 使用更长的测试文本
long_text = '''
那天傍晚，他走在路上，看到了很多的东西。天空灰蒙蒙的，路灯还没有亮起来。街道两旁的梧桐树，叶子已经开始发黄了。风吹过来，带着一股凉意。他裹紧了外套，继续往前走。

路边有一家小超市，门口贴着促销广告。他停下来，看了一眼。货架上的商品摆放得很整齐，但没什么特别的东西。他最终只买了一瓶水。

走出超市，他的手机响了。是朋友发来的消息，问他要不要去吃火锅。他犹豫了一下，回复说再看吧。
'''

print("【原文】")
print(long_text)
print("\n" + "=" * 60 + "\n")

for style in ["余华", "莫言", "王小波", "村上春树"]:
    print(f"\n【{style}风格】")
    styled = ultimate_humanizer.humanize(long_text, master_style=style, intensity='high')
    print(styled)
    print("-" * 40)

print("\n测试完成！")
