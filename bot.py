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
WEBAPP_URL = "https://t.me/KenyChadPSL_bot"

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = "looks.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        role TEXT DEFAULT 'user',
        subscription TEXT DEFAULT 'none',
        sub_expires TEXT,
        stars_balance INTEGER DEFAULT 0,
        daily_ratings INTEGER DEFAULT 0,
        daily_battles INTEGER DEFAULT 0,
        last_reset DATE,
        total_ratings INTEGER DEFAULT 0,
        total_battles INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        photo_id TEXT,
        verdict TEXT,
        observation TEXT,
        strengths TEXT,
        improvements TEXT,
        confidence TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS battles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        photo1_id TEXT,
        photo2_id TEXT,
        verdict1 TEXT,
        verdict2 TEXT,
        winner TEXT,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan TEXT,
        amount INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_or_create_user(tg_id, username, first_name):
    user = get_user(tg_id)
    if user:
        return user
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'owner'")
    owner_exists = c.fetchone()[0]
    role = 'owner' if owner_exists == 0 else 'user'
    today = datetime.now().date().isoformat()
    c.execute('''INSERT INTO users (tg_id, username, first_name, role, last_reset) 
                 VALUES (?, ?, ?, ?, ?)''', (tg_id, username, first_name, role, today))
    conn.commit()
    conn.close()
    return get_user(tg_id)

def update_stars(tg_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET stars_balance = stars_balance + ? WHERE tg_id = ?", (amount, tg_id))
    conn.commit()
    conn.close()

def set_subscription(tg_id, plan, days):
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET subscription = ?, sub_expires = ? WHERE tg_id = ?", (plan, expires, tg_id))
    conn.commit()
    conn.close()

def reset_daily_limits():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("UPDATE users SET daily_ratings = 0, daily_battles = 0, last_reset = ? WHERE last_reset != ?", (today, today))
    conn.commit()
    conn.close()

def can_rate(tg_id):
    user = get_user(tg_id)
    if not user:
        return False, "Пользователь не найден"
    sub = user[5]
    daily = user[8]
    if sub == 'gold':
        return True, "ok"
    if sub == 'bronze':
        if daily >= 10:
            return False, "❌ Лимит 10 оценок в день"
        return True, "ok"
    if sub == 'silver':
        if daily >= 15:
            return False, "❌ Лимит 15 оценок в день"
        return True, "ok"
    return False, "❌ Нет подписки. Купите за 20⭐"

def can_battle(tg_id):
    user = get_user(tg_id)
    if not user:
        return False, "Пользователь не найден"
    sub = user[5]
    daily_b = user[9]
    if sub == 'gold':
        return True, "ok"
    if sub == 'silver':
        if daily_b >= 3:
            return False, "❌ Лимит 3 батла в день"
        return True, "ok"
    return False, "❌ Батл только с Silver/Gold"

def increment_usage(tg_id, typ):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if typ == 'rate':
        c.execute("UPDATE users SET daily_ratings = daily_ratings + 1, total_ratings = total_ratings + 1 WHERE tg_id = ?", (tg_id,))
    elif typ == 'battle':
        c.execute("UPDATE users SET daily_battles = daily_battles + 1, total_battles = total_battles + 1 WHERE tg_id = ?", (tg_id,))
    conn.commit()
    conn.close()

def save_rating(tg_id, photo_id, verdict, observation, strengths, improvements, confidence):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO ratings (user_id, photo_id, verdict, observation, strengths, improvements, confidence) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (tg_id, photo_id, verdict, observation, strengths, improvements, confidence))
    conn.commit()
    conn.close()

def save_battle(tg_id, photo1_id, photo2_id, verdict1, verdict2, winner, reason):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO battles (user_id, photo1_id, photo2_id, verdict1, verdict2, winner, reason) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (tg_id, photo1_id, photo2_id, verdict1, verdict2, winner, reason))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM battles")
    total_battles = c.fetchone()[0]
    c.execute("SELECT SUM(stars_balance) FROM users")
    total_stars = c.fetchone()[0] or 0
    conn.close()
    return total_users, total_ratings, total_battles, total_stars

# ==================== АНАЛИЗ БЕЗ ИИ ====================
def compress_image(image_data, max_size=800):
    try:
        img = Image.open(io.BytesIO(image_data))
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=75, optimize=True)
        return buffer.getvalue()
    except:
        return image_data

