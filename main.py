import os
import logging
import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from parsing import search_movie_info  # type: ignore
from dotenv import load_dotenv
load_dotenv()



TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print(f'{TOKEN=}')
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_PATH = "movie_bot.db"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                timestamp TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                user_id INTEGER,
                title TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, title)
            )
        """)
        await db.commit()

@dp.message(Command(commands=["help"]))
async def cmd_help(message: types.Message) -> None:
    await message.answer(
        "/start — старт бота\n"
        "/help — помощь\n"
        "Просто отправь название фильма/сериала\n"
        "Команды:\n"
        "/history — история твоих запросов\n"
        "/stats — статистика просмотров"
    )


@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "Привет, я кино-бот! Просто напиши название фильма или сериала, "
        "и я найду описание, рейтинг и ссылку для бесплатного просмотра."
    )


@dp.message(Command(commands=["history"]))
async def cmd_history(message: types.Message) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT title, timestamp FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user_id,)
        )
        rows = await cursor.fetchall()
    if not rows:
        await message.answer("Ты пока ничего не искал.")
        return
    text = "Твоя история запросов (последние 20):\n"
    for title, timestamp in rows:
        dt = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        text += f"{dt} — {title}\n"
    await message.answer(text)


@dp.message(Command(commands=["stats"]))
async def cmd_stats(message: types.Message) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT title, count FROM stats WHERE user_id = ? ORDER BY count DESC LIMIT 20", (user_id,)
        )
        rows = await cursor.fetchall()
    if not rows:
        await message.answer("Нет данных по просмотрам.")
        return
    text = "Статистика по просмотрам:\n"
    for title, count in rows:
        text += f"{title}: {count}\n"
    await message.answer(text)


@dp.message()
async def handle_movie_search(message: types.Message) -> None:
    if not message.from_user:
        return
    if not message.text:
        await message.answer("Напишите название фильма для поиска")
        return
    title = message.text.strip()
    user_id = message.from_user.id

    logging.info(f"Пользователь {user_id} запросил фильм: {title}")

    try:
        info = await search_movie_info(title)
    except Exception as e:
        logging.error(f"Ошибка при поиске информации: {e}")
        await message.answer("Что-то сломалось на поиске. Попробуй позже.")
        return

    timestamp = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history (user_id, title, timestamp) VALUES (?, ?, ?)",
            (user_id, title, timestamp)
        )
        cursor = await db.execute(
            "SELECT count FROM stats WHERE user_id = ? AND title = ?", (user_id, info.get("title", title))
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE stats SET count = count + 1 WHERE user_id = ? AND title = ?",
                (user_id, info.get("title", title))
            )
        else:
            await db.execute(
                "INSERT INTO stats (user_id, title, count) VALUES (?, ?, 1)",
                (user_id, info.get("title", title))
            )
        await db.commit()

    text = (
        f"<b>{info.get('title')}</b>\n\n"
        f"{info.get('description')}\n\n"
        f"Жанр: {info.get('genre')}\n"
        f"Год: {info.get('year')}\n"
        f"Длительность: {info.get('runtime')}\n"
        f"Рейтинг: {info.get('rating')}\n\n"
    )

    if info.get("link"):
        text += f'<a href="{info["link"]}">Смотреть</a>'
    else:
        text += "Ссылка на просмотр не найдена."

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)


async def main() -> None:
    await init_db()
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())