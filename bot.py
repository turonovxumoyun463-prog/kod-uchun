"""
GURUH MODERATORI BOT — bitta fayl, hammasi shu yerda.
"""

import asyncio
import logging
import time
import json
import os
import re
from collections import defaultdict, deque
from datetime import timedelta

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import (
    Message, CallbackQuery, ChatMemberUpdated, ChatPermissions,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Majburiy obuna uchun kanal
CHANNEL_USERNAME = "@kotibchi"
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

RULES_URL = "https://telegra.ph/Guruh-Qoidalari-07-22-3"
EXTRA_LINK_URL = "https://t.me/xumoyunjon/242"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="\U0001F4E2 Kanal"), KeyboardButton(text="\U0001F4CB Qoidalar")],
        [KeyboardButton(text="\U0001F198 Yordam"), KeyboardButton(text="\U0001F4F1 Telegram")],
    ],
    resize_keyboard=True,
)

CAPTCHA_TIMEOUT = 90

BANNED_WORD_MUTE_MINUTES = 3
FLOOD_MUTE_MINUTES = 2
FLOOD_MESSAGE_COUNT = 5
FLOOD_MIN_LENGTH = 10
FLOOD_WINDOW_SECONDS = 15

DATA_FILE = "warnings.json"

BANNED_WORDS = [
    "so'kinish",
    "reklama",
    "haqorat",
    "scam",
    "ton",
    "olib beraman",
    "konkurs",
    "boshlandi",
    "gift",
    "premium",
    "sovg'a",
    "yozganga",
    "sotiladi",
    "ming",
]

RULES_TEXT = """\U0001F4CB <b>Guruh qoidalari</b>

1\uFE0F\u20E3 Guruh reklama qilish taqiqlanadi. /ban yoki /mute qo'llaniladi.
2\uFE0F\u20E3 Boshqa kanallardan xabar forward qilish (yuborish) taqiqlanadi.
3\uFE0F\u20E3 Quyidagi so'zlarni ishlatish taqiqlanadi: so'kinish, reklama, haqorat, scam, ton, olib beraman, konkurs, boshlandi, gift, premium, sovg'a, yozganga, sotiladi, ming.
4\uFE0F\u20E3 Shaxsiy adovat va diniy qarashlar haqida suhbat yuritish taqiqlanadi.
5\uFE0F\u20E3 Guruh a'zolarini hurmat qilgan holda guruhdan foydalanishingizni so'raymiz.

\u26A0\uFE0F Qoidabuzarlik uchun ogohlantirish, so'ngra vaqtinchalik cheklov (mute) qo'llaniladi.
\U0001F46E Cheklovni faqat guruh adminlari bekor qila oladi.
\U0001F4E2 Botdan foydalanish uchun @kotibchi kanaliga a'zo bo'lishingiz kerak.

Savol yoki shikoyatlar uchun: @uz_mp
"""


FEATURES_TEXT = """\u2699\uFE0F <b>Bot funksiyalari</b>

\U0001F6E1 Taqiqlangan so'zlarni avtomatik bloklaydi
\U0001F6AB Ketma-ket xabar (flood/spam) yuborishni cheklaydi
\U0001F464 Yangi a'zolarni captcha orqali tekshiradi
\U0001F4E2 Kanalga majburiy obunani tekshiradi
\U0001F46E Adminlar uchun: /ban /unban /mute /unmute /warn /warnings

Qoidalarni ko'rish uchun /qoidalar buyrug'ini yuboring.
"""


FEATURES_TEXT = """\u2699\uFE0F <b>Bot funksiyalari</b>

\U0001F6E1 Taqiqlangan so'zlarni avtomatik bloklaydi
\U0001F6AB Ketma-ket xabar (flood/spam) yuborishni cheklaydi
\U0001F464 Yangi a'zolarni captcha orqali tekshiradi
\U0001F4E2 Kanalga majburiy obunani tekshiradi
\U0001F46E Adminlar uchun: /ban /unban /mute /unmute /warn /warnings

Qoidalarni ko'rish uchun /qoidalar buyrug'ini yuboring.
"""

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tg_mod_bot")


