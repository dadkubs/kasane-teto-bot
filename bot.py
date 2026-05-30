import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import random
import json
from openai import AsyncOpenAI
from collections import deque
from datetime import datetime


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")   # platform.deepseek.com


PLAYLISTS_FILE = "playlists.json"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# DeepSeek (для волн)
deepseek = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Состояние музыки 
queues:      dict[int, deque] = {}
now_playing: dict[int, dict]  = {}
loop_mode:   dict[int, str]   = {}
volumes:     dict[int, float] = {}
track_start: dict[int, float] = {}

#  Цвета / Emoji 
TETO_PINK  = 0xF4789A
TETO_DARK  = 0xC45C80
TETO_GREEN = 0x98E4B0
TETO_GOLD  = 0xFFD700

E = {
    "teto":    "🎀",
    "note":    "🎵",
    "skip":    "⏭️",
    "stop":    "⏹️",
    "queue":   "📋",
    "pause":   "⏸️",
    "play":    "▶️",
    "loop":    "🔁",
    "shuffle": "🔀",
    "save":    "💾",
    "load":    "📂",
    "vol":     "🔊",
    "bar_f":   "█",
    "bar_e":   "░",
}

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}



#  УТИЛИТЫ


def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "∞"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def progress_bar(elapsed: int, total: int, length: int = 12) -> str:
    if not total:
        return E["bar_f"] * length
    filled = int(length * min(elapsed / total, 1))
    return f"`{E['bar_f'] * filled}{E['bar_e'] * (length - filled)}`"


def get_elapsed(guild_id: int) -> int:
    start = track_start.get(guild_id)
    return 0 if start is None else int(datetime.now().timestamp() - start)


def get_queue(guild_id: int) -> deque:
    if guild_id not in queues:
        queues[guild_id] = deque()
    return queues[guild_id]


def get_volume(guild_id: int) -> float:
    return volumes.get(guild_id, 0.5)


def teto_embed(title: str, description: str = "", color=TETO_PINK) -> discord.Embed:
    return discord.Embed(title=f"{E['teto']} {title}", description=description, color=color)\
        .set_footer(
            text="Kasane Teto Bot ♪ ~Te-to-te-to~",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Kasane_Teto_icon.png/240px-Kasane_Teto_icon.png"
        )


def now_playing_embed(track: dict, guild_id: int, queued: int = 0) -> discord.Embed:
    elapsed  = get_elapsed(guild_id)
    total    = track.get("duration", 0)
    bar      = progress_bar(elapsed, total)
    loop     = loop_mode.get(guild_id, "off")
    vol      = int(get_volume(guild_id) * 100)
    loop_str = {"off": "выкл", "track": "🔂 трек", "queue": "🔁 очередь"}[loop]
    desc = (
        f"{E['note']} **[{track['title']}]({track['webpage']})**\n"
        f"👤 {track['uploader']}\n\n"
        f"{bar}  `{fmt_duration(elapsed)} / {fmt_duration(total)}`\n\n"
        f"{E['loop']} Повтор: **{loop_str}**  •  {E['vol']} **{vol}%**"
    )
    if queued:
        desc += f"  •  {E['queue']} В очереди: **{queued}**"
    embed = teto_embed("Сейчас играет~ 🎵", desc)
    if track.get("thumbnail"):
        embed.set_image(url=track["thumbnail"])
    return embed



#  ПЛЕЙЛИСТЫ


def load_playlists() -> dict:
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_playlists(data: dict):
    with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



#  КНОПКИ УПРАВЛЕНИЯ МУЗЫКОЙ


