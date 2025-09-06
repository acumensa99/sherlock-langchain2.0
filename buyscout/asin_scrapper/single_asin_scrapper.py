import asyncio
import json
import os
import time
import re
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from redis import Redis

from models.utils import get_init_page, get_lat_lon_from_pincode

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")

print(f"Redis URL: {REDIS_URL}")
PRODUCT_LIST_KEY = os.getenv("REDIS_PRODUCT_LIST_KEY", "product_queue")
redis_conn = Redis.from_url(REDIS_URL)


async def open_product_page(context, data_asin, tab_index, pincode="751024", latitude=None, longitude=None):
    try:
        # await context.set_cache_enabled(True)
        page = await context.new_page()

        # async def handle_route(route, request):
        #     # Block unnecessary resources like stylesheets, fonts, and media
        #     if request.resource_type in ["stylesheet", "font", "media"]:
        #         await route.abort()
        #     elif any(domain in request.url for domain in ["google", "facebook", "doubleclick"]):
        #         await route.abort()
        #     # Allow images only if they are from the 'media-amazon' domain
        #     elif request.resource_type == 'image' and 'media-amazon' in request.url:
        #         await route.continue_()
        #
        #     # Block other images
        #     elif request.resource_type == 'image':
        #         await route.abort()
        #
        #     # Continue with other resources like scripts, documents, etc.
        #     else:
        #         await route.continue_()

        # await page.route("**/*", handle_route)
        page.set_default_timeout(30000)
        product_url = f"https://www.amazon.in/dp/{data_asin}"
        await page.goto(product_url, wait_until='load')

        print(f"Opened product page for ASIN: {data_asin} in tab {tab_index}")
        # check if captcha page opens
        if await page.locator(
                "//h4[contains(text(), 'Enter the characters you see below')]").count() > 0:
            print("Captcha page opened. Reloading...")
            await page.reload()
        locator = page.locator("//div[@id='corePrice_feature_div']//span[contains(@class, 'a-price-whole')]")
        if tab_index < 5:
            print("Reloading for tab less than 13.")
            await page.reload()
        if tab_index < 2:
            await page.wait_for_load_state('load')
            await page.click("#nav-global-location-popover-link")
            await page.fill("input#GLUXZipUpdateInput", pincode)
            await page.wait_for_timeout(1000)
            await page.click("span#GLUXZipUpdate")
            await page.wait_for_timeout(1000)
            await page.wait_for_selector("span#GLUXZipUpdate", state="hidden")
            # await page.press("input#GLUXZipUpdateInput", "Enter")
            await page.wait_for_load_state('load')
        if await locator.count() > 0:
            price = (await locator.first.inner_text()).strip().replace('\n', '').replace('\t', '')
        else:
            price = "NA"
        locator = page.locator("//div[@id='wayfinding-breadcrumbs_feature_div']//a[1]")
        if await locator.count() > 0:
            category = (await locator.first.inner_text()).strip().replace('\n', '').replace('\t', '')
        else:
            category = "NA"
        locator = page.locator("//span[@data-csa-c-delivery-time]")
        if await locator.count() > 0:
            delivery_time = await locator.first.get_attribute("data-csa-c-delivery-time")
        else:
            delivery_time = "NA"
        locator = page.locator("//div[@id='merchantInfoFeature_feature_div']//a[@id='sellerProfileTriggerId']")
        if await locator.count() > 0:
            winning_seller = await locator.first.inner_text()
        else:
            winning_seller = "NA"
        locator = page.locator("//span[@class='a-size-base a-color-base' and @aria-hidden='true']")
        if await locator.count() > 0:
            seller_rating = await locator.first.inner_text()
        else:
            seller_rating = "NA"
        locator = page.locator(
            "//div[contains(@class, 'brand-snapshot-card-container')]//span[contains(@class, 'a-size-medium') and "
            "contains(@class, 'a-text-bold')]")
        if await locator.count() > 0:
            brand_name = await locator.first.inner_text()
        else:
            brand_name = "NA"
        content = await page.inner_text("body")

        # Extract the rank info using regex
        matches = re.findall(r'#([\d,]+)\s+in\s+([^\n(]+)', content)
        seen = set()
        best_seller_rating = []
        if matches:
            for rank_str, category in matches:
                rank = int(rank_str.replace(",", ""))
                key = (rank, category.strip())
                if key not in seen:
                    best_seller_rating.append({
                        "rank": rank,
                        "category": category.strip()
                    })
                    seen.add(key)
        print(f"best_seller_rating info: {best_seller_rating}")
        other_sellers = []
        while True:
            try:
                locator = page.locator("//div[@id='olpLinkWidget_feature_div']//a[@class='a-link-normal']")
                if await locator.count() > 0:
                    await locator.scroll_into_view_if_needed()
                    await locator.first.click()
                    print("Clicked on the other sellers link. in tab ", tab_index)
                    await page.wait_for_selector("//div[@id='aod-offer-list']", timeout=10000)
                    offers = await page.locator("//div[@id='aod-offer-list']//div[@id='aod-offer']").all()
                    print(f"Found {len(offers)} offers.")
                    for offer in offers:
                        offer_price = (await offer.locator("//span[@class='a-price-whole']").inner_text()).strip().replace(
                            '\n', '').replace('\t', '')
                        offer_seller = await offer.locator(
                            "//div[@id='aod-offer-soldBy']//a[contains(@class, 'a-link-normal') and contains(@class, 'a-size-small')]").inner_text()
                        offer_seller_rating = offer.locator(
                            "//div[@id='aod-offer-seller-rating']//span[contains(@class, 'a-icon-alt')]")
                        if await offer_seller_rating.count() > 0:
                            offer_seller_rating = await offer_seller_rating.first.inner_text()
                        else:
                            offer_seller_rating = "NA"
                        data = {
                            "offer_price": offer_price,
                            "offer_seller": offer_seller,
                            "offer_seller_rating": offer_seller_rating
                        }
                        other_sellers.append(data)

                else:
                    other_sellers = []
                    print("No other sellers found.")
                break
            except Exception as e:
                print(f"Error while scraping other sellers: {e}, Reloading the page...")
                await page.reload()
                await page.wait_for_load_state('load')
                other_sellers = []
    except Exception as e:
        print(f"Error while scraping product page: {e}")
        price = "NA"
        brand_name = "NA"
        delivery_time = "NA"
        winning_seller = "NA"
        seller_rating = "NA"
        other_sellers = []
        best_seller_rating = []
        category = "NA"
    data = {
        "data_asin": data_asin,
        "price": price,
        "brand_name": brand_name,
        "delivery_time": delivery_time,
        "winning_seller": winning_seller,
        "seller_rating": seller_rating,
        "other_sellers": other_sellers,
        "best_seller_rating": best_seller_rating,
        "category": category,
        "pincode": pincode,
        "latitude": latitude,
        "longitude": longitude


    }
    print(f"Scraped data: {data} in tab {tab_index}")
    redis_conn.rpush(PRODUCT_LIST_KEY, json.dumps(data))
    await page.close()
    return data


