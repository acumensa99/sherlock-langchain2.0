# ⛔ DO THIS FIRST — before anything else
import asyncio
import os
import json
from redis.asyncio import Redis
from asin_scrapper.single_asin_scrapper import process_asins_dynamic

# Redis connection setup
#REDIS_URL = os.getenv("REDIS_URL", "redis://default:8UJi1DyhMTXKCC0cA8cKH9Bc3tzuwg7w@redis-17846.crce217.ap-south-1-1.ec2.redns.redis-cloud.com:17846")
REDIS_URL="redis://default:9ffZTAyl1KFYc9iQKUz215ieSqbHiSPU@redis-10281.crce179.ap-south-1-1.ec2.cloud.redislabs.com:10281"
CHANNEL_NAME = "process_asins_channel"

async def redis_listener():
    redis = Redis.from_url(REDIS_URL)
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL_NAME)

    print(f"Subscribed to Redis channel: {CHANNEL_NAME}")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                # Parse the message
                data = json.loads(message["data"])
                seller_name = data["seller_name"]
                product_asins = data["product_asins"]
                requested_at = data.get("requested_at", None)
                # Call the process_asins_dynamic function
                await process_asins_dynamic(
                    product_asins
                )
                print(f"Processed ASINs for seller: {seller_name}")
                #publish a completion message
                completion_message = {
                    "status": "completed",
                    "seller_name": seller_name,
                    "processed_asins": len(product_asins),
                    "requested_at": requested_at,
                }
                await redis.publish("process_asins_completion_channel", json.dumps(completion_message))
            except Exception as e:
                print(f"Error processing message: {e}")

if __name__ == "__main__":
    asyncio.run(redis_listener())
