from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from collections import Counter
import re
from tqdm import tqdm
import time
from datetime import datetime
import json
import os

# Данные для авторизации
api_id = '21331329'
api_hash = 'f058ba68285d181172d6847e2a0ab60d'
chat_id = 613525471

# Инициализация клиента
client = TelegramClient('session_name', api_id, api_hash)

def get_text_from_message(msg):
    """Извлекает текст из сообщения всеми возможными способами"""
    # Проверяем стандартный атрибут text
    if hasattr(msg, 'text') and msg.text:
        return msg.text
    
    # Проверяем атрибут message
    if hasattr(msg, 'message') and msg.message:
        return msg.message
    
    # Проверяем атрибут raw_text
    if hasattr(msg, 'raw_text') and msg.raw_text:
        return msg.raw_text
    
    # Проверяем, есть ли медиа-контент с подписью
    if hasattr(msg, 'media') and msg.media:
        # Проверяем, есть ли у медиа атрибут caption
        if hasattr(msg.media, 'caption') and msg.media.caption:
            return msg.media.caption
    
    # Для фото и документов подпись может быть в другом месте
    if hasattr(msg, 'caption') and msg.caption:
        return msg.caption
    
    # Проверяем, является ли это сервисным сообщением
    if hasattr(msg, 'action') and msg.action:
        action_type = type(msg.action).__name__
        return f"Сервисное сообщение: {action_type}"
    
    # Проверяем наличие пересланного сообщения
    if hasattr(msg, 'forward') and msg.forward:
        if hasattr(msg.forward, 'text') and msg.forward.text:
            return f"Пересланное сообщение: {msg.forward.text}"
    
    # Проверяем специальные типы сообщений
    if hasattr(msg, 'photo'):
        return "Фото"
    if hasattr(msg, 'document'):
        return "Документ"
    if hasattr(msg, 'audio'):
        return "Аудио"
    if hasattr(msg, 'video'):
        return "Видео"
    if hasattr(msg, 'voice'):
        return "Голосовое сообщение"
    if hasattr(msg, 'sticker'):
        return "Стикер"
    
    # Если все способы не дали результата
    return None

def save_messages(messages, filename='count/messages.json'):
    """Сохранение сообщений в JSON файл"""
    print(f"Подготовка к сохранению {len(messages)} сообщений...")
    messages_data = []
    text_count = 0
    null_text_count = 0
    
    for msg in tqdm(messages, desc="Обработка сообщений для сохранения"):
        # Пробуем понять, что это за объект
        message_type = msg.__class__.__name__
        
        # Основные данные сообщения
        message_data = {
            'id': msg.id,
            'date': msg.date.isoformat() if hasattr(msg, 'date') else None,
            'message_type': message_type
        }
        
        # Пробуем получить текст всеми возможными способами
        text = get_text_from_message(msg)
        
        # Если текст найден, сохраняем его
        if text:
            message_data['text'] = text
            text_count += 1
        else:
            message_data['text'] = ""
            null_text_count += 1
            
            # Добавляем отладочную информацию
            try:
                # Удаляем клиента для возможности сериализации
                if hasattr(msg, '_client'):
                    delattr(msg, '_client')
                
                # Собираем информацию о всех атрибутах
                attrs = {}
                for attr in dir(msg):
                    if attr.startswith('_') or callable(getattr(msg, attr)):
                        continue
                    try:
                        value = getattr(msg, attr)
                        if value is not None:
                            if isinstance(value, (str, int, float, bool)):
                                attrs[attr] = value
                            elif hasattr(value, '__dict__'):
                                attrs[attr] = str(type(value).__name__)
                    except:
                        attrs[attr] = "ERROR"
                
                message_data['debug_info'] = {
                    'attrs': attrs
                }
                
                # Если есть медиа, добавляем информацию о нем
                if hasattr(msg, 'media') and msg.media:
                    message_data['media_type'] = msg.media.__class__.__name__
            except Exception as e:
                message_data['debug_error'] = str(e)
        
        messages_data.append(message_data)
    
    print(f"Обработано {len(messages_data)} сообщений:")
    print(f"- Сообщений с текстом: {text_count}")
    print(f"- Сообщений без текста: {null_text_count}")
    print(f"Сохранение в {filename}...")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(messages_data, f, ensure_ascii=False, indent=2)
    print(f"Сообщения сохранены в {filename}")
    return messages_data

def load_messages(filename='count/messages.json'):
    """Загрузка сообщений из JSON файла"""
    if not os.path.exists(filename):
        print(f"Файл {filename} не найден")
        return None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            messages_data = json.load(f)
        
        print(f"Загружено {len(messages_data)} сообщений из {filename}")
        return messages_data
    except Exception as e:
        print(f"Ошибка при загрузке сообщений: {e}")
        return None

