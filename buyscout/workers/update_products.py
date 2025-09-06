import asyncio
import os
import json
import time

from redis import Redis
from dotenv import load_dotenv
from models.product import Product
from db import db
from models.storefront import StoreFront

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
PRODUCT_LIST_KEY = os.getenv("REDIS_PRODUCT_LIST_KEY", "product_queue")

# Setup Redis connection
redis_conn = Redis.from_url(REDIS_URL)


# Helper to parse price string like "999." or "1,640."
def parse_price(price_str):
    try:
        return float(price_str.replace(",", "").replace(".", "").strip())
    except:
        return None


def load_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


def none_if_na(value):
    if isinstance(value, str) and value.strip().upper() == "NA":
        return None
    return value


def pull_batch_from_redis(redis_conn, key, batch_size=10):
    batch = []
    for _ in range(batch_size):
        raw = redis_conn.lpop(key)
        if raw:
            try:
                product_data = json.loads(raw)
                batch.append(product_data)
            except json.JSONDecodeError:
                continue  # skip invalid JSON
        else:
            break  # no more items
    return batch


def upsert_products(batch, batch_no):
    product_records = []
    for data in batch:
        asin = none_if_na(data.get("data_asin"))
        if not asin:
            continue
        product_records.append(Product(
            data_asin=asin,
            price=parse_price(none_if_na(data.get("price", "0"))),
            brand_name=none_if_na(data.get("brand_name")),
            delivery_time=none_if_na(data.get("delivery_time")),
            winning_seller=none_if_na(data.get("winning_seller")),
            seller_rating=float(none_if_na(data.get("seller_rating"))) if none_if_na(
                data.get("seller_rating")) else None,
            other_sellers=json.dumps(none_if_na(data.get("other_sellers")) or []),
            best_seller_rating=json.dumps(none_if_na(data.get("best_seller_rating")) or []),
            category=none_if_na(data.get("category")),
            pincode=none_if_na(data.get("pincode")),
            latitude=none_if_na(data.get("latitude")),
            longitude=none_if_na(data.get("longitude")),
            batch_no=batch_no
        ))
    if product_records:
        Product.bulk_create(product_records)


def add_products_to_db(json_data):
    storefront_records = []

    for store, store_data in json_data.items():
        for product in store_data.get("product_asins", []):
            asin = product.get("data_asin")
            price = parse_price(product.get("price", "0"))
            delivery_time = none_if_na(product.get("delivery_time"))
            if asin:
                storefront_records.append(
                    StoreFront(data_asin=asin, price=price, seller_name=store, delivery_time=delivery_time))
    if storefront_records:
        StoreFront.bulk_create(storefront_records)


async def run(sellername, batch_no):
    try:
        if db.is_closed():
            db.connect(reuse_if_open=True)

        db.create_tables([Product, StoreFront], safe=True)
        json_data = load_json_file(f'output/{sellername}_product_asins.json')
        add_products_to_db(json_data)
        while True:
            batch = pull_batch_from_redis(redis_conn, PRODUCT_LIST_KEY, batch_size=100)
            if not batch:
                print("Queue is empty. Continuing to listen...")
                await asyncio.sleep(5)
                break
            print(f"Processing batch of {len(batch)} products...")
            upsert_products(batch, batch_no=batch_no)
    except Exception as e:
        print(f"DB error: {e}")
    finally:
        if not db.is_closed():
            db.close()
# if __name__ == "__main__":
#     run()
