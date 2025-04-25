import os
import re
import random
import asyncio
import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urljoin
from telegram import Bot
from telegram.error import TelegramError
from tqdm import tqdm

class EnhancedTypechoCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.log_file = 'crawl_log.txt'
        self.output_dir = 'typecho_output'
        self.blog_url = os.getenv('BLOG_URL', 'https://www.207725.xyz')
        self.start_page = int(os.getenv('START_PAGE', 1))
        self.max_pages = int(os.getenv('MAX_PAGES', 1))
        self.session = None
        self._init_dirs()
        
    def _init_dirs(self):
        """初始化目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"Typecho博客爬虫日志 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"博客URL: {self.blog_url}\n")
            f.write(f"开始页码: {self.start_page}, 最大页数: {self.max_pages}\n\n")
    
    async def _log(self, message):
        """异步记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry.strip())
        async with asyncio.Lock():
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
    
    async def _get_telegram_credentials(self):
        """获取Telegram凭证"""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not bot_token or not chat_id:
            raise ValueError("Telegram凭证未设置")
        return bot_token, chat_id
    
    async def _create_session(self):
        """创建aiohttp会话"""
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=5, force_close=True),
            headers={'Accept-Language': 'zh-CN,zh;q=0.9'},
            timeout=aiohttp.ClientTimeout(total=30)
        )
    
    async def _close_session(self):
        """关闭aiohttp会话"""
        if self.session:
            await self.session.close()
    
    async def _random_delay(self):
        """随机延迟"""
        delay = random.uniform(1, 3)
        await asyncio.sleep(delay)
    
    async def fetch_page(self, url):
        """获取页面内容"""
        try:
            headers = {'User-Agent': self.ua.random}
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            await self._log(f"获取页面失败: {url} - {str(e)}")
            return None
    
    def parse_post_links(self, html):
        """解析文章链接"""
        soup = BeautifulSoup(html, 'lxml')
        links = []
        for article in soup.select('article.post, div.post'):
            link = article.select_one('h2 a, h1 a')
            if link and 'href' in link.attrs:
                full_url = urljoin(self.blog_url, link['href'])
                links.append(full_url)
        return links
    
    async def get_all_post_links(self):
        """获取所有文章链接"""
        await self._log("开始收集文章链接...")
        post_links = []
        
        async with tqdm(total=self.max_pages, desc="收集文章链接") as pbar:
            for page in range(self.start_page, self.start_page + self.max_pages):
                page_url = f"{self.blog_url}/page/{page}/" if page > 1 else self.blog_url
                html = await self.fetch_page(page_url)
                if html:
                    links = self.parse_post_links(html)
                    post_links.extend(links)
                    await self._log(f"第{page}页找到{len(links)}篇文章")
                await self._random_delay()
                pbar.update(1)
        
        await self._log(f"共收集到{len(post_links)}篇文章链接")
        return post_links
    
    async def crawl_post(self, url):
        """爬取单篇文章"""
        try:
            html = await self.fetch_page(url)
            if not html:
                return None, None, None
            
            soup = BeautifulSoup(html, 'lxml')
            
            # 提取标题
            title = soup.select_one('h1.post-title, h1.entry-title, h1')
            title_text = title.get_text().strip() if title else "无标题"
            
            # 提取内容
            article = soup.select_one('div.post-content, article.post, div.post-body')
            if article:
                for element in article(['script', 'style', 'nav', 'footer', 'iframe', 'aside']):
                    element.decompose()
                content = article.get_text('\n', strip=True)
                content = re.sub(r'\s+', ' ', content)
            else:
                content = "无内容"
            
            # 提取发布日期
            date = soup.select_one('time.entry-date, time.post-date, .post-meta time')
            date_text = date['datetime'] if date and 'datetime' in date.attrs else (
                date.get_text().strip() if date else "未知日期"
            )
            
            # 保存到文件
            filename = f"{self.output_dir}/{title_text[:50]}.html".replace('/', '_')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"<h1>{title_text}</h1>\n")
                f.write(f"<p><strong>URL:</strong> <a href='{url}'>{url}</a></p>\n")
                f.write(f"<p><strong>发布日期:</strong> {date_text}</p>\n")
                if article:
                    f.write(article.prettify())
                else:
                    f.write(f"<pre>{content}</pre>")
            
            return title_text, content, url
        
        except Exception as e:
            await self._log(f"处理文章失败: {url} - {str(e)}")
            return None, None, None
    
    async def send_telegram_notification(self, posts):
        """发送Telegram通知"""
        try:
            bot_token, chat_id = await self._get_telegram_credentials()
            bot = Bot(token=bot_token)
            
            message = "📚 *博客文章更新通知*\n\n"
            message += f"*博客:* [{self.blog_url}]({self.blog_url})\n"
            message += f"*抓取时间:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            message += f"*发现文章数:* {len(posts)}\n\n"
            message += "*文章列表:*\n"
            
            for idx, (title, _, url) in enumerate(posts, 1):
                # 优化URL显示，只保留路径部分
                clean_url = url.replace(self.blog_url, '')
                message += f"{idx}. [{title}]({url}) `{clean_url}`\n"
                if idx % 5 == 0:  # 每5条消息分割一次
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    message = ""
                    await asyncio.sleep(1)
            
            if message.strip():
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            
            await self._log(f"成功发送{len(posts)}篇文章通知")
            return True
        
        except Exception as e:
            await self._log(f"发送通知失败: {str(e)}")
            return False
    
    async def run(self):
        """主运行方法"""
        await self._create_session()
        try:
            post_links = await self.get_all_post_links()
            crawled_posts = []
            
            await self._log("开始爬取文章内容...")
            for url in tqdm(post_links, desc="爬取文章"):
                title, content, url = await self.crawl_post(url)
                if title and content and url:
                    crawled_posts.append((title, content, url))
                await self._random_delay()
            
            if crawled_posts:
                await self.send_telegram_notification(crawled_posts)
            else:
                await self._log("没有找到可爬取的文章")
            
        finally:
            await self._close_session()

async def main():
    crawler = EnhancedTypechoCrawler()
    await crawler.run()

if __name__ == "__main__":
    asyncio.run(main())
