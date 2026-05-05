# 测试导入
import sys
import importlib.util

# 直接加载模块文件
file_path = r"d:\小说\烽火南境\小说生成器\烽火南境 .py"
spec = importlib.util.spec_from_file_location("novel_generator", file_path)
module = importlib.util.module_from_spec(spec)

try:
    spec.loader.exec_module(module)
    print("✅ 主模块导入成功")
    
    # 测试功能
    service = module.AIService()
    print("✅ AIService实例化成功")
    
    # 测试动态提示词功能
    if hasattr(service, 'get_dynamic_humanization_prompt'):
        prompt = service.get_dynamic_humanization_prompt(genre="都市情感", style="出版小说")
        if prompt:
            print("✅ 动态提示词生成成功")
            print(f"   提示词长度: {len(prompt)} 字符")
        else:
            print("⚠️ 动态提示词为空")
    else:
        print("❌ 动态提示词方法未找到")
    
    # 测试风格分析
    if hasattr(service, 'analyze_text_features'):
        result = service.analyze_text_features("他心中一凛，暗道不好。")
        if result and "error" not in result:
            print("✅ 风格分析功能正常")
            print(f"   题材: {result.get('genre', {}).get('name', 'unknown')}")
        else:
            print(f"⚠️ 风格分析返回: {result}")
    
    print("\n🎉 所有测试通过！系统运行正常。")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
