import discord
import os
import re
import aiohttp

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MY_CHANNEL_ID = 1558758327377338460
URL_PATTERN = re.compile(r'https?://[^\s<>"]+')


def to_raw(link: str) -> str:
    """Приводит ссылку к raw-формату для поддерживаемых сервисов."""
    # GitHub raw — уже raw
    if "raw.githubusercontent.com" in link:
        return link

    # GitHub обычная
    if "github.com" in link and "/blob/" in link:
        return link.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    # Pastefy
    if "pastefy.app" in link and "/raw" not in link:
        return link.rstrip("/") + "/raw"

    # Pastebin
    if "pastebin.com" in link and "/raw/" not in link:
        paste_id = link.rstrip("/").split("/")[-1]
        return f"https://pastebin.com/raw/{paste_id}"

    # GitHub Gist
    if "gist.github.com" in link and "/raw" not in link:
        return link.rstrip("/") + "/raw"

    # Hastebin
    if "hastebin.com" in link and "/raw/" not in link:
        paste_id = link.rstrip("/").split("/")[-1]
        return f"https://hastebin.com/raw/{paste_id}"

    return link


def to_normal(link: str) -> str:
    """Убирает raw-формат, возвращая обычную ссылку."""
    if "raw.githubusercontent.com" in link:
        rest = link.replace("https://raw.githubusercontent.com/", "")
        parts = rest.split("/")
        if len(parts) >= 4:
            owner, repo, branch = parts[0], parts[1], parts[2]
            path = "/".join(parts[3:])
            return f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"

    if "pastefy.app" in link and link.endswith("/raw"):
        return link[:-4]

    if "pastebin.com/raw/" in link:
        paste_id = link.rstrip("/").split("/")[-1]
        return f"https://pastebin.com/{paste_id}"

    if "gist.githubusercontent.com" in link:
        # https://gist.githubusercontent.com/user/id/raw/... -> https://gist.github.com/user/id
        parts = link.replace("https://gist.githubusercontent.com/", "").split("/")
        if len(parts) >= 2:
            return f"https://gist.github.com/{parts[0]}/{parts[1]}"

    if "hastebin.com/raw/" in link:
        paste_id = link.rstrip("/").split("/")[-1]
        return f"https://hastebin.com/{paste_id}"

    return link


def wrap_loadstring(link: str) -> str:
    raw_link = to_raw(link)
    return f'loadstring(game:HttpGet("{raw_link}"))()'


async def fetch_content(link: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(link) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}")
            return await resp.text()


async def upload_to_pastefy(content: str, filename: str = "file.lua") -> str:
    url = "https://pastefy.app/api/v2/paste"
    payload = {"content": content, "title": filename, "visibility": "UNLISTED"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise Exception(f"Pastefy HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
            paste_id = data.get("paste", {}).get("id") or data.get("id")
            if not paste_id:
                raise Exception(f"Не удалось получить ID: {data}")
            return f"https://pastefy.app/{paste_id}"


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
            content = await fetch_content(raw_link)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при скачивании: `{e}`")
            return

        filename = raw_link.split("/")[-1].split("?")[0] or "file.txt"
        if "." not in filename:
            filename += ".txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        await interaction.followup.send(file=discord.File(filename))

    @discord.ui.button(label="loadstring", style=discord.ButtonStyle.danger)
    async def make_loadstring(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(wrap_loadstring(self.link))

    @discord.ui.button(label="Pastefy", style=discord.ButtonStyle.primary, row=1)
    async def make_pastefy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        raw_link = to_raw(self.link)
        try:
            content = await fetch_content(raw_link)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при скачивании: `{e}`")
            return

        filename = raw_link.split("/")[-1].split("?")[0] or "file.lua"
        try:
            paste_link = await upload_to_pastefy(content, filename)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка Pastefy: `{e}`")
            return
        await interaction.followup.send(paste_link)


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
    match = URL_PATTERN.search(content)
    if match:
        view = ActionView(match.group(0))
        await message.reply("Что сделать с этой ссылкой?", view=view)


client.run(os.environ["DISCORD_BOT_TOKEN"])
