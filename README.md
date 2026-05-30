<div align="center">

<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Kasane_Teto_icon.png/240px-Kasane_Teto_icon.png" width="120" alt="Kasane Teto"/>

# 🎀 Kasane Teto Music Bot

**Музыкальный Discord бот с AI-волнами в стиле Kasane Teto**

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord)
![DeepSeek](https://img.shields.io/badge/AI-DeepSeek-orange?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

*~Te-to-te-to~ ♪*

</div>

---

## ✨ Возможности

### 🎵 Музыка
- Воспроизведение по названию или YouTube ссылке
- Очередь треков с прогресс-баром и таймером
- Кнопки управления прямо под сообщением (пауза, скип, стоп, loop, shuffle)
- Режимы повтора: трек / вся очередь
- Регулировка громкости
- Сохранение и загрузка плейлистов

### 🌊 AI Волна (DeepSeek)
- **`/vibe`** — подбирает треки под твоё настроение
- **`/vibe_track`** — строит волну похожих треков на основе текущего
- **`/smartplaylist`** — создаёт и сохраняет плейлист по описанию

---

## 🎮 Команды

### Музыка
| Команда | Описание |
|---|---|
| `/play [запрос]` | Воспроизвести трек по названию или ссылке |
| `/skip` | Пропустить текущий трек |
| `/stop` | Остановить и выйти из канала |
| `/pause` | Пауза / продолжить |
| `/loop [режим]` | Повтор: выкл / трек / очередь |
| `/shuffle` | Перемешать очередь |
| `/queue` | Показать очередь треков |
| `/nowplaying` | Текущий трек с прогресс-баром |
| `/volume [0-100]` | Изменить громкость |
| `/playlist_save [название]` | Сохранить очередь как плейлист |
| `/playlist_load [название]` | Загрузить плейлист |
| `/playlist_list` | Мои плейлисты |

### 🌊 AI Волна
| Команда | Описание |
|---|---|
| `/vibe [настроение]` | Подобрать треки под описание и запустить |
| `/vibe_track` | Волна похожих треков на основе текущего |
| `/smartplaylist [название] [описание]` | Создать AI плейлист и сохранить |

**Примеры:**
```
/vibe грустный дождливый вечер дома
/vibe энергия для тренировки
/vibe ночная поездка в машине
/vibe_track
/smartplaylist лоуфай описание: расслабленный лоуфай для учёбы
```

---

## ⚙️ Установка

### 1. Требования
- Python 3.10+
- FFmpeg

**Установка FFmpeg:**
- **Windows:** скачай с [ffmpeg.org](https://ffmpeg.org/download.html), добавь в PATH
- **Linux:** `sudo apt install ffmpeg`
- **macOS:** `brew install ffmpeg`

### 2. Клонируй репозиторий
```bash
git clone https://github.com/ТВО_ИМЯ/kasane-teto-bot.git
cd kasane-teto-bot
```

### 3. Установи зависимости
```bash
pip install -r requirements.txt
```

### 4. Настрой токены

Открой `bot.py` и вставь свои ключи:
```python
TOKEN            = "ВАШ_DISCORD_ТОКЕН"
DEEPSEEK_API_KEY = "ВАШ_DEEPSEEK_КЛЮЧ"
```

**Где взять:**
- Discord токен: [discord.com/developers](https://discord.com/developers/applications)
- DeepSeek API: [platform.deepseek.com](https://platform.deepseek.com)

### 5. Запусти бота
```bash
python bot.py
```

---

## 🔧 Настройка Discord бота

1. Зайди на [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → дай название
3. Слева → **Bot** → скопируй токен
4. Включи **Privileged Gateway Intents**: ✅ Presence, ✅ Server Members, ✅ Message Content
5. **OAuth2** → **URL Generator** → выбери `bot` + `applications.commands`
6. Права: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `View Channels`
7. Скопируй ссылку и добавь бота на сервер

---

## 📦 Зависимости

```
discord.py>=2.3.0
yt-dlp>=2024.1.1
PyNaCl>=1.5.0
openai>=1.0.0
httpx>=0.25.0
```

---

## 📄 Лицензия

MIT License — используй свободно.

---

<div align="center">

Made with dadkub🎀 by Kasane Teto fans

*~Te-to-te-to~ ♪*

</div>
