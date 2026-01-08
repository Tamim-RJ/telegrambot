from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import logging
import asyncio
import time
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

FILTER_ACTIVE = False
FILTER_WORDS = []
FILTER_BYPASS_ADMINS = True
muted_users = {}

def clean_text(message: types.Message) -> str:
    return (message.text or "").strip()

main_help_text = """<b>راهنمای ربات</b>

یکی از گزینه‌های زیر رو انتخاب کن
"""

help_text = {
    "help_delete": """<b>راهنمای حذف</b>

حذف [تعداد] - پاک کردن پیام‌ها
حذف - حذف پیام مشخص شده (reply)""",

    "help_pin": """<b>راهنمای پین</b>

پین - پین کردن پیام (reply)
حذف پین - حذف پین (reply)
حذف پین همه - حذف همه پین ها""",

    "help_mute": """<b>راهنمای سکوت</b>

سکوت [دقیقه] - سکوت کاربر (reply)
حذف سکوت - لغو سکوت (reply)""",

    "help_eco": """<b>راهنمای اکو</b>

بگوو [متن] - ارسال پیام از طرف ربات"""
}

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def normalize_number(s: str) -> str:
    return s.translate(_DIGIT_MAP)

async def is_admin(chat_id: int, user_id: int) -> bool:
    if OWNER_ID and user_id == OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

async def auto_delete_after(chat_id: int, ids: list[int], delay: int = 10):
    await asyncio.sleep(delay)
    for mid in ids:
        try:
            await bot.delete_message(chat_id, mid)
        except:
            pass

def help_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="حذف", callback_data="help_delete"),
            InlineKeyboardButton(text="پین", callback_data="help_pin"),
            InlineKeyboardButton(text="سکوت", callback_data="help_mute"),
        ],
        [InlineKeyboardButton(text="اکو", callback_data="help_eco")]
    ])

def help_keyboard_sub():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="بازگشت", callback_data="help_main")]
    ])

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    await message.answer(main_help_text, reply_markup=help_keyboard())

@dp.callback_query(F.data.startswith("help_"))
async def help_callback(call: types.CallbackQuery):
    if call.data == "help_main":
        await call.message.edit_text(main_help_text, reply_markup=help_keyboard())
        return
    await call.message.edit_text(help_text.get(call.data, "X"), reply_markup=help_keyboard_sub())

@dp.message()
async def cmd_delete(message: types.Message):
    text = clean_text(message)
    if not text.startswith("حذف"):
        return

    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if message.reply_to_message:
        await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        info = await message.reply("حذف شد")
        asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))
        return

    parts = text.split()
    count = int(normalize_number(parts[1])) if len(parts) > 1 else 10
    count = min(max(count, 1), 100)

    deleted = 0
    async for msg in bot.get_chat_history(message.chat.id, limit=count + 1):
        if msg.message_id != message.message_id:
            try:
                await bot.delete_message(message.chat.id, msg.message_id)
                deleted += 1
            except:
                pass

    info = await message.reply(f"تعداد حذف‌شده: {deleted}")
    asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))

@dp.message()
async def cmd_pin(message: types.Message):
    text = clean_text(message)

    if text == "حذف پین همه":
        if await is_admin(message.chat.id, message.from_user.id):
            await bot.unpin_all_chat_messages(message.chat.id)
        return

    if text == "حذف پین":
        if message.reply_to_message and await is_admin(message.chat.id, message.from_user.id):
            await bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
        return

    if text == "پین":
        if not message.reply_to_message:
            await message.reply("باید روی پیام ریپلای کنی")
            return
        if await is_admin(message.chat.id, message.from_user.id):
            await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id, disable_notification=True)

@dp.message()
async def cmd_say(message: types.Message):
    text = clean_text(message)
    if not text.startswith("بگوو "):
        return

    await message.answer(text[5:])
    await bot.delete_message(message.chat.id, message.message_id)

@dp.message()
async def cmd_mute(message: types.Message):
    text = clean_text(message)

    if text == "حذف سکوت":
        if message.reply_to_message and await is_admin(message.chat.id, message.from_user.id):
            await bot.restrict_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id,
                permissions=types.ChatPermissions(can_send_messages=True)
            )
        return

    if not text.startswith("سکوت"):
        return

    if not message.reply_to_message or not await is_admin(message.chat.id, message.from_user.id):
        return

    parts = text.split()
    minutes = int(normalize_number(parts[1])) if len(parts) > 1 else None
    until = int(time.time() + minutes * 60) if minutes else None

    await bot.restrict_chat_member(
        message.chat.id,
        message.reply_to_message.from_user.id,
        permissions=types.ChatPermissions(can_send_messages=False),
        until_date=until
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
