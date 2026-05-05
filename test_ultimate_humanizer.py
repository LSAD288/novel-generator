#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试终极AI痕迹消除系统"""

import sys
sys.path.insert(0, r'd:\小说\烽火南境\小说生成器')

from ultimate_ai_humanizer import ultimate_humanizer, UltimateAIHumanizer

print('=' * 60)
print('✅ 终极AI痕迹消除系统导入成功！')
print('=' * 60)

# 测试AI痕迹检测
test_ai_text = '''
黑暗在褪色。
 
不是那种开关被拉开的瞬间光亮，是浑浊的，缓慢的，像墨汁在水里一点点晕开，稀释成深浅不一的灰。有什么东西在挤压他的意识，从四面八方，粘稠的，带着温度的，沉甸甸地压下来。
'''

print('\n【AI原文检测】')
result = ultimate_humanizer.detect_ai_score(test_ai_text)
print(f'AI概率: {result["ai_probability"]}%')
print(f'等级: {result["grade"]}')
print(f'建议: {result["recommendation"]}')

print('\n【维度得分】')
for dim, score in result['dimension_scores'].items():
    print(f'  {dim}: {score:.2f}')

print('\n【人类化处理 - 高强度】')
humanized = ultimate_humanizer.humanize(test_ai_text, intensity='high')
print(humanized[:300] + '...' if len(humanized) > 300 else humanized)

print('\n【人类化处理结果检测】')
result2 = ultimate_humanizer.detect_ai_score(humanized)
print(f'AI概率: {result2["ai_probability"]}% (下降了 {result["ai_probability"] - result2["ai_probability"]:.1f}%)')
print(f'等级: {result2["grade"]}')

print('\n' + '=' * 60)
print('测试完成！')
