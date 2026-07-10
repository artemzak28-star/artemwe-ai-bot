import json
import logging
import os
from html import escape
from pathlib import Path

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

DATA_FILE = Path("mutes.json")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

# Формат:
# {
#   "business_connection_id": {
#       "owner_id": 123456,
#       "muted_chats": [111111, 222222]
#   }
# }
data = {}


def load_data():
    global data

    if not DATA_FILE.exists():
        data = {}
        return

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}


def save_data():
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "👋 Artemwe запущен.\n\n"
        "Подключите бота к Telegram Business и разрешите ему управление сообщениями."
    )


async def get_owner_id(
    context: ContextTypes.DEFAULT_TYPE,
    connection_id: str,
):
    connection_data = data.setdefault(
        connection_id,
        {
            "owner_id": None,
            "muted_chats": [],
        },
    )

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

    except TelegramError:
        return None


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

    # Если Telegram не разрешил редактировать сообщение,
    # удаляем команду и отправляем новый текст.
    try:
        await context.bot.delete_business_messages(
            business_connection_id=connection_id,
            message_ids=[message.message_id],
        )
    except TelegramError:
        pass

    try:
        await context.bot.send_message(
            chat_id=message.chat.id,
            text=new_text,
            business_connection_id=connection_id,
        )
    except TelegramError:
        pass


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
        if message.document.file_name:
            return f"📎 Файл: {message.document.file_name}"
        return "📎 Файл"

    if message.sticker:
        return "🖼 Стикер"

    if message.animation:
        return "🎞 GIF"

    if message.location:
        return "📍 Геолокация"

    if message.contact:
        return "👤 Контакт"

    return "Другое сообщение"


async def handle_business_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.business_message

    if not message or not message.business_connection_id:
        return

    connection_id = message.business_connection_id
    chat_id = message.chat.id

    owner_id = await get_owner_id(context, connection_id)

    if not owner_id:
        return

    connection_data = data.setdefault(
        connection_id,
        {
            "owner_id": owner_id,
            "muted_chats": [],
        },
    )

    muted_chats = connection_data.setdefault("muted_chats", [])

    # Сообщение отправил владелец Business-аккаунта
    is_owner_message = (
        message.from_user is not None
        and message.from_user.id == owner_id
    )

    if is_owner_message:
        command = (message.text or "").strip().lower()

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

    # Сообщение написал собеседник
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

    try:
        await context.bot.delete_business_messages(
            business_connection_id=connection_id,
            message_ids=[message.message_id],
        )
    except TelegramError as error:
        logging.error("Не удалось удалить сообщение: %s", error)
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
            "Владелец должен открыть бота Artemwe и нажать START."
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
