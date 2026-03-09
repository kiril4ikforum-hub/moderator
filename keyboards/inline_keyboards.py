from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ── Капча ────────────────────────────────────────

def captcha_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "📜 Прочитать правила", callback_data=f"cap_rules_{uid}"
            )],
            [InlineKeyboardButton(
                "✅ Я согласен с правилами", callback_data=f"cap_ok_{uid}"
            )],
        ]
    )


def rules_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "✅ Я ознакомлен и согласен", callback_data=f"cap_ok_{uid}"
            )],
            [InlineKeyboardButton(
                "◀️ Назад", callback_data=f"cap_back_{uid}"
            )],
        ]
    )


# ── Модерация ────────────────────────────────────

def mod_kb(uid: int, mid: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑 Удалить", callback_data=f"m_del_{uid}_{mid}"
                ),
                InlineKeyboardButton(
                    "⏱ Тайм-аут", callback_data=f"m_to_{uid}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔨 Бан", callback_data=f"m_ban_{uid}"
                ),
                InlineKeyboardButton(
                    "🤔 Спам?", callback_data=f"m_spam_{uid}_{mid}"
                ),
            ],
        ]
    )


def done_kb(label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"✅ {label}", callback_data="noop")]]
    )


# ── Настройки ────────────────────────────────────

def settings_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "👮‍♂️ Управление правами", callback_data="set_rights"
            )],
            [InlineKeyboardButton(
                "🚦 Спам-фильтр", callback_data="set_filter"
            )],
            [InlineKeyboardButton(
                "📊 Статистика", callback_data="set_stats"
            )],
            [InlineKeyboardButton(
                "❓ Помощь", callback_data="set_help"
            )],
        ]
    )


def filter_kb(cid: int, s: dict) -> InlineKeyboardMarkup:
    def icon(v):
        return "✅" if v else "❌"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                f"🤬 Антимат: {icon(s['antimat'])}",
                callback_data=f"tog_mat_{cid}",
            )],
            [InlineKeyboardButton(
                f"🔗 Антиссылки: {icon(s['antilinks'])}",
                callback_data=f"tog_link_{cid}",
            )],
            [InlineKeyboardButton(
                f"⏳ Антифлуд: {icon(s['antiflood'])}",
                callback_data=f"tog_flood_{cid}",
            )],
            [InlineKeyboardButton(
                f"🔐 Капча: {icon(s['captcha'])}",
                callback_data=f"tog_cap_{cid}",
            )],
            [InlineKeyboardButton(
                f"👋 Приветствие: {icon(s['welcome'])}",
                callback_data=f"tog_wel_{cid}",
            )],
            [InlineKeyboardButton(
                "◀️ Назад в меню", callback_data="set_main"
            )],
        ]
    )


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "◀️ Назад в меню", callback_data="set_main"
        )]]
    )
