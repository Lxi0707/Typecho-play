#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import argparse
from datetime import datetime
import logging
import os
import sys
from typing import Dict, List

# 配置部分
BLOG_URL = "https://www.207725.xyz"
POSTS_FILE = "posts.txt"  # 必刷URL列表文件
TELEGRAM_TIMEOUT = 10  # Telegram通知超时(秒)

# 用户代理列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('visitor.log')
    ]
)
logger = logging.getLogger(__name__)

class BlogVisitor:
    def __init__(self, total_visits: int):
        self.total_visits = total_visits
        self.success_count = 0
        self.failure_count = 0
        self.required_stats = {'success': 0, 'failure': 0}
        self.visited_urls: Dict[str, int] = {}
        self.required_urls: Dict[str, int] = {}
        self.session = None
        self.article_urls = []
        self.required_article_urls = []
        
        # 环境检查
        logger.info(f"Python {sys.version.split()[0]} on {sys.platform}")
        logger.info(f"Initializing with {total_visits} normal visits")

    async def load_required_urls(self) -> bool:
        """从posts.txt加载必刷URL列表"""
        try:
            if not os.path.exists(POSTS_FILE):
                default_urls = [
                    f"{BLOG_URL}/index.php/archives/13/",
                    f"{BLOG_URL}/index.php/archives/5/"
                ]
                with open(POSTS_FILE, 'w') as f:
                    f.write('\n'.join(default_urls))
                logger.warning(f"Created {POSTS_FILE} with default URLs")
            
            with open(POSTS_FILE, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
                self.required_article_urls = [
                    url if url.startswith('http') else f"{BLOG_URL}{url}"
                    for url in urls
                ]
            
            logger.info(f"Loaded {len(self.required_article_urls)} required URLs")
            return True
        except Exception as e:
            logger.error(f"Failed to load required URLs: {str(e)}")
            return False

    async def fetch_article_urls(self) -> List[str]:
        """从博客首页获取文章链接"""
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(BLOG_URL, headers=headers) as response:
                    if response.status == 200:
                        from bs4 import BeautifulSoup
                        text = await response.text()
                        soup = BeautifulSoup(text, 'html.parser')
                        
                        # 查找所有可能的文章链接
                        article_links = []
                        for selector in ['a[href*="/archives/"]', '.post-title a', 'article a']:
                            article_links.extend([
                                link['href'] for link in soup.select(selector) 
                                if link.has_attr('href')
                            ])
                        
                        # 去重并规范化URL
                        unique_links = []
                        seen = set()
                        for link in article_links:
                            if link.startswith('/'):
                                full_url = f"{BLOG_URL}{link}"
                            elif link.startswith(BLOG_URL):
                                full_url = link
                            else:
                                continue
                            
                            if full_url not in seen:
                                seen.add(full_url)
                                unique_links.append(full_url)
                        
                        return unique_links or self.get_fallback_urls()
                    else:
                        logger.warning(f"Fetch failed with status: {response.status}")
                        return self.get_fallback_urls()
        except Exception as e:
            logger.error(f"Error fetching articles: {str(e)}")
            return self.get_fallback_urls()

    def get_fallback_urls(self) -> List[str]:
        """获取备用URL列表"""
        return [
            f"{BLOG_URL}/index.php/archives/13/",
            f"{BLOG_URL}/index.php/archives/5/",
            f"{BLOG_URL}/index.php/archives/1/"
        ]

    async def visit_url(self, url: str, is_required: bool = False):
        """访问单个URL"""
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": BLOG_URL,
                "DNT": "1",
            }
            
            await asyncio.sleep(random.uniform(0.5, 2.5))
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                if response.status == 200:
                    if is_required:
                        self.required_stats['success'] += 1
                        self.required_urls[url] = self.required_urls.get(url, 0) + 1
                    else:
                        self.success_count += 1
                        self.visited_urls[url] = self.visited_urls.get(url, 0) + 1
                    logger.debug(f"Visited: {url}")
                else:
                    if is_required:
                        self.required_stats['failure'] += 1
                    else:
                        self.failure_count += 1
                    logger.warning(f"Failed {url} (HTTP {response.status})")
        except Exception as e:
            if is_required:
                self.required_stats['failure'] += 1
            else:
                self.failure_count += 1
            logger.error(f"Error visiting {url}: {str(e)}")

    async def run_required_visits(self):
        """执行必刷URL访问"""
        if not self.required_article_urls:
            logger.warning("No required URLs to visit")
            return
            
        logger.info(f"Starting required visits for {len(self.required_article_urls)} URLs")
        
        tasks = []
        async with aiohttp.ClientSession() as self.session:
            for url in self.required_article_urls:
                tasks.append(self.visit_url(url, is_required=True))
            
            await asyncio.gather(*tasks)
        
        logger.info(f"Required visits completed: {self.required_stats['success']} success, {self.required_stats['failure']} failure")

    async def run_normal_visits(self):
        """执行普通访问"""
        if self.total_visits <= 0:
            logger.info("Skipping normal visits (count <= 0)")
            return
            
        self.article_urls = await self.fetch_article_urls()
        if not self.article_urls:
            logger.error("No articles found for normal visits")
            return
            
        logger.info(f"Starting {self.total_visits} normal visits across {len(self.article_urls)} URLs")
        
        visits_per_url = self.total_visits // len(self.article_urls)
        remainder = self.total_visits % len(self.article_urls)
        
        tasks = []
        async with aiohttp.ClientSession() as self.session:
            for i, url in enumerate(self.article_urls):
                count = visits_per_url + (1 if i < remainder else 0)
                for _ in range(count):
                    tasks.append(self.visit_url(url))
            
            await asyncio.gather(*tasks)
        
        logger.info(f"Normal visits completed: {self.success_count} success, {self.failure_count} failure")

    async def run_visits(self):
        """执行所有访问任务"""
        start_time = datetime.now()
        
        # 加载必刷URL
        if not await self.load_required_urls():
            await self.send_notification("⚠️ 初始化失败: 无法加载必刷URL列表")
            return
        
        # 执行访问
        await self.run_required_visits()
        await self.run_normal_visits()
        
        # 生成报告
        end_time = datetime.now()
        await self.send_report(start_time, end_time)

    async def send_report(self, start_time: datetime, end_time: datetime):
        """生成并发送统计报告"""
        duration = (end_time - start_time).total_seconds()
        total_requests = (
            self.required_stats['success'] + self.required_stats['failure'] +
            self.success_count + self.failure_count
        )
        rps = total_requests / duration if duration > 0 else 0
        
        # 构建消息
        message = [
            "📊 博客访问统计报告",
            f"⏱️ 时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%H:%M:%S')}",
            f"⏳ 耗时: {duration:.1f}秒 | 📈 速度: {rps:.1f}次/秒",
            "",
            "🔴 必刷URL统计:",
            f"  ✅ 成功: {self.required_stats['success']}",
            f"  ❌ 失败: {self.required_stats['failure']}",
            "",
            "🟢 普通访问统计:",
            f"  🎯 目标: {self.total_visits}次",
            f"  ✅ 成功: {self.success_count}",
            f"  ❌ 失败: {self.failure_count}",
            f"  📊 成功率: {self.success_count/self.total_visits*100:.1f}%" if self.total_visits > 0 else "",
            "",
            "📌 必刷URL访问分布:"
        ]
        
        # 添加URL详情
        for url, count in self.required_urls.items():
            message.append(f"  - {url.replace(BLOG_URL, '')}: {count}次")
        
        message.extend([
            "",
            "📝 普通URL访问分布:"
        ])
        
        for url, count in self.visited_urls.items():
            message.append(f"  - {url.replace(BLOG_URL, '')}: {count}次")
        
        message.extend([
            "",
            f"🌐 博客地址: {BLOG_URL}"
        ])
        
        await self.send_notification('\n'.join(filter(None, message)))

    async def send_notification(self, message: str):
        """通过Telegram发送通知"""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram配置不完整，跳过通知")
            return
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=TELEGRAM_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Telegram通知发送成功")
                    else:
                        error = await response.text()
                        logger.error(f"Telegram发送失败: HTTP {response.status} - {error}")
        except Exception as e:
            logger.error(f"发送Telegram通知出错: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Typecho博客访问模拟器")
    parser.add_argument(
        "-n", "--visits",
        type=int,
        default=100,
        help="普通访问次数(必刷URL不计入此数量)，默认100次"
    )
    args = parser.parse_args()
    
    visitor = BlogVisitor(args.visits)
    asyncio.run(visitor.run_visits())

if __name__ == "__main__":
    main()
