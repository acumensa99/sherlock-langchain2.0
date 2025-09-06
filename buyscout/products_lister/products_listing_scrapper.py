import asyncio
import csv
import json
import os
import time

from playwright_stealth import stealth_async
from playwright.async_api import async_playwright

from models.utils import get_init_page


async def scrape_storefront_in_tab(context, base_url, tab_index, last_page_count):
    product_asins = []
    page = await context.new_page()

    async def handle_route(route, request):
        if request.resource_type in ["image", "stylesheet", "font", "media"]:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", handle_route)
    page.set_default_timeout(500000)
    await stealth_async(page)

    for i in range(tab_index, last_page_count + 1, 8):
        page_url = base_url if i == 1 else base_url + f"&page={i}"
        await page.goto(page_url, wait_until='domcontentloaded')
        # print(f"Scraping page {i} of {last_page_count} in tab {tab_index}")
        items = await page.locator('//div[@role="listitem"]').all()
        count = len(items)  # Get total count
        # Loop through each item and print its "data-asin" attribute
        data_asins = []
        for item in items:
            data_asin = await item.get_attribute("data-asin")
            try:
                delivery_time = "NA"
                price = await item.locator(
                    "//span[@class='a-price-whole']").inner_text(timeout=5000)
                locator = item.locator(
                    "//span[contains(@aria-label, 'delivery')]//span[contains(@class, 'a-text-bold')]")
                if await locator.count() > 0:
                    # print(f"Delivery time found: {await locator.first.inner_text()}")
                    delivery_time = (await locator.first.inner_text()).strip().replace('\n', '').replace('\t', '')

            except Exception as e:
                price = 0
                delivery_time = "NA"
            product_asins.append({
                                     "data_asin": data_asin,
                                     "price": price,
                                     "delivery_time": delivery_time,
                                 } if data_asin else None)
            data_asins.append({
                                  "data_asin": data_asin,
                                  "price": price,
                                  "delivery_time": delivery_time,
                              } if data_asin else None)
        print(f"Found {count} products on page {i} in tab {tab_index}")
    await page.close()
    return product_asins


async def scrape_storefront(storefront_url):
    async with async_playwright() as p:
        page, browser, context = await get_init_page(p)

        await page.goto(storefront_url, wait_until='domcontentloaded')
        await page.reload()
        print(f"Scraping: {storefront_url}")
        # Wait for the element to appear
        await page.wait_for_selector('//span[text()="See all products"]')

        # Click the first <a> ancestor element
        await page.locator('//span[text()="See all products"]/ancestor::a[1]').click()
        # wait until the page is loaded
        await page.wait_for_load_state('load')
        try:
            last_page_count = int(await page.locator(
                '//span[@class="s-pagination-strip" and @aria-label="pagination"]//span[@class="s-pagination-item '
                's-pagination-disabled" and @aria-disabled="true"]').inner_text(timeout=5000))
        except:
            try:
                last_page_count = int(await page.locator(
                    "(//li[contains(@class, 's-list-item-margin-right-adjustment')])[last()-1]//a").inner_text(
                    timeout=5000))
            except:
                last_page_count = 1
        print(f"Total pages: {last_page_count}")
        await page.locator(
            "//a[.//div[contains(@class, 'a-checkbox')] and .//span[normalize-space()='Include Out of Stock']]").click()
        await page.wait_for_load_state('load')
        base_url = page.url
        await page.close()

        tasks = [scrape_storefront_in_tab(context, base_url, tab_index, last_page_count) for tab_index in range(1, 9)]
        results = await asyncio.gather(*tasks)

        product_asins = [asin for result in results for asin in result]

        await browser.close()
        return product_asins


async def process_storefronts(seller_name):
    os.makedirs("output", exist_ok=True)
    start_time = time.time()
    with open("input/storefronts.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        storefronts_data = {}
        for row in reader:
            storefront_url = row['storefronts']
            storename = row['storename']
            if seller_name and seller_name.lower() not in storename.lower():
                continue
            product_asins = await scrape_storefront(storefront_url)
            storefronts_data[storename] = {
                "url": storefront_url,
                "product_asins": product_asins
            }
            print(f"Found {len(product_asins)} products for {storefront_url}")

    with open(f"output/{seller_name}_product_asins.json", mode="w", encoding="utf-8") as jsonfile:
        json.dump(storefronts_data, jsonfile, indent=4)
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
