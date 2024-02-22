import os
from typing import NoReturn
from enum import Enum
import time
import asyncio

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from database.dal import CollectionsDAL, TrackingDAL
from database.session import async_session, DBTransactionStatus
from bot import bot, gen_message, gen_markup, update_json, get_data_from_json

basedir = os.path.abspath(os.path.dirname(__file__))


class SortType(str, Enum):
    relevant = "collections"
    newest = "collections%2Fsort%2Fdeployed%3Adesc"
    # oldest = "collections%2Fsort%2Fdeployed%3Aasc"
    minted_recently = "collections%2Fsort%2FlastMintedAt%3Adesc"
    # highest_price = "collections%2Fsort%2Fcost%3Adesc"
    # lowest_price = "collections%2Fsort%2Fcost%3Aasc"


class Parser:
    __instance = None

    @classmethod
    def getInstance(cls):
        try:
            if not cls.__instance:
                cls.__instance = Parser()
            return cls.__instance
        except Exception as e:
            return e

    def __init__(self) -> NoReturn:
        if not Parser.__instance:
            self.__op = webdriver.FirefoxOptions()
            self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()))
            self.BASE_URL = None

    def close_parser(self) -> NoReturn:
        try:
            self.driver.quit()
            self.driver.close()
        except Exception as e:
            return e

    @staticmethod
    async def alert():
        async with async_session() as session:
            collection_dal = CollectionsDAL(session)
            tracking_dal = TrackingDAL(session)

            collections = await collection_dal.get_all()
            collections_href = list(map(lambda x: x.href, collections[0]))

            result = []
            data = get_data_from_json()

            for href in collections_href:
                output_data = await tracking_dal.calculate_sales_change(href=href, interval_minutes=data['alert_interval'])
                if output_data is not None:
                    if output_data[1] >= data['alert_percent']:
                        result.append(href)
                else:
                    pass

            output = []

            for href in result:
                collection = await collection_dal.get(href=href)
                output.append(collection)

            for collection in output:
                
                growth2 = await tracking_dal.calculate_sales_change(
                    href=collection.href,
                    interval_minutes=2
                )

                growth5 = await tracking_dal.calculate_sales_change(
                    href=collection.href,
                    interval_minutes=5
                )

                growth10 = await tracking_dal.calculate_sales_change(
                    href=collection.href,
                    interval_minutes=10
                )

                growth15 = await tracking_dal.calculate_sales_change(
                    href=collection.href,
                    interval_minutes=15
                )

                growth_alert = await tracking_dal.calculate_sales_change(
                    href=collection.href,
                    interval_minutes=data['alert_interval']
                )
                
                bot.send_message(
                    chat_id="@LMNFT",
                    text=f'''
⚠️ ALERT ⚠️
 Коллекция: <a href="{collection.href}">{collection.title}</a>
Alert growth: {growth_alert} for last {data['alert_interval']} min.
💯 Продано в процентах: {collection.sold_percentage}%
🛒 Продано: {collection.sold_stock}/{collection.total_stock} штук
📈 Прирост в (шт/%) за 2 минуты: {growth2[0] if growth2 is not None else 'n/a'} шт / {growth2[1] if growth2 is not None else 'n/a'}%
📈 Прирост в (шт/%) за 5 минут: {growth5[0] if growth5 is not None else 'n/a'} шт / {growth5[1] if growth5 is not None else 'n/a'}%
📈 Прирост в (шт/%) за 10 минут: {growth10[0] if growth10 is not None else 'n/a'} шт / {growth10[1] if growth10 is not None else 'n/a'}%
📈 Прирост в (шт/%) за 15 минут: {growth15[0] if growth15 is not None else 'n/a'} шт / {growth15[1] if growth15 is not None else 'n/a'}%
''',
                    parse_mode="html"
                )

    # https://launchmynft.io/explore?page=1&toggle%5BsoldOut%5D=False&toggle%5BtwitterVerified%5D=true&sortBy=collections%2Fsort%2Fdeployed%3Adesc
    @staticmethod
    def combine_url(
            soldOut: bool,
            twitterVerified: bool,
            sort_type: SortType
    ) -> str:
        BASE_URL = f"https://launchmynft.io/explore?toggle%5BsoldOut%5D={'true' if soldOut else 'false'}&toggle%5BtwitterVerified%5D={'true' if twitterVerified else 'false'}&sortBy={sort_type}"
        return BASE_URL

    async def parse_all_collections(self, parse_url: str) -> NoReturn:

        page = 0

        while True:
            page += 1

            self.driver.get(url=f"{parse_url}&page={page}")
            wait = WebDriverWait(self.driver, 10)

            infinity_scroll = wait.until(
                EC.presence_of_all_elements_located((
                    By.XPATH,
                    '//div[@class="infinite-scroll-component__outerdiv"]'
                )))

            a_tags = infinity_scroll[0].find_elements(By.XPATH, './/a[@style="overflow: hidden;"]')

            if a_tags:

                for a_tag in a_tags:
                    href = a_tag.get_attribute("href")

                    strong_tag = a_tag.find_elements(By.XPATH, './/strong')
                    collection_name = strong_tag[0].text

                    if collection_name == '':
                        continue

                    sold_percentage = strong_tag[1].text
                    sold_percentage = sold_percentage.split("%")
                    sold_percentage = sold_percentage[0]

                    stock = a_tag.find_elements(By.XPATH, './/span')

                    stock = stock[1].text.split("/")

                    sold_stock, total_stock = stock[0], stock[1]

                    print(f"Collection title: {collection_name}")
                    print(f"Link: {href}")
                    print(f"Sold percentage: {sold_percentage}%")
                    print(f"Sold: {sold_stock}")
                    print(f"Total: {total_stock}")
                    print("\n---------------------------\n")

                    async with async_session() as session:
                        collection_dal = CollectionsDAL(session)
                        tracking_dal = TrackingDAL(session)

                        status1 = await collection_dal.create(
                            href=href,
                            title=collection_name,
                            sold_percentage=float(sold_percentage),
                            total_stock=int(total_stock),
                            sold_stock=int(sold_stock)
                        )

                        status2 = await tracking_dal.create(href=href, sold_to_time=sold_stock)

                        if (status1 or status2) is not DBTransactionStatus.SUCCESS:
                            await bot.send_message(text="ошибка при создании или обновлении коллекций", chat_id="@LMNFT")
            else:
                break

    async def main(self):
        while True:
            for sort in SortType:
                url = self.combine_url(soldOut=False, twitterVerified=True, sort_type=sort.value)
                await self.parse_all_collections(parse_url=url)

                msg_editor = get_data_from_json()

                await self.alert()

                await bot.edit_message_text(
                    text=await gen_message(),
                    chat_id="@LMNFT",
                    message_id=msg_editor["message_to_edit"],
                    parse_mode="html"
                )
                await bot.edit_message_reply_markup(
                    chat_id="@LMNFT",
                    message_id=msg_editor["message_to_edit"],
                    reply_markup=gen_markup()
                )

            print("sleep 15 sec")
            time.sleep(15)


p = Parser()
asyncio.run(p.main())
