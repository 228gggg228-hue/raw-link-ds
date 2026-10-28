import discord
import os
import re
import aiohttp
import zipfile
import rarfile
import io

# === ПРИНУДИТЕЛЬНАЯ НАСТРОЙКА ДЛЯ RAR ===
rarfile.UNRAR_TOOL = "unar"  # Указываем unar как основной
rarfile.SEVENZIP_TOOL = "7z" # Запасной вариант

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MY_CHANNEL_ID = 1558758327377338460
GIF_URL = "https://i.imgur.com/iZuWJ2h.gif"
FILE_GIF_URL = "https://i.imgur.com/O7diHFX.gif"
PASTEFY_GIF_URL = "https://i.imgur.com/IzDu2Os.gif"
URL_PATTERN = re.compile(r'https?://[^\s<>"]+')


def to_raw(link: str) -> str:
    if "raw.githubusercontent.com" in link: return link
    if "github.com" in link and "/blob/" in link:
        return link.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "pastefy.app" in link and "/raw" not in link: return link.rstrip("/") + "/raw"
    if "pastebin.com" in link and "/raw/" not in link:
        return f"https://pastebin.com/raw/{link.rstrip('/').split('/')[-1]}"
    return link


def to_normal(link: str) -> str:
    if "raw.githubusercontent.com" in link:
        parts = link.replace("https://raw.githubusercontent.com/", "").split("/")
        if len(parts) >= 4: return f"https://github.com/{parts[0]}/{parts[1]}/blob/{parts[2]}/{'/'.join(parts[3:])}"
    if "pastefy.app" in link and link.endswith("/raw"): return link[:-4]
    return link


def wrap_loadstring(link: str) -> str:
    return f'loadstring(game:HttpGet("{to_raw(link)}"))()'


