"""Палитра «Сакура»: тёмно-синий фон, розовый акцент, лаванда, мята, коралл."""
from textual.theme import Theme

BG = "#0f1226"         # фон — тёмно-синий
PANEL = "#171b36"      # панели
SURFACE = "#13162e"    # поверхности (диалоги, поля)
SAKURA = "#ffa6c9"     # главный акцент
LAVENDER = "#a5b4fc"   # второй акцент
MINT = "#7ef0c3"       # успех
CORAL = "#ff7a85"      # ошибка
PEACH = "#ffd3a1"      # предупреждение / ожидание
TEXT = "#e6e8ff"       # основной текст
MUTED = "#8a90c0"      # приглушённый текст
DIM = "#5a6190"        # запросы, служебное
TIME = "#454b78"       # метки времени в логе

# баннер ARIELBOT: сверху вниз от сакуры к лаванде
BANNER_GRADIENT = ["#ffc4dc", "#ffa6c9", "#f3a9d6", "#dcaee6", "#c0b2f4", LAVENDER]

SAKURA_THEME = Theme(
    name="sakura",
    primary=SAKURA,
    secondary=LAVENDER,
    accent=SAKURA,
    success=MINT,
    warning=PEACH,
    error=CORAL,
    foreground=TEXT,
    background=BG,
    surface=SURFACE,
    panel=PANEL,
    dark=True,
    variables={
        "text-muted": MUTED,
        "footer-key-foreground": SAKURA,
        "block-cursor-background": SAKURA,
        "block-cursor-foreground": BG,
        "input-selection-background": f"{LAVENDER} 35%",
        "scrollbar": DIM,
        "scrollbar-hover": LAVENDER,
        "scrollbar-active": SAKURA,
    },
)
