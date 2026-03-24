"""
系统定时器 (Cron Job) - Roxy 的生物钟
用于实现群聊冷场检测、定时新闻评论等自发行为
"""
import asyncio
import json
import random
from typing import Optional, Dict, Any
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
from logger import log_app


# 新闻 API 源
HOT_NEWS_SOURCES = {
    "微博热搜": "wbHot",
    "知乎热榜": "zhihuHot",
    "B站热搜": "bili"
}
HOT_NEWS_API_BASE = "https://api.vvhan.com/api/hotlist"

# 目标群号（从 config 导入，没有则使用空）
TARGET_GROUP_ID: Optional[str] = None


async def fetch_random_hot_news() -> Optional[Dict[str, str]]:
    """
    异步拉取随机热搜新闻
    
    返回例子:
    {
        "platform": "微博热搜",
        "title": "今天这雨下得也太离谱了",
        "hot": "489万",
        "link": "https://s.weibo.com/weibo?q=..."
    }
    """
    platform_name, endpoint = random.choice(list(HOT_NEWS_SOURCES.items()))
    url = f"{HOT_NEWS_API_BASE}/{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json()
            
            if data.get("success") and data.get("data"):
                # 从前 10 名中随机选择，避免每次都吐槽排名第一
                top_10 = data["data"][:10]
                target_news = random.choice(top_10)
                
                return {
                    "platform": platform_name,
                    "title": target_news.get("title", ""),
                    "hot": target_news.get("hot", "很高"),
                    "link": target_news.get("url", "")
                }
        return None
    except Exception as e:
        log_app(f"[新闻探针] 获取热搜失败: {repr(e)}", level="warning")
        return None


