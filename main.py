#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    🐍 WINOVA PYTHON HOST - PROFESSIONAL EDITION                ║
║                         Telegram Bot for Hosting Python Scripts                ║
║                              Version 5.0 | Enterprise Grade                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import subprocess
import sqlite3
import signal
import time
import threading
import zipfile
import shutil
import re
import json
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

# Install required package if not present
try:
    import telebot
    from telebot import types
except ImportError:
    os.system("pip install pyTelegramBotAPI -q")
    import telebot
    from telebot import types

# ================= CONFIGURATION =================
class Config:
    # Bot Configuration
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "8655103281"))
    CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@JaiShreeRam181")
    CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/JaiShreeRam181")
    SUPPORT_LINK = os.environ.get("SUPPORT_LINK", "https://t.me/WinovaAdmin")
    
    # Hosting Configuration
    HOSTING_DAYS = 30
    MAX_FILE_SIZE_MB = 100
    MAX_SCRIPTS_PER_USER = 1
    MAX_EXECUTION_TIME = 300
    
    # Paths
    BASE_DIR = "winova_host"
    SCRIPTS_DIR = f"{BASE_DIR}/scripts"
    LOGS_DIR = f"{BASE_DIR}/logs"
    DATABASE_DIR = f"{BASE_DIR}/data"
    DB_PATH = f"{DATABASE_DIR}/hosting.db"
    
    # Themes
    THEME_PRIMARY = "#00FF88"
    THEME_SECONDARY = "#0088FF"
    THEME_DANGER = "#FF4444"
    THEME_WARNING = "#FFAA00"
    
    # Bot Info
    BOT_NAME = "Winova Host"
    BOT_VERSION = "5.0"
    BOT_DEVELOPER = "@WinovaAdmin"

