#!/usr/bin/env python
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class EarnQuestBot:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.api_base_url = os.environ.get('API_BASE_URL', 'https://rebackend-ij74.onrender.com/api')
        self.website_url = "https://earnquestapp.com/"
        self.user_sessions = {}
        
        if self.token:
            logger.info(f"✅ Bot token loaded")
        else:
            logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set!")

    # ... (keep all your async methods exactly as they are in the previous version)

    def setup_handlers(self):
        """Setup bot handlers."""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured")
            return False
            
        try:
            self.application = Application.builder().token(self.token).build()
            
            # Add all your handlers here (same as before)
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("login", self.login_command))
            self.application.add_handler(CommandHandler("register", self.register_command))
            self.application.add_handler(CommandHandler("balance", self.balance_command))
            self.application.add_handler(CommandHandler("tasks", self.tasks_command))
            self.application.add_handler(CommandHandler("withdraw", self.withdraw_command))
            self.application.add_handler(CommandHandler("referral", self.referral_command))
            self.application.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
            self.application.add_handler(CommandHandler("offerwalls", self.offerwalls_command))
            self.application.add_handler(CommandHandler("achievements", self.achievements_command))
            self.application.add_handler(CommandHandler("support", self.support_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            self.application.add_error_handler(self.error_handler)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Telegram bot handlers: {e}")
            return False

    def run(self):
        """Run the bot with polling."""
        if not self.setup_handlers():
            return
        
        logger.info("🤖 Starting Telegram Bot with polling...")
        self.application.run_polling()

if __name__ == "__main__":
    bot = EarnQuestBot()
    bot.run()