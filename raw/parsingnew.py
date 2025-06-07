from datetime import datetime, timedelta

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = timedelta(hours=1)  # Время жизни записи

async def search_movie_info(title: str) -> Dict[str, Any]:
    title_key = title.lower().strip()
    
    # Проверяем TTL
    if title_key in CACHE:
        cached_time = CACHE[title_key].get("cache_time")
        if cached_time and datetime.now() - datetime.fromisoformat(cached_time) < CACHE_TTL:
            return CACHE[title_key]
        else:
            del CACHE[title_key]  # Удаляем просроченный кэш

    # ... остальная логика функции ...

    # Добавляем время сохранения в кэш
    info["cache_time"] = datetime.now().isoformat()
    CACHE[title_key] = info
    return info