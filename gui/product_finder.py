"""
Парсинг списка доступных товаров с f-ariel.ru.

Карточки товаров на сайте несут атрибут data-add-to-basket="<id>" (кнопка
добавления в корзину), а название — в соседнем data-item-name внутри той же
карточки (см. site/add-to-basket-DT_4COkg.js: querySelector("[data-item-name]")).
"""
import aiohttp
from bs4 import BeautifulSoup

SITE_URL = "https://f-ariel.ru/"


async def fetch_available_products(url: str = SITE_URL) -> list:
    """Возвращает [{"id": "413", "name": "Матрешка ..." или None}, ...]."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, ssl=False, timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen = set()
    for el in soup.select("[data-add-to-basket]"):
        pid = el.get("data-add-to-basket")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        name_el = el.select_one("[data-item-name]")
        name = name_el.get_text(strip=True) if name_el else None
        products.append({"id": pid, "name": name})
    return products
