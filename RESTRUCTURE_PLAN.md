# 代码库重组计划 (v2.5)

## 📋 目录结构规划

```
bgu-qq-bridge/
├── src/                                    # 源代码
│   ├── __init__.py
│   ├── core/                              # 核心情感AI模块
│   │   ├── __init__.py
│   │   ├── emotion_engine.py              # 6维度情绪系统 (anger/affection/playfulness/fatigue/pride/stress)
│   │   ├── user_profiles.py               # 用户关系档案系统
│   │   ├── decision_engine.py             # LLM决策引擎 (JSON输出)
│   │   ├── action_executor.py             # 动作执行层 (voice/text/image/ignore)
│   │   ├── event_mapper.py                # 事件快速分析 (关键词识别)
│   │
│   ├── utils/                             # 工具模块
│   │   ├── __init__.py
│   │   ├── logger.py                      # 日志系统 (app/message/decision/action/emotion/profile)
│   │   ├── schemas.py                     # Pydantic数据模型
│   │   ├── guard.py                       # 冷却管理(群组/用户级)
│   │   ├── content_refiner.py             # 内容优化 (可选Grok润色)
│   │   ├── tts.py                         # TTS语音合成
│   │
│   ├── interfaces/                        # 通信接口层
│   │   ├── __init__.py
│   │   ├── onebot_client.py               # OneBot v11客户端 (QQ通信)
│   │   ├── probe_api.py                   # 探针API (可选)
│   │   ├── probe_auth.py                  # 认证模块 (可选)
│   │
│   ├── brain.py                           # 决策流程编排
│   ├── app.py                             # FastAPI主应用 (冷却→分析→决策→执行)
│
├── config/                                # 配置管理
│   ├── __init__.py
│   ├── config.py                          # 主配置文件 (模型/人格/QQ)
│   ├── .env                               # 环境变量 (密钥/API)
│
├── tests/                                 # 测试Suite
│   ├── __init__.py
│   ├── test_emotion.py                    # 情绪系统测试
│   ├── test_user_profiles.py              # 用户档案测试
│   ├── test_decision.py                   # 决策引擎测试
│   ├── test_executor.py                   # 执行器测试
│   ├── test_cron_scheduler.py             # 定时任务测试
│
├── docs/                                  # 文档汇总
│   ├── README.md                          # 项目快速入门
│   ├── ARCHITECTURE.md                    # 架构设计文档
│   ├── DEPLOYMENT.md                      # 部署指南
│   ├── EMOTIONS.md                        # 情绪系统详解
│   ├── LLM_MODELS.md                      # LLM模型切换指南
│   ├── API_REFERENCE.md                   # API参考
│   └── (其他必要文档)
│
├── scripts/                               # 工具脚本
│   ├── start_roxy.bat                     # Windows启动脚本
│   ├── start_roxy.sh                      # Linux启动脚本
│   ├── monitor.py                         # 监控脚本
│
├── cache/                                 # 缓存与数据
│   ├── emotion_state.json                 # 全局+用户情绪状态
│   ├── user_profiles.json                 # 用户档案库
│   ├── wav/                               # TTS语音缓存
│   └── dynamic_memes/                     # 动态生成梗图
│
├── memes/                                 # 静态梗图库
│   └── (各种梗图)
│
├── logs/                                  # 日志目录
│   ├── app.log
│   ├── message.log
│   ├── decision.log
│   ├── action.log
│   ├── emotion.log
│   └── profile.log
│
├── requirements.txt                       # 依赖列表
├── README.md                              # 根目录README
└── (其他配置文件: .env, .gitignore等)
```

## 🔄 文件迁移映射

### 核心模块 → src/core/
- emotion_engine.py → src/core/emotion_engine.py
- user_profiles.py → src/core/user_profiles.py
- decision_engine.py → src/core/decision_engine.py
- action_executor.py → src/core/action_executor.py
- event_mapper.py → src/core/event_mapper.py

### 工具模块 → src/utils/
- logger.py → src/utils/logger.py
- schemas.py → src/utils/schemas.py
- guard.py → src/utils/guard.py
- content_refiner.py → src/utils/content_refiner.py
- tts.py → src/utils/tts.py

### 通信模块 → src/interfaces/
- onebot_client.py → src/interfaces/onebot_client.py
- probe_api.py → src/interfaces/probe_api.py
- probe_auth.py → src/interfaces/probe_auth.py

### 应用主体 → src/
- app.py → src/app.py
- brain.py → src/brain.py

### 配置 → config/
- config.py → config/config.py
- .env → config/.env

### 文档 → docs/
- ROXY_V2_GUIDE.md → docs/README.md
- ROXY_IMPLEMENTATION.md → docs/ARCHITECTURE.md
- DEPLOYMENT_CHECKLIST.md → docs/DEPLOYMENT.md
- QUICK_REFERENCE.md → docs/QUICK_REFERENCE.md
- LLM_MODEL_SWITCHING.md → docs/LLM_MODELS.md
- 其他文档进行整合/归档

### 脚本 → scripts/
- start_roxy.bat → scripts/start_roxy.bat
- test_cron_scheduler.py → tests/test_cron_scheduler.py

### 保留在根目录
- requirements.txt
- README.md (新建，指向docs/)
- .env
- .gitignore
- cron_scheduler.py (核心模块，需要考虑位置 - 可放src/utils或src/core)

## 📝 配置更新清单

迁移后需要更新的导入语句：
```python
# 旧: from emotion_engine import ...
# 新: from src.core.emotion_engine import ...

# 旧: from logger import ...
# 新: from src.utils.logger import ...

# 旧: from onebot_client import ...
# 新: from src.interfaces.onebot_client import ...
```

或者使用相对导入(如果从src/app.py调用):
```python
from core.emotion_engine import apply_emotion_event
from utils.logger import log_app
from interfaces.onebot_client import OneBotClient
```

## ✅ 优先级

**Phase 1 (立即执行):**
1. 创建目录结构 ✅
2. 生成整理计划文档 ✅
3. 列出所需的导入语句更新

**Phase 2 (可选):**
1. 移动核心文件
2. 更新所有导入
3. 测试并验证

**Phase 3 (文档整理):**
1. 合并重复文档
2. 生成统一的API参考
3. 创建快速入门指南

## 🎯 整理的好处

1. **可维护性**: 代码分层清晰，易于定位
2. **扩展性**: 新功能可按类型添加到对应目录
3. **可读性**: 文档集中管理，避免重复
4. **测试**: 测试用例与源码分离，便于CI/CD
5. **部署**: 脚本和启动方式统一管理
