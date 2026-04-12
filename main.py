#!/usr/bin/env python3
"""
WINOVA PYTHON HOST - Telegram Bot for Hosting Python Scripts
Deploy on Render.com
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
from datetime import datetime, timedelta

try:
    import telebot
    from telebot import types
except ImportError:
    os.system("pip install pyTelegramBotAPI")
    import telebot
    from telebot import types

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8655103281"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@JaiShreeRam181")
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/JaiShreeRam181")

HOSTING_DAYS = 30
BASE_DIR = "python_host"
SCRIPTS_DIR = f"{BASE_DIR}/scripts"
LOGS_DIR = f"{BASE_DIR}/logs"
DB_PATH = f"{BASE_DIR}/hosting.db"

os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# ================= DATABASE =================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("DROP TABLE IF EXISTS users")
c.execute("DROP TABLE IF EXISTS scripts")

c.execute('''CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    join_date TEXT
)''')

c.execute('''CREATE TABLE scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id TEXT UNIQUE,
    user_id INTEGER,
    script_name TEXT,
    script_path TEXT,
    pid INTEGER,
    status TEXT DEFAULT 'running',
    start_time TEXT,
    expiry_time TEXT
)''')

conn.commit()

bot = telebot.TeleBot(BOT_TOKEN)
active_processes = {}

# ================= PACKAGE DETECTION =================
def detect_imports_from_code(code):
    """Detect all imports from Python code"""
    imports = set()
    
    patterns = [
        r'^import\s+(\w+)',
        r'^from\s+(\w+)\s+import',
    ]
    
    for line in code.split('\n'):
        line = line.strip()
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                module = match.group(1).split('.')[0]
                if module not in ['os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random', 'string', 'collections', 'itertools', 'functools', 'typing']:
                    imports.add(module)
    
    return list(imports)

def auto_install_packages(script_path, chat_id):
    """Auto detect and install required packages"""
    try:
        with open(script_path, 'r') as f:
            code = f.read()
        
        packages = detect_imports_from_code(code)
        
        if not packages:
            return "✅ No external packages needed"
        
        installed = []
        failed = []
        
        for package in packages:
            try:
                check = subprocess.run(
                    [sys.executable, "-c", f"import {package}"],
                    capture_output=True,
                    text=True
                )
                
                if check.returncode == 0:
                    installed.append(f"✅ {package} (already installed)")
                    continue
                
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    installed.append(f"✅ {package}")
                else:
                    failed.append(f"❌ {package}")
                    
            except subprocess.TimeoutExpired:
                failed.append(f"⏰ {package}")
            except:
                failed.append(f"❌ {package}")
        
        result_text = "📦 *Packages Installed:*\n"
        for msg in installed[:10]:
            result_text += msg + "\n"
        if failed:
            result_text += "\n⚠️ *Failed:*\n" + "\n".join(failed[:5])
        
        return result_text
        
    except Exception as e:
        return f"❌ Error: {str(e)[:100]}"

def install_requirements_file(script_dir):
    """Install from requirements.txt"""
    req_path = os.path.join(script_dir, "requirements.txt")
    
    if not os.path.exists(req_path):
        return None
    
    try:
        with open(req_path, 'r') as f:
            reqs = f.read().strip()
        
        if not reqs:
            return None
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            return f"📦 *Requirements installed:*\n```\n{reqs[:200]}\n```"
        else:
            return f"⚠️ *Requirements error:*\n{result.stderr[:100]}"
            
    except subprocess.TimeoutExpired:
        return "⏰ Timeout"
    except Exception as e:
        return f"❌ Error: {str(e)[:50]}"

# ================= FUNCTIONS =================
def check_channel(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def stop_process(pid):
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        os.kill(pid, signal.SIGKILL)
        return True
    except:
        return False

def extract_zip(zip_path, extract_to):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_to)
        return True, "OK"
    except Exception as e:
        return False, str(e)

def find_main_py(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith('.py') and f not in ['requirements.txt', 'setup.py']:
                return os.path.join(root, f)
    return None

def run_script(user_id, script_path, script_id):
    log_path = f"{LOGS_DIR}/{user_id}.log"
    
    with open(log_path, 'w') as log:
        log.write(f"=== SCRIPT STARTED at {datetime.now()} ===\n")
        log.write(f"Script: {script_path}\n")
        log.write("=" * 50 + "\n\n")
    
    process = subprocess.Popen(
        [sys.executable, script_path],
        stdout=open(log_path, 'a'),
        stderr=open(log_path, 'a'),
        text=True
    )
    
    active_processes[user_id] = {
        'pid': process.pid,
        'script_id': script_id,
        'process': process
    }
    
    c.execute("UPDATE scripts SET pid=? WHERE script_id=?", (process.pid, script_id))
    conn.commit()
    
    while True:
        time.sleep(30)
        
        if process.poll() is not None:
            with open(log_path, 'a') as log:
                log.write(f"\n=== SCRIPT RESTARTED at {datetime.now()} ===\n")
            
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=open(log_path, 'a'),
                stderr=open(log_path, 'a'),
                text=True
            )
            active_processes[user_id]['pid'] = process.pid
            active_processes[user_id]['process'] = process
            c.execute("UPDATE scripts SET pid=? WHERE script_id=?", (process.pid, script_id))
            conn.commit()
        
        c.execute("SELECT expiry_time FROM scripts WHERE script_id=?", (script_id,))
        result = c.fetchone()
        if result and datetime.fromisoformat(result[0]) < datetime.now():
            stop_process(process.pid)
            c.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
            conn.commit()
            if user_id in active_processes:
                del active_processes[user_id]
            break

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, join_date) VALUES (?, ?, ?)",
                  (user_id, username, datetime.now().isoformat()))
        conn.commit()
    
    if not check_channel(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ Joined", callback_data="check"))
        bot.reply_to(message, "🚫 *Join channel first!*", parse_mode="Markdown", reply_markup=markup)
        return
    
    text = """
