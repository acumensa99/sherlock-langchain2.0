import asyncio
from datetime import datetime
from time import sleep

from dotenv import load_dotenv

from asin_scrapper.single_asin_scrapper import process_asins
from models.queries import export_seller_data_to_excel
from products_lister.products_listing_scrapper import process_storefronts
import workers.update_products as update_products
import workers.email_sender as email_sender


async def run_full_flow(seller_name):
    batch_no = datetime.now().strftime("%Y%m%d%H%M%S")
    print(f"Running full flow for {seller_name} with batch no: {batch_no}")
    # # Step 1: Process storefronts
    # await process_storefronts(seller_name)
    # # #
    # # # # Step 2: Process ASINs for the given seller
    await process_asins(f'output/{seller_name}_product_asins.json', seller_name)
    # while True:
    #     try:
    #         await update_products.run(seller_name, batch_no=batch_no)
    #         break
    #     except Exception as e:
    #         sleep(15)
    #         print(f"Error in update_products: {e} Retrying")
    # Step 3: Export seller data to Excel
    # export_seller_data_to_excel(seller_name)
    # # #
    # # Step 4: Send email with the results
    # await email_sender.run(seller_name, f"{seller_name}_output.xlsx")


if __name__ == '__main__':
    load_dotenv()
    # asyncio.run(run_full_flow("RK World Infocom"))
    asyncio.run(run_full_flow("Clicktech Retail"))
    # asyncio.run(run_full_flow("Kuber Mart Industries Pvt. Ltd."))
    # asyncio.run(run_full_flow("Shadow Etail"))
    # asyncio.run(run_full_flow("HaloHop"))
    # run_full_flow("shilpa-sales")
    # run_full_flow("Cocoblu Retail")
    # asyncio.run(process_storefronts())
    # asyncio.run(process_asins('output/product_asins.json', 'Nine Ox'))
    # asyncio.run(process_asins('output/product_asins.json', 'Cocoblu Retail'))
    # asyncio.run(run("cocobluretail", "cocobluretail_output.xlsx"))
    # asyncio.run(update_products.run())
    # export_seller_data_to_excel("nineox")
    # print(get_seller_data("cocobluretail"))
    # data_string = get_seller_data("Happy Ecom")
    # run_inference(data_string)
