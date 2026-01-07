from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import logging
import asyncio
import time
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID") or 0)

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.WARNING)

FILTER_ACTIVE = False
FILTER_WORDS = []
FILTER_BYPASS_ADMINS = True

muted = {}

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

def normalize_number(s: str) -> str:
    if not isinstance(s, str):
        return s
    return s.translate(_DIGIT_MAP)

async def is_admin(chat_id: int, uid: int) -> bool:
    if OWNER_ID and uid == OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, uid)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

@dp.message(Command("clear"))
async def clear_chat(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("این دستور فقط تو گروه کار می‌کنه.")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط ادمین‌ها می‌تونن از این دستور استفاده کنن و البته که منم میتونم.")
        return

    parts = (message.text or "").split()

    if message.reply_to_message:
        deleted = 0
        status = await message.reply("در حال پاکسازی پیام ریپلای شده...")
        try:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            deleted = 1
        except Exception:
            pass

        final = await message.answer(f"پاکسازی تموم شد\nتعداد حذف شده: {deleted}")
        await asyncio.sleep(10)
        for mid in (status.message_id, final.message_id, message.message_id):
            try:
                await bot.delete_message(message.chat.id, mid)
            except Exception:
                pass
        return

    try:
        count = int(normalize_number(parts[1])) if len(parts) > 1 else 10
    except Exception:
        await message.reply("یه عدد بعدش بزار.مثلا: /clear 10")
        return

    if count < 1:
        await message.reply("ایسکامونو گرفتی؟؟؟")
        return

    count = min(count, 100)
    status = await message.reply("در حال پاکسازی...")

    ids = [message.message_id - i for i in range(1, count + 1) if message.message_id - i > 0]

    deleted = 0
    for mid in ids:
        try:
            await bot.delete_message(message.chat.id, mid)
            deleted += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    final = await message.answer(f"پاکسازی تموم شد\nتعداد حذف شده: {deleted}")
    await asyncio.sleep(10)
    for mid in (status.message_id, final.message_id, message.message_id):
        try:
            await bot.delete_message(message.chat.id, mid)
        except Exception:
            pass

@dp.message()
async def commands_and_filters(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if message.from_user.is_bot:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    parts = text.split()
    cmd = parts[0].lstrip("/").split("@")[0]

    if cmd == "حذف" and len(parts) > 1 and parts[1] == "پین":
        if not message.reply_to_message:
            await message.reply("برای حذف پین باید روی همان پیام ریپلای کنی.")
            return
        if not await is_admin(chat_id, user_id):
            await message.reply("فقط ادمین/سازنده می‌تواند پین را حذف کند.")
            return
        try:
            await bot.unpin_chat_message(chat_id, message.reply_to_message.message_id)
            info = await message.reply("پین پیام برداشته شد.")
        except Exception:
            await message.reply("خطا در برداشتن پین (ممکن است ربات دسترسی نداشته باشد).")
            return

        await asyncio.sleep(10)
        try:
            await bot.delete_message(chat_id, info.message_id)
            await bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass
        return

    if cmd == "سکوت":
        if not message.reply_to_message:
            await message.reply("برای سکوت باید روی کاربر ریپلای کنی.")
            return
        if not await is_admin(chat_id, user_id):
            await message.reply("فقط ادمین‌ها می‌تونن سکوت کنند.")
            return

        target = message.reply_to_message.from_user
        until = None

        if len(parts) > 1:
            try:
                minutes = int(normalize_number(parts[1]))
                if minutes > 0:
                    until = int(time.time() + minutes * 60)
            except Exception:
                await message.reply("عدد باید بزاری مثلا: سکوت 10")
                return

        muted[(chat_id, target.id)] = until

        try:
            await bot.restrict_chat_member(
                chat_id,
                target.id,
                permissions=types.ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                ),
                until_date=until
            )
        except Exception:
            pass

        if until is None:
            info = await message.reply(f"{target.full_name} سکوت شد.")
        else:
            info = await message.reply(f"{target.full_name} برای {parts[1]} دقیقه سکوت شد.")

            async def auto_unmute():
                await asyncio.sleep(max(0, until - int(time.time())))
                k = (chat_id, target.id)
                if k in muted:
                    try:
                        await bot.restrict_chat_member(
                            chat_id,
                            target.id,
                            permissions=types.ChatPermissions(
                                can_send_messages=True,
                                can_send_media_messages=True,
                                can_send_other_messages=True,
                                can_add_web_page_previews=True,
                            )
                        )
                    except Exception:
                        pass
                    muted.pop(k, None)

            asyncio.create_task(auto_unmute())

        await asyncio.sleep(10)
        try:
            await bot.delete_message(chat_id, info.message_id)
            await bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

    if FILTER_ACTIVE and FILTER_WORDS:
        text_l = text.lower()
        if any(w and w in text_l for w in FILTER_WORDS):
            if FILTER_BYPASS_ADMINS and await is_admin(chat_id, user_id):
                return
            try:
                await bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            warn = await message.answer("پیام شما فحش داشت پس حذف شد.")
            await asyncio.sleep(10)
            try:
                await bot.delete_message(chat_id, warn.message_id)
            except Exception:
                pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
