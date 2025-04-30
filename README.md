# Typecho-play 用于模拟浏览器刷取流量

## 使用介绍

1. 更改主目录 blog_visitor_pro.py 中'blog_url': 'https://www.207725.xyz' 的url为自己的Typecho博客

2.  posts.txt 内容为必刷项，自行添加，格式为 https://www.207725.xyz/index.php/archives/4/
 
3.  'req_per_url' 为必刷项的默认单条文章刷取次数，根据自己需求更改

4.  'default_urls': [
        '/index.php/archives/13/',
        '/index.php/archives/5/'
    ] 为自己博客中文章的url 

5. .github/workflows/blog_visitor.yml 中cron为定时任务，默认 */5 * * * *'  # 5分钟运行，根据自己喜好更改

6. normal_visits 为手动普通模拟次数，default 按总抓取文章自动分配的总浏览量，默认200

7. required_visits 为手动必刷url次数，default，按每个url均分，默认200

# Telegram_bot推送配置指南

## 目录
1. [创建 Telegram Bot](#1-创建-telegram-bot)
2. [获取 Chat ID](#2-获取-chat-id)
3. [GitHub 仓库配置](#3-github-仓库配置)
4. [测试通知功能](#4-测试通知功能)

---

# 1. 创建 Telegram Bot

## 步骤说明
1. 打开 Telegram 搜索 `@BotFather`
2. 发送命令 `/newbot`
3. 按提示操作：
   - 输入你的机器人名称 (如: `MyBlogViewBot`)
   - 输入机器人唯一用户名 (必须以 `bot` 结尾，如: `my_blog_view_bot`)
4. 创建成功后，你会获得一个 **API Token**，格式如下：
   ```
   1234567890:ABCdefGHIJKlmNoPQRsTUVwxyZ-123456789
   ```

## 注意事项
- 机器人名称可以随时修改
- 用户名必须唯一且以 `bot` 结尾
- **API Token 是敏感信息，不要泄露**

---

# 2. 获取 Chat ID

## 个人聊天 ID
1. 搜索 `@GetChatID_IL_BOT`
2. 发送用户名信息给它
3. 它会回复你的 `Chat ID`

## 群组聊天 ID
1. 创建新群组并添加 `@RawDataBot`
2. 该机器人会自动发送群组信息，找到：
   ```json
   "chat": {
     "id": -1001234567890,
     "title": "My Group"
   }
   ```
   - 以 `-100` 开头的数字就是群组 Chat ID

## 重要提示
- 个人聊天 ID 是正数
- 群组聊天 ID 是负数 (以 `-100` 开头)
- 确保机器人已加入目标群组

---

# 3. GitHub 仓库配置

## 添加 Secrets
1. 进入 GitHub 仓库 → Settings → Secrets → Actions → New repository secret
2. 添加两个 secret：

   | Secret 名称       | 值                     | 示例                |
   |-------------------|------------------------|---------------------|
   | `TELEGRAM_BOT_TOKEN`    | 从 @BotFather 获取的 Token | `123456:ABC-def123` |
   | `TELEGRAM_CHAT_ID`      | 个人或群组 Chat ID       | `987654321` 或 `-1001234567890` |

# 4.测试通知

## 手动触发测试
1. 在 GitHub 仓库页面：
   - 进入 Actions → Typecho Pro Visitor → Run workflow
2. 等待运行完成后，检查 Telegram 是否收到如下通知：
   ```
   📊 Typecho访问报告

   ⏱️ 总耗时: 57.3秒

   🌐 博客地址: https://www.207725.xyz

   ...
   ```
