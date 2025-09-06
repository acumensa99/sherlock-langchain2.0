import datetime

from peewee import CharField, AutoField, DateTimeField
from playhouse.postgres_ext import JSONField

from models.base import BaseModel


class ProductReviews(BaseModel):
    id = AutoField(primary_key=True)
    data_asin = CharField()
    reviews = JSONField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