class MusicView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, custom_id="btn_pause")
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("Бот не в канале!", ephemeral=True); return
        if vc.is_playing():
            vc.pause()
            button.emoji = discord.PartialEmoji.from_str("▶️")
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        elif vc.is_paused():
            vc.resume()
            button.emoji = discord.PartialEmoji.from_str("⏸️")
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Ничего не играет!", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary, custom_id="btn_skip")
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message(embed=teto_embed("Пропущено!", "⏭️ Следующий трек~ ♪"), ephemeral=True)
        else:
            await interaction.response.send_message("Ничего не играет!", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="btn_loop")
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild.id
        nxt = {"off": "track", "track": "queue", "queue": "off"}[loop_mode.get(gid, "off")]
        loop_mode[gid] = nxt
        icons = {"off": ("🔁", discord.ButtonStyle.secondary), "track": ("🔂", discord.ButtonStyle.success), "queue": ("🔁", discord.ButtonStyle.primary)}
        button.emoji = discord.PartialEmoji.from_str(icons[nxt][0])
        button.style = icons[nxt][1]
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=teto_embed("Повтор!", f"🔁 Режим: **{{'off':'выкл','track':'трек','queue':'очередь'}}[nxt]**"), ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="btn_shuffle")
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(interaction.guild.id)
        if len(q) < 2:
            await interaction.response.send_message("Мало треков!", ephemeral=True); return
        lst = list(q); random.shuffle(lst)
        queues[interaction.guild.id] = deque(lst)
        await interaction.response.send_message(embed=teto_embed("Перемешано!", f"🔀 {len(lst)} треков~ ♪"), ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="btn_stop")
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild.id
        vc = interaction.guild.voice_client
        if vc:
            queues[gid] = deque(); loop_mode[gid] = "off"; now_playing.pop(gid, None)
            vc.stop(); await vc.disconnect()
        await interaction.response.send_message(embed=teto_embed("Стоп!", "⏹️ Teto уходит~ 👋"), ephemeral=True)



#  МУЗЫКА — ПОИСК И ВОСПРОИЗВЕДЕНИЕ


async def search_and_get_info(query: str) -> dict | None:
    loop = asyncio.get_event_loop()
    def _extract():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            if query.startswith("http"):
                info = ydl.extract_info(query, download=False)
            else:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if "entries" in info and info["entries"]:
                    info = info["entries"][0]
                else:
                    return None
            return info
    try:
        info = await loop.run_in_executor(None, _extract)
        if not info:
            return None
        return {
            "url":       info["url"],
            "title":     info.get("title", "Неизвестный трек"),
            "duration":  info.get("duration", 0),
            "webpage":   info.get("webpage_url", ""),
            "thumbnail": info.get("thumbnail", ""),
            "uploader":  info.get("uploader", "Неизвестно"),
        }
    except Exception as e:
        print(f"[yt-dlp error] {e}")
        return None


def play_next(guild: discord.Guild, voice_client: discord.VoiceClient):
    queue = get_queue(guild.id)
    lmode = loop_mode.get(guild.id, "off")
    if lmode == "track" and guild.id in now_playing:
        queue.appendleft(now_playing[guild.id])
    elif lmode == "queue" and guild.id in now_playing:
        queue.append(now_playing[guild.id])
    if not queue:
        now_playing.pop(guild.id, None); return
    track = queue.popleft()
    now_playing[guild.id] = track
    track_start[guild.id] = datetime.now().timestamp()
    source = discord.PCMVolumeTransformer(
        discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS),
        volume=get_volume(guild.id)
    )
    def after(error):
        if error:
            print(f"[Player error] {error}")
        asyncio.run_coroutine_threadsafe(_play_next_coro(guild, voice_client), bot.loop)
    voice_client.play(source, after=after)


async def _play_next_coro(guild, vc):
    play_next(guild, vc)



#  SLASH КОМАНДЫ — МУЗЫКА


