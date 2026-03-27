# Roxy v2.5 文件导航与快速索引

## 🎯 按功能快速查找

### 想要修改AI人格? 
→ [config/config.py](config/config.py) - `PERSONA_CONFIG`

### 想要调整情绪参数?
→ [src/core/emotion_engine.py](src/core/emotion_engine.py) - 顶部常量

### 想要修改已知关键词?
→ [src/core/event_mapper.py](src/core/event_mapper.py) - 关键词库

### 想要切换LLM模型?
→ [config/config.py](config/config.py) - `LLM_PROVIDER`, `MODEL_NAME`
→ [docs/LLM_MODELS.md](docs/LLM_MODELS.md) - 完整指南

### 想要添加梗图?
→ 放入 `/memes/` 目录
→ 在 [src/core/action_executor.py](src/core/action_executor.py) 注册

### 想要看最近发生了什么?
→ `/logs/app.log` - 应用日志
→ `/logs/message.log` - 消息日志
→ `/logs/decision.log` - 决策日志

### 想要调试某个用户的档案?
→ `/cache/user_profiles.json` - 直接查看/编辑

### 想要调试某个用户的情绪?
→ `/cache/emotion_state.json` - 直接查看/编辑

### 想要添加新的事件类型?
→ [src/core/event_mapper.py](src/core/event_mapper.py) - 编辑EVENT_EMOTION_DELTA