async def fetch_content(link: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(link) as resp:
            if resp.status != 200: raise Exception(f"HTTP {resp.status}")
            return await resp.text()


async def upload_to_pastefy(content: str, filename: str = "file.lua") -> str:
    url = "https://pastefy.app/api/v2/paste"
    payload = {"content": content, "title": filename, "visibility": "UNLISTED"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status not in (200, 201): raise Exception(f"Pastefy HTTP {resp.status}")
            data = await resp.json()
            paste_id = data.get("paste", {}).get("id") or data.get("id")
            return f"https://pastefy.app/{paste_id}"


# --- УНИВЕРСАЛЬНЫЙ ПРОСМОТРЩИК АРХИВОВ ---
class ZipSelect(discord.ui.Select):
    def __init__(self, files_data):
        self.files_data = files_data
        options = []
        for name in list(files_data.keys())[:25]:
            options.append(discord.SelectOption(label=name[:100], description="Нажми, чтобы посмотреть"))
        super().__init__(placeholder="Выбери файл из архива...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen_file = self.values[0]
        content_bytes = self.files_data[chosen_file]
        
        try:
            text_content = content_bytes.decode('utf-8')
            if len(text_content) > 1900:
                filename = f"{chosen_file.split('/')[-1]}.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(text_content)
                await interaction.response.send_message(f"📄 Файл `{chosen_file}` слишком большой, вот он в .txt:", file=discord.File(filename))
            else:
                await interaction.response.send_message(f"📄 **Содержимое {chosen_file}:**\n```\n{text_content}\n```")
        except UnicodeDecodeError:
            await interaction.response.send_message(f"❌ Файл `{chosen_file}` — бинарный, не могу показать текст.")

class ZipView(discord.ui.View):
    def __init__(self, files_data):
        super().__init__(timeout=300)
        self.add_item(ZipSelect(files_data))

class ZipFileView(discord.ui.View):
    def __init__(self, content_bytes, filename):
        super().__init__(timeout=None)
        self.content_bytes = content_bytes
        self.filename = filename

    @discord.ui.button(label="📦 Открыть Архив", style=discord.ButtonStyle.primary)
    async def open_zip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        files_data = {}
        
        try:
            if self.filename.lower().endswith('.rar'):
                with rarfile.RarFile(io.BytesIO(self.content_bytes)) as rf:
                    for file_info in rf.infolist():
                        if not file_info.isdir():
                            files_data[file_info.filename] = rf.read(file_info.filename)
            else:
                with zipfile.ZipFile(io.BytesIO(self.content_bytes)) as z:
                    for file_info in z.infolist():
                        if not file_info.is_dir():
                            files_data[file_info.filename] = z.read(file_info.filename)
            
            if not files_data:
                await interaction.followup.send("❌ Архив пуст.")
                return

            view = ZipView(files_data)
            await interaction.followup.send(f"📦 **Файлы в архиве `{self.filename}`:**\nВыбери файл из списка ниже:", view=view)
            
        except (zipfile.BadZipFile, rarfile.BadRarFile):
            await interaction.followup.send("❌ Это не архив или он поврежден.")
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при чтении архива: `{e}`")


# --- ОБЫЧНЫЕ VIEW (для текста и ссылок) ---
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
        with open(txt_name, "w", encoding="utf-8") as f: f.write(self.content)
        await interaction.followup.send(file=discord.File(txt_name))

    @discord.ui.button(label="Сохранить в .lua", style=discord.ButtonStyle.secondary)
    async def save_lua(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        base = (self.filename or "file").rsplit(".", 1)[0]
        lua_name = f"{base}.lua"
        with open(lua_name, "w", encoding="utf-8") as f: f.write(self.content)
        await interaction.followup.send(file=discord.File(lua_name))

    @discord.ui.button(label="Pastefy", style=discord.ButtonStyle.primary)
    async def make_pastefy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            paste_link = await upload_to_pastefy(self.content, self.filename or "file.lua")
            view = LinkView(paste_link)
            embed = discord.Embed(); embed.set_image(url=PASTEFY_GIF_URL)
            await interaction.followup.send(paste_link, view=view, embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка Pastefy: `{e}`")


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
        try:
            content = await fetch_content(to_raw(self.link))
            filename = to_raw(self.link).split("/")[-1].split("?")[0] or "file.txt"
            if "." not in filename: filename += ".txt"
            with open(filename, "w", encoding="utf-8") as f: f.write(content)
            await interaction.followup.send(file=discord.File(filename))
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при скачивании: `{e}`")

    @discord.ui.button(label="В .lua", style=discord.ButtonStyle.secondary)
    async def send_lua(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            content = await fetch_content(to_raw(self.link))
            base = to_raw(self.link).split("/")[-1].split("?")[0] or "file"
            filename = f"{base.rsplit('.', 1)[0]}.lua"
            with open(filename, "w", encoding="utf-8") as f: f.write(content)
            await interaction.followup.send(file=discord.File(filename))
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при скачивании: `{e}`")

    @discord.ui.button(label="loadstring", style=discord.ButtonStyle.danger)
    async def make_loadstring(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(wrap_loadstring(self.link))

    @discord.ui.button(label="Pastefy", style=discord.ButtonStyle.primary, row=1)
    async def make_pastefy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            content = await fetch_content(to_raw(self.link))
            filename = to_raw(self.link).split("/")[-1].split("?")[0] or "file.lua"
            paste_link = await upload_to_pastefy(content, filename)
            await interaction.followup.send(paste_link)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка Pastefy: `{e}`")


@client.event
async def on_ready():
    print(f'Бот {client.user} запущен и готов к работе!')


@client.event
async def on_message(message):
    if message.author == client.user: return
    if message.channel.id != MY_CHANNEL_ID: return

    target = message
    if message.reference is not None:
        resolved = message.reference.resolved
        target = resolved if isinstance(resolved, discord.Message) else await message.channel.fetch_message(message.reference.message_id)

    content = (target.content or "").strip()

    if target.attachments:
        attachment = target.attachments[0]
        
        if attachment.filename.lower().endswith(('.zip', '.rar')):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status != 200: return
                        raw_bytes = await resp.read()
            except Exception: return
            
            view = ZipFileView(raw_bytes, attachment.filename)
            embed = discord.Embed(title="📦 Архив", description="Нажми на кнопку, чтобы просмотреть файлы.")
            await message.reply(f"Обнаружен архив `{attachment.filename}`!", view=view, embed=embed)
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200: return
                    file_content = (await resp.read()).decode('utf-8')
        except UnicodeDecodeError:
            await message.reply("❌ Файл бинарный, не могу прочитать.")
            return
        except Exception: return

        view = FileView(file_content, attachment.filename)
        embed = discord.Embed(); embed.set_image(url=FILE_GIF_URL)
        await message.reply("Что сделать с этим файлом?", view=view, embed=embed)
        return

    match = URL_PATTERN.search(content)
    if match:
        link = match.group(0)
        
        if link.lower().endswith(('.zip', '.rar')):
            await message.reply("⏳ Скачиваю архив по ссылке...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status != 200:
                            await message.reply(f"❌ Не удалось скачать (HTTP {resp.status})")
                            return
                        raw_bytes = await resp.read()
                
                filename = link.split("/")[-1].split("?")[0]
                view = ZipFileView(raw_bytes, filename)
                embed = discord.Embed(title="📦 Архив по ссылке", description="Нажми на кнопку, чтобы просмотреть файлы.")
                await message.reply("Обнаружен архив!", view=view, embed=embed)
            except Exception as e:
                await message.reply(f"❌ Ошибка: `{e}`")
            return

        view = LinkView(link)
        embed = discord.Embed(); embed.set_image(url=GIF_URL)
        await message.reply("Что сделать с этой ссылкой?", view=view, embed=embed)


client.run(os.environ["DISCORD_BOT_TOKEN"], reconnect=True)