@bot.tree.command(name="play", description="🎀 Воспроизвести музыку по запросу или ссылке")
@app_commands.describe(query="Название трека или YouTube ссылка")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Зайди в голосовой канал сначала! 🎀", TETO_DARK), ephemeral=True); return
    await interaction.response.defer()
    voice_channel = interaction.user.voice.channel
    guild = interaction.guild
    if guild.voice_client is None:
        try:
            vc = await voice_channel.connect()
        except Exception as e:
            await interaction.followup.send(embed=teto_embed("Ошибка!", f"Не могу подключиться: {e}", TETO_DARK)); return
    else:
        vc = guild.voice_client
        if vc.channel != voice_channel:
            await vc.move_to(voice_channel)

    msg = await interaction.followup.send(embed=teto_embed("Ищу трек...", f"{E['note']} **{query}**\n\n*Teto ищет для тебя~ 🎀*"))
    track = await search_and_get_info(query)
    if not track:
        await msg.edit(embed=teto_embed("Не найдено!", f"Ничего по запросу **{query}** 😢", TETO_DARK)); return

    queue = get_queue(guild.id)
    if vc.is_playing() or vc.is_paused():
        queue.append(track)
        embed = teto_embed("Добавлено в очередь!", f"{E['note']} **[{track['title']}]({track['webpage']})**\n👤 {track['uploader']} • ⏱️ {fmt_duration(track['duration'])}\n\nПозиция: **#{len(queue)}**")
        if track["thumbnail"]: embed.set_image(url=track["thumbnail"])
        await msg.edit(embed=embed)
    else:
        queue.append(track)
        play_next(guild, vc)
        current = now_playing.get(guild.id, track)
        await msg.edit(embed=now_playing_embed(current, guild.id, len(queue)), view=MusicView(guild.id))


@bot.tree.command(name="skip", description="⏭️ Пропустить текущий трек")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not (vc.is_playing() or vc.is_paused()):
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Сейчас ничего не играет!", TETO_DARK), ephemeral=True); return
    vc.stop()
    await interaction.response.send_message(embed=teto_embed("Пропущено!", f"{E['skip']} Следующий трек~ ♪"))


@bot.tree.command(name="stop", description="⏹️ Остановить и выйти из канала")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Бот не в канале!", TETO_DARK), ephemeral=True); return
    gid = interaction.guild.id
    queues[gid] = deque(); loop_mode[gid] = "off"; now_playing.pop(gid, None)
    vc.stop(); await vc.disconnect()
    await interaction.response.send_message(embed=teto_embed("Стоп!", f"{E['stop']} Очередь очищена, Teto уходит~ 👋"))


@bot.tree.command(name="pause", description="⏸️ Пауза / продолжить")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Бот не в канале!", TETO_DARK), ephemeral=True); return
    if vc.is_playing():
        vc.pause()
        await interaction.response.send_message(embed=teto_embed("Пауза!", f"{E['pause']} Teto отдыхает~ zzz"))
    elif vc.is_paused():
        vc.resume()
        await interaction.response.send_message(embed=teto_embed("Продолжаем!", f"{E['play']} Teto снова поёт~ ♪"))
    else:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Ничего не играет!", TETO_DARK), ephemeral=True)


@bot.tree.command(name="loop", description="🔁 Режим повтора")
@app_commands.describe(mode="Режим повтора")
@app_commands.choices(mode=[
    app_commands.Choice(name="Выключить", value="off"),
    app_commands.Choice(name="Повтор трека", value="track"),
    app_commands.Choice(name="Повтор очереди", value="queue"),
])
async def loop_cmd(interaction: discord.Interaction, mode: str):
    loop_mode[interaction.guild.id] = mode
    names = {"off": "выключен", "track": "🔂 повтор трека", "queue": "🔁 повтор очереди"}
    await interaction.response.send_message(embed=teto_embed("Повтор!", f"{E['loop']} Режим: **{names[mode]}**"))


