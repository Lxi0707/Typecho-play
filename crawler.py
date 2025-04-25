#!/usr/bin/env python3
import asyncio
import aiohttp
import random
import time
import sys
from bs4 import BeautifulSoup
import argparse
import logging
from typing import List, Dict, Tuple
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
        self.visited_urls = set()
        self.success_count = 0
        self.failure_count = 0
        self.article_urls = []

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

    async def get_article_urls(self, max_pages: int = 10) -> List[str]:
        """改进的文章URL抓取逻辑"""
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
                
                # 改进的选择器，适应Typecho的不同主题
                link_selectors = [
                    '.post-title a',  # 常见的选择器
                    'h2.title a',     # 另一种常见选择器
                    'article header h2 a',  # 更精确的选择器
                    'a[href*="/archives/"]'  # 通用匹配
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
                            
                            # 确保是文章URL且未重复
                            if (href.startswith(f"{self.base_url}/index.php/archives/") and 
                               href not in seen_urls and
                               re.match(r'.*/archives/\d+/.*', href):
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
                
                # 随机延迟防止请求过快
                await asyncio.sleep(random.uniform(1.0, 3.0))
        
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
        
        # 随机打乱URL顺序
        random.shuffle(urls)
        self.article_urls = urls
        return urls

    async def simulate_visits(self, times: int = 10, max_concurrent: int = 5):
        """改进的模拟访问方法"""
        self.success_count = 0
        self.failure_count = 0
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def visit_with_semaphore(url):
            async with semaphore:
                # 随机延迟
                delay = random.uniform(1.0, 5.0)
                await asyncio.sleep(delay)
                
                success, error = await self.fetch_url_with_retry(url)
                if success:
                    self.success_count += 1
                else:
                    self.failure_count += 1
                    logger.warning(f"Failed to visit {url}: {error}")
        
        # 创建访问任务
        tasks = []
        for _ in range(times):
            url = random.choice(self.article_urls)
            tasks.append(visit_with_semaphore(url))
        
        # 执行所有任务
        await asyncio.gather(*tasks)

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
            # 提取文章标题或ID
            match = re.search(r'/archives/(\d+)(?:/([^/]+))?', display_url)
            if match:
                article_id = match.group(1)
                article_slug = match.group(2) or ""
                return f"文章 {article_id} {article_slug}"
        return url

    def generate_report(self) -> str:
        """生成更详细的报告"""
        total_attempts = self.success_count + self.failure_count
        success_rate = (self.success_count / total_attempts * 100) if total_attempts > 0 else 0
        
        # 统计各文章被访问次数
        article_stats = "\n".join(
            f"{i+1}. {self.format_url_for_display(url)}"
            for i, url in enumerate(self.article_urls[:10])  # 只显示前10篇文章
        )
        
        if len(self.article_urls) > 10:
            article_stats += f"\n...（共 {len(self.article_urls)} 篇文章）"
        
        report_lines = [
            "📊 <b>博客访问模拟报告 - 优化版</b>",
            f"🏠 <b>博客地址:</b> {self.base_url}",
            f"🕒 <b>执行时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
            "",
            f"🔍 <b>发现文章数:</b> {len(self.article_urls)}",
            f"🔄 <b>总访问次数:</b> {total_attempts}",
            f"✅ <b>成功访问:</b> {self.success_count} 次",
            f"❌ <b>失败访问:</b> {self.failure_count} 次",
            f"📈 <b>成功率:</b> {success_rate:.1f}%",
            "",
            "📝 <b>部分文章列表:</b>",
            article_stats,
            "",
            "⚡ <b>执行结果:</b> " + ("✅ 成功" if success_rate > 70 else "⚠️ 一般" if success_rate > 50 else "❌ 不理想"),
            "",
            "💡 <b>建议:</b> " + (
                "访问情况良好，继续保持！" if success_rate > 80 else
                "访问成功率一般，建议检查服务器状态" if success_rate > 60 else
                "访问成功率较低，建议调整访问频率或检查网络设置"
            )
        ]
        
        return "\n".join(report_lines)

async def main():
    parser = argparse.ArgumentParser(description='Typecho博客模拟访问工具 - 优化版')
    parser.add_argument('--base-url', type=str, default='https://www.207725.xyz', help='博客基础URL')
    parser.add_argument('--times', type=int, default=30, help='模拟访问次数')
    parser.add_argument('--max-pages', type=int, default=5, help='最大抓取页面数')
    parser.add_argument('--tg-bot-token', type=str, help='Telegram Bot Token')
    parser.add_argument('--tg-chat-id', type=str, help='Telegram Chat ID')
    parser.add_argument('--max-concurrent', type=int, default=3, help='最大并发请求数')
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
        article_urls = await crawler.get_article_urls(max_pages=args.max_pages)
        logger.info(f"共找到 {len(article_urls)} 篇文章")
        
        if not article_urls:
            logger.error("未找到任何文章，退出程序")
            return
        
        # 模拟访问
        logger.info(f"开始模拟 {args.times} 次访问...")
        start_time = time.time()
        await crawler.simulate_visits(times=args.times, max_concurrent=args.max_concurrent)
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
