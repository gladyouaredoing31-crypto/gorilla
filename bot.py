import logging
import os
import sqlite3
import random
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8946069952:AAGIuQF02nm9ur3mCSu27py4NSdFt_LTQKU")
DB_PATH = "game.db"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


# ============================================================
# БАЗА ДАННЫХ
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
            last_income INTEGER DEFAULT 0,
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
            level INTEGER DEFAULT 1,
            last_collect INTEGER DEFAULT 0
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
        c.execute(
            "INSERT INTO players (user_id, registered) VALUES (?, ?)",
            (user_id, int(time.time()))
        )
        conn.commit()
        c.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    conn.close()
    return {
        "user_id": row[0], "username": row[1], "first_name": row[2],
        "balance": row[3], "level": row[4], "xp": row[5],
        "last_bonus": row[6], "last_income": row[7],
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
    c.execute("SELECT id, biz_type, level, last_collect FROM businesses WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "type": r[1], "level": r[2], "last_collect": r[3]} for r in rows]


def add_business(user_id, biz_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO businesses (user_id, biz_type, level, last_collect) VALUES (?, ?, 1, ?)",
        (user_id, biz_type, int(time.time()))
    )
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
BUSINESS_TYPES = {
    "kiosk":      {"name": "Ларёк",         "emoji": "🏪", "price": 500,   "income": 10,  "levelup": 2},
    "cafe":       {"name": "Кофейня",       "emoji": "☕", "price": 2500,  "income": 50,  "levelup": 2},
    "shop":       {"name": "Магазин",       "emoji": "🛒", "price": 10000, "income": 200, "levelup": 2},
    "restaurant": {"name": "Ресторан",      "emoji": "🍽️", "price": 50000, "income": 1000, "levelup": 3},
    "factory":    {"name": "Завод",         "emoji": "🏭", "price": 250000, "income": 5000, "levelup": 3},
    "bank":       {"name": "Банк",          "emoji": "🏦", "price": 1000000, "income": 25000, "levelup": 4},
    "crypto":     {"name": "Крипто-биржа",  "emoji": "₿", "price": 5000000, "income": 100000, "levelup": 5},
    "oil":        {"name": "Нефтекомпания", "emoji": "🛢️", "price": 25000000, "income": 500000, "levelup": 5},
}


def get_business_price(biz_type, current_level):
    base = BUSINESS_TYPES[biz_type]["price"]
    mult = BUSINESS_TYPES[biz_type]["levelup"]
    if current_level <= 1:
        return base
    return int(base * (mult ** (current_level - 1)))


def get_business_income(biz_type, level):
    base = BUSINESS_TYPES[biz_type]["income"]
    return int(base * (1.5 ** (level - 1)))


# ============================================================
# ФОРМАТИРОВАНИЕ
# ============================================================
def fmt_num(n):
    if n >= 1e12: return f"{n/1e12:.2f}T"
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.2f}M"
    if n >= 1e3: return f"{n/1e3:.1f}K"
    return str(int(n))


def fmt_money(n):
    return f"${fmt_num(n)}"


# ============================================================
# ДОХОД
# ============================================================
def collect_income(user_id):
    """Собирает доход со всех бизнесов"""
    bizs = get_businesses(user_id)
    now = int(time.time())
    total = 0
    for b in bizs:
        # Доход капает каждые 60 секунд
        if now - b["last_collect"] >= 60:
            ticks = (now - b["last_collect"]) // 60
            income = get_business_income(b["type"], b["level"]) * ticks
            total += income
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE businesses SET last_collect = ? WHERE id = ?", (now, b["id"]))
            conn.commit()
            conn.close()
    if total > 0:
        p = get_player(user_id)
        update_player(user_id, balance=p["balance"] + total)
    return total


# ============================================================
# КОМАНДЫ
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user.id)
    # Сохраняем имя
    update_player(user.id, username=user.username or "", first_name=user.first_name or "")

    text = (
        f"🦍 Привет, {user.first_name}!\n\n"
        "🎮 Добро пожаловать в Gorilla Game!\n\n"
        "💼 Покупай бизнесы — они капают доход каждую минуту\n"
        "🎰 Играй в казино и умножай деньги\n"
        "🏆 Поднимайся в топе игроков\n\n"
        "**Команды:**\n"
        "/profile — твой профиль\n"
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

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Сначала соберём доход
    collected = collect_income(user.id)
    p = get_player(user.id)
    bizs = get_businesses(user.id)

    # Общий доход в минуту
    income_per_min = sum(get_business_income(b["type"], b["level"]) for b in bizs)

    text = (
        f"👤 **Профиль игрока**\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"📛 Имя: {user.first_name}\n"
        f"💰 Баланс: **{fmt_money(p['balance'])}**\n"
        f"⭐ Уровень: **{p['level']}**\n"
        f"📊 XP: {p['xp']}\n\n"
        f"💼 Бизнесов: **{len(bizs)}**\n"
        f"📈 Доход: **{fmt_money(income_per_min)}/мин**\n\n"
        f"🏆 Побед: {p['total_wins']}\n"
        f"💀 Проигрышей: {p['total_losses']}\n"
        f"📅 В игре с: {datetime.fromtimestamp(p['registered']).strftime('%d.%m.%Y')}"
    )

    if collected > 0:
        text += f"\n\n💵 Собрано дохода: **+{fmt_money(collected)}**"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Мои бизнесы", callback_data="my_biz"),
         InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="bonus"),
         InlineKeyboardButton("🏆 Топ", callback_data="top")],
    ])

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user.id)
    bizs = get_businesses(user.id)
    owned_types = {}
    for b in bizs:
        owned_types[b["type"]] = b

    text = f"💼 **Магазин бизнесов**\n\n💰 Твой баланс: **{fmt_money(p['balance'])}**\n\n"
    buttons = []
    for key, biz in BUSINESS_TYPES.items():
        if key in owned_types:
            lvl = owned_types[key]["level"]
            price = get_business_price(key, lvl + 1)
            income = get_business_income(key, lvl + 1)
            text += f"{biz['emoji']} **{biz['name']}** (Ур. {lvl})\n"
            text += f"   Апгрейд: {fmt_money(price)} → {fmt_money(income)}/мин\n\n"
            buttons.append([InlineKeyboardButton(
                f"⬆️ {biz['emoji']} {biz['name']} → ур.{lvl+1} ({fmt_money(price)})",
                callback_data=f"upgrade:{key}"
            )])
        else:
            price = biz["price"]
            income = biz["income"]
            text += f"{biz['emoji']} **{biz['name']}**\n"
            text += f"   Цена: {fmt_money(price)} → доход {fmt_money(income)}/мин\n\n"
            buttons.append([InlineKeyboardButton(
                f"💰 Купить {biz['emoji']} {biz['name']} ({fmt_money(price)})",
                callback_data=f"buy:{key}"
            )])

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")])
    keyboard = InlineKeyboardMarkup(buttons)

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def my_biz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    collect_income(user.id)
    bizs = get_businesses(user.id)

    if not bizs:
        text = "💼 У тебя пока нет бизнесов.\n\nЗайди в /shop чтобы купить первый!"
    else:
        text = "💼 **Твои бизнесы:**\n\n"
        for b in bizs:
            biz = BUSINESS_TYPES[b["type"]]
            income = get_business_income(b["type"], b["level"])
            text += f"{biz['emoji']} {biz['name']} — Ур. {b['level']} ({fmt_money(income)}/мин)\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")],
    ])

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def casino_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user.id)
    text = (
        f"🎰 **Казино**\n\n"
        f"💰 Твой баланс: **{fmt_money(p['balance'])}**\n\n"
        f"Выбери игру:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Кубик (×2)", callback_data="casino:dice"),
         InlineKeyboardButton("🪙 Монетка (×2)", callback_data="casino:coin")],
        [InlineKeyboardButton("🎰 Слоты (×10)", callback_data="casino:slots")],
        [InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")],
    ])
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    p = get_player(user.id)
    now = int(time.time())
    cooldown = 86400  # 24 часа

    if now - p["last_bonus"] < cooldown:
        left = cooldown - (now - p["last_bonus"])
        hours = left // 3600
        mins = (left % 3600) // 60
        await update.message.reply_text(
            f"⏳ Бонус уже получен!\n\nСледующий через: **{hours}ч {mins}м**",
            parse_mode="Markdown"
        )
        return

    # Бонус зависит от уровня
    bonus = 500 * p["level"]
    update_player(user.id, balance=p["balance"] + bonus, last_bonus=now)
    await update.message.reply_text(
        f"🎁 Ты получил бонус: **+{fmt_money(bonus)}**!\n\n"
        f"💰 Новый баланс: {fmt_money(p['balance'] + bonus)}\n\n"
        f"Возвращайся завтра за новым бонусом!",
        parse_mode="Markdown"
    )


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT first_name, balance FROM players ORDER BY balance DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    if not rows:
        text = "🏆 Пока никто не играет."
    else:
        text = "🏆 **Топ-10 игроков:**\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (name, bal) in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} {name or 'Игрок'} — {fmt_money(bal)}\n"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 **Помощь**\n\n"
        "**Команды:**\n"
        "/start — главное меню\n"
        "/profile — профиль\n"
        "/shop — магазин бизнесов\n"
        "/my_biz — мои бизнесы\n"
        "/casino — казино\n"
        "/bonus — ежедневный бонус\n"
        "/top — топ игроков\n\n"
        "**Как играть:**\n"
        "1. Получи бонус (/bonus) — 500$\n"
        "2. Купи бизнес в /shop\n"
        "3. Бизнесы приносят доход каждую минуту\n"
        "4. Апгрейди бизнесы — они приносят больше\n"
        "5. Играй в казино — умножай баланс\n"
        "6. Поднимайся в топе!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


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
        user = query.from_user
        p = get_player(user.id)
        now = int(time.time())
        cooldown = 86400
        if now - p["last_bonus"] < cooldown:
            left = cooldown - (now - p["last_bonus"])
            hours = left // 3600
            mins = (left % 3600) // 60
            await query.edit_message_text(
                f"⏳ Бонус уже получен!\n\nСледующий через: **{hours}ч {mins}м**",
                parse_mode="Markdown"
            )
            return
        bonus = 500 * p["level"]
        update_player(user.id, balance=p["balance"] + bonus, last_bonus=now)
        await query.edit_message_text(
            f"🎁 Ты получил бонус: **+{fmt_money(bonus)}**!\n\n"
            f"💰 Новый баланс: {fmt_money(p['balance'] + bonus)}",
            parse_mode="Markdown"
        )
    elif data == "back_to_profile":
        await profile_cmd(update, context)
    elif data.startswith("buy:"):
        biz_type = data.split(":")[1]
        user = query.from_user
        p = get_player(user.id)
        bizs = get_businesses(user.id)
        if any(b["type"] == biz_type for b in bizs):
            await query.answer("Уже куплено!", show_alert=True)
            return
        price = BUSINESS_TYPES[biz_type]["price"]
        if p["balance"] < price:
            await query.answer("Недостаточно денег!", show_alert=True)
            return
        update_player(user.id, balance=p["balance"] - price)
        add_business(user.id, biz_type)
        biz = BUSINESS_TYPES[biz_type]
        await query.answer(f"✅ Куплено: {biz['name']}!", show_alert=True)
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
        price = get_business_price(biz_type, my_biz["level"] + 1)
        if p["balance"] < price:
            await query.answer("Недостаточно денег!", show_alert=True)
            return
        update_player(user.id, balance=p["balance"] - price)
        upgrade_business(my_biz["id"], my_biz["level"] + 1)
        await query.answer(f"✅ Апгрейд до ур.{my_biz['level']+1}!", show_alert=True)
        await shop_cmd(update, context)
    elif data.startswith("casino:"):
        game = data.split(":")[1]
        user = query.from_user
        p = get_player(user.id)
        # Минимальная ставка — 100$
        bet = min(1000, p["balance"])
        if p["balance"] < 100:
            await query.answer("Минимум 100$!", show_alert=True)
            return

        if game == "dice":
            win = random.random() < 0.45  # 45% шанс победы
            if win:
                new_bal = p["balance"] + bet
                update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
                await query.edit_message_text(
                    f"🎲 Кубик: **{random.randint(1,6)}** vs **{random.randint(1,6)}**\n\n"
                    f"🎉 Победа! **+{fmt_money(bet)}**\n💰 Баланс: {fmt_money(new_bal)}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Ещё", callback_data="casino"), InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
                )
            else:
                new_bal = p["balance"] - bet
                update_player(user.id, balance=new_bal, total_losses=p["total_losses"] + 1)
                await query.edit_message_text(
                    f"🎲 Кубик: **{random.randint(1,6)}** vs **{random.randint(1,6)}**\n\n"
                    f"💀 Проигрыш! **-{fmt_money(bet)}**\n💰 Баланс: {fmt_money(new_bal)}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Ещё", callback_data="casino"), InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
                )
        elif game == "coin":
            win = random.random() < 0.45
            side = "Орёл" if random.random() < 0.5 else "Решка"
            if win:
                new_bal = p["balance"] + bet
                update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
                await query.edit_message_text(
                    f"🪙 Монетка: **{side}**\n\n🎉 Победа! **+{fmt_money(bet)}**\n💰 Баланс: {fmt_money(new_bal)}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Ещё", callback_data="casino"), InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
                )
            else:
                new_bal = p["balance"] - bet
                update_player(user.id, balance=new_bal, total_losses=p["total_losses"] + 1)
                await query.edit_message_text(
                    f"🪙 Монетка: **{side}**\n\n💀 Проигрыш! **-{fmt_money(bet)}**\n💰 Баланс: {fmt_money(new_bal)}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Ещё", callback_data="casino"), InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
                )
        elif game == "slots":
            roll = random.random()
            if roll < 0.03:
                mult = 10
                result = "🎰🎰🎰 JACKPOT!"
            elif roll < 0.10:
                mult = 3
                result = "🍋🍋🍋 Три в ряд!"
            elif roll < 0.25:
                mult = 2
                result = "🍒🍒⭐ Два в ряд!"
            else:
                mult = 0
                result = f"{random.choice(['🍋','🍒','⭐','🍊'])} {random.choice(['🍋','🍒','⭐','🍊'])} {random.choice(['🍋','🍒','⭐','🍊'])} Мимо..."

            if mult > 0:
                win_amt = bet * mult
                new_bal = p["balance"] + win_amt
                update_player(user.id, balance=new_bal, total_wins=p["total_wins"] + 1)
                await query.edit_message_text(
                    f"🎰 Слоты\n\n{result}\n\n🎉 Победа! **+{fmt_money(win_amt)}** (×{mult})\n💰 Баланс: {fmt_money(new_bal)}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Ещё", callback_data="casino"), InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
                )
            else:
                new_bal = p["balance"] - bet
                update_player(user.id, balance=new_bal, total_losses=p["total_losses"] + 1)
                await query.edit_message_text(
                    f"🎰 Слоты\n\n{result}\n\n💀 Проигрыш! **-{fmt_money(bet)}**\n💰 Баланс: {fmt_money(new_bal)}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎰 Ещё", callback_data="casino"), InlineKeyboardButton("◀️ Профиль", callback_data="back_to_profile")]])
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
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("my_biz", my_biz_cmd))
    app.add_handler(CommandHandler("casino", casino_cmd))
    app.add_handler(CommandHandler("bonus", bonus_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Готов!")
    app.run_polling()


if __name__ == "__main__":
    main()
