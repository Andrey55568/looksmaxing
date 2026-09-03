import asyncio
import sqlite3
import json
import io
import base64
import uuid
import math
from datetime import datetime, timedelta
from PIL import Image, ImageStat
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==================== КОНФИГ ====================
BOT_TOKEN = "8706127340:AAHPeKEi1gQB9l1Tt9Ryxua93bRmF4K5lJs"
ADMIN_ID = 8061549073
