# 伪造事件引擎 - 快速参考卡

## 🔄 核心概念

| 概念 | 说明 |
|------|------|
| **伪造事件** | 由 cron_scheduler 生成的虚拟 OneBot 消息事件 |
| **系统提示** | 【系统提示】开头的特殊指令，让 LLM 理解这是内部心理活动 |
| **生物钟** | RoxyBiorhythm 类，管理所有定时自发行为 |
| **APScheduler** | 异步任务调度库，处理 cron/interval 任务 |

---

## ⚙️ 三步启用

### 1️⃣ 配置群号
```bash
# .env 中添加或修改
TARGET_GROUP_ID="123456789"
```

### 2️⃣ 启动服务
```bash
uvicorn app:app --port 9000
```

### 3️⃣ 观察日志
```bash
# 会看到
[生物钟] 已启动（冷场检测: 每30分钟，新闻评论: 每天15:00）
```

---

## 📅 默认定时任务

| 任务 | 触发时间 | 作用 |
|------|---------|------|
| `check_boredom` | 每 30 分钟 | 检测群聊冷场（>4小时）→ 主动冒泡 |
| `fetch_and_roast_news` | 每天 15:00 | 抓取热点新闻 → 毒舌评论 |

---

## 🎮 快速修改配置

### 改变新闻评论时间
```python
# cron_scheduler.py line ~170
self.scheduler.add_job(
    self.fetch_and_roast_news,
    'cron',
    hour=16,      # ← 改成 16 点
    minute=30,    # ← 改成 30 分
    ...
)
```

### 改变冷场检测频率
```python
# cron_scheduler.py line ~155
self.scheduler.add_job(
    self.check_group_boredom,
    'interval',
    minutes=60,   # ← 改成每 60 分钟检查一次
    ...
)
```

### 改变冷场阈值
```python
# cron_scheduler.py line ~120
boredom_threshold = 7200  # ← 改成 2 小时而不是 4 小时
```

---

## 🚦 事件流程図

```mermaid
定时器触发
    ↓
生物钟生成伪造事件 (_synthetic=true)
    ↓
handle_synthetic_event(event)
    ↓
handle_group_message(event)  [复用现有逻辑]
    ↓
【完整链路】
├─ event_mapper.analyze_message()      [分析事件]
├─ emotion_engine.apply_emotion_event() [更新情绪]
├─ decision_engine.ask_brain()         [LLM决策，接收【系统提示】]
├─ action_executor.execute_decision()  [执行回复]
└─ 保存状态到 cache/
    ↓
发送到 QQ
```

---

## 📝 系统提示语法

```
【系统提示】前缀 + 指令内容

示例 1 (冷场):
【系统提示】群里已经4个小时没人说话了。
你现在感到非常无聊，请立即主动冒泡。

示例 2 (新闻):
【系统提示】你刚看到新闻：「xxx」
请用毒舌言语评论，回复模式必须是 text 或 text_image。

示例 3 (自定义):
【系统提示】现在是你的生日，群里的人都忘了。
你感到失落和生气，请吐槽一下。
```

---

## 🔍 监控和日志

### 应用启动日志
```bash
logs/app.log

[主程序] FastAPI 应用启动，生物钟已初始化
[生物钟] RoxyBiorhythm 初始化完成
[生物钟] 事件处理函数已注册
[生物钟] 已启动（冷场检测: 每30分钟，新闻评论: 每天15:00）
```

### 定时任务触发日志
```bash
logs/app.log + logs/action.log + logs/decision.log

[生物钟] 群聊 123456 已冷场 4.0 小时，Roxy 感到无聊了！
[伪造事件] 开始处理系统事件: SYSTEM_BORED
[电话框] 群聊处理失败: ... （如果有错）
```

---

## 🛠️ 故障排查

| 问题 | 检查项 |
|------|--------|
| 定时任务没触发 | ❌ TARGET_GROUP_ID 未配置<br>❌ 冷场计时器未启动（需要有人先说话）<br>❌ 时区设置错误 |
| 伪造事件发送失败 | ❌ 查看 logs/decision.log (LLM 决策是否出错)<br>❌ 查看 logs/action.log (执行层是否出错) |
| 新闻 API 无响应 | ❌ 网络连接问题<br>❌ 防火墙阻止 api.vvhan.com<br>⚠️ 失败时会自动忽略，继续下个任务 |
| 内存/CPU 过高 | ⚠️ APScheduler 任务堆积<br>✅ 检查是否有无限循环的定时任务 |

---

## 💾 数据持久化

伪造事件仍然会更新：
- ✅ `cache/emotion_state.json` - 情绪变化被记录
- ✅ `cache/user_profiles.json` - (系统用户 id=0 的档案会被更新)
- ✅ `logs/emotion.log` - 情绪变化日志
- ✅ `logs/decision.log` - 决策日志
- ✅ `logs/action.log` - 执行日志

---

## 🎯 常见用法

### 用例 1: 定时摸鱼检查新闻
```python
# 每天下午 2:30 点评论新闻
hour=14, minute=30

# 自定义新闻评论提示
synthetic_prompt = f"【系统提示】今天又有什么劲爆新闻？"
```

### 用例 2: 活跃度检测
```python
# 群聊 30 分钟没动静就问问人
minutes=30
boredom_threshold = 1800  # 30 分钟
```

### 用例 3: 定时签到/问候
```python
async def daily_checkin(self):
    await self._trigger_synthetic_event(
        event_type="SYSTEM_CHECKIN",
        content="【系统提示】现在是打卡时间，你需要在群里签到。"
    )

# 加入 start()
self.scheduler.add_job(self.daily_checkin, 'cron', hour=8, minute=0)
```

---

## 📦 依赖

```
apscheduler>=3.10.0    # 任务调度
httpx                  # 异步 HTTP 客户端（新闻 API）
```

安装：
```bash
pip install -r requirements.txt
```

---

## 🔧 API 参考

### RoxyBiorhythm 类

```python
# 初始化
biorhythm = RoxyBiorhythm(target_group_id="123456789")

# 设置事件处理函数（在 lifespan 中自动调用）
biorhythm.set_event_processor(handle_synthetic_event)

# 启动定时任务
biorhythm.start()

# 更新群聊活动时间（在真实消息处理中调用）
biorhythm.update_activity()

# 手动触发伪造事件
await biorhythm._trigger_synthetic_event(
    event_type="CUSTOM_EVENT",
    content="【系统提示】...",
    group_id="123456789"
)

# 关闭（在 lifespan shutdown 中自动调用）
biorhythm.shutdown()
```

---

## 📚 相关文件

| 文件 | 行数 | 功能 |
|------|------|------|
| [cron_scheduler.py](cron_scheduler.py) | ~350 | 生物钟实现 |
| [app.py](app.py) | ~50 | lifespan + handle_synthetic_event |
| [decision_engine.py](decision_engine.py#L60-L90) | ~30 | System Prompt 扩展 |
| [.env](.env#L20-22) | 1 | TARGET_GROUP_ID 配置 |
| [CRON_SCHEDULER_GUIDE.md](CRON_SCHEDULER_GUIDE.md) | 详细指南 | 完整文档 |

---

**快速开始**: 配置 `TARGET_GROUP_ID` → 启动服务 → 观察日志 → 等待定时触发！

祝使用愉快 🚀
