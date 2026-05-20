from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

CROPS = [
    ("કપાસ (Cotton)", "cotton"),
    ("મગફળી (Groundnut)", "groundnut"),
    ("ઘઉં (Wheat)", "wheat"),
    ("જીરું (Cumin)", "cumin"),
    ("દિવેલા (Castor)", "castor"),
    ("બાજરી (Bajra)", "bajra"),
    ("મગ (Mung)", "mung"),
    ("તલ (Sesame)", "sesame"),
    ("ડાંગર (Rice)", "rice"),
]

LANGUAGES = [
    ("ગુજરાતી", "gu"),
    ("हिंदी", "hi"),
]


def crop_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"crop_{value}")]
        for label, value in CROPS
    ]
    return InlineKeyboardMarkup(buttons)


def language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"lang_{value}")]
        for label, value in LANGUAGES
    ]
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        ["📸 રોગ ઓળખો", "💰 ભાવ જુઓ"],
        ["🌤 હવામાન", "❓ મદદ"],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
