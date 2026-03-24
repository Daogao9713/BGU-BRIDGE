# Roxy v2 情绪决策架构

## 🎭 核心架构

```
QQ消息 → OneBot/NapCat
    ↓
[FastAPI Bridge] (app.py)
    ├─ 冷却判断 (guard.py)
    └─ 事件流处理
    ↓
[事件分析层] (event_mapper.py)
    ├─ 快速消息分类
    └─ 基础情绪增量应用
    ↓
[情绪引擎] (emotion_engine.py)
    ├─ 6维度情绪管理
    ├─ 时间衰减/恢复
    └─ 用户维度 + 群聊维度
    ↓
[决策引擎] (decision_engine.py)
    ├─ LLM JSON推理
    ├─ 情绪感知
    └─ 关系/风格调整
    ↓
[执行层] (action_executor.py)
    ├─ send_voice
    ├─ send_text
    ├─ send_image
    └─ send_text_image
    ↓
QQ消息发回 (OneBot)
```

## 📊 6维度情绪系统

| 维度 | 范围 | 含义 | 衰减速率 |
|------|------|------|---------|
| `anger` | 0-100 | 愤怒程度 | 每分钟-4 |
| `affection` | 0-100 | 亲近感/好感 | 每分钟-1 |
| `playfulness` | 0-100 | 玩心/逗乐倾向 | 每分钟-2 |
| `fatigue` | 0-100 | 疲惫度 | 每分钟-1.5 |
| `pride` | 0-100 | 傲娇/自尊 | 每分钟-1 |
| `stress` | 0-100 | 群聊压力 | 每分钟-5 |

### 情绪与回复关系

**软态** (affection >= 40, anger < 45)
- 优先语音
- 语气自然、傲娇、轻快
- 示例: "你好啊～"

**刺态** (anger >= 45, anger < 70)
- 文字回复为主
- 阴阳怪气、讽刺语气
- 示例: "你这逻辑，哟，也不错嘛。"

**爆态** (anger >= 70 或特定情况)
- 文字 + 梗图
- 冷脸压制，强表达但可控
- 示例: "别重复了，吵。" + 冷眼图

## 📁 文件结构

### 核心模块

#### 1. **emotion_engine.py** - 情绪引擎
```python
from emotion_engine import get_emotion, apply_emotion_event

# 获取当前情绪（会自动应用衰减）
emotion = get_emotion(user_id=123)
print(emotion.anger, emotion.affection)  # 0-100

# 应用情绪事件
apply_emotion_event(
    event_type="praise",
    delta={"affection": +10, "anger": -5},
    user_id=123,
    group_id=456
)
```

特性：
- ✅ 全局情绪基线
- ✅ 用户维度相对偏移
- ✅ 群聊维度相对偏移
- ✅ 自动时间衰减/恢复
- ✅ 持久化存储 (`./cache/emotion_state.json`)

#### 2. **decision_engine.py** - 决策引擎
```python
from decision_engine import make_decision

decision = await make_decision(
    user_message="你好呀",
    user_id=123,
    username="小明",
    source="private",
    persona_config={...}
)

print(decision.response_plan["mode"])      # "voice" / "text" / "text_image"
print(decision.response_plan["style"])     # "soft" / "sarcastic" / "cold"
print(decision.content["text"])            # 实际回复文本
print(decision.emotion_update)             # {"anger": 5, ...}
```

输出 JSON 格式：
```json
{
  "thought": {
    "user_intent": "闲聊",
    "emotion_trigger": "none",
    "risk_level": 0.2
  },
  "emotion_update": {
    "anger": 0,
    "affection": 3,
    "playfulness": 5,
    "fatigue": 0,
    "pride": 0,
    "stress": -1
  },
  "response_plan": {
    "mode": "voice",
    "style": "soft",
    "intensity": 0.6
  },
  "content": {
    "text": "你好呀～",
    "voice_text": "你好呀。",
    "meme_tag": null,
    "meme_text": null
  }
}
```

#### 3. **action_executor.py** - 执行层
```python
from action_executor import execute_decision

success = await execute_decision(
    decision=decision_obj,
    user_id=123,
    username="小明",
    group_id=None  # 如果是群聊则填入群ID
)
```