@bot.tree.command(name="shuffle", description="🔀 Перемешать очередь")
async def shuffle(interaction: discord.Interaction):
    q = get_queue(interaction.guild.id)
    if len(q) < 2:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Мало треков!", TETO_DARK), ephemeral=True); return
    lst = list(q); random.shuffle(lst)
    queues[interaction.guild.id] = deque(lst)
    await interaction.response.send_message(embed=teto_embed("Перемешано!", f"{E['shuffle']} Очередь перемешана~ ({len(lst)} треков)"))


@bot.tree.command(name="queue", description="📋 Показать очередь треков")
async def queue_cmd(interaction: discord.Interaction):
    q = get_queue(interaction.guild.id)
    current = now_playing.get(interaction.guild.id)
    if not current and not q:
        await interaction.response.send_message(embed=teto_embed("Очередь пуста!", "Используй `/play` чтобы начать~ 🎀")); return
    lines = []
    if current:
        elapsed = get_elapsed(interaction.guild.id)
        total = current.get("duration", 0)
        lines.append(f"**{E['note']} Сейчас играет:**\n▶️ **[{current['title']}]({current['webpage']})**\n{progress_bar(elapsed, total, 10)} `{fmt_duration(elapsed)}/{fmt_duration(total)}`\n")
    if q:
        total_dur = sum(t.get("duration", 0) for t in q)
        lines.append(f"**{E['queue']} Очередь — {len(q)} треков (∑ {fmt_duration(total_dur)}):**")
        for i, track in enumerate(list(q)[:15], 1):
            lines.append(f"`{i:>2}.` [{track['title']}]({track['webpage']}) • `{fmt_duration(track['duration'])}`")
        if len(q) > 15:
            lines.append(f"*...и ещё {len(q) - 15} треков*")
    lmode = loop_mode.get(interaction.guild.id, "off")
    lines.append(f"\n{E['loop']} Повтор: **{{'off':'выкл','track':'🔂 трек','queue':'🔁 очередь'}}[lmode]**")
    await interaction.response.send_message(embed=teto_embed("Очередь треков~", "\n".join(lines)))


@bot.tree.command(name="nowplaying", description="🎵 Показать текущий трек")
async def nowplaying(interaction: discord.Interaction):
    current = now_playing.get(interaction.guild.id)
    if not current:
        await interaction.response.send_message(embed=teto_embed("Ничего не играет!", "Используй `/play` чтобы начать~ 🎀", TETO_DARK)); return
    q = get_queue(interaction.guild.id)
    await interaction.response.send_message(embed=now_playing_embed(current, interaction.guild.id, len(q)), view=MusicView(interaction.guild.id))


@bot.tree.command(name="volume", description="🔊 Громкость (0–100)")
@app_commands.describe(level="Уровень от 0 до 100")
async def volume(interaction: discord.Interaction, level: int):
    if not 0 <= level <= 100:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Громкость от 0 до 100!", TETO_DARK), ephemeral=True); return
    volumes[interaction.guild.id] = level / 100
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = level / 100
    bars = int(level / 10)
    await interaction.response.send_message(embed=teto_embed("Громкость!", f"{E['vol']} `{E['bar_f']*bars}{E['bar_e']*(10-bars)}` **{level}%**"))


@bot.tree.command(name="playlist_save", description="💾 Сохранить текущую очередь как плейлист")
@app_commands.describe(name="Название плейлиста")
async def playlist_save(interaction: discord.Interaction, name: str):
    q = list(get_queue(interaction.guild.id))
    cur = now_playing.get(interaction.guild.id)
    tracks = ([cur] if cur else []) + q
    if not tracks:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Очередь пуста!", TETO_DARK), ephemeral=True); return
    data = load_playlists()
    uid = str(interaction.user.id)
    if uid not in data: data[uid] = {}
    data[uid][name] = [{"title": t["title"], "webpage": t["webpage"], "duration": t["duration"], "uploader": t["uploader"], "thumbnail": t.get("thumbnail", "")} for t in tracks]
    save_playlists(data)
    await interaction.response.send_message(embed=teto_embed("Плейлист сохранён!", f"{E['save']} **{name}** — {len(tracks)} треков\n\nЗагрузи через `/playlist_load {name}`", TETO_GREEN))


