import asyncio
import json
import logging
import os
import random
import threading
import time
from html import escape
from pathlib import Path

import requests
from flask import Flask
from telegram import Update
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv(
    "SITE_URL",
    "https://artemwe-ai-bot-w2kq.onrender.com/",
)
PORT = int(os.getenv("PORT", "10000"))

DATA_FILE = Path("mutes.json")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

app = Flask(__name__)

TRICK_WORDS = [
    "бурмалда",
    "хрю-хрю",
    "пук-пук",
    "мур котик",
    "бананчик",
    "кря-кря",
    "пельмешек",
    "мяу-мяу",
    "арбузик",
    "огурчик",
    "чебурек",
    "пингвинчик",
]

# Формат:
# {
#   "business_connection_id": {
#       "owner_id": 123456,
#       "muted_chats": [111111],
#       "trick_chats": {
#           "222222": {
#               "last_prompt_id": 123,
#               "last_word": "бурмалда"
#           }
#       }
#   }
# }
data = {}


@app.get("/")
def home():
    return "Artemwe работает ✅", 200


@app.get("/health")
def health():
    return {"status": "ok"}, 200


def run_web_server():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


def self_ping():
    """Пингует сайт каждые 4 минуты, пока сервис уже запущен."""
    while True:
        time.sleep(240)

        try:
            response = requests.get(SITE_URL, timeout=20)
            logging.info("Автопинг: HTTP %s", response.status_code)
        except requests.RequestException as error:
            logging.warning("Ошибка автопинга: %s", error)


def start_keep_alive():
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()


def load_data():
    global data

    if not DATA_FILE.exists():
        data = {}
        return

    try:
        loaded = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        data = loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, OSError):
        data = {}


def save_data():
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_connection_data(connection_id: str):
    connection_data = data.setdefault(
        connection_id,
        {
            "owner_id": None,
            "muted_chats": [],
            "trick_chats": {},
        },
    )

    connection_data.setdefault("muted_chats", [])
    connection_data.setdefault("trick_chats", {})

    return connection_data


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "👋 Здравствуйте! Я Artemwe.\n\n"
        "🤖 Telegram Business бот.\n\n"
        "📋 Команды:\n"
        "🔇 /mute — замутить\n"
        "🔊 /unmute — снять мут\n"
        "🎭 /trick — включить розыгрыш\n"
        "❌ /untrick — выключить розыгрыш\n"
        "📢 /spam 5 Привет — отправить 5 сообщений\n"
        "📢 /spam 5 10 Привет — отправить 10 сообщений и удалить через 5 сек.\n\n"
        "🚀 Скоро появятся новые функции!"
    )


async def get_owner_id(
    context: ContextTypes.DEFAULT_TYPE,
    connection_id: str,
):
    connection_data = get_connection_data(connection_id)

    if connection_data.get("owner_id"):
        return connection_data["owner_id"]

    try:
        connection = await context.bot.get_business_connection(
            business_connection_id=connection_id
        )

        owner_id = connection.user.id
        connection_data["owner_id"] = owner_id
        save_data()

        return owner_id

    except TelegramError as error:
        logging.error("Не удалось получить владельца Business: %s", error)
        return None


async def delete_business_message(
    context: ContextTypes.DEFAULT_TYPE,
    connection_id: str,
    message_id: int,
):
    try:
        await context.bot.delete_business_messages(
            business_connection_id=connection_id,
            message_ids=[message_id],
        )
        return True
    except TelegramError as error:
        logging.warning("Не удалось удалить сообщение %s: %s", message_id, error)
        return False


async def replace_command(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    new_text: str,
):
    connection_id = message.business_connection_id

    try:
        await context.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=new_text,
            business_connection_id=connection_id,
        )
        return

    except BadRequest:
        pass

    await delete_business_message(
        context,
        connection_id,
        message.message_id,
    )

    try:
        await context.bot.send_message(
            chat_id=message.chat.id,
            text=new_text,
            business_connection_id=connection_id,
        )
    except TelegramError as error:
        logging.warning("Не удалось отправить замену команды: %s", error)


def get_message_content(message):
    if message.text:
        return message.text
    if message.caption:
        return message.caption
    if message.photo:
        return "📷 Фотография"
    if message.video:
        return "🎥 Видео"
    if message.voice:
        return "🎤 Голосовое сообщение"
    if message.video_note:
        return "⭕ Видеосообщение"
    if message.audio:
        return "🎵 Аудио"
    if message.document:
        return (
            f"📎 Файл: {message.document.file_name}"
            if message.document.file_name
            else "📎 Файл"
        )
    if message.sticker:
        return "🖼 Стикер"
    if message.animation:
        return "🎞 GIF"
    if message.location:
        return "📍 Геолокация"
    if message.contact:
        return "👤 Контакт"

    return "Другое сообщение"


async def enable_trick(message, context, connection_data):
    chat_key = str(message.chat.id)
    trick_chats = connection_data["trick_chats"]

    old = trick_chats.get(chat_key, {})
    old_prompt_id = old.get("last_prompt_id")

    if old_prompt_id:
        await delete_business_message(
            context,
            message.business_connection_id,
            old_prompt_id,
        )

    trick_chats[chat_key] = {
        "last_prompt_id": None,
        "last_word": None,
    }
    save_data()

    # Команда /trick просто исчезает.
    await delete_business_message(
        context,
        message.business_connection_id,
        message.message_id,
    )


async def disable_trick(message, context, connection_data):
    chat_key = str(message.chat.id)
    trick_info = connection_data["trick_chats"].pop(chat_key, None)

    if trick_info and trick_info.get("last_prompt_id"):
        await delete_business_message(
            context,
            message.business_connection_id,
            trick_info["last_prompt_id"],
        )

    save_data()

    # Команда выключения тоже исчезает.
    await delete_business_message(
        context,
        message.business_connection_id,
        message.message_id,
    )


