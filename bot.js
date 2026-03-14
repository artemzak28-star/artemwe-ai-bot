const TelegramBot = require("node-telegram-bot-api");
const OpenAI = require("openai");

const TELEGRAM_TOKEN = process.env.8696799139:AAF9PiXcHzw72yuF6fSSHMDXzFFGY7XXC10;
const OPENAI_API_KEY = process.env.https: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;

if (!TELEGRAM_TOKEN) {
  throw new Error("Нет BOT_TOKEN в Render Environment Variables");
}

if (!OPENAI_API_KEY) {
  throw new Error("Нет OPENAI_API_KEY в Render Environment Variables");
}

const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: true });
const client = new OpenAI({ apiKey: OPENAI_API_KEY });

// Простая память диалога по чатам
const chatMemory = new Map();
const MAX_MESSAGES = 12;

function getHistory(chatId) {
  if (!chatMemory.has(chatId)) {
    chatMemory.set(chatId, []);
  }
  return chatMemory.get(chatId);
}

function pushMessage(chatId, role, content) {
  const history = getHistory(chatId);
  history.push({ role, content });

  if (history.length > MAX_MESSAGES) {
    history.splice(0, history.length - MAX_MESSAGES);
  }
}

function clearHistory(chatId) {
  chatMemory.set(chatId, []);
}

bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;

  clearHistory(chatId);

  await bot.sendMessage(
    chatId,
    `👋 Привет!

Я *Artemwe AI*.

💬 Пиши мне вопросы
🤖 Я постараюсь ответить нормально и по делу

Команды:
/start — перезапуск
/reset — очистить память диалога`,
    { parse_mode: "Markdown" }
  );
});

bot.onText(/\/reset/, async (msg) => {
  const chatId = msg.chat.id;
  clearHistory(chatId);

  await bot.sendMessage(chatId, "🧹 Память диалога очищена");
});

bot.on("message", async (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;

  if (!text) return;
  if (text.startsWith("/start")) return;
  if (text.startsWith("/reset")) return;

  try {
    await bot.sendChatAction(chatId, "typing");

    const history = getHistory(chatId);

    const input = [
      {
        role: "system",
        content:
          "Тебя зовут Artemwe AI. Ты дружелюбный и умный Telegram-бот. Отвечай понятно, естественно и без лишнего пафоса. Если пользователь пишет коротко, тоже отвечай коротко. Пиши на русском, если пользователь пишет на русском."
      },
      ...history,
      {
        role: "user",
        content: text
      }
    ];

    const response = await client.responses.create({
      model: "gpt-5.4",
      input
    });

    const answer =
      response.output_text?.trim() || "Не получилось сформировать ответ.";

    pushMessage(chatId, "user", text);
    pushMessage(chatId, "assistant", answer);

    await bot.sendMessage(chatId, answer);
  } catch (error) {
    console.error("Ошибка AI:", error?.response?.data || error.message || error);
    await bot.sendMessage(chatId, "⚠️ Ошибка при ответе AI");
  }
});
