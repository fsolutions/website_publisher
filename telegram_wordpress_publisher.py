import os
import json
import requests
import logging
import sys
import base64
import re
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_USERNAME = os.getenv('TELEGRAM_CHANNEL_USERNAME')
WP_URL = os.getenv('WP_URL')
WP_USERNAME = os.getenv('WP_USERNAME')
WP_PASSWORD = os.getenv('WP_PASSWORD')
WP_CATEGORY_ID = 10  # Category ID for "iz-zhizni"

# File to store the last processed message ID
LAST_MESSAGE_FILE = 'last_message_id.json'

def load_last_message_id():
    try:
        with open(LAST_MESSAGE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_message_id')
    except FileNotFoundError:
        return None

def save_last_message_id(message_id):
    with open(LAST_MESSAGE_FILE, 'w') as f:
        json.dump({'last_message_id': message_id}, f)

def extract_hashtags(text):
    """Extract hashtags from text."""
    hashtags = re.findall(r'#(\w+)', text)
    return hashtags

def escape_html_tags(text):
    """Escape HTML tags in text content to prevent them from being interpreted as actual HTML."""
    # Replace < with &lt; and > with &gt; for all HTML tags
    return re.sub(r'<([^>]+)>', r'&lt;\1&gt;', text)

def format_post_for_wordpress(text, entities=None):
    """Format the Telegram post for WordPress."""
    # Log the original post content
    logger.info(f"Original post content:\n{text}")
    
    # Extract hashtags first
    hashtags = extract_hashtags(text)
    logger.info(f"Extracted hashtags: {hashtags}")
    
    # Remove hashtags from the content
    for hashtag in hashtags:
        text = text.replace(f"#{hashtag}", "")
    
    # Escape HTML tags in the text content
    text = escape_html_tags(text)
    
    # Process entities if available
    if entities:
        logger.info(f"Processing {len(entities)} formatting entities")
        formatted_text = process_telegram_entities(text, entities)
        logger.info(f"Text after entity processing: {formatted_text[:100]}...")
    else:
        # Convert Telegram formatting to HTML
        # Bold: **text** or <b>text</b>
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'<b>(.*?)</b>', r'<strong>\1</strong>', text)
        
        # Italic: *text* or <i>text</i>
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'<i>(.*?)</i>', r'<em>\1</em>', text)
        
        # Underline: __text__ or <u>text</u>
        text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
        text = re.sub(r'<u>(.*?)</u>', r'<u>\1</u>', text)
        
        # Strikethrough: ~~text~~ or <s>text</s>
        text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)
        text = re.sub(r'<s>(.*?)</s>', r'<s>\1</s>', text)
        
        # Code: `text` or <code>text</code>
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        text = re.sub(r'<code>(.*?)</code>', r'<code>\1</code>', text)
        
        # Preformatted text: ```text``` or <pre>text</pre>
        text = re.sub(r'```(.*?)```', r'<pre class="wp-block-code"><code>\1</code></pre>', text, flags=re.DOTALL)
        text = re.sub(r'<pre>(.*?)</pre>', r'<pre class="wp-block-code"><code>\1</code></pre>', text, flags=re.DOTALL)
        
        formatted_text = text
    
    # Now extract the title from the formatted text
    title = ""
    
    # Look for the first <strong> tag in the formatted text
    strong_match = re.search(r'<strong>(.*?)</strong>', formatted_text)
    if strong_match:
        title = strong_match.group(1).strip()
        # Remove the title from the content
        formatted_text = formatted_text.replace(f"<strong>{title}</strong>", "", 1).strip()
    else:
        # If no bold title found, use the first line
        first_line = formatted_text.split('\n')[0]
        # Clean HTML tags from the first line
        clean_first_line = re.sub(r'<[^>]+>', '', first_line)
        title = clean_first_line[:100]  # First 100 characters of first line
        # Remove the first line from the content
        formatted_text = formatted_text.replace(first_line, "", 1).strip()
    
    # Clean the title - remove any HTML tags
    title = re.sub(r'<[^>]+>', '', title)
    
    # Make sure the title is completely removed from the content
    # This is a safety check to ensure the title doesn't appear in the final HTML
    if title in formatted_text:
        logger.info(f"Title still found in content, removing it: {title}")
        formatted_text = formatted_text.replace(title, "", 1).strip()
    
    # Remove empty <strong> tags
    formatted_text = re.sub(r'<strong>\s*</strong>', '', formatted_text)
    
    # Split text into paragraphs
    paragraphs = formatted_text.split('\n\n')
    
    # Process each paragraph
    formatted_paragraphs = []
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        
        # Handle blockquotes
        if re.search(r'^>', paragraph, re.MULTILINE):
            # This is a blockquote
            quote_lines = []
            for line in paragraph.split('\n'):
                if line.startswith('>'):
                    quote_lines.append(line[1:].strip())
                else:
                    quote_lines.append(line.strip())
            
            quote_text = '\n'.join(quote_lines)
            formatted_paragraphs.append(f'<blockquote class="wp-block-quote"><p>{quote_text}</p></blockquote>')
            continue
        
        # Handle lists
        if re.search(r'^[-*]\s', paragraph, re.MULTILINE):
            # This is a list
            list_items = []
            for line in paragraph.split('\n'):
                if line.startswith('-') or line.startswith('*'):
                    list_items.append(line[2:].strip())
            
            list_html = '\n'.join([f'<li>{item}</li>' for item in list_items])
            formatted_paragraphs.append(f'<ul>{list_html}</ul>')
            continue
        
        # Handle numbered lists
        if re.search(r'^\d+\.\s', paragraph, re.MULTILINE):
            # This is a numbered list
            list_items = []
            for line in paragraph.split('\n'):
                if re.match(r'^\d+\.\s', line):
                    list_items.append(re.sub(r'^\d+\.\s', '', line).strip())
            
            list_html = '\n'.join([f'<li>{item}</li>' for item in list_items])
            formatted_paragraphs.append(f'<ol>{list_html}</ol>')
            continue
        
        # Add the formatted paragraph
        formatted_paragraphs.append(f'<p>{paragraph}</p>')
    
    # Join all paragraphs
    content = '\n\n'.join(formatted_paragraphs)
    
    # Final check to ensure title is not in the content
    if title in content:
        logger.warning(f"Title still found in final content, removing it: {title}")
        content = content.replace(title, "", 1).strip()
    
    # Log the final formatted content
    logger.info(f"Final formatted content:\n{content}")
    
    return title, content, hashtags

