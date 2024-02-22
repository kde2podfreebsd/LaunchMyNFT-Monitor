import asyncio
import json
import math
import os
from datetime import datetime

from telebot.async_telebot import AsyncTeleBot
from telebot import types
from dotenv import load_dotenv

from database.dal import CollectionsDAL, TrackingDAL
from database.session import async_session, DBTransactionStatus

load_dotenv()

bot = AsyncTeleBot(str(os.getenv("BOT_TOKEN")))


def update_json(
        user_state: int = None,
        message_to_edit: int = None,
        items_per_page: int = None,
        total_pages: int = None,
        min_stock: int = None,
        sort_type: str = None,
        growth_sort_time_interval: int = None,
        alert_interval: int = None,
        alert_percent: int = None
):
    with open("msg_to_edit.json", 'r') as json_file:
        data = json.load(json_file)

    data['user_state'] = max(1, min(user_state if user_state is not None else data['user_state'], total_pages if total_pages is not None else data['total_pages'])) if user_state is not None else data['user_state']
    data['message_to_edit'] = message_to_edit if message_to_edit is not None else data['message_to_edit']
    data['items_per_page'] = items_per_page if items_per_page is not None else data['items_per_page']
    data['total_pages'] = total_pages if total_pages is not None else data['total_pages']
    data['min_stock'] = min_stock if min_stock is not None else data['min_stock']
    data['sort_type'] = sort_type if sort_type is not None else data['sort_type']
    data['growth_sort_time_interval'] = growth_sort_time_interval if growth_sort_time_interval is not None else data['growth_sort_time_interval']
    data['alert_interval'] = alert_interval if alert_interval is not None else data['alert_interval']
    data['alert_percent'] = alert_percent if alert_percent is not None else data['alert_percent']

    with open("msg_to_edit.json", 'w') as json_file:
        json.dump(data, json_file, indent=4)


def get_data_from_json() -> dict[str: int]:
    with open("msg_to_edit.json", 'r') as json_file:
        data = json.load(json_file)

    return data


async def gen_message():
    async with async_session() as session:
        collection_dal = CollectionsDAL(session)
        tracking_dal = TrackingDAL(session)

        data = get_data_from_json()

        sort_type = data['sort_type']

        print(f"SORT TYPE: {sort_type}")

        if sort_type == "by_stock":

            all_collections, status = await collection_dal.get_all()
            filtered_collections = [collection for collection in all_collections if collection.sold_percentage != 100]
            filtered_collections = [collection for collection in filtered_collections if collection.total_stock > data['min_stock']]
            sorted_filtered_collections = sorted(filtered_collections, key=lambda x: x.sold_percentage, reverse=True)

        elif sort_type == "by_growth":
            all_collections, status = await collection_dal.get_all()
            filtered_collections = [collection for collection in all_collections if collection.sold_percentage != 100]
            filtered_collections = [collection for collection in filtered_collections if collection.total_stock > data['min_stock']]
            filtered_collections = sorted(filtered_collections, key=lambda x: x.sold_percentage, reverse=True)

            with_change = {}
            without_change = {}

            for i in range(len(filtered_collections)):
                href = filtered_collections[i].href
                interval_minutes = data['growth_sort_time_interval']
                growth = await tracking_dal.calculate_sales_change(href=href, interval_minutes=interval_minutes)

                if growth is not None:
                    with_change[href] = growth[1]
                else:
                    without_change[href] = None

            sorted_with_change = dict(sorted(with_change.items(), key=lambda item: item[1], reverse=True))
            collections_without_change = [await collection_dal.get(href=href) for href in without_change.keys()]
            collections_without_change = sorted(collections_without_change, key=lambda x: x.sold_percentage, reverse=True)
            sorted_filtered_collections = [await collection_dal.get(href=href) for href in sorted_with_change.keys()]
            sorted_filtered_collections += collections_without_change

        update_json(total_pages=math.ceil(len(sorted_filtered_collections) / 10))

        if status == DBTransactionStatus.ROLLBACK or sorted_filtered_collections is None:
            return "Error retrieving collections."

        msg_editor = get_data_from_json()

        start_index = (msg_editor["user_state"] - 1) * msg_editor["items_per_page"]
        end_index = start_index + msg_editor["items_per_page"]

        message = f'''
⌛️ Last update: {datetime.now()}
Min stock: {msg_editor['min_stock']}
Alert interval(min)/percent(%): {msg_editor['alert_interval']}min / {msg_editor['alert_percent']}%
Sort type: {msg_editor['sort_type']}
'''
        if msg_editor['sort_type'] == 'by_growth':
            message += f'''Growth sort time interval: {msg_editor['growth_sort_time_interval']}'''

        for i in range(start_index, end_index):
            growth2 = await tracking_dal.calculate_sales_change(
                href=sorted_filtered_collections[i].href,
                interval_minutes=2
            )

            growth5 = await tracking_dal.calculate_sales_change(
                href=sorted_filtered_collections[i].href,
                interval_minutes=5
            )

            growth10 = await tracking_dal.calculate_sales_change(
                href=sorted_filtered_collections[i].href,
                interval_minutes=10
            )

            growth15 = await tracking_dal.calculate_sales_change(
                href=sorted_filtered_collections[i].href,
                interval_minutes=15
            )

            message += f'''
🔗 Коллекция: <a href="{sorted_filtered_collections[i].href}">{sorted_filtered_collections[i].title}</a>
💯 Продано в процентах: {sorted_filtered_collections[i].sold_percentage}%
🛒 Продано: {sorted_filtered_collections[i].sold_stock}/{sorted_filtered_collections[i].total_stock} штук
📈 Прирост в (шт/%) за 2 минуты: {growth2[0] if growth2 is not None else 'n/a'} шт / {growth2[1] if growth2 is not None else 'n/a'}%
📈 Прирост в (шт/%) за 5 минут: {growth5[0] if growth5 is not None else 'n/a'} шт / {growth5[1] if growth5 is not None else 'n/a'}%
📈 Прирост в (шт/%) за 10 минут: {growth10[0] if growth10 is not None else 'n/a'} шт / {growth10[1] if growth10 is not None else 'n/a'}%
📈 Прирост в (шт/%) за 15 минут: {growth15[0] if growth15 is not None else 'n/a'} шт / {growth15[1] if growth15 is not None else 'n/a'}%
\n
'''

