#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import argparse
from datetime import datetime
import logging
import os
from typing import List, Dict, Tuple, Optional

# 配置部分
BLOG_URL = "https://www.207725.xyz"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # 从环境变量获取
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")      # 从环境变量获取
POSTS_FILE = "posts.txt"  # 必刷URL列表文件

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
        self.required_success = 0
        self.required_failure = 0
        self.visited_urls: Dict[str, int] = {}
        self.required_urls: Dict[str, int] = {}
        self.session = None
        self.article_urls = []  # 存储获取到的文章URL
        self.required_article_urls = []  # 存储必刷的文章URL

    async def load_required_urls(self) -> bool:
        """从posts.txt加载必刷URL列表"""
        try:
            if not os.path.exists(POSTS_FILE):
                logger.warning(f"未找到必刷URL文件 {POSTS_FILE}")
                return False
                
            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
                self.required_article_urls = [url for url in urls if url.startswith(('http://', 'https://'))]
                
            if not self.required_article_urls:
                logger.warning(f"必刷URL文件 {POSTS_FILE} 中没有有效的URL")
                return False
                
            logger.info(f"从 {POSTS_FILE} 加载了 {len(self.required_article_urls)} 个必刷URL")
            return True
        except Exception as e:
            logger.error(f"加载必刷URL文件时出错: {str(e)}")
            return False

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

    async def visit_url(self, url: str, is_required: bool = False):
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
                    if is_required:
                        self.required_success += 1
                        self.required_urls[url] = self.required_urls.get(url, 0) + 1
                    else:
                        self.success_count += 1
                        self.visited_urls[url] = self.visited_urls.get(url, 0) + 1
                    logger.info(f"成功访问: {url}")
                else:
                    if is_required:
                        self.required_failure += 1
                    else:
                        self.failure_count += 1
                    logger.warning(f"访问失败: {url}, 状态码: {response.status}")
        except Exception as e:
            if is_required:
                self.required_failure += 1
            else:
                self.failure_count += 1
            logger.error(f"访问 {url} 时出错: {str(e)}")

    async def run_required_visits(self):
        """执行必刷URL的访问"""
        if not self.required_article_urls:
            return
            
        logger.info(f"开始访问 {len(self.required_article_urls)} 个必刷URL")
        
        tasks = []
        async with aiohttp.ClientSession() as self.session:
            for url in self.required_article_urls:
                tasks.append(self.visit_url(url, is_required=True))
            
            await asyncio.gather(*tasks)
        
        logger.info(f"必刷URL访问完成: 成功 {self.required_success}, 失败 {self.required_failure}")

    async def run_normal_visits(self):
        """执行普通访问任务"""
        if self.total_visits <= 0:
            return
            
        logger.info(f"开始模拟访问，总次数: {self.total_visits}")
        
        # 获取文章URL列表
        self.article_urls = await self.fetch_article_urls()
        if not self.article_urls:
            logger.error("无法获取文章URL列表，跳过普通访问")
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
        
        logger.info(f"普通访问完成: 成功 {self.success_count}, 失败 {self.failure_count}")

    async def run_visits(self):
        """执行访问任务"""
        start_time = datetime.now()
        
        # 加载必刷URL
        await self.load_required_urls()
        
        # 先执行必刷URL访问
        await self.run_required_visits()
        
        # 再执行普通访问
        await self.run_normal_visits()
        
        # 计算统计信息
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        total_requests = self.required_success + self.required_failure + self.success_count + self.failure_count
        requests_per_second = total_requests / duration if duration > 0 else 0
        
        # 发送通知
        await self.send_statistics(start_time, end_time, duration, requests_per_second)
    
    async def send_statistics(self, start_time: datetime, end_time: datetime, duration: float, rps: float):
        """发送统计信息到Telegram"""
        message = (
            "📊 博客访问模拟报告\n\n"
            f"⏱️ 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏱️ 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏳ 总耗时: {duration:.2f} 秒\n"
            f"🚀 总请求次数: {self.required_success + self.required_failure + self.success_count + self.failure_count}\n\n"
            "🔴 必刷URL统计:\n"
            f"  ✅ 成功: {self.required_success}\n"
            f"  ❌ 失败: {self.required_failure}\n\n"
            "🟢 普通访问统计:\n"
            f"  🎯 目标次数: {self.total_visits}\n"
            f"  ✅ 成功: {self.success_count}\n"
            f"  ❌ 失败: {self.failure_count}\n"
            f"  📈 平均速度: {rps:.2f} 次/秒\n\n"
        )
        
        # 添加必刷URL的访问统计
        if self.required_urls:
            message += "📌 必刷URL访问分布:\n"
            for url, count in self.required_urls.items():
                display_url = url.replace(BLOG_URL, "")
                message += f"  - {display_url}: {count} 次\n"
            message += "\n"
        
        # 添加普通URL的访问统计
        if self.visited_urls:
            message += "📝 普通URL访问分布:\n"
            for url, count in self.visited_urls.items():
                display_url = url.replace(BLOG_URL, "")
                message += f"  - {display_url}: {count} 次\n"
        
        # 添加总结
        message += f"\n🌐 博客地址: {BLOG_URL}"
        
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
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"发送Telegram通知失败，状态码: {response.status}, 响应: {error_text}")
                    else:
                        logger.info("Telegram通知发送成功")
        except Exception as e:
            logger.error(f"发送Telegram通知时出错: {str(e)}")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Typecho博客访问模拟器")
    parser.add_argument(
        "-n", "--visits",
        type=int,
        default=100,
        help="普通访问次数(必刷URL不计入此数量)，默认为100",
    )
    return parser.parse_args()

async def main():
    args = parse_args()
    visitor = BlogVisitor(args.visits)
    await visitor.run_visits()

if __name__ == "__main__":
    asyncio.run(main())
