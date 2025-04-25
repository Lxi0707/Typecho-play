#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import time
import sys
from bs4 import BeautifulSoup
import argparse
import logging
from typing import List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class TypechoCrawler:
    def __init__(self, base_url: str, tg_bot_token: str = None, tg_chat_id: str = None):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.tg_bot_token = tg_bot_token
        self.tg_chat_id = tg_chat_id
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': self.base_url,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.visited_urls = set()
        self.success_count = 0
        self.failure_count = 0

    async def init_session(self):
        self.session = aiohttp.ClientSession(headers=self.headers, timeout=aiohttp.ClientTimeout(total=30))

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_url(self, url: str) -> bool:
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    logger.info(f"Successfully accessed: {url}")
                    return True
                else:
                    logger.warning(f"Failed to access {url}, status code: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error accessing {url}: {str(e)}")
            return False

    async def get_article_urls(self, max_pages: int = 5) -> List[str]:
        """从博客获取文章URL列表"""
        urls = []
        try:
            for page in range(1, max_pages + 1):
                list_url = f"{self.base_url}/index.php/archives/page/{page}" if page > 1 else self.base_url
                async with self.session.get(list_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # 查找文章链接 - 根据Typecho的结构调整
                        for link in soup.select('.post-title a'):
                            href = link.get('href')
                            if href and href.startswith('/'):
                                href = f"{self.base_url}{href}"
                            if href and href.startswith(self.base_url) and href not in urls:
                                urls.append(href)
                                logger.info(f"Found article: {href}")
                        
                        # 检查是否有下一页
                        next_page = soup.select_one('.next')
                        if not next_page:
                            break
                    else:
                        logger.warning(f"Failed to fetch article list page {page}, status: {response.status}")
                        break
        except Exception as e:
            logger.error(f"Error fetching article URLs: {str(e)}")
        
        # 如果没有找到文章，使用默认的几篇文章
        if not urls:
            logger.warning("No articles found, using default URLs")
            urls = [
                f"{self.base_url}/index.php/archives/13/",
                f"{self.base_url}/index.php/archives/5/",
                f"{self.base_url}/index.php/archives/1/"
            ]
        
        return urls

    async def simulate_visits(self, urls: List[str], times: int = 10, delay: float = 1.0):
        """模拟访问URL"""
        tasks = []
        self.success_count = 0
        self.failure_count = 0
        
        for _ in range(times):
            url = random.choice(urls)
            tasks.append(self.fetch_url(url))
            await asyncio.sleep(delay)  # 添加延迟避免过快请求
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                self.failure_count += 1
                logger.error(f"Task failed: {str(result)}")
            elif result:
                self.success_count += 1
            else:
                self.failure_count += 1

    async def send_telegram_notification(self, message: str):
        """发送Telegram通知"""
        if not self.tg_bot_token or not self.tg_chat_id:
            logger.warning("Telegram bot token or chat ID not provided, skipping notification")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
            data = {
                'chat_id': self.tg_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            
            async with self.session.post(url, json=data) as response:
                if response.status != 200:
                    logger.error(f"Failed to send Telegram notification, status: {response.status}")
                else:
                    logger.info("Telegram notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {str(e)}")

    def format_url_for_display(self, url: str) -> str:
        """格式化URL显示"""
        if url.startswith(self.base_url):
            return url[len(self.base_url):]
        return url

    def generate_report(self, urls: List[str]) -> str:
        """生成报告"""
        visited_counts = {url: 0 for url in urls}
        
        report_lines = [
            "📊 <b>博客访问模拟报告</b>",
            f"🏠 <b>博客地址:</b> {self.base_url}",
            f"🕒 <b>执行时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
            f"✅ <b>成功访问:</b> {self.success_count} 次",
            f"❌ <b>失败访问:</b> {self.failure_count} 次",
            "",
            "📝 <b>访问的文章:</b>"
        ]
        
        # 添加文章列表，美化显示
        for i, url in enumerate(urls, 1):
            display_url = self.format_url_for_display(url)
            report_lines.append(f"{i}. <a href='{url}'>{display_url}</a>")
        
        report_lines.extend([
            "",
            "⚡ <b>执行结果:</b> " + ("成功" if self.success_count > 0 else "失败"),
            f"📈 <b>成功率:</b> {self.success_count / (self.success_count + self.failure_count) * 100:.1f}%"
        ])
        
        return "\n".join(report_lines)

async def main():
    parser = argparse.ArgumentParser(description='Typecho博客模拟访问工具')
    parser.add_argument('--base-url', type=str, default='https://www.207725.xyz', help='博客基础URL')
    parser.add_argument('--times', type=int, default=10, help='模拟访问次数')
    parser.add_argument('--max-pages', type=int, default=3, help='最大抓取页面数')
    parser.add_argument('--tg-bot-token', type=str, help='Telegram Bot Token')
    parser.add_argument('--tg-chat-id', type=str, help='Telegram Chat ID')
    parser.add_argument('--delay', type=float, default=1.0, help='请求之间的延迟(秒)')
    args = parser.parse_args()

    crawler = TypechoCrawler(
        base_url=args.base_url,
        tg_bot_token=args.tg_bot_token,
        tg_chat_id=args.tg_chat_id
    )
    
    try:
        await crawler.init_session()
        
        # 获取文章URL
        logger.info("Fetching article URLs...")
        article_urls = await crawler.get_article_urls(max_pages=args.max_pages)
        logger.info(f"Found {len(article_urls)} articles")
        
        # 模拟访问
        logger.info(f"Simulating {args.times} visits...")
        await crawler.simulate_visits(article_urls, times=args.times, delay=args.delay)
        
        # 发送报告
        report = crawler.generate_report(article_urls)
        logger.info("\n" + report.replace('<b>', '').replace('</b>', ''))
        
        if crawler.tg_bot_token and crawler.tg_chat_id:
            await crawler.send_telegram_notification(report)
        
    except Exception as e:
        logger.error(f"Main error: {str(e)}")
    finally:
        await crawler.close_session()

if __name__ == '__main__':
    asyncio.run(main())
