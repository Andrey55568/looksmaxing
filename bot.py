import asyncio
import sqlite3
import json
import io
import random
import base64
from datetime import datetime, timedelta
from PIL import Image, ImageStat
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==================== КОНФИГ ====================
BOT_TOKEN = "8706127340:AAHPeKEi1gQB9l1Tt9Ryxua93bRmF4K5lJs"
ADMIN_ID = 8061549073
CHANNEL_ID = "@KennyChadPSL"  # Канал для подписки

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

def add_free_ratings(tg_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET free_ratings = free_ratings + ? WHERE tg_id = ?", (amount, tg_id))
    conn.commit()
    conn.close()

def can_rate(tg_id):
    user = get_user(tg_id)
    if not user:
        return False, "Пользователь не найден"
    sub = user[5]
    daily = user[8]
    free = user[7]
    
    if free > 0:
        return True, "free"
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
    return False, "❌ Нет подписки или бесплатных оценок"

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
    c.execute("SELECT SUM(stars_balance) FROM users")
    total_stars = c.fetchone()[0] or 0
    conn.close()
    return total_users, total_ratings, total_battles, total_stars

# ==================== ПРОМОКОДЫ ====================
def create_promo_code(code, discount_percent, free_ratings, uses_left, admin_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO promo_codes (code, discount_percent, free_ratings, uses_left, created_by) 
                 VALUES (?, ?, ?, ?, ?)''', (code, discount_percent, free_ratings, uses_left, admin_id))
    conn.commit()
    conn.close()

def use_promo_code(code, tg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes WHERE code = ? AND uses_left > 0", (code,))
    promo = c.fetchone()
    if not promo:
        conn.close()
        return False, "Промокод не найден или уже использован"
    
    # Начисляем бонусы
    if promo[2] > 0:
        # Скидка на подписку
        pass
    if promo[3] > 0:
        add_free_ratings(tg_id, promo[3])
    
    # Уменьшаем количество использований
    c.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return True, f"✅ Промокод активирован! Получено {promo[3]} бесплатных оценок"

# ==================== АНАЛИЗ ФОТО ====================
def analyze_photo(image_data):
    try:
        img = Image.open(io.BytesIO(image_data))
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        brightness = ImageStat.Stat(img).mean[0]
        contrast = ImageStat.Stat(img).std[0]
        
        quality = "Хорошее"
        if brightness < 40:
            quality = "Тёмное"
        elif brightness > 220:
            quality = "Пересвеченное"
        elif contrast < 20:
            quality = "Низкий контраст"
        
        random.seed(int(brightness * 100))
        if quality == "Хорошее":
            verdict = random.choice(["LTN", "MTN", "HTN"])
        elif quality == "Тёмное":
            verdict = "LTN"
        else:
            verdict = random.choice(["LTN", "MTN"])
        
        return {
            "verdict": verdict,
            "observation": f"Качество фото: {quality}",
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

# ==================== БОТ ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ----- ПРОВЕРКА ПОДПИСКИ -----
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ----- КОМАНДА /START -----
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username or "anon",
        message.from_user.first_name or "User"
    )
    
    # Проверяем подписку
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/KennyChadPSL")],
            [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="check_sub")]
        ])
        await message.answer(
            "🔒 <b>Доступ к боту требует подписки!</b>\n\n"
            "Подпишитесь на наш канал, чтобы пользоваться ботом:\n"
            "👉 @KennyChadPSL",
            reply_markup=kb
        )
        return
    
    # Показываем главное меню
    await show_main_menu(message, user)

async def show_main_menu(message, user=None):
    if not user:
        user = get_user(message.from_user.id)
    
    stars = user[7]
    sub = user[5]
    role = user[4]
    free = user[7]  # бесплатные оценки
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Оценить фото", callback_data="rate_photo")],
        [InlineKeyboardButton(text="⚔️ Батл (2 фото)", callback_data="battle_photo")],
        [InlineKeyboardButton(text="💎 Подписки", callback_data="subscriptions")],
        [InlineKeyboardButton(text="🎫 Промокод", callback_data="promo")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")]
    ])
    
    if role == "owner":
        kb.inline_keyboard.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    
    await message.answer(
        f"👋 <b>Добро пожаловать, {message.from_user.first_name}!</b>\n\n"
        f"⭐ Бесплатных оценок: <b>{free}</b>\n"
        f"📅 Подписка: <b>{sub.upper() if sub != 'none' else 'Нет'}</b>\n"
        f"👤 Роль: <b>{role}</b>\n\n"
        f"<i>Выберите действие:</i>",
        reply_markup=kb
    )

# ----- ПРОВЕРКА ПОДПИСКИ (callback) -----
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        user = get_user(callback.from_user.id)
        await callback.message.delete()
        await show_main_menu(callback.message, user)
        await callback.answer("✅ Подписка подтверждена!", show_alert=True)
    else:
        await callback.answer("❌ Вы ещё не подписались!", show_alert=True)

# ----- ОЦЕНКА ФОТО (запрос фото) -----
@dp.callback_query(F.data == "rate_photo")
async def rate_photo_callback(callback: types.CallbackQuery):
    await callback.message.answer("📸 <b>Отправьте фото для оценки</b>\n\n(одно фото)")
    await callback.answer()

# ----- ОБРАБОТКА ФОТО (оценка) -----
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала выполните /start")
        return
    
    # Проверяем подписку
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишитесь на канал @KennyChadPSL")
        return
    
    # Проверяем возможность оценки
    can, msg = can_rate(message.from_user.id)
    if not can:
        await message.answer(msg)
        return
    
    # Скачиваем фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_data = await bot.download_file(file.file_path)
    image_bytes = image_data.getvalue()
    
    # Анализируем
    result = analyze_photo(image_bytes)
    
    # Сохраняем
    photo_id = str(message.photo[-1].file_id)
    save_rating(message.from_user.id, photo_id, result["verdict"], 
               result["observation"], result["strengths"], 
               result["improvements"], result["confidence"])
    
    # Если использовали бесплатную оценку
    if can == "free":
        use_free_rating(message.from_user.id)
    else:
        increment_usage(message.from_user.id, "rate")
    
    # Отправляем результат
    await message.answer(
        f"📸 <b>Результат оценки</b>\n\n"
        f"🎯 <b>Вердикт:</b> <code>{result['verdict']}</code>\n\n"
        f"👀 <b>Наблюдения:</b>\n{result['observation']}\n\n"
        f"✅ <b>Сильные стороны:</b>\n{result['strengths']}\n\n"
        f"📈 <b>Что улучшить:</b>\n{result['improvements']}\n\n"
        f"📊 <b>Уверенность:</b> {result['confidence']}"
    )
    
    # Показываем меню
    await show_main_menu(message)

# ----- БАТЛ (запрос 2 фото) -----
@dp.callback_query(F.data == "battle_photo")
async def battle_photo_callback(callback: types.CallbackQuery):
    await callback.message.answer("⚔️ <b>Отправьте ДВА фото для батла</b>\n\n(сначала одно, потом второе)")
    await callback.answer()

# ----- ОБРАБОТКА БАТЛА (сохраняем фото в памяти) -----
user_photos = {}

@dp.message(F.photo)
async def handle_battle_photo(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем подписку
    if not await check_subscription(user_id):
        await message.answer("❌ Подпишитесь на канал @KennyChadPSL")
        return
    
    # Проверяем батл
    can, msg = can_battle(user_id)
    if not can:
        await message.answer(msg)
        return
    
    # Сохраняем фото
    if user_id not in user_photos:
        user_photos[user_id] = []
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_data = await bot.download_file(file.file_path)
    image_bytes = image_data.getvalue()
    
    user_photos[user_id].append(image_bytes)
    
    if len(user_photos[user_id]) == 1:
        await message.answer("📸 <b>Фото 1 сохранено!</b>\nТеперь отправьте <b>второе</b> фото")
    elif len(user_photos[user_id]) == 2:
        # Анализируем оба
        img1 = user_photos[user_id][0]
        img2 = user_photos[user_id][1]
        
        result1 = analyze_photo(img1)
        result2 = analyze_photo(img2)
        
        score_map = {"LTN": 1, "MTN": 2, "HTN": 3, "Chadlite": 4, "Chad": 5}
        score1 = score_map.get(result1.get("verdict", "MTN"), 2)
        score2 = score_map.get(result2.get("verdict", "MTN"), 2)
        
        if score1 > score2:
            winner = "Фото 1"
            reason = f"Фото 1 ({result1['verdict']}) > Фото 2 ({result2['verdict']})"
        elif score2 > score1:
            winner = "Фото 2"
            reason = f"Фото 2 ({result2['verdict']}) > Фото 1 ({result1['verdict']})"
        else:
            winner = "Ничья"
            reason = "Оба фото получили одинаковую оценку"
        
        # Сохраняем батл
        save_battle(user_id, "photo1", "photo2", result1["verdict"], result2["verdict"], winner, reason)
        increment_usage(user_id, "battle")
        
        # Очищаем память
        del user_photos[user_id]
        
        await message.answer(
            f"⚔️ <b>Результат батла</b>\n\n"
            f"📸 Фото 1: <code>{result1['verdict']}</code>\n"
            f"📸 Фото 2: <code>{result2['verdict']}</code>\n\n"
            f"🏆 <b>Победитель:</b> <code>{winner}</code>\n\n"
            f"💬 <b>Причина:</b>\n{reason}"
        )
        
        # Показываем меню
        await show_main_menu(message)

# ----- ПОДПИСКИ -----
@dp.callback_query(F.data == "subscriptions")
async def subscriptions_callback(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 Bronze — 10 оценок/день", callback_data="buy_bronze")],
        [InlineKeyboardButton(text="🥈 Silver — 15 оценок + 3 батла", callback_data="buy_silver")],
        [InlineKeyboardButton(text="🥇 Gold — Безлимит", callback_data="buy_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(
        "💎 <b>Выберите тариф:</b>\n\n"
        "🥉 <b>Bronze</b> — 100⭐/мес\n"
        "   • 10 оценок в день\n\n"
        "🥈 <b>Silver</b> — 200⭐/мес\n"
        "   • 15 оценок в день\n"
        "   • 3 батла в день\n\n"
        "🥇 <b>Gold</b> — 450⭐/мес\n"
        "   • Безлимит на всё",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "buy_bronze")
async def buy_bronze(callback: types.CallbackQuery):
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Bronze Subscription",
        description="10 оценок в день на 30 дней",
        payload="sub_bronze",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Bronze", "amount": 100}],
        start_parameter="subscription"
    )
    await callback.answer()

@dp.callback_query(F.data == "buy_silver")
async def buy_silver(callback: types.CallbackQuery):
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Silver Subscription",
        description="15 оценок + 3 батла в день на 30 дней",
        payload="sub_silver",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Silver", "amount": 200}],
        start_parameter="subscription"
    )
    await callback.answer()

@dp.callback_query(F.data == "buy_gold")
async def buy_gold(callback: types.CallbackQuery):
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Gold Subscription",
        description="Безлимит на 30 дней",
        payload="sub_gold",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Gold", "amount": 450}],
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
    await show_main_menu(message)

# ----- ПРОМОКОД -----
@dp.callback_query(F.data == "promo")
async def promo_callback(callback: types.CallbackQuery):
    await callback.message.answer("🎫 <b>Введите промокод</b>\n\n(отправьте текстом)")
    await callback.answer()

@dp.message(F.text)
async def handle_promo(message: types.Message):
    if message.text.startswith("/"):
        return
    
    user = get_user(message.from_user.id)
    if not user:
        return
    
    # Проверяем, может это промокод
    success, msg = use_promo_code(message.text.upper(), message.from_user.id)
    if success:
        await message.answer(msg)
    else:
        # Если не промокод — просто игнорируем
        pass
    await show_main_menu(message)

# ----- СТАТИСТИКА -----
@dp.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"⭐ Бесплатных оценок: <b>{user[7]}</b>\n"
        f"📅 Подписка: <b>{user[5].upper() if user[5] != 'none' else 'Нет'}</b>\n"
        f"📸 Всего оценок: <b>{user[10]}</b>\n"
        f"⚔️ Всего батлов: <b>{user[11]}</b>\n"
        f"📈 Оценок сегодня: <b>{user[8]}/15</b>\n"
        f"⚔️ Батлов сегодня: <b>{user[9]}/3</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.delete()
    await show_main_menu(callback.message, user)
    await callback.answer()

# ==================== АДМИН-ПАНЕЛЬ ====================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[4] != 'owner':
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    total_users, total_ratings, total_battles, total_stars = get_stats()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📸 Оценок: <b>{total_ratings}</b>\n"
        f"⚔️ Батлов: <b>{total_battles}</b>\n"
        f"⭐ Звёзд: <b>{total_stars}</b>",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[4] != 'owner':
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    total_users, total_ratings, total_battles, total_stars = get_stats()
    
    # Собираем топ пользователей
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, total_ratings FROM users WHERE role != 'owner' ORDER BY total_ratings DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    top_text = "\n".join([f"{i+1}. @{u[0] or 'anon'} — {u[1]} оценок" for i, u in enumerate(top_users)])
    
    await callback.message.edit_text(
        f"📊 <b>Полная статистика</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📸 Оценок: <b>{total_ratings}</b>\n"
        f"⚔️ Батлов: <b>{total_battles}</b>\n"
        f"⭐ Звёзд: <b>{total_stars}</b>\n\n"
        f"🏆 <b>Топ пользователей:</b>\n{top_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_promo")
async def admin_promo_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[4] != 'owner':
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "🎫 <b>Создание промокода</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>ПРОМОКОД|скидка%|бесплатных_оценок|кол-во_использований</code>\n\n"
        "Пример:\n"
        "<code>SUMMER2024|0|5|10</code> — даст 5 бесплатных оценок, можно использовать 10 раз\n"
        "<code>VIP50|50|0|1</code> — скидка 50% на подписку, можно использовать 1 раз"
    )
    await callback.answer()

@dp.message(F.text)
async def handle_admin_promo(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or user[4] != 'owner':
        return
    
    if "|" not in message.text:
        return
    
    parts = message.text.split("|")
    if len(parts) != 4:
        await message.answer("❌ Неверный формат! Используйте: КОД|СКИДКА|БЕСПЛ_ОЦЕНКИ|ИСПОЛЬЗОВАНИЙ")
        return
    
    code, discount, free, uses = parts
    try:
        discount = int(discount)
        free = int(free)
        uses = int(uses)
    except:
        await message.answer("❌ Скидка, оценки и использования должны быть числами")
        return
    
    create_promo_code(code.upper(), discount, free, uses, message.from_user.id)
    await message.answer(f"✅ Промокод <b>{code.upper()}</b> создан!\n\n"
                        f"🎫 Скидка: {discount}%\n"
                        f"⭐ Бесплатных оценок: {free}\n"
                        f"📊 Использований: {uses}")

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user[4] != 'owner':
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer("📢 <b>Рассылка</b>\n\nОтправьте сообщение для рассылки всем пользователям")
    await callback.answer()

@dp.message(F.text)
async def handle_broadcast(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or user[4] != 'owner':
        return
    
    # Проверяем, что это рассылка (не команда и не промокод)
    if message.text.startswith("/") or "|" in message.text:
        return
    
    # Получаем всех пользователей
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE tg_id != ?", (message.from_user.id,))
    users = c.fetchall()
    conn.close()
    
    if not users:
        await message.answer("❌ Нет пользователей для рассылки")
        return
    
    sent = 0
    for user_id in users:
        try:
            await bot.send_message(user_id[0], f"📢 <b>Объявление от администратора</b>\n\n{message.text}")
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    
    await message.answer(f"✅ Рассылка отправлена <b>{sent}</b> пользователям")

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    print("🚀 Бот запущен!")
    print(f"👤 Админ: {ADMIN_ID}")
    print(f"📢 Канал: {CHANNEL_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