╔════════════════════════════════╗
║     🐍 *WINOVA HOST*           ║
║  Auto Package Installer        ║
╚════════════════════════════════╝

📎 *Send me:*
• .py file - Single script
• .zip file - Full project

✨ *Features:*
├ Auto detects imports
├ Auto installs packages
├ 30 days free hosting
└ 24/7 running

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ *Commands:*
/status - Check status
/logs - View output
/stop - Stop script
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📊 Status", callback_data="status"),
        types.InlineKeyboardButton("🛑 Stop", callback_data="stop")
    )
    
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['status'])
def status_cmd(message):
    user_id = message.from_user.id
    
    c.execute("SELECT script_name, start_time, expiry_time FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    script = c.fetchone()
    
    if script:
        name, start, expiry = script
        days = (datetime.fromisoformat(expiry) - datetime.now()).days
        days = max(0, days)
        
        c.execute("SELECT pid FROM scripts WHERE user_id=? AND status='running'", (user_id,))
        pid_result = c.fetchone()
        is_running = False
        if pid_result and pid_result[0]:
            try:
                os.kill(pid_result[0], 0)
                is_running = True
            except:
                pass
        
        status_icon = "🟢" if is_running else "🔴"
        
        text = f"""
📊 *SCRIPT STATUS*

{status_icon} Status: {'Running' if is_running else 'Stopped'}
📄 Name: {name}
⏱️ Expires: {days} days left
📅 Started: {start[:10]}
"""
    else:
        text = "❌ *No script running*\n\nSend a .py or .zip file to start."
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['logs'])
def logs_cmd(message):
    user_id = message.from_user.id
    
    log_path = f"{LOGS_DIR}/{user_id}.log"
    
    if not os.path.exists(log_path):
        bot.reply_to(message, "❌ No logs found!", parse_mode="Markdown")
        return
    
    with open(log_path, 'r') as f:
        content = f.read()
    
    if not content:
        bot.reply_to(message, "📝 Log file is empty", parse_mode="Markdown")
        return
    
    content = content[-3000:]
    if len(content) > 4000:
        content = content[:4000] + "\n\n... (truncated)"
    
    bot.reply_to(message, f"📝 *OUTPUT LOGS*\n```\n{content}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_cmd(message):
    user_id = message.from_user.id
    
    c.execute("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    script = c.fetchone()
    
    if not script:
        bot.reply_to(message, "❌ No script running!", parse_mode="Markdown")
        return
    
    script_id, pid = script
    
    if pid and stop_process(pid):
        c.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
        conn.commit()
        if user_id in active_processes:
            del active_processes[user_id]
        bot.reply_to(message, "✅ *Script stopped!*", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Failed to stop!", parse_mode="Markdown")

# ================= FILE UPLOAD =================
@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    
    if not check_channel(user_id):
        bot.reply_to(message, "🚫 Join channel first!")
        return
    
    c.execute("SELECT script_id, expiry_time FROM scripts WHERE user_id=? AND status='running'", (user_id,))
    existing = c.fetchone()
    
    if existing:
        script_id, expiry_time = existing
        if datetime.fromisoformat(expiry_time) > datetime.now():
            days_left = (datetime.fromisoformat(expiry_time) - datetime.now()).days
            bot.reply_to(message, f"⚠️ *You already have a script!*\n\nExpires in {days_left} days.\nUse /stop first.", parse_mode="Markdown")
            return
    
    file_name = message.document.file_name
    
    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        bot.reply_to(message, "❌ Send .py or .zip file only!", parse_mode="Markdown")
        return
    
    status_msg = bot.reply_to(message, "📤 *Processing...*", parse_mode="Markdown")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        script_id = f"{user_id}_{int(time.time())}"
        script_dir = f"{SCRIPTS_DIR}/{script_id}"
        os.makedirs(script_dir, exist_ok=True)
        
        script_path = None
        script_name = file_name
        
        if file_name.endswith('.zip'):
            zip_path = os.path.join(script_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(downloaded)
            
            bot.edit_message_text("📦 *Extracting...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
            
            success, err = extract_zip(zip_path, script_dir)
            if not success:
                bot.edit_message_text(f"❌ Extract failed: {err}", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                return
            
            script_path = find_main_py(script_dir)
            if not script_path:
                bot.edit_message_text("❌ No .py file found!", message.chat.id, status_msg.message_id, parse_mode="Markdown")
                return
            
            script_name = os.path.basename(script_path)
            
            req_result = install_requirements_file(script_dir)
            if req_result:
                bot.send_message(message.chat.id, req_result, parse_mode="Markdown")
            
        else:
            script_path = os.path.join(script_dir, file_name)
            with open(script_path, 'wb') as f:
                f.write(downloaded)
        
        bot.edit_message_text("🔍 *Installing packages...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
        install_result = auto_install_packages(script_path, message.chat.id)
        bot.send_message(message.chat.id, install_result, parse_mode="Markdown")
        
        expiry_time = (datetime.now() + timedelta(days=HOSTING_DAYS)).isoformat()
        
        c.execute('''INSERT INTO scripts (script_id, user_id, script_name, script_path, start_time, expiry_time, status) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (script_id, user_id, script_name, script_path, datetime.now().isoformat(), expiry_time, 'running'))
        conn.commit()
        
        bot.edit_message_text("🚀 *Starting script...*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
        thread = threading.Thread(target=run_script, args=(user_id, script_path, script_id), daemon=True)
        thread.start()
        
        expiry_date = datetime.fromisoformat(expiry_time).strftime("%d/%m/%Y")
        
        success_text = f"""
✅ *SCRIPT HOSTED!*

📄 Name: {script_name}
⏱️ Expires: {expiry_date}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Commands:
/status - Check status
/logs - View output
/stop - Stop script
"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📊 Status", callback_data="status"),
            types.InlineKeyboardButton("📜 Logs", callback_data="logs"),
            types.InlineKeyboardButton("🛑 Stop", callback_data="stop")
        )
        
        bot.edit_message_text(success_text, message.chat.id, status_msg.message_id, parse_mode="Markdown", reply_markup=markup)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)[:100]}", message.chat.id, status_msg.message_id, parse_mode="Markdown")

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "check":
        if check_channel(user_id):
            bot.edit_message_text("✅ Verified! Send .py or .zip file", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "Join channel first!", show_alert=True)
        return
    
    if data == "status":
        c.execute("SELECT script_name, expiry_time FROM scripts WHERE user_id=? AND status='running'", (user_id,))
        script = c.fetchone()
        if script:
            name, expiry = script
            days = (datetime.fromisoformat(expiry) - datetime.now()).days
            days = max(0, days)
            text = f"✅ Running\n📄 {name}\n⏱️ {days} days left"
        else:
            text = "❌ No script running"
        bot.answer_callback_query(call.id, text, show_alert=True)
        return
    
    if data == "logs":
        log_path = f"{LOGS_DIR}/{user_id}.log"
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                content = f.read()[-500:]
            bot.answer_callback_query(call.id, "Check logs below", show_alert=False)
            bot.send_message(call.message.chat.id, f"📝 *Recent Output*\n```\n{content}\n```", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "No logs yet!", show_alert=True)
        return
    
    if data == "stop":
        c.execute("SELECT script_id, pid FROM scripts WHERE user_id=? AND status='running'", (user_id,))
        script = c.fetchone()
        if script:
            script_id, pid = script
            if pid and stop_process(pid):
                c.execute("UPDATE scripts SET status='stopped' WHERE script_id=?", (script_id,))
                conn.commit()
                if user_id in active_processes:
                    del active_processes[user_id]
                bot.answer_callback_query(call.id, "✅ Stopped!", show_alert=True)
                bot.edit_message_text("✅ Script stopped!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "Failed!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "No script!", show_alert=True)
        return

# ================= CLEANUP =================
def cleanup_worker():
    while True:
        time.sleep(3600)
        now = datetime.now().isoformat()
        c.execute("SELECT script_id, pid FROM scripts WHERE expiry_time < ? AND status='running'", (now,))
        expired = c.fetchall()
        for script_id, pid in expired:
            if pid:
                stop_process(pid)
            c.execute("UPDATE scripts SET status='expired' WHERE script_id=?", (script_id,))
        conn.commit()

# ================= MAIN =================
if __name__ == "__main__":
    print("=" * 50)
    print("🐍 WINOVA PYTHON HOST")
    print("=" * 50)
    print("Bot Started!")
    print(f"Admin ID: {ADMIN_ID}")
    print("=" * 50)
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    
    bot.infinity_polling()