@bot.tree.command(name="playlist_load", description="📂 Загрузить плейлист в очередь")
@app_commands.describe(name="Название плейлиста")
async def playlist_load(interaction: discord.Interaction, name: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(embed=teto_embed("Ошибка!", "Зайди в голосовой канал!", TETO_DARK), ephemeral=True); return
    data = load_playlists()
    playlist = data.get(str(interaction.user.id), {}).get(name)
    if not playlist:
        await interaction.response.send_message(embed=teto_embed("Не найдено!", f"Плейлист **{name}** не найден.", TETO_DARK), ephemeral=True); return
    await interaction.response.defer()
    msg = await interaction.followup.send(embed=teto_embed("Загружаю...", f"{E['load']} **{name}** — {len(playlist)} треков"))
    guild = interaction.guild
    vc = guild.voice_client or await interaction.user.voice.channel.connect()
    q = get_queue(guild.id)
    loaded = 0
    for t in playlist:
        track = await search_and_get_info(t["webpage"])
        if track: q.append(track); loaded += 1
    if not vc.is_playing() and not vc.is_paused():
        play_next(guild, vc)
    current = now_playing.get(guild.id)
    await msg.edit(embed=teto_embed("Плейлист загружен!", f"{E['load']} **{name}** — {loaded}/{len(playlist)} треков\n" + (f"{E['note']} Играет: **{current['title']}**" if current else ""), TETO_GREEN))


@bot.tree.command(name="playlist_list", description="📋 Мои сохранённые плейлисты")
async def playlist_list(interaction: discord.Interaction):
    playlists = load_playlists().get(str(interaction.user.id), {})
    if not playlists:
        await interaction.response.send_message(embed=teto_embed("Плейлисты", "Нет сохранённых плейлистов.\nСохрани через `/playlist_save`! 🎀")); return
    lines = [f"{E['save']} **{n}** — {len(t)} треков, ∑ {fmt_duration(sum(x.get('duration',0) for x in t))}" for n, t in playlists.items()]
    await interaction.response.send_message(embed=teto_embed("Мои плейлисты~", "\n".join(lines)))





#  AI — ВОЛНА / УМНЫЕ ПЛЕЙЛИСТЫ


async def deepseek_tracklist(prompt: str, count: int = 8) -> list[str]:
    """Просит DeepSeek составить список треков. Возвращает список строк 'исполнитель - трек'."""
    try:
        response = await deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": (
                    "Ты — музыкальный эксперт. Отвечай ТОЛЬКО списком треков, без пояснений. "
                    f"Формат: ровно {count} строк, каждая строка: Исполнитель - Название трека. "
                    "Никакого нумерации, никакого текста кроме треков. Только реальные существующие треки."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.85,
        )
        text = response.choices[0].message.content.strip()
        tracks = [line.strip() for line in text.split("\n") if line.strip() and " - " in line]
        return tracks[:count]
    except Exception as e:
        print(f"[DeepSeek tracklist error] {e}")
        return []


