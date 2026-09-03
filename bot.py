import asyncio
import sqlite3
import io
import random
import math
from datetime import datetime, timedelta
from PIL import Image, ImageStat
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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
        free_ratings INTEGER DEFAULT 1,
        daily_ratings INTEGER DEFAULT 0,
        daily_battles INTEGER DEFAULT 0,
        last_reset DATE,
        total_ratings INTEGER DEFAULT 0,
        total_battles INTEGER DEFAULT 0,
        height INTEGER DEFAULT 0,
        weight INTEGER DEFAULT 0,
        age INTEGER DEFAULT 0,
        gender TEXT DEFAULT 'male',
        bmi REAL DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        free_ratings INTEGER DEFAULT 0,
        uses_left INTEGER DEFAULT 1,
        created_by INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        photo_id TEXT,
        verdict TEXT,
        face_score REAL,
        potential_score REAL,
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
        check_daily_bonus(tg_id)
        return user
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'owner'")
    owner_exists = c.fetchone()[0]
    role = 'owner' if owner_exists == 0 else 'user'
    today = datetime.now().date().isoformat()
    c.execute('''INSERT INTO users (tg_id, username, first_name, role, last_reset, free_ratings) 
                 VALUES (?, ?, ?, ?, ?, ?)''', (tg_id, username, first_name, role, today, 1))
    conn.commit()
    conn.close()
    return get_user(tg_id)

def check_daily_bonus(tg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_reset, free_ratings FROM users WHERE tg_id = ?", (tg_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        return
    last_reset, free = result
    today = datetime.now().date().isoformat()
    if last_reset != today:
        c.execute("UPDATE users SET free_ratings = free_ratings + 1, last_reset = ? WHERE tg_id = ?", (today, tg_id))
        conn.commit()
    conn.close()

def update_user_stats(tg_id, height, weight, age, gender):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    bmi = weight / ((height/100) ** 2) if height > 0 and weight > 0 else 0
    c.execute('''UPDATE users SET height = ?, weight = ?, age = ?, gender = ?, bmi = ? 
                 WHERE tg_id = ?''', (height, weight, age, gender, bmi, tg_id))
    conn.commit()
    conn.close()
    return bmi

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
    if user[4] == 'owner':
        return True, "owner"
    check_daily_bonus(tg_id)
    user = get_user(tg_id)
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
    return False, "❌ Бесплатные оценки закончились. Завтра +1."

def can_battle(tg_id):
    user = get_user(tg_id)
    if not user:
        return False, "Пользователь не найден"
    if user[4] == 'owner':
        return True, "owner"
    sub = user[5]
    daily_b = user[9]
    if sub == 'gold':
        return True, "ok"
    if sub == 'silver' and daily_b < 3:
        return True, "ok"
    return False, "❌ Батл только с Silver/Gold"

def increment_usage(tg_id, typ):
    user = get_user(tg_id)
    if user and user[4] == 'owner':
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if typ == 'rate':
        c.execute("UPDATE users SET daily_ratings = daily_ratings + 1, total_ratings = total_ratings + 1 WHERE tg_id = ?", (tg_id,))
    elif typ == 'battle':
        c.execute("UPDATE users SET daily_battles = daily_battles + 1, total_battles = total_battles + 1 WHERE tg_id = ?", (tg_id,))
    conn.commit()
    conn.close()

def use_free_rating(tg_id):
    user = get_user(tg_id)
    if user and user[4] == 'owner':
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET free_ratings = free_ratings - 1 WHERE tg_id = ? AND free_ratings > 0", (tg_id,))
    conn.commit()
    conn.close()

def save_rating(tg_id, photo_id, verdict, face_score, potential_score, observation, strengths, improvements, confidence):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO ratings (user_id, photo_id, verdict, face_score, potential_score, observation, strengths, improvements, confidence) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (tg_id, photo_id, verdict, face_score, potential_score, observation, strengths, improvements, confidence))
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
        return False, "❌ Промокод не найден или использован"
    add_free_ratings(tg_id, promo[2])
    c.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return True, f"✅ +{promo[2]} бесплатных оценок!"

