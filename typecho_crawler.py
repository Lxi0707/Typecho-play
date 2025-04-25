import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

def get_telegram_credentials():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        raise ValueError("Telegram credentials not found")
    return bot_token, chat_id

def clean_content(content):
    """优化内容清理逻辑"""
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'(post-(footer|tags|copyright)|comment-)', '', content)
    return content.strip()

def send_telegram_notification(title, content, url):
    try:
        bot_token, chat_id = get_telegram_credentials()
        bot = Bot(token=bot_token)
        
        # 优化URL显示
        clean_url = url.replace('https://www.207725.xyz', '')
        
        message = f"📝 *博客文章抓取结果*\n\n"
        message += f"*标题:* {title}\n"
        message += f"*路径:* `{clean_url}`\n"
        message += f"*完整链接:* [点击查看]({url})\n\n"
        message += f"*内容摘要:*\n{content[:1000]}..." if len(content) > 1000 else content
        
        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        log(f"通知发送成功: {title}")
        return True
    except Exception as e:
        log(f"发送通知失败: {str(e)}")
        return False

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    with open('crawl_log.txt', 'a', encoding='utf-8') as f:
        f.write(log_entry)

def crawl_typecho_post(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        log(f"开始抓取: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 针对Typecho的特定选择器
        title = soup.select_one('h1.post-title, article.post h1, h1.entry-title, h1')
        title_text = title.get_text().strip() if title else "未找到标题"
        
        # 针对Typecho的内容区域
        article = soup.select_one('div.post-content, article.post, div.post-body, div.entry-content')
        
        if article:
            # 清理不需要的元素
            for element in article(['script', 'style', 'nav', 'footer', 'iframe', 'aside', 'div.post-meta']):
                element.decompose()
            
            content = clean_content(article.get_text('\n', strip=True))
        else:
            content = "未找到文章内容"
        
        # 提取发布日期
        date = soup.select_one('time.entry-date, time.post-date, .post-meta time')
        date_text = date.get('datetime') or (date.get_text().strip() if date else "未知日期")
        
        # 保存结果
        with open('output.html', 'w', encoding='utf-8') as f:
            f.write(f"<!DOCTYPE html>\n<html>\n<head>\n<title>{title_text}</title>\n</head>\n<body>\n")
            f.write(f"<h1>{title_text}</h1>\n")
            f.write(f"<p><strong>URL:</strong> <a href='{url}'>{url}</a></p>\n")
            f.write(f"<p><strong>日期:</strong> {date_text}</p>\n")
            if article:
                f.write(article.prettify())
            else:
                f.write(f"<pre>{content}</pre>")
            f.write("\n</body>\n</html>")
        
        log(f"抓取成功: {title_text}")
        return title_text, content
    
    except requests.RequestException as e:
        log(f"请求失败: {str(e)}")
        return f"请求错误: {str(e)}", ""
    except Exception as e:
        log(f"处理失败: {str(e)}")
        return f"处理错误: {str(e)}", ""

if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv('TARGET_URL', 'https://www.207725.xyz')
    
    # 确保处理您提供的示例URL格式
    if not target_url.startswith('https://www.207725.xyz'):
        target_url = f"https://www.207725.xyz{target_url}" if target_url.startswith('/') else f"https://www.207725.xyz/{target_url}"
    
    log(f"目标URL: {target_url}")
    title, content = crawl_typecho_post(target_url)
    
    if title and content:
        success = send_telegram_notification(title, content, target_url)
        log(f"处理完成{'且通知成功' if success else '但通知失败'}")
    else:
        log("抓取失败，未发送通知")
