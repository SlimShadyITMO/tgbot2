import aiohttp
import asyncio
import logging
import os
import typing as tp
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

CACHE: Dict[str, Dict[str, Any]] = {}

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
KINOPOISK_UNOFFICIAL_API_KEY = os.getenv("KINOPOISK_UNOFFICIAL_API_KEY", "")


async def fetch_html(session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Optional[str]:
    try:
        async with session.get(url, timeout=timeout) as resp:  # type: ignore
            logging.info(f"[fetch_html] Fetching {url} - Status {resp.status}")
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        logging.error(f"[fetch_html] Ошибка получения HTML: {e}")
    return None


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: tp.Any = None,
                     timeout: Optional[int] = 10) -> dict[tp.Any, tp.Any] | None:
    try:
        async with session.get(url, headers=headers, timeout=timeout) as resp:  # type: ignore
            logging.info(f"[fetch_json] Fetching {url} - Status {resp.status}")
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        logging.error(f"[fetch_json] Ошибка получения JSON: {e}")
    return None


async def search_serper(session: aiohttp.ClientSession, title: str, site: str) -> Optional[str]:
    if not SERPER_API_KEY:
        logging.warning("[search_serper] SERPER_API_KEY не задан")
        return None
    query = f"{title} site:{site}"
    headers = {"X-API-KEY": SERPER_API_KEY}
    url = "https://google.serper.dev/search"
    try:
        async with session.post(url, headers=headers, json={"q": query}, timeout=10) as resp:  # type: ignore
            logging.info(f"[search_serper] Searching for '{title}' on {site}, Status: {resp.status}")
            if resp.status == 200:
                result = await resp.json()
                for res in result.get("organic", []):
                    link = res.get("link", "")
                    if site in link:
                        logging.info(f"[search_serper] Найдена ссылка: {link}")
                        return link
    except Exception as e:
        logging.error(f"[search_serper] Ошибка поиска через Serper: {e}")
    return None


async def fetch_kinopoisk_data(session: aiohttp.ClientSession, title: str) -> Dict[str, Any]:
    try:
        url = f"https://kinopoiskapiunofficial.tech/api/v2.1/films/search-by-keyword?keyword={title}&page=1"
        headers = {
            "accept": "application/json",
            "X-API-KEY": KINOPOISK_UNOFFICIAL_API_KEY
        }
        data = await fetch_json(session, url, headers=headers)
        if data and data.get("films"):
            film = data["films"][0]
            return {
                "title": film.get("nameRu") or film.get("nameEn"),
                "description": film.get("description") or "Описание отсутствует",
                "rating": str(film.get("rating")) if film.get("rating") else "Рейтинг не найден",
                "genre": ", ".join(g["genre"] for g in film.get("genres", [])) or "Жанр не найден",
                "year": str(film.get("year", "Год не найден")),
                "runtime": str(film.get("filmLength", "-")),
                "poster": film.get("posterUrl"),
                "source": "kinopoisk",
                "link": None
            }
    except Exception as e:
        logging.warning(f"[fetch_kinopoisk_data] Ошибка получения данных Кинопоиска: {e}")
    return {}


async def search_movie_info(title: str) -> Dict[str, Any]:
    title_key = title.lower().strip()
    if title_key in CACHE:
        logging.info(f"[search_movie_info] Достаем из кэша: {title_key}")
        return CACHE[title_key]

    async with aiohttp.ClientSession() as session:
        task_lordfilm = asyncio.create_task(search_serper(session, title, "lordfilm"))
        task_rutube = asyncio.create_task(search_serper(session, title, "rutube.ru"))
        task_kp = asyncio.create_task(fetch_kinopoisk_data(session, title))

        lordfilm_link, rutube_link, kp_data = await asyncio.gather(task_lordfilm, task_rutube, task_kp)

        info: Dict[str, Any] = {}

        link = None
        if lordfilm_link:
            link = lordfilm_link
        elif rutube_link:
            link = rutube_link

        if kp_data:
            logging.info("[search_movie_info] Используем данные с неофициального API Кинопоиска")
            info = kp_data
            info["link"] = link
        elif lordfilm_link:
            logging.info(f"[search_movie_info] Используем данные с Lordfilm: {lordfilm_link}")
            html = await fetch_html(session, lordfilm_link)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                tittle_found = soup.find("h1")
                if tittle_found:
                    info["title"] = tittle_found.text.strip()
                else:
                    info["title"] = title
                desc_found = soup.find("div", class_="fdesc")
                if desc_found:
                    info["description"] = desc_found.get_text(strip=True)
                else:
                    info["description"] = "Описание отсутствует"
                info["link"] = lordfilm_link
                info["source"] = "lordfilm"
        elif rutube_link:
            logging.info("[search_movie_info] Ничего не найдено, fallback на rutube")
            info = {
                "title": title,
                "description": "Ссылка на просмотр доступна",
                "poster": None,
                "link": rutube_link,
                "source": "rutube"
            }
        else:
            logging.info("[search_movie_info] Ничего не найдено, fallback на rutube")
            info = {
                "title": "Ничего не найдено",
                "description": ""
            }

        info.setdefault("title", title)
        info.setdefault("description", "Описание отсутствует")
        info.setdefault("rating", "-")
        info.setdefault("genre", "-")
        info.setdefault("year", "-")
        info.setdefault("runtime", "-")
        info.setdefault("poster", None)
        info.setdefault("link", None)
        info.setdefault("source", "none")

        CACHE[title_key] = info
        return info
