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
SPAM_LIMIT = 5
SPAM_INTERVAL = 5
SPAM_MUTE_DURATION = 5
user_message_times = {}

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
حذف پین همه - حذف همه پین ها (reply)""",
    "help_mute": """<b>راهنمای سکوت</b>

سکوت [دقیقه] - سکوت کاربر (reply)
حذف سکوت - لغو سکوت (reply)""",
    "help_eco": """<b>راهنمای اکو</b>

بگوو [متن] - ارسال پیام از طرف ربات
"""
}

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def normalize_number(s: str) -> str:
    return s.translate(_DIGIT_MAP) if isinstance(s, str) else s

async def is_admin(chat_id: int, user_id: int) -> bool:
    if OWNER_ID and user_id == OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def delete_messages_safe(chat_id: int, message_ids: list[int]):
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception as e:
            logger.debug(f"Could not delete message {mid}: {e}")

async def auto_delete_after(chat_id: int, message_ids: list[int], delay: int = 10):
    await asyncio.sleep(delay)
    await delete_messages_safe(chat_id, message_ids)

def help_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="حذف", callback_data="help_delete"),
            InlineKeyboardButton(text="پین", callback_data="help_pin"),
            InlineKeyboardButton(text="سکوت", callback_data="help_mute"),
        ],
        [
            InlineKeyboardButton(text="اکو", callback_data="help_eco")
        ]
    ])

def help_keyboard_sub():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="بازگشت", callback_data="help_main")
        ]
    ])

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    await message.answer(main_help_text, reply_markup=help_keyboard())

@dp.callback_query(F.data.startswith("help_"))
async def help_callback(call: types.CallbackQuery):
    if call.data == "help_main":
        await call.message.edit_text(main_help_text, reply_markup=help_keyboard())
        await call.answer()
        return

    text = help_text.get(call.data, "راهنمایی موجود نیست.")
    await call.message.edit_text(text, reply_markup=help_keyboard_sub())
    await call.answer()

@dp.message(F.text == "پین")
async def cmd_pin(message: types.Message):
    if not message.reply_to_message:
        await message.reply("باید ریپ کنی")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط ادمین میتونه و من..")
        return

    try:
        await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id, disable_notification=True)
        info = await message.reply("پیام پین شد.")
        asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))
    except Exception as e:
        logger.error(f"Pin failed: {e}")
        await message.reply("منو ادمین کردی؟")

@dp.message(F.text == "حذف پین همه")
async def cmd_unpin_all(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم.")
        return

    try:
        await bot.unpin_all_chat_messages(message.chat.id)
        info = await message.reply("پین ها رو برداشتم.")
        asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))
    except Exception as e:
        logger.error(f"Unpin all failed: {e}")
        await message.reply("نمیتونم بردارم.. چک کن ببین دسترسی دارم؟؟")

@dp.message(F.text == "حذف پین")
async def cmd_unpin(message: types.Message):
    if not message.reply_to_message:
        await message.reply("باید رو پیام پین‌شده ریپ کنی")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم.")
        return

    try:
        await bot.unpin_chat_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        info = await message.reply("پین رو برداشتم.")
        asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))
    except Exception as e:
        logger.error(f"Unpin failed: {e}")
        await message.reply("خطا: نشد که بشه..")

@dp.message(F.text.startswith("بگوو"))
async def cmd_say(message: types.Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("بلد نیستی دست نزن...")
        return

    text = parts[1]
    try:
        if message.reply_to_message and await is_admin(message.chat.id, message.from_user.id):
            await bot.send_message(message.chat.id, text, reply_to_message_id=message.reply_to_message.message_id)
        else:
            await message.answer(text)
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.error(f"Say command failed: {e}")

@dp.message(F.text.startswith("سکوت"))
async def cmd_mute(message: types.Message):
    if not message.reply_to_message:
        await message.reply("باید رو یکی ریپ کنی")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط ادمین و من میتونیم سکوت بدیم")
        return

    target = message.reply_to_message.from_user
    parts = (message.text or "").split()

    duration_minutes = None
    until_time = None
    if len(parts) > 1:
        try:
            duration_minutes = int(normalize_number(parts[1]))
            if duration_minutes > 0:
                until_time = int(time.time() + duration_minutes * 60)
        except ValueError:
            await message.reply("باید مثلا بگی سکوت 10")
            return

    muted_users[(message.chat.id, target.id)] = until_time

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until_time
        )
    except Exception as e:
        logger.error(f"Mute failed: {e}")
        await message.reply("خطا")
        return

    if duration_minutes:
        info = await message.reply(f"{target.full_name} برای {duration_minutes} دقیقه سکوت شد.")
        asyncio.create_task(schedule_unmute(message.chat.id, target.id, until_time))
    else:
        info = await message.reply(f"{target.full_name} سکوت شد.")

    asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))

@dp.message(F.text == "حذف سکوت")
async def cmd_unmute(message: types.Message):
    if not message.reply_to_message:
        await message.reply("باید رو یکی ریپ کنی")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم.")
        return

    target = message.reply_to_message.from_user
    key = (message.chat.id, target.id)

    if key not in muted_users:
        await message.reply("سکوت نیست که..")
        return

    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=types.ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        muted_users.pop(key, None)
        info = await message.reply(f"سکوت {target.full_name} برداشته شد.")
    except Exception as e:
        logger.error(f"Unmute failed: {e}")
        await message.reply("خطا")
        return

    asyncio.create_task(auto_delete_after(message.chat.id, [info.message_id, message.message_id]))

async def schedule_unmute(chat_id: int, user_id: int, until_time: int):
    delay = max(0, until_time - int(time.time()))
    await asyncio.sleep(delay)

    key = (chat_id, user_id)
    if key in muted_users and muted_users[key] == until_time:
        try:
            await bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=types.ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            muted_users.pop(key, None)
            await bot.send_message(chat_id, f"زمان سکوت تموم شد.")
        except Exception as e:
            logger.error(f"Auto-unmute failed: {e}")

async def check_spam(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return False

    user_id = message.from_user.id
    chat_id = message.chat.id
    now = time.time()
    key = (chat_id, user_id)

    times = user_message_times.get(key, [])
    times = [t for t in times if now - t < SPAM_INTERVAL]
    times.append(now)
    user_message_times[key] = times

    if len(times) > SPAM_LIMIT:
        until_time = int(now + SPAM_MUTE_DURATION * 60)
        muted_users[key] = until_time
        try:
            await bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=types.ChatPermissions(can_send_messages=False),
                until_date=until_time
            )
            warn = await message.reply(f"{message.from_user.full_name} برای {SPAM_MUTE_DURATION} دقیقه سکوت شد (اسپم).")
            asyncio.create_task(auto_delete_after(chat_id, [warn.message_id]))
        except Exception as e:
            logger.error(f"Spam mute failed: {e}")
        user_message_times[key] = []
        return True
    
@dp.message(F.text.startswith("حذف"))
async def cmd_delete(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم")
        return
    
    if message.reply_to_message:
        status = await message.reply("در حال حذف...")
        deleted = 0
        try:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            deleted = 1
        except Exception:
            pass

        final = await message.answer(f"حذف کردم\nتعداد: {deleted}")
        asyncio.create_task(auto_delete_after(
            message.chat.id,
            [status.message_id, final.message_id, message.message_id]
        ))
        return

    parts = (message.text or "").split()
    try:
        count = int(normalize_number(parts[1])) if len(parts) > 1 else 10
    except Exception:
        await message.reply("اینجوریه: حذف [تعداد] یا رو یه پیام ریپ کن")
        return

    count = min(max(count, 1), 100)

    status = await message.reply(f"دارم {count} پیام رو حذف می‌کنم...")

    deleted = 0
    last_message_id = message.message_id

    for i in range(count):
        msg_id = last_message_id - i - 1
        if msg_id <= 0:
            break
        try:
            await bot.delete_message(message.chat.id, msg_id)
            deleted += 1
        except Exception as e:
            logger.debug(f"Cannot delete message {msg_id}: {e}")
        await asyncio.sleep(0.05)

    final = await message.answer(f"حذف شد\nتعداد: {deleted}")
    asyncio.create_task(auto_delete_after(
        message.chat.id, [status.message_id, final.message_id, message.message_id]
    ))

    return False

@dp.message(F.text | F.caption)
async def handle_message(message: types.Message):
    if await check_spam(message):
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
        return

    if message.chat.type not in ("group", "supergroup"):
        return

    if not FILTER_ACTIVE or not FILTER_WORDS:
        return

    text = (message.text or message.caption or "").lower()
    if any(word and word in text for word in FILTER_WORDS):
        if FILTER_BYPASS_ADMINS and await is_admin(message.chat.id, message.from_user.id):
            return
        try:
            await bot.delete_message(message.chat.id, message.message_id)
            warn = await message.answer("بی ادب")
            asyncio.create_task(auto_delete_after(message.chat.id, [warn.message_id]))
        except Exception as e:
            logger.error(f"Filter failed: {e}")

async def main():
    logger.info("Bot is starting...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Bot stopped with error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
