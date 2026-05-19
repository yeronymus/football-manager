import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from app.config import settings

# Initialize Bot instance in a separate file to avoid circular imports.
# This file should only contain the bot initialization and its basic properties.

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

logger = logging.getLogger(__name__)
logger.info("Bot instance initialized in app.bot.instance")
