import os
import sys
import re
import random
import asyncio
import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from telegram import Bot
from telegram.error import TelegramError

class AsyncTypechoCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.log_file = 'async_crawl_log.txt'
        self.connector = None
        self.session = None
        self._init_log()
        
    def _init_log(self):
        """初始化日志文件"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"异步Typecho爬虫日志 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    async def _log(self, message):
        """异步记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry.strip())
        async with asyncio.Lock():
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
    
    async def _get_telegram_credentials(self):
        """获取 Telegram 凭证"""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            raise ValueError("Telegram 凭证未在环境变量中找到")
        
        return bot_token, chat_id
    
    def _clean_content(self, content):
        """清理文章内容"""
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'post-(footer|tags|copyright)', '', content)
        return content.strip()
    
    async def _random_delay(self):
        """随机延迟 1-3 秒"""
        delay = random.uniform(1, 3)
        await self._log(f"随机延迟 {delay:.2f} 秒...")
        await asyncio.sleep(delay)
    
    async def _create_session(self):
        """创建aiohttp会话"""
        self.connector = aiohttp.TCPConnector(
            limit=5,  # 同时最大连接数
            force_close=True,
            enable_cleanup_closed=True,
            ttl_dns_cache=300
        )
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            headers={'Accept-Language': 'zh-CN,zh;q=0.9'},
            timeout=aiohttp.ClientTimeout(total=30)
        )
    
    async def _close_session(self):
        """关闭aiohttp会话"""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
    
    async def _simulate_visit(self, url, visit_num):
        """模拟单次异步访问"""
        try:
            headers = {
                'User-Agent': self.ua.random,
                'Referer': 'https://www.207725.xyz' if visit_num == 1 else url
            }
            
            await self._log(f"模拟访问 #{visit_num} - 使用 UA: {headers['User-Agent']}")
            await self._random_delay()
            
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.text()
        
        except Exception as e:
            await self._log(f"模拟访问 #{visit_num} 失败: {str(e)}")
            return None
    
    async def crawl_typecho_post(self, url, visit_count=1):
        """异步爬取 Typecho 博客文章"""
        try:
            visit_count = min(max(int(visit_count), 1), 5)  # 限制1-5次
            
            await self._log(f"开始异步爬取: {url} (模拟访问次数: {visit_count})")
            await self._create_session()
            
            # 创建所有访问任务
            tasks = [self._simulate_visit(url, i+1) for i in range(visit_count)]
            html_contents = await asyncio.gather(*tasks)
            
            # 过滤掉失败的访问
            html_contents = [html for html in html_contents if html is not None]
            
            if not html_contents:
                return "访问失败", ""
            
            # 使用最后一次成功访问的结果
            soup = BeautifulSoup(html_contents[-1], 'lxml')
            
            # Typecho 文章标题
            title = soup.select_one('h1.post-title, h1')
            title_text = title.get_text().strip() if title else "未找到标题"
            
            # Typecho 文章内容
            article = soup.select_one('div.post-content, article.post, div.post-body')
            
            if article:
                # 移除不需要的元素
                for element in article(['script', 'style', 'nav', 'footer', 'iframe', 'aside', 'div.post-meta', 'div.post-footer']):
                    element.decompose()
                
                content = self._clean_content(article.get_text('\n', strip=True))
            else:
                content = "未找到文章内容"
            
            # 保存结果到 HTML 文件
            with open('typecho_output.html', 'w', encoding='utf-8') as f:
                f.write(f"<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n")
                f.write(f"<title>{title_text}</title>\n</head>\n<body>\n")
                f.write(f"<h1>{title_text}</h1>\n")
                f.write(f"<p><strong>URL:</strong> <a href='{url}'>{url}</a></p>\n")
                f.write(f"<p><strong>抓取时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
                f.write(f"<p><strong>模拟访问次数:</strong> {visit_count}</p>\n")
                if article:
                    f.write(article.prettify())
                else:
                    f.write(f"<pre>{content}</pre>")
                f.write("\n</body>\n</html>")
            
            return title_text, content
        
        except Exception as e:
            await self._log(f"爬取过程中发生错误: {str(e)}")
            return f"处理错误: {str(e)}", ""
        finally:
            await self._close_session()
    
    async def send_telegram_notification(self, title, content, url, visit_count):
        """异步发送 Telegram 通知"""
        try:
            bot_token, chat_id = await self._get_telegram_credentials()
            bot = Bot(token=bot_token)
            
            message = f"📝 *异步博客文章抓取完成*\n\n"
            message += f"*标题:* {title}\n"
            message += f"*链接:* [点击查看]({url})\n"
            message += f"*模拟访问次数:* {visit_count}\n\n"
            
            # 发送标题消息
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            
            # 如果内容太长，分开发送
            chunk_size = 3000
            content_chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
            
            # 发送内容分块
            for i, chunk in enumerate(content_chunks, 1):
                chunk_msg = f"*内容 (部分 {i}/{len(content_chunks)}):*\n{chunk}"
                await bot.send_message(
                    chat_id=chat_id,
                    text=chunk_msg,
                    parse_mode='Markdown'
                )
                await asyncio.sleep(1)  # 避免发送过快
            
            await self._log("Telegram 通知发送成功")
            return True
        
        except TelegramError as e:
            await self._log(f"发送 Telegram 通知失败: {str(e)}")
            return False
        except Exception as e:
            await self._log(f"发送通知时发生错误: {str(e)}")
            return False

async def main():
    if len(sys.argv) < 2:
        print("使用方法: python async_typecho_crawler.py <url> [visit_count]")
        return
    
    target_url = sys.argv[1]
    visit_count = sys.argv[2] if len(sys.argv) > 2 else 1
    
    crawler = AsyncTypechoCrawler()
    
    title, content = await crawler.crawl_typecho_post(target_url, visit_count)
    
    if title and content:
        success = await crawler.send_telegram_notification(title, content, target_url, visit_count)
        await crawler._log(f"爬取{'并通知' if success else '但通知失败'}")
    else:
        await crawler._log("爬取失败，未发送通知")

if __name__ == "__main__":
    asyncio.run(main())
