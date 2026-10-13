import logging
import os
import sqlite3
import random
import time
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ============================================================
# ТВОЙ ID (узнать: @userinfobot)
# ============================================================
ADMIN_ID = 0  # ← ЗАМЕНИ НА СВОЙ ID

# ============================================================
# БАЗА
# ============================================================
import os as _os
DB_PATH = "/app/data/game.db" if _os.path.exists("/app/data") else "game.db"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 100,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            last_work INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            total_losses INTEGER DEFAULT 0,
            registered INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            biz_type TEXT,
            level INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            amount INTEGER,
            uses INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 100,
            created INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS used_promos (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    """)
    conn.commit()
    conn.close()


def get_player(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO players (user_id, registered) VALUES (?, ?)", (user_id, int(time.time())))
        conn.commit()
        c.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    conn.close()
    return {
        "user_id": row[0], "username": row[1], "first_name": row[2],
        "balance": row[3], "level": row[4], "xp": row[5],
        "last_bonus": row[6], "last_work": row[7],
        "total_wins": row[8], "total_losses": row[9], "registered": row[10],
    }


def update_player(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for key, val in kwargs.items():
        c.execute(f"UPDATE players SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()


def get_businesses(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, biz_type, level FROM businesses WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "type": r[1], "level": r[2]} for r in rows]


def add_business(user_id, biz_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO businesses (user_id, biz_type, level) VALUES (?, ?, 1)", (user_id, biz_type))
    conn.commit()
    conn.close()


def upgrade_business(biz_id, level):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE businesses SET level = ? WHERE id = ?", (level, biz_id))
    conn.commit()
    conn.close()


# ============================================================
# БИЗНЕСЫ
# ============================================================
BIZ = {
    "kiosk":      {"name": "Ларёк",         "emoji": "🏪", "price": 500,     "income": 5,      "mult": 2},
    "cafe":       {"name": "Кофейня",       "emoji": "☕", "price": 2500,    "income": 25,     "mult": 2},
    "shop":       {"name": "Магазин",       "emoji": "🛒", "price": 10000,   "income": 100,    "mult": 2},
    "restaurant": {"name": "Ресторан",      "emoji": "🍽️", "price": 50000,   "income": 500,    "mult": 2.5},
    "factory":    {"name": "Завод",         "emoji": "🏭", "price": 250000,  "income": 2500,   "mult": 2.5},
    "bank":       {"name": "Банк",          "emoji": "🏦", "price": 1000000, "income": 12000,  "mult": 3},
    "crypto":     {"name": "Крипто-биржа",  "emoji": "₿", "price": 5000000, "income": 70000,  "mult": 3},
    "oil":        {"name": "Нефтекомпания", "emoji": "🛢️", "price": 25000000, "income": 400000, "mult": 3.5},
}

# ============================================================
# КЕЙСЫ
# ============================================================
CASES = {
    "common": {"name": "Обычный кейс",   "emoji": "📦", "price": 500,   "chance": 0.7, "mult_low": 0.5, "mult_high": 2.0},
    "rare":   {"name": "Редкий кейс",    "emoji": "🎁", "price": 5000,  "chance": 0.5, "mult_low": 1.0, "mult_high": 4.0},
    "epic":   {"name": "Эпический кейс", "emoji": "💎", "price": 50000, "chance": 0.35, "mult_low": 1.5, "mult_high": 8.0},
}


def biz_price(biz_type, lvl):
    base = BIZ[biz_type]["price"]
    m = BIZ[biz_type]["mult"]
    if lvl <= 1:
        return base
    return int(base * (m ** (lvl - 1)))


def biz_income(biz_type, lvl):
    base = BIZ[biz_type]["income"]
    return int(base * (1.7 ** (lvl - 1)))


def total_income(user_id):
    bizs = get_businesses(user_id)
    return sum(biz_income(b["type"], b["level"]) for b in bizs)


def fmt(n):
    n = int(n)
    if n >= 1e12: return f"{n/1e12:.2f}T"
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.2f}M"
    if n >= 1e3: return f"{n/1e3:.1f}K"
    return f"{n:,}".replace(",", " ")


def fm(n):
    return "$" + fmt(n)


# ============================================================
# КОМАНДЫ
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_player(user.id)
    update_player(user.id, username=user.username or "", first_name=user.first_name or "")

    text = (
        f"🦍 Привет, {user.first_name}!\n\n"
        "🎮 Добро пожаловать в Gorilla Game!\n\n"
        "💼 Бизнесы — пассивный доход\n"
        "💰 /work — заработай раз в час\n"
        "📦 /case — открой кейс\n"
        "🎰 Казино и игры\n"
        "🏆 Топ игроков\n\n"
        "Команды:\n"
        "/profile /shop /my_biz\n"
        "/casino /bonus /work /case\n"
        "/top /promo /help\n\n"
        "Игры в чате:\n"
        "💣 Мины 100\n"
        "🎰 Рулетка 100 красное\n"
        "🎲 Кости 100\n"
        "🪙 Монетка 100 орёл\n"
        "🎯 Дартс 100"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("💼 Магазин", callback_data="shop")],
        [InlineKeyboardButton("💰 Работа", callback_data="work"),
         InlineKeyboardButton("📦 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino"),
         InlineKeyboardButton("🏆 Топ", callback_data="top")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="bonus")],
    ])

    await update.message.reply_text(text, reply_markup=keyboard)


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    p = get_player(user.id)
    bizs = get_businesses(user.id)
    inc = total_income(user.id)

    text = (
        f"👤 Профиль игрока\n\n"
        f"🆔 ID: {user.id}\n"
        f"📛 Имя: {user.first_name}\n"
        f"💰 Баланс: {fm(p['balance'])}\n"
        f"⭐ Уровень: {p['level']}\n"
        f"📊 XP: {p['xp']}\n\n"
        f"💼 Бизнесов: {len(bizs)}\n"
        f"📈 Доход: {fm(inc)}/час\n\n"
        f"🏆 Побед: {p['total_wins']}\n"
        f"💀 Проигрышей: {p['total_losses']}\n"
        f"📅 В игре с: {datetime.fromtimestamp(p['registered']).strftime('%d.%m.%Y')}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Мои бизнесы", callback_data="my_biz"),
         InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("💰 Работа", callback_data="work"),
         InlineKeyboardButton("📦 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="bonus"),
         InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    p = get_player(user.id)
    bizs = get_businesses(user.id)
    owned = {b["type"]: b for b in bizs}

    text = f"💼 Магазин бизнесов\n\n💰 Баланс: {fm(p['balance'])}\n\n"
    buttons = []
    for key, biz in BIZ.items():
        if key in owned:
            lvl = owned[key]["level"]
            price = biz_price(key, lvl + 1)
            inc = biz_income(key, lvl + 1)
            text += f"{biz['emoji']} {biz['name']} (ур. {lvl})\n"
            text += f"Апгрейд: {fm(price)} → {fm(inc)}/час\n\n"
            buttons.append([InlineKeyboardButton(
                f"⬆️ {biz['emoji']} {biz['name']} → ур.{lvl+1} ({fm(price)})",
                callback_data=f"upgrade:{key}"
            )])
        else:
            text += f"{biz['emoji']} {biz['name']}\n"
            text += f"{fm(biz['price'])} → {fm(biz['income'])}/час\n\n"
            buttons.append([InlineKeyboardButton(
                f"💰 {biz['emoji']} {biz['name']} ({fm(biz['price'])})",
                callback_data=f"buy:{key}"
            )])

    buttons.append([InlineKeyboardButton("📦 Кейсы", callback_data="cases")])
    buttons.append([InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")])
    keyboard = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def my_biz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    bizs = get_businesses(user.id)

    if not bizs:
        text = "💼 У тебя нет бизнесов.\n\nЗайди в /shop чтобы купить!"
    else:
        text = "💼 Твои бизнесы:\n\n"
        for b in bizs:
            biz = BIZ[b["type"]]
            inc = biz_income(b["type"], b["level"])
            text += f"{biz['emoji']} {biz['name']} — ур. {b['level']} ({fm(inc)}/час)\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")],
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def work_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    p = get_player(user.id)
    now = int(time.time())
    cooldown = 3600

    if now - p["last_work"] < cooldown:
        left = cooldown - (now - p["last_work"])
        m = left // 60
        text = f"⏳ Ты уже работал!\n\nСледующая работа через: {m} мин"
    else:
        earned = random.randint(100, 500) + p["level"] * 50
        update_player(user.id, balance=p["balance"] + earned, last_work=now)
        jobs = ["🚕 Таксистом", "🍕 Курьером", "💻 Программистом", "🎨 Дизайнером", "📦 Грузчиком",
                "🎤 Стримером", "📸 Фотографом", "🍔 Поваром", "🚚 Водителем", "🏗️ Строителем"]
        job = random.choice(jobs)
        text = f"💼 Ты подработал {job}!\n\n💰 Заработал: +{fm(earned)}\n💵 Баланс: {fm(p['balance'] + earned)}"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")]])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def cases_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    p = get_player(user.id)

    text = f"📦 Кейсы\n\n💰 Баланс: {fm(p['balance'])}\n\nВыбери кейс:"
    buttons = []
    for key, case in CASES.items():
        text += f"\n{case['emoji']} {case['name']} — {fm(case['price'])}"
        text += f"\n   Шанс ×{case['mult_high']:.1f}, вплоть до ×{case['mult_high']:.1f}"
        buttons.append([InlineKeyboardButton(
            f"{case['emoji']} {case['name']} ({fm(case['price'])})",
            callback_data=f"case:{key}"
        )])
    buttons.append([InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    p = get_player(user.id)
    now = int(time.time())
    cooldown = 86400

    if now - p["last_bonus"] < cooldown:
        left = cooldown - (now - p["last_bonus"])
        h = left // 3600
        m = (left % 3600) // 60
        text = f"⏳ Бонус получен!\n\nСледующий через: {h}ч {m}м"
    else:
        bonus = 500 * p["level"]
        update_player(user.id, balance=p["balance"] + bonus, last_bonus=now)
        text = f"🎁 Бонус: +{fm(bonus)}!\n\n💰 Баланс: {fm(p['balance'] + bonus)}"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")]])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def promo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip().upper()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("❌ Напиши: /promo КОД")
        return

    code = parts[1]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT amount, uses, max_uses FROM promos WHERE code = ?", (code,))
    promo = c.fetchone()

    if not promo:
        await update.message.reply_text("❌ Промокод не найден")
        conn.close()
        return

    amount, uses, max_uses = promo
    if uses >= max_uses:
        await update.message.reply_text("❌ Промокод больше не работает")
        conn.close()
        return

    c.execute("SELECT * FROM used_promos WHERE user_id = ? AND code = ?", (user.id, code))
    if c.fetchone():
        await update.message.reply_text("❌ Ты уже активировал этот промокод")
        conn.close()
        return

    p = get_player(user.id)
    update_player(user.id, balance=p["balance"] + amount)
    c.execute("UPDATE promos SET uses = uses + 1 WHERE code = ?", (code,))
    c.execute("INSERT INTO used_promos (user_id, code) VALUES (?, ?)", (user.id, code))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🎁 Промокод активирован!\n\n"
        f"💰 +{fm(amount)}\n"
        f"💵 Баланс: {fm(p['balance'] + amount)}"
    )


async def addpromo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    parts = update.message.text.split()
    if len(parts) < 3:
        await update.message.reply_text("Формат: /addpromo КОД СУММА [макс_использований]")
        return

    code = parts[1].upper()
    try:
        amount = int(parts[2])
        max_uses = int(parts[3]) if len(parts) > 3 else 100
    except:
        await update.message.reply_text("❌ Сумма должна быть числом")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO promos (code, amount, max_uses, created) VALUES (?, ?, ?, ?)",
                  (code, amount, max_uses, int(time.time())))
        conn.commit()
        await update.message.reply_text(f"✅ Промокод {code} создан на {fm(amount)} (макс: {max_uses})")
    except:
        await update.message.reply_text("❌ Такой промокод уже есть")
    conn.close()


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT first_name, balance FROM players ORDER BY balance DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    if not rows:
        text = "🏆 Пока никто не играет."
    else:
        text = "🏆 Топ-10 игроков:\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (name, bal) in enumerate(rows):
            m = medals[i] if i < 3 else f"{i+1}."
            text += f"{m} {name or 'Игрок'} — {fm(bal)}\n"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")]])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def casino_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.callback_query:
        user = update.callback_query.from_user
    p = get_player(user.id)

    text = (
        f"🎰 Казино\n\n"
        f"💰 Баланс: {fm(p['balance'])}\n\n"
        f"Выбери игру:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Кубик (×2)", callback_data="casino:dice"),
         InlineKeyboardButton("🪙 Монетка (×2)", callback_data="casino:coin")],
        [InlineKeyboardButton("🎰 Слоты (×10)", callback_data="casino:slots")],
        [InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")],
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user.id)
    await update.message.reply_text(f"💰 Твой баланс: {fm(p['balance'])}")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 Помощь\n\n"
        "💰 Заработок:\n"
        "/work — раз в час (100-500$)\n"
        "/bonus — раз в день (500$ × уровень)\n"
        "/case — открыть кейс\n"
        "/promo КОД — активировать промокод\n\n"
        "🎮 Игры:\n"
        "/casino — кубик, монетка, слоты\n"
        "💣 Мины 100\n"
        "🎰 Рулетка 100 красное\n"
        "🎲 Кости 100\n"
        "🪙 Монетка 100 орёл\n"
        "🎯 Дартс 100\n\n"
        "💼 Бизнесы:\n"
        "/shop /my_biz\n\n"
        "🏆 Топ:\n"
        "/top /profile /balance"
    )
    await update.message.reply_text(text)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM players")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM businesses")
    total_biz = c.fetchone()[0]
    c.execute("SELECT SUM(balance) FROM players")
    total_money = c.fetchone()[0] or 0
    c.execute("SELECT first_name, balance FROM players ORDER BY balance DESC LIMIT 5")
    top = c.fetchall()
    conn.close()

    text = (
        "📊 СТАТИСТИКА\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Игроков: {total_users}\n"
        f"💼 Бизнесов: {total_biz}\n"
        f"💰 Денег в игре: {fm(total_money)}\n\n"
        "🏆 Топ-5:\n"
    )
    for i, (name, bal) in enumerate(top):
        text += f"{i+1}. {name or 'Игрок'} — {fm(bal)}\n"

    await update.message.reply_text(text)


# ============================================================
# МИНЫ
# ============================================================
active_mines = {}
MULT = {1: 1.3, 2: 1.7, 3: 2.2, 4: 2.9, 5: 3.8, 6: 5.0, 7: 6.5, 8: 8.5, 9: 11.0,
        10: 15.0, 11: 20.0, 12: 27.0, 13: 36.0, 14: 50.0, 15: 70.0, 16: 100.0,
        17: 150.0, 18: 220.0, 19: 340.0, 20: 500.0, 21: 800.0, 22: 1200.0}


async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("❌ Напиши: Мины 100")
        return

    try:
        bet = int(parts[1])
    except:
        await update.message.reply_text("❌ Ставка должна быть числом")
        return

    if bet < 100:
        await update.message.reply_text("❌ Минимум 100$")
        return
    if bet > 10000:
        await update.message.reply_text("❌ Максимум 10 000$")
        return

    p = get_player(user.id)
    if p["balance"] < bet:
        await update.message.reply_text(f"❌ Не хватает. У тебя: {fm(p['balance'])}")
        return

    update_player(user.id, balance=p["balance"] - bet)

    cells = list(range(25))
    random.shuffle(cells)
    mine_positions = set(cells[:3])

    text_msg = (
        f"💣 МИНЫ\n\n"
        f"👤 {user.first_name}\n"
        f"💰 Ставка: {fm(bet)}\n"
        f"🎯 Мин: 3 из 25\n"
        f"✅ Открыто: 0\n\n"
        f"Открывай клетки и не попади на мину!\n"
        f"Забери после 1 открытой клетки."
    )

    keyboard = build_mines_keyboard(set(), mine_positions, False)
    msg = await update.message.reply_text(text_msg, reply_markup=keyboard)

    active_mines[msg.message_id] = {
        "user_id": user.id,
        "user_name": user.first_name,
        "bet": bet,
        "mines": mine_positions,
        "opened": set(),
        "finished": False,
        "message_id": msg.message_id,
        "chat_id": msg.chat_id,
    }


def build_mines_keyboard(opened, mines, finished):
    keyboard = []
    for row in range(5):
        btn_row = []
        for col in range(5):
            idx = row * 5 + col
            if finished:
                emoji = "💣" if idx in mines else ("💎" if idx in opened else "⬛")
            else:
                emoji = "💎" if idx in opened else "⬛"
            btn_row.append(InlineKeyboardButton(emoji, callback_data=f"mine:{idx}"))
        keyboard.append(btn_row)
    return InlineKeyboardMarkup(keyboard)


async def mines_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if not data.startswith("mine:"):
        return

    idx_str = data.split(":")[1]
    if idx_str == "cashout":
        await mines_cashout(update, context)
        return

    idx = int(idx_str)
    msg_id = query.message.message_id
    user = query.from_user

    game = active_mines.get(msg_id)
    if not game:
        await query.answer("Игра не найдена", show_alert=True)
        return

    if game["finished"]:
        await query.answer("Игра завершена", show_alert=True)
        return

    if game["user_id"] != user.id:
        await query.answer("Это не твоя игра!", show_alert=True)
        return

    if idx in game["opened"]:
        await query.answer("Уже открыто", show_alert=True)
        return

    if idx in game["mines"]:
        game["finished"] = True
        keyboard = build_mines_keyboard(game["opened"], game["mines"], True)
        await query.message.edit_text(
            f"💥 БУМ! Попал на мину!\n\n"
            f"👤 {game['user_name']}\n"
            f"💰 Ставка {fm(game['bet'])} сгорела\n"
            f"✅ Открыто: {len(game['opened'])}\n\n"
            f"Играй ещё: Мины 100",
            reply_markup=keyboard
        )
        p = get_player(user.id)
        update_player(user.id, total_losses=p["total_losses"] + 1)
        del active_mines[msg_id]
        return

    game["opened"].add(idx)
    opened_count = len(game["opened"])
    mult = MULT.get(opened_count, 1500.0)
    win_amount = int(game["bet"] * mult)
    next_mult = MULT.get(opened_count + 1, 1500.0)

    keyboard = build_mines_keyboard(game["opened"], game["mines"], False)
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(f"💰 ЗАБРАТЬ {fm(win_amount)}", callback_data="mine:cashout")
    ])

    await query.answer(f"💎 Открыто: {opened_count}")
    await query.message.edit_text(
        f"💣 МИНЫ\n\n"
        f"👤 {game['user_name']}\n"
        f"💰 Ставка: {fm(game['bet'])}\n"
        f"✅ Открыто: {opened_count}\n"
        f"💎 Следующая: ×{next_mult:.1f}\n"
        f"🏆 Заберёшь: {fm(win_amount)}",
        reply_markup=keyboard
    )


async def mines_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    msg_id = query.message.message_id
    user = query.from_user

    game = active_mines.get(msg_id)
    if not game:
        await query.answer("Игра не найдена", show_alert=True)
        return

    if game["user_id"] != user.id:
        await query.answer("Это не твоя игра!", show_alert=True)
        return

    if game["finished"]:
        await query.answer("Игра завершена", show_alert=True)
        return

    opened = len(game["opened"])
    if opened == 0:
        await query.answer("Открой хотя бы одну клетку!", show_alert=True)
        return

    mult = MULT.get(opened, 1.0)
    win_amount = int(game["bet"] * mult)
    game["finished"] = True

    p = get_player(user.id)
    update_player(user.id, balance=p["balance"] + win_amount, total_wins=p["total_wins"] + 1)

    keyboard = build_mines_keyboard(game["opened"], game["mines"], True)
    await query.message.edit_text(
        f"💰 ЗАБРАЛ!\n\n"
        f"👤 {game['user_name']}\n"
        f"✅ Открыто: {opened}\n"
        f"🏆 Выигрыш: +{fm(win_amount)} (×{mult:.1f})\n"
        f"💰 Баланс: {fm(p['balance'] + win_amount)}\n\n"
        f"Играй ещё: Мины 100",
        reply_markup=keyboard
    )
    del active_mines[msg_id]


# ============================================================
# РУЛЕТКА
# ============================================================
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

active_roulette = {}


async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text.strip().lower()
    parts = text.split()

    if len(parts) < 3:
        await update.message.reply_text(
            "🎰 Формат: Рулетка 100 красное\n"
            "Варианты: красное / чёрное / зеро"
        )
        return

    try:
        bet = int(parts[1])
    except:
        await update.message.reply_text("❌ Ставка должна быть числом")
        return

    if bet < 100:
        await update.message.reply_text("❌ Минимум 100$")
        return
    if bet > 10000:
        await update.message.reply_text("❌ Максимум 10 000$")
        return

    choice = parts[2].lower()
    if choice in ("красное", "красный", "красн", "red", "к"):
        color = "red"
        color_name = "🔴 Красное"
    elif choice in ("чёрное", "черное", "чёрный", "черный", "чёрн", "черн", "black", "ч"):
        color = "black"
        color_name = "⚫ Чёрное"
    elif choice in ("зеро", "zero", "0", "з"):
        color = "zero"
        color_name = "🟢 Зеро"
    else:
        await update.message.reply_text("❌ Ставь на: красное / чёрное / зеро")
        return

    p = get_player(user.id)
    if p["balance"] < bet:
        await update.message.reply_text(f"❌ Не хватает. У тебя: {fm(p['balance'])}")
        return

    update_player(user.id, balance=p["balance"] - bet)

    chat_id = chat.id

    if chat_id in active_roulette and not active_roulette[chat_id]["finished"]:
        active_roulette[chat_id]["bets"].append({
            "user_id": user.id,
            "user_name": user.first_name,
            "bet": bet,
            "color": color,
            "color_name": color_name,
        })
        bets_count = len(active_roulette[chat_id]["bets"])
        await update.message.reply_text(
            f"✅ Ставка: {color_name} — {fm(bet)}\n"
            f"👥 Всего ставок: {bets_count}\n"
            f"⏳ Приём открыт..."
        )
        return

    active_roulette[chat_id] = {
        "bets": [{
            "user_id": user.id,
            "user_name": user.first_name,
            "bet": bet,
            "color": color,
            "color_name": color_name,
        }],
        "finished": False,
        "started": time.time(),
    }

    await update.message.reply_text(
        f"🎰 РУЛЕТКА ЗАПУЩЕНА!\n\n"
        f"👤 {user.first_name} — {color_name} {fm(bet)}\n\n"
        f"⏳ Приём ставок: 30 секунд\n"
        f"💡 Пиши: Рулетка 100 красное\n"
        f"Или: Рулетка 500 чёрное\n"
        f"Или: Рулетка 50 зеро"
    )

    asyncio.create_task(run_roulette(chat_id, context.bot))


async def run_roulette(chat_id, bot):
    await asyncio.sleep(30)

    game = active_roulette.get(chat_id)
    if not game or game["finished"]:
        return

    game["finished"] = True

    number = random.randint(0, 36)

    if number == 0:
        result_color = "zero"
        result_name = "🟢 ЗЕРО"
        result_emoji = "🟢"
    elif number in RED_NUMBERS:
        result_color = "red"
        result_name = "🔴 КРАСНОЕ"
        result_emoji = "🔴"
    else:
        result_color = "black"
        result_name = "⚫ ЧЁРНОЕ"
        result_emoji = "⚫"

    lines = [f"🎰 РУЛЕТКА\n\n{result_emoji} Выпало: {result_name} ({number})\n"]
    lines.append("━━━━━━━━━━━━━━━━━\n")

    total_won = 0
    total_lost = 0

    for bet in game["bets"]:
        user_id = bet["user_id"]
        p = get_player(user_id)

        if bet["color"] == result_color:
            mult = 35 if result_color == "zero" else 2
            win = bet["bet"] * mult
            update_player(user_id, balance=p["balance"] + win, total_wins=p["total_wins"] + 1)
            lines.append(f"🎉 {bet['user_name']} — {bet['color_name']} — +{fm(win)}")
            total_won += 1
        else:
            update_player(user_id, total_losses=p["total_losses"] + 1)
            lines.append(f"💀 {bet['user_name']} — {bet['color_name']} — -{fm(bet['bet'])}")
            total_lost += 1

    lines.append(f"\n🏆 Побед: {total_won} | 💀 Проигрышей: {total_lost}")
    lines.append("\n🎰 Новая игра: Рулетка 100 красное")

    try:
        await bot.send_message(chat_id=chat_id, text="\n".join(lines))
    except Exception as e:
        logging.error(f"Ошибка рулетки: {e}")

    del active_roulette[chat_id]


# ============================================================
# КОСТИ
# ============================================================
async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip().lower()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("❌ Формат: Кости 100")
        return

    try:
        bet = int(parts[1])
    except:
        await update.message.reply_text("❌ Ставка должна быть числом")
        return

    if bet < 100 or bet > 10000:
        await update.message.reply_text("❌ Ставка от 100 до 10 000$")
        return

    p = get_player(user.id)
    if p["balance"] < bet:
        await update.message.reply_text(f"❌ Не хватает. У тебя: {fm(p['balance'])}")
        return

    update_player(user.id, balance=p["balance"] - bet)

    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2

    if d1 == d2:
        mult = 5
        result = f"🎉 ДУБЛЬ! ×5"
    elif total > 7:
        mult = 2
        result = f"🎉 Больше 7! ×2"
    elif total == 7:
        mult = 3
        result = f"🎉 РОВНО 7! ×3"
    else:
        mult = 0
        result = f"💀 Меньше 7 — проигрыш"

    if mult > 0:
        win = bet * mult
        new_bal = p["balance"] + win
        update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
        res_text = f"{result}\n\n💰 +{fm(win)}\n💵 Баланс: {fm(new_bal)}"
    else:
        new_bal = p["balance"] - bet
        update_player(user.id, total_losses=p["total_losses"] + 1)
        res_text = f"{result}\n\n💵 Баланс: {fm(new_bal)}"

    await update.message.reply_text(
        f"🎲 КОСТИ\n\n"
        f"👤 {user.first_name} | 💰 Ставка: {fm(bet)}\n\n"
        f"Кубик 1: {d1}\n"
        f"Кубик 2: {d2}\n"
        f"Сумма: {total}\n\n"
        f"{res_text}\n\n"
        f"Играй ещё: Кости 100"
    )


# ============================================================
# МОНЕТКА
# ============================================================
async def coin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip().lower()
    parts = text.split()

    if len(parts) < 3:
        await update.message.reply_text("❌ Формат: Монетка 100 орёл")
        return

    try:
        bet = int(parts[1])
    except:
        await update.message.reply_text("❌ Ставка должна быть числом")
        return

    if bet < 100 or bet > 10000:
        await update.message.reply_text("❌ Ставка от 100 до 10 000$")
        return

    choice = parts[2].lower()
    if choice in ("орёл", "орел", "o", "heads"):
        pick = "орёл"
    elif choice in ("решка", "р", "tails"):
        pick = "решка"
    else:
        await update.message.reply_text("❌ Ставь на: орёл или решка")
        return

    p = get_player(user.id)
    if p["balance"] < bet:
        await update.message.reply_text(f"❌ Не хватает. У тебя: {fm(p['balance'])}")
        return

    update_player(user.id, balance=p["balance"] - bet)

    result = random.choice(["орёл", "решка"])

    if result == pick:
        win = bet * 2
        new_bal = p["balance"] + win
        update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
        res_text = f"🎉 ПОБЕДА! +{fm(win)}\n💵 Баланс: {fm(new_bal)}"
    else:
        new_bal = p["balance"] - bet
        update_player(user.id, total_losses=p["total_losses"] + 1)
        res_text = f"💀 Проигрыш -{fm(bet)}\n💵 Баланс: {fm(new_bal)}"

    await update.message.reply_text(
        f"🪙 МОНЕТКА\n\n"
        f"👤 {user.first_name} | 💰 Ставка: {fm(bet)}\n"
        f"🎯 Твой выбор: {pick}\n"
        f"🎲 Выпало: {result}\n\n"
        f"{res_text}\n\n"
        f"Играй ещё: Монетка 100 орёл"
    )


# ============================================================
# ДАРТС
# ============================================================
async def darts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip().lower()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text("❌ Формат: Дартс 100")
        return

    try:
        bet = int(parts[1])
    except:
        await update.message.reply_text("❌ Ставка должна быть числом")
        return

    if bet < 100 or bet > 10000:
        await update.message.reply_text("❌ Ставка от 100 до 10 000$")
        return

    p = get_player(user.id)
    if p["balance"] < bet:
        await update.message.reply_text(f"❌ Не хватает. У тебя: {fm(p['balance'])}")
        return

    update_player(user.id, balance=p["balance"] - bet)

    roll = random.random()
    if roll < 0.05:
        mult, zone = 10, "🎯 В ЯБЛОЧКО!"
    elif roll < 0.20:
        mult, zone = 3, "🎯 В центр!"
    elif roll < 0.50:
        mult, zone = 1.5, "🎯 Рядом с центром"
    else:
        mult, zone = 0, "💀 Мимо!"

    if mult > 0:
        win = int(bet * mult)
        new_bal = p["balance"] + win
        update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
        res_text = f"{zone}\n\n🎉 +{fm(win)} (×{mult})\n💵 Баланс: {fm(new_bal)}"
    else:
        new_bal = p["balance"] - bet
        update_player(user.id, total_losses=p["total_losses"] + 1)
        res_text = f"{zone}\n\n💀 -{fm(bet)}\n💵 Баланс: {fm(new_bal)}"

    await update.message.reply_text(
        f"🎯 ДАРТС\n\n"
        f"👤 {user.first_name} | 💰 Ставка: {fm(bet)}\n\n"
        f"{res_text}\n\n"
        f"Играй ещё: Дартс 100"
    )


# ============================================================
# КНОПКИ
# ============================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "profile":
        await profile_cmd(update, context)
    elif data == "shop":
        await shop_cmd(update, context)
    elif data == "my_biz":
        await my_biz_cmd(update, context)
    elif data == "casino":
        await casino_cmd(update, context)
    elif data == "top":
        await top_cmd(update, context)
    elif data == "bonus":
        await bonus_cmd(update, context)
    elif data == "work":
        await work_cmd(update, context)
    elif data == "cases":
        await cases_cmd(update, context)
    elif data == "back_profile":
        await profile_cmd(update, context)
    elif data.startswith("case:"):
        case_key = data.split(":")[1]
        case = CASES[case_key]
        user = query.from_user
        p = get_player(user.id)
        if p["balance"] < case["price"]:
            await query.answer("Недостаточно денег!", show_alert=True)
            return
        update_player(user.id, balance=p["balance"] - case["price"])
        if random.random() < case["chance"]:
            mult = round(random.uniform(case["mult_low"], case["mult_high"]), 2)
            win = int(case["price"] * mult)
            new_bal = p["balance"] - case["price"] + win
            update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
            result = f"🎉 ВЫИГРЫШ ×{mult}!\n+{fm(win)}"
        else:
            new_bal = p["balance"] - case["price"]
            update_player(user.id, total_losses=p["total_losses"] + 1)
            result = f"💀 Пусто... Кейс не сработал"
        await query.edit_message_text(
            f"{case['emoji']} {case['name']}\n\n{result}\n\n💵 Баланс: {fm(new_bal)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Ещё кейс", callback_data="cases")],
                [InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")]
            ])
        )
    elif data.startswith("buy:"):
        biz_type = data.split(":")[1]
        user = query.from_user
        p = get_player(user.id)
        bizs = get_businesses(user.id)
        if any(b["type"] == biz_type for b in bizs):
            await query.answer("Уже куплено!", show_alert=True)
            return
        price = BIZ[biz_type]["price"]
        if p["balance"] < price:
            await query.answer("Недостаточно денег!", show_alert=True)
            return
        update_player(user.id, balance=p["balance"] - price)
        add_business(user.id, biz_type)
        await query.answer(f"✅ {BIZ[biz_type]['name']} куплено!", show_alert=True)
        await shop_cmd(update, context)
    elif data.startswith("upgrade:"):
        biz_type = data.split(":")[1]
        user = query.from_user
        p = get_player(user.id)
        bizs = get_businesses(user.id)
        my_biz = next((b for b in bizs if b["type"] == biz_type), None)
        if not my_biz:
            await query.answer("Сначала купи!", show_alert=True)
            return
        price = biz_price(biz_type, my_biz["level"] + 1)
        if p["balance"] < price:
            await query.answer("Недостаточно денег!", show_alert=True)
            return
        update_player(user.id, balance=p["balance"] - price)
        upgrade_business(my_biz["id"], my_biz["level"] + 1)
        await query.answer(f"✅ Ур. {my_biz['level']+1}!", show_alert=True)
        await shop_cmd(update, context)
    elif data.startswith("casino:"):
        game = data.split(":")[1]
        user = query.from_user
        p = get_player(user.id)
        bet = min(1000, p["balance"])
        if p["balance"] < 100:
            await query.answer("Минимум 100$!", show_alert=True)
            return

        if game == "dice":
            win = random.random() < 0.45
            if win:
                new_bal = p["balance"] + bet
                update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
                result = f"🎉 Победа! +{fm(bet)}\n💰 {fm(new_bal)}"
            else:
                new_bal = p["balance"] - bet
                update_player(user.id, balance=new_bal, total_losses=p["total_losses"] + 1)
                result = f"💀 Проигрыш! -{fm(bet)}\n💰 {fm(new_bal)}"
            await query.edit_message_text(
                f"🎲 Кубик: {random.randint(1,6)} vs {random.randint(1,6)}\n\n{result}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎰 Ещё", callback_data="casino"),
                    InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")
                ]])
            )
        elif game == "coin":
            win = random.random() < 0.45
            side = "Орёл" if random.random() < 0.5 else "Решка"
            if win:
                new_bal = p["balance"] + bet
                update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
                result = f"🎉 Победа! +{fm(bet)}\n💰 {fm(new_bal)}"
            else:
                new_bal = p["balance"] - bet
                update_player(user.id, balance=new_bal, total_losses=p["total_losses"] + 1)
                result = f"💀 Проигрыш! -{fm(bet)}\n💰 {fm(new_bal)}"
            await query.edit_message_text(
                f"🪙 Монетка: {side}\n\n{result}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎰 Ещё", callback_data="casino"),
                    InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")
                ]])
            )
        elif game == "slots":
            roll = random.random()
            if roll < 0.03:
                mult, result = 10, "🎰🎰🎰 JACKPOT!"
            elif roll < 0.10:
                mult, result = 3, "🍋🍋🍋 Три в ряд!"
            elif roll < 0.25:
                mult, result = 2, "🍒🍒⭐ Два в ряд!"
            else:
                mult, result = 0, "🍋🍒⭐ Мимо..."
            if mult > 0:
                win_amt = bet * mult
                new_bal = p["balance"] + win_amt
                update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
                res = f"🎉 +{fm(win_amt)} (×{mult})\n💰 {fm(new_bal)}"
            else:
                new_bal = p["balance"] - bet
                update_player(user.id, balance=new_bal, total_losses=p["total_losses"] + 1)
                res = f"💀 -{fm(bet)}\n💰 {fm(new_bal)}"
            await query.edit_message_text(
                f"🎰 Слоты\n\n{result}\n\n{res}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎰 Ещё", callback_data="casino"),
                    InlineKeyboardButton("◀️ Профиль", callback_data="back_profile")
                ]])
            )


# ============================================================
# ЗАПУСК
# ============================================================
def main():
    if not BOT_TOKEN:
        print("❌ Нет токена!")
        return
    init_db()
    print("🚀 Gorilla Game запущена...")
    print(f"📊 Админ ID: {ADMIN_ID}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("my_biz", my_biz_cmd))
    app.add_handler(CommandHandler("casino", casino_cmd))
    app.add_handler(CommandHandler("bonus", bonus_cmd))
    app.add_handler(CommandHandler("work", work_cmd))
    app.add_handler(CommandHandler("case", cases_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("promo", promo_cmd))
    app.add_handler(CommandHandler("addpromo", addpromo_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))

    # Игры в чате
    app.add_handler(MessageHandler(
        filters.Regex(r'(?i)^мины?\s+\d+') | filters.Regex(r'(?i)^mines?\s+\d+'),
        mines_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r'(?i)^рулетка\s+\d+\s+\w+') | filters.Regex(r'(?i)^roulette\s+\d+\s+\w+'),
        roulette_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r'(?i)^кости\s+\d+') | filters.Regex(r'(?i)^dice\s+\d+'),
        dice_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r'(?i)^монетка\s+\d+\s+\w+') | filters.Regex(r'(?i)^coin\s+\d+\s+\w+'),
        coin_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r'(?i)^дартс\s+\d+') | filters.Regex(r'(?i)^darts\s+\d+'),
        darts_cmd
    ))

    # Кнопки мин
    app.add_handler(CallbackQueryHandler(mines_cashout, pattern="^mine:cashout$"))
    app.add_handler(CallbackQueryHandler(mines_button, pattern=r'^mine:\d+$'))

    # Общий обработчик кнопок
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Готов!")
    app.run_polling()


if __name__ == "__main__":
    main()
