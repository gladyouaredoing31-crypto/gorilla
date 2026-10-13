import logging
import os
import sqlite3
import random
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8946069952:AAEaDHomD3A6xlXUwfqcextImf2I4rpa-vs")

# ============================================================
# ТВОЙ ID (узнать: @userinfobot)
# ============================================================
ADMIN_ID = 1673532605  # ← ЗАМЕНИ НА СВОЙ ID

DB_PATH = "game.db"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


# ============================================================
# БАЗА
# ============================================================
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
        "last_bonus": row[6], "total_wins": row[7], "total_losses": row[8], "registered": row[9],
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


# ============================================================
# ФОРМАТ
# ============================================================
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
        "💼 Покупай бизнесы — капает доход\n"
        "🎰 Играй в казино — умножай деньги\n"
        "🎁 Получай бонус каждый день\n"
        "🏆 Поднимайся в топе игроков\n\n"
        "Команды:\n"
        "/profile — профиль\n"
        "/shop — магазин бизнесов\n"
        "/my_biz — мои бизнесы\n"
        "/casino — казино\n"
        "/bonus — ежедневный бонус\n"
        "/top — топ игроков\n"
        "/help — помощь"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("💼 Магазин", callback_data="shop")],
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


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 Помощь\n\n"
        "/start — главное меню\n"
        "/profile — профиль\n"
        "/shop — магазин\n"
        "/my_biz — мои бизнесы\n"
        "/casino — казино\n"
        "/bonus — ежедневный бонус\n"
        "/top — топ игроков\n\n"
        "Как играть:\n"
        "1. Получи бонус (/bonus) — 500$\n"
        "2. Купи бизнес в /shop\n"
        "3. Бизнесы приносят доход\n"
        "4. Играй в казино\n"
        "5. Поднимайся в топе!"
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
    elif data == "back_profile":
        await profile_cmd(update, context)
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("my_biz", my_biz_cmd))
    app.add_handler(CommandHandler("casino", casino_cmd))
    app.add_handler(CommandHandler("bonus", bonus_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Готов!")
    app.run_polling()


if __name__ == "__main__":
    main()