def process_telegram_entities(text, entities):
    """Process Telegram message entities to restore formatting."""
    if not entities:
        return text
    
    # Sort entities by offset in reverse order to avoid index shifting
    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)
    
    # Create a list of characters for easier manipulation
    chars = list(text)
    
    # Process each entity
    for entity in sorted_entities:
        start = entity.offset
        end = start + entity.length
        
        # Make sure we don't go out of bounds
        if start >= len(chars) or end > len(chars):
            logger.warning(f"Entity out of bounds: start={start}, end={end}, text length={len(chars)}")
            continue
        
        # Get the text for this entity
        entity_text = ''.join(chars[start:end])
        
        # Apply formatting based on entity type
        if entity.type == 'bold':
            formatted_text = f'<strong>{entity_text}</strong>'
        elif entity.type == 'italic':
            formatted_text = f'<em>{entity_text}</em>'
        elif entity.type == 'underline':
            formatted_text = f'<u>{entity_text}</u>'
        elif entity.type == 'strikethrough':
            formatted_text = f'<s>{entity_text}</s>'
        elif entity.type == 'code':
            formatted_text = f'<code>{entity_text}</code>'
        elif entity.type == 'pre':
            # For pre-formatted text blocks
            if hasattr(entity, 'language') and entity.language:
                formatted_text = f'<pre class="wp-block-code"><code class="language-{entity.language}">{entity_text}</code></pre>'
            else:
                formatted_text = f'<pre class="wp-block-code"><code>{entity_text}</code></pre>'
        else:
            # Skip unknown entity types
            continue
        
        # Replace the original text with the formatted text
        chars[start:end] = list(formatted_text)
    
    # Join the characters back into a string
    return ''.join(chars)

def get_or_create_tag(tag_name):
    """Get or create a tag and return its ID."""
    # Remove any special characters from tag name
    clean_tag = re.sub(r'[^\w\s-]', '', tag_name).strip()
    
    # First, try to find the tag
    endpoint = f'{WP_URL}/wp-json/wp/v2/tags'
    params = {'search': clean_tag}
    
    # Remove any quotes from the password if present
    clean_password = WP_PASSWORD.strip("'").strip('"')
    
    # Create the Basic Auth header
    auth_string = f"{WP_USERNAME}:{clean_password}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}'
    }
    
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        
        if response.status_code == 200:
            tags = response.json()
            
            # Check if we found an exact match
            for tag in tags:
                if tag['name'].lower() == clean_tag.lower():
                    logger.info(f"Found existing tag: {clean_tag} (ID: {tag['id']})")
                    return tag['id']
        
        # If we didn't find the tag, create it
        create_data = {
            'name': clean_tag
        }
        
        create_response = requests.post(endpoint, headers=headers, json=create_data)
        
        if create_response.status_code == 201:
            new_tag = create_response.json()
            logger.info(f"Created new tag: {clean_tag} (ID: {new_tag['id']})")
            return new_tag['id']
        else:
            logger.error(f"Failed to create tag: {clean_tag}")
            logger.error(f"Response: {create_response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting/creating tag: {e}")
        return None

