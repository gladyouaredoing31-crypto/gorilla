import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3
import random
import time
import os
import re

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('vk1.a.NeVzXhHIacAAhMagzCsuKF01C5eCdo9NN5eXDG5TRyklhCV_67EA8Pib3Q-LjGXm-heGXwPq4w0eX2mCJzk_2AaJ1pyYeUWtT-kRC0N_ewpDHD2Phig1yHRHiqCtGVeReu-kyMvOprN3UTxQCoosSvunU_aOY0QY555H6aZAb41p7Vcz3Rfy-eQypM9rK7a-YkzGOpevpE4g5bW-zyPYLg') 
GROUP_ID = 229194730  # ЗАМЕНИ НА ID СВОЕГО СООБЩЕСТВА (без минуса)!
ADMIN_ID = 697665022  # ЗАМЕНИ НА СВОЙ ID ВК!

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect('game.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;") 

cursor.execute('''CREATE TABLE IF NOT EXISTS players 
                  (user_id INTEGER PRIMARY KEY, 
                   balance INTEGER, bank_deposit INTEGER DEFAULT 0, energy INTEGER, 
                   level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, 
                   last_work_time INTEGER DEFAULT 0, last_business_time INTEGER DEFAULT 0, 
                   last_race_time INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0, 
                   last_crime INTEGER DEFAULT 0, car TEXT DEFAULT 'Нет', pet TEXT DEFAULT 'Нет', 
                   businesses TEXT DEFAULT '', donate INTEGER DEFAULT 0, 
                   vip_until INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bets 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, target_id INTEGER, 
                   amount INTEGER, bet_type TEXT, status TEXT DEFAULT 'pending', created_at INTEGER)''')
conn.commit()

# --- СЛОВАРИ ---
WORKS = {
    "1": {"name": "🧹 Дворник", "earn_min": 50, "earn_max": 100, "energy": 1, "xp": 5},
    "2": {"name": "🏪 Продавец", "earn_min": 150, "earn_max": 250, "energy": 2, "xp": 15},
    "3": {"name": "💻 Программист", "earn_min": 400, "earn_max": 600, "energy": 4, "xp": 40},
    "4": {"name": "👔 Директор", "earn_min": 1000, "earn_max": 1500, "energy": 8, "xp": 100}
}
BUSINESSES = {
    "1": {"name": "🏪 Ларёк", "price": 5000, "income": 100}, "2": {"name": "☕ Кофейня", "price": 15000, "income": 350},
    "3": {"name": "🍔 Фастфуд", "price": 35000, "income": 800}, "4": {"name": "💈 Барбершоп", "price": 70000, "income": 1600},
    "5": {"name": "🏋️ Спортзал", "price": 150000, "income": 3500}, "6": {"name": "🏬 Супермаркет", "price": 300000, "income": 7000},
    "7": {"name": "🏭 Завод", "price": 600000, "income": 15000}, "8": {"name": "🏨 Отель", "price": 1200000, "income": 30000},
    "9": {"name": "🏦 Банк", "price": 3000000, "income": 80000}, "10": {"name": "🏙️ Небоскреб", "price": 10000000, "income": 250000}
}
CARS = {
    "1": {"name": "🚗 Лада", "price": 50000, "speed": 10}, "2": {"name": "🚙 Ford", "price": 150000, "speed": 15},
    "3": {"name": "🚗 Toyota", "price": 400000, "speed": 22}, "4": {"name": "🚙 BMW", "price": 800000, "speed": 30},
    "5": {"name": "🏎️ Audi", "price": 1500000, "speed": 38}, "6": {"name": "🏎️ Mercedes", "price": 2500000, "speed": 45},
    "7": {"name": "🏎️ Porsche", "price": 4500000, "speed": 55}, "8": {"name": "🏎️ Nissan GTR", "price": 7000000, "speed": 65},
    "9": {"name": "🏎️ Lambo", "price": 15000000, "speed": 80}, "10": {"name": "🚀 Bugatti", "price": 30000000, "speed": 100}
}
PETS = {
    "1": {"name": "🐹 Хомяк", "price": 2000, "bonus": 0.05}, "2": {"name": "🐱 Кот", "price": 10000, "bonus": 0.10},
    "3": {"name": "🐶 Собака", "price": 50000, "bonus": 0.20}, "4": {"name": "🦅 Орел", "price": 250000, "bonus": 0.50}
}
DONATE_SHOP = {
    "1": {"name": "⚡ Энергия", "price": 5, "desc": "Восстанавливает 10 энергии"},
    "2": {"name": "💎 VIP на 7 дней", "price": 50, "desc": "+50% к доходу"},
    "3": {"name": "🏎️ Тачка Киберпанк", "price": 150, "desc": "Скорость 120"},
    "4": {"name": "💰 Чемодан денег", "price": 20, "desc": "Дает 500.000$"}
}

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('👤 Профиль', color=VkKeyboardColor.PRIMARY)
    kb.add_button('🎁 Бонус', color=VkKeyboardColor.POSITIVE)
    kb.add_button('🏆 Топ', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button('💼 Работы', color=VkKeyboardColor.POSITIVE)
    kb.add_button('🏢 Бизнес', color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button('🏦 Банк', color=VkKeyboardColor.SECONDARY)
    kb.add_button('🏎️ Гонки', color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_button('🛒 Магазин', color=VkKeyboardColor.SECONDARY)
    kb.add_button('💎 Донат', color=VkKeyboardColor.PRIMARY)
    return kb.get_keyboard()

def get_works_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('1 Дворник', color=VkKeyboardColor.SECONDARY)
    kb.add_button('2 Продавец', color=VkKeyboardColor.SECONDARY)
    kb.add_button('3 Программист', color=VkKeyboardColor.SECONDARY)
    kb.add_button('4 Директор', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_back_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_shop_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('🚗 Автосалон', color=VkKeyboardColor.PRIMARY)
    kb.add_button('🐾 Питомцы', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_business_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('💵 Собрать доход', color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button('📋 Список бизнесов', color=VkKeyboardColor.SECONDARY)
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_bank_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('💵 Вложить 1000', color=VkKeyboardColor.POSITIVE)
    kb.add_button('💵 Вложить 10000', color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button('💰 Снять все', color=VkKeyboardColor.SECONDARY)
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_race_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('🏁 Погнали!', color=VkKeyboardColor.POSITIVE)
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_donate_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('🛍 Донат-Магазин', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_donate_shop_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('Купить 1', color=VkKeyboardColor.SECONDARY)
    kb.add_button('Купить 2', color=VkKeyboardColor.SECONDARY)
    kb.add_button('Купить 3', color=VkKeyboardColor.SECONDARY)
    kb.add_button('Купить 4', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

# --- ФУНКЦИИ ---
def check_player(user_id):
    """Проверяет, есть ли игрок в базе"""
    cursor.execute("SELECT user_id FROM players WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def get_player(user_id):
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO players VALUES (?, 1000, 0, 10, 1, 0, 0, 0, 0, 0, 0, 'Нет', 'Нет', '', 0, 0, 0)", (user_id,))
        conn.commit()
        return get_player(user_id)
    return row

def format_money(amount):
    return f"{amount:,}".replace(",", ".")

def add_xp(user_id, amount, peer_id):
    cursor.execute("SELECT level, xp FROM players WHERE user_id = ?", (user_id,))
    lvl, xp = cursor.fetchone()
    new_xp = xp + amount
    needed = lvl * 100 
    
    if new_xp >= needed:
        new_lvl = lvl + 1
        cursor.execute("UPDATE players SET level = ?, xp = xp + ? - ?, energy = 10, balance = balance + ? WHERE user_id = ?", 
                       (new_lvl, amount, needed, new_lvl * 500, user_id))
        conn.commit()
        send_msg(peer_id, f"🎉 **НОВЫЙ УРОВЕНЬ: {new_lvl}!**\n💰 Бонус: +{format_money(new_lvl * 500)}$\n⚡ Энергия восстановлена!", from_group=1)
    else:
        cursor.execute("UPDATE players SET xp = xp + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

def send_msg(peer_id, text, keyboard=None, from_group=0):
    params = {'peer_id': peer_id, 'message': text, 'random_id': 0}
    if keyboard: params['keyboard'] = keyboard
    if from_group: params['from_group'] = 1
    try:
        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка ВК: {e}")

# --- ОСНОВНОЙ ЦИКЛ ---
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()

print("🚀 Бот запущен! Система регистрации активна.")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        msg = event.text.lower().strip()
        user_id = event.user_id
        peer_id = event.peer_id
        now = int(time.time())
        
        # ==========================================
        # 0. ПРОВЕРКА РЕГИСТРАЦИИ И СТАРТ
        # ==========================================
        
        # Если игрок не зарегистрирован, разрешаем только команды старта
        if not check_player(user_id):
            if msg in ['начать', 'я', 'меню']:
                get_player(user_id) # Создаем в БД
                send_msg(peer_id, "🎉 **Добро пожаловать в игру!**\n\nТвой стартовый капитал: **1.000$**\nЭнергия: **10/10**\n\nВыбирай действия на клавиатуре ниже или пиши команды в чат!", get_main_keyboard())
            else:
                send_msg(peer_id, "👋 Привет! Ты тут впервые.\nНапиши **«начать»**, **«я»** или **«меню»**, чтобы зарегистрироваться и получить стартовый капитал.")
            continue # Пропускаем остальной код для незарегистрированных

        # Если дошли сюда — игрок зарегистрирован
        player = get_player(user_id)
        is_vip = player[15] > now
        is_admin = (user_id == ADMIN_ID or player[16] == 1)
        
        # ==========================================
        # 1. ТАЙМЕРЫ (Проверяются каждое сообщение)
        # ==========================================
        cursor.execute("SELECT id, creator_id, target_id, amount FROM bets WHERE status = 'pending' AND created_at < ?", (now - 600,))
        for bet in cursor.fetchall():
            cursor.execute("UPDATE bets SET status = 'expired' WHERE id = ?", (bet[0],))
            cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (bet[3], bet[1]))
            conn.commit()
            send_msg(peer_id, f"⏳ Ставка от ID {bet[1]} отменена (10 мин). Деньги возвращены.", from_group=1)

        cursor.execute("SELECT id, creator_id, amount, bet_type FROM bets WHERE status = 'roulette' AND created_at < ?", (now - 60,))
        for rou in cursor.fetchall():
            bot_roll = random.randint(0, 36)
            if bot_roll == 0: color, is_red = "🟢 ЗЕРО", False
            else:
                is_red = (bot_roll % 2 != 0)
                color = "🔴 КРАСНОЕ" if is_red else "⚫ ЧЕРНОЕ"
            
            player_bet_red = (rou[3] == 'к')
            cursor.execute("UPDATE bets SET status = 'finished' WHERE id = ?", (rou[0],))
            
            if bot_roll != 0 and (is_red == player_bet_red):
                win_amount = rou[2] * 2
                cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (win_amount, rou[1]))
                conn.commit()
                send_msg(peer_id, f"🎰 Выпало: **{bot_roll}** ({color})\n🏆 ID {rou[1]} забирает {format_money(win_amount)}$!", from_group=1)
            else:
                send_msg(peer_id, f"🎰 Выпало: **{bot_roll}** ({color})\n💥 ID {rou[1]} проиграл {format_money(rou[2])}$.", from_group=1)

        # ==========================================
        # 2. АДМИНКА
        # ==========================================
        if msg == '/a':
            if is_admin:
                text = ("👑 **АДМИН-ПАНЕЛЬ**\n\n"
                        "Команды работают **ответом** на сообщение человека или с указанием @id:\n\n"
                        "`дай 5000` — выдать деньги\n"
                        "`алмаз 10` — выдать алмазы\n"
                        "`выдать админку` — выдать админку\n"
                        "`забрать админку` — забрать админку\n"
                        "`сброс` — сбросить энергию и кулдауны\n"
                        "`лвл 50` — установить уровень")
                send_msg(peer_id, text)

        elif is_admin:
            try:
                parts = msg.split()
                cmd = parts[0]
                target_id = event.reply_message['from_id'] if event.reply_message else None
                
                if not target_id:
                    for p in parts:
                        if '@id' in p:
                            target_id = int(p.replace('@id', '').split('|')[0])
                            break
                
                if target_id:
                    get_player(target_id) # Создаем, если нет
                    if cmd == 'дай':
                        amount = int(parts[1])
                        cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                        send_msg(peer_id, f"✅ Выдано {format_money(amount)}$ игроку ID {target_id}.")
                    elif cmd == 'алмаз':
                        amount = int(parts[1])
                        cursor.execute("UPDATE players SET donate = donate + ? WHERE user_id = ?", (amount, target_id))
                        send_msg(peer_id, f"✅ Выдано {amount} алмазов ID {target_id}.")
                    elif msg == 'выдать админку':
                        cursor.execute("UPDATE players SET is_admin = 1 WHERE user_id = ?", (target_id,))
                        send_msg(peer_id, f"👑 ID {target_id} теперь админ!")
                    elif msg == 'забрать админку':
                        cursor.execute("UPDATE players SET is_admin = 0 WHERE user_id = ?", (target_id,))
                        send_msg(peer_id, f"✅ ID {target_id} больше не админ.")
                    elif msg == 'сброс':
                        cursor.execute("UPDATE players SET energy = 10, last_work_time = 0, last_race_time = 0, last_crime = 0 WHERE user_id = ?", (target_id,))
                        send_msg(peer_id, f"✅ Кулдауны ID {target_id} сброшены.")
                    elif cmd == 'лвл':
                        lvl = int(parts[1])
                        cursor.execute("UPDATE players SET level = ? WHERE user_id = ?", (lvl, target_id))
                        send_msg(peer_id, f"✅ Уровень ID {target_id} теперь {lvl}.")
                    conn.commit()
            except: pass

        # ==========================================
        # 3. PAY (Перевод)
        # ==========================================
        elif msg.startswith('перевод '):
            try:
                parts = msg.split()
                amount = int(parts[1])
                
                target_id = event.reply_message['from_id'] if event.reply_message else None
                if not target_id:
                    for p in parts:
                        if '@id' in p:
                            target_id = int(p.replace('@id', '').split('|')[0])
                            break
                
                if not target_id:
                    send_msg(peer_id, "❌ Ответь на сообщение человека или укажи @id123.")
                elif target_id == user_id:
                    send_msg(peer_id, "❌ Себе переводить нельзя.")
                elif amount < 10:
                    send_msg(peer_id, "❌ Минимальный перевод: 10$.")
                elif player[1] < amount:
                    send_msg(peer_id, "❌ Недостаточно средств.")
                else:
                    get_player(target_id)
                    cursor.execute("UPDATE players SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                    cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                    conn.commit()
                    send_msg(peer_id, f"💸 Ты перевел **{format_money(amount)}$** игроку ID {target_id}!", get_main_keyboard())
                    send_msg(target_id, f"💰 Тебе перевели **{format_money(amount)}$** от ID {user_id}!", from_group=1)
            except:
                send_msg(peer_id, "❌ Ошибка. Пиши: `pay 500` (ответом) или `pay 500 @id123`")

        # ==========================================
        # 4. ИГРОВЫЕ КОМАНДЫ
        # ==========================================
        elif msg in ['профиль', 'начать', 'я', 'меню', '⬅️ назад']:
            my_biz = player[13].split(',') if player[13] else []
            total_income = sum(BUSINESSES[b]['income'] for b in my_biz if b in BUSINESSES)
            vip_text = "👑 VIP" if is_vip else ""
            adm_text = "🛡 Админ" if is_admin else ""
            
            text = (f"👤 **Профиль** {vip_text} {adm_text}\n"
                    f"🏆 Уровень: {player[4]} (XP: {player[5]}/{player[4]*100})\n"
                    f"💰 Баланс: {format_money(player[1])}$\n"
                    f"💎 Алмазы: {player[14]}\n"
                    f"🏦 Депозит: {format_money(player[2])}$\n"
                    f"⚡ Энергия: {player[3]}/10\n"
                    f"🐾 Питомец: {player[12]}\n"
                    f"🏢 Бизнесов: {len(my_biz)}\n"
                    f"🚗 Машина: {player[11]}")
            send_msg(peer_id, text, get_main_keyboard())

        elif msg == 'работы':
            send_msg(peer_id, "Выбери работу (кулдаунов нет):\n1 Дворник (1 энергия)\n2 Продавец (2 энергии)\n3 Программист (4 энергии)\n4 Директор (8 энергий)", get_works_keyboard())

        elif msg in ['1 дворник', '2 продавец', '3 программист', '4 директор']:
            work = WORKS[msg[0]]
            if player[3] < work["energy"]:
                send_msg(peer_id, "⚡ Мало энергии!")
            else:
                earned = random.randint(work["earn_min"], work["earn_max"])
                for pet in PETS.values():
                    if pet['name'] == player[12]: earned = int(earned * (1 + pet['bonus']))
                if is_vip: earned = int(earned * 1.5)
                cursor.execute("UPDATE players SET balance=balance+?, energy=energy-?, last_work_time=? WHERE user_id=?", (earned, work["energy"], now, user_id))
                conn.commit()
                add_xp(user_id, work["xp"], peer_id)
                send_msg(peer_id, f"💼 {work['name']}\nЗаработано: **{format_money(earned)}$**\n⚡ Энергии: {player[3] - work['energy']}/10", get_main_keyboard())

        elif msg == 'бонус':
            if now - player[9] < 86400:
                send_msg(peer_id, "⏳ Бонус уже получен сегодня.")
            else:
                daily_money = random.randint(500, 2000) + (player[4] * 100)
                if is_vip: daily_money *= 2
                cursor.execute("UPDATE players SET balance = balance + ?, energy = 10, last_daily = ? WHERE user_id = ?", (daily_money, now, user_id))
                conn.commit()
                send_msg(peer_id, f"🎁 Бонус: **+{format_money(daily_money)}$**\n⚡ Энергия восстановлена!", get_main_keyboard())

        elif msg == 'магазин':
            send_msg(peer_id, "Выбери раздел:", get_shop_keyboard())

        elif msg == 'автосалон':
            text = "🚗 **АВТОСАЛОН** (пиши 'купить авто 1'):\n"
            for k, v in CARS.items(): text += f"{k}. {v['name']} — {format_money(v['price'])}$\n"
            send_msg(peer_id, text, get_back_keyboard())

        elif msg.startswith('купить авто '):
            try:
                car_id = msg.split()[2]
                car = CARS[car_id]
                if player[1] >= car["price"]:
                    cursor.execute("UPDATE players SET balance=balance-?, car=? WHERE user_id=?", (car["price"], car["name"], user_id))
                    conn.commit()
                    send_msg(peer_id, f"✅ Куплено: {car['name']}!", get_main_keyboard())
                else: send_msg(peer_id, "❌ Мало денег!")
            except: pass

        elif msg == 'питомцы':
            text = "🐾 **ПИТОМЦЫ** (пиши 'купить питомца 1'):\n"
            for k, v in PETS.items(): text += f"{k}. {v['name']} — {format_money(v['price'])}$ (+{int(v['bonus']*100)}%)\n"
            send_msg(peer_id, text, get_back_keyboard())

        elif msg.startswith('купить питомца '):
            try:
                pet_id = msg.split()[2]
                pet = PETS[pet_id]
                if player[1] >= pet["price"]:
                    cursor.execute("UPDATE players SET balance=balance-?, pet=? WHERE user_id=?", (pet["price"], pet["name"], user_id))
                    conn.commit()
                    send_msg(peer_id, f"✅ Куплен: {pet['name']}!", get_main_keyboard())
                else: send_msg(peer_id, "❌ Мало денег!")
            except: pass

        elif msg == 'бизнес':
            send_msg(peer_id, "Бизнес-центр:", get_business_keyboard())
            
        elif msg == 'список бизнесов':
            text = "🏢 **БИЗНЕСЫ** (пиши 'купить бизнес 1'):\n"
            for k, v in BUSINESSES.items(): text += f"{k}. {v['name']} — {format_money(v['price'])}$ (+{format_money(v['income'])}$)\n"
            send_msg(peer_id, text)
            
        elif msg.startswith('купить бизнес '):
            try:
                biz_id = msg.split()[2]
                biz = BUSINESSES[biz_id]
                if player[1] >= biz["price"]:
                    current_biz = player[13].split(',') if player[13] else []
                    current_biz.append(biz_id)
                    cursor.execute("UPDATE players SET balance=balance-?, businesses=? WHERE user_id=?", (biz["price"], ",".join(current_biz), user_id))
                    conn.commit()
                    send_msg(peer_id, f"✅ Куплен: {biz['name']}!", get_business_keyboard())
                else: send_msg(peer_id, "❌ Мало денег!")
            except: pass

        elif msg == 'собрать доход':
            if now - player[7] < 3600:
                send_msg(peer_id, f"⏳ Жди {3600 - (now - player[7])} сек.")
            else:
                my_biz = player[13].split(',') if player[13] else []
                if not my_biz: send_msg(peer_id, "Нет бизнесов!")
                else:
                    total_income = sum(BUSINESSES[b]['income'] for b in my_biz if b in BUSINESSES)
                    if is_vip: total_income = int(total_income * 1.5)
                    cursor.execute("UPDATE players SET balance=balance+?, last_business_time=? WHERE user_id=?", (total_income, now, user_id))
                    conn.commit()
                    send_msg(peer_id, f"💰 Доход: **+{format_money(total_income)}$**")

        elif msg == 'банк':
            text = f"🏦 **БАНК**\nНа руках: {format_money(player[1])}$\nНа депозите: {format_money(player[2])}$"
            send_msg(peer_id, text, get_bank_keyboard())

        elif msg.startswith('вложить ') or msg in ['вложить 1000', 'вложить 10000']:
            try:
                if '1000' in msg: amount = 1000
                elif '10000' in msg: amount = 10000
                else: amount = int(msg.split()[1])
                
                if player[1] >= amount and amount > 0:
                    cursor.execute("UPDATE players SET balance=balance-?, bank_deposit=bank_deposit+? WHERE user_id=?", (amount, amount, user_id))
                    conn.commit()
                    send_msg(peer_id, f"✅ Вложено: {format_money(amount)}$", get_bank_keyboard())
            except: pass

        elif msg == 'снять все':
            if player[2] > 0:
                profit = int(player[2] * 0.05)
                total_w = player[2] + profit
                cursor.execute("UPDATE players SET balance=balance+?, bank_deposit=0 WHERE user_id=?", (total_w, user_id))
                conn.commit()
                send_msg(peer_id, f"💰 Снято: **{format_money(total_w)}$**", get_bank_keyboard())
            else: send_msg(peer_id, "Депозит пуст.")

        elif msg == 'гонки':
            send_msg(peer_id, f"🏎️ **ГОНКИ**\nТвоя тачка: {player[11]}\nВход: 1000$.", get_race_keyboard())

        elif msg == 'погнали':
            if player[11] == 'Нет': send_msg(peer_id, "❌ Нет машины!")
            elif player[1] < 1000: send_msg(peer_id, "❌ Нужно 1000$.")
            elif now - player[8] < 60: send_msg(peer_id, "⏳ Жди минуту.")
            else:
                speed = 120 if player[11] == '🏎️ Тачка Киберпанк' else 0
                for c in CARS.values():
                    if c['name'] == player[11]: speed = c['speed']
                
                p_roll = random.randint(1, 100) + speed
                e_roll = random.randint(1, 100) + 15
                cursor.execute("UPDATE players SET last_race_time=? WHERE user_id=?", (now, user_id))
                
                if p_roll > e_roll:
                    cursor.execute("UPDATE players SET balance=balance+1000 WHERE user_id=?", (user_id,))
                    conn.commit()
                    add_xp(user_id, 20, peer_id)
                    send_msg(peer_id, f"🏆 **ПОБЕДА!** {p_roll} vs {e_roll}\n+1000$", get_main_keyboard())
                else:
                    cursor.execute("UPDATE players SET balance=balance-1000 WHERE user_id=?", (user_id,))
                    conn.commit()
                    send_msg(peer_id, f"💥 **ПРОИГРЫШ!** {p_roll} vs {e_roll}\n-1000$", get_main_keyboard())

        elif msg == 'донат':
            send_msg(peer_id, f"💎 Твои алмазы: **{player[14]}**\nVIP: {'✅' if is_vip else '❌'}", get_donate_keyboard())

        elif msg == 'донат-магазин':
            text = "🛍 **ДОНАТ-МАГАЗИН** (пиши 'купить донат 1'):\n"
            for k, v in DONATE_SHOP.items(): text += f"{k}. {v['name']} — {v['price']} 💎\n"
            send_msg(peer_id, text, get_donate_shop_keyboard())

        elif msg.startswith('купить донат '):
            try:
                item_id = msg.split()[2]
                item = DONATE_SHOP[item_id]
                if player[14] >= item['price']:
                    cursor.execute("UPDATE players SET donate = donate - ? WHERE user_id = ?", (item['price'], user_id))
                    if item_id == "1": cursor.execute("UPDATE players SET energy = 10 WHERE user_id = ?", (user_id,))
                    elif item_id == "2": cursor.execute("UPDATE players SET vip_until = ? WHERE user_id = ?", (now + 604800, user_id))
                    elif item_id == "3": cursor.execute("UPDATE players SET car = '🏎️ Тачка Киберпанк' WHERE user_id = ?", (user_id,))
                    elif item_id == "4": cursor.execute("UPDATE players SET balance = balance + 500000 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    send_msg(peer_id, f"✅ Куплено: {item['name']}!", get_main_keyboard())
                else: send_msg(peer_id, "❌ Мало алмазов!")
            except: pass

        elif msg == 'топ':
            cursor.execute("SELECT user_id, balance + bank_deposit as total FROM players ORDER BY total DESC LIMIT 5")
            top = cursor.fetchall()
            text = "🏆 **ТОП БОГАЧЕЙ:**\n"
            for i, row in enumerate(top): text += f"{i+1}. ID {row[0]} — {format_money(row[1])}$\n"
            send_msg(peer_id, text)

        # Казино
        roulette_match = re.match(r'^(к|ч)\s+(\d+)$', msg)
        if roulette_match:
            bet_type = roulette_match.group(1).upper()
            amount = int(roulette_match.group(2))
            if amount >= 10 and player[1] >= amount:
                cursor.execute("UPDATE players SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                cursor.execute("INSERT INTO bets (creator_id, target_id, amount, bet_type, status, created_at) VALUES (?, 0, ?, ?, 'roulette', ?)", (user_id, amount, bet_type, now))
                conn.commit()
                send_msg(peer_id, f"🎰 Ставка **{amount}$** на {'🔴 КРАСНОЕ' if bet_type == 'К' else '⚫ ЧЕРНОЕ'}. Ждем 60 сек!", from_group=1)

        dice_match = re.match(r'^кости\s+(\d+)(?:\s+\[id(\d+)\|.*?\])?', msg)
        if dice_match:
            amount = int(dice_match.group(1))
            target_id = int(dice_match.group(2)) if dice_match.group(2) else (event.reply_message['from_id'] if event.reply_message else None)
            if target_id and target_id != user_id and player[1] >= amount:
                cursor.execute("UPDATE players SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                cursor.execute("INSERT INTO bets (creator_id, target_id, amount, bet_type, status, created_at) VALUES (?, ?, ?, 'кости', 'pending', ?)", (user_id, target_id, amount, now))
                conn.commit()
                send_msg(peer_id, f"🎲 ID {user_id} вызывает ID {target_id} на {amount}$!\nНапиши 'принять'.", from_group=1)

        elif msg == 'принять':
            cursor.execute("SELECT id, creator_id, amount FROM bets WHERE target_id = ? AND status = 'pending' ORDER BY created_at ASC LIMIT 1", (user_id,))
            bet = cursor.fetchone()
            if bet and player[1] >= bet[2]:
                cursor.execute("UPDATE players SET balance = balance - ? WHERE user_id = ?", (bet[2], user_id))
                r1, r2 = random.randint(1, 100), random.randint(1, 100)
                while r1 == r2: r1, r2 = random.randint(1, 100), random.randint(1, 100)
                
                if r1 > r2:
                    cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (bet[2]*2, bet[1]))
                    res = f"Победил ID {bet[1]}"
                else:
                    cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (bet[2]*2, user_id))
                    res = f"Победил ID {user_id}"
                cursor.execute("UPDATE bets SET status = 'finished' WHERE id = ?", (bet[0],))
                conn.commit()
                send_msg(peer_id, f"🎲 {res}!\nСчет: {r1} - {r2}\nВыигрыш: {bet[2]*2}$", from_group=1)

        elif msg == 'отменить':
            cursor.execute("SELECT id, amount FROM bets WHERE creator_id = ? AND status = 'pending' LIMIT 1", (user_id,))
            bet = cursor.fetchone()
            if bet:
                cursor.execute("UPDATE bets SET status = 'cancelled' WHERE id = ?", (bet[0],))
                cursor.execute("UPDATE players SET balance = balance + ? WHERE user_id = ?", (bet[1], user_id))
                conn.commit()
                send_msg(peer_id, f"✅ Ставка отменена. Возврат {bet[1]}$")