# "Изменение за 15 минут: {absolute_change_15}штук/{percentage_change_15}%

        return message


def gen_markup():
    msg_editor = get_data_from_json()
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.row_width = 2
    markup.add(
        types.InlineKeyboardButton("⬅️ Back", callback_data="back"),
        types.InlineKeyboardButton("Next ➡️", callback_data="next"),
        types.InlineKeyboardButton("⬅️ Back 5", callback_data="back5"),
        types.InlineKeyboardButton("Next 5 ➡️", callback_data="next5"),
        types.InlineKeyboardButton(f"📄 Page: {msg_editor['user_state']} / {msg_editor['total_pages']}", callback_data="page"))
    return markup


async def send_message(chat_id: int | str, message: str):
    msg = await bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=gen_markup(),
        parse_mode='html'
    )

    return msg.id


@bot.callback_query_handler(func=lambda call: True)
async def HandlerInlineMiddleware(call):

    if "back" in call.data:
        msg_editor = get_data_from_json()

        if msg_editor['user_state'] > 1:
            update_json(user_state=msg_editor['user_state'] - 1 if call.data == "back" else msg_editor['user_state'] - 5)

            msg_editor = get_data_from_json()

            print(msg_editor['user_state'])
            if msg_editor['user_state'] < 1:
                update_json(user_state=1)

            await bot.edit_message_text(
                text=await gen_message(),
                chat_id=call.message.chat.id,
                message_id=msg_editor['message_to_edit'],
                parse_mode="html"
            )
            await bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=msg_editor['message_to_edit'],
                reply_markup=gen_markup()
            )
        else:
            await bot.answer_callback_query(call.id, text="Вы на первой странице")

    if "next" in call.data:
        msg_editor = get_data_from_json()
        if msg_editor['user_state'] < msg_editor['total_pages']:
            update_json(user_state=msg_editor['user_state'] + 1 if call.data == "next" else msg_editor['user_state'] + 5)

            msg_editor = get_data_from_json()
            if msg_editor['user_state'] > msg_editor['total_pages'] - 1:
                update_json(total_pages=msg_editor['total_pages'] - 1)

            await bot.edit_message_text(
                text=await gen_message(),
                chat_id=call.message.chat.id,
                message_id=msg_editor['message_to_edit'],
                parse_mode="html"
            )
            await bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=msg_editor['message_to_edit'],
                reply_markup=gen_markup()
            )
        else:
            await bot.answer_callback_query(call.id, text="Вы на последней странице")


@bot.message_handler(commands=["start"])
async def start(message) -> None:
    await bot.send_message(
        chat_id=message.chat.id,
        text='''
Команды:
/min_stock <b>min_value</b> - минимальная планка стока для сортировки
/by_stock - выбрать тип сортировки по кол-ву стока
/by_growth <b>sort_time_interval</b> - выбрать тип сортировки по приросту за указанный интервал
/alert <b>time_interval</b> <b>growth_percent%</b> - установить временной интервал и процентный прирост для алерта
''',
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="html"
    )


