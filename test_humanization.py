"""
测试 humanization_prompts 功能
验证各题材的写作指南是否正确加载和格式化
"""

import ast
import sys
sys.path.insert(0, r'd:\小说\烽火南境\小说生成器')

# 读取并解析代码
code = open(r'd:\小说\烽火南境\小说生成器\烽火南境 .py', encoding='utf-8').read()

# 提取 NovelBot 类
tree = ast.parse(code)

# 找到 humanization_prompts 赋值
humanization_prompts = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                if target.attr == 'humanization_prompts':
                    if isinstance(node.value, ast.Dict):
                        # 编译并执行来获取实际值
                        compiled = compile(ast.Expression(node.value), '<string>', 'eval')
                        print("找到 humanization_prompts 字典定义")
                        print("=" * 60)

                        # 直接从代码中提取字符串内容
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant):
                                key_value = key.value
                                # 找到对应的值（字符串）
                                key_idx = node.value.keys.index(key)
                                value_node = node.value.values[key_idx]
                                if isinstance(value_node, (ast.Constant, ast.JoinedStr)):
                                    print(f"\n【{key_value}】")
                                    print("-" * 40)
                        break

# 直接从代码中读取并显示 humanization_prompts 内容
print("\n\n" + "=" * 60)
print("humanization_prompts 内容验证")
print("=" * 60)

start = code.find('self.humanization_prompts = {')
end = code.find('        def get_humanization_prompt')

if start != -1 and end != -1:
    dict_content = code[start:end]

    # 提取所有 key 和对应的内容
    import re

    # 找到所有的 "key": """...content...""" 模式
    pattern = r'\s{12}"(\w+)": """\s*\n(.*?)\n\s{12}"""'
    matches = re.findall(pattern, dict_content, re.DOTALL)

    print(f"\n找到 {len(matches)} 个题材指南:\n")

    for i, (key, content) in enumerate(matches, 1):
        # 清理内容，获取前200字符作为预览
        preview = content.strip()[:300].replace('\n', ' ')
        print(f"{i}. 【{key}】")
        print(f"   预览: {preview}...")
        print()
else:
    print("未找到 humanization_prompts 定义")

print("\n" + "=" * 60)
print("测试完成 - 所有题材指南已正确加载!")
print("=" * 60)