class RoxyBiorhythm:
    """
    Roxy 的生物钟 - 管理所有定时自发行为
    """
    
    def __init__(self, target_group_id: Optional[str] = None):
        """
        初始化生物钟
        
        Args:
            target_group_id: Roxy 的主阵地群号（可选）
        """
        self.scheduler = AsyncIOScheduler()
        self.target_group_id = target_group_id
        
        # 活动计时器（用于检测群聊冷场）
        self.last_group_msg_time: float = 0.0
        
        # 处理函数引用（会在 app.py 中设置）
        self._process_synthetic_event_fn = None
        
        log_app("[生物钟] RoxyBiorhythm 初始化完成")
    
    def set_event_processor(self, fn):
        """
        设置伪造事件处理函数
        这个函数会被 app.py 传入，用来处理由调度器生成的事件
        
        Args:
            fn: async function(synthetic_event: dict) -> None
        """
        self._process_synthetic_event_fn = fn
        log_app("[生物钟] 事件处理函数已注册")
    
    def update_activity(self):
        """
        更新群聊活动时间戳
        每次接到群里消息时调用这个，用来重置无聊计时器
        """
        self.last_group_msg_time = asyncio.get_event_loop().time()
    
    async def check_group_boredom(self):
        """
        [定时任务] 群聊冷场检测
        每 30 分钟检查一次，如果群里超过指定时间没人说话，就主动冒泡
        
        规则:
        - 如果 4 小时内没有新消息，Roxy 会感到无聊
        - 触发后会重置计时器，防止连续刷屏
        """
        if not self.target_group_id:
            return  # 没有配置目标群，跳过
        
        now = asyncio.get_event_loop().time()
        silence_duration = now - self.last_group_msg_time
        
        # 4 小时 = 14400 秒
        boredom_threshold = 14400
        
        if silence_duration > boredom_threshold:
            log_app(
                f"[生物钟] 群聊 {self.target_group_id} 已冷场 {silence_duration/3600:.1f} 小时，"
                f"Roxy 感到无聊了！",
                level="info"
            )
            
            await self._trigger_synthetic_event(
                event_type="SYSTEM_BORED",
                content=(
                    "【系统提示】群里已经4个小时没人说话了。"
                    "你现在感到非常无聊，请立即主动在群里冒个泡，"
                    "分享点有趣的话题，吐槽点什么，或者发表情包。"
                    "你必须用非常活跃、甚至有点烦躁的语气。"
                ),
                group_id=self.target_group_id
            )
            
            # 重置计时器，防止连续刷屏
            self.last_group_msg_time = now
    
    async def fetch_and_roast_news(self):
        """
        [定时任务] 定时新闻评论
        每天下午 3 点（或其他配置的时间）自动抓取热点新闻并吐槽
        """
        if not self.target_group_id:
            return  # 没有配置目标群，跳过
        
        log_app("[生物钟] Roxy 正在网上冲浪検测热点...", level="info")
        
        news_data = await fetch_random_hot_news()
        if not news_data:
            log_app("[生物钟] 新闻获取失败，本次跳过", level="warning")
            return
        
        # 构造系统指令
        synthetic_prompt = (
            f"【系统提示】你刚刚在{news_data['platform']}上刷到了这条爆款新闻：\n"
            f"「{news_data['title']}」\n"
            f"(热度: {news_data.get('hot', '很高')})\n\n"
            f"规则：\n"
            f"1. 假装是你自己正在群里分享这个吃瓜链接。\n"
            f"2. 你必须用极其毒舌、辛辣的网络用语进行锐评（15字以内）。\n"
            f"3. 回复模式必须是 'text' 或 'text_image'，绝对禁止语音！\n"
            f"4. 可以配上梗图或表情符号。\n"
            f"5. 原链接：{news_data['link']}"
        )
        
        await self._trigger_synthetic_event(
            event_type="SYSTEM_NEWS",
            content=synthetic_prompt,
            group_id=self.target_group_id
        )
        
        log_app(
            f"[生物钟] 新闻评论已触发: {news_data['title'][:30]}...",
            level="info"
        )
    
    async def _trigger_synthetic_event(
        self,
        event_type: str,
        content: str,
        group_id: Optional[str] = None,
        user_id: int = 0
    ):
        """
        将系统事件伪造成 OneBot 消息，塞进处理队列
        
        Args:
            event_type: "SYSTEM_BORED" 或 "SYSTEM_NEWS" 等
            content: 系统指令（会被放到 raw_message 字段）
            group_id: 目标群号（默认使用 self.target_group_id）
            user_id: 伪造的发送者（默认 0，表示系统）
        """
        if not self._process_synthetic_event_fn:
            log_app("[生物钟] 警告: 处理函数未设置，无法处理伪造事件", level="warning")
            return
        
        group_id = group_id or self.target_group_id
        
        # 构造一个伪造的 OneBot 消息事件
        synthetic_event: Dict[str, Any] = {
            "post_type": "message",
            "message_type": "group",
            "sub_type": "normal",
            "group_id": int(group_id) if group_id else 0,
            "user_id": user_id,  # 0 表示系统触发
            "message_id": -1,
            "raw_message": content,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": content
                    }
                }
            ],
            "sender": {
                "user_id": user_id,
                "nickname": "Roxy_System",
                "card": "Roxy_System"
            },
            "self_id": 0,
            "time": int(datetime.now().timestamp()),
            
            # 自定义字段，表示这是系统伪造的事件
            "_synthetic": True,
            "_event_type": event_type,
        }
        
        try:
            await self._process_synthetic_event_fn(synthetic_event)
        except Exception as e:
            log_app(
                f"[生物钟] 伪造事件处理失败: {repr(e)}",
                level="error"
            )
    
    def start(self):
        """
        启动生物钟（必须在 FastAPI lifespan 的 startup 中调用）
        """
        # 每 30 分钟检查一次群聊冷场
        self.scheduler.add_job(
            self.check_group_boredom,
            'interval',
            minutes=30,
            id='check_boredom',
            max_instances=1  # 防止并发执行
        )
        
        # 每天下午 3 点准时抓取热点新闻
        self.scheduler.add_job(
            self.fetch_and_roast_news,
            'cron',
            hour=15,
            minute=0,
            id='fetch_news',
            max_instances=1
        )
        
        self.scheduler.start()
        log_app("[生物钟] 已启动（冷场检测: 每30分钟，新闻评论: 每天15:00）", level="info")
    
    def shutdown(self):
        """
        关闭生物钟（必须在 FastAPI lifespan 的 shutdown 中调用）
        """
        try:
            self.scheduler.shutdown()
            log_app("[生物钟] 已正常关闭", level="info")
        except Exception as e:
            log_app(f"[生物钟] 关闭出错: {repr(e)}", level="error")