# Create directories
for dir_path in [Config.SCRIPTS_DIR, Config.LOGS_DIR, Config.DATABASE_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ================= DATABASE SETUP =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Users table
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            join_date TEXT,
            last_active TEXT,
            total_scripts INTEGER DEFAULT 0,
            total_downloads INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_expiry TEXT
        )''')
        
        # Scripts table
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id TEXT UNIQUE,
            user_id INTEGER,
            script_name TEXT,
            script_path TEXT,
            script_size INTEGER,
            pid INTEGER,
            status TEXT DEFAULT 'active',
            start_time TEXT,
            expiry_time TEXT,
            last_active TEXT,
            error_count INTEGER DEFAULT 0,
            restart_count INTEGER DEFAULT 0
        )''')
        
        # Activity logs
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )''')
        
        # System settings
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        self.conn.commit()
    
    def execute(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except Exception as e:
            print(f"Database error: {e}")
            return None
    
    def fetchone(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()
    
    def fetchall(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()
    
    def close(self):
        self.conn.close()

db = Database()

# ================= BOT INITIALIZATION =================
bot = telebot.TeleBot(Config.BOT_TOKEN)
active_scripts = {}

# ================= HELPER FUNCTIONS =================
def log_activity(user_id, action, details=""):
    try:
        db.execute("INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
                  (user_id, action, details[:500], datetime.now().isoformat()))
    except:
        pass

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"

def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.0f} sec"
    elif seconds < 3600:
        return f"{seconds/60:.0f} min"
    else:
        return f"{seconds/3600:.1f} hours"

def get_user_status(user_id):
    user = db.fetchone("SELECT is_premium, premium_expiry FROM users WHERE user_id=?", (user_id,))
    if not user:
        return "free"
    if user[0] == 1 and user[1] and datetime.fromisoformat(user[1]) > datetime.now():
        return "premium"
    return "free"

def can_upload(user_id):
    if user_id == Config.ADMIN_ID:
        return True, "OK"
    
    status = get_user_status(user_id)
    if status == "premium":
        return True, "OK"
    
    # Check free user limit
    script_count = db.fetchone("SELECT COUNT(*) FROM scripts WHERE user_id=? AND status='active'", (user_id,))[0]
    if script_count >= Config.MAX_SCRIPTS_PER_USER:
        return False, f"❌ *Free Limit Reached!*\n\nYou can only host {Config.MAX_SCRIPTS_PER_USER} script.\n💎 Upgrade to Premium for more scripts!"
    
    return True, "OK"

def check_channel(user_id):
    if not Config.CHANNEL_USERNAME:
        return True
    try:
        member = bot.get_chat_member(Config.CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def safe_stop_process(pid):
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        os.kill(pid, signal.SIGKILL)
        return True
    except:
        return False

def detect_and_install_packages(script_path):
    """Detect imports and install required packages"""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all imports
        import_pattern = r'^(?:from\s+(\w+)|import\s+(\w+))'
        packages = set()
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                match = re.search(import_pattern, line)
                if match:
                    pkg = match.group(1) or match.group(2)
                    pkg = pkg.split('.')[0]
                    # Skip built-in modules
                    builtins = {'os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random',
                               'string', 'collections', 'itertools', 'functools', 'typing',
                               'sqlite3', 'subprocess', 'threading', 'socket', 'hashlib',
                               'base64', 'csv', 'logging', 'pathlib', 'tempfile', 'shutil'}
                    if pkg not in builtins:
                        packages.add(pkg)
        
        if not packages:
            return "✅ No external packages needed"
        
        installed = []
        failed = []
        
        for pkg in packages:
            try:
                # Try to import
                result = subprocess.run([sys.executable, "-c", f"import {pkg}"], 
                                       capture_output=True, timeout=10)
                if result.returncode == 0:
                    installed.append(f"✅ {pkg} (already)")
                    continue
                
                # Install package
                install = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                                        capture_output=True, timeout=60)
                if install.returncode == 0:
                    installed.append(f"✅ {pkg}")
                else:
                    failed.append(f"❌ {pkg}")
            except:
                failed.append(f"❌ {pkg}")
        
        result_text = "📦 *Package Installation:*\n"
        for msg in installed[:5]:
            result_text += msg + "\n"
        if failed:
            result_text += "\n⚠️ *Failed:* " + ", ".join(failed[:3])
        
        return result_text
        
    except Exception as e:
        return f"⚠️ Package detection error: {str(e)[:50]}"

def run_script_async(user_id, script_path, script_id):
    """Run script in background with monitoring"""
    log_path = f"{Config.LOGS_DIR}/{user_id}.log"
    
    try:
        # Initialize log
        with open(log_path, 'w') as f:
            f.write(f"╔══════════════════════════════════════════════════════════╗\n")
            f.write(f"║     🐍 WINOVA HOST - SCRIPT EXECUTION LOG                  ║\n")
            f.write(f"╚══════════════════════════════════════════════════════════╝\n\n")
            f.write(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"📄 Script ID: {script_id}\n")
            f.write(f"📁 Script Path: {script_path}\n")
            f.write(f"{'='*60}\n\n")
        
        # Start process
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=open(log_path, 'a'),
            stderr=open(log_path, 'a'),
            text=True
        )
        
        active_scripts[user_id] = {
            'pid': process.pid,
            'script_id': script_id,
            'process': process
        }
        
        db.execute("UPDATE scripts SET pid=?, last_active=? WHERE script_id=?", 
                   (process.pid, datetime.now().isoformat(), script_id))
        
        # Monitoring loop
        while True:
            time.sleep(30)
            
            # Check if process is still running
            if process.poll() is not None:
                with open(log_path, 'a') as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"🔄 SCRIPT RESTARTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{'='*60}\n\n")
                
                # Restart process
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=open(log_path, 'a'),
                    stderr=open(log_path, 'a'),
                    text=True
                )
                active_scripts[user_id]['pid'] = process.pid
                active_scripts[user_id]['process'] = process
                
                # Update restart count
                db.execute("UPDATE scripts SET pid=?, restart_count=restart_count+1, last_active=? WHERE script_id=?",
                          (process.pid, datetime.now().isoformat(), script_id))
            
            # Check expiry
            result = db.fetchone("SELECT expiry_time FROM scripts WHERE script_id=?", (script_id,))
            if result and datetime.fromisoformat(result[0]) < datetime.now():
                safe_stop_process(process.pid)
                db.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
                if user_id in active_scripts:
                    del active_scripts[user_id]
                break
                
    except Exception as e:
        with open(log_path, 'a') as f:
            f.write(f"\n❌ FATAL ERROR: {str(e)}\n")

# ================= UI COMPONENTS =================
def create_welcome_message(user_id, username):
    """Create beautiful welcome message"""
    user = db.fetchone("SELECT join_date, total_scripts FROM users WHERE user_id=?", (user_id,))
    
    if user:
        join_date = datetime.fromisoformat(user[0]).strftime("%d %B %Y")
        total_scripts = user[1]
    else:
        join_date = datetime.now().strftime("%d %B %Y")
        total_scripts = 0
    
    status = get_user_status(user_id)
    
    if status == "premium":
        status_icon = "💎"
        status_text = "PREMIUM"
        status_color = "🌟"
    else:
        status_icon = "🎁"
        status_text = "FREE"
        status_color = "📀"
    
    welcome_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              🐍 *WELCOME TO WINOVA HOST* 🐍                  ║
║                                                              ║
║         Professional Python Script Hosting Service          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

👤 *USER PROFILE*
├ 🆔 ID: `{user_id}`
├ 📛 Name: `{username}`
├ 💎 Plan: {status_icon} *{status_text}*
├ 📅 Joined: `{join_date}`
└ 📊 Scripts Hosted: `{total_scripts}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ *WHAT I CAN DO FOR YOU*

│  📤 *Upload & Host* - Send me your Python scripts
│  🔄 *24/7 Running* - Your scripts run continuously
│  📦 *Auto Packages* - Dependencies installed automatically
│  🔁 *Auto Restart* - Scripts restart if they crash
│  📅 *30 Days Free* - Hosting for 30 days
│  📊 *Real-time Logs* - View output anytime

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 *QUICK START*

Simply send me a `.py` file or `.zip` project file!
I'll automatically detect and install all required packages.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 *SELECT AN OPTION BELOW*
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 UPLOAD SCRIPT", callback_data="upload"),
        types.InlineKeyboardButton("📊 DASHBOARD", callback_data="dashboard")
    )
    markup.add(
        types.InlineKeyboardButton("📜 MY SCRIPTS", callback_data="my_scripts"),
        types.InlineKeyboardButton("📥 VIEW LOGS", callback_data="view_logs")
    )
    markup.add(
        types.InlineKeyboardButton("💎 UPGRADE", callback_data="upgrade"),
        types.InlineKeyboardButton("❓ HELP", callback_data="help")
    )
    markup.add(
        types.InlineKeyboardButton("ℹ️ ABOUT", callback_data="about"),
        types.InlineKeyboardButton("🛑 STOP SCRIPT", callback_data="stop_script")
    )
    
    return welcome_text, markup

def create_dashboard(user_id):
    """Create user dashboard"""
    # Get user stats
    user = db.fetchone("SELECT username, join_date, total_scripts, total_downloads FROM users WHERE user_id=?", (user_id,))
    if not user:
        return "⚠️ User not found", None
    
    username, join_date, total_scripts, total_downloads = user
    
    # Get active script
    script = db.fetchone("SELECT script_name, start_time, expiry_time, status, restart_count FROM scripts WHERE user_id=? AND status='active'", (user_id,))
    
    # Calculate days left
    if script:
        expiry = datetime.fromisoformat(script[2])
        days_left = max(0, (expiry - datetime.now()).days)
        script_name = script[0]
        start_time = datetime.fromisoformat(script[1]).strftime("%d/%m/%Y")
        restart_count = script[4]
    else:
        days_left = 0
        script_name = "No active script"
        start_time = "N/A"
        restart_count = 0
    
    status = get_user_status(user_id)
    
    # Create progress bar
    if status == "premium":
        used_percent = (total_scripts / 100) * 100 if total_scripts > 0 else 0
        bar_length = 20
        filled = int(used_percent / 5)
        bar = "█" * filled + "░" * (bar_length - filled)
        limit_text = "100 scripts"
    else:
        used_percent = (total_scripts / Config.MAX_SCRIPTS_PER_USER) * 100
        bar_length = 20
        filled = int(used_percent / 5)
        bar = "█" * filled + "░" * (bar_length - filled)
        limit_text = f"{Config.MAX_SCRIPTS_PER_USER} script"
    
    dashboard_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                      📊 *USER DASHBOARD*                      ║
╚══════════════════════════════════════════════════════════════╝

👤 *ACCOUNT INFORMATION*
├ 🆔 User ID: `{user_id}`
├ 📛 Username: `{username}`
├ 💎 Plan: `{status.upper()}`
├ 📅 Member Since: `{join_date[:10]}`
└ 📊 Total Scripts: `{total_scripts}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 *STORAGE USAGE*
├ Limit: `{limit_text}`
├ Used: `{total_scripts} scripts`
├ {bar} `{used_percent:.1f}%`
└ 📥 Total Downloads: `{total_downloads}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🐍 *ACTIVE SCRIPT*
├ 📄 Name: `{script_name}`
├ 📅 Started: `{start_time}`
├ ⏱️ Expires: `{days_left} days left`
├ 🔄 Restarts: `{restart_count}`
└ 📊 Status: `🟢 Running` if script else `⚪ None`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *TIPS*
• Use /logs to see script output
• Use /stop to stop your script
• Upload new script to replace old one
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 UPLOAD", callback_data="upload"),
        types.InlineKeyboardButton("📜 LOGS", callback_data="view_logs")
    )
    markup.add(
        types.InlineKeyboardButton("🛑 STOP", callback_data="stop_script"),
        types.InlineKeyboardButton("💎 UPGRADE", callback_data="upgrade")
    )
    markup.add(types.InlineKeyboardButton("🔙 BACK", callback_data="back_to_menu"))
    
    return dashboard_text, markup

def create_scripts_list(user_id):
    """List all user scripts"""
    scripts = db.fetchall("SELECT script_id, script_name, status, start_time, expiry_time FROM scripts WHERE user_id=? ORDER BY id DESC", (user_id,))
    
    if not scripts:
        return "📁 *No scripts found*\n\nSend a `.py` file to get started!", None
    
    text = "📁 *YOUR SCRIPTS*\n\n"
    for script_id, name, status, start, expiry in scripts[:5]:
        status_icon = "🟢" if status == "active" else "🔴"
        start_date = datetime.fromisoformat(start).strftime("%d/%m/%y")
        text += f"{status_icon} `{script_id[:12]}...`\n"
        text += f"   📄 {name[:30]}\n"
        text += f"   📅 {start_date}\n\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 BACK", callback_data="back_to_menu"))
    
    return text, markup

# ================= BOT COMMANDS =================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    full_name = message.from_user.full_name
    
    # Register user
    user = db.fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not user:
        db.execute("INSERT INTO users (user_id, username, full_name, join_date, last_active) VALUES (?, ?, ?, ?, ?)",
                   (user_id, username, full_name, datetime.now().isoformat(), datetime.now().isoformat()))
        log_activity(user_id, "registered", f"New user: {username}")
    
    # Check channel
    if not check_channel(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 JOIN CHANNEL", url=Config.CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ CHECK", callback_data="check_channel"))
        bot.reply_to(message, "🚫 *Access Denied!*\n\nPlease join our channel to use this bot.", 
                    parse_mode="Markdown", reply_markup=markup)
        return
    
    welcome_text, markup = create_welcome_message(user_id, username)
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['menu'])
def menu_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    welcome_text, markup = create_welcome_message(user_id, username)
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['dashboard'])
def dashboard_command(message):
    user_id = message.from_user.id
    dashboard_text, markup = create_dashboard(user_id)
    bot.reply_to(message, dashboard_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['logs'])
def logs_command(message):
    user_id = message.from_user.id
    log_path = f"{Config.LOGS_DIR}/{user_id}.log"
    
    if not os.path.exists(log_path):
        bot.reply_to(message, "📝 *No logs found!*\n\nUpload a script first.", parse_mode="Markdown")
        return
    
    try:
        with open(log_path, 'r') as f:
            content = f.read()
        
        if not content:
            bot.reply_to(message, "📝 *Log file is empty*", parse_mode="Markdown")
            return
        
        # Get last 3000 characters
        content = content[-3000:]
        if len(content) > 4000:
            content = content[:4000] + "\n\n... (truncated)"
        
        bot.reply_to(message, f"📝 *SCRIPT OUTPUT LOGS*\n```\n{content}\n```", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error reading logs: {str(e)[:100]}", parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.from_user.id
    
    script = db.fetchone("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='active'", (user_id,))
    if not script:
        bot.reply_to(message, "❌ *No active script found!*", parse_mode="Markdown")
        return
    
    script_id, pid = script
    
    if pid and safe_stop_process(pid):
        db.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
        if user_id in active_scripts:
            del active_scripts[user_id]
        bot.reply_to(message, "✅ *Script stopped successfully!*", parse_mode="Markdown")
        log_activity(user_id, "stopped_script", f"Script ID: {script_id}")
    else:
        bot.reply_to(message, "❌ *Failed to stop script!*", parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = message.from_user.id
    
    script = db.fetchone("SELECT script_name, start_time, expiry_time, status FROM scripts WHERE user_id=? AND status='active'", (user_id,))
    
    if script:
        name, start, expiry, status = script
        days_left = max(0, (datetime.fromisoformat(expiry) - datetime.now()).days)
        
        text = f"""
📊 *SCRIPT STATUS*

🟢 *Status:* Active
📄 *Name:* `{name}`
⏱️ *Expires:* `{days_left} days left`
📅 *Started:* `{start[:10]}`

💡 Use /logs to see output
"""
    else:
        text = "❌ *No active script!*\n\nSend a `.py` file to start hosting."
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    text = """
╔══════════════════════════════════════════════════════════════╗
║                      ❓ *HELP CENTER*                         ║
╚══════════════════════════════════════════════════════════════╝

📌 *HOW TO HOST A SCRIPT*

1️⃣ *Send a Python file*
   Just send me any `.py` file

2️⃣ *Send a project zip*
   Zip your project folder and send it

3️⃣ *Auto installation*
   I'll detect and install all required packages

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ *COMMANDS LIST*

/start - Show main menu
/menu - Show main menu  
/dashboard - View your dashboard
/logs - View script output
/status - Check script status
/stop - Stop your script
/help - Show this help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *HOSTING LIMITS*

FREE PLAN:
├ 📁 {Config.MAX_SCRIPTS_PER_USER} script
├ 📅 {Config.HOSTING_DAYS} days hosting
├ 📏 Up to {Config.MAX_FILE_SIZE_MB}MB files
└ 🔄 Auto restart on crash

PREMIUM PLAN:
├ 📁 100 scripts
├ 📅 Unlimited days
├ 📏 Up to 500MB files
└ 🚀 Priority support

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *NEED HELP?*
Contact: {Config.SUPPORT_LINK}
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 BACK TO MENU", callback_data="back_to_menu"))
    markup.add(types.InlineKeyboardButton("💎 UPGRADE", callback_data="upgrade"))
    
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

# ================= FILE UPLOAD HANDLER =================
@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    user_id = message.from_user.id
    
    # Check channel
    if not check_channel(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 JOIN CHANNEL", url=Config.CHANNEL_LINK))
        bot.reply_to(message, "🚫 *Please join our channel first!*", parse_mode="Markdown", reply_markup=markup)
        return
    
    # Check if can upload
    can, msg = can_upload(user_id)
    if not can:
        bot.reply_to(message, msg, parse_mode="Markdown")
        return
    
    file_name = message.document.file_name
    
    # Check file type
    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        bot.reply_to(message, "❌ *Invalid file type!*\n\nPlease send `.py` or `.zip` file only.", parse_mode="Markdown")
        return
    
    # Check file size
    if message.document.file_size > Config.MAX_FILE_SIZE_MB * 1024 * 1024:
        bot.reply_to(message, f"❌ *File too large!*\n\nMax size: {Config.MAX_FILE_SIZE_MB}MB", parse_mode="Markdown")
        return
    
    # Stop existing script if any
    existing = db.fetchone("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='active'", (user_id,))
    if existing:
        script_id, pid = existing
        if pid:
            safe_stop_process(pid)
        db.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
        if user_id in active_scripts:
            del active_scripts[user_id]
    
    status_msg = bot.reply_to(message, "📤 *Processing your file...*", parse_mode="Markdown")
    
    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # Create unique ID
        script_hash = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:16]
        script_id = f"{user_id}_{script_hash}"
        script_dir = f"{Config.SCRIPTS_DIR}/{script_id}"
        os.makedirs(script_dir, exist_ok=True)
        
        script_path = None
        script_name = file_name
        
        if file_name.endswith('.zip'):
            # Extract zip
            bot.edit_message_text("📦 *Extracting zip file...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
            
            zip_path = os.path.join(script_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(downloaded)
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(script_dir)
            
            # Find main python file
            for root, dirs, files in os.walk(script_dir):
                for f in files:
                    if f.endswith('.py') and f not in ['requirements.txt', 'setup.py']:
                        script_path = os.path.join(root, f)
                        break
                if script_path:
                    break
            
            if not script_path:
                bot.edit_message_text("❌ *No Python file found in zip!*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                return
            
            script_name = os.path.basename(script_path)
            
            # Install requirements if exists
            req_path = os.path.join(script_dir, "requirements.txt")
            if os.path.exists(req_path):
                bot.edit_message_text("📦 *Installing requirements...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], 
                             capture_output=True, timeout=120)
        
        else:
            # Single py file
            script_path = os.path.join(script_dir, file_name)
            with open(script_path, 'wb') as f:
                f.write(downloaded)
        
        # Detect and install packages
        bot.edit_message_text("🔍 *Detecting and installing packages...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        install_result = detect_and_install_packages(script_path)
        bot.send_message(message.chat.id, install_result, parse_mode="Markdown")
        
        # Save to database
        expiry_time = (datetime.now() + timedelta(days=Config.HOSTING_DAYS)).isoformat()
        
        db.execute("""INSERT INTO scripts 
                     (script_id, user_id, script_name, script_path, script_size, start_time, expiry_time, status) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (script_id, user_id, script_name, script_path, message.document.file_size,
                    datetime.now().isoformat(), expiry_time, 'active'))
        
        db.execute("UPDATE users SET total_scripts = total_scripts + 1, last_active=? WHERE user_id=?", 
                   (datetime.now().isoformat(), user_id))
        
        # Start script in background
        bot.edit_message_text("🚀 *Starting your script...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
        thread = threading.Thread(target=run_script_async, args=(user_id, script_path, script_id), daemon=True)
        thread.start()
        
        # Success message
        success_text = f"""
✅ *SCRIPT HOSTED SUCCESSFULLY!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 *Script:* `{script_name}`
📦 *Size:* {message.document.file_size/1024:.1f} KB
🔑 *ID:* `{script_id[:12]}...`
⏱️ *Expires:* {datetime.fromisoformat(expiry_time).strftime('%d/%m/%Y')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 *What next?*
• /logs - View script output
• /status - Check script status  
• /stop - Stop your script
• /dashboard - View your dashboard

💡 *Your script is now running 24/7!*
"""
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📊 DASHBOARD", callback_data="dashboard"),
            types.InlineKeyboardButton("📜 VIEW LOGS", callback_data="view_logs")
        )
        markup.add(
            types.InlineKeyboardButton("🛑 STOP", callback_data="stop_script"),
            types.InlineKeyboardButton("🏠 MENU", callback_data="back_to_menu")
        )
        
        bot.edit_message_text(success_text, message.chat.id, status_msg.message_id, parse_mode="Markdown", reply_markup=markup)
        log_activity(user_id, "uploaded_script", f"Script: {script_name}")
        
    except Exception as e:
        bot.edit_message_text(f"❌ *Upload failed!*\n\nError: {str(e)[:100]}", 
                             message.chat.id, status_msg.message_id, parse_mode="Markdown")

# ================= CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "check_channel":
        if check_channel(user_id):
            bot.edit_message_text("✅ *Verification successful!* Use /start to continue.", 
                                 call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "Please join channel first!", show_alert=True)
        return
    
    if data == "back_to_menu":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        username = call.from_user.username or call.from_user.first_name
        welcome_text, markup = create_welcome_message(user_id, username)
        bot.send_message(call.message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)
        return
    
    if data == "upload":
        bot.edit_message_text("📎 *Send me your Python (.py) file* or `.zip` project file!\n\nI'll automatically detect and install all required packages.",
                             call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return
    
    if data == "dashboard":
        dashboard_text, markup = create_dashboard(user_id)
        bot.edit_message_text(dashboard_text, call.message.chat.id, call.message.message_id, 
                             parse_mode="Markdown", reply_markup=markup)
        return
    
    if data == "my_scripts":
        scripts_text, markup = create_scripts_list(user_id)
        bot.edit_message_text(scripts_text, call.message.chat.id, call.message.message_id,
                             parse_mode="Markdown", reply_markup=markup)
        return
    
    if data == "view_logs":
        log_path = f"{Config.LOGS_DIR}/{user_id}.log"
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                content = f.read()[-500:]
            bot.answer_callback_query(call.id, "Logs sent below!", show_alert=False)
            bot.send_message(call.message.chat.id, f"📝 *SCRIPT LOGS*\n```\n{content}\n```", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "No logs found! Upload a script first.", show_alert=True)
        return
    
    if data == "stop_script":
        script = db.fetchone("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='active'", (user_id,))
        if script:
            script_id, pid = script
            if pid and safe_stop_process(pid):
                db.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
                if user_id in active_scripts:
                    del active_scripts[user_id]
                bot.answer_callback_query(call.id, "✅ Script stopped!", show_alert=True)
                bot.edit_message_text("✅ *Script stopped successfully!*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "Failed to stop!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "No active script!", show_alert=True)
        return
    
    if data == "upgrade":
        text = """
💎 *UPGRADE TO PREMIUM*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ *PREMIUM BENEFITS:*

├ 📁 *100 Scripts* - Host up to 100 scripts
├ 📅 *Unlimited Days* - No expiry
├ 📏 *500MB Files* - Larger file support
├ 🚀 *Priority Support* - Fast response
├ 🔗 *Custom Domains* - Brand your links
└ 📊 *Advanced Analytics* - Detailed stats

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 *PRICE:* ₹99/month or ₹999/year

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💳 *PAYMENT METHODS:*
• UPI (Google Pay, PhonePe, Paytm)
• Crypto (USDT, BTC)
• Bank Transfer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📞 *CONTACT:* {Config.SUPPORT_LINK}

Click below to contact admin and upgrade!
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 CONTACT ADMIN", url=Config.SUPPORT_LINK))
        markup.add(types.InlineKeyboardButton("🔙 BACK", callback_data="back_to_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return
    
    if data == "help":
        help_text = """
❓ *QUICK HELP*

📌 *Commands:*
/start - Main menu
/dashboard - View stats
/logs - See output
/status - Check status
/stop - Stop script

💡 *Need more help?* Contact support!
"""
        bot.answer_callback_query(call.id, "Help sent!", show_alert=False)
        bot.send_message(call.message.chat.id, help_text, parse_mode="Markdown")
        return
    
    if data == "about":
        text = f"""
ℹ️ *ABOUT WINOVA HOST*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *Version:* {Config.BOT_VERSION}
👨‍💻 *Developer:* {Config.BOT_DEVELOPER}
📅 *Release:* 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ *FEATURES:*

├ 🔒 Secure Sandbox Environment
├ 🐍 Full Python 3 Support
├ 📤 Real-time Output Streaming
├ 📦 Auto Package Installation
├ 🔄 Auto Restart on Crash
├ 📊 Detailed Analytics
└ 💎 Premium Plans Available

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📢 *Join our channel:* {Config.CHANNEL_USERNAME}
💬 *Support:* {Config.SUPPORT_LINK}

💎 *Powered by Winova Technologies*
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 JOIN CHANNEL", url=Config.CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("🔙 BACK", callback_data="back_to_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

# ================= ADMIN COMMANDS =================
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    # Get stats
    total_users = db.fetchone("SELECT COUNT(*) FROM users")[0]
    active_scripts = db.fetchone("SELECT COUNT(*) FROM scripts WHERE status='active'")[0]
    total_scripts = db.fetchone("SELECT COUNT(*) FROM scripts")[0]
    
    # Calculate storage
    total_size = 0
    for path in Path(Config.SCRIPTS_DIR).rglob("*.py"):
        total_size += path.stat().st_size
    
    text = f"""
👑 *ADMIN DASHBOARD*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *STATISTICS*

├ 👥 Users: {total_users}
├ 📜 Active Scripts: {active_scripts}
├ 📁 Total Scripts: {total_scripts}
└ 💾 Storage: {total_size/1024/1024:.2f} MB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ *COMMANDS*

/users - List all users
/reset ID - Reset user
/broadcast - Send message
/cleanup - Clean expired
/status - System status
"""
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['users'])
def users_command(message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    users = db.fetchall("SELECT user_id, username, join_date, total_scripts FROM users ORDER BY join_date DESC LIMIT 20")
    
    text = "👥 *RECENT USERS*\n\n"
    for uid, uname, joined, scripts in users:
        text += f"👤 `{uid}` - {uname[:15]}\n   📅 {joined[:10]} | 📜 {scripts} scripts\n\n"
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['reset'])
def reset_command(message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: `/reset user_id`", parse_mode="Markdown")
            return
        
        target_id = int(parts[1])
        
        # Stop script
        script = db.fetchone("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='active'", (target_id,))
        if script:
            script_id, pid = script
            if pid:
                safe_stop_process(pid)
            db.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
        
        # Delete user data
        db.execute("DELETE FROM scripts WHERE user_id=?", (target_id,))
        db.execute("DELETE FROM users WHERE user_id=?", (target_id,))
        
        # Delete files
        log_path = f"{Config.LOGS_DIR}/{target_id}.log"
        if os.path.exists(log_path):
            os.remove(log_path)
        
        for folder in os.listdir(Config.SCRIPTS_DIR):
            if folder.startswith(str(target_id)):
                shutil.rmtree(os.path.join(Config.SCRIPTS_DIR, folder), ignore_errors=True)
        
        bot.reply_to(message, f"✅ *User {target_id} reset successfully!*", parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}", parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    msg = message.text.replace('/broadcast', '', 1).strip()
    if not msg:
        bot.reply_to(message, "Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return
    
    users = db.fetchall("SELECT user_id FROM users")
    success = 0
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 *ANNOUNCEMENT*\n\n{msg}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except:
            pass
    
    bot.reply_to(message, f"✅ *Broadcast sent to {success} users!*", parse_mode="Markdown")

@bot.message_handler(commands=['cleanup'])
def cleanup_command(message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    now = datetime.now().isoformat()
    expired = db.fetchall("SELECT script_id, pid FROM scripts WHERE expiry_time < ? AND status='active'", (now,))
    
    count = 0
    for script_id, pid in expired:
        if pid:
            safe_stop_process(pid)
        db.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
        count += 1
    
    bot.reply_to(message, f"✅ *Cleaned {count} expired scripts!*", parse_mode="Markdown")

# ================= CLEANUP THREAD =================
def cleanup_worker():
    while True:
        time.sleep(3600)  # Every hour
        try:
            now = datetime.now().isoformat()
            expired = db.fetchall("SELECT script_id, pid FROM scripts WHERE expiry_time < ? AND status='active'", (now,))
            for script_id, pid in expired:
                if pid:
                    safe_stop_process(pid)
                db.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
        except Exception as e:
            print(f"Cleanup error: {e}")

# ================= MAIN =================
if __name__ == "__main__":
    print("=" * 70)
    print("🐍 WINOVA PYTHON HOST - PROFESSIONAL EDITION v5.0")
    print("=" * 70)
    print(f"🤖 Bot: @{bot.get_me().username}")
    print(f"👑 Admin ID: {Config.ADMIN_ID}")
    print(f"📢 Channel: {Config.CHANNEL_USERNAME}")
    print(f"📅 Hosting Days: {Config.HOSTING_DAYS}")
    print(f"📊 Max Scripts: {Config.MAX_SCRIPTS_PER_USER}")
    print("=" * 70)
    print("✅ BOT IS RUNNING...")
    print("💡 Features: Auto Packages | Dashboard | Error Resistant")
    print("=" * 70)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    
    # Start bot
    try:
        bot.infinity_polling(timeout=60)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped!")
        db.close()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
