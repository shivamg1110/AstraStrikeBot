#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════╗
║     🐍 WINOVA PYTHON HOST - PROFESSIONAL EDITION v4.0             ║
║     Auto Error Recovery | Smart Package Installer | 24/7 Running  ║
╚═══════════════════════════════════════════════════════════════════╝
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
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ================= LOGGING SETUP =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= TELEGRAM IMPORT WITH FALLBACK =================
try:
    import telebot
    from telebot import types
except ImportError:
    os.system("pip install pyTelegramBotAPI")
    import telebot
    from telebot import types

# ================= CONFIGURATION =================
class Config:
    # Bot Settings
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8777583497:AAHICyyUsxIOIwFIUbY75BD6x6OvFoJaECs")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "8655103281"))
    CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@JaiShreeRam181")
    CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/JaiShreeRam181")
    
    # Hosting Settings
    HOSTING_DAYS = 30
    MAX_SCRIPTS_PER_USER = 1
    MAX_EXECUTION_TIME = 300  # 5 minutes max per script execution
    AUTO_RESTART_DELAY = 5  # Seconds before restarting crashed script
    
    # Paths
    BASE_DIR = "python_host"
    SCRIPTS_DIR = f"{BASE_DIR}/scripts"
    LOGS_DIR = f"{BASE_DIR}/logs"
    BACKUP_DIR = f"{BASE_DIR}/backups"
    DB_PATH = f"{BASE_DIR}/hosting.db"
    
    # Error Recovery
    MAX_RETRIES = 3
    RETRY_DELAY = 10

# Create directories
for dir_path in [Config.SCRIPTS_DIR, Config.LOGS_DIR, Config.BACKUP_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ================= DATABASE =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            join_date TEXT,
            total_scripts INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )''')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id TEXT UNIQUE,
            user_id INTEGER,
            script_name TEXT,
            script_path TEXT,
            pid INTEGER,
            status TEXT DEFAULT 'running',
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            start_time TEXT,
            expiry_time TEXT,
            last_active TEXT
        )''')
        
        self.c.execute('''CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            script_id TEXT,
            error_type TEXT,
            error_message TEXT,
            traceback TEXT,
            timestamp TEXT,
            is_fixed INTEGER DEFAULT 0
        )''')
        
        self.conn.commit()
        logger.info("Database initialized successfully")
    
    def execute(self, query, params=()):
        try:
            self.c.execute(query, params)
            self.conn.commit()
            return self.c
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
    
    def close(self):
        self.conn.close()

db = Database()

# ================= BOT INIT =================
bot = telebot.TeleBot(Config.BOT_TOKEN)
active_processes = {}