@bot.tree.command(name="vibe", description="🌊 Создать волну по описанию настроения и добавить в очередь")
@app_commands.describe(mood="Опиши волну: например 'грустный вечер дома' или 'качать в машине ночью'")
async def vibe(interaction: discord.Interaction, mood: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            embed=teto_embed("Ошибка!", "Зайди в голосовой канал~ 🎀", TETO_DARK), ephemeral=True
        ); return

    await interaction.response.defer()
    guild = interaction.guild

    # Подключаемся
    if guild.voice_client is None:
        try:
            vc = await interaction.user.voice.channel.connect()
        except Exception as e:
            await interaction.followup.send(embed=teto_embed("Ошибка!", str(e), TETO_DARK)); return
    else:
        vc = guild.voice_client

    msg = await interaction.followup.send(embed=teto_embed(
        "Подбираю волну~",
        f"🌊 **«{mood}»**\n\n*Teto спрашивает у DeepSeek какая музыка подойдёт...*"
    ))

    # DeepSeek подбирает треки
    track_names = await deepseek_tracklist(
        f"Подбери 8 треков для такого настроения/волны: {mood}. "
        "Учитывай жанр, темп, атмосферу. Разнообразные исполнители."
    )

    if not track_names:
        await msg.edit(embed=teto_embed("Ошибка!", "DeepSeek не смог подобрать треки 😢", TETO_DARK)); return

    await msg.edit(embed=teto_embed(
        "Нашла треки~ Загружаю...",
        f"🌊 **«{mood}»**\n\n" + "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(track_names)) +
        "\n\n*Ищу на YouTube...*"
    ))

    # Ищем каждый трек на YouTube
    q = get_queue(guild.id)
    loaded = []
    for name in track_names:
        track = await search_and_get_info(name)
        if track:
            q.append(track)
            loaded.append(track["title"])

    if not loaded:
        await msg.edit(embed=teto_embed("Ошибка!", "Не нашла треки на YouTube 😢", TETO_DARK)); return

    # Запускаем если ничего не играет
    if not vc.is_playing() and not vc.is_paused():
        play_next(guild, vc)

    current = now_playing.get(guild.id)
    desc = (
        f"🌊 **Волна: «{mood}»**\n"
        f"Загружено **{len(loaded)}** треков~\n\n" +
        "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(loaded)) +
        (f"\n\n{E['note']} Сейчас играет: **{current['title']}**" if current else "")
    )
    await msg.edit(embed=teto_embed("Волна запущена! 🌊", desc, TETO_GREEN))


@bot.tree.command(name="vibe_track", description="🌊 Создать волну похожих треков на основе текущего")
async def vibe_track(interaction: discord.Interaction):
    current = now_playing.get(interaction.guild.id)
    if not current:
        await interaction.response.send_message(
            embed=teto_embed("Ошибка!", "Сейчас ничего не играет! Запусти трек через `/play`~ 🎀", TETO_DARK),
            ephemeral=True
        ); return

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            embed=teto_embed("Ошибка!", "Зайди в голосовой канал~", TETO_DARK), ephemeral=True
        ); return

    await interaction.response.defer()
    guild = interaction.guild
    vc = guild.voice_client

    msg = await interaction.followup.send(embed=teto_embed(
        "Анализирую трек~",
        f"{E['note']} **{current['title']}**\n\n*Teto ищет похожую музыку...*"
    ))

    track_names = await deepseek_tracklist(
        f"Текущий трек: {current['title']} — {current['uploader']}. "
        "Подбери 8 похожих треков: такой же жанр, темп, настроение, эпоха. "
        "Не повторяй текущий трек."
    )

    if not track_names:
        await msg.edit(embed=teto_embed("Ошибка!", "Не смогла подобрать похожие треки 😢", TETO_DARK)); return

    await msg.edit(embed=teto_embed(
        "Нашла похожие~ Загружаю...",
        f"На основе: **{current['title']}**\n\n" +
        "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(track_names)) +
        "\n\n*Ищу на YouTube...*"
    ))

    q = get_queue(guild.id)
    loaded = []
    for name in track_names:
        track = await search_and_get_info(name)
        if track:
            q.append(track)
            loaded.append(track["title"])

    desc = (
        f"На основе: **{current['title']}**\n"
        f"Добавлено **{len(loaded)}** похожих треков~\n\n" +
        "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(loaded))
    )
    await msg.edit(embed=teto_embed("Волна по треку! 🌊", desc, TETO_GREEN))


