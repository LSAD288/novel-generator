"""
完整的人性化处理流程测试
"""
import sys
sys.path.insert(0, r"d:\小说\烽火南境\小说生成器")

print("=" * 80)
print("测试1: 终极AI痕迹消除系统独立测试")
print("=" * 80)

from ultimate_ai_humanizer import ultimate_humanizer

ai_text = '''
黑暗在褪色。
 
不是那种开关被拉开的瞬间光亮，是浑浊的，缓慢的，像墨汁在水里一点点晕开，稀释成深浅不一的灰。有什么东西在挤压他的意识，从四面八方，粘稠的，带着温度的，沉甸甸地压下来。
 
听觉先回来了。
 
不是一只，是一群。乌鸦的叫声，短促，嘶哑，带着贪婪的兴奋。此起彼伏，像锈蚀的铁片互相摩擦。翅膀扑棱的声音，沉闷地拍打空气。
'''

print("【原文】")
print(ai_text)
print("\n" + "-" * 40 + "\n")

print("【破坏AI结构后】")
destroyed = ultimate_humanizer._destroy_ai_structure(ai_text)
print(destroyed)
print("\n" + "-" * 40 + "\n")

print("【完整人类化处理】")
humanized = ultimate_humanizer.humanize(ai_text, intensity='high')
print(humanized)
print("\n" + "-" * 40 + "\n")

print("【AI检测结果】")
result = ultimate_humanizer.detect_ai_score(ai_text)
print(f"原文AI概率: {result['ai_probability']}%")

humanized_result = ultimate_humanizer.detect_ai_score(humanized)
print(f"人类化后AI概率: {humanized_result['ai_probability']}%")

print("\n" + "=" * 80)
print("测试2: 烽火南境主程序humanize_content方法测试")
print("=" * 80)

try:
    from 烽火南境 import NovelGenerator
    
    generator = NovelGenerator()
    generator.humanize_enabled = True
    generator.humanize_intensity = 7
    
    test_content = '''黑暗在褪色。
 
不是那种开关被拉开的瞬间光亮，是浑浊的，缓慢的，像墨汁在水里一点点晕开。
听觉先回来了。
不是一只，是一群。'''
    
    print("\n【主程序humanize_content测试】")
    print("输入内容:")
    print(test_content)
    print("\n" + "-" * 40 + "\n")
    
    result = generator.humanize_content(test_content, intensity=7)
    print("输出内容:")
    print(result)
    
    detect_result = generator.detect_ai_score(result)
    print(f"\n处理后AI概率: {detect_result['ai_probability']}%")
    print(f"等级: {detect_result['grade']}")
    
except Exception as e:
    print(f"主程序测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试3: 大神风格模拟测试")
print("=" * 80)

try:
    style_test = "他走在路上，看到了很多的东西。"
    
    for style in ["余华", "莫言", "王小波", "村上春树"]:
        styled = ultimate_humanizer.humanize(style_test, master_style=style, intensity='high')
        print(f"\n【{style}风格】")
        print(styled)
        
except Exception as e:
    print(f"风格测试失败: {e}")

print("\n" + "=" * 80)
print("所有测试完成！")
print("=" * 80)
