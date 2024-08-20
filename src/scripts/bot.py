import os
import json
import spacy
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext

# Получаем абсолютный путь к файлу faq.json
base_dir = os.path.dirname(os.path.abspath(__file__))
faq_path = os.path.join(base_dir, '../resources/faq.json')

# Загрузка базы данных
with open(faq_path, 'r', encoding='utf-8') as f:
    faq_data = json.load(f)

# Инициализация spaCy
nlp = spacy.load('ru_core_news_md')

# Функция поиска лучшего ответа
def find_best_match(question):
    question_doc = nlp(question)
    best_match = None
    best_similarity = 0.0

    for item in faq_data['вопросы']:
        faq_doc = nlp(item['вопрос'])
        similarity = question_doc.similarity(faq_doc)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = item['ответ']

    if best_similarity > 0.7:
        return best_match
    else:
        return "Извините, я не могу найти подходящий ответ. Попробуйте сформулировать вопрос иначе или обратитесь в службу поддержки."

# Обработчик сообщений
async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    answer = find_best_match(user_message)
    await update.message.reply_text(answer)

# Запуск бота
async def main():
    app = Application.builder().token("7200244522:AAFiObA4LT1wzz1DJ0-9z1KdQCLKjRFPRDA").build()

    # Явная инициализация приложения
    await app.initialize()

    # Добавление обработчика сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск приложения
    await app.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
