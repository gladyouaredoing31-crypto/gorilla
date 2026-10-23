import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import time
import os

# ============================================================
# НАСТРОЙКИ
# ============================================================
TOKEN = os.environ.get("VK_TOKEN", "vk1.a.NeVzXhHIacAAhMagzCsuKF01C5eCdo9NN5eXDG5TRyklhCV_67EA8Pib3Q-LjGXm-heGXwPq4w0eX2mCJzk_2AaJ1pyYeUWtT-kRC0N_ewpDHD2Phig1yHRHiqCtGVeReu-kyMvOprN3UTxQCoosSvunU_aOY0QY555H6aZAb41p7Vcz3Rfy-eQypM9rK7a-YkzGOpevpE4g5bW-zyPYLg")
GROUP_ID = os.environ.get("VK_GROUP_ID", "229194730")

# ТВОЙ ЛИЧНЫЙ ID (чтобы бот слушался только тебя)
ADMIN_ID = 697665022  # <--- ЗАМЕНИ НА СВОЙ ID (цифры)

TEXT_FILE = "ad_text.txt"

# ============================================================
# ФУНКЦИИ
# ============================================================
def get_ad_text():
    if os.path.exists(TEXT_FILE):
        with open(TEXT_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return "Реклама пока не задана. Напиши /текст ..."

def save_ad_text(text):
    with open(TEXT_FILE, 'w', encoding='utf-8') as f:
        f.write(text)

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

print("✅ Бот запущен (Режим ЛС)")

def send_msg(peer_id, text):
    try:
        vk.messages.send(peer_id=peer_id, message=text, random_id=random.randint(0, 2**31))
    except Exception as e:
        print(f"❌ Ошибка отправки в {peer_id}: {e}")

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.obj.message
        peer_id = msg['peer_id']
        text = msg['text'].strip()
        from_id = msg['from_id']
        
        # Работаем только если пишет Админ в ЛС (peer_id = from_id)
        if from_id == ADMIN_ID and peer_id == ADMIN_ID:
            if text.startswith('/текст'):
                new_text = text[6:].strip()
                if new_text:
                    save_ad_text(new_text)
                    send_msg(peer_id, f"✅ Текст обновлен!\n\nПредпросмотр:\n{new_text}")
                else:
                    send_msg(peer_id, "❌ Напиши текст после команды. Пример:\n/текст Привет! Заходите к нам...")
            
            elif text == '/показать':
                current = get_ad_text()
                send_msg(peer_id, f"📝 Текущий текст:\n\n{current}")
                
            elif text == '/список':
                try:
                    # Получаем список бесед
                    conversations = vk.messages.getConversations(count=200)
                    items = conversations['items']
                    chats = [item for item in items if item['conversation']['peer']['type'] == 'chat']
                    
                    if not chats:
                        send_msg(peer_id, "🤷‍♂️ Бот пока не добавлен ни в одну беседу.")
                    else:
                        res = f"📋 Бот добавлен в {len(chats)} бесед:\n\n"
                        for item in chats:
                            peer = item['conversation']['peer']
                            res += f"ID: {peer['local_id']} | {peer.get('title', 'Без названия')}\n"
                        send_msg(peer_id, res)
                except Exception as e:
                    send_msg(peer_id, f"❌ Ошибка получения списка: {e}")
                    
            elif text == '/рассылка':
                ad = get_ad_text()
                if "Реклама пока не задана" in ad:
                    send_msg(peer_id, "❌ Сначала задай текст через /текст")
                    continue
                    
                send_msg(peer_id, "🚀 Начинаю рассылку по всем беседам...")
                
                try:
                    conversations = vk.messages.getConversations(count=200)
                    items = conversations['items']
                    chats = [item for item in items if item['conversation']['peer']['type'] == 'chat']
                    
                    success = 0
                    for item in chats:
                        target_peer = item['conversation']['peer']['id']
                        send_msg(target_peer, ad)
                        success += 1
                        time.sleep(1) # Задержка чтобы не забанили
                    
                    send_msg(peer_id, f"✅ Рассылка завершена! Отправлено в {success} чатов.")
                except Exception as e:
                    send_msg(peer_id, f"❌ Ошибка рассылки: {e}")
                    
            else:
                send_msg(peer_id, "👋 Привет, Админ!\n\nКоманды:\n/текст [текст] — задать рекламу\n/показать — посмотреть текущую\n/список — список чатов\n/рассылка — разослать по всем чатам")
