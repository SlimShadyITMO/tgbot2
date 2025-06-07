ADMIN_IDS = [123456789]  # Замени на свои ID

class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS

@dp.message(Command("stats_all"), IsAdmin())
async def cmd_stats_all(message: types.Message) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, title, COUNT(*) as count 
            FROM stats 
            GROUP BY user_id, title 
            ORDER BY count DESC
        """)
        rows = await cursor.fetchall()
    
    if not rows:
        await message.answer("Нет данных.")
        return
    
    text = "Общая статистика:\n"
    for user_id, title, count in rows:
        text += f"👤 {user_id}: {title} — {count}\n"
    
    await message.answer(text)