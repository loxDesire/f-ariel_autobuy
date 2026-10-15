// Cloudflare Worker: прокси к Telegram Bot API для тех, у кого
// api.telegram.org заблокирован.
//
// Как поставить (бесплатно):
//   1. dash.cloudflare.com -> Workers & Pages -> Create -> Create Worker
//   2. Deploy, затем "Edit code" -> вставить этот файл целиком -> Deploy
//   3. URL воркера (https://<имя>.<аккаунт>.workers.dev) вписать в ARIELBOT:
//      Настройки -> API base (или "api_base" в config.json -> "telegram")
//
// Бот шлёт POST <URL воркера>/bot<токен>/sendMessage — воркер пересылает
// его на api.telegram.org как есть и возвращает ответ.

export default {
  async fetch(request) {
    const url = new URL(request.url);
    // пропускаем только запросы к Bot API, чтобы воркер не стал открытым прокси
    if (!url.pathname.startsWith("/bot")) {
      return new Response("ARIELBOT telegram proxy", { status: 404 });
    }
    const target = "https://api.telegram.org" + url.pathname + url.search;
    return fetch(target, {
      method: request.method,
      headers: { "Content-Type": request.headers.get("Content-Type") || "application/json" },
      body: request.method === "GET" ? undefined : await request.text(),
    });
  },
};
