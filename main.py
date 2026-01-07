import asyncio
import time
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

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

@dp.message(Command("clear"))
async def clear_chat(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("این دستور فقط تو گروه کار می‌کنه.")
        return
    
    if message.from_user.id != OWNER_ID:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ("administrator", "creator"):
            await message.reply("فقط ادمین‌ها می‌تونن از این دستور استفاده کنن و البته که منم میتونم.")
            return

    parts = (message.text or "").strip().split()
    is_reply = bool(message.reply_to_message)

    if is_reply:
        deleted = 0
        status_msg = await message.reply("در حال پاکسازی پیام ریپلای شده...")
        try:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            deleted = 1
        except Exception:
            deleted = 0
        final_msg = await message.answer(f"پاکسازی تموم شد\nتعداد حذف شده: {deleted}")
        await asyncio.sleep(10)
        for mid in (status_msg.message_id, final_msg.message_id, message.message_id):
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

    MAX_DELETE = 100
    count = min(count, MAX_DELETE)

    status_msg = await message.reply("در حال پاکسازی...")

    ids = [message.message_id - i for i in range(1, count + 1)]
    ids = [m for m in ids if m > 0]

    deleted = 0
    try:
        await bot.delete_messages(message.chat.id, ids)
        deleted = len(ids)
    except Exception:
        deleted = 0
        for mid in ids:
            try:
                await bot.delete_message(message.chat.id, mid)
                deleted += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)

    final_msg = await message.answer(f"پاکسازی تموم شد\nتعداد حذف شده: {deleted}")
    await asyncio.sleep(10)
    for mid in (status_msg.message_id, final_msg.message_id, message.message_id):
        try:
            await bot.delete_message(message.chat.id, mid)
        except Exception:
            pass