async def handle_trick_message(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    connection_data,
):
    connection_id = message.business_connection_id
    chat_key = str(message.chat.id)
    trick_info = connection_data["trick_chats"].get(chat_key)

    if trick_info is None:
        return False

    # Удаляем сообщение собеседника.
    deleted = await delete_business_message(
        context,
        connection_id,
        message.message_id,
    )
    if not deleted:
        return True

    # Удаляем прошлую подсказку Artemwe.
    old_prompt_id = trick_info.get("last_prompt_id")
    if old_prompt_id:
        await delete_business_message(
            context,
            connection_id,
            old_prompt_id,
        )

        # Коротко показываем ошибку, потом удаляем её.
        try:
            error_message = await context.bot.send_message(
                chat_id=message.chat.id,
                text="❌ Ошибка. Кодовое слово не принято.",
                business_connection_id=connection_id,
            )
            await asyncio.sleep(1.2)
            await delete_business_message(
                context,
                connection_id,
                error_message.message_id,
            )
        except TelegramError as error:
            logging.warning("Не удалось показать ошибку розыгрыша: %s", error)

    previous_word = trick_info.get("last_word")
    available_words = [
        word for word in TRICK_WORDS
        if word != previous_word
    ]
    new_word = random.choice(available_words or TRICK_WORDS)

    prompt_text = (
        "⚠️ Собеседник не видит ваше сообщение! "
        "Чтобы ваше сообщение увидели, напишите: "
        f"«{new_word}»"
    )

    try:
        prompt = await context.bot.send_message(
            chat_id=message.chat.id,
            text=prompt_text,
            business_connection_id=connection_id,
        )

        trick_info["last_prompt_id"] = prompt.message_id
        trick_info["last_word"] = new_word
        save_data()

    except TelegramError as error:
        logging.error("Не удалось отправить текст розыгрыша: %s", error)

    return True



async def handle_spam_command(message, context):
    parts = (message.text or "").split()
    if len(parts) < 3:
        return False

    delete_after = None
    try:
        if len(parts) >= 4 and parts[1].isdigit() and parts[2].isdigit():
            delete_after = int(parts[1])
            count = int(parts[2])
            spam_text = " ".join(parts[3:])
        elif parts[1].isdigit():
            count = int(parts[1])
            spam_text = " ".join(parts[2:])
        else:
            return False
    except ValueError:
        return False

    count = max(1, min(count, 10))

    await delete_business_message(context, message.business_connection_id, message.message_id)

    ids=[]
    for _ in range(count):
        m=await context.bot.send_message(
            chat_id=message.chat.id,
            text=spam_text,
            business_connection_id=message.business_connection_id,
        )
        ids.append(m.message_id)

    if delete_after is not None:
        await asyncio.sleep(delete_after)
        for mid in ids:
            await delete_business_message(context, message.business_connection_id, mid)
    return True

async def handle_business_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.business_message

    if not message or not message.business_connection_id:
        return

    connection_id = message.business_connection_id
    chat_id = message.chat.id
    chat_key = str(chat_id)

    owner_id = await get_owner_id(context, connection_id)
    if not owner_id:
        return

    connection_data = get_connection_data(connection_id)
    muted_chats = connection_data["muted_chats"]

    is_owner_message = (
        message.from_user is not None
        and message.from_user.id == owner_id
    )

    if is_owner_message:
        command = (message.text or "").strip().lower()

        if command in ("/trick", ".trick"):
            await enable_trick(message, context, connection_data)
            return

        if command in (
            "/untrick",
            "/trickoff",
            ".untrick",
            ".trickoff",
        ):
            await disable_trick(message, context, connection_data)
            return

        if command.startswith("/spam") or command.startswith(".spam"):
            if await handle_spam_command(message, context):
                return

        if command in ("/mute", ".mute"):
            if chat_id not in muted_chats:
                muted_chats.append(chat_id)
                save_data()

            await replace_command(
                message,
                context,
                "🔇 Вы были замучены.",
            )
            return

        if command in ("/unmute", ".unmute"):
            if chat_id in muted_chats:
                muted_chats.remove(chat_id)
                save_data()

            await replace_command(
                message,
                context,
                "🔊 Вы были размучены.",
            )
            return

        return

    # Розыгрыш имеет приоритет над мутом.
    if chat_key in connection_data["trick_chats"]:
        await handle_trick_message(
            message,
            context,
            connection_data,
        )
        return

    if chat_id not in muted_chats:
        return

    content = get_message_content(message)
    user = message.from_user

    if user and user.username:
        user_name = f"@{user.username}"
    elif user:
        user_name = user.full_name
    else:
        user_name = "Пользователь"

    deleted = await delete_business_message(
        context,
        connection_id,
        message.message_id,
    )
    if not deleted:
        return

    notification = (
        f"🔇 <b>{escape(user_name)}</b> пытался вам написать\n\n"
        f"💬 <b>Текст:</b>\n"
        f"{escape(content)}"
    )

    try:
        await context.bot.send_message(
            chat_id=owner_id,
            text=notification,
            parse_mode="HTML",
        )
    except Forbidden:
        logging.warning(
            "Владелец должен открыть Artemwe и нажать START."
        )
    except TelegramError as error:
        logging.error("Ошибка отправки уведомления: %s", error)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logging.error(
        "Ошибка при обработке обновления:",
        exc_info=context.error,
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "Добавьте BOT_TOKEN в переменные окружения."
        )

    load_data()
    start_keep_alive()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(
            filters.UpdateType.BUSINESS_MESSAGE,
            handle_business_message,
        )
    )

    application.add_error_handler(error_handler)

    print("Artemwe запущен")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
