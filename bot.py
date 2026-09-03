import asyncio
import sqlite3
import io
import random
from datetime import datetime, timedelta
from PIL import Image, ImageStat
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==================== КОНФИГ ====================
BOT_TOKEN = "8706127340:AAHPeKEi1gQB9l1Tt9Ryxua93bRmF4K5lJs"
ADMIN_ID = 8061549073
CHANNEL_ID = "@KennyChadPSL"

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
        free_ratings INTEGER DEFAULT 0,
        daily_ratings INTEGER DEFAULT 0,
        daily_battles INTEGER DEFAULT 0,
        last_reset DATE,
        total_ratings INTEGER DEFAULT 0,
        total_battles INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        discount_percent INTEGER DEFAULT 0,
        free_ratings INTEGER DEFAULT 0,
        uses_left INTEGER DEFAULT 1,
        created_by INTEGER
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

def add_free_ratings(tg_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET free_ratings = free_ratings + ? WHERE tg_id = ?", (amount, tg_id))
    conn.commit()
    conn.close()

def set_subscription(tg_id, plan, days):
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET subscription = ?, sub_expires = ? WHERE tg_id = ?", (plan, expires, tg_id))
    conn.commit()
    conn.close()

def can_rate(tg_id):
    user = get_user(tg_id)
    if not user:
        return False, "Пользователь не найден"
    
    free = user[7]
    sub = user[5]
    daily = user[8]
    
    if free > 0:
        return True, "free"
    if sub == 'gold':
        return True, "ok"
    if sub == 'bronze' and daily < 10:
        return True, "ok"
    if sub == 'silver' and daily < 15:
        return True, "ok"
    return False, "❌ Нет бесплатных оценок или подписки"

def can_battle(tg_id):
    user = get_user(tg_id)
    if not user:
        return False, "Пользователь не найден"
    sub = user[5]
    daily_b = user[9]
    if sub == 'gold':
        return True, "ok"
    if sub == 'silver' and daily_b < 3:
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

def use_free_rating(tg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET free_ratings = free_ratings - 1 WHERE tg_id = ? AND free_ratings > 0", (tg_id,))
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
    conn.close()
    return total_users, total_ratings, total_battles

def use_promo_code(code, tg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes WHERE code = ? AND uses_left > 0", (code,))
    promo = c.fetchone()
    if not promo:
        conn.close()
        return False, "Промокод не найден"
    
    if promo[3] > 0:
        add_free_ratings(tg_id, promo[3])
    
    c.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return True, f"✅ Получено {promo[3]} бесплатных оценок!"

def create_promo_code(code, discount, free, uses, admin_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO promo_codes (code, discount_percent, free_ratings, uses_left, created_by) 
                 VALUES (?, ?, ?, ?, ?)''', (code, discount, free, uses, admin_id))
    conn.commit()
    conn.close()

# ==================== АНАЛИЗ ФОТО ====================
def analyze_photo(image_data):
    try:
        img = Image.open(io.BytesIO(image_data))
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        brightness = ImageStat.Stat(img).mean[0]
        
        random.seed(int(brightness * 100))
        verdicts = ["LTN", "MTN", "HTN"]
        verdict = random.choice(verdicts)
        
        return {
            "verdict": verdict,
            "observation": f"Яркость фото: {int(brightness)}/255",
            "strengths": "Хорошее качество" if brightness > 80 else "Среднее качество",
            "improvements": "Улучшите освещение" if brightness < 60 else "Можно другой ракурс",
            "confidence": "Высокая" if brightness > 100 else "Средняя"
        }
    except Exception as e:
        return {
            "verdict": "Ошибка",
            "observation": f"Не удалось обработать: {str(e)}",
            "strengths": "-",
            "improvements": "-",
            "confidence": "Низкая"
        }

# ==================== БОТ ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранилище для батлов
user_photos = {}

# ----- ПРОВЕРКА ПОДПИСКИ -----
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ----- /START -----
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username or "anon",
        message.from_user.first_name or "User"
    )
    
    if not await check_subscription(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url="https://t.me/KennyChadPSL")],
            [InlineKeyboardButton(text="🔄 Проверить", callback_data="check_sub")]
        ])
        await message.answer(
            "🔒 <b>Требуется подписка!</b>\n\n"
            "Подпишитесь на @KennyChadPSL",
            reply_markup=kb
        )
        return
    
    await show_menu(message)

async def show_menu(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    free = user[7]
    sub = user[5]
    role = user[4]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Оценить фото", callback_data="rate")],
        [InlineKeyboardButton(text="⚔️ Батл", callback_data="battle")],
        [InlineKeyboardButton(text="💎 Подписки", callback_data="subscriptions")],
        [InlineKeyboardButton(text="🎫 Промокод", callback_data="promo")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])
    
    if role == "owner":
        kb.inline_keyboard.append([InlineKeyboardButton(text="⚙️ Админ", callback_data="admin")])
    
    await message.answer(
        f"👋 <b>Добро пожаловать!</b>\n\n"
        f"⭐ Бесплатно: <b>{free}</b>\n"
        f"📅 Подписка: <b>{sub.upper() if sub != 'none' else 'Нет'}</b>",
        reply_markup=kb
    )

# ----- ПРОВЕРКА ПОДПИСКИ (callback) -----
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await show_menu(callback.message)
        await callback.answer("✅ Подписка подтверждена!", show_alert=True)
    else:
        await callback.answer("❌ Вы не подписаны!", show_alert=True)

# ----- ОЦЕНКА -----
@dp.callback_query(F.data == "rate")
async def rate_callback(callback: types.CallbackQuery):
    await callback.message.answer("📸 Отправьте фото для оценки")
    await callback.answer()

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ /start")
        return
    
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишитесь на @KennyChadPSL")
        return
    
    can, msg = can_rate(message.from_user.id)
    if not can:
        await message.answer(msg)
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_data = await bot.download_file(file.file_path)
    image_bytes = image_data.getvalue()
    
    result = analyze_photo(image_bytes)
    
    photo_id = str(photo.file_id)
    save_rating(message.from_user.id, photo_id, result["verdict"], 
               result["observation"], result["strengths"], 
               result["improvements"], result["confidence"])
    
    if can == "free":
        use_free_rating(message.from_user.id)
    else:
        increment_usage(message.from_user.id, "rate")
    
    await message.answer(
        f"📸 <b>Результат</b>\n\n"
        f"🎯 Вердикт: <code>{result['verdict']}</code>\n\n"
        f"👀 {result['observation']}\n"
        f"✅ {result['strengths']}\n"
        f"📈 {result['improvements']}\n"
        f"📊 Уверенность: {result['confidence']}"
    )
    
    await show_menu(message)

# ----- БАТЛ -----
@dp.callback_query(F.data == "battle")
async def battle_callback(callback: types.CallbackQuery):
    user_photos[callback.from_user.id] = []
    await callback.message.answer("⚔️ Отправьте ДВА фото по очереди")
    await callback.answer()

@dp.message(F.photo)
async def handle_battle_photo(message: types.Message):
    user_id = message.from_user.id
    
    if not await check_subscription(user_id):
        await message.answer("❌ Подпишитесь на @KennyChadPSL")
        return
    
    if user_id not in user_photos:
        user_photos[user_id] = []
    
    if len(user_photos[user_id]) >= 2:
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_data = await bot.download_file(file.file_path)
    image_bytes = image_data.getvalue()
    
    user_photos[user_id].append(image_bytes)
    
    if len(user_photos[user_id]) == 1:
        await message.answer("📸 Фото 1 сохранено! Теперь второе")
    elif len(user_photos[user_id]) == 2:
        can, msg = can_battle(user_id)
        if not can:
            await message.answer(msg)
            del user_photos[user_id]
            return
        
        img1 = user_photos[user_id][0]
        img2 = user_photos[user_id][1]
        
        result1 = analyze_photo(img1)
        result2 = analyze_photo(img2)
        
        score_map = {"LTN": 1, "MTN": 2, "HTN": 3}
        score1 = score_map.get(result1["verdict"], 1)
        score2 = score_map.get(result2["verdict"], 1)
        
        if score1 > score2:
            winner = "Фото 1"
            reason = f"{result1['verdict']} > {result2['verdict']}"
        elif score2 > score1:
            winner = "Фото 2"
            reason = f"{result2['verdict']} > {result1['verdict']}"
        else:
            winner = "Ничья"
            reason = "Одинаковые оценки"
        
        save_battle(user_id, "photo1", "photo2", result1["verdict"], result2["verdict"], winner, reason)
        increment_usage(user_id, "battle")
        
        del user_photos[user_id]
        
        await message.answer(
            f"⚔️ <b>Результат батла</b>\n\n"
            f"📸 Фото 1: <code>{result1['verdict']}</code>\n"
            f"📸 Фото 2: <code>{result2['verdict']}</code>\n\n"
            f"🏆 Победитель: <code>{winner}</code>\n"
            f"💬 {reason}"
        )
        
        await show_menu(message)

# ----- ПОДПИСКИ -----
@dp.callback_query(F.data == "subscriptions")
async def subscriptions_callback(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 Bronze — 100⭐", callback_data="buy_bronze")],
        [InlineKeyboardButton(text="🥈 Silver — 200⭐", callback_data="buy_silver")],
        [InlineKeyboardButton(text="🥇 Gold — 450⭐", callback_data="buy_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    await callback.message.edit_text(
        "💎 <b>Тарифы</b>\n\n"
        "🥉 Bronze: 10 оценок/день\n"
        "🥈 Silver: 15 оценок + 3 батла/день\n"
        "🥇 Gold: Безлимит",
        reply_markup=kb
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
        await message.answer(f"✅ Подписка <b>{plan.capitalize()}</b> активирована!")
    await show_menu(message)

# ----- ПРОМОКОД -----
@dp.callback_query(F.data == "promo")
async def promo_callback(callback: types.CallbackQuery):
    await callback.message.answer("🎫 Введите промокод текстом")
    await callback.answer()

@dp.message(F.text)
async def handle_promo(message: types.Message):
    if message.text.startswith("/"):
        return
    
    user = get_user(message.from_user.id)
    if not user:
        return
    
    # Проверяем, админ ли создаёт промокод
    if user[4] == "owner" and "|" in message.text:
        parts = message.text.split("|")
        if len(parts) == 4:
            try:
                code, discount, free, uses = parts
                create_promo_code(code.upper(), int(discount), int(free), int(uses), user[0])
                await message.answer(f"✅ Промокод {code.upper()} создан!")
                return
            except:
                await message.answer("❌ Ошибка формата")
                return
    
    # Использование промокода
    success, msg = use_promo_code(message.text.upper(), message.from_user.id)
    if success:
        await message.answer(msg)
        await show_menu(message)
    else:
        await message.answer("❌ Промокод не найден")

# ----- СТАТИСТИКА -----
@dp.callback_query(F.data == "stats")
async def stats_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"⭐ Бесплатно: <b>{user[7]}</b>\n"
        f"📅 Подписка: <b>{user[5].upper() if user[5] != 'none' else 'Нет'}</b>\n"
        f"📸 Оценок: <b>{user[10]}</b>\n"
        f"⚔️ Батлов: <b>{user[11]}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back_callback(callback: types.CallbackQuery):
    await callback.message.delete()
    await show_menu(callback.message)
    await callback.answer()

# ----- АДМИН -----
@dp.callback_query(F.data == "admin")
async def admin_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[4] != "owner":
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    total_users, total_ratings, total_battles = get_stats()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    
    await callback.message.edit_text(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📸 Оценок: <b>{total_ratings}</b>\n"
        f"⚔️ Батлов: <b>{total_battles}</b>",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    total_users, total_ratings, total_battles = get_stats()
    await callback.message.edit_text(
        f"📊 <b>Полная статистика</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📸 Оценок: <b>{total_ratings}</b>\n"
        f"⚔️ Батлов: <b>{total_battles}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_promo")
async def admin_promo_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        "🎫 <b>Создание промокода</b>\n\n"
        "Формат:\n"
        "<code>КОД|СКИДКА|БЕСПЛ_ОЦЕНКИ|ИСПОЛЬЗОВАНИЙ</code>\n\n"
        "Пример:\n"
        "<code>SUMMER|0|5|10</code>"
    )
    await callback.answer()

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
