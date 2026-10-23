import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import os
import re

# ============================================================
# НАСТРОЙКИ
# ============================================================
TOKEN = os.environ.get("VK_TOKEN", "vk1.a.NeVzXhHIacAAhMagzCsuKF01C5eCdo9NN5eXDG5TRyklhCV_67EA8Pib3Q-LjGXm-heGXwPq4w0eX2mCJzk_2AaJ1pyYeUWtT-kRC0N_ewpDHD2Phig1yHRHiqCtGVeReu-kyMvOprN3UTxQCoosSvunU_aOY0QY555H6aZAb41p7Vcz3Rfy-eQypM9rK7a-YkzGOpevpE4g5bW-zyPYLg")
GROUP_ID = os.environ.get("VK_GROUP_ID", "229194730")
ADMIN_ID = 697665022  # <--- ЗАМЕНИ НА СВОЙ ID ВК (цифры)

# Список запрещенных слов (можешь дополнять)
BAD_WORDS = ['хуй', 'пизда', 'блять', 'сука', 'ебать', 'мудак', 'долбоеб', 'шлюха']

# Запрещать ли ссылки (True - да, False - нет)
BLOCK_LINKS = True

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

def send_msg(peer_id, text):
    try:
        vk.messages.send(peer_id=peer_id, message=text, random_id=random.randint(0, 2**31))
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def delete_msg(message_id, peer_id):
    try:
        vk.messages.delete(message_ids=message_id, delete_for_all=1)
    except Exception as e:
        print(f"Ошибка удаления: {e}")

def kick_user(peer_id, user_id):
    try:
        vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=user_id)
    except Exception as e:
        print(f"Ошибка кика: {e}")

print("🚀 Бот-модератор запущен...")

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
for event in longpoll.listen():
    # Если бота добавили в чат
    if event.type == VkBotEventType.MESSAGE_EVENT:
        if event.object.get('type') == 'chat_invite_user':
            peer_id = event.object['peer_id']
            # Проверяем, кого добавили
            user_id = event.object.get('user_id')
            if user_id and user_id < 0: # Если добавили БОТА (у ботов ID отрицательные)
                # Кикаем чужого бота
                kick_user(peer_id, user_id)
                send_msg(peer_id, "🤖 В чат добавлен бот. Я его удалил. Здесь только я главный.")
                # Уведомляем админа
                send_msg(ADMIN_ID, f"⚠️ В беседу {peer_id} пытались добавить другого бота. Я его кикнул.")
            elif user_id and user_id != ADMIN_ID:
                send_msg(peer_id, "👋 Привет! Я модератор этого чата. Соблюдайте правила!")

    # Новое сообщение
    elif event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.obj.message
        peer_id = msg['peer_id']
        user_id = msg['from_id']
        message_id = msg['id']
        text = msg.get('text', '').lower()

        # Работаем только в беседах и только для админов
        if peer_id > 2000000000:
            # Если пишет админ — не трогаем
            if user_id == ADMIN_ID:
                continue

            # Проверка на мат
            has_bad_word = False
            for word in BAD_WORDS:
                if re.search(r'\b' + word + r'\w*', text):
                    has_bad_word = True
                    break
            
            if has_bad_word:
                delete_msg(message_id, peer_id)
                send_msg(peer_id, f"🚫 @id{user_id}, не матерись! Сообщение удалено.")
                send_msg(ADMIN_ID, f"🚫 В чате {peer_id} удалено сообщение от @id{user_id} за мат.")
                continue

            # Проверка на ссылки
            if BLOCK_LINKS and re.search(r'https?://|vk\.com/', text):
                delete_msg(message_id, peer_id)
                send_msg(peer_id, f"🔗 @id{user_id}, ссылки запрещены!")
                send_msg(ADMIN_ID, f"🔗 В чате {peer_id} удалена ссылка от @id{user_id}.")
                continue
