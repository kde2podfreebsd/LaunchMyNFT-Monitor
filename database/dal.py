from psycopg2 import IntegrityError
from sqlalchemy.future import select
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Collections, Tracking
from typing import Union, Tuple, List
from datetime import datetime, timedelta

from database.session import DBTransactionStatus


class CollectionsDAL:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(
            self,
            href: str,
            title: str,
            sold_percentage: float,
            total_stock: int,
            sold_stock: int
    ):
        existing_collection = await self.db_session.execute(
            select(Collections).where(and_(Collections.href == href))
        )

        existing_collection = existing_collection.scalars().first()

        if existing_collection:
            existing_collection.sold_stock = sold_stock
            existing_collection.sold_percentage = sold_percentage

            try:
                await self.db_session.flush()
                return DBTransactionStatus.SUCCESS

            except IntegrityError as e:
                await self.db_session.rollback()
                return DBTransactionStatus.ROLLBACK

        new_collection = Collections(
            href=href,
            title=title,
            sold_percentage=sold_percentage,
            total_stock=total_stock,
            sold_stock=sold_stock
        )

        self.db_session.add(new_collection)

        try:
            await self.db_session.commit()
            return DBTransactionStatus.SUCCESS

        except IntegrityError as e:
            await self.db_session.rollback()
            return DBTransactionStatus.ROLLBACK

    async def get_all(self):
        try:
            result = await self.db_session.execute(select(Collections))
            collections = result.scalars().all()
            return collections, DBTransactionStatus.SUCCESS

        except Exception as e:
            await self.db_session.rollback()
            return None, DBTransactionStatus.ROLLBACK

    async def get(self, href: str):
        existing_collection = await self.db_session.execute(
            select(Collections).where(and_(Collections.href == href))
        )

        existing_collection = existing_collection.scalars().first()

        return existing_collection



class TrackingDAL:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(
            self,
            href: str,
            sold_to_time: int
    ) -> DBTransactionStatus:

        new_tracking = Tracking(
            time=datetime.now(),
            sold_to_time=int(sold_to_time)
        )

        existing_collection = await self.db_session.execute(
            select(Collections).where(Collections.href == href)
        )
        existing_collection = existing_collection.scalars().first()

        if not existing_collection:
            return DBTransactionStatus.NOT_EXIST

        new_tracking.collection = existing_collection

        self.db_session.add(new_tracking)

        try:
            await self.db_session.commit()
            return DBTransactionStatus.SUCCESS
        except IntegrityError as e:
            await self.db_session.rollback()
            return DBTransactionStatus.ROLLBACK

    async def calculate_sales_change(
            self,
            href: str,
            interval_minutes: int
    ) -> Union[None, Tuple[int, float]]:
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=interval_minutes)

        collection = await self.db_session.execute(
            select(Collections).where(Collections.href == href)
        )
        collection = collection.scalars().first()

        if not collection:
            return None

        start_tracking = await self.db_session.execute(
            select(Tracking)
            .filter(Tracking.collection == collection)
            .filter(Tracking.time >= start_time)
            .filter(Tracking.time <= end_time)
            .order_by(Tracking.time)
            .limit(1)
        )
        start_tracking = start_tracking.scalars().first()

        end_tracking = await self.db_session.execute(
            select(Tracking)
            .filter(Tracking.collection == collection)
            .filter(Tracking.time <= end_time)
            .order_by(Tracking.time.desc())
            .limit(1)
        )
        end_tracking = end_tracking.scalars().first()

        if not start_tracking or not end_tracking:
            return None

        absolute_change = end_tracking.sold_to_time - start_tracking.sold_to_time
        percentage_change = (
                                        absolute_change / start_tracking.sold_to_time) * 100 if start_tracking.sold_to_time != 0 else 0

        return absolute_change, percentage_change