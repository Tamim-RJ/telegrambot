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

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def normalize_number(s: str) -> str:
    """Convert Persian/Arabic digits to English"""
    return s.translate(_DIGIT_MAP) if isinstance(s, str) else s

async def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin or owner"""
    if OWNER_ID and user_id == OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def delete_messages_safe(chat_id: int, message_ids: list[int]):
    """Safely delete multiple messages"""
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception as e:
            logger.debug(f"Could not delete message {mid}: {e}")

async def auto_delete_after(chat_id: int, message_ids: list[int], delay: int = 10):
    """Auto-delete messages after delay"""
    await asyncio.sleep(delay)
    await delete_messages_safe(chat_id, message_ids)

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    """Show help message"""
    if message.chat.type == "private" or "group" or "supergroup":
        help_text = """
<b>راهنمای ربات</b>

<b>دستورات مدیریتی:</b>
/clear [تعداد] - پاک کردن پیام‌ها
حذف [تعداد] - پاک کردن پیام‌ها
پین - پین کردن پیام (reply)
حذف پین - حذف پین (reply)
حذف پین همه - حذف همه پین ها (reply)
سکوت [دقیقه] - سکوت کاربر (reply)
حذف سکوت - لغو سکوت (reply)
بگوو [متن] - ارسال پیام از طرف ربات