def create_promo_code(code, free, uses):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO promo_codes (code, free_ratings, uses_left, created_by) 
                 VALUES (?, ?, ?, ?)''', (code.upper(), free, uses, ADMIN_ID))
    conn.commit()
    conn.close()

def get_all_promo_codes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT code, free_ratings, uses_left FROM promo_codes WHERE uses_left > 0")
    codes = c.fetchall()
    conn.close()
    return codes

def get_top_users(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT username, total_ratings, total_battles 
                 FROM users WHERE role != 'owner' 
                 ORDER BY total_ratings DESC LIMIT ?''', (limit,))
    top = c.fetchall()
    conn.close()
    return top

# ==================== АНАЛИЗ ФОТО (ИСПРАВЛЕННЫЙ) ====================
def analyze_photo(image_data):
    try:
        # Пытаемся открыть изображение
        img = Image.open(io.BytesIO(image_data))
        
        # Приводим к RGB
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Уменьшаем для ускорения
        img.thumbnail((600, 600), Image.Resampling.LANCZOS)
        
        # Получаем яркость и контраст
        stat = ImageStat.Stat(img)
        brightness = stat.mean[0] if stat.mean else 128
        contrast = stat.std[0] if stat.std else 30
        
        # Генерируем скор на основе параметров фото
        random.seed(int(brightness * 100 + contrast))
        base_score = 3.0 + (brightness / 255) * 3.0 + (contrast / 100) * 1.5
        face_score = round(min(max(base_score, 2.5), 9.0), 1)
        potential_score = round(min(max(2.0 + (contrast / 100) * 4.0, 2.0), 9.0), 1)
        
        # Вердикт
        if face_score >= 8.0:
            verdict = "True Adam"
        elif face_score >= 7.0:
            verdict = "Chad"
        elif face_score >= 6.0:
            verdict = "Chadlite"
        elif face_score >= 5.5:
            verdict = "HTN"
        elif face_score >= 4.5:
            verdict = "MTN"
        elif face_score >= 3.5:
            verdict = "LTN"
        else:
            verdict = "Sub5"
        
        # Рекомендации
        if potential_score > 7:
            improvements = "🔥 Огромный потенциал! Работай над массой/осанкой."
        elif potential_score > 5:
            improvements = "💪 Хороший потенциал. Смени причёску/стиль."
        else:
            improvements = "📈 Работай над кожей/формой лица."
        
        return {
            "verdict": verdict,
            "face_score": face_score,
            "potential_score": potential_score,
            "observation": f"⭐ Яркость: {int(brightness)}/255, Контраст: {int(contrast)}",
            "strengths": "✅ Отличное фото" if brightness > 150 else "📷 Хорошее фото",
            "improvements": improvements,
            "confidence": "🔥 Высокая" if brightness > 120 and contrast > 40 else "📊 Средняя"
        }
    except Exception as e:
        # Запасной вариант при ошибке
        print(f"Ошибка анализа фото: {e}")
        random.seed(datetime.now().microsecond)
        face_score = round(random.uniform(3.0, 8.0), 1)
        potential_score = round(random.uniform(2.0, 9.0), 1)
        
        if face_score >= 8.0:
            verdict = "True Adam"
        elif face_score >= 7.0:
            verdict = "Chad"
        elif face_score >= 6.0:
            verdict = "Chadlite"
        elif face_score >= 5.5:
            verdict = "HTN"
        elif face_score >= 4.5:
            verdict = "MTN"
        elif face_score >= 3.5:
            verdict = "LTN"
        else:
            verdict = "Sub5"
        
        return {
            "verdict": verdict,
            "face_score": face_score,
            "potential_score": potential_score,
            "observation": "⚠️ Обработано запасным алгоритмом (не удалось распознать фото)",
            "strengths": "—",
            "improvements": "Попробуй другое фото или улучши освещение",
            "confidence": "Средняя"
        }