支持的响应模式：
- `voice` - 纯语音回复
- `text` - 纯文本回复
- `text_image` - 文本 + 梗图
- `ignore` - 忽略（无回复）
- `delay` - 延迟回复

#### 4. **user_profiles.py** - 用户档案
```python
from user_profiles import get_user_profile, update_user_interaction

profile = get_user_profile(user_id=123, nickname="小明")
print(profile.favorability)    # 好感度 0-100
print(profile.familiarity)     # 熟悉度 0-100
print(profile.boundary_risk)   # 边界风险 0-100

# 更新交互统计
update_user_interaction(user_id=123, nickname="小明")
```

档案持久化: `./cache/user_profiles.json`

#### 5. **event_mapper.py** - 事件分析
```python
from event_mapper import analyze_message

event_type, emotion_delta = analyze_message("你好呀，你很厉害啊！")
# ("praise", {"affection": +10, "anger": -5, ...})
```

识别的事件类型：
- `praise` - 夸奖
- `insult` - 贬低
- `abuse` - 辱骂
- `tease` - 逗趣
- `spam_risk` - 骚扰风险
- `neutral_chat` - 中立聊天
- `empty` - 空消息

### 配置文件

#### config.py
```python
# 情绪基线
EMOTION_BASELINE = {
    "anger": 20.0,
    "affection": 55.0,
    "playfulness": 60.0,
    "fatigue": 15.0,
    "pride": 70.0,
    "stress": 10.0
}

# 人格调整
PERSONA_CONFIG = {
    "sharpness": 0.65,        # 锋利程度 [0-1]
    "voice_preference": 0.7,  # 语音倾向 [0-1]
    "meme_preference": 0.5,   # 梗图倾向 [0-1]
    "tsundere_level": 0.8,    # 傲娇程度 [0-1]
    "mercy": 0.4              # 怜悯心 [0-1]
}

# 冷却时间
GROUP_COOLDOWN_SEC = 10
USER_COOLDOWN_SEC = 6
```

## 🔄 消息处理流程

```
1. 收到 OneBot 事件
   ↓
2. 冷却判断 (guard.py)
   ↓
3. 更新用户档案 + 交互统计
   ↓
4. 事件分析 (event_mapper.py)
   └─ 应用基础情绪增量
   ↓
5. 情绪衰减/恢复计算 (emotion_engine.py)
   ↓
6. 调用 LLM 决策 (decision_engine.py)
   ├─ 输入: 当前情绪 + 用户档案 + 关系偏差
   └─ 输出: JSON 决策
   ↓
7. 执行决策 (action_executor.py)
   ├─ 应用 emotion_update
   ├─ 发送消息 (text/voice/image)
   └─ 记录日志
   ↓
8. 回复到 QQ
```

## 🎯 使用示例

### 私聊处理
```python
async def handle_private_message(event: dict):
    user_id = event.get("user_id")
    raw_message = extract_text(event)
    username = event.get("sender", {}).get("nickname", str(user_id))
    
    # 1. 更新用户
    update_user_interaction(user_id, username)
    
    # 2. 分析事件并应用初始情绪
    event_type, emotion_delta = analyze_message(raw_message)
    apply_emotion_event(event_type, emotion_delta, user_id=user_id)
    
    # 3. 获取决策
    decision = await ask_brain(
        user_text=raw_message,
        user_id=user_id,
        username=username,
        source="private"
    )
    
    # 4. 执行决策
    await execute_decision(decision, user_id, username)
```

### 查询情绪状态
```python
from emotion_engine import get_emotion, get_global_emotion

# 全局情绪
global_emotion = get_global_emotion()
print(f"全局愤怒: {global_emotion.anger}")

# 特定用户的情绪（= 全局 + 用户偏移）
user_emotion = get_emotion(user_id=123)
print(f"用户 123 的亲近感: {user_emotion.affection}")

# 自动应用群聊维度
group_emotion = get_emotion(user_id=123, group_id=456)
print(f"群 456 里的压力: {group_emotion.stress}")
```

## 🎨 梗图系统

