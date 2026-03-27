# Roxy v2.5 项目总结 - 情感AI QQ机器人完整架构

**项目名**: bgu-qq-bridge  
**版本**: v2.5  
**发布日期**: 2026-03-27  
**状态**: 核心模块完成 ✅  

---

## 📊 项目概览

Roxy v2.5是一个基于FastAPI的智能QQ群聊机器人，集成了：
- **6维度情绪系统** (anger/affection/playfulness/fatigue/pride/stress)
- **用户关系档案** (好感度/熟悉度/边界风险)  
- **LLM决策引擎** (支持OpenAI/Deepseek/Grok)
- **多模式回复** (语音/文字/梗图)
- **群聊冷却机制** (避免被刷屏)
- **生物钟系统** (定时自主行为)
- **动态梗图生成** (Pillow + 静态库混合)

---

## 🏗️ 核心架构(5层)

```
┌─────────────────────────────────────────────────┐
│  FastAPI 应用层 (app.py)                        │
│  - HTTP接收 OneBot事件                          │
│  - 消息路由 + 后台任务                          │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│  流程编排层 (dispatch)                          │
│  - 冷却检查 (guard.py)                          │
│  - 事件快速分析 (event_mapper.py)               │
│  - 用户交互更新 (user_profiles.py)              │
│  - 情绪状态应用 (emotion_engine.py)             │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│  决策层 (brain.py + decision_engine.py)         │
│  - LLM推理 (前缀提示 + 用户档案 + 情绪)        │
│  - JSON响应解析 (mode/style/text/meme)         │
│  - 异常处理 + 降级策略                          │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│  执行层 (action_executor.py)                    │
│  - send_voice() → TTS + OneBot语音              │
│  - send_text() → OneBot文字                     │
│  - send_image() → 梗图 → OneBot                 │
│  - 失败降级链 (voice→text→text_image)          │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│  通信层 + 持久化层                              │
│  - OneBot客户端 (src/interfaces/onebot_client)  │
│  - JSON原子写入 (emotion_state.json/profile.json)│
│  - TTS缓存 (cache/wav/)                         │
│  - 日志系统 (log/app.log 等)                    │
└─────────────────────────────────────────────────┘
```

---

## 📦 核心模块详解

### 1. **emotion_engine.py** - 6维度情绪引擎
```python
情绪维度:
┌──────────────┬────────────┬───────────┐
│ 维度         │ 衰减/min   │ 默认范围  │
├──────────────┼────────────┼───────────┤
│ anger(愤怒)   │ 4.0       │ 0-100    │
│ affection(好感)│ 1.0      │ 0-100    │
│ playfulness   │ 2.0       │ 0-100    │
│ fatigue(疲惫) │ 1.5       │ 0-100    │
│ pride(傲娇)   │ 1.0       │ 0-100    │
│ stress(压力)  │ 5.0       │ 0-100    │
└──────────────┴────────────┴───────────┘

三层架构:
1. 全局基线: 作为所有用户的初始状态
2. 用户维度偏移: 针对特定用户的个性差异
3. 群聊维度偏移: 针对特定群组的背景情绪

持久化: cache/emotion_state.json (原子操作)
```

关键API:
- `apply_emotion_event(event_type, user_id, group_id)` - 应用情绪变化
- `get_emotion(user_id, group_id)` - 获取当前情绪
- `get_global_emotion()` - 获取全局基线

### 2. **user_profiles.py** - 用户关系档案
```python
档案结构 (per user):
{
  "user_id": 123,
  "favorability": 60,        # 好感度 (0-100)
  "familiarity": 40,         # 熟悉度 (0-100)  
  "boundary_risk": 15,       # 边界风险 (0-100)
  "interaction_count": 23,   # 交互次数
  "last_interaction": "2026-03-27T10:30:00",
  "tags": ["开玩笑", "经常被怼"],
  "notes": "..."
}

关系偏差函数:
- 高好感 (>70) → +心情系数影响  
- 低好感 (<30) → -心情系数影响
- 高边界风险 (>60) → 优先文字/冷脸

关键API:
- update_user_interaction(user_id, favorability_delta)
- get_relationship_bias(user_id) → 返回该用户的态度调整
- get_user_profile(user_id)
```