# ================= ERROR HANDLER DECORATOR =================
def handle_errors(func):
    """Decorator to handle errors in bot commands"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error in {func.__name__}: {error_trace}")
            
            # Get message object
            message = args[0] if args else None
            if message and hasattr(message, 'chat'):
                try:
                    bot.reply_to(message, f"⚠️ *An error occurred*\n\n```\n{str(e)[:200]}\n```\nPlease try again or contact @admin.", parse_mode="Markdown")
                except:
                    pass
    return wrapper

# ================= PACKAGE MANAGEMENT =================
class PackageManager:
    @staticmethod
    def detect_imports(code):
        """Smart import detection"""
        imports = set()
        patterns = [
            r'^import\s+(\w+)',
            r'^from\s+(\w+)\s+import',
            r'^from\s+(\w+)\.',
        ]
        
        builtins = {'os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random', 
                   'string', 'collections', 'itertools', 'functools', 'typing', 
                   'sqlite3', 'subprocess', 'threading', 'socket', 'ssl', 'hashlib',
                   'base64', 'codecs', 'pickle', 'copy', 'glob', 'argparse', 'logging'}
        
        for line in code.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                continue
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    module = match.group(1).split('.')[0]
                    if module not in builtins:
                        imports.add(module)
        
        return list(imports)
    
    @staticmethod
    def install_package(package):
        """Install a single package with retry"""
        for attempt in range(Config.MAX_RETRIES):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet", package],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    return True, f"✅ {package}"
                else:
                    # Try without version
                    base_pkg = package.split('=')[0]
                    result2 = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--quiet", base_pkg],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result2.returncode == 0:
                        return True, f"✅ {package}"
            except Exception as e:
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                return False, f"❌ {package}: {str(e)[:30]}"
        return False, f"❌ {package}"
    
    @staticmethod
    def install_requirements(script_path, chat_id=None):
        """Auto detect and install all requirements"""
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            packages = PackageManager.detect_imports(code)
            
            if not packages:
                return "✅ No external packages needed"
            
            installed = []
            failed = []
            
            for package in packages:
                success, msg = PackageManager.install_package(package)
                if success:
                    installed.append(msg)
                else:
                    failed.append(msg)
            
            result = "📦 *Package Installation Results*\n\n"
            if installed:
                result += "✅ *Installed:*\n" + "\n".join(installed[:10])
            if failed:
                result += "\n\n⚠️ *Failed:*\n" + "\n".join(failed[:5])
            
            return result
            
        except Exception as e:
            return f"❌ Package detection error: {str(e)[:100]}"

# ================= SCRIPT EXECUTION =================
class ScriptRunner:
    @staticmethod
    def run_script(user_id, script_path, script_id):
        """Run script with auto-restart and error recovery"""
        log_path = f"{Config.LOGS_DIR}/{user_id}.log"
        
        with open(log_path, 'w', encoding='utf-8') as log:
            log.write(f"╔════════════════════════════════════════╗\n")
            log.write(f"║ 🐍 SCRIPT STARTED at {datetime.now()}  ║\n")
            log.write(f"║ Script ID: {script_id}                  ║\n")
            log.write(f"╚════════════════════════════════════════╝\n\n")
        
        error_count = 0
        
        while True:
            try:
                process = subprocess.Popen(
                    [sys.executable, "-u", script_path],
                    stdout=open(log_path, 'a', encoding='utf-8'),
                    stderr=open(log_path, 'a', encoding='utf-8'),
                    text=True
                )
                
                active_processes[user_id] = {
                    'pid': process.pid,
                    'script_id': script_id,
                    'process': process,
                    'start_time': datetime.now()
                }
                
                db.execute("UPDATE scripts SET pid=?, last_active=? WHERE script_id=?", 
                          (process.pid, datetime.now().isoformat(), script_id))
                
                # Wait for process
                while True:
                    time.sleep(10)
                    
                    if process.poll() is not None:
                        error_count += 1
                        with open(log_path, 'a', encoding='utf-8') as log:
                            log.write(f"\n⚠️ Script crashed at {datetime.now()}\n")
                            log.write(f"Restarting in {Config.AUTO_RESTART_DELAY} seconds...\n")
                        
                        # Log error to database
                        db.execute("INSERT INTO errors (user_id, script_id, error_type, error_message, timestamp) VALUES (?, ?, ?, ?, ?)",
                                  (user_id, script_id, 'CRASH', f'Process exited with code {process.returncode}', datetime.now().isoformat()))
                        
                        time.sleep(Config.AUTO_RESTART_DELAY)
                        break
                    
                    # Check expiry
                    result = db.execute("SELECT expiry_time FROM scripts WHERE script_id=?", (script_id,))
                    if result:
                        row = result.fetchone()
                        if row and datetime.fromisoformat(row[0]) < datetime.now():
                            ScriptRunner.stop_script(process.pid)
                            db.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
                            if user_id in active_processes:
                                del active_processes[user_id]
                            return
                
            except Exception as e:
                error_count += 1
                logger.error(f"Script runner error: {e}")
                db.execute("INSERT INTO errors (user_id, script_id, error_type, error_message, timestamp) VALUES (?, ?, ?, ?, ?)",
                          (user_id, script_id, 'RUNNER_ERROR', str(e)[:200], datetime.now().isoformat()))
                time.sleep(Config.AUTO_RESTART_DELAY)
    
    @staticmethod
    def stop_script(pid):
        """Stop a running script"""
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            os.kill(pid, signal.SIGKILL)
            return True
        except:
            return False

# ================= BOT COMMANDS =================
@bot.message_handler(commands=['start'])
@handle_errors
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    full_name = message.from_user.full_name
    
    # Register user
    result = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not result.fetchone():
        db.execute("INSERT INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)",
                  (user_id, username, full_name, datetime.now().isoformat()))
        logger.info(f"New user registered: {user_id} ({username})")
    
    # Check channel
    if Config.CHANNEL_USERNAME:
        try:
            member = bot.get_chat_member(Config.CHANNEL_USERNAME, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📢 Join Channel", url=Config.CHANNEL_LINK))
                markup.add(types.InlineKeyboardButton("✅ I Joined", callback_data="check_channel"))
                bot.reply_to(message, "🚫 *Please join our channel first!*", parse_mode="Markdown", reply_markup=markup)
                return
        except:
            pass
    
    # Show menu
    show_main_menu(message)

def show_main_menu(message):
    user_id = message.from_user.id
    
    result = db.execute("SELECT script_name, expiry_time FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    script = result.fetchone()
    
    if script:
        name, expiry = script
        days_left = max(0, (datetime.fromisoformat(expiry) - datetime.now()).days)
        status_text = f"🟢 *Active* | {name} | {days_left} days left"
    else:
        status_text = "⚪ *No active script*"
    
    menu_text = f"""
