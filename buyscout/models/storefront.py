import datetime

from peewee import CharField, FloatField, AutoField, DateTimeField
from models.base import BaseModel


class StoreFront(BaseModel):
    id = AutoField(primary_key=True)
    data_asin = CharField()
    price = FloatField(null=True)
    seller_name = CharField(null=True)
    delivery_time = CharField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
