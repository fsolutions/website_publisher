# Telegram to WordPress Publisher

This script monitors a Telegram channel and automatically publishes new posts to a WordPress website.

## Features

- Checks your Telegram channel for new posts
- Extracts text and media content from posts
- Automatically formats content for WordPress
- Publishes posts to WordPress using the REST API
- Keeps track of processed messages to avoid duplicates
- Runs via cron job

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a Telegram Bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Create a new bot using `/newbot`
   - Copy the bot token

3. Set up WordPress:
   - Go to your WordPress admin panel
   - Navigate to Users → Application Passwords
   - Create a new application password
   - Copy the username and application password

4. Configure the environment:
   - Copy `.env.example` to `.env`
   - Fill in your credentials:
     - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
     - `TELEGRAM_CHANNEL_USERNAME`: Your channel username (without @)
     - `WP_URL`: Your WordPress site URL
     - `WP_USERNAME`: Your WordPress username
     - `WP_PASSWORD`: Your WordPress application password

5. Add the bot to your channel:
   - Make the bot an administrator of your channel
   - Ensure the bot has permission to read messages

## Running with Cron

The script is designed to run once and exit, making it perfect for scheduling with cron.

### Setting up a Cron Job

1. Open your crontab:
```bash
crontab -e
```

2. Add a line to run the script at your desired interval. For example, to run every 10 minutes:
```
*/10 * * * * cd /path/to/your/script/directory && /path/to/python /path/to/your/script/directory/telegram_wordpress_publisher.py >> /path/to/your/script/directory/cron.log 2>&1
```

3. Save and exit. The cron job will now run automatically at the specified interval.

### Common Cron Intervals

- Every 5 minutes: `*/5 * * * *`
- Every 10 minutes: `*/10 * * * *`
- Every 30 minutes: `*/30 * * * *`
- Every hour: `0 * * * *`
- Every 2 hours: `0 */2 * * *`
- Every day at midnight: `0 0 * * *`

## Manual Usage

If you prefer to run the script manually:
```bash
python telegram_wordpress_publisher.py
```

The script will:
1. Check your Telegram channel for new posts
2. When a new post is detected, it will:
   - Extract the text and any media
   - Format the content for WordPress
   - Create a new post on your WordPress site
   - Save the message ID to avoid duplicate posts

## Notes

- The script uses the first bold text as the WordPress post title
- Images are automatically embedded in the WordPress post
- The script keeps track of the last processed message to avoid duplicates
- Logs are written to both console and `telegram_bot.log` file
- All errors are logged for debugging 