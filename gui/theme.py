"""
Палитра и QSS-стиль, приближенные к внешнему виду f-ariel.ru
(см. скриншот главной страницы и классы в site/add-to-basket-DT_4COkg.js:
blue-light-1/blue-main/blue-dark-1/blue-dark-2, gray-light-2/gray-main, rounded-lg).
"""

BLUE_MAIN = "#2F6FED"
BLUE_DARK_1 = "#2557C7"
BLUE_DARK_2 = "#1D46A3"
BLUE_LIGHT_1 = "#EAF1FE"
BLUE_LIGHT_3 = "#C7D9FB"

TEXT_DARK = "#1A1F29"
TEXT_MUTED = "#5B6472"

BORDER = "#E5E7EB"
BG = "#FFFFFF"
BG_SOFT = "#F7F8FA"
BADGE_BG = "#F3F4F6"

GREEN = "#1E9E5A"
GREEN_BG = "#E7F7EE"
RED = "#DC2F44"
RED_BG = "#FDEAEC"

FONT_FAMILY = '"Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif'
MONO_FONT_FAMILY = '"Cascadia Mono", "Consolas", "SF Mono", "Menlo", monospace'
RADIUS = 8

QSS = f"""
* {{
    font-family: {FONT_FAMILY};
    color: {TEXT_DARK};
}}

QMainWindow, QWidget {{
    background: {BG};
}}

QLabel#sectionTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT_DARK};
}}

QLabel#muted {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER};
    background: {BG};
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 10px 18px;
    font-size: 13px;
    border: none;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {BLUE_MAIN};
    font-weight: 600;
    border-bottom: 2px solid {BLUE_MAIN};
}}

QTabBar::tab:hover {{
    color: {BLUE_DARK_1};
}}

QFrame#card {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
}}

QFrame#cardSoft {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
}}

QLineEdit, QSpinBox, QComboBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    background: {BG};
    selection-background-color: {BLUE_LIGHT_1};
    min-height: 20px;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {BLUE_MAIN};
}}

QSpinBox {{
    padding-right: 6px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
    border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
    border: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QPushButton {{
    border-radius: {RADIUS}px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid transparent;
}}

QPushButton#primaryButton {{
    background: {BLUE_MAIN};
    color: white;
}}
QPushButton#primaryButton:hover {{ background: {BLUE_DARK_1}; }}
QPushButton#primaryButton:pressed {{ background: {BLUE_DARK_2}; }}
QPushButton#primaryButton:disabled {{ background: {BLUE_LIGHT_3}; color: {BG}; }}

QPushButton#dangerButton {{
    background: {RED};
    color: white;
}}
QPushButton#dangerButton:hover {{ background: #C22539; }}
QPushButton#dangerButton:disabled {{ background: #F2B4BC; color: {BG}; }}

QPushButton#secondaryButton {{
    background: {BG};
    color: {BLUE_MAIN};
    border: 1px solid {BLUE_MAIN};
}}
QPushButton#secondaryButton:hover {{ background: {BLUE_LIGHT_1}; }}
QPushButton#secondaryButton:pressed {{ background: {BLUE_LIGHT_3}; }}

QPushButton#linkButton {{
    background: transparent;
    color: {BLUE_MAIN};
    border: none;
    padding: 2px 4px;
    font-weight: 600;
}}
QPushButton#linkButton:hover {{ color: {BLUE_DARK_1}; text-decoration: underline; }}

QPushButton#iconButton {{
    background: {BG};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px;
    font-size: 13px;
    font-weight: 400;
}}
QPushButton#iconButton:hover {{ background: {BLUE_LIGHT_1}; border: 1px solid {BLUE_MAIN}; }}
QPushButton#iconButton:checked {{ background: {BLUE_LIGHT_1}; border: 1px solid {BLUE_MAIN}; color: {BLUE_MAIN}; }}

QWidget#tagChip {{
    background: {BADGE_BG};
    border-radius: 11px;
}}
QLabel#tagChipLabel {{
    color: {TEXT_DARK};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}
QPushButton#chipRemove {{
    background: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-radius: 7px;
    padding: 0px;
    margin: 0px;
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#chipRemove:hover {{ background: {RED_BG}; color: {RED}; }}

QPushButton#radioToggle {{
    background: transparent;
    border: none;
    padding: 3px 4px;
    text-align: left;
    font-size: 13px;
    font-weight: 400;
    color: {TEXT_DARK};
}}
QPushButton#radioToggle:hover {{ color: {BLUE_MAIN}; }}
QPushButton#radioToggle:checked {{ font-weight: 600; color: {BLUE_MAIN}; }}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid {TEXT_MUTED};
    background: {BG};
}}
QCheckBox::indicator:hover {{ border: 1px solid {BLUE_MAIN}; }}
QCheckBox::indicator:checked {{
    border: 1px solid {BLUE_MAIN};
    background: {BLUE_MAIN};
}}

QLabel#badge {{
    background: {BADGE_BG};
    color: {TEXT_MUTED};
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#badgeSuccess {{
    background: {GREEN_BG};
    color: {GREEN};
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#badgeError {{
    background: {RED_BG};
    color: {RED};
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QTextEdit#logView {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    font-family: {MONO_FONT_FAMILY};
    font-size: 12px;
    padding: 8px;
}}

QTableWidget {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    gridline-color: {BORDER};
    background: {BG};
    selection-background-color: {BLUE_LIGHT_1};
    selection-color: {TEXT_DARK};
}}

QHeaderView::section {{
    background: {BG_SOFT};
    color: {TEXT_MUTED};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
    font-size: 12px;
}}

QScrollArea {{
    border: none;
}}

QCheckBox, QRadioButton {{
    spacing: 6px;
}}
"""
