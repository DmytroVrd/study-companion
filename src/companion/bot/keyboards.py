from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/new"), KeyboardButton(text="/projects")],
            [KeyboardButton(text="/export"), KeyboardButton(text="/help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Upload a file or ask a question",
    )


def quiz_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="A", callback_data="quiz:A"),
                InlineKeyboardButton(text="B", callback_data="quiz:B"),
                InlineKeyboardButton(text="C", callback_data="quiz:C"),
                InlineKeyboardButton(text="D", callback_data="quiz:D"),
            ]
        ]
    )
