@dp.message(Command(commands=["clear_history"]))
async def cmd_clear_history(message: types.Message) -> None:
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        await db.commit()
    
    await message.answer("История очищена!")