@bot.tree.command(name="smartplaylist", description="💾 Создать и сохранить плейлист по описанию через AI")
@app_commands.describe(
    name="Название плейлиста",
    description="Опиши что хочешь: жанр, настроение, эпоха, активность"
)
async def smartplaylist(interaction: discord.Interaction, name: str, description: str):
    await interaction.response.defer()

    msg = await interaction.followup.send(embed=teto_embed(
        "Создаю плейлист~",
        f"{E['save']} **{name}**\n🎨 *{description}*\n\n*DeepSeek подбирает треки...*"
    ))

    track_names = await deepseek_tracklist(
        f"Составь плейлист из 10 треков: {description}. "
        "Разнообразные исполнители, хорошо подобранные под описание.",
        count=10
    )

    if not track_names:
        await msg.edit(embed=teto_embed("Ошибка!", "Не смогла составить плейлист 😢", TETO_DARK)); return

    await msg.edit(embed=teto_embed(
        "Нашла треки~ Сохраняю...",
        f"{E['save']} **{name}**\n\n" +
        "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(track_names)) +
        "\n\n*Сохраняю плейлист...*"
    ))

    # Сохраняем в playlists.json как поисковые запросы
    data = load_playlists()
    uid = str(interaction.user.id)
    if uid not in data: data[uid] = {}
    data[uid][name] = [
        {"title": t, "webpage": t, "duration": 0, "uploader": "AI", "thumbnail": "", "is_query": True}
        for t in track_names
    ]
    save_playlists(data)

    desc = (
        f"{E['save']} **{name}** сохранён!\n"
        f"🎨 *{description}*\n\n" +
        "\n".join(f"`{i+1}.` {t}" for i, t in enumerate(track_names)) +
        f"\n\nЗагрузи через `/playlist_load {name}`~"
    )
    await msg.edit(embed=teto_embed("Плейлист создан! 🎨", desc, TETO_GREEN))



@bot.tree.command(name="teto", description="🎀 Информация о боте")
async def teto_info(interaction: discord.Interaction):
    await interaction.response.send_message(embed=teto_embed(
        "Kasane Teto Bot",
        "**Привет! Я Kasane Teto Bot~ ♪**\n\n"
        "**🎵 Музыка:**\n"
        "`/play` — играть • `/skip` — пропустить • `/stop` — стоп\n"
        "`/pause` — пауза • `/loop` — повтор • `/shuffle` — перемешать\n"
        "`/queue` — очередь • `/nowplaying` — текущий трек • `/volume` — громкость\n"
        "`/playlist_save` • `/playlist_load` • `/playlist_list`\n\n"
        "**🌊 AI Волна:**\n"
        "`/vibe [настроение]` — волна по описанию\n"
        "`/vibe_track` — волна по текущему треку\n"
        "`/smartplaylist [название] [описание]` — AI плейлист\n\n"
        "*~Te-to-te-to~ ♪*"
    ))



#  СОБЫТИЯ


@bot.event
async def on_ready():
    print(f"[Teto Bot] Запущен как {bot.user} (ID: {bot.user.id})")
    print("[Teto Bot] Синхронизирую команды...")
    try:
        synced = await bot.tree.sync()
        print(f"[Teto Bot] Синхронизировано {len(synced)} команд!")
    except Exception as e:
        print(f"[Teto Bot] Ошибка синхронизации: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="~Te-to-te-to~ 🎀 /play"))
    print("[Teto Bot] Готов к работе! ~Te-to-te-to~ ♪")


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    vc = member.guild.voice_client
    if not vc: return
    if len([m for m in vc.channel.members if not m.bot]) == 0:
        await asyncio.sleep(30)
        if member.guild.voice_client and len([m for m in member.guild.voice_client.channel.members if not m.bot]) == 0:
            queues[member.guild.id] = deque()
            now_playing.pop(member.guild.id, None)
            await member.guild.voice_client.disconnect()


if __name__ == "__main__":
    bot.run(TOKEN)