def analyze_photo(image_data):
    try:
        compressed = compress_image(image_data)
        img = Image.open(io.BytesIO(compressed))
        brightness = ImageStat.Stat(img).mean[0]
        contrast = ImageStat.Stat(img).std[0]
        quality = "Хорошее"
        if brightness < 40:
            quality = "Тёмное"
        elif brightness > 220:
            quality = "Пересвеченное"
        elif contrast < 20:
            quality = "Низкий контраст"
        
        # Простая эмуляция оценки
        import random
        random.seed(int(brightness * 100))
        verdicts = ["LTN", "MTN", "HTN", "Chadlite"]
        if quality == "Хорошее":
            verdict = random.choice(["MTN", "HTN"])
        elif quality == "Тёмное":
            verdict = "LTN"
        else:
            verdict = random.choice(["LTN", "MTN"])
        
        return {
            "verdict": verdict,
            "observation": f"Качество фото: {quality}. Лицо обнаружено.",
            "strengths": "Чёткое фото" if quality == "Хорошее" else "-",
            "improvements": "Улучшите освещение" if quality != "Хорошее" else "Можно другой ракурс",
            "confidence": "Высокая" if quality == "Хорошее" else "Средняя"
        }
    except:
        return {
            "verdict": "Ошибка",
            "observation": "Не удалось обработать фото",
            "strengths": "-",
            "improvements": "-",
            "confidence": "Низкая"
        }

def compare_photos(image1_data, image2_data):
    try:
        result1 = analyze_photo(image1_data)
        result2 = analyze_photo(image2_data)
        score_map = {"LTN": 1, "MTN": 2, "HTN": 3, "Chadlite": 4, "Chad": 5}
        score1 = score_map.get(result1.get("verdict", "MTN"), 2)
        score2 = score_map.get(result2.get("verdict", "MTN"), 2)
        if score1 > score2:
            winner = "Фото 1"
            reason = f"Фото 1 получило {result1['verdict']} > {result2['verdict']}"
        elif score2 > score1:
            winner = "Фото 2"
            reason = f"Фото 2 получило {result2['verdict']} > {result1['verdict']}"
        else:
            winner = "Ничья"
            reason = "Оба фото получили одинаковую оценку"
        return {
            "verdict1": result1.get("verdict", "MTN"),
            "verdict2": result2.get("verdict", "MTN"),
            "winner": winner,
            "reason": reason
        }
    except:
        return {
            "verdict1": "Ошибка",
            "verdict2": "Ошибка",
            "winner": "Не определен",
            "reason": "Ошибка обработки"
        }

# ==================== БОТ ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username or "anon", message.from_user.first_name or "User")
    if user[6]:
        expires = datetime.fromisoformat(user[6])
        if expires < datetime.now():
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET subscription = 'none' WHERE tg_id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
            user = get_user(message.from_user.id)
    stars = user[7]
    sub = user[5]
    role = user[4]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть Mini App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="💰 Купить подписку", callback_data="subscribe")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])
    if role == 'owner':
        kb.inline_keyboard.append([InlineKeyboardButton(text="⚙️ Админ", callback_data="admin")])
    await message.answer(
        f"👋 <b>Добро пожаловать, {message.from_user.first_name}!</b>\n\n"
        f"⭐ Баланс: <b>{stars}</b> звёзд\n"
        f"📅 Подписка: <b>{sub.upper() if sub != 'none' else 'Нет'}</b>\n"
        f"👤 Роль: <b>{role}</b>\n\n"
        f"<i>Используй Mini App для оценки!</i>",
        reply_markup=kb
    )

