import discord
import os

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Бот {client.user} запущен и готов к работе!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if "raw.githubusercontent.com" in message.content:
        parts = message.content.replace("https://raw.githubusercontent.com/", "").split("/")
        
        if len(parts) >= 4:
            owner = parts[0]
            repo = parts[1]
            branch = parts[2]
            file_path = "/".join(parts[3:])
            
            normal_link = f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}"
            
            await message.channel.send(normal_link)

# Токен берётся из переменной окружения (безопасно)
client.run(os.environ["DISCORD_BOT_TOKEN"])