@bot.message_handler(commands=["alert"])
async def alert_interval(message) -> None:
    data = message.text.split(" ")
    if data[1] is not None and data[2] is not None:
        data[1] = int(data[1])
        data[2] = int(data[2])
        if isinstance(data[1], int) and isinstance(data[2], int):
            if data[1] < 2:
                await bot.send_message(chat_id=message.chat.id,
                                       text="Вы не можете установить временной интервал меньше 2 минут")

            elif data[2] < 1:
                await bot.send_message(chat_id=message.chat.id,
                                       text="Вы не можете установить процентный рост меньше 1%")

            else:
                update_json(alert_interval=data[1], alert_percent=data[2])

                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"Вы установили алерт на инетрвал {data[1]} минут с процентным ростом {data[2]}"
                )

                msg_editor = get_data_from_json()
                await bot.edit_message_text(
                    text=await gen_message(),
                    chat_id="@LMNFT",
                    message_id=msg_editor['message_to_edit'],
                    parse_mode="html"
                )
                await bot.edit_message_reply_markup(
                    chat_id="@LMNFT",
                    message_id=msg_editor['message_to_edit'],
                    reply_markup=gen_markup()
                )

        else:
            await bot.send_message(chat_id=message.chat.id, text="Не корректные значения")


@bot.message_handler(commands=["by_stock"])
async def by_stock(message) -> None:
    update_json(sort_type="by_stock")

    await bot.send_message(
        chat_id=message.chat.id,
        text="Выбран тип сортировки по кол-ву стока",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="html"
    )

    msg_editor = get_data_from_json()
    await bot.edit_message_text(
        text=await gen_message(),
        chat_id="@LMNFT",
        message_id=msg_editor['message_to_edit'],
        parse_mode="html"
    )
    await bot.edit_message_reply_markup(
        chat_id="@LMNFT",
        message_id=msg_editor['message_to_edit'],
        reply_markup=gen_markup()
    )


@bot.message_handler(commands=["by_growth"])
async def by_growth(message) -> None:
    data = message.text.split(" ")
    if data[1] is not None:
        data[1] = int(data[1])
        if isinstance(data[1], int):
            if data[1] < 2:
                await bot.send_message(chat_id=message.chat.id, text="Вы не можете установить временной интервал меньше 2 минут")
            else:
                update_json(growth_sort_time_interval=data[1], sort_type="by_growth")

                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"Выбран тип сортировки по приросту минтов за интервал: {data[1]} минут"
                )

                msg_editor = get_data_from_json()
                await bot.edit_message_text(
                    text=await gen_message(),
                    chat_id="@LMNFT",
                    message_id=msg_editor['message_to_edit'],
                    parse_mode="html"
                )
                await bot.edit_message_reply_markup(
                    chat_id="@LMNFT",
                    message_id=msg_editor['message_to_edit'],
                    reply_markup=gen_markup()
                )

        else:
            await bot.send_message(chat_id=message.chat.id, text="Не корректное значение")


@bot.message_handler(commands=["min_stock"])
async def min_stock(message) -> None:
    data = message.text.split(" ")
    if data[1] is not None:
        data[1] = int(data[1])
        if isinstance(data[1], int):
            if data[1] < 1:
                await bot.send_message(chat_id=message.chat.id, text="Вы не можете установить значение меньше 1")
            else:
                update_json(min_stock=data[1])

                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"Минимальная планка установлена на значение {data[1]}"
                )

                msg_editor = get_data_from_json()
                await bot.edit_message_text(
                    text=await gen_message(),
                    chat_id="@LMNFT",
                    message_id=msg_editor['message_to_edit'],
                    parse_mode="html"
                )
                await bot.edit_message_reply_markup(
                    chat_id="@LMNFT",
                    message_id=msg_editor['message_to_edit'],
                    reply_markup=gen_markup()
                )

        else:
            await bot.send_message(chat_id=message.chat.id, text="Не корректное значение")


async def send_first_message():
    data = get_data_from_json()
    try:
        await bot.delete_message(chat_id="@LMNFT", message_id=data['message_to_edit'])
    except Exception:
        pass
    msg_id = await send_message(chat_id="@LMNFT", message=await gen_message())
    update_json(message_to_edit=msg_id)


async def polling():
    task1 = asyncio.create_task(bot.infinity_polling())
    await task1


async def main():
    await send_first_message()
    await polling()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
