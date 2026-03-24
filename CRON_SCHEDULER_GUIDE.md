# 伪造事件引擎 (Cron Scheduler) 使用指南

## 📋 概述

Roxy v2.1 新增了**伪造事件引擎** (`cron_scheduler.py`)，让 Roxy 能够主动发起对话，而无需等待用户消息。这是一个统一的系统，可以：

1. **群聊冷场检测** - 4小时无人说话时主动冒泡
2. **定时新闻评论** - 每天固定时间抓取热点新闻并吐槽

核心特性：
- ✅ 使用 APScheduler 异步任务调度
- ✅ 伪造 OneBot 消息事件，走完整的分析-决策-执行链路
- ✅ 无需修改现有的 emotion_engine/decision_engine/action_executor 核心代码
- ✅ 系统事件通过【系统提示】指令被模型理解为"内部心理活动"

---

## 🔧 配置方法

### 1. 环境变量 (.env)

```bash
# Roxy 的主阵地群号（用于定时事件的目标群）
TARGET_GROUP_ID="123456789"
```

**说明**:
- 留空或不配置 → 不启用定时事件
- 填入群号 → 启用所有定时任务（冷场检测、新闻评论等）

### 2. 定时任务配置

所有定时任务的配置都在 `cron_scheduler.py` 中，可以自定义：

#### 冷场检测配置 (check_boredom)
```python
# 每 30 分钟检查一次
self.scheduler.add_job(
    self.check_group_boredom,
    'interval',
    minutes=30,  # ← 修改这个参数调整检查频率
    id='check_boredom',
    max_instances=1
)

# 冷场阈值（秒数）
boredom_threshold = 14400  # 4小时 = 14400秒，可修改
```

#### 新闻评论配置 (fetch_and_roast_news)
```python
# 每天下午 3 点执行
self.scheduler.add_job(
    self.fetch_and_roast_news,
    'cron',
    hour=15,      # ← 修改小时 (0-23)
    minute=0,     # ← 修改分钟 (0-59)
    id='fetch_news',
    max_instances=1
)
```

**常见时间配置**:
- 早上 7 点: `hour=7, minute=0`
- 中午 12 点: `hour=12, minute=0`
- 晚上 9 点: `hour=21, minute=0`

---

## 🎯 工作原理

### 消息处理链路

```
[定时器触发]
     ↓
[生物钟生成伪造事件]
     ↓
[调用 handle_synthetic_event()]
     ↓
[真实消息处理链路]
  - analyze_message()       → 事件分析（可选，但伪造事件通常跳过）
  - ask_brain()              → LLM 决策（接收【系统提示】）
  - execute_decision()      → 执行动作
  - 保存情绪和档案         → 更新状态
```

### 伪造事件的特殊字段

所有由 cron_scheduler 生成的伪造事件都包含：

```json
{
  "post_type": "message",
  "message_type": "group",
  "group_id": "目标群号",
  "user_id": 0,                    // 0 表示系统触发
  "raw_message": "【系统提示】...",
  "message": [...],
  "_synthetic": true,              // 特殊标记
  "_event_type": "SYSTEM_NEWS"     // 事件类型
}
```

### 【系统提示】指令 (System Prompt)

伪造事件的内容是一段【系统提示】，它会被 LLM 理解为：

> "这不是来自用户的消息，而是你的内部想法或看到的信息"

例如：

**冷场检测触发**:
```
【系统提示】群里已经4个小时没人说话了。
你现在感到非常无聊，请立即主动在群里冒个泡，
分享点有趣的话题，吐槽点什么，或者发表情包。
你必须用非常活跃、甚至有点烦躁的语气。
```

**新闻评论触发**:
```
【系统提示】你刚刚在微博热搜上刷到了这条爆款新闻：
「男子网恋被骗8万，对方竟是同寝室室友」

规则：
1. 假装是你自己正在群里分享这个吃瓜链接。
2. 你必须用极其毒舌、辛辣的网络用语进行锐评（15字以内）。
3. 回复模式必须是 'text' 或 'text_image'，绝对禁止语音！
```

---

## 🌐 新闻 API 说明

定时新闻评论功能使用**韩小韩 Web API**（免鉴权、公益免费）：

```
微博热搜: https://api.vvhan.com/api/hotlist/wbHot
知乎热榜: https://api.vvhan.com/api/hotlist/zhihuHot
B站热搜: https://api.vvhan.com/api/hotlist/bili
```

**返回格式**:
```json
{
  "success": true,
  "data": [
    {
      "index": 1,
      "title": "热点标题",
      "hot": "热度值",
      "url": "原链接"
    }
  ]
}
```

**防护措施**:
- 每次请求随机选择一个平台（微博/知乎/B站）
- 从前 10 名中随机选取一条新闻（避免每次都评论第一名）
- 如果 API 请求失败，安静地跳过这一次（不会刷屏）

---

## 🚀 启动和运行

### 1. 启动应用

