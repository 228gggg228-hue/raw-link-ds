import discord
import os
import aiohttp

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# ID канала, в котором бот будет работать
MY_CHANNEL_ID = 1558758327377338460


def to_raw(link: str) -> str:
    """Преобразует обычную ссылку GitHub в raw. Если уже raw — возвращает как есть."""
    if "raw.githubusercontent.com" in link:
        return link
    if "github.com" in link and "/blob/" in link:
        return link.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return link


def to_normal(link: str) -> str:
    """Преобразует raw-ссылку в обычную."""
    if "raw.githubusercontent.com" in link:
        rest = link.replace("https://raw.githubusercontent.com/", "")
        parts = rest.split("/")
        if len(parts) >= 4:
            owner = parts[0]
            repo = parts[1]
            branch = parts[2]
            path = "/".join(parts[3:])
            return f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    return link


def wrap_loadstring(link: str) -> str:
    """Оборачивает ссылку в loadstring, предварительно приведя её к raw."""
    raw_link = to_raw(link)
    return f'loadstring(game:HttpGet("{raw_link}"))()'


class ActionView(discord.ui.View):
    def __init__(self, link: str):
        super().__init__(timeout=None)
        self.link = link

    @discord.ui.button(label="Сделать raw", style=discord.ButtonStyle.primary)
    async def make_raw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(to_raw(self.link))

    @discord.ui.button(label="Сделать без raw", style=discord.ButtonStyle.success)
    async def make_normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(to_normal(self.link))

    @discord.ui.button(label="Отправить файл", style=discord.ButtonStyle.secondary)
    async def send_file(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        raw_link = to_raw(self.link)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(raw_link) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            f"❌ Не удалось получить файл (HTTP {resp.status})."
                        )
                        return
                    content = await resp.text()
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при скачивании: `{e}`")
            return

        filename = raw_link.split("/")[-1] or "file.txt"
        if not filename.endswith(".txt"):
            filename += ".txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        await interaction.followup.send(file=discord.File(filename))

    @discord.ui.button(label="loadstring", style=discord.ButtonStyle.danger)
    async def make_loadstring(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"```lua\n{wrap_loadstring(self.link)}\n```")


@client.event
async def on_ready():
    print(f'Бот {client.user} запущен и готов к работе!')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id != MY_CHANNEL_ID:
        return

    content = message.content.strip()

    if "githubusercontent.com" in content or ("github.com" in content and "/blob/" in content):
        view = ActionView(content)
        await message.reply("Что сделать с этой ссылкой?", view=view)


client.run(os.environ["DISCORD_BOT_TOKEN"])
