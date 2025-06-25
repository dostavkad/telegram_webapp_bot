from contextlib import suppress
import logging
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.utils.callback_data import CallbackData
from aiogram.utils import executor

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import os
import json
from datetime import datetime, date
import aiocron  # для запуска по расписанию

load_dotenv()  # Загрузить переменные из .env

API_TOKEN = os.getenv("API_TOKEN")  # Получаем токен
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 📦 CallbackData для inline-кнопок статуса
status_cb = CallbackData("status", "action", "order_id", "client_id")
def save_order(order):
    now = datetime.now()
    order['timestamp'] = now.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open("orders.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    data.append(order)
    with open("orders.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
from datetime import date, timedelta

@aiocron.crontab('0 0 * * *')  # каждый день в 00:00
async def send_daily_report():
    try:
        with open("orders.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = []

    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    orders = [o for o in data if o['timestamp'].startswith(yesterday)]
    total = sum(o.get("total", 0) for o in orders)
    count = len(orders)

    text = f"🧾 Финальный отчёт за {yesterday}:\n\n📦 Заказов: {count}\n💰 Общая сумма: {total:,} сум"
    if orders:
        text += "\n\n📋 Список заказов:\n"
        for i, order in enumerate(orders, 1):
            name = order.get("name", "Неизвестно")
            amount = order.get("total", 0)
            text += f"{i}) {name} — {amount:,} сум\n"

    await bot.send_message(ADMIN_CHAT_ID, text)

    # 🧹 Удаляем доставленные заказы из файла для курьеров
    updated_data = [o for o in data if o.get("status") != "доставлено"]
    with open("orders.json", "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)

@dp.message_handler(Text(equals="📊 Отчёт"))
async def report_button_handler(message: types.Message):
    ADMIN_CHAT_ID = 611617181
    if message.from_user.id != ADMIN_CHAT_ID:
        return

    from datetime import date
    today = date.today().strftime('%Y-%m-%d')

    try:
        with open("orders.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = []

    orders = [o for o in data if o['timestamp'].startswith(today)]
    total = sum(o.get("total", 0) for o in orders)
    count = len(orders)

    text = f"📊 Текущий отчёт за {today}:\n\n📦 Заказов: {count}\n💰 Общая сумма: {total:,} сум"
    if orders:
        text += "\n\n📋 Список заказов:\n"
        for i, order in enumerate(orders, 1):
            name = order.get("name", "Неизвестно")
            amount = order.get("total", 0)
            text += f"{i}) {name} — {amount:,} сум\n"

    await message.answer(text)

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(
        text="🛍 Список продуктов",
        web_app=WebAppInfo(url="https://cedar-absorbing-oriole.glitch.me/")
    ))
    kb.add(KeyboardButton("📞 Поддержка"))

    if message.from_user.id == ADMIN_CHAT_ID:
        kb.add(KeyboardButton("📊 Отчёт"))

    await message.answer(
        "👋 Добро пожаловать в ваш продуктовый магазин!\n\n"
        "🚜 ДОСТАВКА ПРЯМО С ДЕХКАНСКОГО ОПТОВОГО БАЗАРА\n"
        "💸 Дешевле, чем в магазине\n"
        "🏡 Не выходя из дома — заказывайте и ЭКОНОМЬТЕ уже сегодня!\n\n"
        "🛍 Нажмите кнопку *Список продуктов*, чтобы выбрать товары.",
        reply_markup=kb,
        parse_mode='Markdown'
    )


# 📞 Поддержка
@dp.message_handler(Text(equals="📞 Поддержка"))
async def support_handler(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(
        text="🛍 Список продуктов",
        web_app=WebAppInfo(url="https://cedar-absorbing-oriole.glitch.me/")
    ))
    kb.add(KeyboardButton("📞 Поддержка"))

    await message.answer(
        "📞 <b>Поддержка</b>\n"
        "Телефон: <a href='tel:+998(97)111-24-24'>+998 97 111 24 24</a>\n"
        "Telegram: <a href='https://t.me/jamshwdovich_8'>@jamshwdovich_8</a>",
        parse_mode='HTML'
    )

# 📤 Обработка данных из WebApp
@dp.message_handler(content_types=types.ContentType.WEB_APP_DATA)
async def webapp_data_handler(message: types.Message):
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

    try:
        data = json.loads(message.web_app_data.data)
        order_text = data.get("text")
        order_id = data.get("order_id")
        client_id = data.get("client_id") or message.from_user.id

        # Кнопки для курьера
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("✅ Оплачено", callback_data=status_cb.new(action="оплачено", order_id=order_id, client_id=client_id)),
            InlineKeyboardButton("🚗 В пути", callback_data=status_cb.new(action="в_пути", order_id=order_id, client_id=client_id)),
            InlineKeyboardButton("📦 Доставлено", callback_data=status_cb.new(action="доставлено", order_id=order_id, client_id=client_id))
        )

        # Отправка курьеру
        await bot.send_message(chat_id='611617181', text=order_text, parse_mode="Markdown", reply_markup=markup   )

        # Отправка клиенту с новым текстом
        await bot.send_message(
            chat_id=client_id,
            text=f"📦 *Ваш заказ принят!*\n📲 *Скоро мы свяжемся с вами!*\n\n{order_text}",
            parse_mode="Markdown"
        )

        # Сохранить заказ
        save_order(data)
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке заказа: {e}")

# 🔄 Обработка изменения статуса заказа
@dp.callback_query_handler(status_cb.filter())
async def status_handler(query: types.CallbackQuery, callback_data: dict):
    status = callback_data['action']
    order_id = callback_data['order_id']
    client_id = int(callback_data['client_id'])

    # обновим статус в файле
    try:
        with open("orders.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = []

    for order in data:
        if order.get("order_id") == order_id:
            order["status"] = status
            break

    with open("orders.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Отправка уведомления клиенту
    status_texts = {
        'оплачено': '✅ Ваш заказ #{} оплачен.',
        'в_пути': '🚗 Ваш заказ #{} в пути.',
        'доставлено': '📦 Ваш заказ #{} доставлен. Спасибо за покупку!'
    }
    message = status_texts.get(status, '📦 Статус обновлён').format(order_id)
    await bot.send_message(chat_id=client_id, text=message)
    await query.answer(f"Статус заказа обновлён: {status}")

import os
from aiogram.utils.executor import start_webhook

WEBHOOK_HOST = 'https://telegram-webapp-bot-vhk8.onrender.com'  # <-- Твой адрес на Render
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(dp):
    from contextlib import suppress
    with suppress(Exception):
        await send_daily_report.__wrapped__()  # Вызов отчёта
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000))
    )