def publish_to_wordpress(title, content, hashtags=None):
    """Publish the post to WordPress using REST API."""
    endpoint = f'{WP_URL}/wp-json/wp/v2/posts'
    
    # Remove any quotes from the password if present
    clean_password = WP_PASSWORD.strip("'").strip('"')
    
    # Create the Basic Auth header
    auth_string = f"{WP_USERNAME}:{clean_password}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth_b64}'
    }
    
    # Clean up the content to ensure proper formatting
    # Replace any double newlines with single newlines to avoid extra spacing
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Prepare the data
    data = {
        'title': title,
        'content': content,
        'status': 'publish',
        'format': 'standard',  # Use standard post format
        'categories': [WP_CATEGORY_ID]  # Add category
    }
    
    # Add tags if present
    if hashtags:
        # First, get or create tags
        tag_ids = []
        for tag in hashtags:
            tag_id = get_or_create_tag(tag)
            if tag_id:
                tag_ids.append(tag_id)
        
        if tag_ids:
            data['tags'] = tag_ids
    
    logger.info(f"Publishing to WordPress: {endpoint}")
    logger.info(f"Title: {title}")
    logger.info(f"Category: {WP_CATEGORY_ID}")
    if hashtags:
        logger.info(f"Tags: {hashtags}")
    
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        
        if response.status_code == 201:
            logger.info(f"Successfully published post: {title}")
            return True
        else:
            logger.error(f"Failed to publish post. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error publishing to WordPress: {e}")
        return False

def check_channel_for_new_posts():
    """Check the channel for new posts."""
    try:
        # Create a bot instance
        logger.info(f"Connecting to Telegram with bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Get the channel ID
        logger.info(f"Attempting to get channel info for @{TELEGRAM_CHANNEL_USERNAME}")
        try:
            channel_info = bot.get_chat(f"@{TELEGRAM_CHANNEL_USERNAME}")
            channel_id = channel_info.id
            logger.info(f"Successfully found channel with ID: {channel_id}")
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            logger.error("Make sure the bot is added to the channel as an administrator")
            return
        
        # Get the last message ID we processed
        last_processed_id = load_last_message_id()
        logger.info(f"Last processed message ID: {last_processed_id}")
        
        # Get recent messages from the channel
        logger.info("Fetching recent messages from the channel...")
        try:
            # Use a larger offset to get more messages
            offset = -1
            if last_processed_id:
                offset = last_processed_id + 1
            
            updates = bot.get_updates(offset=offset, limit=20, timeout=60)
            logger.info(f"Retrieved {len(updates)} updates from Telegram")
        except Exception as e:
            logger.error(f"Failed to get updates: {e}")
            return
        
        # Filter for channel posts
        channel_messages = [update for update in updates if update.channel_post and update.channel_post.chat.id == channel_id]
        logger.info(f"Found {len(channel_messages)} channel posts")
        
        # Process new messages
        for update in channel_messages:
            message = update.channel_post
            
            # Skip if we've already processed this message
            if last_processed_id and message.message_id <= last_processed_id:
                logger.info(f"Skipping already processed message ID: {message.message_id}")
                continue
                
            # Save the new message ID
            save_last_message_id(message.message_id)
            logger.info(f"Processing new message ID: {message.message_id}")
            
            # Extract text and media
            text = message.text or message.caption or ""
            logger.info(f"Message text: {text[:50]}...")
            
            # Process entities if available
            entities = message.entities or message.caption_entities
            if entities:
                logger.info(f"Found {len(entities)} formatting entities")
                # Log each entity for debugging
                for i, entity in enumerate(entities):
                    logger.info(f"Entity {i+1}: type={entity.type}, offset={entity.offset}, length={entity.length}")
            
            # Get media URLs
            media_urls = []
            
            if message.photo:
                # Get the largest photo
                photo = message.photo[-1]
                logger.info(f"Found photo with file_id: {photo.file_id}")
                file = bot.get_file(photo.file_id)
                media_urls.append(file.file_path)
                logger.info(f"Photo URL: {file.file_path}")
            
            # Format and publish to WordPress
            title, content, hashtags = format_post_for_wordpress(text, entities)
            logger.info(f"Formatted title: {title}")
            publish_to_wordpress(title, content, hashtags)
            
        logger.info("Channel check completed")
        
    except Exception as e:
        logger.error(f"Error checking channel: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def main():
    """Run the channel check once and exit."""
    try:
        check_channel_for_new_posts()
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        logger.info("Script completed with errors")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1) 