async def process_asins(file_path, key):
    # Setup Redis connection

    os.makedirs("output", exist_ok=True)
    start_time = time.time()
    pincode_list = [
        "110001",
        # "600001",
        # "700001",
        "400001",
        # "462001"
    ]
    for pincode1 in pincode_list:
        latitude1, longitude1 = get_lat_lon_from_pincode(pincode1)
        print(f"Latitude: {latitude1}, Longitude: {longitude1} for pincode {pincode1}")
        async with async_playwright() as p:
            page, browser, context = await get_init_page(p, latitude1, longitude1)

            with open(file_path, 'r', encoding='utf-8') as file:

                data = json.load(file)
                product_asins = data[key]['product_asins']
                semaphore = asyncio.Semaphore(9)
                tasks = []

                async def sem_open_product_page(data_asin, tab_index, pincode, latitude, longitude):
                    async with semaphore:
                        return await open_product_page(context, data_asin, tab_index, pincode, latitude, longitude)

                for tab_index, product in enumerate(product_asins):
                    if product:
                        tasks.append(
                            sem_open_product_page(product['data_asin'], tab_index, pincode1, latitude1, longitude1))
                products_data = await asyncio.gather(*tasks)

            with open(f"output/{key}_products_data.json", mode="w", encoding="utf-8") as jsonfile:
                json.dump(products_data, jsonfile, indent=4)
            end_time = time.time()
            print(f"Time taken: {end_time - start_time} seconds")
            await browser.close()


async def process_asins_dynamic(product_asins):
    # Setup Redis connection

    os.makedirs("output", exist_ok=True)
    start_time = time.time()
    pincode_list = [
        "110001",
        # "600001",
        # "700001",
        # "400001",
        # "462001"
    ]
    for pincode1 in pincode_list:
        latitude1, longitude1 = get_lat_lon_from_pincode(pincode1)
        print(f"Latitude: {latitude1}, Longitude: {longitude1} for pincode {pincode1}")
        async with async_playwright() as p:
            page, browser, context = await get_init_page(p, latitude1, longitude1)
            # product_asins = data[key]['product_asins']
            semaphore = asyncio.Semaphore(9)
            tasks = []

            async def sem_open_product_page(data_asin, tab_index, pincode, latitude, longitude):
                async with semaphore:
                    return await open_product_page(context, data_asin, tab_index, pincode, latitude, longitude)

            for tab_index, product in enumerate(product_asins):
                if product:
                    tasks.append(
                        sem_open_product_page(product, tab_index, pincode1, latitude1, longitude1))
            products_data = await asyncio.gather(*tasks)

            # with open(f"output/{key}_products_data.json", mode="w", encoding="utf-8") as jsonfile:
            #     json.dump(products_data, jsonfile, indent=4)
            end_time = time.time()
            print(f"Time taken: {end_time - start_time} seconds")
            await browser.close()
