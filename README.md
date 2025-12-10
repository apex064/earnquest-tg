# EarnQuest Telegram Bot

A fully-featured Telegram bot with dual-mode operation: **Site Interface** in private chats and **Moderator** in groups.

## 🌟 Features

### Dual Mode Operation

| Mode | Description |
|------|-------------|
| **Private Chat** | Site interface - login, balance, referrals, support |
| **Group Chat** | Moderator - auto-moderation, announcements, intelligent responses |

### Private Chat Features
- 🔐 Login/Register
- 💰 Check balance & stats
- 👥 Referral program
- 🏆 Leaderboard
- 🆘 Support tickets (creates tickets via API)
- ❓ Interactive FAQ

### Group Moderation Features
- 🚫 Auto-delete links (configurable)
- 🔇 Spam detection & auto-mute
- ⚠️ Warning system (3 warnings = auto-ban)
- 👋 Welcome messages for new members
- 📜 Rules command
- 🤖 Intelligent responses to questions

### Admin Dashboard Control
From Django admin, you can:
- 📢 Schedule posts (with images!)
- 🎁 Post bonus codes
- 📝 Post new offers/tasks
- 🚫 Ban users from groups
- ⚙️ Configure moderation settings
- 📊 View bot events/logs

## 🛠 Setup

### Environment Variables

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# API Connection
API_BASE_URL=https://rebackend-ij74.onrender.com/api
BOT_API_KEY=your_secure_api_key  # Bot authenticates with backend
```

### Backend Environment

Add to your Django backend's `.env`:
```env
BOT_API_KEY=your_secure_api_key  # Same key as bot uses
TELEGRAM_ADMIN_API_KEY=admin_key_for_manual_admin_actions
```

### Django Admin Setup

1. Run migrations: `python manage.py migrate`
2. Go to Django Admin
3. Create **Telegram Bot Settings** entry
4. Configure:
   - `main_group_id`: Your Telegram group ID (e.g., `-1001234567890`)
   - `announcement_channel_id`: Your channel ID (optional)
   - Moderation settings
   - Welcome/Rules messages

## 📡 API Endpoints

### Bot Sync Endpoints (used by bot)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/bot/settings/` | GET | Get moderation settings |
| `/api/bot/scheduled-posts/` | GET | Get pending posts |
| `/api/bot/scheduled-posts/{id}/mark-executed/` | POST | Mark post as sent |
| `/api/bot/events/` | POST | Log bot events |
| `/api/bot/banned-users/` | GET | Get banned users list |

### Admin Endpoints (for manual actions)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/user-search/` | GET | Search users |
| `/api/admin/apply-bonus/` | POST | Apply bonus to user |

## 📝 Creating Scheduled Posts

In Django Admin → **Telegram Scheduled Posts**:

1. **Post Type**: announcement, offer, bonus_code, update, promotion, tip
2. **Content**: Use Markdown, `{website}` will be replaced with site URL
3. **Image URL**: Optional image to attach
4. **Scheduling**: Leave blank for immediate, or set date/time
5. **Targeting**: Send to group, channel, or custom group IDs

### Example Post Content:
```markdown
🔥 **NEW HIGH-PAYING TASK!**

Complete this task and earn $5.00!

👉 Start now: {website}/tasks

💰 Limited time offer!
```

## 🛡 Moderation Settings

Configure in Django Admin → **Telegram Bot Settings**:

| Setting | Default | Description |
|---------|---------|-------------|
| `allow_links` | False | Allow links in group |
| `allow_forwards` | True | Allow forwarded messages |
| `max_messages_per_minute` | 5 | Spam threshold |
| `mute_duration_minutes` | 30 | Default mute time |
| `auto_delete_links` | True | Auto-delete link messages |

## 🤖 Bot Commands

### User Commands
```
/start     - Main menu
/login     - Login to account
/register  - Create account
/balance   - Check balance
/stats     - View statistics
/referral  - Get referral link
/leaderboard - Top earners
/support   - Create support ticket
/faq       - FAQ menu
/rules     - Group rules (in groups)
```

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DJANGO ADMIN                          │
│  • Telegram Bot Settings (moderation config)            │
│  • Telegram Scheduled Posts (announcements)             │
│  • Telegram Banned Users (group bans)                   │
│  • Telegram Bot Events (logs)                           │
└────────────────────────┬────────────────────────────────┘
                         │ API
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   TELEGRAM BOT                           │
│  Polls every 60s for:                                   │
│  • Scheduled posts to send                              │
│  • Updated moderation settings                          │
│  • Banned users list                                    │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   ┌──────────┐                  ┌──────────────┐
   │ PRIVATE  │                  │    GROUP     │
   │  CHATS   │                  │    CHATS     │
   │          │                  │              │
   │ • Login  │                  │ • Moderation │
   │ • Stats  │                  │ • Welcomes   │
   │ • Support│                  │ • Auto-reply │
   └──────────┘                  └──────────────┘
```

## 🚀 Deployment (Render)

1. Create new **Background Worker** (not Web Service)
2. Build: `pip install -r requirements.txt`
3. Start: `python bot.py`
4. Set environment variables

## 🔒 Security

- Bot API key required for all backend calls
- Passwords deleted from chat immediately
- Admin actions logged
- Rate limiting on API calls
- Withdrawals & Faucet are **website-only**
