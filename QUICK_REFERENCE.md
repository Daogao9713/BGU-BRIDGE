# Roxy v2 快速参考卡

## 📌 模块导入清单

```python
# 情绪管理
from emotion_engine import get_emotion, get_global_emotion, apply_emotion_event

# 用户档案
from user_profiles import get_user_profile, update_user_interaction, get_relationship_bias

# 决策与执行
from decision_engine import make_decision, DecisionOutput
from action_executor import execute_decision

# 事件分析
from event_mapper import analyze_message
```

## 🎮 常用操作代码片段

### 获取情绪状态
```python
# 全局情绪
global_emotion = get_global_emotion()
print(f"anger={global_emotion.anger:.1f}")

# 用户相对情绪
user_emotion = get_emotion(user_id=123)

# 带群聊维度的情绪
group_emotion = get_emotion(user_id=123, group_id=456)
```

### 应用情绪事件
```python
from emotion_engine import apply_emotion_event

# 夸奖
apply_emotion_event("praise", 
    {"affection": +10, "anger": -5}, 
    user_id=123)

# 辱骂
apply_emotion_event("abuse",
    {"anger": +30, "affection": -20, "pride": +10},
    user_id=123)

# 群聊压力
apply_emotion_event("spam_risk",
    {"stress": +15, "anger": +5},
    user_id=123, group_id=456)
```

### 获取用户档案
```python
from user_profiles import get_user_profile, get_relationship_bias

profile = get_user_profile(123, "小明")
print(f"好感: {profile.favorability}")

bias = get_relationship_bias(123)
print(f"容错度: {bias['tolerance']}")
```

### 做出决策
```python
from decision_engine import make_decision

decision = await make_decision(
    user_message="你好呀",
    user_id=123,
    username="小明",
    source="private"
)

print(decision.response_plan["mode"])     # voice/text/text_image
print(decision.response_plan["style"])    # soft/sarcastic/cold
print(decision.content["text"])
print(decision.emotion_update)
```

### 执行决策
```python
from action_executor import execute_decision

success = await execute_decision(
    decision=decision,
    user_id=123,
    username="小明",
    group_id=None
)
```

### 分析消息
```python
from event_mapper import analyze_message

event_type, emotion_delta = analyze_message("你真的超强")
# ("praise", {"affection": +10, "anger": -5, ...})
```

## 📊 情绪值范围参考

| 概念 | Anger | Affection | Playfulness | Fatigue | Pride | Stress |
|------|-------|-----------|------------|---------|-------|--------|
| 完全平静 | 0-10 | 70-100 | 0-20 | 0-10 | 60-80 | 0-5 |
| 正常 | 20-40 | 40-60 | 40-70 | 10-30 | 60-80 | 5-20 |
| 烦躁 | 40-60 | 20-40 | 20-50 | 30-60 | 40-70 | 20-70 |
| 生气 | 60-80 | 0-20 | 0-30 | 50-80 | 50-90 | 40-80 |
| 爆炸 | 80+ | 0-10 | 10-40 | 70+ | 70+ | 60+ |

## 🎯 决策模式对照表

| Mode | 何时使用 | 条件 |
|------|----------|------|
| `voice` | 心情好时 | anger<45, affection≥40 |
| `text` | 有点烦时 | anger 40-60, stress 高 |
| `text_image` | 生气时 | anger≥60, 需要强烈表达 |
| `ignore` | 不想理 | stress/fatigue 极高，或垃圾消息 |
| `delay` | 需要冷静 | anger 爆炸，需要先冷却 |

## 🎨 梗图 Tag 对照表

| Tag | 含义 | 情绪 |
|-----|------|------|
| `sneer` | 嘲笑 | sarcastic, anger 中 |
| `slap_table` | 拍桌子 | angry, indignant |
| `speechless` | 无言 | cold, tired |
| `smug` | 自满 | playful, proud |
| `cold_stare` | 冷眼 | cold, angry 高 |

## 🚀 常见故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 一直发语音 | affection 一直很高 | - 让用户骂你降低 affection<br>- 调整 PERSONA_CONFIG["voice_preference"] |
| 一直不发语音 | anger 太高或 stress 太高 | - 等待衰减<br>- 手动 apply_emotion_event 降低 anger |
| 表情不生动 | playfulness 太低 | - 互动更多<br>- 调整 event_mapper 提升 playfulness |
| 忽视所有消息 | stress 爆表 | - 等待 10 分钟衰减<br>- 检查是否垃圾消息触发器 |
| 总是发文字 | PERSONA_CONFIG["voice_preference"] < 0.5 | 改大这个值 |

## 📝 JSON 输出完整示例

```json
{
  "thought": {
    "user_intent": "打招呼",
    "emotion_trigger": "neutral",
    "risk_level": 0.1
  },
  "emotion_update": {
    "anger": -1,
    "affection": 2,
    "playfulness": 2,
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

## 🛍️ 配置速查

### 快速调整人格
```python
# 在 config.py 中修改

# 更锋利
PERSONA_CONFIG["sharpness"] = 0.8

# 更倾向发语音
PERSONA_CONFIG["voice_preference"] = 0.85

# 更傲娇
PERSONA_CONFIG["tsundere_level"] = 0.9

# 更无情
PERSONA_CONFIG["mercy"] = 0.2
```

### 快速调整衰减速率
```python
# 在 emotion_engine.py 的 EmotionEngine 类中

DECAY_RATES = {
    "anger": 2.0,         # 更快冷静
    "stress": 8.0,        # 更快释压
    "affection": 0.5      # 更缓慢遗忘
}
```

## 🔌 集成到自己的 LLM 应用

```python
# 在你的 LLM 应用中
import asyncio
from emotion_engine import get_emotion
from decision_engine import make_decision
from action_executor import execute_decision

async def chat_with_roxy(user_id, message):
    # 获取决策
    decision = await make_decision(
        user_message=message,
        user_id=user_id,
        username="用户",
        source="private"
    )
    
    # 返回文本或执行
    return decision.content["text"]
```

## 🎓 学习路径

1. **理解基础** → 读 ROXY_V2_GUIDE.md
2. **查看实现** → 读 emotion_engine.py + decision_engine.py
3. **运行示例** → 在 Python REPL 中玩情绪API
4. **定制规则** → 修改 event_mapper.py 的关键词
5. **调教人格** → 修改 config.py 的 PERSONA_CONFIG
6. **深度定制** → 修改 decision_engine.py 的 system_prompt

## 🔑 核心哲学

```
Roxy 不是无脑回复机，而是：
1. 有"心情"（6维度情绪）
2. 有"记忆"（用户档案）
3. 有"性格"（人格配置）
4. 能"变心"（情绪衰减/恢复）
5. 会"反思"（LLM 决策）
```

---

**提示：把这个卡打印出来贴在你的开发空间！** 📌