<b>توجه:</b> برای ادمین و منه
        """
        await message.answer(help_text.strip())

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    """Clear messages with /clear command"""
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("این دستور فقط تو گروه کار می‌کند.")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم.")
        return

    if message.reply_to_message:
        status = await message.reply("دارم میپاکم...")
        deleted = 0
        try:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            deleted = 1
        except Exception as e:
            logger.error(f"Failed to delete replied message: {e}")
        
        final = await message.answer(f"پاکیدم\nتعداد پاکیده شده: {deleted}")
        asyncio.create_task(auto_delete_after(
            message.chat.id,
            [status.message_id, final.message_id, message.message_id]
        ))
        return

    parts = (message.text or "").split()
    try:
        count = int(normalize_number(parts[1])) if len(parts) > 1 else 10
    except (IndexError, ValueError):
        await message.reply("بلد نیستی دست نزن دیگه... اه.")
        return

    if count < 1:
        await message.reply("😐")
        return

    count = min(count, 100)
    status = await message.reply(f"دارم میپاکم{count} پیام...")

    ids = [message.message_id - i for i in range(1, count + 1) if message.message_id - i > 0]
    
    deleted = 0
    try:
        await bot.delete_messages(message.chat.id, ids)
        deleted = len(ids)
    except Exception as e:
        logger.warning(f"Bulk delete failed, falling back to single deletes: {e}")
        for mid in ids:
            try:
                await bot.delete_message(message.chat.id, mid)
                deleted += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass

    final = await message.answer(f"پاکیدم\nتعداد حذف شده: {deleted}")
    asyncio.create_task(auto_delete_after(
        message.chat.id,
        [status.message_id, final.message_id, message.message_id]
    ))

@dp.message(F.text.startswith("پین"))
async def cmd_pin(message: types.Message):
    """Pin a message"""
    if not message.reply_to_message:
        await message.reply("باید ریپ کنی")
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط ادمین میتونه و من..")
        return

    try:
        await bot.pin_chat_message(
            message.chat.id,
            message.reply_to_message.message_id,
            disable_notification=True
        )
        info = await message.reply("پیام پین شد.")
        asyncio.create_task(auto_delete_after(
            message.chat.id,
            [info.message_id, message.message_id]
        ))
    except Exception as e:
        logger.error(f"Pin failed: {e}")
        await message.reply("منو ادمین کردی؟")

@dp.message(F.text.startswith("حذف پین همه"))
async def cmd_unpin(message: types.Message):
    """Unpin the currently pinned message"""
    if message.chat.type not in ("group", "supergroup"):
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم.")
        return
    
    try:
        await bot.unpin_all_chat_messages(message.chat.id)
        
        info = await message.reply("پین ها رو برداشتم.")
        asyncio.create_task(auto_delete_after(
            message.chat.id,
            [info.message_id, message.message_id]
        ))
    except Exception as e:
        logger.error(f"Unpin failed: {e}")
        await message.reply("نمیتونم بردارم.. چک کن ببین دسترسی دارم؟؟")

@dp.message(F.text.startswith("حذف پین"))
async def cmd_unpin(message: types.Message):
    """Unpin a specific message (by reply)"""
    if not message.reply_to_message:
        await message.reply("باید رو پیام پین‌شده ریپ کنی")
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من و ادمین میتونیم.")
        return
    
    try:
        await bot.unpin_chat_message(
            chat_id=message.chat.id,
            message_id=message.reply_to_message.message_id
        )
        
        info = await message.reply("پین رو برداشتم.")
        asyncio.create_task(auto_delete_after(
            message.chat.id,
            [info.message_id, message.message_id]
        ))
    except Exception as e:
        logger.error(f"Unpin failed: {e}")
        await message.reply("خطا: نشد که بشه..")

@dp.message(F.text.startswith("بگوو"))
async def cmd_say(message: types.Message):
    """Make bot say something"""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("بلد نیستی دست نزن...")
        return

    text = parts[1]
    try:
        if message.reply_to_message and await is_admin(message.chat.id, message.from_user.id):
            sent = await bot.send_message(
                message.chat.id,
                text,
                reply_to_message_id=message.reply_to_message.message_id
            )
        else:
            sent = await message.answer(text)
        
        await bot.delete_message(message.chat.id, message.message_id)

    except Exception as e:
        logger.error(f"Say command failed: {e}")

@dp.message(F.text.startswith("سکوت"))
async def cmd_mute(message: types.Message):
    """Mute a user"""
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

    asyncio.create_task(auto_delete_after(
        message.chat.id,
        [info.message_id, message.message_id]
    ))

@dp.message(F.text.startswith("حذف سکوت"))
async def cmd_unmute(message: types.Message):
    """Unmute a user"""
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

    asyncio.create_task(auto_delete_after(
        message.chat.id,
        [info.message_id, message.message_id]
    ))

@dp.message(F.text.startswith("حذف"))
async def cmd_delete(message: types.Message):
    """Delete messages with 'حذف' command"""
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("فقط من وادمین میتونیم")
        return

    if message.reply_to_message:
        status = await message.reply(" در حال حذف...")
        deleted = 0
        try:
            await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            deleted = 1
        except Exception as e:
            logger.error(f"Delete failed: {e}")
        
        final = await message.answer(f"حذف کردم.\nتعداد: {deleted}")
        asyncio.create_task(auto_delete_after(
            message.chat.id,
            [status.message_id, final.message_id, message.message_id]
        ))
        return



    parts = (message.text or "").split()
    try:
        count = int(normalize_number(parts[1])) if len(parts) > 1 else 10
    except (IndexError, ValueError):
        await message.reply("اینجوریه: حذف [تعداد]")
        return

    if count < 1:
        await message.reply("😐")
        return

    count = min(count, 100)
    status = await message.reply(f" دارم می حذفم {count} پیام...")

    ids = [message.message_id - i for i in range(1, count + 1) if message.message_id - i > 0]
    
    deleted = 0
    try:
        await bot.delete_messages(message.chat.id, ids)
        deleted = len(ids)
    except Exception:
        for mid in ids:
            try:
                await bot.delete_message(message.chat.id, mid)
                deleted += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass

    final = await message.answer(f"حذف کردم\nتعداد: {deleted}")
    asyncio.create_task(auto_delete_after(
        message.chat.id,
        [status.message_id, final.message_id, message.message_id]
    ))



async def schedule_unmute(chat_id: int, user_id: int, until_time: int):
    """Schedule automatic unmute"""
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
            await bot.send_message(
                chat_id,
                f"زمان سکوت تموم شد."
            )
        except Exception as e:
            logger.error(f"Auto-unmute failed: {e}")



@dp.message(F.text | F.caption)
async def filter_profanity(message: types.Message):
    """Filter bad words"""
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
    """Start the bot"""
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