### 梗图库
```
./memes/
  ├─ sneer.jpg        (嘲笑)
  ├─ slap_table.jpg   (拍桌子)
  ├─ speechless.jpg   (无言)
  ├─ smug.jpg         (自满)
  └─ cold_stare.jpg   (冷眼)
```

### 动态梗图生成
```python
from action_executor import MemeLibrary

success = MemeLibrary.create_dynamic_meme(
    base_image_path="./memes/smug.jpg",
    text="你是真的有勇气",
    output_path="./cache/dynamic_memes/custom_1234.jpg"
)
```

## 📝 System Prompt 说明

决策引擎会自动生成包含以下内容的系统提示词：

1. **角色定义** - "你是有情绪的 Roxy"
2. **6维度情绪** - 当前各维度数值 (0-100)
3. **关系档案** - 用户好感度、熟悉度、边界风险
4. **响应规则** - anger/stress/fatigue 阈值决策
5. **人格配置** - 锋利程度、语音倾向、傲娇程度等
6. **响应样式** - soft/tsundere/sarcastic/cold/playful

LLM 必须输出**结构化 JSON**，不允许其他内容。

## 🚀 部署建议

### 必需依赖
```bash
pip install fastapi uvicorn openai httpx pillow python-dotenv
```

### 环境变量
```.env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

NAPCAT_API=http://127.0.0.1:6090
BOT_QQ=123456789
TTS_GPU_IP=127.0.0.1
TTS_SPEAKER=绝区零-中文-铃

TRIGGER_PREFIX=Roxy,roxy
```

### 启动
```bash
uvicorn app:app --host 0.0.0.0 --port 9000
```

### 输出目录
```
./cache/
  ├─ emotion_state.json       (情绪状态)
  ├─ user_profiles.json       (用户档案)
  ├─ wav/                     (语音缓存)
  └─ dynamic_memes/           (动态梗图)
```

## 🔧 高级定制

### 调整人格强度
```python
# 可在 config.py 中修改
PERSONA_CONFIG = {
    "sharpness": 0.8,         # 更锋利
    "voice_preference": 0.9,  # 更倾向语音
    "tsundere_level": 0.9,    # 更傲娇
    "mercy": 0.2              # 更无情
}
```

### 添加自定义事件映射
编辑 `event_mapper.py`，在 `EventMapper` 类中添加新的关键词列表和事件处理。

### 梗图库扩展
1. 在 `./memes/` 目录下放入新图片
2. 在 `action_executor.py` 的 `MemeLibrary.MEME_MAP` 中添加映射
3. 具体梗图 tag 由 LLM 在 JSON 中指定

## ✅ P0-P6 优先级清单

- ✅ **P0** - 群聊触发、冷却、副作用修复
- ✅ **P1** - 情绪状态存储（用户/群聊维度 + 时间衰减）
- ✅ **P2** - JSON 决策输出 (mode/style/text/voice_text/meme)
- ✅ **P3** - 统一执行器 (send_voice/text/image)
- ⚠️ **P4** - 静态梗图库（已支持，需放入 ./memes 目录）
- 🔲 **P5** - Pillow 动态叠字梗图（已实现，可选）
- 🔲 **P6** - Grok 润色 / SD 图生成（未实现，可选）

## 📞 故障排除

### 决策失败？
- 检查 `OPENAI_API_KEY` 是否有效
- 确保模型支持 `response_format={"type": "json_object"}`
- 查看日志中的 JSON 解析错误信息

### 情绪没有衰减？
- 检查 `emotion_state.json` 是否被正确加载
- 确保有定期调用 `get_emotion()` 来触发衰减计算

### 用户档案丢失？
- 检查 `./cache/` 目录权限
- 查看 `user_profiles.json` 是否存在

### 梗图不显示？
- 确保 `./memes/` 目录下有对应的图片文件
- 检查文件路径中是否有中文或特殊字符
- 尝试用绝对路径替代相对路径

## 📚 扩展阅读

参考 `decision_engine.py` 中的系统提示词来理解情绪决策的完整逻辑。

---

**Roxy v2 - 有状态、有情绪、会变心的赛博少女** 🤖💕
