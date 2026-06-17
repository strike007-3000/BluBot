import asyncio
import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from src.utils import SafeLogger

async def run_telegram_test():
    load_dotenv()
    
    print("=" * 60)
    print("      BluBot: Telegram Gateway Setup & Test Tool")
    print("=" * 60)
    
    # Try reading from env, otherwise prompt
    env_token = os.getenv("TELEGRAM_BOT_TOKEN")
    env_uid = os.getenv("TELEGRAM_USER_ID")
    
    if env_token:
        print(f"Loaded Bot Token from environment: {env_token[:10]}...{env_token[-5:]}")
        use_env_token = input("Use this token? (Y/n): ").strip().lower() != 'n'
        token = env_token if use_env_token else input("Enter Telegram Bot Token: ").strip()
    else:
        token = input("Enter Telegram Bot Token: ").strip()
        
    if env_uid:
        print(f"Loaded User ID from environment: {env_uid}")
        use_env_uid = input("Use this user ID? (Y/n): ").strip().lower() != 'n'
        uid = env_uid if use_env_uid else input("Enter Telegram User ID: ").strip()
    else:
        uid = input("Enter Telegram User ID: ").strip()

    if not token or not uid:
        print("❌ Error: Both Bot Token and User ID are required to run the test.")
        return

    print("\n[1/3] Initializing Telegram bot client...")
    try:
        bot = Bot(token=token)
        bot_info = await bot.get_me()
        print(f"✅ Connected to bot: @{bot_info.username} ({bot_info.first_name})")
    except Exception as e:
        print(f"❌ Failed to connect to Telegram bot: {e}")
        print("Please check your Bot Token and try again.")
        return

    print("\n[2/3] Sending test approval message to your Telegram chat...")
    try:
        keyboard = [
            [
                InlineKeyboardButton("✅ Test Approve", callback_data="test_approve"),
                InlineKeyboardButton("❌ Test Reject", callback_data="test_reject")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        sent_message = await bot.send_message(
            chat_id=uid,
            text="🔔 *BluBot setup check!*\n\nClick one of the buttons below to confirm approval queue communication.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        print("✅ Message sent! Check your Telegram chat with the bot.")
    except Exception as e:
        print(f"❌ Failed to send message to User ID {uid}: {e}")
        print("Hint: Make sure you have searched for the bot and clicked 'Start' or sent a message to it first!")
        return

    print("\n[3/3] Waiting up to 60 seconds for your button click...")
    
    # Clean old updates
    updates = await bot.get_updates(limit=100)
    offset = updates[-1].update_id + 1 if updates else None
    
    elapsed = 0
    poll_interval = 1
    timeout = 60
    
    while elapsed < timeout:
        try:
            updates = await bot.get_updates(offset=offset, timeout=1)
            for update in updates:
                offset = update.update_id + 1
                if update.callback_query:
                    query = update.callback_query
                    
                    if str(query.from_user.id) != str(uid):
                        print(f"⚠️ Ignored click from unauthorized user ID: {query.from_user.id}")
                        continue
                        
                    if query.message and query.message.message_id == sent_message.message_id:
                        action = query.data
                        if action == "test_approve":
                            print("\n🎉 SUCCESS! Received 'Approve' click!")
                            await query.answer("Setup checked!")
                            await bot.send_message(chat_id=uid, text="🎉 Configuration verified successfully! Ready to curate.")
                            return
                        elif action == "test_reject":
                            print("\n🎉 SUCCESS! Received 'Reject' click!")
                            await query.answer("Setup checked!")
                            await bot.send_message(chat_id=uid, text="🛑 Configuration verified! (Rejected choice registered successfully).")
                            return
        except Exception as e:
            pass
            
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        
    print("\n⏰ Timeout: No button interaction was detected within 60 seconds.")
    print("Please check that the bot is running, you've started a chat with it, and click one of the buttons.")

if __name__ == "__main__":
    try:
        asyncio.run(run_telegram_test())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