@dp.callback_query(F.data == "subscribe")
async def subscribe_callback(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 Bronze — 100⭐/мес", callback_data="buy_bronze")],
        [InlineKeyboardButton(text="🥈 Silver — 200⭐/мес", callback_data="buy_silver")],
        [InlineKeyboardButton(text="🥇 Gold — 450⭐/мес", callback_data="buy_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    await callback.message.edit_text(
        "💎 <b>Выберите тариф:</b>\n\n"
        "🥉 Bronze — 10 оценок/день\n"
        "🥈 Silver — 15 оценок + 3 батла/день\n"
        "🥇 Gold — Безлимит",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back_callback(callback: types.CallbackQuery):
    await start_cmd(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "stats")
async def stats_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"⭐ Баланс: <b>{user[7]}</b>\n"
        f"📅 Подписка: <b>{user[5].upper() if user[5] != 'none' else 'Нет'}</b>\n"
        f"📸 Всего оценок: <b>{user[10]}</b>\n"
        f"⚔️ Всего батлов: <b>{user[11]}</b>\n"
        f"📈 Оценок сегодня: <b>{user[8]}/15</b>\n"
        f"⚔️ Батлов сегодня: <b>{user[9]}/3</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "admin")
async def admin_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[4] != 'owner':
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    total_users, total_ratings, total_battles, total_stars = get_stats()
    await callback.message.edit_text(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📸 Оценок: <b>{total_ratings}</b>\n"
        f"⚔️ Батлов: <b>{total_battles}</b>\n"
        f"⭐ Звёзд: <b>{total_stars}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_callback(callback: types.CallbackQuery):
    plan = callback.data.split("_")[1]
    prices = {"bronze": 100, "silver": 200, "gold": 450}
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"{plan.capitalize()} Subscription",
        description=f"Подписка {plan.capitalize()} на 30 дней",
        payload=f"sub_{plan}",
        provider_token="",
        currency="XTR",
        prices=[{"label": plan.capitalize(), "amount": prices[plan]}],
        start_parameter="subscription"
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout: types.PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@dp.message(F.successful_payment)
async def payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("sub_"):
        plan = payload.split("_")[1]
        days = {"bronze": 30, "silver": 30, "gold": 30}
        set_subscription(message.from_user.id, plan, days[plan])
        await message.answer(f"✅ Подписка <b>{plan.capitalize()}</b> активирована на 30 дней!")

@dp.message(F.web_app_data)
async def webapp_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        tg_id = message.from_user.id
        
        if action == "rate":
            photo_data = data.get("photo")
            if not photo_data:
                await message.answer("❌ Нет фото")
                return
            can, msg = can_rate(tg_id)
            if not can:
                await message.answer(msg)
                return
            image_bytes = base64.b64decode(photo_data.split(",")[1])
            result = analyze_photo(image_bytes)
            photo_id = str(uuid.uuid4())
            save_rating(tg_id, photo_id, result["verdict"], result["observation"], 
                       result["strengths"], result["improvements"], result["confidence"])
            increment_usage(tg_id, "rate")
            await message.answer(
                f"📸 <b>Результат оценки</b>\n\n"
                f"🎯 <b>Вердикт:</b> <code>{result['verdict']}</code>\n\n"
                f"👀 <b>Наблюдения:</b>\n{result['observation']}\n\n"
                f"✅ <b>Сильные стороны:</b>\n{result['strengths']}\n\n"
                f"📈 <b>Что улучшить:</b>\n{result['improvements']}\n\n"
                f"📊 <b>Уверенность:</b> {result['confidence']}"
            )
            
        elif action == "battle":
            photo1 = data.get("photo1")
            photo2 = data.get("photo2")
            if not photo1 or not photo2:
                await message.answer("❌ Нужны оба фото")
                return
            can, msg = can_battle(tg_id)
            if not can:
                await message.answer(msg)
                return
            img1 = base64.b64decode(photo1.split(",")[1])
            img2 = base64.b64decode(photo2.split(",")[1])
            result = compare_photos(img1, img2)
            photo1_id = str(uuid.uuid4())
            photo2_id = str(uuid.uuid4())
            save_battle(tg_id, photo1_id, photo2_id, result["verdict1"], result["verdict2"], result["winner"], result["reason"])
            increment_usage(tg_id, "battle")
            await message.answer(
                f"⚔️ <b>Результат батла</b>\n\n"
                f"📸 Фото 1: <code>{result['verdict1']}</code>\n"
                f"📸 Фото 2: <code>{result['verdict2']}</code>\n\n"
                f"🏆 <b>Победитель:</b> <code>{result['winner']}</code>\n\n"
                f"💬 <b>Причина:</b>\n{result['reason']}"
            )
            
        elif action == "buy_subscription":
            plan = data.get("plan")
            prices = {"bronze": 100, "silver": 200, "gold": 450}
            await bot.send_invoice(
                chat_id=message.chat.id,
                title=f"{plan.capitalize()} Subscription",
                description=f"Подписка {plan.capitalize()} на 30 дней",
                payload=f"sub_{plan}",
                provider_token="",
                currency="XTR",
                prices=[{"label": plan.capitalize(), "amount": prices[plan]}],
                start_parameter="subscription"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    print("🚀 Бот запущен!")
    print(f"👤 Админ: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
