#!/usr/bin/env python3
"""
Typecho博客自动访问脚本
功能：
1. 从posts.txt加载必刷URL列表
2. 自动发现博客文章
3. 均匀分配访问量
4. Telegram通知
5. 详细统计报告
"""

import asyncio
import aiohttp
import random
import argparse
from datetime import datetime
import logging
import os
import sys
from typing import Dict, List, Tuple

# 基础配置
CONFIG = {
    'blog_url': 'https://www.207725.xyz',
    'posts_file': 'posts.txt',
    'telegram_timeout': 10,
    'request_timeout': 15,
    'min_delay': 0.3,
    'max_delay': 2.0,
    'default_urls': [
        '/index.php/archives/13/',
        '/index.php/archives/5/'
    ]
}

# 用户代理池 (2024年最新版)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"
]

class BlogVisitor:
    def __init__(self, visits: int):
        self.normal_visits = visits
        self.stats = {
            'required': {'success': 0, 'failure': 0, 'urls': {}},
            'normal': {'success': 0, 'failure': 0, 'urls': {}}
        }
        self.start_time = datetime.now()
        self._setup_logging()
        
        logger.info(f"初始化完成 | 普通访问量: {visits}")
        logger.info(f"Python {sys.version.split()[0]} | {sys.platform}")

    def _setup_logging(self):
        """配置日志系统"""
        global logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('visit.log', encoding='utf-8')
            ]
        )
        logger = logging.getLogger('typecho_visitor')

    async def _get_urls(self) -> Tuple[List[str], List[str]]:
        """获取URL列表：返回(必刷URLs, 普通URLs)"""
        required_urls = await self._load_required_urls()
        normal_urls = await self._discover_urls()
        return required_urls, normal_urls or self._get_fallback_urls()

    async def _load_required_urls(self) -> List[str]:
        """加载必刷URL列表"""
        try:
            if not os.path.exists(CONFIG['posts_file']):
                with open(CONFIG['posts_file'], 'w', encoding='utf-8') as f:
                    f.write('\n'.join(CONFIG['default_urls']))
                logger.warning(f"已创建默认 {CONFIG['posts_file']}")
            
            with open(CONFIG['posts_file'], 'r', encoding='utf-8') as f:
                return [self._normalize_url(line.strip()) for line in f if line.strip()]
        except Exception as e:
            logger.error(f"加载必刷URL失败: {str(e)}")
            return []

    async def _discover_urls(self) -> List[str]:
        """自动发现文章URL"""
        try:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            timeout = aiohttp.ClientTimeout(total=CONFIG['request_timeout'])
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(CONFIG['blog_url'], headers=headers) as resp:
                    if resp.status == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        return list({
                            self._normalize_url(a['href'])
                            for a in soup.find_all('a', href=True)
                            if '/archives/' in a['href']
                        })
                    logger.warning(f"发现文章失败 HTTP {resp.status}")
        except Exception as e:
            logger.error(f"文章发现错误: {str(e)}")
        return []

    def _normalize_url(self, url: str) -> str:
        """标准化URL格式"""
        if url.startswith('http'):
            return url
        return f"{CONFIG['blog_url']}{url if url.startswith('/') else '/' + url}"

    def _get_fallback_urls(self) -> List[str]:
        """获取备用URL列表"""
        return [self._normalize_url(url) for url in CONFIG['default_urls']]

    async def _visit(self, session: aiohttp.ClientSession, url: str, is_required: bool):
        """执行单次访问"""
        try:
            await asyncio.sleep(random.uniform(CONFIG['min_delay'], CONFIG['max_delay']))
            
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Referer': CONFIG['blog_url'],
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=CONFIG['request_timeout'])
            ) as resp:
                key = 'required' if is_required else 'normal'
                if resp.status == 200:
                    self.stats[key]['success'] += 1
                    self.stats[key]['urls'][url] = self.stats[key]['urls'].get(url, 0) + 1
                    logger.debug(f"访问成功: {url}")
                else:
                    self.stats[key]['failure'] += 1
                    logger.warning(f"访问失败: {url} (HTTP {resp.status})")
        except Exception as e:
            key = 'required' if is_required else 'normal'
            self.stats[key]['failure'] += 1
            logger.error(f"访问错误: {url} - {str(e)}")

    async def _run_visits(self, urls: List[str], is_required: bool = False):
        """执行批量访问"""
        if not urls:
            return logger.error("无有效URL可访问")
            
        logger.info(f"开始{'必刷' if is_required else '普通'}访问 | URL数量: {len(urls)}")
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            if is_required:
                tasks = [self._visit(session, url, True) for url in urls]
            else:
                base_count = self.normal_visits // len(urls)
                extra = self.normal_visits % len(urls)
                for i, url in enumerate(urls):
                    count = base_count + (1 if i < extra else 0)
                    tasks.extend([self._visit(session, url, False) for _ in range(count)])
            
            await asyncio.gather(*tasks)

    async def _send_report(self):
        """发送统计报告"""
        duration = (datetime.now() - self.start_time).total_seconds()
        total_success = sum(v['success'] for v in self.stats.values())
        total_failure = sum(v['failure'] for v in self.stats.values())
        
        def format_urls(url_type: str) -> str:
            return '\n'.join(
                f"  - {url.replace(CONFIG['blog_url'], '')}: {count}次"
                for url, count in self.stats[url_type]['urls'].items()
            )
        
        message = [
            "✨ Typecho访问统计报告",
            f"⏱️ 总耗时: {duration:.1f}秒",
            f"🌐 博客地址: {CONFIG['blog_url']}",
            "",
            "🔴 必刷URL统计:",
            f"  ✅ 成功: {self.stats['required']['success']}次",
            f"  ❌ 失败: {self.stats['required']['failure']}次",
            "",
            "🟢 普通访问统计:",
            f"  🎯 目标: {self.normal_visits}次",
            f"  ✅ 成功: {self.stats['normal']['success']}次",
            f"  ❌ 失败: {self.stats['normal']['failure']}次",
            f"  📊 成功率: {self.stats['normal']['success']/self.normal_visits*100:.1f}%" if self.normal_visits > 0 else "",
            "",
            "📌 必刷URL访问分布:",
            format_urls('required'),
            "",
            "📝 普通URL访问分布:",
            format_urls('normal')
        ]
        
        await self._notify_telegram('\n'.join(filter(None, message)))

    async def _notify_telegram(self, text: str):
        """发送Telegram通知"""
        if not (token := os.getenv('TELEGRAM_BOT_TOKEN')) or not (chat_id := os.getenv('TELEGRAM_CHAT_ID')):
            return logger.warning("未配置Telegram通知")
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=CONFIG['telegram_timeout'])
            ) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"Telegram通知失败: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Telegram通知错误: {str(e)}")

    async def execute(self):
        """主执行流程"""
        required_urls, normal_urls = await self._get_urls()
        
        await self._run_visits(required_urls, is_required=True)
        await self._run_visits(normal_urls)
        
        await self._send_report()
        logger.info("任务执行完成")

def main():
    parser = argparse.ArgumentParser(
        description="Typecho博客访问模拟器",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-n', '--visits',
        type=int,
        default=100,
        help='普通访问次数（必刷URL不计入）'
    )
    args = parser.parse_args()
    
    visitor = BlogVisitor(args.visits)
    asyncio.run(visitor.execute())

if __name__ == '__main__':
    main()
