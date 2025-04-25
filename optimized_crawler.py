#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import time
import sys
from bs4 import BeautifulSoup
import argparse
import logging
from typing import List, Dict, Tuple, DefaultDict
from collections import defaultdict
import re

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
        self.article_urls = []
        self.visit_stats = defaultdict(lambda: {'success': 0, 'failed': 0})

    async def init_session(self):
        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60)
        )

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_url_with_retry(self, url: str, max_retries: int = 3) -> Tuple[bool, str]:
        """带重试机制的URL访问"""
        last_error = ""
        for attempt in range(max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return True, ""
                    last_error = f"HTTP status {response.status}"
                    if response.status == 429:  # Too Many Requests
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"Rate limited, waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
            except Exception as e:
                last_error = str(e)
            
            if attempt < max_retries - 1:
                wait_time = random.uniform(1.0, 3.0) * (attempt + 1)
                logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        return False, last_error

    def is_valid_article_url(self, href: str) -> bool:
        """验证URL是否是有效的文章URL"""
        if not href.startswith(f"{self.base_url}/index.php/archives/"):
            return False
        if not re.search(r'/archives/\d+/', href):
            return False
        return True

    async def get_article_urls(self, max_pages: int = 10) -> List[str]:
        """获取所有文章URL"""
        urls = []
        seen_urls = set()
        
        try:
            for page in range(1, max_pages + 1):
                list_url = f"{self.base_url}/index.php/archives/page/{page}" if page > 1 else self.base_url
                
                logger.info(f"Fetching articles from page {page}: {list_url}")
                success, error = await self.fetch_url_with_retry(list_url)
                
                if not success:
                    logger.warning(f"Failed to fetch page {page}: {error}")
                    continue
                
                async with self.session.get(list_url) as response:
                    html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # 多种选择器确保找到所有文章链接
                link_selectors = [
                    '.post-title a', 
                    'h2.title a',
                    'article header h2 a',
                    'a[href*="/archives/"]'
                ]
                
                found_links = False
                for selector in link_selectors:
                    links = soup.select(selector)
                    if links:
                        found_links = True
                        for link in links:
                            href = link.get('href', '').strip()
                            if not href:
                                continue
                                
                            # 规范化URL
                            if href.startswith('/'):
                                href = f"{self.base_url}{href}"
                            elif not href.startswith(('http://', 'https://')):
                                href = f"{self.base_url}/{href}"
                            
                            if self.is_valid_article_url(href) and href not in seen_urls:
                                seen_urls.add(href)
                                urls.append(href)
                                logger.debug(f"Found article: {href}")
                        
                        if found_links:
                            break
                
                if not found_links:
                    logger.warning(f"No article links found on page {page} with selectors")
                
                # 检查是否有下一页
                next_page = soup.select_one('.next, .page-navigator a:contains("下一页"), a[rel="next"]')
                if not next_page:
                    logger.info(f"No more pages found after page {page}")
                    break
                
                await asyncio.sleep(random.uniform(1.0, 3.0))
        
        except Exception as e:
            logger.error(f"Error fetching article URLs: {str(e)}")
        
        if not urls:
            logger.warning("No articles found, using default URLs")
            urls = [
                f"{self.base_url}/index.php/archives/13/",
                f"{self.base_url}/index.php/archives/5/",
                f"{self.base_url}/index.php/archives/1/"
            ]
        
        self.article_urls = urls
        return urls

    async def simulate_visits(self, total_visits: int = 100, max_concurrent: int = 5):
        """精确分配访问量的模拟访问方法"""
        if not self.article_urls:
            logger.error("No articles to visit")
            return
        
        # 计算每篇文章的基础访问次数和剩余次数
        base_visits = total_visits // len(self.article_urls)
        remaining_visits = total_visits % len(self.article_urls)
        
        # 创建访问任务列表
        tasks = []
        for i, url in enumerate(self.article_urls):
            visits = base_visits + (1 if i < remaining_visits else 0)
            for _ in range(visits):
                tasks.append(url)
        
        # 随机打乱任务顺序
        random.shuffle(tasks)
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def visit_with_semaphore(url):
            async with semaphore:
                # 随机延迟
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                success, error = await self.fetch_url_with_retry(url)
                if success:
                    self.visit_stats[url]['success'] += 1
                else:
                    self.visit_stats[url]['failed'] += 1
                    logger.warning(f"Failed to visit {url}: {error}")
        
        # 执行所有任务
        logger.info(f"Starting {len(tasks)} visits ({total_visits} requested)...")
        start_time = time.time()
        await asyncio.gather(*[visit_with_semaphore(url) for url in tasks])
        elapsed = time.time() - start_time
        logger.info(f"Completed {len(tasks)} visits in {elapsed:.1f} seconds")

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
                    response_text = await response.text()
                    logger.error(f"Failed to send Telegram notification, status: {response.status}, response: {response_text}")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {str(e)}")

    def format_url_for_display(self, url: str) -> str:
        """格式化URL显示"""
        if url.startswith(self.base_url):
            display_url = url[len(self.base_url):]
            match = re.search(r'/archives/(\d+)(?:/([^/]+))?', display_url)
            if match:
                article_id = match.group(1)
                article_slug = match.group(2) or ""
                return f"/archives/{article_id} {article_slug}"
        return url

    def generate_report(self) -> str:
        """生成详细的统计报告"""
        total_success = sum(stats['success'] for stats in self.visit_stats.values())
        total_failed = sum(stats['failed'] for stats in self.visit_stats.values())
        total_attempts = total_success + total_failed
        success_rate = (total_success / total_attempts * 100) if total_attempts > 0 else 0
        
        # 每篇文章的访问详情
        article_details = []
        for url in sorted(self.article_urls, key=lambda x: self.visit_stats[x]['success'], reverse=True):
            stats = self.visit_stats[url]
            article_details.append(
                f"{self.format_url_for_display(url)} - "
                f"✅{stats['success']} ❌{stats['failed']} "
                f"({stats['success']/(stats['success']+stats['failed'])*100:.1f}%)"
            )
        
        # 构建报告内容
        report_lines = [
            "📊 <b>博客访问模拟详细报告</b>",
            f"🏠 <b>博客地址:</b> {self.base_url}",
            f"🕒 <b>执行时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
            "",
            f"🔍 <b>发现文章数:</b> {len(self.article_urls)}",
            f"🔄 <b>总访问次数:</b> {total_attempts}",
            f"✅ <b>成功访问:</b> {total_success} 次",
            f"❌ <b>失败访问:</b> {total_failed} 次",
            f"📈 <b>总成功率:</b> {success_rate:.1f}%",
            "",
            "📝 <b>文章访问详情:</b>",
            *article_details[:20],  # 最多显示20篇文章详情
            "",
            f"⚡ <b>执行结果:</b> {'✅ 成功' if success_rate > 90 else '⚠️ 一般' if success_rate > 70 else '❌ 不理想'}",
            "",
            "💡 <b>建议:</b> " + (
                "访问情况非常理想" if success_rate > 90 else
                "访问情况良好，可适当增加访问量" if success_rate > 80 else
                "访问成功率一般，建议检查服务器状态" if success_rate > 60 else
                "访问成功率较低，建议调整访问频率或检查网络设置"
            )
        ]
        
        if len(article_details) > 20:
            report_lines.insert(-4, f"...（共 {len(article_details)} 篇文章的详细数据）")
        
        return "\n".join(report_lines)

async def main():
    parser = argparse.ArgumentParser(description='Typecho博客精确访问模拟工具')
    parser.add_argument('--base-url', type=str, default='https://www.207725.xyz', help='博客基础URL')
    parser.add_argument('--visits', type=int, default=100, help='总访问次数')
    parser.add_argument('--max-pages', type=int, default=10, help='最大抓取页面数')
    parser.add_argument('--tg-bot-token', type=str, help='Telegram Bot Token')
    parser.add_argument('--tg-chat-id', type=str, help='Telegram Chat ID')
    parser.add_argument('--max-concurrent', type=int, default=5, help='最大并发请求数')
    args = parser.parse_args()

    crawler = TypechoCrawler(
        base_url=args.base_url,
        tg_bot_token=args.tg_bot_token,
        tg_chat_id=args.tg_chat_id
    )
    
    try:
        await crawler.init_session()
        
        # 获取文章URL
        logger.info("开始抓取文章URL...")
        start_time = time.time()
        article_urls = await crawler.get_article_urls(max_pages=args.max_pages)
        elapsed = time.time() - start_time
        logger.info(f"共找到 {len(article_urls)} 篇文章，耗时 {elapsed:.1f} 秒")
        
        if not article_urls:
            logger.error("未找到任何文章，退出程序")
            return
        
        # 模拟访问
        logger.info(f"开始模拟 {args.visits} 次访问...")
        start_time = time.time()
        await crawler.simulate_visits(total_visits=args.visits, max_concurrent=args.max_concurrent)
        elapsed = time.time() - start_time
        logger.info(f"模拟访问完成，耗时 {elapsed:.1f} 秒")
        
        # 发送报告
        report = crawler.generate_report()
        logger.info("\n" + report.replace('<b>', '').replace('</b>', ''))
        
        if crawler.tg_bot_token and crawler.tg_chat_id:
            await crawler.send_telegram_notification(report)
        
    except Exception as e:
        logger.error(f"主程序错误: {str(e)}")
        if crawler.tg_bot_token and crawler.tg_chat_id:
            await crawler.send_telegram_notification(f"⚠️ 博客访问脚本出错:\n{str(e)}")
    finally:
        await crawler.close_session()

if __name__ == '__main__':
    asyncio.run(main())
