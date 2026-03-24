# 🚀 Roxy v2.1 伪造事件引擎 - 5 分钟快速开始

> 新年的 Roxy 学会了"心理活动" —— 自己想说话就说话，无需等待用户搭理！

---

## ⚡ 三行命令启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置群号 (编辑 .env，改这一行)
TARGET_GROUP_ID="123456789"  # ← 你的目标群号

# 3. 启动服务
uvicorn app:app --port 9000
```

## ✅ 验证成功的标志

看到这样的日志就说明成功了：

```
[生物钟] 已启动（冷场检测: 每30分钟，新闻评论: 每天15:00）
```

---

## 🎯 两个核心功能

### 功能 1️⃣ : 群聊冷场检测 (SYSTEM_BORED)

**触发条件**:
- 群里 4 小时没人说话
- 每 30 分钟检查一次

**Roxy 会**:
```
Roxy: "怎么就没人说话了啊...都快无聊死了"
Roxy: "有人吗？来聊天啊！"
Roxy: "[发表情包或梗图]"
```

### 功能 2️⃣ : 定时新闻评论 (SYSTEM_NEWS)

**触发条件**:
- 每天下午 3 点 (15:00)

**Roxy 会**:
```
Roxy: "【热搜】男子网恋被骗8万..."
Roxy: "哈哈哈，这傻子......"
Roxy: "[毒舌评论，通常是文字或文字+梗图]"
```

---

## 🧪 快速测试 (可选)

不想等 4 小时？运行这个：

```bash
python test_cron_scheduler.py
```

菜单会问你选择：
```
1. 测试冷场检测 
2. 测试新闻评论
3. 测试新闻拉取
4. 测试生物钟基本功能
5. 全部测试
```

选 `5` 全部测试一遍，所有功能都验证通过！

---

## 📝 三个配置参数 (可选修改)

都在 `cron_scheduler.py`：

### 1. 改变新闻评论时间

```python
# line ~170 左右
hour=15,      # ← 改成你想要的 (0-23)
minute=0,     # ← 改成你想要的 (0-59)
```

例如改成 8:30 早上评论：
```python
hour=8,
minute=30
```

### 2. 改变冷场检测频率

```python
# line ~155 左右
minutes=30,   # ← 改成想要的分钟数
```

例如改成每个小时检查一次：
```python
minutes=60
```

### 3. 改变冷场阈值

```python
# line ~120 左右
boredom_threshold = 14400  # ← 改成秒数 (现在是 4 小时)
```

例如改成 2 小时：
```python
boredom_threshold = 7200  # 2 小时
```

---

## 📊 常见疑问

**Q: 为什么定时任务没有执行？**

A: 检查三个地方
1. `.env` 中有没有 `TARGET_GROUP_ID="群号"`
2. 有没有在目标群发送过消息（冷场计时器需要激活）  
3. 启动日志有没有显示 `[生物钟] 已启动`

**Q: 新闻 API 是什么？会泄露数据吗？**

A: 是公益免费 API（vvhan），不需要密钥，完全匿名，放心用

**Q: 伪造事件是什么意思？**

A: Roxy 虽然没有收到真实用户消息，但系统给它发一个虚拟消息（伪造事件），告诉它"你感到无聊了"或"你看到新闻了"，然后它就像真的一样回复

**Q: 可以自己添加定时任务吗？**

A: 可以！参考文档 `CRON_SCHEDULER_GUIDE.md` 中的"添加新的定时任务"部分

---

## 📚 三份详细文档

| 文档 | 用途 | 给谁 |
|------|------|------|
| [CRON_SCHEDULER_GUIDE.md](CRON_SCHEDULER_GUIDE.md) | 完整指南 (450行) | 想充分理解原理的人 |
| [CRON_QUICK_REFERENCE.md](CRON_QUICK_REFERENCE.md) | 速查表 (300行) | 想快速查找配置的人 |
| [DEPLOYMENT_CHECKLIST_CRON.md](DEPLOYMENT_CHECKLIST_CRON.md) | 部署清单 (400行) | 想逐步验证的人 |

---

## 🔄 工作原理 (超简版)

```
定时器触发 
  ↓
生物钟生成虚拟消息 (伪造事件)
  ↓
【系统提示】告诉 Roxy
  ↓
LLM (大模型) 理解后生成回复
  ↓
Roxy 的回复发送到群里 
  ↓
情绪、档案、日志都被更新
```

就是这么简单！

---

## 🎮 完整启动检查清单

启动前检查：
```
□ Python 3.8+
□ pip install -r requirements.txt 成功
□ .env 中有 TARGET_GROUP_ID="你的群号"
□ OpenAI API Key 配置过
□ logs/ 目录存在
□ cache/ 目录存在
```

启动后检查：
```
□ 看到 [生物钟] 已启动 的日志
□ 能在群里 @Roxy 并收到回复
□ logs/app.log 有新行
□ logs/action.log 有新行
```

都 ✅ 了就说明成功！

---

## 🆘 遇到问题？

### 问题 1: 日志中出现 "target_group_id is None"

**解决**: 编辑 .env，加入：
```
TARGET_GROUP_ID="123456789"
```

### 问题 2: "ModuleNotFoundError: No module named 'apscheduler'"

**解决**:
```bash
pip install apscheduler>=3.10.0
```

### 问题 3: 定时任务从没执行过

**解决**:
1. 先在目标群发个消息给 Roxy，她回复说明工作正常
2. 等待下一个检查时间（30分钟一次）或手动执行：
   ```bash
   python test_cron_scheduler.py
   # 选 5 全部测试
   ```

### 问题 4: 新闻拉取失败

**解决**: 可能网络问题，不用担心，下次自动重试

---

## 🚀 下一步？

1. **启动服务**: `uvicorn app:app --port 9000`
2. **在群里聊天**: 让计时器启动
3. **等待触发**: 4 小时后冷场检测，或明天 15:00 新闻评论
4. **查看日志**: `tail -f logs/app.log`
5. **自定义配置**: 修改 `cron_scheduler.py` 中的参数

---

## 💡 小贴士

- 日志都在 `logs/` 目录，遇到问题先看日志
- 伪造事件会同时更新情绪和档案（跟真实消息一样）
- 新闻评论每次拉取不同平台和新闻，不会重复
- 除了【系统提示】是伪造的，Roxy 的回复都是真实的（由 LLM 生成）

---

## 📞 需要帮助？

1. 查看 `CRON_SCHEDULER_GUIDE.md` 的"故障排查"章节
2. 运行 `test_cron_scheduler.py` 逐个测试功能
3. 查看 `logs/` 下的日志文件找错误信息

---

**准备好了吗？启动 Roxy v2.1，让她自己会聊天吧！** 🎉

```bash
uvicorn app:app --port 9000
```

祝使用愉快！✨
