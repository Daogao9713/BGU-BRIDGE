# Roxy v2 实现细节 & 测试指南

## 🔍 架构细节

### 情绪系统的双层设计

Roxy v2 采用"全局基线 + 相对偏移"的设计：

```
当前情绪 = 全局基线 + 用户维度偏移 + 群聊维度偏移

例子：
全局基线: anger=20, affection=55
用户 123: anger_delta=+10, affection_delta=-5  → anger=30, affection=50
同时在群 456: stress_delta=+15  → stress=25
```

**优势：**
1. 全局情绪变化会影响所有用户（Roxy 的大脑状态）
2. 用户维度允许对不同人有不同的相对态度
3. 群聊维度允许对繁忙群体做出压力升高的反应
4. 节约存储空间（只存 delta，不是完整状态）

### 时间衰减机制

```
decay = decay_rate * (秒数 / 60)
当前值 = max(0, 当前值 - decay)
```

每个 emotion 维度有独立的衰减速率：
- `anger`: 4 点/分钟 (快速冷静)
- `stress`: 5 点/分钟 (快速释压)
- `playfulness`: 2 点/分钟 (中速)
- `fatigue`: 1.5 点/分钟 (缓速)
- `affection`: 1 点/分钟 (很缓速)
- `pride`: 1 点/分钟 (很缓速)

**调用流程：**
```python
# 每次 get_emotion() 时自动触发衰减
emotion = get_emotion(user_id=123)
# 内部会计算最后更新以来的时间，并应用衰减
```

### 决策引擎的条件决策树

LLM 收到的上下文包含：
1. 当前 6 维度情绪值
2. 用户关系档案（好感度、熟悉度、边界风险）
3. 用户的消息内容
4. 人格配置（锋利程度、语音倾向等）

LLM 输出的决策包含：
1. `response_plan.mode` - 枚举: voice/text/text_image/ignore/delay
2. `response_plan.style` - 枚举: soft/tsundere/sarcastic/cold/playful
3. `response_plan.intensity` - 浮点: 0-1 表示强度
4. `content.text` - 实际的文本内容
5. `emotion_update` - 建议的情绪增量

**硬规则补充（在 Python 中）：**

虽然 LLM 做决策，但为了安全性，app.py 中可以添加硬规则覆盖：

```python
# 例子：如果pressure太高，强制降级为text
if decision.response_plan["mode"] == "voice" and emotion.stress > 80:
    decision.response_plan["mode"] = "text"
    print("由于压力过高，强制降级为文本")
```

## 🧪 测试场景

### 场景 1: 用户夸奖

```
用户消息: "你真的超棒！"

预期：
1. event_mapper 识别为 "praise"
   └─ emotion_delta: affection+10, anger-5
2. emotion_engine 应用增量
3. LLM 决策：
   - thought.emotion_trigger: "被夸奖，心情好"
   - response_plan.mode: "voice"
   - response_plan.style: "soft" 或 "playful"
   - content.text: 类似 "你也不错呢～" 或 "哼，就这样吧"
4. execute_decision 发送语音（因为 affection 高、anger 低）
```

### 场景 2: 用户辱骂

```
用户消息: "你是垃圾，去死！"

预期：
1. event_mapper 识别为 "abuse"
   └─ emotion_delta: anger+30, affection-20, pride+10
2. emotion_engine 应用增量
3. LLM 决策：
   - think.risk_level: 0.8+
   - response_plan.mode: "text_image"
   - response_plan.style: "cold"
   - content.text: "别叽歪，吵。"
   - content.meme_tag: "cold_stare"
4. execute_decision 发送文本+梗图，不发语音
```

### 场景 3: 高频骚扰（群聊）

```
同一个用户在10秒内连续发送5条"？"

预期：
1. 第 1-3 条：
   - event_mapper 识别为 "spam_risk"
   - emotion_delta: stress+8, anger+5
   - LLM 决策并回复
   
2. 第 4-5 条：
   - user_cooldown 拦截（6秒冷却）
   - 不处理，无回复
   
3. 30秒后：
   - stress 衰减 5*0.5=2.5 分钟内衰减~12.5点
   - anger 衰减 4*0.5=2 点
   - 情绪恢复到基本状态
```

### 场景 4: 熟人开玩笑 vs 陌生人说同样的话

```
消息: "你看起来像菜鸡"

熟人（familiarity=80, favorability=70）:
- LLM 判断: "这是玩笑，可能是逗我"
- response_plan.style: "playful"
- emotion_update: anger-5, playfulness+10

陌生人（familiarity=20, favorability=20）:
- LLM 判断: "这是嘲讽"
- response_plan.style: "sarcastic"
- emotion_update: anger+15, affection-5
```

## 🔄 情绪恢复曲线模拟

假设 anger 被激怒到 60：

```
时间 → anger 值变化

T0:   anger = 60  (被激怒)
T1m:  anger ≈ 56  (-4)
T2m:  anger ≈ 52  (-4)
T5m:  anger ≈ 40  (-4×3)
T10m: anger ≈ 20  (-4×5)
T15m: anger ≈ 0   (-4×6, 触底)
```

