#!/usr/bin/env python
"""
EarnQuest Telegram Bot - Full Featured
======================================
DUAL MODE:
- PRIVATE CHAT: Site interface (login, balance, support)
- GROUP CHAT: Moderator + Announcements

FEATURES:
- Polls backend for scheduled posts
- Auto-moderates groups (no links, spam detection)
- Controlled via Django admin panel
- Posts photos + text
- Intelligent support conversations
"""

import os
import re
import json
import logging
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ContextTypes, ConversationHandler, filters
)
from telegram.constants import ParseMode, ChatMemberStatus, ChatType
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(AWAITING_EMAIL, AWAITING_PASSWORD, AWAITING_REG_USERNAME, AWAITING_REG_EMAIL, 
 AWAITING_REG_PASSWORD, AWAITING_SUPPORT_MESSAGE, AWAITING_SUPPORT_FOLLOWUP) = range(7)


class EarnQuestBot:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.api_base_url = os.environ.get('API_BASE_URL', 'https://rebackend-ij74.onrender.com/api')
        self.bot_api_key = os.environ.get('BOT_API_KEY', '')  # Key for bot to auth with backend
        self.website_url = "https://earnquestapp.com"
        self.support_email = "support@earnquestapp.com"
        
        # Group settings
        self.managed_groups = set()  # Groups where bot is moderator
        
        # User sessions
        self.user_sessions: Dict[int, Dict] = {}
        
        # Support conversations
        self.support_conversations: Dict[int, Dict] = {}
        
        # Spam tracking
        self.message_counts: Dict[int, list] = {}  # user_id -> list of timestamps
        self.warned_users: Dict[int, int] = {}  # user_id -> warning count
        
        # Moderation settings (fetched from backend)
        self.mod_settings = {
            'allow_links': False,
            'allow_forwards': True,
            'max_messages_per_minute': 5,
            'mute_duration_minutes': 30,
            'auto_delete_links': True,
            'welcome_message': "👋 Welcome to EarnQuest! Earn money completing tasks at {website}",
            'rules_message': "📜 **Group Rules:**\n1. No spam\n2. No links\n3. Be respectful\n4. English only",
        }
        
        # FAQ responses for intelligent chat
        self.knowledge_base = {
            'withdraw': "💰 **Withdrawals** are done on our website: {website}/withdraw\n\nMinimum varies by method. You need $1.00 in qualifying earnings (tasks/surveys - referral & faucet don't count).",
            'faucet': "🚿 **Faucet** lets you claim free rewards every few minutes!\n\nVisit: {website}/rewards",
            'referral': "👥 **Referral Program**\n\n• Earn 10% of all your referrals' earnings!\n• Both get $0.10 signup bonus\n\nGet your link: Use /referral or visit {website}/rewards",
            'task': "📝 **Tasks** are available at {website}/tasks\n\nComplete tasks, submit proof, and earn money!\n\nUse /tasks to see available tasks!",
            'survey': "📊 **Surveys** are on our offerwalls: {website}/offerwalls\n\nMultiple providers = more opportunities!\n\nUse /surveys or /offerwalls to see options!",
            'offerwall': "🎯 **Offerwalls** let you earn by:\n\n• Completing surveys\n• Downloading apps\n• Signing up for services\n• Watching videos\n\nUse /offerwalls to browse!\n\nVisit: {website}/offerwalls",
            'offer': "🎯 **Offers & Surveys**\n\nEarn money completing offers on our offerwalls!\n\nUse /offerwalls to see all providers\nVisit: {website}/offerwalls",
            'payment': "💳 We support: PayPal, USDT, Litecoin, Skrill, and more!\n\nCheck methods at: {website}/withdraw",
            'help': "🆘 Need help?\n\n• Use /support in private chat\n• Email: {email}\n• Visit: {website}/help",
            'earn': "💵 **Ways to Earn:**\n\n1. 🎯 Offerwalls - /offerwalls\n2. 📝 Tasks - /tasks\n3. 👥 Referrals - /referral\n4. 🚿 Faucet - {website}/rewards\n5. 🎁 Bonus codes\n\nStart at: {website}",
            'minimum': "📊 **Withdrawal Minimum**\n\nYou need $1.00 in qualifying earnings.\n\n⚠️ Referral & faucet earnings don't count!\nOnly tasks, surveys, and offerwalls count.",
            'balance': "💰 Check your balance:\n\n• Use /balance in private chat\n• Visit: {website}/dashboard",
            'login': "🔐 To login:\n\n• Use /login in private chat\n• Or visit: {website}/signin",
            'register': "📝 To register:\n\n• Use /register in private chat\n• Or visit: {website}/register",
            'start': "🚀 **Getting Started:**\n\n1. /register or /login\n2. /offerwalls to earn\n3. /tasks for quick tasks\n4. /referral to invite friends\n5. /balance to check earnings",
        }
        
        logger.info(f"🔧 API: {self.api_base_url}")
        logger.info(f"✅ Bot token: {'Loaded' if self.token else 'MISSING!'}")

    # ==================== API HELPERS ====================
    
    def api_request(self, method: str, endpoint: str, token: str = None, data: dict = None, timeout: int = 15) -> tuple:
        """Make API request"""
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Token {token}'
        if self.bot_api_key:
            headers['X-Bot-Key'] = self.bot_api_key
            
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=timeout)
            else:
                return None, "Invalid method"
            return response, None
        except Exception as e:
            logger.error(f"API Error: {e}")
            return None, str(e)

    def get_user_token(self, telegram_id: int) -> Optional[str]:
        """Get user's API token if logged in"""
        session = self.user_sessions.get(telegram_id)
        return session.get('token') if session else None

    # ==================== BACKEND SYNC ====================
    
    async def fetch_scheduled_posts(self, context: ContextTypes.DEFAULT_TYPE):
        """Fetch and execute scheduled posts from backend"""
        try:
            response, error = self.api_request('GET', '/bot/scheduled-posts/')
            
            if error or not response or response.status_code != 200:
                return
            
            posts = response.json()
            
            for post in posts:
                await self.execute_scheduled_post(context, post)
                
        except Exception as e:
            logger.error(f"Error fetching scheduled posts: {e}")

    async def execute_scheduled_post(self, context: ContextTypes.DEFAULT_TYPE, post: dict):
        """Execute a scheduled post"""
        try:
            post_id = post.get('id')
            post_type = post.get('post_type')
            content = post.get('content', '')
            image_url = post.get('image_url')
            target_groups = post.get('target_groups', [])
            
            # Format content with website URL
            content = content.replace('{website}', self.website_url)
            
            for group_id in target_groups:
                try:
                    if image_url:
                        await context.bot.send_photo(
                            chat_id=group_id,
                            photo=image_url,
                            caption=content,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=group_id,
                            text=content,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    
                    # Log successful post
                    await self.report_to_backend(
                        event_type='post_sent',
                        data={'post_id': post_id, 'post_type': post_type, 'has_image': bool(image_url)},
                        chat_id=int(group_id) if str(group_id).lstrip('-').isdigit() else None,
                        description=f"Scheduled post #{post_id} ({post_type}) sent successfully"
                    )
                except Exception as e:
                    logger.error(f"Failed to post to {group_id}: {e}")
                    # Log failed post
                    await self.report_to_backend(
                        event_type='error',
                        data={'post_id': post_id, 'error': str(e), 'target_group': group_id},
                        description=f"Failed to send scheduled post #{post_id} to {group_id}: {e}"
                    )
            
            # Mark post as executed
            self.api_request('POST', f'/bot/scheduled-posts/{post_id}/mark-executed/')
            
        except Exception as e:
            logger.error(f"Error executing post: {e}")

    async def fetch_mod_settings(self):
        """Fetch moderation settings from backend"""
        try:
            response, error = self.api_request('GET', '/bot/settings/')
            if response and response.status_code == 200:
                settings = response.json()
                self.mod_settings.update(settings)
                logger.info("✅ Mod settings synced")
        except Exception as e:
            logger.error(f"Error fetching settings: {e}")

    async def report_to_backend(self, event_type: str, data: dict, 
                                  telegram_user_id: int = None, 
                                  telegram_username: str = None,
                                  chat_id: int = None,
                                  description: str = None):
        """Report events to backend for logging"""
        try:
            # Build payload with all required fields
            payload = {
                'event_type': event_type,
                'data': data,
            }
            
            if telegram_user_id:
                payload['telegram_user_id'] = telegram_user_id
            if telegram_username:
                payload['telegram_username'] = telegram_username
            if chat_id:
                payload['chat_id'] = chat_id
            if description:
                payload['description'] = description
            
            # Make request with bot API key header
            headers = {'Content-Type': 'application/json'}
            if self.bot_api_key:
                headers['X-Bot-Key'] = self.bot_api_key
            
            response = requests.post(
                f"{self.api_base_url}/bot/events/",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"Event logging failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error logging event: {e}")

    # ==================== MODERATION (GROUP MODE) ====================
    
    async def moderate_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Moderate group messages. Returns True if message should be deleted."""
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        
        # Only moderate in groups
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return False
        
        # Don't moderate admins
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return False
        except:
            pass
        
        text = message.text or message.caption or ''
        
        # Check for links
        if not self.mod_settings.get('allow_links', False):
            url_pattern = r'(https?://|www\.|t\.me/|@\w+)'
            if re.search(url_pattern, text, re.IGNORECASE):
                try:
                    await message.delete()
                    warning = await chat.send_message(
                        f"⚠️ @{user.username or user.first_name}, links are not allowed!",
                    )
                    # Log the deletion
                    await self.report_to_backend(
                        event_type='message_deleted',
                        data={'reason': 'Link detected', 'text_preview': text[:100]},
                        telegram_user_id=user.id,
                        telegram_username=user.username or user.first_name,
                        chat_id=chat.id,
                        description=f"Deleted message with link from @{user.username or user.first_name}"
                    )
                    # Delete warning after 10 seconds
                    await asyncio.sleep(10)
                    await warning.delete()
                except:
                    pass
                
                await self.warn_user_internal(chat.id, user.id, context, "Posting links")
                return True
        
        # Check for spam (too many messages)
        if await self.check_spam(user.id):
            try:
                await message.delete()
                await self.mute_user_internal(chat.id, user.id, context, 5)  # 5 min mute
                await chat.send_message(
                    f"🔇 @{user.username or user.first_name} muted for 5 minutes (spam)"
                )
                # Log the mute
                await self.report_to_backend(
                    event_type='user_muted',
                    data={'reason': 'Spam detected', 'duration_minutes': 5},
                    telegram_user_id=user.id,
                    telegram_username=user.username or user.first_name,
                    chat_id=chat.id,
                    description=f"Muted @{user.username or user.first_name} for 5 minutes (spam)"
                )
            except:
                pass
            return True
        
        # Check for forwarded messages (if not allowed)
        if message.forward_date and not self.mod_settings.get('allow_forwards', True):
            try:
                await message.delete()
            except:
                pass
            return True
        
        return False

    async def check_spam(self, user_id: int) -> bool:
        """Check if user is spamming"""
        now = datetime.now()
        max_per_minute = self.mod_settings.get('max_messages_per_minute', 5)
        
        if user_id not in self.message_counts:
            self.message_counts[user_id] = []
        
        # Clean old timestamps (older than 1 minute)
        self.message_counts[user_id] = [
            ts for ts in self.message_counts[user_id]
            if (now - ts).seconds < 60
        ]
        
        self.message_counts[user_id].append(now)
        
        return len(self.message_counts[user_id]) > max_per_minute

    async def warn_user_internal(self, chat_id: int, user_id: int, context, reason: str):
        """Internal warning system"""
        if user_id not in self.warned_users:
            self.warned_users[user_id] = 0
        
        self.warned_users[user_id] += 1
        warnings = self.warned_users[user_id]
        
        if warnings >= 3:
            await self.ban_user_internal(chat_id, user_id, context)
            await context.bot.send_message(
                chat_id,
                f"🚫 User banned after 3 warnings!"
            )
            # Log the ban
            await self.report_to_backend(
                event_type='user_banned',
                data={'reason': f'3 warnings: {reason}', 'warning_count': warnings},
                telegram_user_id=user_id,
                chat_id=chat_id,
                description=f"User banned after 3 warnings. Last warning: {reason}"
            )
            del self.warned_users[user_id]
            return  # Don't log a warning if we already logged a ban
        
        # Report warning to backend
        await self.report_to_backend(
            event_type='user_warned',
            data={'reason': reason, 'warning_count': warnings},
            telegram_user_id=user_id,
            chat_id=chat_id,
            description=f"User warned ({warnings}/3): {reason}"
        )

    async def mute_user_internal(self, chat_id: int, user_id: int, context, minutes: int):
        """Mute a user"""
        until = datetime.now() + timedelta(minutes=minutes)
        try:
            await context.bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until
            )
        except Exception as e:
            logger.error(f"Failed to mute: {e}")

    async def ban_user_internal(self, chat_id: int, user_id: int, context):
        """Ban a user"""
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
        except Exception as e:
            logger.error(f"Failed to ban: {e}")

    # ==================== GROUP COMMANDS ====================
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome new members"""
        for member in update.message.new_chat_members:
            if member.is_bot:
                continue
            
            welcome = self.mod_settings.get('welcome_message', '👋 Welcome!')
            welcome = welcome.replace('{website}', self.website_url)
            welcome = welcome.replace('{name}', member.first_name)
            
            keyboard = [[InlineKeyboardButton("🌐 Start Earning", url=self.website_url)]]
            
            try:
                msg = await update.effective_chat.send_message(
                    f"👋 Welcome {member.first_name}!\n\n{welcome}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                # Delete welcome after 60 seconds to keep chat clean
                await asyncio.sleep(60)
                await msg.delete()
            except:
                pass

    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group rules"""
        rules = self.mod_settings.get('rules_message', '📜 Be respectful!')
        rules = rules.replace('{website}', self.website_url)
        await update.message.reply_text(rules, parse_mode=ParseMode.MARKDOWN)

    # ==================== INTELLIGENT CHAT (GROUP) ====================
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in groups - moderate + respond intelligently"""
        message = update.effective_message
        
        # First, moderate
        if await self.moderate_message(update, context):
            return  # Message was deleted
        
        text = (message.text or '').lower()
        
        # Check if bot is mentioned or replied to
        bot_mentioned = False
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            bot_mentioned = True
        if f'@{(await context.bot.get_me()).username}'.lower() in text:
            bot_mentioned = True
        
        if not bot_mentioned:
            # Check for keywords and respond helpfully
            for keyword, response in self.knowledge_base.items():
                if keyword in text and ('?' in text or 'how' in text or 'what' in text or 'where' in text):
                    formatted = response.format(website=self.website_url, email=self.support_email)
                    await message.reply_text(formatted, parse_mode=ParseMode.MARKDOWN)
                    return
            return
        
        # Bot was mentioned - provide help
        await self.intelligent_response(update, context, text)

    async def intelligent_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Generate intelligent response based on user query"""
        message = update.effective_message
        
        # Find best matching response
        best_match = None
        best_score = 0
        
        keywords_map = {
            'withdraw': ['withdraw', 'payout', 'cash out', 'payment', 'get money', 'get paid'],
            'faucet': ['faucet', 'free', 'claim'],
            'referral': ['referral', 'refer', 'invite', 'friend', 'commission'],
            'task': ['task', 'job', 'work', 'complete'],
            'survey': ['survey', 'offerwall', 'offer'],
            'payment': ['paypal', 'usdt', 'crypto', 'litecoin', 'skrill'],
            'help': ['help', 'support', 'problem', 'issue', 'contact'],
            'earn': ['earn', 'money', 'make money', 'how to', 'start'],
            'minimum': ['minimum', 'min', 'requirement', 'need', 'qualifying'],
            'balance': ['balance', 'check', 'how much'],
            'login': ['login', 'sign in', 'log in', 'access'],
            'register': ['register', 'sign up', 'create account', 'join'],
        }
        
        for key, keywords in keywords_map.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_match = key
        
        if best_match and best_match in self.knowledge_base:
            response = self.knowledge_base[best_match]
            formatted = response.format(website=self.website_url, email=self.support_email)
            await message.reply_text(formatted, parse_mode=ParseMode.MARKDOWN)
        else:
            # Default response
            await message.reply_text(
                f"🤖 Hi! I can help with:\n\n"
                f"• /balance - Check your balance\n"
                f"• /referral - Get referral link\n"
                f"• /support - Get help\n\n"
                f"Or ask me about: withdrawals, tasks, surveys, referrals, faucet\n\n"
                f"🌐 Full features at: {self.website_url}",
                parse_mode=ParseMode.MARKDOWN
            )

    # ==================== PRIVATE CHAT COMMANDS ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - different for private vs group"""
        chat = update.effective_chat
        user = update.effective_user
        
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            # Group - show brief info
            await update.message.reply_text(
                f"🤖 **EarnQuest Bot**\n\n"
                f"I'm here to help and keep this group clean!\n\n"
                f"🌐 Start earning: {self.website_url}\n"
                f"💬 DM me for account features",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Private chat - full menu
        keyboard = [
            [InlineKeyboardButton("🔐 Login", callback_data="start_login"),
             InlineKeyboardButton("📝 Register", callback_data="start_register")],
            [InlineKeyboardButton("💰 Balance", callback_data="cmd_balance"),
             InlineKeyboardButton("📊 Stats", callback_data="cmd_stats")],
            [InlineKeyboardButton("🎯 Offerwalls", callback_data="cmd_offerwalls"),
             InlineKeyboardButton("📝 Tasks", callback_data="cmd_tasks")],
            [InlineKeyboardButton("👥 Referral", callback_data="cmd_referral"),
             InlineKeyboardButton("🏆 Leaderboard", callback_data="cmd_leaderboard")],
            [InlineKeyboardButton("🆘 Support", callback_data="cmd_support"),
             InlineKeyboardButton("❓ FAQ", callback_data="cmd_faq")],
            [InlineKeyboardButton("🌐 Visit Website", url=self.website_url)],
        ]
        
        welcome = f"""
🎉 **Welcome to EarnQuest, {user.first_name}!**

Earn money by completing tasks, surveys, and offers!

**💰 Earning Options:**
• 🎯 Offerwalls - Complete offers & surveys
• 📝 Tasks - Simple tasks for quick cash
• 👥 Referrals - Earn 10% from friends

**Quick Commands:**
/offerwalls - Browse earning opportunities  
/tasks - View available tasks
/balance - Check your earnings
/referral - Get your referral link

_Tap a button below to get started!_
"""
        
        await update.message.reply_text(
            welcome,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start login process"""
        if update.effective_chat.type != ChatType.PRIVATE:
            await update.message.reply_text("🔐 Please login in private chat: @EarnQuestBot")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "📧 **Login to EarnQuest**\n\nPlease enter your email address:",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAITING_EMAIL

    async def receive_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive email"""
        email = update.message.text.strip()
        
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            await update.message.reply_text("❌ Invalid email. Please try again:")
            return AWAITING_EMAIL
        
        context.user_data['login_email'] = email
        await update.message.reply_text("🔐 Now enter your password:")
        return AWAITING_PASSWORD

    async def receive_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete login"""
        password = update.message.text
        email = context.user_data.get('login_email')
        
        # Delete password message
        try:
            await update.message.delete()
        except:
            pass
        
        status_msg = await update.effective_chat.send_message("🔄 Logging in...")
        
        response, error = self.api_request('POST', '/auth/login/', data={
            'email': email,
            'password': password
        })
        
        if error:
            await status_msg.edit_text(f"❌ Connection error. Please try again later.")
            context.user_data.clear()
            return ConversationHandler.END
        
        if response.status_code == 200:
            data = response.json()
            self.user_sessions[update.effective_user.id] = {
                'token': data.get('token'),
                'username': data.get('username'),
                'user_id': data.get('user_id'),
                'email': email
            }
            
            # Log the login event
            await self.report_to_backend(
                event_type='login',
                data={'platform_user_id': data.get('user_id'), 'username': data.get('username')},
                telegram_user_id=update.effective_user.id,
                telegram_username=update.effective_user.username or '',
                description=f"User {data.get('username')} logged in via Telegram"
            )
            
            await status_msg.edit_text(
                f"✅ **Welcome back, {data.get('username')}!**\n\n"
                f"Use /balance to check your earnings\n"
                f"Use /referral to get your referral link\n"
                f"Use /support if you need help",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            try:
                error_msg = response.json().get('error', 'Invalid credentials')
            except:
                error_msg = 'Login failed'
            await status_msg.edit_text(f"❌ {error_msg}")
        
        context.user_data.clear()
        return ConversationHandler.END

    async def register_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start registration"""
        if update.effective_chat.type != ChatType.PRIVATE:
            await update.message.reply_text("📝 Please register in private chat: @EarnQuestBot")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "📝 **Create your EarnQuest account!**\n\n"
            "Choose a username (letters, numbers, underscores):",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAITING_REG_USERNAME

    async def receive_reg_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.message.text.strip()
        if len(username) < 3 or not re.match(r'^[\w]+$', username):
            await update.message.reply_text("❌ Invalid username. Min 3 chars, letters/numbers/underscores:")
            return AWAITING_REG_USERNAME
        
        context.user_data['reg_username'] = username
        await update.message.reply_text("📧 Enter your email address:")
        return AWAITING_REG_EMAIL

    async def receive_reg_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        email = update.message.text.strip()
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            await update.message.reply_text("❌ Invalid email. Please try again:")
            return AWAITING_REG_EMAIL
        
        context.user_data['reg_email'] = email
        await update.message.reply_text("🔐 Create a password (min 6 characters):")
        return AWAITING_REG_PASSWORD

    async def receive_reg_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        password = update.message.text
        
        try:
            await update.message.delete()
        except:
            pass
        
        if len(password) < 6:
            await update.effective_chat.send_message("❌ Password too short. Min 6 characters:")
            return AWAITING_REG_PASSWORD
        
        status_msg = await update.effective_chat.send_message("🔄 Creating account...")
        
        response, error = self.api_request('POST', '/auth/register/', data={
            'username': context.user_data['reg_username'],
            'email': context.user_data['reg_email'],
            'password': password,
            'confirm_password': password,
            'agree_to_terms': True
        })
        
        if error:
            await status_msg.edit_text(f"❌ Connection error. Please try later.")
            context.user_data.clear()
            return ConversationHandler.END
        
        if response.status_code == 201:
            data = response.json()
            
            # Log the registration event
            await self.report_to_backend(
                event_type='registration',
                data={'platform_user_id': data.get('user_id'), 'username': data.get('username')},
                telegram_user_id=update.effective_user.id,
                telegram_username=update.effective_user.username or '',
                description=f"New user {data.get('username')} registered via Telegram"
            )
            
            await status_msg.edit_text(
                f"🎉 **Welcome to EarnQuest, {data.get('username')}!**\n\n"
                f"💰 You received a **$0.10 welcome bonus!**\n\n"
                f"📧 Check your email to verify your account.\n\n"
                f"Use /login to access your account.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            try:
                errors = response.json()
                error_text = str(errors)
            except:
                error_text = 'Registration failed'
            await status_msg.edit_text(f"❌ {error_text}")
        
        context.user_data.clear()
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END

    # ==================== USER FEATURE COMMANDS ====================
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check balance"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        if not token:
            await update.message.reply_text("🔐 Please /login first!")
            return
        
        response, error = self.api_request('GET', '/profile/', token=token)
        
        if error or response.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch balance. Try /login again.")
            return
        
        data = response.json()
        withdrawal_info = data.get('withdrawal_info', {})
        can_withdraw = withdrawal_info.get('can_withdraw', False)
        remaining = withdrawal_info.get('remaining_to_unlock', 0)
        
        status = "✅ Ready to withdraw!" if can_withdraw else f"⏳ Need ${remaining:.2f} more qualifying earnings"
        
        await update.message.reply_text(
            f"💰 **Your Balance**\n\n"
            f"**Balance:** ${float(data.get('current_balance', 0)):.2f}\n"
            f"**Total Earned:** ${float(data.get('total_earned', 0)):.2f}\n"
            f"**Qualifying:** ${float(data.get('qualifying_earnings', 0)):.2f}\n"
            f"**Referral Earnings:** ${float(data.get('referral_earnings', 0)):.2f}\n"
            f"**Level:** {data.get('level', 'Bronze')}\n\n"
            f"**Withdrawal:** {status}\n\n"
            f"🌐 Withdraw at: {self.website_url}/withdraw",
            parse_mode=ParseMode.MARKDOWN
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show stats"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        if not token:
            await update.message.reply_text("🔐 Please /login first!")
            return
        
        response, error = self.api_request('GET', '/dashboard/stats/', token=token)
        
        if error or response.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch stats.")
            return
        
        data = response.json()
        ref = data.get('referral_stats', {})
        
        await update.message.reply_text(
            f"📊 **Your Statistics**\n\n"
            f"💵 Balance: ${data.get('balance', 0):.2f}\n"
            f"💰 Total Earned: ${data.get('total_earned', 0):.2f}\n"
            f"📈 Today: ${data.get('today_earnings', 0):.2f}\n"
            f"✅ Tasks: {data.get('total_tasks', 0)}\n"
            f"🔥 Streak: {data.get('streak_days', 0)} days\n"
            f"👥 Referrals: {ref.get('total_referrals', 0)}\n"
            f"💎 Ref Earnings: ${ref.get('earnings', 0):.2f}\n\n"
            f"🌐 {self.website_url}/dashboard",
            parse_mode=ParseMode.MARKDOWN
        )

    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referral info"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        if not token:
            await update.message.reply_text("🔐 Please /login first!")
            return
        
        response, error = self.api_request('GET', '/my-referral-info/', token=token)
        
        if error or response.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch referral info.")
            return
        
        data = response.json()
        
        await update.message.reply_text(
            f"👥 **Your Referral Program**\n\n"
            f"📋 Code: `{data.get('referral_code', 'N/A')}`\n\n"
            f"🔗 Link:\n{data.get('referral_url', 'N/A')}\n\n"
            f"📊 **Stats:**\n"
            f"• Referrals: {data.get('total_referrals', 0)}\n"
            f"• Earnings: ${data.get('referral_earnings', 0):.2f}\n\n"
            f"💰 **Earn 10% of all your referrals' earnings!**",
            parse_mode=ParseMode.MARKDOWN
        )

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show leaderboard"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        if not token:
            await update.message.reply_text("🔐 Please /login first!")
            return
        
        response, error = self.api_request('GET', '/leaderboard/top-earners/', token=token)
        
        if error or response.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch leaderboard.")
            return
        
        data = response.json()
        top = data.get('top_earners', [])[:10]
        
        medals = ['🥇', '🥈', '🥉'] + ['🏅'] * 7
        
        msg = "🏆 **Top Earners**\n\n"
        for i, user in enumerate(top):
            msg += f"{medals[i]} {user.get('username')} - ${user.get('earnings', 0):.2f}\n"
        
        msg += f"\n🌐 {self.website_url}/leaderboard"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def offerwalls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available offerwalls"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        if not token:
            await update.message.reply_text(
                "🔐 **Login Required**\n\n"
                "Please /login to access offerwalls and start earning!\n\n"
                f"Or visit: {self.website_url}/offerwalls",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        status_msg = await update.message.reply_text("🔄 Loading offerwalls...")
        
        response, error = self.api_request('GET', '/offerwalls/', token=token)
        
        if error or response.status_code != 200:
            await status_msg.edit_text("❌ Failed to fetch offerwalls. Try again later.")
            return
        
        data = response.json()
        offerwalls = data if isinstance(data, list) else data.get('results', data.get('offerwalls', []))
        
        if not offerwalls:
            await status_msg.edit_text(
                "📭 **No Offerwalls Available**\n\n"
                f"Check back later or visit: {self.website_url}/offerwalls",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Build message with offerwall list
        msg = "🎯 **Available Offerwalls**\n\n"
        msg += "Complete offers & surveys to earn money!\n\n"
        
        keyboard = []
        
        for wall in offerwalls[:10]:  # Limit to 10
            name = wall.get('name', wall.get('title', 'Unknown'))
            provider = wall.get('provider', '')
            status = "✅" if wall.get('is_active', True) else "⏸️"
            
            # Get iframe URL if available
            iframe_url = wall.get('iframe_url', wall.get('url', ''))
            wall_id = wall.get('id', '')
            
            msg += f"{status} **{name}**"
            if provider:
                msg += f" ({provider})"
            msg += "\n"
            
            # Create direct link button
            if wall_id:
                # Link to offerwall page on website
                wall_url = f"{self.website_url}/offerwalls?wall={wall_id}"
                keyboard.append([InlineKeyboardButton(f"🎯 {name}", url=wall_url)])
        
        msg += f"\n💡 _Tip: Click a button below to start earning!_"
        
        # Add main offerwalls page link
        keyboard.append([InlineKeyboardButton("🌐 View All Offerwalls", url=f"{self.website_url}/offerwalls")])
        
        await status_msg.edit_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available tasks"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        if not token:
            await update.message.reply_text(
                "🔐 **Login Required**\n\n"
                "Please /login to view and complete tasks!\n\n"
                f"Or visit: {self.website_url}/tasks",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        status_msg = await update.message.reply_text("🔄 Loading tasks...")
        
        response, error = self.api_request('GET', '/tasks/', token=token)
        
        if error or response.status_code != 200:
            await status_msg.edit_text("❌ Failed to fetch tasks. Try again later.")
            return
        
        data = response.json()
        tasks = data if isinstance(data, list) else data.get('results', data.get('tasks', []))
        
        if not tasks:
            await status_msg.edit_text(
                "📭 **No Tasks Available**\n\n"
                "Check back later for new earning opportunities!\n\n"
                f"🎯 Try offerwalls instead: /offerwalls\n"
                f"🌐 {self.website_url}/tasks",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Count and categorize tasks
        total_tasks = len(tasks)
        total_reward = sum(float(t.get('reward', t.get('amount', 0))) for t in tasks)
        
        msg = f"📝 **Available Tasks: {total_tasks}**\n\n"
        msg += f"💰 Total Potential: ${total_reward:.2f}\n\n"
        
        # Show top 5 tasks
        msg += "**Top Tasks:**\n"
        for i, task in enumerate(tasks[:5], 1):
            title = task.get('title', task.get('name', 'Task'))[:40]
            reward = float(task.get('reward', task.get('amount', 0)))
            category = task.get('category', {})
            cat_name = category.get('name', '') if isinstance(category, dict) else str(category)
            
            msg += f"{i}. {title}\n"
            msg += f"   💵 ${reward:.2f}"
            if cat_name:
                msg += f" | 📂 {cat_name}"
            msg += "\n"
        
        if total_tasks > 5:
            msg += f"\n_...and {total_tasks - 5} more tasks!_\n"
        
        msg += f"\n💡 _Complete tasks on our website to earn!_"
        
        keyboard = [
            [InlineKeyboardButton("📝 View All Tasks", url=f"{self.website_url}/tasks")],
            [InlineKeyboardButton("🎯 Offerwalls", callback_data="cmd_offerwalls"),
             InlineKeyboardButton("💰 Balance", callback_data="cmd_balance")],
        ]
        
        await status_msg.edit_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def surveys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show survey info - directs to offerwalls"""
        user_id = update.effective_user.id
        token = self.get_user_token(user_id)
        
        msg = """📊 **Surveys on EarnQuest**

Surveys are available through our offerwalls!

**Popular Survey Providers:**
• Bitlabs - High payouts
• CPX Research - Many opportunities
• Pollfish - Quick surveys
• Theorem Reach - Regular surveys

**Tips for Surveys:**
✅ Fill out your profile completely
✅ Be consistent with answers
✅ Use a desktop for best experience
✅ Check multiple providers

"""
        
        keyboard = [
            [InlineKeyboardButton("🎯 Go to Offerwalls", url=f"{self.website_url}/offerwalls")],
        ]
        
        if token:
            keyboard.insert(0, [InlineKeyboardButton("🎯 View Offerwalls", callback_data="cmd_offerwalls")])
        else:
            msg += "🔐 /login to access surveys!"
        
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== SUPPORT SYSTEM ====================
    
    async def support_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start support conversation"""
        if update.effective_chat.type != ChatType.PRIVATE:
            await update.message.reply_text("🆘 For support, please DM me: @EarnQuestBot")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("💰 Withdrawal Issue", callback_data="support_withdrawal")],
            [InlineKeyboardButton("📝 Task Problem", callback_data="support_task")],
            [InlineKeyboardButton("🔐 Account Issue", callback_data="support_account")],
            [InlineKeyboardButton("🐛 Bug Report", callback_data="support_bug")],
            [InlineKeyboardButton("❓ Other", callback_data="support_other")],
        ]
        
        await update.message.reply_text(
            "🆘 **EarnQuest Support**\n\n"
            "What do you need help with?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return AWAITING_SUPPORT_MESSAGE

    async def receive_support_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle support category selection"""
        query = update.callback_query
        await query.answer()
        
        category = query.data.replace('support_', '')
        context.user_data['support_category'] = category
        
        await query.edit_message_text(
            f"📝 **Support - {category.title()}**\n\n"
            f"Please describe your issue in detail:\n"
            f"• What were you trying to do?\n"
            f"• What happened?\n"
            f"• Any error messages?\n\n"
            f"Type /cancel to exit.",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAITING_SUPPORT_MESSAGE

    async def receive_support_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive support message and create ticket"""
        message = update.message.text
        user = update.effective_user
        category = context.user_data.get('support_category', 'general')
        
        # Get session info
        session = self.user_sessions.get(user.id, {})
        
        # Try to create ticket via API
        if session.get('token'):
            response, error = self.api_request('POST', '/support/tickets/',
                token=session['token'],
                data={
                    'subject': f'[Telegram] {category.title()} Issue',
                    'message': message,
                    'category': category
                }
            )
            
            if response and response.status_code == 201:
                ticket = response.json()
                
                # Log the support ticket event
                await self.report_to_backend(
                    event_type='support_ticket',
                    data={'ticket_id': ticket.get('id'), 'category': category, 'subject': f'[Telegram] {category.title()} Issue'},
                    telegram_user_id=user.id,
                    telegram_username=user.username or user.first_name,
                    description=f"Support ticket #{ticket.get('id')} created: {category.title()}"
                )
                
                await update.message.reply_text(
                    f"✅ **Ticket Created!**\n\n"
                    f"**Ticket ID:** #{ticket.get('id')}\n"
                    f"**Category:** {category.title()}\n\n"
                    f"We'll respond within 24-48 hours.\n"
                    f"Check status at: {self.website_url}/support",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data.clear()
                return ConversationHandler.END
        
        # Fallback - store for manual handling
        await update.message.reply_text(
            f"✅ **Message Received!**\n\n"
            f"Our team will review your message.\n\n"
            f"📧 You can also email: {self.support_email}\n"
            f"🌐 Or visit: {self.website_url}/support",
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data.clear()
        return ConversationHandler.END

    async def faq_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show FAQ"""
        keyboard = [
            [InlineKeyboardButton("🎯 Offerwalls", callback_data="faq_offerwall"),
             InlineKeyboardButton("📝 Tasks", callback_data="faq_task")],
            [InlineKeyboardButton("💰 Withdrawals", callback_data="faq_withdraw"),
             InlineKeyboardButton("📊 Minimum", callback_data="faq_minimum")],
            [InlineKeyboardButton("👥 Referrals", callback_data="faq_referral"),
             InlineKeyboardButton("🚿 Faucet", callback_data="faq_faucet")],
            [InlineKeyboardButton("💵 How to Earn", callback_data="faq_earn"),
             InlineKeyboardButton("🚀 Getting Started", callback_data="faq_start")],
        ]
        
        await update.message.reply_text(
            "❓ **Frequently Asked Questions**\n\nSelect a topic:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== CALLBACK HANDLER ====================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Start actions
        if data == "start_login":
            await query.message.reply_text("📧 Enter your email:")
            return AWAITING_EMAIL
        
        if data == "start_register":
            await query.message.reply_text("👤 Choose a username:")
            return AWAITING_REG_USERNAME
        
        # Command shortcuts
        if data == "cmd_balance":
            # Simulate balance command
            update.message = query.message
            await self.balance_command(update, context)
            return
        
        if data == "cmd_stats":
            update.message = query.message
            await self.stats_command(update, context)
            return
        
        if data == "cmd_referral":
            update.message = query.message
            await self.referral_command(update, context)
            return
        
        if data == "cmd_leaderboard":
            update.message = query.message
            await self.leaderboard_command(update, context)
            return
        
        if data == "cmd_offerwalls":
            update.message = query.message
            await self.offerwalls_command(update, context)
            return
        
        if data == "cmd_tasks":
            update.message = query.message
            await self.tasks_command(update, context)
            return
        
        if data == "cmd_surveys":
            update.message = query.message
            await self.surveys_command(update, context)
            return
        
        if data == "cmd_support":
            keyboard = [
                [InlineKeyboardButton("💰 Withdrawal", callback_data="support_withdrawal")],
                [InlineKeyboardButton("📝 Task", callback_data="support_task")],
                [InlineKeyboardButton("🔐 Account", callback_data="support_account")],
                [InlineKeyboardButton("❓ Other", callback_data="support_other")],
            ]
            await query.edit_message_text(
                "🆘 **Support**\n\nWhat do you need help with?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        if data == "cmd_faq":
            update.message = query.message
            await self.faq_command(update, context)
            return
        
        # Support categories
        if data.startswith("support_"):
            context.user_data['support_category'] = data.replace('support_', '')
            await query.edit_message_text(
                "📝 Describe your issue in detail:\n\n/cancel to exit"
            )
            return AWAITING_SUPPORT_MESSAGE
        
        # FAQ answers
        if data.startswith("faq_"):
            topic = data.replace("faq_", "")
            if topic in self.knowledge_base:
                answer = self.knowledge_base[topic].format(
                    website=self.website_url, 
                    email=self.support_email
                )
                await query.edit_message_text(answer, parse_mode=ParseMode.MARKDOWN)

    # ==================== MESSAGE ROUTER ====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route messages based on chat type"""
        chat = update.effective_chat
        
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await self.handle_group_message(update, context)
        # Private messages handled by conversation handlers

    # ==================== SCHEDULED TASKS ====================
    
    async def scheduled_post_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to check for scheduled posts"""
        await self.fetch_scheduled_posts(context)

    async def sync_settings_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to sync moderation settings"""
        await self.fetch_mod_settings()

    # ==================== SETUP ====================
    
    def setup_handlers(self):
        """Setup all handlers"""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not set!")
            return False
        
        try:
            self.application = Application.builder().token(self.token).build()
            
            # Login conversation
            login_conv = ConversationHandler(
                entry_points=[
                    CommandHandler('login', self.login_command),
                    CallbackQueryHandler(self.button_handler, pattern='^start_login$')
                ],
                states={
                    AWAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_email)],
                    AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_password)],
                },
                fallbacks=[CommandHandler('cancel', self.cancel)],
                per_message=False,
            )
            
            # Register conversation
            register_conv = ConversationHandler(
                entry_points=[
                    CommandHandler('register', self.register_command),
                    CallbackQueryHandler(self.button_handler, pattern='^start_register$')
                ],
                states={
                    AWAITING_REG_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_reg_username)],
                    AWAITING_REG_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_reg_email)],
                    AWAITING_REG_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_reg_password)],
                },
                fallbacks=[CommandHandler('cancel', self.cancel)],
                per_message=False,
            )
            
            # Support conversation
            support_conv = ConversationHandler(
                entry_points=[
                    CommandHandler('support', self.support_command),
                    CallbackQueryHandler(self.receive_support_category, pattern='^support_')
                ],
                states={
                    AWAITING_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_support_message)],
                },
                fallbacks=[CommandHandler('cancel', self.cancel)],
                per_message=False,
            )
            
            # Add conversation handlers first
            self.application.add_handler(login_conv)
            self.application.add_handler(register_conv)
            self.application.add_handler(support_conv)
            
            # Commands
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("help", self.start))
            self.application.add_handler(CommandHandler("balance", self.balance_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("referral", self.referral_command))
            self.application.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
            self.application.add_handler(CommandHandler("offerwalls", self.offerwalls_command))
            self.application.add_handler(CommandHandler("offers", self.offerwalls_command))  # Alias
            self.application.add_handler(CommandHandler("tasks", self.tasks_command))
            self.application.add_handler(CommandHandler("surveys", self.surveys_command))
            self.application.add_handler(CommandHandler("earn", self.offerwalls_command))  # Alias
            self.application.add_handler(CommandHandler("faq", self.faq_command))
            self.application.add_handler(CommandHandler("rules", self.rules_command))
            
            # Callback handler
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # New members
            self.application.add_handler(MessageHandler(
                filters.StatusUpdate.NEW_CHAT_MEMBERS, 
                self.handle_new_member
            ))
            
            # All other messages
            self.application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_message
            ))
            
            # Error handler
            async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                """Handle errors gracefully"""
                error = context.error
                
                # Ignore conflict errors (multiple instances)
                if "Conflict" in str(error):
                    logger.warning("⚠️ Conflict with another instance - this will resolve automatically")
                    return
                
                # Log other errors
                logger.error(f"Exception while handling an update: {error}")
            
            self.application.add_error_handler(error_handler)
            
            # Scheduled jobs (requires job-queue extension)
            job_queue = self.application.job_queue
            if job_queue:
                job_queue.run_repeating(self.scheduled_post_job, interval=60, first=10)  # Check every minute
                job_queue.run_repeating(self.sync_settings_job, interval=300, first=5)  # Sync every 5 minutes
                logger.info("✅ Job queue configured!")
            else:
                logger.warning("⚠️ Job queue not available. Install with: pip install 'python-telegram-bot[job-queue]'")
            
            logger.info("✅ Bot handlers configured!")
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

    async def clear_webhook_and_updates(self):
        """Clear webhook and pending updates before starting"""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                # Delete webhook and drop pending updates
                url = f"https://api.telegram.org/bot{self.token}/deleteWebhook?drop_pending_updates=true"
                response = await client.post(url)
                if response.status_code == 200:
                    logger.info("✅ Webhook cleared, pending updates dropped")
                else:
                    logger.warning(f"⚠️ Failed to clear webhook: {response.text}")
        except Exception as e:
            logger.error(f"Error clearing webhook: {e}")

    def run(self):
        """Run the bot"""
        import time
        
        # Wait for old instance to fully stop
        logger.info("⏳ Waiting 5 seconds for old instance to stop...")
        time.sleep(5)
        
        if not self.setup_handlers():
            return
        
        logger.info("🤖 Starting EarnQuest Bot...")
        
        # Run polling with error handling
        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,  # Drop any queued updates
                close_loop=False
            )
        except Exception as e:
            logger.error(f"Bot stopped with error: {e}")


if __name__ == "__main__":
    import time
    import sys
    
    # Add startup delay to prevent conflicts during deployment
    startup_delay = int(os.environ.get('BOT_STARTUP_DELAY', '5'))
    if startup_delay > 0:
        logger.info(f"⏳ Startup delay: {startup_delay} seconds...")
        time.sleep(startup_delay)
    
    # Clear any existing sessions via API
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if token:
        try:
            import requests
            # Force delete webhook and drop pending updates
            url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
            response = requests.post(url, timeout=10)
            logger.info(f"🔄 Webhook cleanup: {response.json()}")
            
            # Small delay after cleanup
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Webhook cleanup failed: {e}")
    
    bot = EarnQuestBot()
    
    # Retry logic for conflict errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            bot.run()
            break
        except Exception as e:
            if "Conflict" in str(e) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                logger.warning(f"⚠️ Conflict detected, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Bot failed: {e}")
                sys.exit(1)
