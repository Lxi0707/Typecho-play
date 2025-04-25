#!/usr/bin/env python3
"""
Typecho博客专业访问脚本V3.2
更新内容：
1. 修复GitHub Actions参数传递问题
2. 保持所有原有功能不变
3. 增强错误处理
"""

import asyncio
import aiohttp
import random
import argparse
from datetime import datetime
import logging
import os
import sys
from typing import Dict, List, Tuple, Optional

# 全局配置
CONFIG = {
    'blog_url': 'https://www.207725.xyz',
    'posts_file': 'posts.txt',
    'telegram_timeout': 15,
    'request_timeout': 20,
    'min_delay': 1.0,
    'max_delay': 3.0,
    'max_retries': 2,
    'conn_limit': 10,
    'req_per_url': 3,  # 默认每个必刷URL访问次数
    'default_urls': [
        '/index.php/archives/13/',
        '/index.php/archives/5/'
    ]
}

# 用户代理池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
]

class TypechoVisitor:
    def __init__(self, normal_visits: int, required_visits: Optional[int] = None):
        self.normal_visits = normal_visits
        self.required_visits = required_visits if required_visits is not None else CONFIG['req_per_url']
        self.stats = {
            'required': {'success': 0, 'failure': 0, 'urls': {}},
            'normal': {'success': 0, 'failure': 0, 'urls': {}}
        }
        self.start_time = datetime.now()
        self._setup_logging()
        
        logger.info(f"初始化完成 | 普通访问: {normal_visits}次 | 必刷访问: {self.required_visits}次/URL")

    def _setup_logging(self):
        """配置日志系统"""
        global logger
        logger = logging.getLogger('typecho_visitor')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        file_handler = logging.FileHandler('visit.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    async def _get_connector(self):
        """创建优化的TCP连接器"""
        return aiohttp.TCPConnector(
            limit=CONFIG['conn_limit'],
            force_close=False,
            enable_cleanup_closed=True,
            ssl=False
        )

    async def _get_urls(self) -> Tuple[List[str], List[str]]:
        """获取URL列表：(必刷URLs, 普通URLs)"""
        required = await self._load_required_urls()
        normal = await self._discover_normal_urls()
        return required, normal or self._get_fallback_urls()

    async def _load_required_urls(self) -> List[str]:
        """加载必刷URL列表"""
        try:
            if not os.path.exists(CONFIG['posts_file']):
                with open(CONFIG['posts_file'], 'w', encoding='utf-8') as f:
                    f.write('\n'.join(CONFIG['default_urls']))
                logger.info(f"已创建默认 {CONFIG['posts_file']}")
            
            with open(CONFIG['posts_file'], 'r', encoding='utf-8') as f:
                return [self._normalize_url(line.strip()) for line in f if line.strip()]
        except Exception as e:
            logger.error(f"加载必刷URL失败: {str(e)}")
            return []

    async def _discover_normal_urls(self) -> List[str]:
        """发现普通文章URL"""
        try:
            async with aiohttp.ClientSession(
                connector=await self._get_connector(),
                timeout=aiohttp.ClientTimeout(total=CONFIG['request_timeout'])
            ) as session:
                async with session.get(
                    CONFIG['blog_url'],
                    headers={'User-Agent': random.choice(USER_AGENTS)}
                ) as resp:
                    if resp.status == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        return list({
                            self._normalize_url(a['href'])
                            for a in soup.find_all('a', href=True)
                            if '/archives/' in a['href'] and '#' not in a['href']
                        })
        except Exception as e:
            logger.error(f"发现文章异常: {str(e)}")
        return []

    def _normalize_url(self, url: str) -> str:
        """标准化URL格式"""
        if url.startswith('http'):
            return url.split('#')[0]
        return f"{CONFIG['blog_url']}{url if url.startswith('/') else '/' + url}".split('#')[0]

    def _get_fallback_urls(self) -> List[str]:
        """获取备用URL列表"""
        return [self._normalize_url(url) for url in CONFIG['default_urls']]

    async def _visit(self, session: aiohttp.ClientSession, url: str, is_required: bool):
        """执行单次访问（含重试机制）"""
        key = 'required' if is_required else 'normal'
        
        for attempt in range(CONFIG['max_retries'] + 1):
            try:
                await asyncio.sleep(random.uniform(CONFIG['min_delay'], CONFIG['max_delay']))
                
                async with session.get(
                    url,
                    headers={
                        'User-Agent': random.choice(USER_AGENTS),
                        'Accept': 'text/html,application/xhtml+xml',
                        'Referer': CONFIG['blog_url']
                    },
                    timeout=aiohttp.ClientTimeout(total=CONFIG['request_timeout'])
                ) as resp:
                    if resp.status == 200:
                        self.stats[key]['success'] += 1
                        self.stats[key]['urls'][url] = self.stats[key]['urls'].get(url, 0) + 1
                        return True
                    logger.warning(f"访问失败[{attempt+1}]: {url} (HTTP {resp.status})")
            except Exception as e:
                logger.warning(f"访问异常[{attempt+1}]: {url} - {type(e).__name__}")
            
            if attempt < CONFIG['max_retries']:
                await asyncio.sleep(1)
        
        self.stats[key]['failure'] += 1
        return False

    async def _run_required_visits(self, urls: List[str]):
        """执行必刷URL访问"""
        if not urls:
            return logger.warning("没有必刷URL，跳过该阶段")
            
        logger.info(f"开始必刷访问 | URL数: {len(urls)} | 每URL次数: {self.required_visits}")
        
        async with aiohttp.ClientSession(
            connector=await self._get_connector(),
            timeout=aiohttp.ClientTimeout(total=CONFIG['request_timeout'])
        ) as session:
            tasks = []
            for url in urls:
                for _ in range(self.required_visits):
                    tasks.append(self._visit(session, url, True))
            
            await asyncio.gather(*tasks)

    async def _run_normal_visits(self, urls: List[str]):
        """执行普通URL访问"""
        if self.normal_visits <= 0:
            return logger.info("普通访问次数为0，跳过该阶段")
            
        if not urls:
            return logger.error("没有可用的普通URL")
            
        base_visits = self.normal_visits // len(urls)
        extra_visits = self.normal_visits % len(urls)
        
        logger.info(f"开始普通访问 | URL数: {len(urls)} | 总次数: {self.normal_visits}")
        
        async with aiohttp.ClientSession(
            connector=await self._get_connector(),
            timeout=aiohttp.ClientTimeout(total=CONFIG['request_timeout'])
        ) as session:
            tasks = []
            for i, url in enumerate(urls):
                visits = base_visits + (1 if i < extra_visits else 0)
                for _ in range(visits):
                    tasks.append(self._visit(session, url, False))
            
            await asyncio.gather(*tasks)

    def _generate_report(self) -> str:
        """生成统计报告"""
        duration = (datetime.now() - self.start_time).total_seconds()
        req = self.stats['required']
        norm = self.stats['normal']
        
        def format_urls(urls: Dict[str, int], limit: int = 15) -> str:
            sorted_items = sorted(urls.items(), key=lambda x: -x[1])[:limit]
            return '\n'.join(
                f"  - {url.replace(CONFIG['blog_url'], ''):<35}: {count}次"
                for url, count in sorted_items
            )
        
        return (
            "📊 Typecho访问报告\n\n"
            f"⏱️ 总耗时: {duration:.1f}秒\n"
            f"🌐 博客地址: {CONFIG['blog_url']}\n\n"
            "🔴 必刷访问统计:\n"
            f"  • 成功: {req['success']}次\n"
            f"  • 失败: {req['failure']}次\n"
            f"  • 成功率: {req['success']/(req['success']+req['failure'])*100:.1f}%\n\n"
            "🟢 普通访问统计:\n"
            f"  • 成功: {norm['success']}次\n"
            f"  • 失败: {norm['failure']}次\n"
            f"  • 成功率: {norm['success']/self.normal_visits*100:.1f}%\n\n"
            "📌 必刷URL访问详情:\n"
            f"{format_urls(req['urls'])}\n\n"
            "📝 普通URL访问TOP15:\n"
            f"{format_urls(norm['urls'])}"
        )

    async def _send_report(self):
        """发送Telegram报告"""
        report = self._generate_report()
        logger.info("\n" + report)
        
        if not (token := os.getenv('TELEGRAM_BOT_TOKEN')) or not (chat_id := os.getenv('TELEGRAM_CHAT_ID')):
            return logger.warning("未配置Telegram通知")
            
        try:
            async with aiohttp.ClientSession(
                connector=await self._get_connector(),
                timeout=aiohttp.ClientTimeout(total=CONFIG['telegram_timeout'])
            ) as session:
                await session.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        'chat_id': chat_id,
                        'text': report,
                        'parse_mode': 'Markdown',
                        'disable_web_page_preview': True
                    }
                )
        except Exception as e:
            logger.error(f"发送报告失败: {str(e)}")

    async def execute(self):
        """主执行流程"""
        required_urls, normal_urls = await self._get_urls()
        
        await self._run_required_visits(required_urls)
        await self._run_normal_visits(normal_urls)
        
        await self._send_report()
        logger.info("任务执行完成")

def main():
    parser = argparse.ArgumentParser(
        description="Typecho博客专业访问脚本",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-n', '--normal-visits',
        type=int,
        default=500,
        help='普通访问目标次数（默认500）'
    )
    parser.add_argument(
        '-r', '--required-visits',
        type=int,
        help='每个必刷URL的访问次数（默认3次）'
    )
    args = parser.parse_args()
    
    visitor = TypechoVisitor(
        normal_visits=args.normal_visits,
        required_visits=args.required_visits
    )
    asyncio.run(visitor.execute())

if __name__ == '__main__':
    main()
