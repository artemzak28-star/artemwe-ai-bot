import os
import threading
import time
import traceback
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PING_URL = "https://artemwe-ai-bot-e9yo.onrender.com/"

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

SYSTEM_PROMPT = """
Ты Artemwe — ИИ-помощник Артёма.
Пиши коротко, по-человечески, на русском.
Не пиши как ИИ.
Если человек не прав — спокойно возрази.
Не оскорбляй, но отвечай уверенно.
Помогай с Telegram, ботами, GitHub, Render, GMP, Stars и текстами.
"""

@app.route("/")
def home():
    return "Artemwe AI работает ✅"

def auto_ping():
    while True:
        try:
            requests.get(PING_URL, timeout=15)
            print("✅ Пинг успешный")
        except Exception as e:
            print("❌ Ошибка пинга:", e)
        time.sleep(240)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Artemwe AI.\n\n"
        "Пиши, что нужно — разберёмся."
    )

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    try:
        await update.message.chat.send_action("typing")

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ]
        )

        await update.message.reply_text(response.output_text)

    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text(f"Ошибка:\n{e}")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_ping, daemon=True).start()

    bot = ApplicationBuilder().token(BOT_TOKEN).build()

    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("🤖 Artemwe AI запущен")
    bot.run_polling()

if __name__ == "__main__":
    main()