持久化: cache/user_profiles.json (原子操作)

### 3. **decision_engine.py** - LLM决策引擎
```python
输入编织:
  user_message + current_emotion + user_profile + persona_config 
  → 编织为结构化提示词

LLM调用:
  OpenAI GPT-4o-mini (或 Deepseek/Grok)
  response_format={"type": "json_object"}

输出解析 (Pydantic模型):
{
  "thought": "string",           # 行为逻辑
  "emotion_update": {            # 情绪变化
    "anger": 5,
    "affection": -2,
    ...
  },
  "response_mode": "voice",      # voice/text/text_image/ignore/delay
  "response_style": "soft",      # soft/tsundere/sarcastic/cold/playful
  "content": "你在凡尔赛什么呢",  # 回复内容
  "voice_text": "你在凡尔赛什么呢",  # TTS输入(可选)
  "meme_type": "sneer"           # 梗图类型(可选)
}

风格选择:
┌────────────┬──────────────────┬────────────────┐
│ 风格       │ 触发条件         │ 特点           │
├────────────┼──────────────────┼────────────────┤
│ soft(软态) │ anger<45 &       │ 语音 + 傲娇    │
│            │ affection≥40     │ 轻快温和       │
├────────────┼──────────────────┼────────────────┤
│ tsundere   │ 高affection时    │ 欲言又止+调皮 │
│            │ 的变体           │               │
├────────────┼──────────────────┼────────────────┤
│ sarcastic  │ anger 40-65      │ 文字阴阳怪气  │
│ (刺态)     │                  │ 隐晦讽刺       │
├────────────┼──────────────────┼────────────────┤
│ cold(爆态) │ anger≥70         │ 文字+梗图冷脸 │
│            │                  │ 直接压制       │
├────────────┼──────────────────┼────────────────┤
│ playful    │ playfulness>60   │ 开玩笑模式    │
│            │                  │ 轻松幽默       │
└────────────┴──────────────────┴────────────────┘

降级策略:
  决策失败 → 使用 DEFAULT_RESPONSE_TEMPLATES
  LLM无效JSON → 返回通用回复 + 记录错误
```

### 4. **action_executor.py** - 执行层
```python
执行流程:
1. 解析决策输出 (Decision对象)
2. 检查执行前置条件
3. 按模式执行 (voice → text → image)
4. 应用情绪更新 + 记录交互

执行函数:
- send_voice(group_id, content, voice_text) 
  → TTS合成 + 缓存 + OneBot语音
  → 失败降级: text + tts_fail 日志

- send_text(group_id, content)
  → 直接OneBot文字消息

- send_image(group_id, meme_type/filepath)
  → 梗图库查询/生成 → OneBot图片
  → 支持Pillow动态生成

响应流的后处理:
  - 应用emotion_update到情绪系统
  - 更新user_interaction计数
  - 记录动作到action.log
  - 标记群组冷却 (mark_group_reply)
```

### 5. **event_mapper.py** - 事件快速分析
```python
识别事件类型:
- praise(表扬): 关键词 [好, 神, 牛, 强] → +affection +affection
- insult(辱骂): 关键词 [傻, 垃圾, 菜] → +anger -affection  
- abuse(骂街): 关键词 [你妈, NMSL] → +anger +stress
- tease(调戏): 关键词 [老色批, 你是gay] → +playfulness
- spam_risk(灌水): 检测连续相同消息 → +stress
- neutral_chat(日常): 无匹配 → 保持/微调

情绪增量预设:
```python
EVENT_EMOTION_DELTA = {
    "praise": {"affection": 3, "playfulness": 2, ...},
    "insult": {"anger": 4, "affection": -3, ...},
    ...
}
```

特点:
- 轻量级正则/关键词匹配
- O(1)预设查表
- 用于快速路径(不走LLM)
- 可与decision_engine联合使用
```

### 6. **guard.py** - 冷却管理
```python
双层冷却机制:
1. 群组级冷却: 防止群聊被刷屏
   - group_cooldown[group_id] = timestamp
   - 默认冷却时间: 30秒/条

2. 用户级冷却: 防止单用户高频率触发
   - user_cooldown[user_id] = timestamp  
   - 默认冷却时间: 10秒/条

API:
- group_in_cooldown(group_id) → bool
- user_in_cooldown(user_id) → bool
- mark_group_reply(group_id)
- mark_user_reply(user_id)
```