def _load_warnings():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_warnings(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_warning(chat_id: int, user_id: int) -> int:
    data = _load_warnings()
    c, u = str(chat_id), str(user_id)
    data.setdefault(c, {})
    data[c][u] = data[c].get(u, 0) + 1
    _save_warnings(data)
    return data[c][u]


def get_warnings(chat_id: int, user_id: int) -> int:
    data = _load_warnings()
    return data.get(str(chat_id), {}).get(str(user_id), 0)


def reset_warnings(chat_id: int, user_id: int):
    data = _load_warnings()
    c, u = str(chat_id), str(user_id)
    if c in data and u in data[c]:
        data[c][u] = 0
        _save_warnings(data)


def contains_profanity(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(word.lower() in lowered for word in BANNED_WORDS)


def find_banned_word(text: str):
    if not text:
        return None
    lowered = text.lower()
    for word in BANNED_WORDS:
        if word.lower() in lowered:
            return word
    return None


async def is_user_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


captcha_router = Router()
pending_verification: set[tuple[int, int]] = set()


@captcha_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated, bot: Bot):
    chat_id = event.chat.id
    user = event.new_chat_member.user
    if user.is_bot:
        return

    try:
        await bot.restrict_chat_member(chat_id, user.id, permissions=ChatPermissions(can_send_messages=False))
    except Exception as e:
        logger.warning(f"Restrict qilib bo'lmadi: {e}")
        return

    pending_verification.add((chat_id, user.id))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Men robot emasman", callback_data=f"verify_{chat_id}_{user.id}")
    ]])
    msg = await bot.send_message(
        chat_id,
        f"👋 Xush kelibsiz, {user.full_name}!\n\n"
        f"Guruhda yozish uchun {CAPTCHA_TIMEOUT} soniya ichida pastdagi tugmani bosing.",
        reply_markup=keyboard,
    )

    await asyncio.sleep(CAPTCHA_TIMEOUT)

    if (chat_id, user.id) in pending_verification:
        pending_verification.discard((chat_id, user.id))
        try:
            await bot.ban_chat_member(chat_id, user.id)
            await bot.unban_chat_member(chat_id, user.id)
            await msg.edit_text(f"⛔ {user.full_name} vaqtida tasdiqlamadi va guruhdan chiqarildi.")
        except Exception as e:
            logger.warning(f"Kick qilib bo'lmadi: {e}")


@captcha_router.callback_query(F.data.startswith("verify_"))
async def on_verify_click(callback: CallbackQuery, bot: Bot):
    _, chat_id_str, user_id_str = callback.data.split("_")
    chat_id, user_id = int(chat_id_str), int(user_id_str)

    if callback.from_user.id != user_id:
        await callback.answer("Bu tugma sizga tegishli emas.", show_alert=True)
        return
    if (chat_id, user_id) not in pending_verification:
        await callback.answer("Tasdiqlash muddati allaqachon tugagan.", show_alert=True)
        return

    pending_verification.discard((chat_id, user_id))
    try:
        await bot.restrict_chat_member(
            chat_id, user_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_other_messages=True,
            ),
        )
    except Exception as e:
        logger.warning(f"Ruxsat berib bo'lmadi: {e}")

    await callback.message.edit_text(f"✅ {callback.from_user.full_name} tasdiqlandi. Xush kelibsiz!")
    await callback.answer("Tasdiqlandi!")


moderation_router = Router()
_recent_messages: dict[tuple[int, int], deque] = defaultdict(deque)


def _check_flood(chat_id: int, user_id: int, text_len: int) -> bool:
    if text_len < FLOOD_MIN_LENGTH:
        return False
    now = time.monotonic()
    key = (chat_id, user_id)
    dq = _recent_messages[key]
    dq.append(now)
    while dq and now - dq[0] > FLOOD_WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= FLOOD_MESSAGE_COUNT:
        dq.clear()
        return True
    return False


def _violation_keyboard(bot_username: str, chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{chat_id}_{user_id}"),
        InlineKeyboardButton(text="📋 Qoidalar", url=f"https://t.me/{bot_username}?start=qoidalar"),
    ]])


async def _restrict_user(bot: Bot, chat_id: int, user_id: int, minutes: int):
    until = int(time.time()) + minutes * 60
    await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)