@dp.message()
async def _commands_and_filters(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    if message.from_user.is_bot:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    async def is_admin(uid: int) -> bool:
        if uid == OWNER_ID:
            return True
        try:
            member = await bot.get_chat_member(chat_id, uid)
            return member.status in ("administrator", "creator")
        except Exception:
            return False

    logging.debug(f"Incoming message id={message.message_id} from={user_id} reply_to={bool(message.reply_to_message)}")
    if message.reply_to_message:
        try:
            rt = message.reply_to_message
            logging.debug(f"Replied message id={rt.message_id} from={(rt.from_user.id if rt.from_user else 'None')} is_bot={(rt.from_user.is_bot if rt.from_user else 'N/A')} text={(rt.text or rt.caption or '')}")
        except Exception:
            logging.exception("could not log replied-to message")

    key = (chat_id, user_id)
    if key in muted:
        until = muted[key]
        if until is None or until > time.time():
            try:
                await bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            return
        else:
            try:
                del muted[key]
            except KeyError:
                pass

    text = (message.text or message.caption or "").strip()
    if text:
        parts = text.split()
        cmd = parts[0].lstrip("/").split("@")[0]
        logging.debug(f"Handler text='{text}' from user={user_id} in chat={chat_id}")

        if cmd == "حذف" and len(parts) > 1 and parts[1] == "سکوت":
            if not message.reply_to_message:
                await message.reply("برای حذف سکوت باید روی کاربر ریپلای کنی.")
                return
            logging.debug(f"Attempting unmute by admin={message.from_user.id}")
            if not await is_admin(message.from_user.id):
                await message.reply("فقط ادمین‌ها می‌تونن حذف سکوت انجام بدن و البته که من.")
                return
            target = message.reply_to_message.from_user
            if not target:
                await message.reply("یکیو ریپ کن..")
                return
            k = (chat_id, target.id)
            if k in muted:
                try:
                    await bot.restrict_chat_member(chat_id, target.id, permissions=types.ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                    ))
                except Exception:
                    logging.exception("failed to lift restriction when unmuting")
                del muted[k]
                info = await message.reply(f"سکوت {target.full_name} برداشته شد.")
            else:
                info = await message.reply("سکوت نیست که..")
            await asyncio.sleep(10)
            try:
                await bot.delete_message(chat_id, info.message_id)
                await bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            return

        if cmd == "حذف":
            if not await is_admin(message.from_user.id):
                await message.reply("فقط ادمین‌ها می‌تونن حذف کنن و من...")
                return

            if message.reply_to_message:
                deleted = 0
                status = await message.reply("در حال حذف پیام ریپلای شده...")
                try:
                    logging.debug(f"Deleting replied message id={message.reply_to_message.message_id}")
                    await bot.delete_message(chat_id, message.reply_to_message.message_id)
                    deleted = 1
                except Exception as e:
                    logging.exception("failed to delete replied message")
                    deleted = 0
                final = await message.answer(f"پاکسازی تموم شد\nتعداد حذف شده: {deleted}")
                await asyncio.sleep(10)
                for mid in (status.message_id, final.message_id, message.message_id):
                    try:
                        await bot.delete_message(chat_id, mid)
                    except Exception:
                        pass
                return

            try:
                count = int(normalize_number(parts[1])) if len(parts) > 1 else 10
            except Exception:
                await message.reply("یه عدد بعدش بزار.مثلا: حذف 10")
                return
            if count < 1:
                await message.reply("ایسکامونو گرفتی؟؟؟")
                return
            MAX_DELETE = 100
            count = min(count, MAX_DELETE)
            status = await message.reply("در حال پاکسازی...")
            ids = [message.message_id - i for i in range(1, count + 1)]
            ids = [m for m in ids if m > 0]
            deleted = 0
            try:
                await bot.delete_messages(chat_id, ids)
                deleted = len(ids)
            except Exception:
                logging.exception("bulk delete failed, falling back to single deletes")
                for mid in ids:
                    try:
                        await bot.delete_message(chat_id, mid)
                        deleted += 1
                    except Exception:
                        logging.exception(f"failed to delete message {mid}")
                    await asyncio.sleep(0.05)
            final = await message.answer(f"پاکسازی تموم شد\nتعداد حذف شده: {deleted}")
            await asyncio.sleep(10)
            for mid in (status.message_id, final.message_id, message.message_id):
                try:
                    await bot.delete_message(chat_id, mid)
                except Exception:
                    pass
            return

        if cmd == "سکوت":
            if not message.reply_to_message:
                await message.reply("برای سکوت باید روی کاربر ریپلای کنی.")
                return
            if not await is_admin(message.from_user.id):
                await message.reply("فقط ادمین‌ها می‌تونن سکوت کنند.")
                return
            target = message.reply_to_message.from_user
            until = None
            if len(parts) > 1:
                try:
                    minutes = int(normalize_number(parts[1]))
                    if minutes > 0:
                        until = time.time() + minutes * 60
                except Exception:
                    await message.reply("عدد باید بزاری مثلا: سکوت 10")
                    return

            muted[(chat_id, target.id)] = until
            # apply restriction to prevent sending messages
            try:
                await bot.restrict_chat_member(chat_id, target.id, permissions=types.ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                ), until_date=until)
            except Exception:
                logging.exception("failed to restrict user when muting")
            if until is None:
                info = await message.reply(f"{target.full_name} سکوت شد.")
            else:
                info = await message.reply(f"{target.full_name} برای {parts[1]} دقیقه سکوت شد.")

                # schedule unmute
                async def _auto_unmute(c_id, u_id, delay):
                    await asyncio.sleep(delay)
                    k = (c_id, u_id)
                    if k in muted and muted[k] is not None and muted[k] <= time.time():
                        try:
                            # lift restriction in telegram
                            try:
                                await bot.restrict_chat_member(c_id, u_id, permissions=types.ChatPermissions(
                                    can_send_messages=True,
                                    can_send_media_messages=True,
                                    can_send_other_messages=True,
                                    can_add_web_page_previews=True,
                                ))
                            except Exception:
                                logging.exception("failed to lift restriction in auto-unmute")
                            del muted[k]
                        except KeyError:
                            pass
                        try:
                            await bot.send_message(c_id, f"سکوت کاربر <a href=\"tg://user?id={u_id}\">کاربر</a> برداشته شد.")
                        except Exception:
                            logging.exception("failed to send auto-unmute notice")

                if until is not None:
                    delay = max(0, int(until - time.time()))
                    asyncio.create_task(_auto_unmute(chat_id, target.id, delay))

            await asyncio.sleep(10)
            try:
                await bot.delete_message(chat_id, info.message_id)
                await bot.delete_message(chat_id, message.message_id)
            except Exception:
                logging.exception("failed to delete control messages after mute/unmute")
            return

    if FILTER_ACTIVE and (message.text or message.caption):
        text_l = (message.text or message.caption or "").lower()
        matched = any(w for w in FILTER_WORDS if w and w in text_l)
        if matched:
            if FILTER_BYPASS_ADMINS and await is_admin(user_id):
                return
            try:
                await bot.delete_message(chat_id, message.message_id)
            except Exception:
                logging.exception("failed to delete filtered message")
            try:
                warn = await message.answer("پیام شما فحش داشت پس حذف شد.")
                await asyncio.sleep(10)
                try:
                    await bot.delete_message(chat_id, warn.message_id)
                except Exception:
                    logging.exception("failed to delete warning message")
            except Exception:
                logging.exception("failed to send warning for filtered message")
            return

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
