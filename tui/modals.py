"""Общие модальные окна: подтверждение и форма из полей ввода."""
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [("escape", "dismiss(False)", "Отмена")]

    def __init__(self, question: str, yes: str = "Да", no: str = "Отмена"):
        super().__init__()
        self.question, self.yes, self.no = question, yes, no

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.question, classes="dialog-text")
            with Horizontal(classes="dialog-buttons"):
                yield Button(self.yes, id="yes", variant="error")
                yield Button(self.no, id="no")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "yes")


class FormModal(ModalScreen[dict]):
    """
    Форма из полей: fields = [(ключ, подпись, значение, password)].
    Возвращает {ключ: текст} или None при отмене.
    """
    BINDINGS = [("escape", "cancel", "Отмена")]

    def __init__(self, title: str, fields: list, ok_label: str = "Сохранить"):
        super().__init__()
        self.title_text, self.fields, self.ok_label = title, fields, ok_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.title_text, classes="dialog-title")
            for key, label, value, password in self.fields:
                yield Label(label, classes="field-label")
                yield Input(value=value or "", password=password, id=f"f-{key}")
            with Horizontal(classes="dialog-buttons"):
                yield Button(self.ok_label, id="ok", variant="primary")
                yield Button("Отмена", id="cancel")

    def on_input_submitted(self, event: Input.Submitted):
        self._submit()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "ok":
            self._submit()
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def _submit(self):
        self.dismiss({key: self.query_one(f"#f-{key}", Input).value.strip()
                      for key, *_ in self.fields})