如果有新的激怒事件（+15）：

```
T6m:  新事件 anger+15  → anger = 40+15 = 55
T7m:  anger ≈ 51  (-4)
... 重新衰减循环
```

## 💾 持久化设计

### emotion_state.json 结构
```json
{
  "global_emotion": {
    "anger": 25.3,
    "affection": 50.1,
    "playfulness": 65.2,
    "fatigue": 18.5,
    "pride": 72.1,
    "stress": 12.3
  },
  "global_emotion_time": 1234567890.123,
  
  "user_emotion_delta": {
    "123": {"anger": 10, "affection": -5, ...},
    "456": {"anger": -10, "affection": 20, ...}
  },
  "user_emotion_time": {
    "123": 1234567890.123,
    "456": 1234567890.456
  },
  
  "group_emotion_delta": {
    "789": {"stress": 25, ...}
  },
  "group_emotion_time": {
    "789": 1234567890.789
  }
}
```

### user_profiles.json 结构
```json
{
  "123": {
    "user_id": 123,
    "nickname": "小明",
    "favorability": 65.5,
    "familiarity": 72.3,
    "boundary_risk": 15.0,
    "last_interaction": 1234567890.123,
    "interaction_count": 45,
    "created_at": 1230000000.0
  }
}
```

## 🎯 关系偏差系统

`get_relationship_bias(user_id)` 返回的数据用来调整情绪：

```python
bias = {
    "affection_bonus": -10,      # 当前亲近度相对于基线的偏差
    "anger_bias": 5,             # 这个用户更容易激怒你的程度
    "tolerance": 20,             # 对这个用户的容错度
    "familiarity": 45.0,
    "favorability": 55.0,
    "boundary_risk": 18.0
}
```

在 LLM 的上下文中，这些数据会被用来做决策：
- 熟人 + 高好感 → 更容易软态、发语音
- 高边界风险 → 更容易生气
- 低容错 → 更容易发冷脸

## 🛠️ 调试技巧

### 1. 查看当前情绪
```bash
# 在 Python REPL 中
from emotion_engine import get_emotion, get_global_emotion
global_e = get_global_emotion()
print(f"全局: anger={global_e.anger:.1f}, stress={global_e.stress:.1f}")

user_e = get_emotion(user_id=123)
print(f"用户123: affection={user_e.affection:.1f}")
```

### 2. 模拟情绪事件
```python
from emotion_engine import apply_emotion_event

# 模拟用户骂人
apply_emotion_event(
    "abuse",
    {"anger": 30, "affection": -20},
    user_id=123
)

# 检查效果
from emotion_engine import get_emotion
print(get_emotion(user_id=123).anger)
```

### 3. 强制重置
```python
from emotion_engine import emotion_engine
emotion_engine.reset_emotion()

from user_profiles import user_profile_manager
user_profile_manager.profiles.clear()
user_profile_manager.save_profiles()
```

### 4. LLM 响应检查
在 `decision_engine.py` 中添加调试日志：
```python
print(f"系统提示词: {system_prompt[:200]}...")
print(f"用户上下文: {user_context[:100]}...")
print(f"LLM响应: {response_text[:200]}...")
```

## ⚡ 性能优化建议

### 1. 缓存关系档案
```python
# 在 app.py 中缓存最近的查询
user_bias_cache = {}  # {user_id: bias}

if user_id not in user_bias_cache:
    user_bias_cache[user_id] = get_relationship_bias(user_id)
bias = user_bias_cache[user_id]
```

### 2. 批量情绪保存
```python
# emotion_engine 中添加自动保存定时器
import asyncio

async def auto_save_emotion():
    while True:
        await asyncio.sleep(60)  # 每分钟保存一次
        emotion_engine.save_state()
```

### 3. 异步梗图生成
```python
# 在 action_executor 中
if meme_needed:
    # 当前是同步生成，可改为子任务
    background_tasks.add_task(
        MemeLibrary.create_dynamic_meme,
        base_path, text, output_path
    )
```

## 🚨 风险控制

### 1. 防止情绪爆炸
```python
# 在 action_executor 的执行前
if decision.emotion_update.get("anger", 0) > 50:
    # 减少强度或转为冷脸
    decision.response_plan["style"] = "cold"
    decision.response_plan["intensity"] = 0.5
```

### 2. 防止频繁冷却
冷却已由 `guard.py` 控制：
- 群聊: 10秒全局冷却
- 用户: 6秒用户维度冷却

### 3. 防止信息泄露
不要在日志中打印完整的用户档案。

## 📈 监控指标建议

```python
# 添加到 app.py
metrics = {
    "total_messages": 0,
    "decisions_made": 0,
    "execution_success": 0,
    "execution_failed": 0,
    "emotion_updates": {}  # 按 event_type 统计
}
```

---

**继续迭代，让 Roxy 越来越像"真实的人"！** 🚀
