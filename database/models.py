from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base


class Collections(Base):
    __tablename__ = 'collection'

    id = Column(Integer(), primary_key=True)
    href = Column(String(), nullable=False, unique=True)
    title = Column(String(), nullable=False, unique=False)
    sold_percentage = Column(Float())
    total_stock = Column(Integer())
    sold_stock = Column(Integer())

    tracking = relationship("Tracking", back_populates="collection")


class Tracking(Base):
    __tablename__ = 'tracking'

    id = Column(Integer(), primary_key=True)
    time = Column(DateTime)
    sold_to_time = Column(Integer())

    collection_href = Column(String(), ForeignKey('collection.href'))
    collection = relationship("Collections", back_populates="tracking")
