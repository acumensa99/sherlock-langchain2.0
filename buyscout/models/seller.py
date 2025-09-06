import datetime

from peewee import CharField, FloatField, AutoField, DateTimeField
from playhouse.postgres_ext import JSONField

from models.base import BaseModel


class Seller(BaseModel):
    id = AutoField(primary_key=True)
    seller_id = CharField(unique=True)
    seller_name = CharField()
    seller_rating = FloatField(null=True)
    seller_reviews_count = FloatField(null=True)
    seller_reviews = JSONField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
