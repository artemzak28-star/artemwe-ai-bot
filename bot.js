const TelegramBot = require('node-telegram-bot-api');

const token = process.env.BOT_TOKEN;

const bot = new TelegramBot(token, { polling: true });

bot.onText(/\/start/, (msg) => {

bot.sendMessage(
msg.chat.id,
`👋 Привет!

Я *Artemwe* — AI помощник.

💬 Можешь писать мне любой вопрос
🤖 Я постараюсь помочь!`,
{
parse_mode:"Markdown"
}
);

});

bot.on("message", async (msg) => {

if(msg.text === "/start") return;

const chatId = msg.chat.id;
const text = msg.text;

if(!text) return;

try{

const reply = `🤖 Artemwe думает...

Ты написал:
"${text}"

Пока что я простой AI бот, но скоро стану умнее 😎`;

bot.sendMessage(chatId, reply);

}catch(err){

bot.sendMessage(chatId,"⚠️ Ошибка");

}

});