```bash
uvicorn app:app --host 0.0.0.0 --port 9000
```

### 2. 查看日志

启动后会看到类似的日志：

```
[主程序] FastAPI 应用启动，生物钟已初始化
[生物钟] RoxyBiorhythm 初始化完成
[生物钟] 事件处理函数已注册
[生物钟] 已启动（冷场检测: 每30分钟，新闻评论: 每天15:00）
```

### 3. 监控定时任务

所有伪造事件都会记录在日志中：

```
[生物钟] 群聊 123456789 已冷场 4.5 小时，Roxy 感到无聊了！
[伪造事件] 开始处理系统事件: SYSTEM_BORED
[伪造事件] 处理系统事件: SYSTEM_NEWS (新闻: "你说的对，但...")
```

---

## 📊 调试和故障排查

### 伪造事件没有触发？

**检查清单**:

1. ✅ 确认 `TARGET_GROUP_ID` 在 `.env` 中正确配置
   ```bash
   echo $env:TARGET_GROUP_ID  # Windows PowerShell
   ```

2. ✅ 查看应用启动日志是否有错误
   
3. ✅ 确认群聊有人发过消息（否则冷场计时器不会启动）
   
4. ✅ 检查时区设置（新闻评论是按本地时间，不是 UTC）

### 伪造事件发送失败？

检查 `logs/` 目录下的日志文件：

```bash
tail -f logs/action.log         # 动作执行日志
tail -f logs/decision.log       # 决策日志
tail -f logs/emotion.log        # 情绪变化
```

### 新闻 API 无法访问？

可能原因：
- 网络问题或 API 服务故障
- 防火墙阻止了对 `api.vvhan.com` 的访问

感知方式：
- 日志中会出现 `[新闻探针] 获取热搜失败`
- 下一次定时任务照常执行（不会崩溃）

---

## 🎓 高级定制

### 自定义冷场检测

例如：改为 2 小时检测一次，冷场阈值改为 3 小时

```python
# cron_scheduler.py 中修改

# 改成每 120 分钟检查一次
self.scheduler.add_job(
    self.check_group_boredom,
    'interval',
    minutes=120,  # ← 从 30 改成 120
    ...
)

# 改成冷场阈值 3 小时
boredom_threshold = 10800  # 改成 10800 秒 (3小时)
```

### 自定义新闻评论提示

在 `fetch_and_roast_news()` 方法中修改 `synthetic_prompt` 的内容：

```python
synthetic_prompt = (
    f"【系统提示】你刚刚在{news_data['platform']}上刷到了这条新闻：\n"
    f"「{news_data['title']}」\n\n"
    f"你现在需要用你的个性来评论这条新闻。"
    f"可以嘲讽、可以同情，但要保持你的角色设定。"  # ← 修改这里
)
```

### 添加新的定时任务

例如：添加每天早上 7 点的"早安问候"任务

```python
async def send_good_morning(self):
    """早安问候"""
    await self._trigger_synthetic_event(
        event_type="SYSTEM_GREETING",
        content="【系统提示】新的一天开始了。请在群里发个早安，用你的方式问候大家。",
        group_id=self.target_group_id
    )

# 在 start() 中注册
self.scheduler.add_job(
    self.send_good_morning,
    'cron',
    hour=7,
    minute=0,
    id='good_morning',
    max_instances=1
)
```

---

## 📚 相关文件

- [cron_scheduler.py](cron_scheduler.py) - 生物钟实现
- [app.py](app.py#L30-L50) - lifespan 生命周期配置
- [decision_engine.py](decision_engine.py#L50-L100) - System Prompt 扩展
- [.env](.env) - 环境变量配置

---

## ❓ 常见问题

**Q: 可以同时运行多个定时任务吗？**

> A: 可以！APScheduler 支持多个并发任务。但由于 OneBot 是单消息队列，发送会自动排队。

**Q: 冷场检测会不会导致刷屏？**

> A: 不会。冷场事件触发后，计时器会被重置，所以不会在短时间内重复触发。

**Q: 可以取消定时任务吗？**

> A: 可以。在 `start()` 中将 `add_job()` 注释掉即可。

**Q: 定时任务的时间是 UTC 还是本地时间？**

> A: APScheduler 使用本地时间，与系统时区一致。

---

## 🎬 快速开始 (5 分钟)

1. **配置目标群号**
   ```bash
   # 编辑 .env，找到这一行
   TARGET_GROUP_ID="123456789"  # ← 改成你要的群号
   ```

2. **启动应用**
   ```bash
   uvicorn app:app --port 9000
   ```

3. **观察日志**
   ```bash
   # 另开一个终端，查看生物钟日志
   tail -f logs/app.log
   ```

4. **等待定时触发** 或 修改 `cron_scheduler.py` 中的时间参数快速测试

5. **查看 logs/ 和 cache/ 目录**，观察伪造事件的处理结果

---

**祝你使用愉快！** 🚀

Created with 💕 for Roxy v2.1 Biorhythm System
