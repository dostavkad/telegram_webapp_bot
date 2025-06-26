
from contextlib import suppress
import logging
import json
import os
from datetime import datetime, date, timedelta
import aiocron
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.utils.callback_data import CallbackData
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ✅ Загружаем переменные окружения
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
OPERATOR_ID = 611617181

# ✅ Создаём экземпляры бота и диспетчера только один раз
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ✅ CallbackData после создания Dispatcher
reply_cb = CallbackData("reply", "client_id")
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

@aiocron.crontab('0 0 * * *')
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

    updated_data = [o for o in data if o.get("status") != "доставлено"]
    with open("orders.json", "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)

@dp.message_handler(Text(equals="📊 Отчёт"))
async def report_button_handler(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return

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
    kb.add(KeyboardButton(text="🛍 Список продуктов", web_app=WebAppInfo(url="https://cedar-absorbing-oriole.glitch.me/")))
    kb.add(KeyboardButton("📞 Поддержка"))
    if message.from_user.id == ADMIN_CHAT_ID:
        kb.add(KeyboardButton("📊 Отчёт"))

    await message.answer(
        "👋 Добро пожаловать в ваш продуктовый магазин!\n\n"
        "🚜 ДОСТАВКА ПРЯМО С ДЕХКАНСКОГО ОПТОВОГО БАЗАРА\n"
        "💸 Дешевле, чем в магазине\n"
        "🏡 Не выходя из дома — заказывайте и ЭКОНОМЬТЕ уже сегодня!\n\n"
        "🛍 Нажмите кнопку *Список продуктов*, чтобы выбрать товары или 📸Вы можете отправлять список продуктов или фото прямо сюда — мы быстро оформим заказ! ",
        reply_markup=kb,
        parse_mode='Markdown'
    )
@dp.message_handler(lambda message: message.chat.id == OPERATOR_ID)
async def operator_message_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    client_id = data.get("reply_client_id")

    if client_id:
        try:
            await bot.send_message(client_id, f"📨 Сообщение от оператора:\n{message.text}")
            await message.answer("✅ Отправлено клиенту.")
            await state.finish()
            return
        except:
            await message.answer("❌ Не удалось отправить клиенту.")
            return

    if message.reply_to_message and "ID:" in message.reply_to_message.text:
        try:
            text = message.reply_to_message.text
            client_id = int(text.split("ID:")[1].split()[0].strip())
            await bot.send_message(client_id, f"📨 Сообщение от оператора:\n{message.text}")
            await message.answer("✅ Отправлено клиенту.")
            return
        except:
            await message.answer("❌ Не удалось отправить клиенту.")
            return

    await message.answer("ℹ️ Сначала нажмите кнопку 'Ответить' под сообщением клиента или ответьте на сообщение, где есть ID.")

@dp.callback_query_handler(reply_cb.filter())
async def handle_reply_button(query: types.CallbackQuery, callback_data: dict):
    client_id = int(callback_data["client_id"])
    state = dp.current_state(user=query.from_user.id)
    await state.update_data(reply_client_id=client_id)
    await bot.send_message(query.from_user.id, "✍️ Напишите сообщение, которое хотите отправить клиенту.")
    await query.answer()

@dp.message_handler(Text(equals="📞 Поддержка"))
async def support_handler(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(text="🛍 Список продуктов", web_app=WebAppInfo(url="https://cedar-absorbing-oriole.glitch.me/")))
    kb.add(KeyboardButton("📞 Поддержка"))
    await message.answer(
        "📞 <b>Поддержка</b>\n"
        "Телефон: <a href='tel:+998(97)111-24-24'>+998 97 111 24 24</a>\n"
        "Telegram: <a href='https://t.me/jamshwdovich_8'>@jamshwdovich_8</a>"
        "🧑‍💬 <b>Вы также можете написать прямо сюда</b> — оператор ответит вам в этом чате.",
        parse_mode='HTML'
    )


@dp.message_handler(content_types=types.ContentType.WEB_APP_DATA)
async def webapp_data_handler(message: types.Message):
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    try:
        data = json.loads(message.web_app_data.data)
        order_text = data.get("text")
        order_id = data.get("order_id")
        client_id = data.get("client_id") or message.from_user.id
        markup = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("✅ Оплачено", callback_data=status_cb.new(action="оплачено", order_id=order_id, client_id=client_id)),
            InlineKeyboardButton("🚗 В пути", callback_data=status_cb.new(action="в_пути", order_id=order_id, client_id=client_id)),
            InlineKeyboardButton("📦 Доставлено", callback_data=status_cb.new(action="доставлено", order_id=order_id, client_id=client_id))
        )
        await bot.send_message(chat_id='611617181', text=order_text, parse_mode="Markdown", reply_markup=markup)
        await bot.send_message(chat_id=client_id, text=f"📦 *Ваш заказ принят!*\n📲 *Скоро мы свяжемся с вами!*\n\n{order_text}", parse_mode="Markdown")
        save_order(data)
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке заказа: {e}")

@dp.callback_query_handler(status_cb.filter())
async def status_handler(query: types.CallbackQuery, callback_data: dict):
    status = callback_data['action']
    order_id = callback_data['order_id']
    client_id = int(callback_data['client_id'])
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
    status_texts = {
        'оплачено': '✅ Ваш заказ #{} оплачен.',
        'в_пути': '🚗 Ваш заказ #{} в пути.',
        'доставлено': '📦 Ваш заказ #{} доставлен. Спасибо за покупку!'
    }
    message = status_texts.get(status, '📦 Статус обновлён').format(order_id)
    await bot.send_message(chat_id=client_id, text=message)
    await query.answer(f"Статус заказа обновлён: {status}")

@dp.message_handler(lambda message: message.chat.id != OPERATOR_ID and message.web_app_data is None, content_types=types.ContentTypes.ANY)
async def forward_to_operator(message: types.Message):
    try:
        # 🟢 Сообщение клиенту
        await message.answer("✅ Ваше сообщение принято.\n⏳ Пожалуйста, дождитесь ответа оператора.")
        
        user = message.from_user
        caption = (
            f"✉️ {user.full_name} (@{user.username})\n"
            f"🆔 ID: {user.id}\n\n"
        )

        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✉️ Ответить", callback_data=reply_cb.new(client_id=user.id))
        )

        if message.text:
            await bot.send_message(OPERATOR_ID, caption + message.text, reply_markup=markup)
        elif message.photo:
            photo = message.photo[-1].file_id
            await bot.send_photo(OPERATOR_ID, photo=photo, caption=caption + (message.caption or ""), reply_markup=markup)
        elif message.voice:
            await bot.send_voice(OPERATOR_ID, message.voice.file_id, caption=caption, reply_markup=markup)
        elif message.video:
            await bot.send_video(OPERATOR_ID, message.video.file_id, caption=caption + (message.caption or ""), reply_markup=markup)
        elif message.document:
            await bot.send_document(OPERATOR_ID, message.document.file_id, caption=caption + (message.caption or ""), reply_markup=markup)
        elif message.location:
            await bot.send_message(OPERATOR_ID, caption + "📍 Геолокация клиента:", reply_markup=markup)
            await bot.send_location(OPERATOR_ID, latitude=message.location.latitude, longitude=message.location.longitude)
        elif message.video_note:
            await bot.send_video_note(OPERATOR_ID, message.video_note.file_id)
        else:
            await bot.send_message(OPERATOR_ID, caption + "📎 Сообщение клиента (неподдерживаемый тип)", reply_markup=markup)

    except Exception as e:
        logging.error(f"Ошибка при пересылке сообщения оператору: {e}")


if __name__ == "__main__":
    from aiogram import executor
    from handlers import dp  # ❌ удалить это

    async def on_startup(dp):
        await bot.set_webhook(WEBHOOK_URL)

    async def on_shutdown(dp):
        await bot.delete_webhook()

    executor.start_webhook(
        dispatcher=dp,
        webhook_path="/",
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host="0.0.0.0",  # Render требует это!
        port=int(os.environ.get("PORT", 8080))  # Render сам задаёт PORT
    )

