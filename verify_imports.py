#!/usr/bin/env python3
"""
验证脚本 - 检查所有模块导入是否正确
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def test_import(module_path, name):
    """测试导入一个模块"""
    try:
        __import__(module_path)
        print(f"✅ {name}: {module_path}")
        return True
    except Exception as e:
        print(f"❌ {name}: {module_path}")
        print(f"   错误: {e}")
        return False

# 测试关键导入
tests = [
    ("config.config", "Config"),
    ("src.core.emotion_engine", "Emotion Engine"),
    ("src.core.user_profiles", "User Profiles"),
    ("src.core.decision_engine", "Decision Engine"),
    ("src.core.event_mapper", "Event Mapper"),
    ("src.core.action_executor", "Action Executor"),
    ("src.utils.logger", "Logger"),
    ("src.utils.guard", "Guard"),
    ("src.utils.schemas", "Schemas"),
    ("src.utils.tts", "TTS"),
    ("src.utils.content_refiner", "Content Refiner"),
    ("src.interfaces.onebot_client", "OneBot Client"),
    ("src.brain", "Brain"),
    ("src.app", "FastAPI App"),
]

print("=" * 60)
print("模块导入验证")
print("=" * 60)

results = []
for module, name in tests:
    results.append(test_import(module, name))

print("=" * 60)
passed = sum(results)
total = len(results)
print(f"结果: {passed}/{total} 通过")

if passed == total:
    print("✅ 所有导入验证通过！")
    sys.exit(0)
else:
    print("❌ 部分模块导入失败，请检查")
    sys.exit(1)