async def analyze_chat():
    # Словарь для хранения статистики
    stats = {
        'мау': 0,
        'я люблю тебя': 0,
        'люблю тебя': 0,
        'солнце': 0,
        'солнышко': 0,
        'ева': 0,
        'евушка': 0,
        'яков': 0,
        'яша': 0,
        'яшечка': 0
    }
    
    # Счетчик для всех слов
    all_words = Counter()
    
    # Файл для сохранения сообщений
    messages_file = 'count/messages.json'
    
    # Пробуем загрузить сохраненные сообщения
    messages_data = load_messages(messages_file)
    
    if messages_data is None:
        # Если сохраненных сообщений нет, загружаем их из Telegram
        messages = []
        offset_id = 0
        total_messages = 0
        last_message_count = 0
        last_check_time = time.time()
        save_needed = False
        
        print("Начинаем загрузку сообщений из Telegram...")
        start_time = time.time()
        
        try:
            while True:
                history = await client(GetHistoryRequest(
                    peer=chat_id,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=100,
                    max_id=0,
                    min_id=0,
                    hash=0
                ))
                
                if not history.messages:
                    break
                    
                messages.extend(history.messages)
                offset_id = messages[-1].id
                total_messages = len(messages)
                
                current_time = time.time()
                elapsed_time = current_time - start_time
                check_interval = current_time - last_check_time
                
                # Проверяем скорость загрузки каждые 2 секунды
                if check_interval >= 2:
                    messages_per_interval = total_messages - last_message_count
                    speed = messages_per_interval / check_interval
                    
                    # Если скорость близка к нулю, возможно, началась пауза
                    if speed < 1 and total_messages > last_message_count:
                        save_needed = True
                    
                    last_message_count = total_messages
                    last_check_time = current_time
                
                # Оценка оставшегося времени
                estimated_time = (elapsed_time / total_messages) * 10000 if total_messages > 0 else 0
                msg_per_sec = total_messages / elapsed_time if elapsed_time > 0 else 0
                
                hours, remainder = divmod(estimated_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                print(f"\rЗагружено сообщений: {total_messages} | Скорость: {msg_per_sec:.2f} сообщений/сек | Примерное время окончания: {int(hours)}ч {int(minutes)}м {int(seconds)}с", end='')
                
                # Сохраняем при обнаружении паузы или каждые 3000 сообщений
                if save_needed or total_messages % 3000 == 0 and total_messages > 0:
                    print(f"\nСохранение промежуточных результатов ({total_messages} сообщений)...")
                    save_messages(messages, messages_file)
                    save_needed = False
                
                if len(history.messages) < 100:
                    break
            
            print(f"\nВсего загружено сообщений: {total_messages}")
            
            # Сохраняем все загруженные сообщения
            messages_data = save_messages(messages, messages_file)
            
        except Exception as e:
            print(f"\nОшибка при загрузке сообщений: {e}")
            
            # В случае ошибки пытаемся сохранить то, что успели загрузить
            if messages:
                print("Пытаемся сохранить уже загруженные сообщения...")
                messages_data = save_messages(messages, messages_file)
            else:
                return
    
    # Анализируем сообщения
    print("\nНачинаем анализ сообщений...")
    start_time = time.time()
    
    try:
        total_messages = len(messages_data)
        text_messages = 0
        
        for message in tqdm(messages_data, desc="Анализ сообщений"):
            if message.get('text'):
                text_messages += 1
                text = message['text'].lower()
                
                # Подсчет специальных фраз
                stats['мау'] += text.count('мау')
                stats['я люблю тебя'] += text.count('я люблю тебя')
                stats['люблю тебя'] += text.count('люблю тебя')
                stats['солнце'] += text.count('солнце')
                stats['солнышко'] += text.count('солнышко')
                stats['ева'] += text.count('ева')
                stats['евушка'] += text.count('евушка')
                stats['яков'] += text.count('яков')
                stats['яша'] += text.count('яша')
                stats['яшечка'] += text.count('яшечка')
                
                # Подсчет всех слов
                words = re.findall(r'\b\w+\b', text)
                all_words.update(words)
                
        print(f"Проанализировано {text_messages} текстовых сообщений из {total_messages} общих")
    except Exception as e:
        print(f"Ошибка при анализе сообщений: {e}")
    
    # Записываем результаты в файл
    try:
        with open('count/statistic.txt', 'w', encoding='utf-8') as f:
            f.write(f"Всего сообщений: {total_messages}\n")
            f.write(f"Текстовых сообщений: {text_messages}\n\n")
            
            f.write("Статистика по специальным фразам:\n")
            for phrase, count in stats.items():
                f.write(f"{phrase}: {count}\n")
            
            f.write("\nТоп-10 самых употребляемых слов:\n")
            for word, count in all_words.most_common(10):
                f.write(f"{word}: {count}\n")
            
            f.write("\nСписок из 10 случайных слов:\n")
            for word, count in list(all_words.items())[:10]:
                f.write(f"{word}: {count}\n")
        
        end_time = time.time()
        print(f"\nАнализ завершен за {end_time - start_time:.2f} секунд")
        print("Результаты сохранены в файл statistic.txt")
    except Exception as e:
        print(f"Ошибка при сохранении результатов: {e}")

async def main():
    await client.start()
    await analyze_chat()
    await client.disconnect()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main()) 