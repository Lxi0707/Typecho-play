#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import argparse
from datetime import datetime
import logging
from typing import List, Dict, Tuple

# 配置部分
BLOG_URL = "https://www.207725.xyz"
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # 替换为你的Telegram bot token
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"     # 替换为你的Telegram chat ID

# 用户代理列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
]

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlogVisitor:
    def __init__(self, total_visits: int):
        self.total_visits = total_visits
        self.success_count = 0
        self.failure_count = 0
        self.visited_urls: Dict[str, int] = {}
        self.session = None
        self.article_urls = []  # 存储获取到的文章URL

    async def fetch_article_urls(self) -> List[str]:
        """从博客首页获取文章链接"""
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(BLOG_URL, headers=headers) as response:
                    if response.status == 200:
                        text = await response.text()
                        # 简单的解析逻辑，根据Typecho的结构获取文章链接
                        # 这里需要根据实际HTML结构调整
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(text, 'html.parser')
                        article_links = []
                        
                        # 查找文章链接 - 根据Typecho的结构调整选择器
                        for link in soup.select('a[href*="/archives/"]'):
                            href = link.get('href')
                            if href and href.startswith(BLOG_URL) and href not in article_links:
                                article_links.append(href)
                        
                        # 如果没有找到文章链接，使用默认的几个
                        if not article_links:
                            article_links = [
                                f"{BLOG_URL}/index.php/archives/13/",
                                f"{BLOG_URL}/index.php/archives/5/",
                                f"{BLOG_URL}/index.php/archives/1/",
                            ]
                        
                        return article_links
                    else:
                        logger.warning(f"获取文章列表失败，状态码: {response.status}")
                        return [
                            f"{BLOG_URL}/index.php/archives/13/",
                            f"{BLOG_URL}/index.php/archives/5/",
                            f"{BLOG_URL}/index.php/archives/1/",
                        ]
        except Exception as e:
            logger.error(f"获取文章列表时出错: {str(e)}")
            return [
                f"{BLOG_URL}/index.php/archives/13/",
                f"{BLOG_URL}/index.php/archives/5/",
                f"{BLOG_URL}/index.php/archives/1/",
            ]

    async def visit_url(self, url: str):
        """访问单个URL"""
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": BLOG_URL,
                "DNT": "1",  # Do Not Track
            }
            
            # 随机延迟，模拟真实用户行为
            await asyncio.sleep(random.uniform(0.5, 3.0))
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    self.success_count += 1
                    self.visited_urls[url] = self.visited_urls.get(url, 0) + 1
                    logger.info(f"成功访问: {url}")
                else:
                    self.failure_count += 1
                    logger.warning(f"访问失败: {url}, 状态码: {response.status}")
        except Exception as e:
            self.failure_count += 1
            logger.error(f"访问 {url} 时出错: {str(e)}")

    async def run_visits(self):
        """执行访问任务"""
        start_time = datetime.now()
        logger.info(f"开始模拟访问，总次数: {self.total_visits}")
        
        # 获取文章URL列表
        self.article_urls = await self.fetch_article_urls()
        if not self.article_urls:
            logger.error("无法获取文章URL列表，退出")
            await self.send_notification("❌ 模拟访问失败: 无法获取文章URL列表")
            return
        
        logger.info(f"获取到 {len(self.article_urls)} 篇文章")
        
        # 计算每篇文章的访问次数（均匀分配）
        visits_per_article = self.total_visits // len(self.article_urls)
        remaining_visits = self.total_visits % len(self.article_urls)
        
        # 创建访问任务列表
        tasks = []
        async with aiohttp.ClientSession() as self.session:
            for i, url in enumerate(self.article_urls):
                # 分配访问次数
                visits = visits_per_article + (1 if i < remaining_visits else 0)
                for _ in range(visits):
                    tasks.append(self.visit_url(url))
            
            # 并发执行所有访问任务
            await asyncio.gather(*tasks)
        
        # 计算统计信息
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        requests_per_second = self.total_visits / duration if duration > 0 else 0
        
        # 发送通知
        await self.send_statistics(start_time, end_time, duration, requests_per_second)
    
    async def send_statistics(self, start_time: datetime, end_time: datetime, duration: float, rps: float):
        """发送统计信息到Telegram"""
        message = (
            "📊 博客访问模拟报告\n\n"
            f"⏱️ 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏱️ 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏳ 总耗时: {duration:.2f} 秒\n"
            f"🚀 总访问次数: {self.total_visits}\n"
            f"✅ 成功次数: {self.success_count}\n"
            f"❌ 失败次数: {self.failure_count}\n"
            f"📈 平均速度: {rps:.2f} 次/秒\n\n"
            "🔗 访问分布:\n"
        )
        
        # 添加每个URL的访问统计
        for url, count in self.visited_urls.items():
            # 美化URL显示，只保留路径部分
            display_url = url.replace(BLOG_URL, "")
            message += f"  - {display_url}: {count} 次\n"
        
        # 添加成功率和总结
        success_rate = (self.success_count / self.total_visits * 100) if self.total_visits > 0 else 0
        message += (
            f"\n🎯 成功率: {success_rate:.2f}%\n"
            f"🌐 博客地址: {BLOG_URL}"
        )
        
        await self.send_notification(message)
    
    async def send_notification(self, message: str):
        """通过Telegram bot发送通知"""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("未配置Telegram bot token或chat ID，跳过通知发送")
            return
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"发送Telegram通知失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"发送Telegram通知时出错: {str(e)}")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Typecho博客访问模拟器")
    parser.add_argument(
        "-n", "--visits",
        type=int,
        default=100,
        help="总访问次数，默认为100",
    )
    return parser.parse_args()

async def main():
    args = parse_args()
    visitor = BlogVisitor(args.visits)
    await visitor.run_visits()

if __name__ == "__main__":
    asyncio.run(main())
