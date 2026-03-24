#!/usr/bin/env python3
"""
伪造事件测试脚本
用于快速验证 Roxy 的伪造事件引擎是否正常工作
"""

import asyncio
import json
from datetime import datetime
from cron_scheduler import RoxyBiorhythm, fetch_random_hot_news
from logger import log_app

# 测试消息
TEST_MESSAGES = {
    "SYSTEM_BORED": {
        "event_type": "SYSTEM_BORED",
        "content": "【系统提示】群里已经4个小时没人说话了。你现在感到非常无聊，请立即主动在群里冒个泡，分享点有趣的话题，吐槽点什么，或者发表情包。你必须用非常活跃、甚至有点烦躁的语气。"
    },
    "SYSTEM_NEWS": {
        "event_type": "SYSTEM_NEWS",
        "content": "【系统提示】你刚刚在微博热搜上刷到了这条爆款新闻：「男子网恋被骗8万，对方竟是自己同寝室室友」。规则：1. 假装是你自己正在群里分享这个吃瓜链接。2. 你必须用极其毒舌、辛辣的网络用语进行锐评（15字以内）。3. 回复模式必须是 'text' 或 'text_image'，绝对禁止语音！"
    }
}


async def test_fake_event(biorhythm: RoxyBiorhythm, event_type: str, group_id: str = "123456789"):
    """
    测试伪造事件
    """
    print(f"\n{'='*60}")
    print(f"[测试] 正在创建伪造事件: {event_type}")
    print(f"{'='*60}\n")
    
    msg_config = TEST_MESSAGES.get(event_type)
    if not msg_config:
        print(f"❌ 未知的事件类型: {event_type}")
        print(f"   可用类型: {', '.join(TEST_MESSAGES.keys())}")
        return
    
    # 创建伪造事件
    await biorhythm._trigger_synthetic_event(
        event_type=msg_config["event_type"],
        content=msg_config["content"],
        group_id=group_id
    )
    
    print(f"✅ 伪造事件已发送: {event_type}")
    print(f"   目标群号: {group_id}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


async def test_fetch_news():
    """
    测试新闻拉取功能
    """
    print(f"\n{'='*60}")
    print("[测试] 正在测试新闻拉取...")
    print(f"{'='*60}\n")
    
    try:
        news = await fetch_random_hot_news()
        if news:
            print("✅ 新闻拉取成功！")
            print(f"   平台: {news['platform']}")
            print(f"   标题: {news['title']}")
            print(f"   热度: {news['hot']}")
            print(f"   链接: {news['link'][:50]}...")
        else:
            print("⚠️  新闻拉取返回空结果（可能是网络问题）")
    except Exception as e:
        print(f"❌ 新闻拉取失败: {repr(e)}")
    print()


async def test_biorhythm_functions(biorhythm: RoxyBiorhythm):
    """
    测试生物钟的基本功能
    """
    print(f"\n{'='*60}")
    print("[测试] 正在测试生物钟基本功能...")
    print(f"{'='*60}\n")
    
    # 测试 update_activity()
    print("1. 测试 update_activity()...")
    biorhythm.update_activity()
    print(f"   ✅ 活动时间戳已更新: {biorhythm.last_group_msg_time}")
    print()
    
    # 测试冷场检测函数
    print("2. 测试 check_group_boredom()...")
    try:
        # 直接调用一次（不会等 4 小时）
        await biorhythm.check_group_boredom()
        print("   ✅ 冷场检测函数执行成功（如没有消息，跳过触发）")
    except Exception as e:
        print(f"   ❌ 冷场检测出错: {repr(e)}")
    print()
    
    # 测试新闻评论函数
    print("3. 测试 fetch_and_roast_news()...")
    try:
        await biorhythm.fetch_and_roast_news()
        print("   ✅ 新闻评论函数执行成功")
    except Exception as e:
        print(f"   ❌ 新闻评论出错: {repr(e)}")
    print()


async def main():
    """
    主测试函数
    """
    print("\n" + "="*60)
    print("   Roxy 伪造事件引擎 - 测试套件")
    print("="*60)
    
    # 需要用户输入目标群号
    default_group = "123456789"
    group_input = input(f"\n请输入目标群号 (默认: {default_group}): ").strip()
    target_group = group_input if group_input else default_group
    
    print(f"✅ 目标群号: {target_group}\n")
    
    # 初始化生物钟 (不启动定时任务，只用于测试)
    biorhythm = RoxyBiorhythm(target_group_id=target_group)
    
    # 设置一个简单的伪造事件处理函数（只打印，不真实发送）
    async def mock_handler(event):
        print("\n[处理器] 伪造事件已接收")
        print(f"   事件类型: {event.get('_event_type')}")
        print(f"   群号: {event.get('group_id')}")
        print(f"   内容摘要: {event.get('raw_message')[:50]}...")
    
    biorhythm.set_event_processor(mock_handler)
    
    # 显示菜单
    menu = """
【菜单】选择要测试的功能:
  1. 测试冷场检测 (SYSTEM_BORED)
  2. 测试新闻评论 (SYSTEM_NEWS)  
  3. 测试新闻拉取 (fetch_random_hot_news)
  4. 测试生物钟基本功能
  5. 全部测试
  0. 退出

请输入选项 (0-5):"""
    
    while True:
        print(menu)
        choice = input("> ").strip()
        
        if choice == "0":
            print("\n👋 退出测试")
            break
        elif choice == "1":
            await test_fake_event(biorhythm, "SYSTEM_BORED", target_group)
        elif choice == "2":
            await test_fake_event(biorhythm, "SYSTEM_NEWS", target_group)
        elif choice == "3":
            await test_fetch_news()
        elif choice == "4":
            await test_biorhythm_functions(biorhythm)
        elif choice == "5":
            print("\n开始全部测试...\n")
            await test_biorhythm_functions(biorhythm)
            await test_fetch_news()
            await test_fake_event(biorhythm, "SYSTEM_BORED", target_group)
            await test_fake_event(biorhythm, "SYSTEM_NEWS", target_group)
            print("\n✅ 全部测试完成！")
        else:
            print("❌ 无效选项，请重试")
        
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断 (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ 测试出错: {repr(e)}")
        import traceback
        traceback.print_exc()
