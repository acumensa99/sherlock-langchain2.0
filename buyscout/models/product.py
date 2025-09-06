import datetime

from peewee import CharField, FloatField, AutoField, DateTimeField, BigIntegerField
from playhouse.postgres_ext import JSONField

from models.base import BaseModel


class Product(BaseModel):
    id = AutoField(primary_key=True)
    batch_no = BigIntegerField(null=True)
    data_asin = CharField()
    price = FloatField(null=True)
    brand_name = CharField(null=True)
    delivery_time = CharField(null=True)
    winning_seller = CharField(null=True)
    seller_rating = FloatField(null=True)
    other_sellers = JSONField(null=True)
    best_seller_rating = JSONField(null=True)
    category = CharField(null=True)
    pincode = CharField(null=True)
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)
    created_at_p = DateTimeField(default=datetime.datetime.now)
