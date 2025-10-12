from fastmcp import FastMCP
import json
import logging
from datetime import datetime
from redis.asyncio import from_url  # using redis-py asyncio
import httpx
REDIS_URL = "redis://default:8UJi1DyhMTXKCC0cA8cKH9Bc3tzuwg7w@redis-17846.crce217.ap-south-1-1.ec2.redns.redis-cloud.com:17846"
CHANNEL = "process_asins_channel"
COMPLETION_CHANNEL = "process_asins_completion_channel"
logging.basicConfig(level=logging.DEBUG)
mcp = FastMCP("AmazonBuyBoxScraper")


# @mcp.tool
# def add(a: int, b: int) -> int:
#     """Add two numbers"""
#     return a + b


@mcp.tool()
async def scrape_asins(seller_name: str, product_asins: list[str], topicId: str, userId: str) -> dict:
    """
    Publishes a message to Redis pub/sub for ASIN scraping.
    """



    if not seller_name or not isinstance(product_asins, list):
        raise ValueError("seller_name must be a string and product_asins must be a list of strings.")
    time_id = datetime.utcnow().isoformat() + "Z"
    payload = {
        "seller_name": seller_name,
        "product_asins": product_asins,
        "requested_at": time_id
    }

    redis = from_url(REDIS_URL)
    try:
        await redis.publish(CHANNEL, json.dumps(payload))
        logging.info("Published to Redis channel '%s': %s", CHANNEL, payload)
        # add push a pubsub in the notif changel of redis containing the topic and queue
        notif_payload = {
            "topicId": topicId,
            "userId": userId,
            "channel": "SCRAPING",
            "status": "Task Queued"
        }
        await redis.publish("notif_channel", json.dumps(notif_payload))
    finally:
        await redis.close()
    try:
        # Publish message


        # Subscribe to completion channel
        pubsub = redis.pubsub()
        await pubsub.subscribe(COMPLETION_CHANNEL)
        logging.info("Subscribed to channel: %s", COMPLETION_CHANNEL)
        logging.info("Waiting for completion message...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                logging.info("Received completion message: %s", data)

                # Example completion format check
                if data.get("status") == "completed" and data.get("requested_at") == time_id:
                    logging.info("Processing complete for seller: %s, ASINs processed: %s",
                                 data.get("seller_name"), data.get("processed_asins"))
                    #get all the data from redis list product_queue
                    try:
                        # LRANGE list_name 0 -1 gets all elements
                        items = await redis.lrange("product_queue", 0, -1)
                        decoded_items = [item.decode('utf-8') for item in items]
                        #delete the list after processing
                        await redis.delete("product_queue")
                        print("Items in product_queue:", decoded_items)
                        notif_payload = {
                            "topicId": topicId,
                            "userId": userId,
                            "channel": "SCRAPING",
                            "status": "Task Completed"
                        }
                        await redis.publish("notif_channel", json.dumps(notif_payload))
                        return {"status": "Completed", "channel": CHANNEL, "payload": decoded_items}
                    finally:
                        await redis.close()

                    break

    finally:
        await pubsub.unsubscribe(COMPLETION_CHANNEL)
        await pubsub.close()
        await redis.close()



    logging.info("Published to Redis: %s", payload)
    return {"status": "Triggered", "channel": CHANNEL, "payload": payload}


# @mcp.tool()
# async def scrape_asins(seller_name: str, product_asins: list[str]) -> dict:
#     """
#     Scrapes amazon product triggers Bright Data API.
#     """
#     if not seller_name or not isinstance(product_asins, list):
#         raise ValueError("seller_name must be a string and product_asins must be a list of strings.")
#
#     # Construct URLs from ASINs
#     urls = [f"https://www.amazon.in/dp/{asin}" for asin in product_asins]
#
#     # Prepare payload for Bright Data API
#     payload = [{"url": url, "zipcode": "734006", "language": "EN"} for url in urls]
#
#     # Bright Data API endpoint and headers
#     api_url = "https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_l7q7dkf244hwjntr0&include_errors=true"
#     headers = {
#         "Authorization": "Bearer 6fe958505b7364ef8d54f9515b360be6ad2bbf2a01d7beea1ad4e862ceed314d",
#         "Content-Type": "application/json"
#     }
#
#     async with httpx.AsyncClient() as client:
#         response = await client.post(api_url, json=payload, headers=headers)
#         response.raise_for_status()  # Raise exception for HTTP errors
#         return response.json()


if __name__ == "__main__":
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=8001,
        log_level="debug"
    )