### 想要了解整体架构?
→ [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

### 想要快速上手?
→ [docs/README.md](docs/README.md)

### 想要部署到生产?
→ [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 📁 完整文件树 + 说明

```
bgu-qq-bridge/
│
├── 📄 README.md                          # 项目根入口 (链接到docs/)
├── 📄 requirements.txt                   # 依赖列表
├── 📄 .env                               # 环境变量模板 ⚠️ 不要提交!
├── 📄 .gitignore                         # Git忽略配置
│
├── 📁 src/                               # 💻 源代码
│   ├── 📄 __init__.py
│   ├── 📄 app.py                         # ⭐ FastAPI主应用 
│   │                                    # 事件入口 + 路由 + 后台任务
│   ├── 📄 brain.py                       # ⭐ 流程编排层
│   │                                    # 冷却→分析→决策→执行
│   │
│   ├── 📁 core/                          # 🧠 核心AI模块
│   │   ├── 📄 __init__.py
│   │   ├── 📄 emotion_engine.py          # ⭐ 6维度情绪系统
│   │   ├── 📄 user_profiles.py           # ⭐ 用户档案系统
│   │   ├── 📄 decision_engine.py         # ⭐ LLM决策引擎
│   │   ├── 📄 action_executor.py         # ⭐ 动作执行层
│   │   ├── 📄 event_mapper.py            # ⭐ 事件快速分析
│   │   └── 📄 cron_scheduler.py          # ⭐ 生物钟定时系统
│   │
│   ├── 📁 utils/                         # 🔧 工具模块
│   │   ├── 📄 __init__.py
│   │   ├── 📄 logger.py                  # 日志系统 (6个日志文件)
│   │   ├── 📄 schemas.py                 # Pydantic数据模型
│   │   ├── 📄 guard.py                   # 冷却管理系统
│   │   ├── 📄 content_refiner.py         # 文本优化 (可选Grok)
│   │   └── 📄 tts.py                     # TTS语音合成
│   │
│   └── 📁 interfaces/                    # 🌐 通信接口
│       ├── 📄 __init__.py
│       ├── 📄 onebot_client.py           # onebot v11客户端 (QQ)
│       ├── 📄 probe_api.py               # 探针API (可选)
│       └── 📄 probe_auth.py              # 认证模块 (可选)
│
├── 📁 config/                            # ⚙️ 配置管理
│   ├── 📄 __init__.py
│   ├── 📄 config.py                      # 主配置 (模型/人格/QQ)
│   └── 📄 .env                           # 环境变量 (私密信息)
│
├── 📁 tests/                             # 🧪 测试套件
│   ├── 📄 __init__.py
│   ├── 📄 test_emotion.py                # 情绪系统单元测试
│   ├── 📄 test_user_profiles.py          # 档案系统单元测试
│   ├── 📄 test_decision.py               # 决策引擎单元测试
│   ├── 📄 test_executor.py               # 执行器单元测试
│   └── 📄 test_cron_scheduler.py         # 定时任务测试
│
├── 📁 docs/                              # 📚 文档
│   ├── 📄 README.md                      # 快速入门指南
│   ├── 📄 ARCHITECTURE.md                # 架构设计文档
│   ├── 📄 DEPLOYMENT.md                  # 部署指南
│   ├── 📄 EMOTIONS.md                    # 情绪系统详解
│   ├── 📄 LLM_MODELS.md                  # LLM模型指南
│   ├── 📄 API_REFERENCE.md               # API参考
│   ├── 📄 QUICK_REFERENCE.md             # 快速参考卡
│   └── 📄 TROUBLESHOOTING.md             # 问题排查指南
│
├── 📁 scripts/                           # 🚀 工具脚本
│   ├── 📄 start_roxy.bat                 # Windows启动脚本
│   ├── 📄 start_roxy.sh                  # Unix启动脚本
│   ├── 📄 monitor.py                     # 监控脚本
│   └── 📄 backup.py                      # 备份脚本
│
├── 📁 cache/                             # 💾 缓存与数据
│   ├── 📄 emotion_state.json             # 当前情绪状态 (原子写入)
│   ├── 📄 user_profiles.json             # 用户档案库 (原子写入)
│   ├── 📁 wav/                           # TTS语音缓存
│   │   └── 📄 *.wav                      # 自动生成
│   └── 📁 dynamic_memes/                 # Pillow动态生成
│       └── 📄 *.png                      # 自动生成
│
├── 📁 memes/                             # 🖼️ 静态梗图库
│   ├── 📄 sneer.jpg                      # 冷脸
│   ├── 📄 angry.jpg                      # 生气
│   └── 📄 (其他梗图)                     # 手动维护
│
├── 📁 logs/                              # 📋 日志目录
│   ├── 📄 app.log                        # 应用启动/错误
│   ├── 📄 message.log                    # 收到消息
│   ├── 📄 decision.log                   # LLM决策过程
│   ├── 📄 action.log                     # 执行结果
│   ├── 📄 emotion.log                    # 情绪变化
│   └── 📄 profile.log                    # 档案更新
│
├── 📄 RESTRUCTURE_PLAN.md                # 🗂️ 代码整理计划
└── 📄 ROXY_V2.5_SUMMARY.md              # 📊 v2.5版本总结 (本文件)


其他说明文件:
├── ROXY_V2_GUIDE.md                      # (需整理到docs/)
├── ROXY_IMPLEMENTATION.md                # (需整理到docs/)
├── DEPLOYMENT_CHECKLIST.md               # (需整理到docs/)
├── QUICK_REFERENCE.md                    # (需整理到docs/)
├── LLM_MODEL_SWITCHING.md                # (需整理到docs/)
├── CRON_SCHEDULER_GUIDE.md               # (可存档或删除)
├── IMPLEMENTATION_REPORT.md              # (可存档)
└── 其他迁移中的文档...
```

---

## 🔧 关键配置点

| 配置项 | 位置 | 说明 |
|--------|------|------|
| LLM模型选择 | `config/config.py` | MODEL_NAME, LLM_PROVIDER |
| AI人格参数 | `config/config.py` | PERSONA_CONFIG (锋利/语音/傲娇/怜悯) |
| 情绪衰减速率 | `src/core/emotion_engine.py` | EMOTION_DECAY_RATES |
| 冷却时间 | `src/utils/guard.py` | GROUP_COOLDOWN_SECONDS, USER_COOLDOWN_SECONDS |
| 事件关键词 | `src/core/event_mapper.py` | PRAISE_KEYWORDS, INSULT_KEYWORDS等 |
| QQ机器人ID | `config/.env` | BOT_QQ |
| 监听群组ID | `config/config.py` | TARGET_GROUP_ID |
| API密钥 | `config/.env` | OPENAI_API_KEY等 |
| 日志级别 | `src/utils/logger.py` | LOG_LEVEL |

---

## 🔄 常见操作流程

### 流程1: 启动应用
```bash
cd e:\Project\bgu-qq-bridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --port 9000
```

### 流程2: 修改人格
1. 编辑 `config/config.py` 的 `PERSONA_CONFIG`
2. 重启应用
3. 观察 `logs/decision.log` 验证变化

### 流程3: 添加梗图
1. 将图片放入 `memes/` 目录
2. 编辑 `src/core/action_executor.py` - `MemeLibrary.get_meme()`
3. 重启应用或动态加载

### 流程4: 调试用户情绪
1. 查看 `cache/emotion_state.json` 中该用户的当前情绪
2. 观察 `logs/emotion.log` 的变化历史
3. 编辑JSON手动调整 (或通过事件触发)

### 流程5: 查看决策过程
1. 发送消息到机器人
2. 查看 `logs/decision.log` 的LLM输入/输出
3. 查看 `logs/action.log` 的执行结果
4. 如需调试，观察 `logs/message.log` 的原始消息

### 流程6: 切换LLM
1. 编辑 `config/config.py`
2. 设置 `LLM_PROVIDER = "openai"` 或 `"deepseek"` 或 `"grok"`
3. 确保 `.env` 中有对应的API_KEY
4. 重启应用

---

## 📊 数据文件格式速查

### emotion_state.json
```json
{
  "global": {
    "anger": 20,
    "affection": 55,
    "playfulness": 60,
    "fatigue": 15,
    "pride": 70,
    "stress": 10,
    "last_update": "2026-03-27T10:30:00"
  },
  "user_offsets": {
    "123456789": {
      "anger": 5,
      "affection": -10,
      ...
    }
  },
  "group_offsets": {
    "987654321": {
      "anger": -5,
      "stress": 8,
      ...
    }
  }
}
```

### user_profiles.json
```json
{
  "123456789": {
    "user_id": 123456789,
    "favorability": 65,
    "familiarity": 40,
    "boundary_risk": 20,
    "interaction_count": 23,
    "last_interaction": "2026-03-27T10:30:00",
    "tags": ["开玩笑", "热心"],
    "notes": "用户描述"
  }
}
```

---

## ✨ 快速参考 - API调用示例

```python
# 在任何模块中使用
from src.core.emotion_engine import apply_emotion_event, get_emotion
from src.core.user_profiles import update_user_interaction, get_user_profile
from src.utils.logger import log_emotion_change, log_decision

# 应用情绪事件
apply_emotion_event("praise", user_id=123, group_id=456)

# 获取当前情绪
emotion = get_emotion(user_id=123, group_id=456)
print(emotion.anger)  # 0-100

# 更新用户档案
update_user_interaction(123, favorability_delta=5)

# 查看用户档案
profile = get_user_profile(123)
print(profile.favorability)

# 记录日志
log_emotion_change(123, {"anger": 5, "affection": -2})
log_decision(123, "input", {"...": "..."})
```

---

## 🎯 文件优先级

| 优先级 | 文件 | 原因 |
|--------|------|------|
| P0 ⭐⭐⭐ | app.py, brain.py | 应用入口和流程编排 |
| P0 ⭐⭐⭐ | emotion_engine.py, user_profiles.py | 核心数据模型 |
| P1 ⭐⭐ | decision_engine.py, action_executor.py | 决策和执行 |
| P1 ⭐⭐ | config.py, .env | 参数配置 |
| P2 ⭐ | event_mapper.py, guard.py | 优化层 |
| P2 ⭐ | logger.py, schemas.py | 基础工具 |
| P3 | cron_scheduler.py | 可选特性 |
| P3 | content_refiner.py, tts.py | 可选特性 |

---

## 📖 学习路径

**初级开发者:**
1. 阅读 [README.md](docs/README.md)
2. 运行"启动应用"流程
3. 阅读 [QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
4. 修改 `config/config.py` 的参数观察效果

**中级开发者:**
1. 阅读 [ARCHITECTURE.md](docs/ARCHITECTURE.md)
2. 研究各个core模块的源码
3. 阅读 [LLM_MODELS.md](docs/LLM_MODELS.md) 尝试切换模型
4. 编写单元测试

**高级开发者:**
1. 研究 `brain.py` 的流程编排
2. 优化 `decision_engine.py` 的提示词
3. 扩展 `event_mapper.py` 的事件类型
4. 实现自定义LLM集成

---

**最后更新**: 2026-03-27
