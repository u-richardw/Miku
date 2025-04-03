import asyncio
import random
import ollama
from twitchio.ext import commands

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token='1ashkq252nievdfihwpy491chkqmj2', prefix='!', initial_channels=['YOUR_TWITCH_CHANNEL'])

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'Connected to channel | {self.initial_channels[0]}')

    async def event_message(self, message):
        if message.author.name.lower() == self.nick.lower():
            return  # Ignore bot's own messages

        chat_message = f"{message.author.name}: {message.content}"
        print(chat_message)

        # Store chat messages for learning
        with open("chat_log.txt", "a", encoding="utf-8") as file:
            file.write(chat_message + "\n")

        # Generate AI response using fine-tuned Ollama model
        response = ollama.chat(model="my-chatbot", messages=[{"role": "user", "content": message.content}])
        reply = response['message']['content']

        await message.channel.send(reply)

bot = Bot()
bot.run()
