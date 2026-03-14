const TelegramBot = require("node-telegram-bot-api");
const OpenAI = require("openai");

const bot = new TelegramBot(process.env.BOT_TOKEN, { polling: true });

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

bot.on("message", async (msg) => {

  const chatId = msg.chat.id;
  const text = msg.text;

  if (!text) return;

  try {

    const response = await openai.chat.completions.create({
      model: "gpt-4.1-mini",
      messages: [
        { role: "system", content: "Ты AI помощник по имени Artemwe." },
        { role: "user", content: text }
      ]
    });

    const reply = response.choices[0].message.content;

    bot.sendMessage(chatId, reply);

  } catch (error) {

    console.log(error);
    bot.sendMessage(chatId, "Ошибка AI 🤖");

  }

});
