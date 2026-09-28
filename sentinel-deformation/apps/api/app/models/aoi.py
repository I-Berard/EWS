from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry
import datetime

Base = declarative_base()

class AOI(Base):
    __tablename__ = 'aoi'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    geometry = Column(Geometry('POLYGON'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
