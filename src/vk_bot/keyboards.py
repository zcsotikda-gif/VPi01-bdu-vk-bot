"""Клавиатуры VK.

Кнопки описываются простыми данными (Button + spec — список рядов),
здесь же происходит перевод spec в JSON vkbottle. Благодаря этому
handlers не содержат JSON клавиатур, а тесты проверяют spec без VK.
"""

from dataclasses import dataclass

from vkbottle import Keyboard, KeyboardButtonColor, Text

PRIMARY = "primary"
SECONDARY = "secondary"
POSITIVE = "positive"
NEGATIVE = "negative"

_COLORS = {
    PRIMARY: KeyboardButtonColor.PRIMARY,
    SECONDARY: KeyboardButtonColor.SECONDARY,
    POSITIVE: KeyboardButtonColor.POSITIVE,
    NEGATIVE: KeyboardButtonColor.NEGATIVE,
}


@dataclass
class Button:
    label: str
    action: str | None = None
    params: dict | None = None
    color: str = PRIMARY

    def payload(self) -> dict | None:
        if not self.action:
            return None
        payload = {"action": self.action}
        if self.params:
            payload.update(self.params)
        return payload


def menu_button() -> Button:
    return Button("Главное меню", "show_menu", color=SECONDARY)


def back_button() -> Button:
    return Button("Назад", "back", color=SECONDARY)


def manager_button() -> Button:
    return Button("Менеджер", "request_manager", color=SECONDARY)


def to_vk(spec: list[list[Button]]) -> str:
    """Собрать JSON клавиатуры для messages.send."""
    keyboard = Keyboard(one_time=False)
    for row_spec in spec:
        keyboard.row()
        for button in row_spec:
            keyboard.add(Text(button.label, payload=button.payload()), color=_COLORS.get(button.color))
    return keyboard.get_json()


# --------------------------------------------------------------- экраны
def kb_greeting() -> list[list[Button]]:
    return [
        [Button("Для себя 👤", "choose_segment", {"segment": "person"}),
         Button("Для бизнеса 🏢", "choose_segment", {"segment": "business"})],
        [Button("Посмотреть услуги", "show_services", color=SECONDARY),
         Button("Задать вопрос", "ask_question", color=SECONDARY)],
    ]


def kb_segment(needs: list[dict]) -> list[list[Button]]:
    rows: list[list[Button]] = []
    for i in range(0, len(needs), 2):
        rows.append([
            Button(need["title"], "choose_need", {"need": need["id"]})
            for need in needs[i : i + 2]
        ])
    rows.append([menu_button()])
    return rows


def kb_service() -> list[list[Button]]:
    return [
        [Button("Оценить мою задачу", "start_qualification", color=POSITIVE)],
        [Button("Подробнее", "service_details"),
         Button("Другая услуга", "service_other", color=SECONDARY)],
        [back_button(), menu_button()],
    ]


def kb_qualification() -> list[list[Button]]:
    return [[manager_button()], [menu_button()]]


def kb_consent() -> list[list[Button]]:
    return [
        [Button("Согласен", "agree_consent", color=POSITIVE)],
        [Button("Не сохранять", "refuse_consent", color=NEGATIVE)],
        [menu_button()],
    ]


def kb_confirm() -> list[list[Button]]:
    return [
        [Button("Отправить заявку", "confirm_lead", color=POSITIVE)],
        [Button("Изменить", "start_qualification", color=SECONDARY)],
        [Button("Отмена", "cancel_lead", color=NEGATIVE), menu_button()],
    ]


def kb_llm() -> list[list[Button]]:
    return [
        [Button("Подобрать услугу", "show_services", color=SECONDARY)],
        [manager_button()],
        [menu_button()],
    ]


def kb_llm_fallback() -> list[list[Button]]:
    return [
        [Button("Услуги", "show_services", color=SECONDARY)],
        [manager_button()],
        [menu_button()],
    ]


def kb_menu() -> list[list[Button]]:
    """Главное меню: из него доступны обе ветки, каталог, вопрос и менеджер (5 кнопок)."""
    return [
        [Button("Для себя 👤", "choose_segment", {"segment": "person"}),
         Button("Для бизнеса 🏢", "choose_segment", {"segment": "business"})],
        [Button("Посмотреть услуги", "show_services", color=SECONDARY),
         Button("Задать вопрос", "ask_question", color=SECONDARY)],
        [manager_button()],
    ]


def kb_simple() -> list[list[Button]]:
    return [[menu_button()]]


def kb_delete_confirm() -> list[list[Button]]:
    return [
        [Button("Да, удалить", "delete_data_confirm", color=NEGATIVE)],
        [Button("Отмена", "delete_data_cancel", color=SECONDARY)],
    ]


def kb_after_delete() -> list[list[Button]]:
    return [[Button("Начать сначала", "restart", color=POSITIVE)]]
