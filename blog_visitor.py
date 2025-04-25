#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import argparse
from datetime import datetime
import logging
import os
import sys
from typing import Dict, List, Optional

# 配置部分
BLOG_URL = "https://www.207725.xyz"
POSTS_FILE = "posts.txt"  # 必刷URL列表文件
TELEGRAM_TIMEOUT = 10  # Telegram通知超时(秒)
REQUEST_TIMEOUT = 15    # 请求超时(秒)

# 用户代理列表 (更新至2024年最新版本)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
]

class BlogVisitor:
    def __init__(self, total_visits: int):
        self.total_visits = total_visits
        self.stats = {
            'required': {'success': 0, 'failure': 0},
            'normal': {'success': 0, 'failure': 0}
        }
        self.visited_urls: Dict[str, Dict[str, int]] = {
            'required': {},
            'normal': {}
        }
        self.session = None
        self._setup_logging()
        
        logger.info(f"Initialized with {total_visits} normal visits")
        logger.info(f"Python {sys.version.split()[0]} on {sys.platform}")

    def _setup_logging(self):
        """配置日志系统"""
        global logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('visitor.log', encoding='utf-8')
            ]
        )
        logger = logging.getLogger(__name__)

    async def _load_urls_from_file(self, filename: str) -> List[str]:
        """从文件加载URL列表"""
        try:
            if not os.path.exists(filename):
                default_urls = [
                    f"{BLOG_URL}/index.php/archives/13/",
                    f"{BLOG_URL}/index.php/archives/5/"
                ]
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(default_urls))
                logger.warning(f"Created {filename} with default URLs")
                return default_urls
            
            with open(filename, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
                return [
                    url if url.startswith('http') else f"{BLOG_URL}{url}"
                    for url in urls
                ]
        except Exception as e:
            logger.error(f"Failed to load {filename}: {str(e)}")
            return []

    async def _fetch_articles(self) -> List[str]:
        """从博客获取文章列表"""
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(BLOG_URL, headers=headers) as resp:
                    if resp.status == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        return list({
                            link['href'] if link['href'].startswith('http') 
                            else f"{BLOG_URL}{link['href']}"
                            for link in soup.find_all('a', href=True)
                            if '/archives/' in link['href']
                        })
                    logger.warning(f"Fetch failed: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching articles: {str(e)}")
        
        return self._get_fallback_urls()

    def _get_fallback_urls(self) -> List[str]:
        """获取备用URL列表"""
        return [
            f"{BLOG_URL}/index.php/archives/13/",
            f"{BLOG_URL}/index.php/archives/5/",
            f"{BLOG_URL}/index.php/archives/1/"
        ]

    async def _visit_url(self, url: str, is_required: bool = False):
        """访问单个URL"""
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Referer": BLOG_URL,
                "DNT": "1",
            }
            
            await asyncio.sleep(random.uniform(0.3, 2.0))
            
            async with self.session.get(
                url, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                key = 'required' if is_required else 'normal'
                if resp.status == 200:
                    self.stats[key]['success'] += 1
                    self.visited_urls[key][url] = self.visited_urls[key].get(url, 0) + 1
                    logger.debug(f"Visited: {url}")
                else:
                    self.stats[key]['failure'] += 1
                    logger.warning(f"Failed {url} (HTTP {resp.status})")
        except Exception as e:
            key = 'required' if is_required else 'normal'
            self.stats[key]['failure'] += 1
            logger.error(f"Error visiting {url}: {str(e)}")

    async def run_required_visits(self):
        """执行必刷URL访问"""
        required_urls = await self._load_urls_from_file(POSTS_FILE)
        if not required_urls:
            logger.error("No required URLs to visit")
            return
            
        logger.info(f"Starting required visits for {len(required_urls)} URLs")
        
        async with aiohttp.ClientSession() as self.session:
            tasks = [self._visit_url(url, True) for url in required_urls]
            await asyncio.gather(*tasks)
        
        logger.info(f"Required visits completed: {self.stats['required']['success']} success")

    async def run_normal_visits(self):
        """执行普通访问"""
        if self.total_visits <= 0:
            logger.info("Skipping normal visits")
            return
            
        article_urls = await self._fetch_articles() or self._get_fallback_urls()
        if not article_urls:
            logger.error("No articles found for normal visits")
            return
            
        logger.info(f"Distributing {self.total_visits} visits across {len(article_urls)} URLs")
        
        base_visits = self.total_visits // len(article_urls)
        extra_visits = self.total_visits % len(article_urls)
        
        async with aiohttp.ClientSession() as self.session:
            tasks = []
            for i, url in enumerate(article_urls):
                visits = base_visits + (1 if i < extra_visits else 0)
                tasks.extend([self._visit_url(url) for _ in range(visits)])
            
            await asyncio.gather(*tasks)
        
        logger.info(f"Normal visits completed: {self.stats['normal']['success']} success")

    async def generate_report(self) -> str:
        """生成统计报告"""
        total_success = sum(s['success'] for s in self.stats.values())
        total_failure = sum(s['failure'] for s in self.stats.values())
        
        report = [
            "📊 博客访问统计报告",
            f"🌐 博客地址: {BLOG_URL}",
            "",
            "🔴 必刷URL统计:",
            f"  ✅ 成功: {self.stats['required']['success']}",
            f"  ❌ 失败: {self.stats['required']['failure']}",
            "",
            "🟢 普通访问统计:",
            f"  🎯 目标: {self.total_visits}",
            f"  ✅ 成功: {self.stats['normal']['success']}",
            f"  ❌ 失败: {self.stats['normal']['failure']}",
            f"  📊 成功率: {self.stats['normal']['success']/self.total_visits*100:.1f}%" if self.total_visits > 0 else "",
            "",
            "📌 访问分布详情:"
        ]
        
        for url_type in ['required', 'normal']:
            if self.visited_urls[url_type]:
                report.append(f"\n{(url_type.capitalize())} URLs:")
                for url, count in self.visited_urls[url_type].items():
                    report.append(f"  - {url.replace(BLOG_URL, '')}: {count}次")
        
        return '\n'.join(report)

    async def send_telegram_notification(self, message: str):
        """发送Telegram通知"""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram配置缺失，跳过通知")
            return
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TELEGRAM_TIMEOUT)
            ) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"Telegram发送失败: HTTP {resp.status} - {error}")
        except Exception as e:
            logger.error(f"发送Telegram通知出错: {str(e)}")

    async def run(self):
        """主执行流程"""
        start_time = datetime.now()
        
        await self.run_required_visits()
        await self.run_normal_visits()
        
        report = await self.generate_report()
        await self.send_telegram_notification(report)
        
        logger.info(f"Total execution time: {(datetime.now()-start_time).total_seconds():.1f}s")

def main():
    parser = argparse.ArgumentParser(
        description="Typecho博客访问模拟器",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-n", "--visits",
        type=int,
        default=100,
        help="普通访问次数(必刷URL不计入此数量)"
    )
    args = parser.parse_args()
    
    visitor = BlogVisitor(args.visits)
    asyncio.run(visitor.run())

if __name__ == "__main__":
    main()
