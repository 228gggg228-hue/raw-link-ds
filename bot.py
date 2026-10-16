import discord
import os
import re
import aiohttp

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MY_CHANNEL_ID = 1558758327377338460
GIF_URL = "https://i.imgur.com/iZuWJ2h.gif"
FILE_GIF_URL = "https://i.imgur.com/O7diHFX.gif"
PASTEFY_GIF_URL = "https://i.imgur.com/IzDu2Os.gif"
URL_PATTERN = re.compile(r'https?://[^\s<>"]+')


def to_raw(link: str) -> str:
    if "raw.githubusercontent.com" in link:
        return link
    if "github.com" in link and "/blob/" in link:
        return link.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "pastefy.app" in link and "/raw" not in link:
        return link.rstrip("/") + "/raw"
    if "pastebin.com" in link and "/raw/" not in link:
        paste_id = link.rstrip("/").split("/")[-1]
        return f"https://pastebin.com/raw/{paste_id}"
    if "gist.github.com" in link and "/raw" not in link:
        return link.rstrip("/") + "/raw"
    if "hastebin.com" in link and "/raw/" not in link:
        paste_id = link.rstrip("/").split("/")[-1]
        return f"https://hastebin.com/raw/{paste_id}"
    return link


def to_normal(link: str) -> str:
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


class LinkView(discord.ui.View):
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

    @discord.ui.button(label="В .lua", style=discord.ButtonStyle.secondary)
    async def send_lua(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        raw_link = to_raw(self.link)
        try:
            content = await fetch_content(raw_link)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при скачивании: `{e}`")
            return
        base = raw_link.split("/")[-1].split("?")[0] or "file"
        base = base.rsplit(".", 1)[0]
        filename = f"{base}.lua"
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


class FileView(discord.ui.View):
    def __init__(self, content: str, filename: str):
        super().__init__(timeout=None)
        self.content = content
        self.filename = filename

    @discord.ui.button(label="Сохранить в .txt", style=discord.ButtonStyle.secondary)
    async def save_txt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        base = (self.filename or "file").rsplit(".", 1)[0]
        txt_name = f"{base}.txt"
        with open(txt_name, "w", encoding="utf-8") as f:
            f.write(self.content)
        await interaction.followup.send(file=discord.File(txt_name))

    @discord.ui.button(label="Сохранить в .lua", style=discord.ButtonStyle.secondary)
    async def save_lua(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        base = (self.filename or "file").rsplit(".", 1)[0]
        lua_name = f"{base}.lua"
        with open(lua_name, "w", encoding="utf-8") as f:
            f.write(self.content)
        await interaction.followup.send(file=discord.File(lua_name))

    @discord.ui.button(label="Pastefy", style=discord.ButtonStyle.primary)
    async def make_pastefy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        filename = self.filename or "file.lua"
        try:
            paste_link = await upload_to_pastefy(self.content, filename)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка Pastefy: `{e}`")
            return
        view = LinkView(paste_link)
        embed = discord.Embed()
        embed.set_image(url=PASTEFY_GIF_URL)
        await interaction.followup.send(paste_link, view=view, embed=embed)


@client.event
async def on_ready():
    print(f'Бот {client.user} запущен и готов к работе!')


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != MY_CHANNEL_ID:
        return

    target = message
    if message.reference is not None:
        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message):
            target = resolved
        else:
            try:
                target = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                target = message

    content = (target.content or "").strip()

    if target.attachments:
        attachment = target.attachments[0]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        await message.reply(f"❌ Не удалось скачать файл (HTTP {resp.status}).")
                        return
                    file_content = await resp.text()
        except Exception as e:
            await message.reply(f"❌ Ошибка при скачивании файла: `{e}`")
            return

        view = FileView(file_content, attachment.filename)
        embed = discord.Embed()
        embed.set_image(url=FILE_GIF_URL)
        await message.reply("Что сделать с этим файлом?", view=view, embed=embed)
        return

    match = URL_PATTERN.search(content)
    if match:
        view = LinkView(match.group(0))
        embed = discord.Embed()
        embed.set_image(url=GIF_URL)
        await message.reply("Что сделать с этой ссылкой?", view=view, embed=embed)


client.run(os.environ["DISCORD_BOT_TOKEN"], reconnect=True)
