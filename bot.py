#!/usr/bin/env python
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Configure logging - FIXED THE TYPO: 'asctime' not 'asasctime'
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class EarnQuestBot:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
        # FORCE the correct API URL - override any environment variable
        self.api_base_url = 'https://rebackend-ij74.onrender.com/api'
        self.website_url = "https://earnquestapp.com/"
        self.user_sessions = {}
        self.application = None
        
        # Log the API URL for debugging
        logger.info(f"🔧 API Base URL SET TO: {self.api_base_url}")
        
        if self.token:
            logger.info(f"✅ Bot token loaded: {self.token[:10]}...")
        else:
            logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set!")

    def debug_api_response(self, response, endpoint_name):
        """Debug function to print API response details"""
        logger.info(f"🔍 DEBUG API Response for {endpoint_name}:")
        logger.info(f"   Status Code: {response.status_code}")
        logger.info(f"   Headers: {dict(response.headers)}")
        logger.info(f"   URL: {response.url}")
        
        try:
            response_data = response.json()
            logger.info(f"   Response JSON: {response_data}")
        except Exception as e:
            logger.info(f"   Response Text: {response.text}")
            logger.info(f"   JSON Parse Error: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        await update.message.reply_text(welcome_text)
        
        # Check if user already has a session
        if user_id in self.user_sessions:
            await update.message.reply_text("✅ You are already logged in! Use /tasks to start earning.")

    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start login process."""
        await update.message.reply_text("🔐 Please enter your email address to login:")
        context.user_data['awaiting_email'] = True

    async def register_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start registration process."""
        keyboard = [
            [InlineKeyboardButton("Register with Email", callback_data="register_email")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📝 Let's create your EarnQuest account!", reply_markup=reply_markup)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages for login/registration."""
        user_id = update.effective_user.id
        text = update.message.text
        
        if context.user_data.get('awaiting_email'):
            # User is providing email for login
            context.user_data['email'] = text
            context.user_data['awaiting_email'] = False
            context.user_data['awaiting_password'] = True
            await update.message.reply_text("🔐 Now please enter your password:")
            
        elif context.user_data.get('awaiting_password'):
            # User is providing password
            email = context.user_data['email']
            password = text
            context.user_data.clear()
            await self.perform_login(update, email, password)
            
        elif context.user_data.get('register_awaiting_username'):
            # User is providing username for registration
            context.user_data['reg_username'] = text
            context.user_data['register_awaiting_username'] = False
            context.user_data['register_awaiting_email'] = True
            await update.message.reply_text("📧 Please enter your email address:")
            
        elif context.user_data.get('register_awaiting_email'):
            # User is providing email for registration
            context.user_data['reg_email'] = text
            context.user_data['register_awaiting_email'] = False
            context.user_data['register_awaiting_password'] = True
            await update.message.reply_text("🔐 Please create a password:")
            
        elif context.user_data.get('register_awaiting_password'):
            # User is providing password for registration
            context.user_data['reg_password'] = text
            context.user_data['register_awaiting_password'] = False
            await self.complete_registration(update, context)

    async def perform_login(self, update: Update, email: str, password: str):
        """Perform API login."""
        try:
            logger.info(f"🔐 Attempting login for email: {email}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/auth/login/")
            
            # FIX: Ensure we're using the correct API URL
            login_url = f"{self.api_base_url}/auth/login/"
            logger.info(f"🔧 Full login URL: {login_url}")
            
            response = requests.post(
                login_url,
                json={'email': email, 'password': password},
                timeout=10
            )
            
            # Debug API response
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
                
                await update.message.reply_text(
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
                
                logger.error(f"Login failed with status {response.status_code}: {error_msg}")
                await update.message.reply_text(f"❌ Login failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            await update.message.reply_text("❌ Connection error. Please try again later.")

    async def complete_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            
            logger.info(f"📝 Attempting registration for username: {user_data['reg_username']}, email: {user_data['reg_email']}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/auth/register/")
            
            # FIX: Ensure we're using the correct API URL
            register_url = f"{self.api_base_url}/auth/register/"
            
            response = requests.post(
                register_url,
                json=payload,
                timeout=10
            )
            
            # Debug API response
            self.debug_api_response(response, "Registration")
            
            if response.status_code == 201:
                data = response.json()
                await update.message.reply_text(
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
                    
                logger.error(f"Registration failed with status {response.status_code}: {error_msg}")
                await update.message.reply_text(f"❌ Registration failed:\n{error_msg}")
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            await update.message.reply_text("❌ Registration failed. Please try again.")
        
        context.user_data.clear()

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "register_email":
            context.user_data['register_awaiting_username'] = True
            await query.edit_message_text("👤 Please choose a username:")
            
        elif data == "cancel":
            context.user_data.clear()
            await query.edit_message_text("❌ Operation cancelled.")
            
        elif data.startswith("withdraw_"):
            await self.handle_withdrawal_method(query, data)
            
        elif data.startswith("task_"):
            await self.handle_task_action(query, data)
            
        elif data.startswith("offerwall_"):
            await self.handle_offerwall_action(query, data)
            
        elif data.startswith("withdraw_method_"):
            await self.handle_withdraw_method_selection(query, data)

    async def handle_withdrawal_method(self, query, method: str):
        """Handle withdrawal method selection."""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("🔐 Please login first using /login")
            return
        
        await self.show_withdrawal_website_redirect(query)

    async def show_withdrawal_website_redirect(self, query):
        """Redirect users to website for withdrawals."""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("🔐 Please login first using /login")
            return
        
        await query.edit_message_text(
            f"💰 Withdrawal Management\n\n"
            f"To manage withdrawals, please visit our website:\n"
            f"{self.website_url}\n\n"
            f"On the website you can:\n"
            f"• View available withdrawal methods\n"
            f"• Check minimum amounts and fees\n"
            f"• Submit withdrawal requests\n"
            f"• Track withdrawal status\n\n"
            f"💡 All withdrawal operations are handled through our web platform for security and better user experience."
        )

    async def show_withdrawal_methods(self, query):
        """Show withdrawal methods with website redirect."""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("🔐 Please login first using /login")
            return
        
        await query.edit_message_text(
            f"💰 Withdrawal Methods\n\n"
            f"Available withdrawal methods include:\n"
            f"• USDT (TRC20) - Min $5.00\n"
            f"• PayPal - Min $10.00\n"
            f"• Gift Cards - Min $5.00\n"
            f"• Bank Transfer - Min $20.00\n\n"
            f"📱 To view all methods and request withdrawals, visit:\n"
            f"{self.website_url}\n\n"
            f"All withdrawal processing is done through our secure web platform."
        )

    async def handle_withdraw_method_selection(self, query, method_data: str):
        """Handle withdrawal method selection with website redirect."""
        await self.show_withdrawal_website_redirect(query)

    async def show_withdrawal_form(self, query, method: str):
        """Show withdrawal form with website redirect."""
        await self.show_withdrawal_website_redirect(query)

    async def handle_task_action(self, query, action: str):
        """Handle task-related actions."""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("🔐 Please login first using /login")
            return
        
        await self.show_tasks_website_redirect(query)

    async def show_tasks_website_redirect(self, query):
        """Redirect users to website for tasks."""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("🔐 Please login first using /login")
            return
        
        await query.edit_message_text(
            f"📝 Task Management\n\n"
            f"To view and manage tasks, please visit our website:\n"
            f"{self.website_url}\n\n"
            f"On the website you can:\n"
            f"• Browse all available tasks\n"
            f"• Start and complete tasks\n"
            f"• Track your task progress\n"
            f"• Submit task completions\n"
            f"• View your task history\n\n"
            f"💡 The web platform provides a better experience for task completion with full features and visuals."
        )

    async def handle_offerwall_action(self, query, action: str):
        """Handle offerwall actions."""
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("🔐 Please login first using /login")
            return
        
        if action == "offerwall_list":
            await self.show_offerwalls(query)
        elif action.startswith("offerwall_"):
            offerwall_name = action.replace("offerwall_", "")
            await self.show_offerwall_details(query, offerwall_name)

    async def show_offerwall_details(self, query, offerwall_name: str):
        """Show details for specific offerwall."""
        user_id = query.from_user.id
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            logger.info(f"🎯 Fetching offerwall details for: {offerwall_name}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/services/{offerwall_name}/iframe/")
            
            response = requests.get(
                f"{self.api_base_url}/services/{offerwall_name}/iframe/", 
                headers=headers,
                timeout=10
            )
            
            # Debug API response
            self.debug_api_response(response, f"Offerwall {offerwall_name}")
            
            if response.status_code == 200:
                data = response.json()
                iframe_url = data.get('iframe_url')
                
                if iframe_url:
                    await query.edit_message_text(
                        f"🎯 {offerwall_name.title()} Offerwall\n\n"
                        f"Visit this URL to access the offerwall:\n"
                        f"{iframe_url}\n\n"
                        f"Complete offers and surveys to earn money!\n"
                        f"Earnings will be automatically credited to your account."
                    )
                else:
                    await query.edit_message_text(
                        f"❌ {offerwall_name.title()} offerwall is not available at the moment.\n\n"
                        f"📱 Try visiting our website for more options:\n"
                        f"{self.website_url}"
                    )
            else:
                await query.edit_message_text(
                    f"❌ Failed to load {offerwall_name} offerwall.\n\n"
                    f"📱 Please visit our website for offerwalls:\n"
                    f"{self.website_url}"
                )
                
        except Exception as e:
            logger.error(f"Offerwall details error: {e}")
            await query.edit_message_text(
                f"❌ Connection error. Please try again.\n\n"
                f"📱 Or visit our website directly:\n"
                f"{self.website_url}"
            )

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user balance."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            logger.info(f"💰 Fetching balance for user: {user_id}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/dashboard/stats/")
            
            response = requests.get(f"{self.api_base_url}/dashboard/stats/", headers=headers, timeout=10)
            
            # Debug API response
            self.debug_api_response(response, "Balance")
            
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
                await update.message.reply_text(message)
            else:
                logger.error(f"Balance fetch failed with status {response.status_code}")
                await update.message.reply_text("❌ Failed to fetch balance. Please try again.")
                
        except Exception as e:
            logger.error(f"Balance error: {e}")
            await update.message.reply_text("❌ Connection error. Please try again later.")

    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available tasks with website redirect."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        await update.message.reply_text(
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

    async def start_task_for_user(self, query, token: str, task_id: str):
        """Start a specific task for the user with website redirect."""
        await self.show_tasks_website_redirect(query)

    async def show_available_tasks(self, query, token: str, refresh: bool = False):
        """Show available tasks with website redirect."""
        await self.show_tasks_website_redirect(query)

    async def withdraw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show withdrawal options with website redirect."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        await update.message.reply_text(
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

    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referral information."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            logger.info(f"👥 Fetching referral info for user: {user_id}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/my-referral-info/")
            
            response = requests.get(f"{self.api_base_url}/my-referral-info/", headers=headers, timeout=10)
            
            # Debug API response
            self.debug_api_response(response, "Referral")
            
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
                await update.message.reply_text(message, parse_mode='HTML')
            else:
                logger.error(f"Referral fetch failed with status {response.status_code}")
                await update.message.reply_text("❌ Failed to fetch referral info.")
                
        except Exception as e:
            logger.error(f"Referral error: {e}")
            await update.message.reply_text("❌ Connection error. Please try again.")

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show leaderboard."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            logger.info(f"🏆 Fetching leaderboard for user: {user_id}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/leaderboard/top-earners/")
            
            response = requests.get(f"{self.api_base_url}/leaderboard/top-earners/", headers=headers, timeout=10)
            
            # Debug API response
            self.debug_api_response(response, "Leaderboard")
            
            if response.status_code == 200:
                data = response.json()
                top_earners = data.get('top_earners', [])
                
                message = "🏆 Top Earners Leaderboard\n\n"
                for i, earner in enumerate(top_earners[:10], 1):
                    username = earner.get('username', 'Anonymous')
                    earnings = earner.get('earnings', 0)
                    message += f"{i}. {username} - ${earnings:.2f}\n"
                
                message += f"\n📱 Visit our website for full leaderboard:\n{self.website_url}"
                await update.message.reply_text(message)
            else:
                logger.error(f"Leaderboard fetch failed with status {response.status_code}")
                await update.message.reply_text("❌ Failed to fetch leaderboard.")
                
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            await update.message.reply_text("❌ Connection error. Please try again.")

    async def offerwalls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available offerwalls."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
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
        
        await update.message.reply_text(
            "🎯 Available Offerwalls\n\n"
            "Complete surveys and offers to earn money!\n"
            "Choose an offerwall to get started:",
            reply_markup=reply_markup
        )

    async def show_offerwalls(self, query):
        """Show available offerwalls with inline keyboard."""
        keyboard = [
            [InlineKeyboardButton("TimeWall", callback_data="offerwall_timewall")],
            [InlineKeyboardButton("BitLabs", callback_data="offerwall_bitlabs")],
            [InlineKeyboardButton("PubScale", callback_data="offerwall_pubscale")],
            [InlineKeyboardButton("RevToo", callback_data="offerwall_revtoo")],
            [InlineKeyboardButton("CPX Research", callback_data="offerwall_cpx")],
            [InlineKeyboardButton("KiwiWall", callback_data="offerwall_kiwiwall")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎯 Available Offerwalls\n\n"
            "Complete surveys and offers to earn money!\n"
            "Choose an offerwall to get started:",
            reply_markup=reply_markup
        )

    async def my_tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's active and completed tasks with website redirect."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        await update.message.reply_text(
            f"📋 Your Tasks\n\n"
            f"To view your active and completed tasks, please visit our website:\n"
            f"{self.website_url}\n\n"
            f"On the website you can:\n"
            f"• View all your task history\n"
            f"• Track active task progress\n"
            f"• See completed task rewards\n"
            f"• Monitor your earnings\n"
            f"• Get detailed task analytics\n\n"
            f"💡 The web platform provides comprehensive task management with better visuals and tracking."
        )

    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's achievements."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            logger.info(f"🏆 Fetching achievements for user: {user_id}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/user-achievements/")
            
            response = requests.get(f"{self.api_base_url}/user-achievements/", headers=headers, timeout=10)
            
            # Debug API response
            self.debug_api_response(response, "Achievements")
            
            if response.status_code == 200:
                achievements = response.json()
                
                if not achievements:
                    await update.message.reply_text(
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
                await update.message.reply_text(message)
            else:
                logger.error(f"Achievements fetch failed with status {response.status_code}")
                await update.message.reply_text("❌ Failed to fetch achievements. Please try again.")
                
        except Exception as e:
            logger.error(f"Achievements error: {e}")
            await update.message.reply_text("❌ Connection error. Please try again.")

    async def support_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(support_text)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user statistics."""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("🔐 Please login first using /login")
            return
        
        token = self.user_sessions[user_id]['token']
        
        try:
            headers = {'Authorization': f'Token {token}'}
            logger.info(f"📊 Fetching stats for user: {user_id}")
            logger.info(f"🔧 Using API URL: {self.api_base_url}/dashboard/stats/")
            
            response = requests.get(f"{self.api_base_url}/dashboard/stats/", headers=headers, timeout=10)
            
            # Debug API response
            self.debug_api_response(response, "Stats")
            
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
                await update.message.reply_text(message)
            else:
                logger.error(f"Stats fetch failed with status {response.status_code}")
                await update.message.reply_text("❌ Failed to fetch statistics. Please try again.")
                
        except Exception as e:
            logger.error(f"Stats error: {e}")
            await update.message.reply_text("❌ Connection error. Please try again.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message."""
        help_text = f"""
🤖 EarnQuest Bot Help

Available Commands:
/login - Login to your account
/register - Create a new account
/balance - Check your balance and stats
/tasks - View available tasks (Website)
/mytasks - View your active tasks (Website)
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
        await update.message.reply_text(help_text)

    async def debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Debug command to show current session and API status."""
        user_id = update.effective_user.id
        
        debug_info = f"""
🔧 Debug Information

User ID: {user_id}
Session Active: {user_id in self.user_sessions}
API Base URL: {self.api_base_url}
Website URL: {self.website_url}
        """
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            debug_info += f"""
Session Details:
- Token: {session['token'][:20]}...
- User ID: {session['user_data'].get('user_id')}
- Username: {session['user_data'].get('username')}
            """
        
        await update.message.reply_text(debug_info)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in the telegram bot."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_user:
                await context.bot.send_message(
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
            self.application = Application.builder().token(self.token).build()
            
            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("login", self.login_command))
            self.application.add_handler(CommandHandler("register", self.register_command))
            self.application.add_handler(CommandHandler("balance", self.balance_command))
            self.application.add_handler(CommandHandler("tasks", self.tasks_command))
            self.application.add_handler(CommandHandler("mytasks", self.my_tasks_command))
            self.application.add_handler(CommandHandler("withdraw", self.withdraw_command))
            self.application.add_handler(CommandHandler("referral", self.referral_command))
            self.application.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
            self.application.add_handler(CommandHandler("offerwalls", self.offerwalls_command))
            self.application.add_handler(CommandHandler("achievements", self.achievements_command))
            self.application.add_handler(CommandHandler("support", self.support_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("debug", self.debug_command))
            
            # Add callback query handler
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # Add message handler for login/registration
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Add error handler
            self.application.add_error_handler(self.error_handler)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Telegram bot handlers: {e}")
            return False

    def run(self):
        """Run the bot - SIMPLIFIED VERSION"""
        if not self.setup_handlers():
            return
        
        logger.info("🤖 Starting Telegram Bot...")
        
        # Use the simple blocking version - this works reliably
        self.application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query'],
            close_loop=False  # Important: don't close the loop
        )

# Create bot instance
bot = EarnQuestBot()

def main():
    """Main function to run the bot."""
    bot.run()

if __name__ == "__main__":
    # Run the bot
    main()