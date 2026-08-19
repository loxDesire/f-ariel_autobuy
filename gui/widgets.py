"""Переиспользуемые виджеты GUI."""
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme


# Кастомные иконки рисуются с oversampling (реальный холст в OVERSAMPLE раз
# больше логического размера + devicePixelRatio) — иначе на экранах с
# масштабированием (125%/150%/200%) они выглядят пиксельными/размытыми.
_OVERSAMPLE = 4


def _new_icon_painter(size: int):
    pixmap = QPixmap(size * _OVERSAMPLE, size * _OVERSAMPLE)
    pixmap.setDevicePixelRatio(_OVERSAMPLE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    return pixmap, painter


def _eye_icon(size: int = 16, color: str = theme.TEXT_MUTED, crossed: bool = False) -> QIcon:
    """Рисует минималистичную линейную иконку глаза (не эмодзи — без
    цветастого системного эмодзи-шрифта), опционально перечёркнутую."""
    pixmap, painter = _new_icon_painter(size)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.2, size * 0.09))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    margin_x = size * 0.12
    rect = QRectF(margin_x, size * 0.30, size - 2 * margin_x, size * 0.40)
    painter.drawArc(rect, 0, 180 * 16)
    painter.drawArc(rect, 180 * 16, 180 * 16)

    painter.setBrush(QColor(color))
    r = size * 0.075
    painter.drawEllipse(QPointF(size / 2, size / 2), r, r)

    if crossed:
        painter.drawLine(QPointF(size * 0.16, size * 0.16), QPointF(size * 0.84, size * 0.84))

    painter.end()
    return QIcon(pixmap)


def _radio_icon(size: int = 16, checked: bool = False,
                 color: str = theme.TEXT_MUTED, accent: str = theme.BLUE_MAIN) -> QIcon:
    """Честно нарисованный круг (не полагаемся на нативный
    QRadioButton::indicator — на некоторых системах/стилях Qt он рендерится
    не круглым)."""
    pixmap, painter = _new_icon_painter(size)
    ring_color = accent if checked else color
    pen = QPen(QColor(ring_color))
    pen.setWidthF(max(1.2, size * 0.09))
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    m = size * 0.09
    painter.drawEllipse(QRectF(m, m, size - 2 * m, size - 2 * m))
    if checked:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(accent))
        r = size * 0.22
        painter.drawEllipse(QPointF(size / 2, size / 2), r, r)
    painter.end()
    return QIcon(pixmap)


class RadioToggle(QPushButton):
    """Замена QRadioButton с честно нарисованным кругом-индикатором вместо
    нативного ::indicator (см. _radio_icon). Совместима с QButtonGroup —
    работает как обычная checkable-кнопка."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("radioToggle")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(16, 16))
        self._off_icon = _radio_icon(checked=False)
        self._on_icon = _radio_icon(checked=True)
        self.setIcon(self._off_icon)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self.setIcon(self._on_icon if checked else self._off_icon)


class FlowLayout(QLayout):
    """Раскладка, переносящая дочерние виджеты на новую строку по мере
    нехватки места по горизонтали — стандартный рецепт Qt (Flow Layout Example),
    используется для чипов product_ids."""

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + bottom


class _TagChip(QWidget):
    removed = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.setObjectName("tagChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(4)
        label = QLabel(text)
        label.setObjectName("tagChipLabel")
        remove_btn = QPushButton("×")
        remove_btn.setObjectName("chipRemove")
        remove_btn.setFixedSize(14, 14)
        remove_btn.clicked.connect(self.removed.emit)
        layout.addWidget(label)
        layout.addWidget(remove_btn)
        self.setFixedHeight(22)


class TagListWidget(QWidget):
    """Список тегов (используется для product_ids): чипы + поле ввода
    с добавлением по Enter или запятой."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.chips_container = QWidget()
        self.chips_container.setMinimumHeight(28)
        self.flow_layout = FlowLayout(self.chips_container, margin=0, spacing=6)
        outer.addWidget(self.chips_container)

        self.input = QLineEdit()
        self.input.setPlaceholderText("ID товара — Enter или запятая")
        self.input.returnPressed.connect(self._on_return)
        self.input.textChanged.connect(self._on_text_changed)
        outer.addWidget(self.input)

        self._chips = {}  # text -> _TagChip

    def _on_text_changed(self, text: str):
        if "," in text:
            parts = [p.strip() for p in text.split(",")]
            for p in parts[:-1]:
                if p:
                    self.add_tag(p)
            self.input.setText(parts[-1])

    def _on_return(self):
        text = self.input.text().strip()
        if text:
            self.add_tag(text)
            self.input.clear()

    def add_tag(self, text):
        text = str(text).strip()
        if not text or text in self._chips:
            return
        chip = _TagChip(text)
        chip.removed.connect(lambda: self._remove_tag(text))
        self.flow_layout.addWidget(chip)
        self._chips[text] = chip
        self.changed.emit()

    def _remove_tag(self, text: str):
        chip = self._chips.pop(text, None)
        if chip is not None:
            self.flow_layout.removeWidget(chip)
            chip.setParent(None)
            chip.deleteLater()
        self.changed.emit()

    def set_tags(self, values):
        for text in list(self._chips.keys()):
            self._remove_tag(text)
        for v in values:
            self.add_tag(v)

    def tags(self) -> list:
        return list(self._chips.keys())


class PasswordField(QLineEdit):
    """QLineEdit в режиме пароля с иконкой-глазком ВНУТРИ поля (trailing action),
    без отдельной кнопки сбоку — единая рамка, как у остальных полей формы."""

    def __init__(self, initial: str = "", parent=None):
        super().__init__(initial, parent)
        self.setEchoMode(QLineEdit.Password)

        self._show_icon = _eye_icon(color=theme.TEXT_MUTED, crossed=False)
        self._hide_icon = _eye_icon(color=theme.TEXT_MUTED, crossed=True)

        self._action = self.addAction(self._show_icon, QLineEdit.TrailingPosition)
        self._action.setToolTip("Показать пароль")
        self._action.triggered.connect(self._toggle)
        self._visible = False

    def _toggle(self):
        self._visible = not self._visible
        self.setEchoMode(QLineEdit.Normal if self._visible else QLineEdit.Password)
        self._action.setIcon(self._hide_icon if self._visible else self._show_icon)
        self._action.setToolTip("Скрыть пароль" if self._visible else "Показать пароль")