### 7. **cron_scheduler.py** - 生物钟系统
```python
自主行为触发 (定时任务):
- 每天08:00: 早安提示
- 每天12:00: 午餐时间吐槽
- 每天22:00: 晚安推荐
- 每周五20:00: 周末预告

实现: APScheduler (后台定时)
```

### 8. **logger.py** - 日志系统
```python
日志分类 (6个独立日志文件):
1. app.log - 启动/关闭/重错误
2. message.log - 收到消息 + 基本信息
3. decision.log - LLM输入输出 + 思考过程
4. action.log - 执行结果 + 降级记录
5. emotion.log - 情绪变化追踪 (per-user)
6. profile.log - 用户档案更新

日志级别: DEBUG | INFO | WARNING | ERROR

关键API:
- log_app(level, message)
- log_decision(user_id, prompt, response)  
- log_action(action_type, result)
- log_emotion_change(user_id, emotion_delta)
```

---

## 📋 人格配置系统

```python
# config.py - PERSONA_CONFIG
PERSONA_CONFIG = {
    "sharpness": 0.65,           # 锋利程度 (0=温和, 1=尖刻)
    "voice_preference": 0.7,     # 倾向语音 vs 文字 (0=全文字, 1=全语音)
    "tsundere_level": 0.8,       # 傲娇程度 (0=直爽, 1=完全傲娇)
    "mercy": 0.4                 # 怜悯心 (0=无情, 1=温暖)
}

LLM提示词会根据这些参数调整回复风格
```

---

## 🔄 消息处理完整流程

```
1️⃣  OneBot事件到达 (post_type=message)
    ├─ 检查: 是否为机器人自己消息 → 忽略
    ├─ 检查: 是否为私聊 → 忽略
    ├─ 检查: 是否包含触发词 (default: 前缀匹配或@机器人)
    └─ 通过检查 → 2️⃣

2️⃣  冷却检查 (guard.py)
    ├─ 群组是否在冷却? → 放入延迟队列 (delay模式)
    ├─ 用户是否在冷却? → 降低处理优先级
    └─ 通过检查 → 3️⃣

3️⃣  快速路径 - 事件分析 (event_mapper.py)
    ├─ 识别事件类型 (praise/insult/abuse/tease/...)
    ├─ 即时应用预设情绪增量 (apply_emotion_event)
    └─ 更新用户档案 (update_user_interaction)

4️⃣  慢速路径 - LLM决策 (ask_brain)
    ├─ 编织输入: user_message + emotion + profile + config
    ├─ 调用LLM: GPT-4o-mini (可切换)
    ├─ 解析JSON: Decision(mode/style/text/meme_type)
    └─ 异常时降级到 DEFAULT_RESPONSE

5️⃣  执行决策 (execute_decision)
    ├─ 检查mode: voice/text/text_image/ignore/delay
    ├─ 执行send_{voice|text|image}
    ├─ 应用emotion_update
    ├─ 更新user_interaction  
    ├─ 标记群组冷却
    └─ 记录action.log

6️⃣  后台任务 (background task)
    └─ 异步持久化: emotion_state.json + user_profiles.json (原子操作)
```

---

## 🛠️ 技术栈

| 层级      | 技术                    | 版本  |
|-----------|----------------------|-------|
| 框架      | FastAPI              | 最新  |
| 服务器    | Uvicorn              | 最新  |
| AI决策   | OpenAI / Deepseek / Grok | -   |
| 数据模型   | Pydantic             | ≥2.0  |
| 语音合成   | TTS (Edge/Google/本地) | -    |
| 动态图片   | Pillow               | 最新  |
| 定时任务   | APScheduler          | ≥3.10 |
| 通信协议   | OneBot v11 (QQ)      | -     |
| 日志      | Python logging       | 内置  |
| 持久化    | JSON (原子写入)      | -     |

---

## 📂 文件统计

