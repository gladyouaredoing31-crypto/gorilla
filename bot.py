import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import time
import os

# ============================================================
# НАСТРОЙКИ (Берутся из переменных Railway)
# ============================================================
TOKEN = os.environ.get("VK_TOKEN", "vk1.a.NeVzXhHIacAAhMagzCsuKF01C5eCdo9NN5eXDG5TRyklhCV_67EA8Pib3Q-LjGXm-heGXwPq4w0eX2mCJzk_2AaJ1pyYeUWtT-kRC0N_ewpDHD2Phig1yHRHiqCtGVeReu-kyMvOprN3UTxQCoosSvunU_aOY0QY555H6aZAb41p7Vcz3Rfy-eQypM9rK7a-YkzGOpevpE4g5bW-zyPYLg")
GROUP_ID = os.environ.get("VK_GROUP_ID", "229194730")

# Текст рекламы
AD_TEXT = (
"🚀 Крутой игровой бот Jump ждёт тебя! 🚀

✨ Преимущества бота:
• Интуитивный интерфейс
• Стабильная работа 24/7

🎯 Переходи к боту: @jumpbot
💰 Не упусти возможность начать с большим преимуществом!"
)

# Ключевые слова для триггера
TRIGGER_WORDS = ['цена', 'купить', 'заказ', 'инфо', 'привет', 'товар']

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================
if not TOKEN or not GROUP_ID:
    print("❌ Ошибка: Не заданы VK_TOKEN или VK_GROUP_ID")
    exit(1)

try:
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("✅ Бот успешно подключен к ВК!")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    exit(1)

def send_msg(peer_id, text):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=random.randint(0, 2**31)
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

print("🚀 Бот запущен и слушает сообщения...")

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
while True:
    try:
        for event in longpoll.listen():
            # 1. Новое сообщение
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.obj.message
                peer_id = msg['peer_id']
                text = msg['text'].lower()
                from_id = msg['from_id']
                
                # Игнорируем ботов
                if from_id < 0:
                    continue

                # Проверка на ключевые слова
                for word in TRIGGER_WORDS:
                    if word in text:
                        send_msg(peer_id, AD_TEXT)
                        break

            # 2. Бота добавили в беседу
            elif event.type == VkBotEventType.MESSAGE_EVENT:
                # Если добавили в чат (invite)
                if event.object.get('type') == 'chat_invite_user':
                    peer_id = event.object['peer_id']
                    send_msg(peer_id, "👋 Всем привет! Я бот-помощник. Напишите 'цена', чтобы узнать наши предложения.")
    except Exception as e:
        print(f"⚠️ Ошибка Long Poll (переподключение через 5 сек): {e}")
        time.sleep(5)