╔══════════════════════════════════════════════════╗
║              🐍 *WINOVA HOST v4.0*                ║
║         Professional Python Script Hosting        ║
╚══════════════════════════════════════════════════╝

📊 *Status:* {status_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 *Features:*
├ 🔍 Auto detects imports
├ 📦 Auto installs packages
├ 🔄 Auto restarts on crash
├ 📝 Error logging & recovery
├ ⏱️ {Config.HOSTING_DAYS} days free hosting
└ 🚀 24/7 running

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ *Quick Commands:*
/status - Check script status
/logs - View output logs
/stop - Stop running script
/help - Full help guide

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📎 *Send a .py or .zip file to start hosting!*
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Status", callback_data="status"),
        types.InlineKeyboardButton("📜 Logs", callback_data="logs"),
        types.InlineKeyboardButton("🛑 Stop", callback_data="stop"),
        types.InlineKeyboardButton("❓ Help", callback_data="help")
    )
    
    bot.reply_to(message, menu_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['status'])
@handle_errors
def status_cmd(message):
    user_id = message.from_user.id
    
    result = db.execute("SELECT script_name, start_time, expiry_time, error_count FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    script = result.fetchone()
    
    if script:
        name, start, expiry, error_count = script
        days_left = max(0, (datetime.fromisoformat(expiry) - datetime.now()).days)
        
        # Check if process is actually running
        result2 = db.execute("SELECT pid FROM scripts WHERE user_id=? AND status='running'", (user_id,))
        pid_row = result2.fetchone()
        is_running = False
        if pid_row and pid_row[0]:
            try:
                os.kill(pid_row[0], 0)
                is_running = True
            except:
                pass
        
        status_icon = "🟢" if is_running else "🔴"
        
        text = f"""
📊 *SCRIPT STATUS REPORT*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{status_icon} *Status:* {'Running' if is_running else 'Crashed'}
📄 *Name:* `{name}`
⏱️ *Expires:* {days_left} days left
📅 *Started:* {start[:10]}
🔄 *Auto-restarts:* {error_count}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *Commands:*
/logs - View script output
/stop - Stop this script
"""
    else:
        text = "❌ *No script running*\n\nSend a .py or .zip file to start hosting."
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['logs'])
@handle_errors
def logs_cmd(message):
    user_id = message.from_user.id
    log_path = f"{Config.LOGS_DIR}/{user_id}.log"
    
    if not os.path.exists(log_path):
        bot.reply_to(message, "❌ *No logs found!*\n\nUpload a script first.", parse_mode="Markdown")
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content.strip():
        bot.reply_to(message, "📝 *Log file is empty*\n\nYour script hasn't produced any output yet.", parse_mode="Markdown")
        return
    
    # Get last 3000 characters
    content = content[-3000:]
    
    # Split if too long
    chunks = [content[i:i+3500] for i in range(0, len(content), 3500)]
    
    for i, chunk in enumerate(chunks):
        bot.reply_to(message, f"📝 *SCRIPT OUTPUT* (Part {i+1}/{len(chunks)})\n```\n{chunk}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
@handle_errors
def stop_cmd(message):
    user_id = message.from_user.id
    
    result = db.execute("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    script = result.fetchone()
    
    if not script:
        bot.reply_to(message, "❌ *No script running!*", parse_mode="Markdown")
        return
    
    script_id, pid = script
    
    if pid and ScriptRunner.stop_script(pid):
        db.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
        if user_id in active_processes:
            del active_processes[user_id]
        bot.reply_to(message, "✅ *Script stopped successfully!*", parse_mode="Markdown")
        logger.info(f"User {user_id} stopped script {script_id}")
    else:
        bot.reply_to(message, "⚠️ *Script already stopped or not responding*", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
@handle_errors
def help_cmd(message):
    text = """
❓ *WINOVA HOST HELP GUIDE*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *HOW TO HOST A SCRIPT:*

*Method 1 - Single File:*
1. Send a `.py` file
2. Bot auto-detects imports
3. Installs required packages
4. Script runs 24/7

*Method 2 - Full Project:*
1. Zip your project folder
2. Include `requirements.txt`
3. Send the `.zip` file
4. Bot extracts and runs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *COMMANDS:*

/start - Main menu
/status - Check script status
/logs - View output logs
/stop - Stop running script
/help - Show this guide

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *HOSTING LIMITS:*

├ 30 Days Free Hosting
├ 1 Script per user
├ Auto-restart on crash
└ Error logging & recovery

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 *TROUBLESHOOTING:*

1. Script not working? Use /logs to see errors
2. Missing package? Bot auto-installs
3. Script crashed? Auto-restarts in 5 seconds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *NEED HELP?* Contact @WinovaAdmin
"""
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
@handle_errors
def admin_cmd(message):
    if message.from_user.id != Config.ADMIN_ID:
        bot.reply_to(message, "⛔ *Admin access required*", parse_mode="Markdown")
        return
    
    result = db.execute("SELECT COUNT(*) FROM users")
    total_users = result.fetchone()[0]
    
    result = db.execute("SELECT COUNT(*) FROM scripts WHERE status='running'")
    active_scripts = result.fetchone()[0]
    
    result = db.execute("SELECT COUNT(*) FROM errors WHERE is_fixed=0")
    pending_errors = result.fetchone()[0]
    
    text = f"""
👑 *ADMIN DASHBOARD*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *STATISTICS:*

├ 👥 Total Users: {total_users}
├ 📜 Active Scripts: {active_scripts}
├ ⚠️ Pending Errors: {pending_errors}
└ ⏱️ Hosting Days: {Config.HOSTING_DAYS}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *ADMIN COMMANDS:*

/broadcast <msg> - Send to all users
/reset <user_id> - Reset user data
/stats - Server statistics
/cleanup - Clean expired scripts
"""
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
@handle_errors
def broadcast_cmd(message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    msg = message.text.replace('/broadcast', '', 1).strip()
    if not msg:
        bot.reply_to(message, "Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return
    
    result = db.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = result.fetchall()
    
    success = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 *ANNOUNCEMENT*\n\n{msg}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except:
            pass
    
    bot.reply_to(message, f"✅ Broadcast sent to {success} users")

# ================= FILE HANDLER =================
@bot.message_handler(content_types=['document'])
@handle_errors
def handle_file(message):
    user_id = message.from_user.id
    
    # Check channel
    if Config.CHANNEL_USERNAME:
        try:
            member = bot.get_chat_member(Config.CHANNEL_USERNAME, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                bot.reply_to(message, "🚫 *Please join our channel first!*", parse_mode="Markdown")
                return
        except:
            pass
    
    # Check existing script
    result = db.execute("SELECT expiry_time FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    existing = result.fetchone()
    if existing and datetime.fromisoformat(existing[0]) > datetime.now():
        days_left = (datetime.fromisoformat(existing[0]) - datetime.now()).days
        bot.reply_to(message, f"⚠️ *You already have a script running!*\n\nExpires in {days_left} days.\nUse /stop first.", parse_mode="Markdown")
        return
    
    file_name = message.document.file_name
    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        bot.reply_to(message, "❌ *Invalid file type!*\n\nSend `.py` or `.zip` file only.", parse_mode="Markdown")
        return
    
    status_msg = bot.reply_to(message, "📤 *Processing your request...*", parse_mode="Markdown")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        script_id = f"{user_id}_{int(time.time())}"
        script_dir = f"{Config.SCRIPTS_DIR}/{script_id}"
        os.makedirs(script_dir, exist_ok=True)
        
        script_path = None
        
        if file_name.endswith('.zip'):
            zip_path = os.path.join(script_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(downloaded)
            
            bot.edit_message_text("📦 *Extracting files...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(script_dir)
            
            # Find main python file
            for root, dirs, files in os.walk(script_dir):
                for f in files:
                    if f.endswith('.py') and f != 'requirements.txt':
                        script_path = os.path.join(root, f)
                        break
                if script_path:
                    break
            
            if not script_path:
                bot.edit_message_text("❌ *No Python file found in zip!*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                return
            
            script_name = os.path.basename(script_path)
            
            # Check for requirements.txt
            req_path = os.path.join(script_dir, "requirements.txt")
            if os.path.exists(req_path):
                bot.edit_message_text("📦 *Installing requirements...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], capture_output=True, text=True, timeout=120)
                
        else:
            script_path = os.path.join(script_dir, file_name)
            with open(script_path, 'wb') as f:
                f.write(downloaded)
            script_name = file_name
        
        # Auto install packages
        bot.edit_message_text("🔍 *Detecting and installing packages...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        install_result = PackageManager.install_requirements(script_path)
        bot.send_message(message.chat.id, install_result, parse_mode="Markdown")
        
        # Save to database
        expiry_time = (datetime.now() + timedelta(days=Config.HOSTING_DAYS)).isoformat()
        
        db.execute('''INSERT INTO scripts (script_id, user_id, script_name, script_path, start_time, expiry_time, status) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (script_id, user_id, script_name, script_path, datetime.now().isoformat(), expiry_time, 'running'))
        
        # Start script
        bot.edit_message_text("🚀 *Starting your script...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
        thread = threading.Thread(target=ScriptRunner.run_script, args=(user_id, script_path, script_id), daemon=True)
        thread.start()
        
        expiry_date = datetime.fromisoformat(expiry_time).strftime("%d/%m/%Y")
        
        success_text = f"""
✅ *SCRIPT HOSTED SUCCESSFULLY!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 *Name:* `{script_name}`
⏱️ *Expires:* {expiry_date}
🔄 *Auto-restart:* Enabled

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *Commands to manage your script:*

/status - Check status
/logs - View output
/stop - Stop script

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *Your script is now running 24/7!*
"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📊 Status", callback_data="status"),
            types.InlineKeyboardButton("📜 Logs", callback_data="logs"),
            types.InlineKeyboardButton("🛑 Stop", callback_data="stop")
        )
        
        bot.edit_message_text(success_text, message.chat.id, status_msg.message_id, parse_mode="Markdown", reply_markup=markup)
        logger.info(f"User {user_id} hosted script: {script_name}")
        
    except Exception as e:
        error_msg = str(e)[:200]
        bot.edit_message_text(f"❌ *Error:* {error_msg}", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        logger.error(f"Upload error for user {user_id}: {e}")

# ================= CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
@handle_errors
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "check_channel":
        try:
            member = bot.get_chat_member(Config.CHANNEL_USERNAME, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                bot.edit_message_text("✅ *Verification successful!*\n\nSend a .py or .zip file to start hosting.", 
                                     call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "Please join channel first!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "Error checking membership!", show_alert=True)
        return
    
    if data == "status":
        result = db.execute("SELECT script_name, expiry_time FROM scripts WHERE user_id=? AND status='running'", (user_id,))
        script = result.fetchone()
        if script:
            name, expiry = script
            days = max(0, (datetime.fromisoformat(expiry) - datetime.now()).days)
            bot.answer_callback_query(call.id, f"✅ Running: {name}\n⏱️ {days} days left", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ No script running", show_alert=True)
        return
    
    if data == "logs":
        log_path = f"{Config.LOGS_DIR}/{user_id}.log"
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()[-1000:]
            bot.answer_callback_query(call.id, "📝 Check logs below", show_alert=False)
            bot.send_message(call.message.chat.id, f"📝 *Recent Output*\n```\n{content}\n```", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "No logs yet!", show_alert=True)
        return
    
    if data == "stop":
        result = db.execute("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='running'", (user_id,))
        script = result.fetchone()
        if script:
            script_id, pid = script
            if pid and ScriptRunner.stop_script(pid):
                db.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
                bot.answer_callback_query(call.id, "✅ Script stopped!", show_alert=True)
                bot.edit_message_text("✅ *Script stopped successfully!*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "Failed to stop!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "No script running!", show_alert=True)
        return
    
    if data == "help":
        help_text = """
📌 *Quick Help*

Send .py or .zip file to host
/status - Check status
/logs - View output
/stop - Stop script

30 days free hosting!
"""
        bot.edit_message_text(help_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

# ================= CLEANUP WORKER =================
def cleanup_worker():
    """Auto cleanup expired scripts"""
    while True:
        try:
            time.sleep(3600)  # Every hour
            
            now = datetime.now().isoformat()
            result = db.execute("SELECT script_id, pid FROM scripts WHERE expiry_time < ? AND status='running'", (now,))
            expired = result.fetchall()
            
            for script_id, pid in expired:
                if pid:
                    ScriptRunner.stop_script(pid)
                db.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired scripts")
                
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")

# ================= MAIN =================
if __name__ == "__main__":
    print("=" * 60)
    print("🐍 WINOVA PYTHON HOST - PROFESSIONAL EDITION v4.0")
    print("=" * 60)
    print(f"✅ Bot Started Successfully!")
    print(f"👑 Admin ID: {Config.ADMIN_ID}")
    print(f"📢 Channel: {Config.CHANNEL_USERNAME}")
    print(f"📅 Hosting Days: {Config.HOSTING_DAYS}")
    print(f"🔄 Auto-restart: Enabled")
    print(f"📦 Auto-package Installer: Enabled")
    print("=" * 60)
    print("💡 Bot is running... Press Ctrl+C to stop")
    print("=" * 60)
    
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
        logger.error(f"Fatal error: {e}")
        db.close()