# ==================== КЛАВИАТУРА ====================
def get_main_keyboard(role="user"):
    keyboard = [
        [KeyboardButton(text="📸 Оценить"), KeyboardButton(text="⚔️ Батл")],
        [KeyboardButton(text="📊 Моя статистика"), KeyboardButton(text="💎 Подписки")],
        [KeyboardButton(text="🎫 Промокод"), KeyboardButton(text="📏 Антропометрия")],
        [KeyboardButton(text="🏆 Топ-10"), KeyboardButton(text="📈 Мой потенциал")]
    ]
    if role == "owner":
        keyboard.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==================== БОТ ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
user_photos_battle = {}

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ==================== /START ====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username or "anon",
        message.from_user.first_name or "User"
    )
    
    if not await check_subscription(message.from_user.id):
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📢 Подписаться", url="https://t.me/KennyChadPSL")]],
            resize_keyboard=True
        )
        await message.answer(
            "🔒 <b>ТРЕБУЕТСЯ ПОДПИСКА!</b>\n\n"
            "Подпишись на канал, чтобы использовать бота:\n"
            "👉 @KennyChadPSL",
            reply_markup=kb
        )
        return
    
    await show_menu(message)

async def show_menu(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    check_daily_bonus(message.from_user.id)
    user = get_user(message.from_user.id)
    
    free = user[7]
    sub = user[5]
    role = user[4]
    
    await message.answer(
        f"🏠 <b>ГЛАВНОЕ МЕНЮ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⭐ Бесплатно: <b>{free}</b> (+1 каждый день)\n"
        f"📅 Подписка: <b>{sub.upper() if sub != 'none' else 'Нет'}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👇 <i>Выбери действие на панели внизу</i>",
        reply_markup=get_main_keyboard(role)
    )

# ==================== ОЦЕНКА ФОТО ====================
@dp.message(F.text == "📸 Оценить")
async def rate_button(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ /start")
        return
    
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишись на @KennyChadPSL")
        return
    
    can, msg = can_rate(message.from_user.id)
    if not can:
        await message.answer(msg)
        return
    
    await message.answer(
        "📸 <b>Отправь фото для оценки</b>\n\n"
        "Я оценю: лицо, потенциал и дам рекомендации",
        reply_markup=get_main_keyboard(user[4])
    )

# ==================== ОБРАБОТКА ФОТО ====================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ /start")
        return
    
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишись на @KennyChadPSL")
        return
    
    # Проверяем, не батл ли это
    if message.from_user.id in user_photos_battle:
        await handle_battle_photo(message)
        return
    
    can, msg = can_rate(message.from_user.id)
    if not can:
        await message.answer(msg)
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file.file_path)
    image_bytes = downloaded_file.getvalue()
    
    result = analyze_photo(image_bytes)
    photo_id = str(photo.file_id)
    save_rating(message.from_user.id, photo_id, result["verdict"], 
               result["face_score"], result["potential_score"],
               result["observation"], result["strengths"], 
               result["improvements"], result["confidence"])
    
    if can != "owner":
        if can == "free":
            use_free_rating(message.from_user.id)
        else:
            increment_usage(message.from_user.id, "rate")
    
    user = get_user(message.from_user.id)
    free = user[7]
    
    await message.answer(
        f"📸 <b>РЕЗУЛЬТАТ ОЦЕНКИ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Вердикт:</b> <code>{result['verdict']}</code>\n"
        f"⭐ <b>Скор лица:</b> {result['face_score']}/10\n"
        f"🚀 <b>Потенциал:</b> {result['potential_score']}/10\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👀 {result['observation']}\n"
        f"✅ {result['strengths']}\n"
        f"📈 {result['improvements']}\n"
        f"📊 <b>Уверенность:</b> {result['confidence']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⭐ Осталось: <b>{free}</b> бесплатных оценок",
        reply_markup=get_main_keyboard(user[4])
    )

# ==================== БАТЛ ====================
@dp.message(F.text == "⚔️ Батл")
async def battle_button(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ /start")
        return
    
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишись на @KennyChadPSL")
        return
    
    can, msg = can_battle(message.from_user.id)
    if not can:
        await message.answer(msg)
        return
    
    user_photos_battle[message.from_user.id] = []
    await message.answer(
        "⚔️ <b>БАТЛ</b>\n\n"
        "Отправь <b>ДВА</b> фото по очереди.\n"
        "Я сравню их и скажу, кто победил!",
        reply_markup=get_main_keyboard(user[4])
    )

async def handle_battle_photo(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user_id not in user_photos_battle:
        user_photos_battle[user_id] = []
    
    if len(user_photos_battle[user_id]) >= 2:
        return
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file.file_path)
    image_bytes = downloaded_file.getvalue()
    user_photos_battle[user_id].append(image_bytes)
    
    if len(user_photos_battle[user_id]) == 1:
        await message.answer("📸 <b>Фото 1 сохранено!</b> Теперь отправь <b>второе</b>")
    elif len(user_photos_battle[user_id]) == 2:
        img1 = user_photos_battle[user_id][0]
        img2 = user_photos_battle[user_id][1]
        result1 = analyze_photo(img1)
        result2 = analyze_photo(img2)
        
        score1 = result1["face_score"]
        score2 = result2["face_score"]
        
        if score1 > score2:
            winner = "🏆 <b>Фото 1</b>"
            reason = f"Скор {score1:.1f} > {score2:.1f}"
        elif score2 > score1:
            winner = "🏆 <b>Фото 2</b>"
            reason = f"Скор {score2:.1f} > {score1:.1f}"
        else:
            winner = "🤝 <b>Ничья</b>"
            reason = "Одинаковые скоры!"
        
        save_battle(user_id, "photo1", "photo2", result1["verdict"], result2["verdict"], winner, reason)
        increment_usage(user_id, "battle")
        
        del user_photos_battle[user_id]
        
        await message.answer(
            f"⚔️ <b>РЕЗУЛЬТАТ БАТЛА</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📸 Фото 1: <code>{result1['verdict']}</code> ({result1['face_score']:.1f}/10)\n"
            f"📸 Фото 2: <code>{result2['verdict']}</code> ({result2['face_score']:.1f}/10)\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{winner}\n"
            f"💬 {reason}",
            reply_markup=get_main_keyboard(user[4])
        )

# ==================== СТАТИСТИКА ====================
@dp.message(F.text == "📊 Моя статистика")
async def stats_button(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    check_daily_bonus(message.from_user.id)
    user = get_user(message.from_user.id)
    
    await message.answer(
        f"📊 <b>МОЯ СТАТИСТИКА</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⭐ Бесплатно: <b>{user[7]}</b> (+1 каждый день)\n"
        f"📅 Подписка: <b>{user[5].upper() if user[5] != 'none' else 'Нет'}</b>\n"
        f"📸 Оценок всего: <b>{user[10]}</b>\n"
        f"⚔️ Батлов всего: <b>{user[11]}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Оценок сегодня: <b>{user[8]}/15</b>\n"
        f"⚔️ Батлов сегодня: <b>{user[9]}/3</b>"
    )

# ==================== АНТРОПОМЕТРИЯ ====================
@dp.message(F.text == "📏 Антропометрия")
async def anthropometry_button(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    height = user[12] or 0
    weight = user[13] or 0
    age = user[14] or 0
    gender = user[15] or "male"
    bmi = user[16] or 0
    
    status = "🏋️ Норма" if 18.5 <= bmi <= 24.9 else "⚠️ Отклонение"
    
    await message.answer(
        f"📏 <b>АНТРОПОМЕТРИЯ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📏 Рост: <b>{height} см</b>\n"
        f"⚖️ Вес: <b>{weight} кг</b>\n"
        f"🎂 Возраст: <b>{age} лет</b>\n"
        f"⚤ Пол: <b>{'Мужской' if gender == 'male' else 'Женский'}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🧮 <b>ИМТ:</b> {bmi:.1f} — {status}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>Отправь: рост вес возраст пол</i>\n"
        f"Пример: <code>180 75 25 male</code>"
    )

@dp.message(F.text.regexp(r'^\d+\s+\d+\s+\d+\s+(male|female)$'))
async def handle_anthropometry_input(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    parts = message.text.split()
    height = int(parts[0])
    weight = int(parts[1])
    age = int(parts[2])
    gender = parts[3].lower()
    
    if not (50 <= height <= 250):
        await message.answer("❌ Рост 50-250 см")
        return
    if not (20 <= weight <= 300):
        await message.answer("❌ Вес 20-300 кг")
        return
    if not (10 <= age <= 100):
        await message.answer("❌ Возраст 10-100 лет")
        return
    
    bmi = update_user_stats(message.from_user.id, height, weight, age, gender)
    ideal_weight = 22 * ((height/100) ** 2)
    diff = weight - ideal_weight
    
    await message.answer(
        f"✅ <b>ДАННЫЕ СОХРАНЕНЫ!</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📏 Рост: {height} см\n"
        f"⚖️ Вес: {weight} кг\n"
        f"🎂 Возраст: {age} лет\n"
        f"⚤ Пол: {'Мужской' if gender == 'male' else 'Женский'}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🧮 <b>ИМТ:</b> {bmi:.1f}\n"
        f"💡 <b>Идеальный вес:</b> {ideal_weight:.1f} кг\n"
        f"📊 <b>Отклонение:</b> {diff:+.1f} кг\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>ИМТ 18.5-24.9 — норма</i>"
    )

# ==================== ПРОМОКОД ====================
@dp.message(F.text == "🎫 Промокод")
async def promo_button(message: types.Message):
    await message.answer("🎫 <b>Введите промокод</b>\n\nПример: <code>SUMMER2024</code>")

@dp.message(F.text.regexp(r'^[A-Z0-9]+$'))
async def handle_promo_input(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    if message.text.startswith('/'):
        return
    
    success, msg = use_promo_code(message.text.upper(), message.from_user.id)
    await message.answer(msg)
    if success:
        await show_menu(message)

@dp.message(F.text.regexp(r'^/promo\s+[A-Z0-9]+\s+\d+$'))
async def create_promo_command(message: types.Message):
    user = get_user(message.from_user.id)
    if user[4] != "owner":
        await message.answer("⛔ Только для владельца!")
        return
    
    parts = message.text.split()
    code = parts[1].upper()
    free = int(parts[2])
    create_promo_code(code, free, 999999)
    await message.answer(f"✅ <b>Промокод создан!</b>\n\n"
                        f"🎫 Код: <code>{code}</code>\n"
                        f"⭐ Бесплатных оценок: {free}\n"
                        f"📊 Использований: <b>∞</b>")

# ==================== ПОТЕНЦИАЛ ====================
@dp.message(F.text == "📈 Мой потенциал")
async def potential_button(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT verdict, face_score, potential_score FROM ratings WHERE user_id = ? ORDER BY id DESC LIMIT 1", (message.from_user.id,))
    last = c.fetchone()
    conn.close()
    
    if not last:
        await message.answer("📈 <b>ПОТЕНЦИАЛ</b>\n\nСначала оцени хотя бы одно фото!")
        return
    
    verdict, face_score, potential = last
    
    if potential > 7:
        advice = "🔥 Огромный потенциал! Работай над массой и осанкой. Ты можешь стать Chad!"
    elif potential > 5:
        advice = "💪 Хороший потенциал. Смени причёску, работай над стилем и кожей."
    else:
        advice = "📈 Работай над базой: кожа, причёска, улыбка. Не сдавайся!"
    
    await message.answer(
        f"📈 <b>ТВОЙ ПОТЕНЦИАЛ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 Текущий вердикт: <code>{verdict}</code>\n"
        f"⭐ Скор лица: {face_score}/10\n"
        f"🚀 Потенциал: {potential}/10\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 <b>Рекомендация:</b>\n{advice}"
    )

# ==================== ТОП-10 ====================
@dp.message(F.text == "🏆 Топ-10")
async def top_button(message: types.Message):
    top = get_top_users(10)
    
    if not top:
        await message.answer("🏆 <b>ТОП-10</b>\n\nНет данных. Будь первым!")
        return
    
    text = "🏆 <b>ТОП-10 ПОЛЬЗОВАТЕЛЕЙ</b>\n━━━━━━━━━━━━━━━\n"
    for i, (username, ratings, battles) in enumerate(top, 1):
        text += f"{i}. @{username or 'anon'} — {ratings} оценок, {battles} батлов\n"
    
    await message.answer(text)

# ==================== ПОДПИСКИ ====================
@dp.message(F.text == "💎 Подписки")
async def subscriptions_button(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🥉 Bronze — 100⭐"), KeyboardButton(text="🥈 Silver — 200⭐")],
            [KeyboardButton(text="🥇 Gold — 450⭐")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "💎 <b>ТАРИФЫ</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "🥉 <b>Bronze</b> — 100⭐/мес\n"
        "   • 10 оценок в день\n\n"
        "🥈 <b>Silver</b> — 200⭐/мес\n"
        "   • 15 оценок в день\n"
        "   • 3 батла в день\n\n"
        "🥇 <b>Gold</b> — 450⭐/мес\n"
        "   • Безлимит на всё",
        reply_markup=kb
    )

@dp.message(F.text.startswith("🥉"))
async def buy_bronze(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Bronze Subscription",
        description="10 оценок в день на 30 дней",
        payload="sub_bronze",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Bronze", "amount": 100}],
        start_parameter="subscription"
    )

@dp.message(F.text.startswith("🥈"))
async def buy_silver(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Silver Subscription",
        description="15 оценок + 3 батла в день на 30 дней",
        payload="sub_silver",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Silver", "amount": 200}],
        start_parameter="subscription"
    )

@dp.message(F.text.startswith("🥇"))
async def buy_gold(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Gold Subscription",
        description="Безлимит на 30 дней",
        payload="sub_gold",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Gold", "amount": 450}],
        start_parameter="subscription"
    )

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
    await show_menu(message)

# ==================== АДМИН-ПАНЕЛЬ ====================
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_button(message: types.Message):
    user = get_user(message.from_user.id)
    if user[4] != "owner":
        await message.answer("⛔ Доступ запрещён!")
        return
    
    total_users, total_ratings, total_battles = get_stats()
    codes = get_all_promo_codes()
    
    codes_text = "\n".join([f"• <code>{c[0]}</code> — +{c[1]}⭐ (осталось {c[2]})" for c in codes[:5]])
    if not codes_text:
        codes_text = "Нет активных промокодов"
    
    await message.answer(
        f"⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📸 Оценок: <b>{total_ratings}</b>\n"
        f"⚔️ Батлов: <b>{total_battles}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎫 <b>Активные промокоды:</b>\n{codes_text}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>Создай промокод: /promo КОД КОЛИЧЕСТВО</i>"
    )

# ==================== НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ====================
@dp.message()
async def unknown_message(message: types.Message):
    if message.text and not message.text.startswith('/'):
        await message.answer(
            "❓ <b>Неизвестная команда</b>\n\n"
            "Используй <b>кнопки</b> на панели внизу экрана.\n"
            "Если их нет — нажми /start",
            reply_markup=get_main_keyboard(get_user(message.from_user.id)[4] if get_user(message.from_user.id) else "user")
        )

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    print("🚀 Бот запущен!")
    print(f"👑 Владелец: {ADMIN_ID}")
    print(f"📢 Канал: {CHANNEL_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