@moderation_router.message(F.text | F.caption)
async def moderate_message(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return
    user = message.from_user
    if user is None or user.is_bot:
        return
    if await is_user_admin(bot, message.chat.id, user.id):
        return

    text = message.text or message.caption or ""
    mention = f"@{user.username}" if user.username else user.full_name
    me = await bot.get_me()
    keyboard = _violation_keyboard(me.username, message.chat.id, user.id)

    matched_word = find_banned_word(text)
    if matched_word:
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirib bo'lmadi: {e}")
        try:
            await _restrict_user(bot, message.chat.id, user.id, BANNED_WORD_MUTE_MINUTES)
        except Exception as e:
            logger.warning(f"Cheklab bo'lmadi: {e}")
            return
        await bot.send_message(
            message.chat.id,
            f"⚠️ {mention} ogohlantirildi va cheklandi.\n"
            f"Sababi: taqiqlangan so'z ishlatdi (\"{matched_word}\")\n"
            f"Holati: {BANNED_WORD_MUTE_MINUTES} daqiqalik yoza olmaslik rejimida",
            reply_markup=keyboard,
        )
        return

    if _check_flood(message.chat.id, user.id, len(text)):
        try:
            await _restrict_user(bot, message.chat.id, user.id, FLOOD_MUTE_MINUTES)
        except Exception as e:
            logger.warning(f"Cheklab bo'lmadi: {e}")
            return
        await bot.send_message(
            message.chat.id,
            f"🚫 {mention} cheklandi\n"
            f"Sababi: ketma-ket xabar yubordi\n"
            f"Holati: {FLOOD_MUTE_MINUTES} daqiqalik yoza olmaslik rejimida",
            reply_markup=keyboard,
        )
        return


@moderation_router.callback_query(F.data.startswith("cancel_"))
async def on_cancel_click(callback: CallbackQuery, bot: Bot):
    _, chat_id_str, user_id_str = callback.data.split("_")
    chat_id, user_id = int(chat_id_str), int(user_id_str)

    if not await is_user_admin(bot, chat_id, callback.from_user.id):
        await callback.answer("Bu tugmani faqat adminlar bosa oladi.", show_alert=True)
        return

    try:
        await bot.restrict_chat_member(
            chat_id, user_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_other_messages=True,
            ),
        )
    except Exception as e:
        logger.warning(f"Cheklovni bekor qilib bo'lmadi: {e}")
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    await callback.message.edit_text(
        callback.message.html_text + f"\n\n✅ Admin ({callback.from_user.full_name}) tomonidan bekor qilindi.",
        reply_markup=None,
    )
    await callback.answer("Cheklov bekor qilindi.")


admin_router = Router()


def _get_target(message: Message):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    return None


@admin_router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    if not await is_user_admin(bot, message.chat.id, message.from_user.id):
        return
    target = _get_target(message)
    if not target:
        await message.reply("Foydalanuvchini ban qilish uchun uning xabariga javob qilib /ban yozing.")
        return
    try:
        await bot.ban_chat_member(message.chat.id, target.id)
        await message.reply(f"🚫 {target.full_name} ban qilindi.")
    except Exception as e:
        await message.reply(f"Xatolik: {e}")


@admin_router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    if not await is_user_admin(bot, message.chat.id, message.from_user.id):
        return
    target = _get_target(message)
    if not target:
        await message.reply("Ban ochish uchun foydalanuvchining xabariga javob qilib /unban yozing.")
        return
    try:
        await bot.unban_chat_member(message.chat.id, target.id)
        await message.reply(f"✅ {target.full_name} uchun ban ochildi.")
    except Exception as e:
        await message.reply(f"Xatolik: {e}")


@admin_router.message(Command("mute"))
async def cmd_mute(message: Message, bot: Bot):
    if not await is_user_admin(bot, message.chat.id, message.from_user.id):
        return
    target = _get_target(message)
    if not target:
        await message.reply("Mute qilish uchun foydalanuvchining xabariga javob qilib /mute yozing.")
        return
    try:
        until = message.date + timedelta(hours=24)
        await bot.restrict_chat_member(
            message.chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until,
        )
        await message.reply(f"🔇 {target.full_name} 24 soatga mute qilindi.")
    except Exception as e:
        await message.reply(f"Xatolik: {e}")


@admin_router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    if not await is_user_admin(bot, message.chat.id, message.from_user.id):
        return
    target = _get_target(message)
    if not target:
        await message.reply("Mute ochish uchun foydalanuvchining xabariga javob qilib /unmute yozing.")
        return
    try:
        await bot.restrict_chat_member(
            message.chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_other_messages=True,
            ),
        )
        await message.reply(f"🔊 {target.full_name} uchun mute ochildi.")
    except Exception as e:
        await message.reply(f"Xatolik: {e}")


@admin_router.message(Command("warn"))
async def cmd_warn(message: Message, bot: Bot):
    if not await is_user_admin(bot, message.chat.id, message.from_user.id):
        return
    target = _get_target(message)
    if not target:
        await message.reply("Ogohlantirish berish uchun foydalanuvchining xabariga javob qilib /warn yozing.")
        return
    count = add_warning(message.chat.id, target.id)
    await message.reply(f"⚠️ {target.full_name} ogohlantirildi. Jami: {count}")


@admin_router.message(Command("warnings"))
async def cmd_warnings(message: Message):
    target = _get_target(message) or message.from_user
    count = get_warnings(message.chat.id, target.id)
    await message.reply(f"{target.full_name} uchun ogohlantirishlar soni: {count}")


