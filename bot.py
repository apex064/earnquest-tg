#!/usr/bin/env python
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext
from telegram.ext import filters  # Updated import
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
        self.updater = None
        
        # Log the API URL for debugging
        logger.info(f"🔧 API Base URL: {self.api_base_url}")
        
        if self.token:
            logger.info(f"✅ Bot token loaded")
        else:
            logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set!")

    def debug_api_response(self, response, endpoint_name):
        """Debug function to print API response details"""
        logger.info(f"🔍 DEBUG API Response for {endpoint_name}:")
        logger.info(f"   Status Code: {response.status_code}")
        logger.info(f"   URL: {response.url}")
        
        try:
            response_data = response.json()
            logger.info(f"   Response JSON: {response_data}")
        except Exception as e:
            logger.info(f"   Response Text: {response.text}")
            logger.info(f"   JSON Parse Error: {e}")

    def start(self, update: Update, context: CallbackContext):
        """Send welcome message when the command /start is issued."""
        user_id = update.effective_user.id
        
        welcome_text = f"""
🤖 Welcome to EarnQuest Bot!

Earn money by completing tasks, surveys, and offers directly through Telegram!

Available Commands:
/login - Login to your account
/register - Create a new account
/balance - Check your balance
/tasks - View available tasks
/withdraw - Request withdrawal
/referral - Get referral info
/leaderboard - View top earners
/offerwalls - Complete surveys and offers
/achievements - View your achievements
/stats - View your earning statistics
/support - Get help and support
/help - Show this help message

📱 Visit our website for full features:
{self.website_url}

Start by logging in with /login or register with /register!
        """
        
        update.message.reply_text(welcome_text)

    def login_command(self, update: Update, context: CallbackContext):
        """Start login process."""
        update.message.reply_text("🔐 Please enter your email address to login:")
        context.user_data['awaiting_email'] = True

    def register_command(self, update: Update, context: CallbackContext):
        """Start registration process."""
        keyboard = [
            [InlineKeyboardButton("Register with Email", callback_data="register_email")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("📝 Let's create your EarnQuest account!", reply_markup=reply_markup)

    def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages for login/registration."""
        user_id = update.effective_user.id
        text = update.message.text
        
        if context.user_data.get('awaiting_email'):
            context.user_data['email'] = text
            context.user_data['awaiting_email'] = False
            context.user_data['awaiting_password'] = True
            update.message.reply_text("🔐 Now please enter your password:")
            
        elif context.user_data.get('awaiting_password'):
            email = context.user_data['email']
            password = text
            context.user_data.clear()
            self.perform_login(update, email, password)
            
        elif context.user_data.get('register_awaiting_username'):
            context.user_data['reg_username'] = text
            context.user_data['register_awaiting_username'] = False
            context.user_data['register_awaiting_email'] = True
            update.message.reply_text("📧 Please enter your email address:")
            
        elif context.user_data.get('register_awaiting_email'):
            context.user_data['reg_email'] = text
            context.user_data['register_awaiting_email'] = False
            context.user_data['register_awaiting_password'] = True
            update.message.reply_text("🔐 Please create a password:")
            
        elif context.user_data.get('register_awaiting_password'):
            context.user_data['reg_password'] = text
            context.user_data['register_awaiting_password'] = False
            self.complete_registration(update, context)

    def perform_login(self, update: Update, email: str, password: str):
        """Perform API login."""
        try:
            logger.info(f"🔐 Attempting login for email: {email}")
            
            response = requests.post(
                f"{self.api_base_url}/auth/login/",
                json={'email': email, 'password': password},
                timeout=10
            )
            
            self.debug_api_response(response, "Login")
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('token')
                user_id = update.effective_user.id
                
                self.user_sessions[user_id] = {
                    'token': token,
                    'user_data': {
                        'user_id': data.get('user_id'),
                        'username': data.get('username')
                    }
                }
                
                update.message.reply_text(
                    f"✅ Login successful! Welcome back, {data.get('username', 'User')}!\n\n"
                    f"Use /balance to check your earnings or visit our website for full features:\n"
                    f"{self.website_url}"
                )
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'Login failed')
                except:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                
                update.message.reply_text(f"❌ Login failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            update.message.reply_text("❌ Connection error. Please try again later.")

    def complete_registration(self, update: Update, context: CallbackContext):
        """Complete user registration."""
        try:
            user_data = context.user_data
            payload = {
                'username': user_data['reg_username'],
                'email': user_data['reg_email'],
                'password': user_data['reg_password'],
                'confirm_password': user_data['reg_password'],
                'agree_to_terms': True
            }
            
            response = requests.post(
                f"{self.api_base_url}/auth/register/",
                json=payload,
                timeout=10
            )
            
            self.debug_api_response(response, "Registration")
            
            if response.status_code == 201:
                data = response.json()
                update.message.reply_text(
                    f"🎉 Registration successful! Welcome to EarnQuest, {data.get('username')}!\n\n"
                    f"Your account has been created with a $0.10 welcome bonus!\n\n"
                    f"📱 Visit our website to start earning:\n"
                    f"{self.website_url}\n\n"
                    f"Use /login to access your account through Telegram."
                )
            else:
                try:
                    errors = response.json().get('errors', {})
                    error_msg = "\n".join([f"• {error}" for error in errors.values()])
                except:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    
                update.message.reply_text(f"❌ Registration failed:\n{error_msg}")
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            update.message.reply_text("❌ Registration failed. Please try again.")
        
        context.user_data.clear()

    def button_handler(self, update: Update, context: CallbackContext):
        """Handle button callbacks."""
        query = update.callback_query
        query.answer()
        
        data = query.data
        
        if data == "register_email":
            context.user_data['register_awaiting_username'] = True
            query.edit_message_text("👤 Please choose a username:")
            
        elif data == "cancel":
            context.user_data.clear()
            query.edit_message_text("❌ Operation cancelled.")

    def balance_command(self, update: Update, context: CallbackContext):
        """Check user balance."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            response = requests.get(f"{self.api_base_url}/dashboard/stats/", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                balance = data.get('balance', 0)
                total_earned = data.get('total_earned', 0)
                
                message = (
                    f"💰 Your Balance\n\n"
                    f"Current Balance: ${balance:.2f}\n"
                    f"Total Earned: ${total_earned:.2f}\n"
                    f"Streak: {data.get('streak_days', 0)} days\n"
                    f"Level: {data.get('level', 1)}\n\n"
                    f"📱 Visit our website for withdrawals and full features:\n"
                    f"{self.website_url}"
                )
                update.message.reply_text(message)
            else:
                update.message.reply_text("❌ Failed to fetch balance. Please try again.")
                
        except Exception as e:
            logger.error(f"Balance error: {e}")
            update.message.reply_text("❌ Connection error. Please try again later.")

    def tasks_command(self, update: Update, context: CallbackContext):
        """Show available tasks with website redirect."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        update.message.reply_text(
            f"📝 Available Tasks\n\n"
            f"To view and start tasks, please visit our website:\n"
            f"{self.website_url}\n\n"
            f"The web platform provides:\n"
            f"• Complete task browsing with images\n"
            f"• Easy task submission\n"
            f"• Progress tracking\n"
            f"• Instant rewards\n"
            f"• Better user experience\n\n"
            f"💡 You can complete tasks directly on the website for faster earnings!"
        )

    def withdraw_command(self, update: Update, context: CallbackContext):
        """Show withdrawal options with website redirect."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        update.message.reply_text(
            f"💰 Withdrawal Options\n\n"
            f"To manage withdrawals, please visit our website:\n"
            f"{self.website_url}\n\n"
            f"On the website you can:\n"
            f"• View all available withdrawal methods\n"
            f"• Check minimum amounts and processing times\n"
            f"• Submit withdrawal requests securely\n"
            f"• Track your withdrawal status\n"
            f"• View transaction history\n\n"
            f"💡 All financial operations are processed through our secure web platform for your safety."
        )

    def referral_command(self, update: Update, context: CallbackContext):
        """Show referral information."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            response = requests.get(f"{self.api_base_url}/my-referral-info/", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                referral_code = data.get('referral_code', 'N/A')
                referral_url = data.get('referral_url', 'N/A')
                total_referrals = data.get('total_referrals', 0)
                referral_earnings = data.get('referral_earnings', 0)
                
                message = (
                    f"👥 Referral Program\n\n"
                    f"Your Referral Code: <code>{referral_code}</code>\n"
                    f"Total Referrals: {total_referrals}\n"
                    f"Referral Earnings: ${referral_earnings:.2f}\n\n"
                    f"Share your referral link:\n{referral_url}\n\n"
                    f"Earn 10% commission on all your referrals' earnings!\n\n"
                    f"📱 Visit our website for more referral tools:\n"
                    f"{self.website_url}"
                )
                update.message.reply_text(message, parse_mode='HTML')
            else:
                update.message.reply_text("❌ Failed to fetch referral info.")
                
        except Exception as e:
            logger.error(f"Referral error: {e}")
            update.message.reply_text("❌ Connection error. Please try again.")

    def leaderboard_command(self, update: Update, context: CallbackContext):
        """Show leaderboard."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            response = requests.get(f"{self.api_base_url}/leaderboard/top-earners/", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                top_earners = data.get('top_earners', [])
                
                message = "🏆 Top Earners Leaderboard\n\n"
                for i, earner in enumerate(top_earners[:10], 1):
                    username = earner.get('username', 'Anonymous')
                    earnings = earner.get('earnings', 0)
                    message += f"{i}. {username} - ${earnings:.2f}\n"
                
                message += f"\n📱 Visit our website for full leaderboard:\n{self.website_url}"
                update.message.reply_text(message)
            else:
                update.message.reply_text("❌ Failed to fetch leaderboard.")
                
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            update.message.reply_text("❌ Connection error. Please try again.")

    def offerwalls_command(self, update: Update, context: CallbackContext):
        """Show available offerwalls."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        keyboard = [
            [InlineKeyboardButton("TimeWall", callback_data="offerwall_timewall")],
            [InlineKeyboardButton("BitLabs", callback_data="offerwall_bitlabs")],
            [InlineKeyboardButton("PubScale", callback_data="offerwall_pubscale")],
            [InlineKeyboardButton("RevToo", callback_data="offerwall_revtoo")],
            [InlineKeyboardButton("CPX Research", callback_data="offerwall_cpx")],
            [InlineKeyboardButton("KiwiWall", callback_data="offerwall_kiwiwall")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "🎯 Available Offerwalls\n\n"
            "Complete surveys and offers to earn money!\n"
            "Choose an offerwall to get started:",
            reply_markup=reply_markup
        )

    def achievements_command(self, update: Update, context: CallbackContext):
        """Show user's achievements."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            response = requests.get(f"{self.api_base_url}/user-achievements/", headers=headers, timeout=10)
            
            if response.status_code == 200:
                achievements = response.json()
                
                if not achievements:
                    update.message.reply_text(
                        "🏆 You haven't unlocked any achievements yet. Complete tasks to earn achievements!\n\n"
                        f"📱 Visit our website to start earning:\n{self.website_url}"
                    )
                    return
                
                message = "🏆 Your Achievements\n\n"
                for achievement in achievements[:10]:
                    title = achievement.get('achievement_title', 'Unknown')
                    description = achievement.get('achievement_description', '')
                    message += f"• {title}\n  {description}\n\n"
                
                message += f"📱 View all achievements on our website:\n{self.website_url}"
                update.message.reply_text(message)
            else:
                update.message.reply_text("❌ Failed to fetch achievements. Please try again.")
                
        except Exception as e:
            logger.error(f"Achievements error: {e}")
            update.message.reply_text("❌ Connection error. Please try again.")

    def support_command(self, update: Update, context: CallbackContext):
        """Show support information."""
        support_text = f"""
🆘 Support & Help

If you need assistance, here's how you can get help:

1. **Common Issues:**
   - Forgot password? Use /login to reset
   - Withdrawal issues? Visit our website
   - Task not approved? Contact support

2. **Contact Support:**
   - Email: support@earnquest.com
   - Website: {self.website_url}
   - Response time: 24-48 hours

3. **Before Contacting:**
   - Check /help for common solutions
   - Ensure you're logged in with /login
   - Check your balance with /balance

We're here to help you earn more! 💰
        """
        update.message.reply_text(support_text)

    def stats_command(self, update: Update, context: CallbackContext):
        """Show user statistics."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            response = requests.get(f"{self.api_base_url}/dashboard/stats/", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                message = (
                    f"📊 Your Statistics\n\n"
                    f"💰 Current Balance: ${data.get('balance', 0):.2f}\n"
                    f"💰 Total Earned: ${data.get('total_earned', 0):.2f}\n"
                    f"📈 Today's Earnings: ${data.get('today_earnings', 0):.2f}\n"
                    f"✅ Tasks Completed: {data.get('total_tasks', 0)}\n"
                    f"🔥 Streak Days: {data.get('streak_days', 0)}\n"
                    f"🎯 Level: {data.get('level', 1)}\n"
                    f"👥 Referrals: {data.get('referral_stats', {}).get('total_referrals', 0)}\n"
                    f"💰 Referral Earnings: ${data.get('referral_stats', {}).get('earnings', 0):.2f}\n\n"
                    f"📱 Visit our website for detailed analytics:\n{self.website_url}"
                )
                update.message.reply_text(message)
            else:
                update.message.reply_text("❌ Failed to fetch statistics. Please try again.")
                
        except Exception as e:
            logger.error(f"Stats error: {e}")
            update.message.reply_text("❌ Connection error. Please try again.")

    def help_command(self, update: Update, context: CallbackContext):
        """Show help message."""
        help_text = f"""
🤖 EarnQuest Bot Help

Available Commands:
/login - Login to your account
/register - Create a new account
/balance - Check your balance and stats
/tasks - View available tasks (Website)
/withdraw - Request withdrawal (Website)
/referral - Get referral code and stats
/leaderboard - View top earners
/offerwalls - Complete surveys and offers
/achievements - View your achievements
/stats - View your earning statistics
/support - Get help and support
/help - Show this help message

📱 Full features available on our website:
{self.website_url}

Need assistance? Use /support to contact our team.

Happy earning! 💰
        """
        update.message.reply_text(help_text)

    def error_handler(self, update: Update, context: CallbackContext):
        """Handle errors in the telegram bot."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_user:
                context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="❌ An error occurred. Please try again later or visit our website."
                )
        except Exception as e:
            logger.error(f"Error in error handler: {e}")

    def setup_handlers(self):
        """Setup bot handlers."""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured")
            return False
            
        try:
            # Updated to use the new Application class for newer versions
            from telegram.ext import Application
            self.application = Application.builder().token(self.token).build()
            dispatcher = self.application
            
            # Add command handlers
            dispatcher.add_handler(CommandHandler("start", self.start))
            dispatcher.add_handler(CommandHandler("login", self.login_command))
            dispatcher.add_handler(CommandHandler("register", self.register_command))
            dispatcher.add_handler(CommandHandler("balance", self.balance_command))
            dispatcher.add_handler(CommandHandler("tasks", self.tasks_command))
            dispatcher.add_handler(CommandHandler("withdraw", self.withdraw_command))
            dispatcher.add_handler(CommandHandler("referral", self.referral_command))
            dispatcher.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
            dispatcher.add_handler(CommandHandler("offerwalls", self.offerwalls_command))
            dispatcher.add_handler(CommandHandler("achievements", self.achievements_command))
            dispatcher.add_handler(CommandHandler("support", self.support_command))
            dispatcher.add_handler(CommandHandler("stats", self.stats_command))
            dispatcher.add_handler(CommandHandler("help", self.help_command))
            
            # Add callback query handler
            dispatcher.add_handler(CallbackQueryHandler(self.button_handler))
            
            # Add message handler for login/registration - updated filters usage
            dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Add error handler
            dispatcher.add_error_handler(self.error_handler)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Telegram bot handlers: {e}")
            return False

    def run(self):
        """Run the bot."""
        if not self.setup_handlers():
            return
        
        logger.info("🤖 Starting Telegram Bot...")
        
        # Start the bot
        self.application.run_polling()

# Create and run bot instance
if __name__ == "__main__":
    bot = EarnQuestBot()
    bot.run()