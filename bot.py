import discord
import os

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# ID канала, в котором бот будет работать
MY_CHANNEL_ID = 1558758327377338460


@client.event
async def on_ready():
    print(f'Бот {client.user} запущен и готов к работе!')


@client.event
async def on_message(message):
    # Игнорируем сообщения от самого бота
    if message.author == client.user:
        return

    # Проверяем: сообщение из нужного канала И содержит raw-ссылку
    if message.channel.id == MY_CHANNEL_ID and "raw.githubusercontent.com" in message.content:
        # Разбиваем ссылку на части
        parts = message.content.replace("https://raw.githubusercontent.com/", "").split("/")

        if len(parts) >= 4:
            owner = parts[0]
            repo = parts[1]
            branch = parts[2]
            file_path = "/".join(parts[3:])  # на случай подпапок в пути

            # Собираем обычную ссылку
            normal_link = f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}"

            await message.channel.send(normal_link)


# Токен берётся из переменной окружения (безопасно)
client.run(os.environ["DISCORD_BOT_TOKEN"])
