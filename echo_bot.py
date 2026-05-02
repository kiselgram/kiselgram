#!/usr/bin/env python3
"""
Kiselgram Echo Bot
Simple bot that echoes back any message it receives.
"""

import requests
import time
import json
import sys
from datetime import datetime
from colorama import Fore, Back, Style, init

init()

# Configuration
API_BASE_URL = "http://localhost:5000"  # Change to your Kiselgram URL
BOT_TOKEN = None  # Will be set via command line or input


class KiselgramEchoBot:
    def __init__(self, api_url, token):
        self.api_url = api_url.rstrip('/')
        self.token = token
        self.last_message_id = 0
        self.running = True
        self.start_time = None
        self.message_count = 0

    def send_message(self, chat_id, text):
        """Send a message to a chat"""
        url = f"{self.api_url}/premium/api/bot/{self.token}/send"

        payload = {
            "chat_id": chat_id,
            "content": text
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"  ✅ Reply sent to {chat_id}")
                    return True
                else:
                    print(f"  ❌ API error: {data.get('error')}")
            else:
                print(f"  ❌ HTTP {response.status_code}: {response.text}")
        except Exception as e:
            print(f"  ❌ Error sending message: {e}")

        return False

    def get_updates(self):
        """Poll for new messages (long polling)"""
        url = f"{self.api_url}/premium/api/bot/{self.token}/updates"

        params = {
            "after_id": self.last_message_id,
            "timeout": 30
        }

        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('updates', [])
            elif response.status_code != 404:
                print(f"⚠️ HTTP {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            print(f"⚠️ Error getting updates: {e}")
            time.sleep(5)

        return []

    def process_message(self, message):
        """Process a single message"""
        msg_id = message.get('id')
        chat_id = message.get('chat_id')
        sender_id = message.get('sender_id')
        content = message.get('content', '')

        if msg_id and msg_id > self.last_message_id:
            self.last_message_id = msg_id

        if message.get('is_bot'):
            return

        print(f"\n📨 New message from {sender_id}: {content[:50]}...")

        reply = f"🔄 Echo: {content}"
        content_lower = content.lower().strip()

        if content_lower == "ping":
            reply = "🏓 Pong!"
        elif content_lower in ["hello", "hi", "hey"]:
            reply = "👋 Hello! I'm an echo bot. Send me any message and I'll echo it back!"
        elif content_lower == "time":
            reply = f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elif content_lower == "help":
            reply = """🤖 Kiselgram Echo Bot Commands:
• ping - Pong!
• time - Show current time
• help - Show this help
• status - Bot statistics
• Any other text - I'll echo it back!"""
        elif content_lower == "status":
            runtime = datetime.now() - self.start_time if self.start_time else "Unknown"
            reply = f"""📊 Bot Status:
• Running since: {self.start_time.strftime('%H:%M:%S') if self.start_time else 'Unknown'}
• Messages processed: {self.message_count}
• Last message ID: {self.last_message_id}
• Runtime: {runtime}"""

        self.send_message(chat_id, reply)
        self.message_count += 1

    def run(self):
        """Main bot loop"""
        print("🤖 Kiselgram Echo Bot starting...")
        print(f"📡 API: {self.api_url}")
        print(f"🔑 Token: {self.token[:10]}...")
        print("-" * 40)

        self.start_time = datetime.now()
        self.message_count = 0

        # Test connection
        test_url = f"{self.api_url}/premium/api/bot/{self.token}/test"
        try:
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                bot_name = data.get('bot_name', 'Unknown')
                print(f"✅ Connected! Bot name: {bot_name}")
            else:
                print(f"⚠️ Connection test failed: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"⚠️ Could not test connection: {e}")

        print("\n📨 Waiting for messages... (Ctrl+C to stop)\n")

        while self.running:
            try:
                updates = self.get_updates()

                for update in updates:
                    if 'message' in update:
                        self.process_message(update['message'])

            except KeyboardInterrupt:
                print("\n\n👋 Shutting down...")
                self.running = False
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                time.sleep(5)

        print(f"\n📊 Session summary:")
        print(f"   • Messages processed: {self.message_count}")
        runtime = datetime.now() - self.start_time if self.start_time else "Unknown"
        print(f"   • Runtime: {runtime}")
        print("👋 Goodbye!")


if __name__ == "__main__":
    # Get token from command line or input
    if len(sys.argv) > 1:
        BOT_TOKEN = sys.argv[1]
    else:
        BOT_TOKEN = input("Enter bot token: ").strip()

    if not BOT_TOKEN:
        print("❌ Bot token is required!")
        sys.exit(1)

    # Ask for API URL
    api_url = input(f"API URL [{API_BASE_URL}]: ").strip()
    if not api_url:
        api_url = API_BASE_URL

    bot = KiselgramEchoBot(api_url, BOT_TOKEN)

    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")