@admin_router.message(Command("resetwarn"))
async def cmd_resetwarn(message: Message, bot: Bot):
    if not await is_user_admin(bot, message.chat.id, message.from_user.id):
        return
    target = _get_target(message)
    if not target:
        await message.reply("Tozalash uchun foydalanuvchining xabariga javob qilib /resetwarn yozing.")
        return
    reset_warnings(message.chat.id, target.id)
    await message.reply(f"✅ {target.full_name} uchun ogohlantirishlar tozalandi.")


@admin_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(
        "🤖 Bot buyruqlari (xabarga javob qilib yozing, faqat adminlar uchun):\n\n"
        "/ban /unban /mute /unmute /warn /warnings /resetwarn\n\n"
        "Bot avtomatik: taqiqlangan so'zlarni va ketma-ket xabar (flood) yuborishni cheklaydi, "
        "yangi a'zolarni captcha bilan tekshiradi."
    )


rules_router = Router()


@rules_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    if message.chat.type != "private":
        return

    arg = command.args or "none"

    if not await is_subscribed(bot, message.from_user.id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001F4E2 Kanalga a'zo bo'lish", url=CHANNEL_URL)],
            [InlineKeyboardButton(text="\u2705 Tekshirish", callback_data=f"checksub_{arg}")],
        ])
        await message.answer(
            "\U0001F512 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling, "
            "so'ngra \"\u2705 Tekshirish\" tugmasini bosing.",
            reply_markup=keyboard,
        )
        return

    if arg == "qoidalar":
        await message.answer(RULES_TEXT)
    else:
        await message.answer(
            "\U0001F44B Salom! Men guruhingizni nazorat qiluvchi botman.\n\n"
            "Pastdagi menyudan kerakli bo'limni tanlang.",
            reply_markup=MAIN_MENU,
        )


@rules_router.callback_query(F.data.startswith("checksub_"))
async def on_checksub(callback: CallbackQuery, bot: Bot):
    if not await is_subscribed(bot, callback.from_user.id):
        await callback.answer("Hali kanalga a'zo bo'lmagansiz!", show_alert=True)
        return

    arg = callback.data.split("_", 1)[1]

    if arg == "qoidalar":
        await callback.message.edit_text(RULES_TEXT)
    else:
        await callback.message.edit_text(
            "\u2705 Rahmat! Endi botdan to'liq foydalanishingiz mumkin.\n\n"
            "Qoidalarni ko'rish uchun /qoidalar buyrug'ini yuboring."
        )
    await callback.answer("Tasdiqlandi!")


@rules_router.message(Command("qoidalar"))
async def cmd_rules(message: Message):
    if message.chat.type == "private":
        await message.answer(RULES_TEXT)


@rules_router.callback_query(F.data == "show_rules")
async def on_show_rules(callback: CallbackQuery):
    await callback.message.edit_text(RULES_TEXT)
    await callback.answer()


@rules_router.callback_query(F.data == "show_features")
async def on_show_features(callback: CallbackQuery):
    await callback.message.edit_text(FEATURES_TEXT)
    await callback.answer()


@rules_router.message(Command("funksiyalar"))
async def cmd_features(message: Message, bot: Bot):
    me = await bot.get_me()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F4CB Qoidalar", url=f"https://t.me/{me.username}?start=qoidalar")],
    ])
    await message.answer(FEATURES_TEXT, reply_markup=keyboard)


@rules_router.message(F.text == "\U0001F4E2 Kanal")
async def on_menu_channel(message: Message):
    if message.chat.type != "private":
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F4E2 Kanalga o'tish", url=CHANNEL_URL)],
    ])
    await message.answer("Bizning kanal:", reply_markup=keyboard)


@rules_router.message(F.text == "\U0001F4CB Qoidalar")
async def on_menu_rules(message: Message):
    if message.chat.type != "private":
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F4D6 Qoidalarni o'qish", url=RULES_URL)],
    ])
    await message.answer("Guruh qoidalari:", reply_markup=keyboard)


@rules_router.message(F.text == "\U0001F198 Yordam")
async def on_menu_help(message: Message):
    if message.chat.type != "private":
        return
    await message.answer("Savol yoki shikoyatlar uchun: @uz_mp")


@rules_router.message(F.text == "\U0001F4F1 Telegram")
async def on_menu_telegram(message: Message):
    if message.chat.type != "private":
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F4F1 Ochish", url=EXTRA_LINK_URL)],
    ])
    await message.answer("Havola:", reply_markup=keyboard)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi! .env faylini yarating va BOT_TOKEN=... qiling "
            "(tokenni @BotFather dan oling)."
        )

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(admin_router)
    dp.include_router(rules_router)
    dp.include_router(captcha_router)
    dp.include_router(moderation_router)

    logger.info("Bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