```
核心模块:        7文件 (emotion_engine, user_profiles, decision_engine, action_executor, event_mapper, brain, app)
工具模块:        5文件 (logger, schemas, guard, content_refiner, tts)
通信模块:        3文件 (onebot_client, probe_api, probe_auth)
配置管理:        2文件 (config, .env)
文档:           15+ 文件 (ROXY_V2_GUIDE, IMPLEMENTATION, etc)
测试:            1文件 (test_cron_scheduler, 可扩展)
脚本:            1文件 (start_roxy.bat)
缓存目录:        4类  (emotion, profile, wav, memes)
日志目录:        6类  (app, message, decision, action, emotion, profile)

总计: ~40+文件 + 目录结构
```

---

## ✅ 已完成的特性

- ✅ 6维度情绪系统 + 自动衰减
- ✅ 用户关系档案 + 好感度/熟悉度/边界风险
- ✅ JSON决策引擎 (mode/style/content)
- ✅ 多模式执行 (voice/text/image) + 降级链
- ✅ 梗图库 (静态库 + Pillow动态生成)
- ✅ 冷却系统 (群组/用户级)
- ✅ 事件快速分析 (关键词识别)
- ✅ 生物钟系统 (定时自主行为)
- ✅ 完整日志系统 (6个分类日志)
- ✅ 原子化持久化 (emotion + profile)
- ✅ LLM模型切换 (OpenAI/Deepseek/Grok)
- ✅ 错误处理 + 降级策略

---

## 🔲 可选扩展 (v2.6+)

- ⭕ Stable Diffusion 图像生成
- ⭕ 多语言支持 (英文/日文)
- ⭕ 浮窗弹幕系统
- ⭕ 数据库集成 (MySQL/MongoDB)
- ⭕ 多群组独立人格配置
- ⭕ 用户权限系统 (管理员/禁用)
- ⭕ 机器学习个性化学习 (情绪历史分析)
- ⭕ Docker容器化部署

---

## 🚀 快速部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置.env
OPENAI_API_KEY=sk-xxx
BOT_QQ=123456789
TARGET_GROUP_ID=987654321

# 3. 配置config.py
MODEL_NAME = "gpt-4o-mini"
PERSONA_CONFIG = {...}

# 4. 启动应用
uvicorn app:app --port 9000

# 5. 监听 http://localhost:9000/message (OneBot回调)
```

---

## 📚 相关文档

- [完整使用指南](docs/ROXY_V2_GUIDE.md)
- [实现细节&测试场景](docs/ROXY_IMPLEMENTATION.md)  
- [部署检查清单](docs/DEPLOYMENT_CHECKLIST.md)
- [快速参考卡](docs/QUICK_REFERENCE.md)
- [LLM模型切换](docs/LLM_MODEL_SWITCHING.md)

---

## 🎯 项目优势

1. **模块化设计** - 每个功能独立测试/部署
2. **可观察性** - 详细的6层日志系统
3. **容错能力** - 多备选降级策略
4. **配置灵活** - 人格/冷却/LLM均可定制
5. **状态持久化** - 情绪和档案跨会话保存
6. **关系建模** - 区分用户维度和群聊维度
7. **即插即用** - 支持多种LLM后端 (OpenAI/Deepseek/Grok)

---

## ⚙️ 系统要求

- Python 3.8+
- 2+ core CPU
- 512MB+ RAM
- OneBot v11兼容的QQ机器人框架 (NapCat/Shamisen等)
- 互联网连接 (LLM API)

---

## 📞 核心联系点

| 组件          | 文件                      | 职责                    |
|--------------|---------------------------|------------------------|
| 入口          | app.py                   | FastAPI服务            |
| 调度          | brain.py                 | 流程编排                |
| 情绪管理      | emotion_engine.py        | 6维度情绪              |
| 用户管理      | user_profiles.py         | 档案维护                |
| 决策          | decision_engine.py       | LLM调用                |
| 执行          | action_executor.py       | 动作分发                |
| 通信          | onebot_client.py         | QQ消息收发             |
| 配置          | config.py                | 系统参数               |
| 日志          | logger.py                | 事件记录                |

---

**最后更新**: 2026-03-27  
**维护者**: Roxy Development Team  
**许可**: MIT/Private
