import json
import re
from datetime import datetime

import dateparser
import pandas as pd
from peewee import fn, Case, Value

from models.product import Product
from models.storefront import StoreFront


def get_winning_and_loosing_asin_count(normalized_product_seller, normalized_storefront_seller):
    query = (Product
             .select(
        fn.COUNT(Case(None, [(normalized_product_seller == normalized_storefront_seller, 1)])).alias('matching_count'),
        fn.COUNT(Case(None, [(normalized_product_seller != normalized_storefront_seller, 1)])).alias(
            'non_matching_count'))
             .join(StoreFront, on=(Product.data_asin == StoreFront.data_asin))
             .group_by(StoreFront.data_asin, Product.pincode)
             )
    result = query.dicts().get()
    print("Matching :", result['matching_count'])
    print("Non-Matching:", result['non_matching_count'])
    return result['matching_count'], result['non_matching_count']


def get_lost_due_to_price_count(normalized_product_seller, normalized_storefront_seller):
    query = (Product.select(fn.COUNT(Product.id).alias('lower_price_count')).join(StoreFront, on=(
            Product.data_asin == StoreFront.data_asin))
    .group_by(StoreFront.data_asin, Product.pincode).where(
        (normalized_product_seller != normalized_storefront_seller) &
        (Product.price < StoreFront.price)))

    result = query.dicts().get()
    print("🟡 Non-matching where other seller has lower price:", result['lower_price_count'])
    return result['lower_price_count']


def get_lost_due_to_delivery_speed_count(normalized_product_seller, normalized_storefront_seller):
    query = (Product.select(fn.COUNT(Product.id).alias('faster_delivery_count')).join(StoreFront, on=(
            Product.data_asin == StoreFront.data_asin))
    .group_by(StoreFront.data_asin, Product.pincode).where(
        (normalized_product_seller != normalized_storefront_seller) &
        (fn.REPLACE(fn.LOWER(Product.delivery_time), ' ', '') < fn.REPLACE(fn.LOWER(StoreFront.delivery_time), ' ',
                                                                           ''))))

    result = query.dicts().get()
    print("🟡 Non-matching where other seller has faster delivery:", result['faster_delivery_count'])
    return result['faster_delivery_count']


def normalize(s):
    return re.sub(r'[^a-z0-9]', '', s.lower()) if s else ''


def get_lost_due_to_rating_count(normalized_seller_name):
    happy_lost_due_to_rating = 0
    total_checked = 0

    # Filter only products where the target seller is in other_sellers, but is not the winner
    candidate_products = Product.select().where(
        fn.LOWER(fn.REPLACE(fn.REPLACE(Product.winning_seller, ' ', ''), '.', '')) != normalized_seller_name,
        Product.other_sellers.is_null(False)
    )

    print(f"🔍 Products to inspect: {candidate_products.count()}")

    for row in candidate_products:
        try:
            other_sellers = json.loads(row.other_sellers or '[]')
            target_offer = next(
                (s for s in other_sellers if normalized_seller_name in normalize(s.get('offer_seller'))),
                None
            )

            if not target_offer:
                continue

            # Clean and parse offer price
            happy_price = float(target_offer.get("offer_price", "").replace(",", "").replace("₹", "").strip())
            winning_price = row.price
            happy_rating = None

            # Extract numeric rating
            rating_text = target_offer.get("offer_seller_rating", "").lower()
            if "out of" in rating_text:
                parts = rating_text.split("out of")
                try:
                    happy_rating = float(parts[0].split()[-1])
                except ValueError:
                    pass

            if happy_price <= winning_price and happy_rating is not None and row.seller_rating is not None:
                total_checked += 1
                if happy_rating < row.seller_rating:
                    happy_lost_due_to_rating += 1
                    print(
                        f"📌 Product ID: {row.id} | Seller Rating: {happy_rating} < Winner Rating: {row.seller_rating}"
                    )

        except Exception as e:
            print(f"⚠️ Error on row {row.id}: {e}")

    print(
        f"📊 {normalized_seller_name} lost due to lower rating: {happy_lost_due_to_rating} out of {total_checked} checked offers")
    return happy_lost_due_to_rating


def parse_delivery_date(text: str):
    print(f"Parsing delivery date from text: {text}")
    if not text:
        return None
    try:
        # Append year if not already present
        current_year = datetime.now().year
        if ',' in text and not any(str(current_year) in word for word in text.split()):
            text = f"{text} {current_year}"
        parsed = dateparser.parse(text)
        return parsed.date() if parsed else None
    except Exception as e:
        print(f"Error parsing delivery date from text: {text} | Error: {e}")
        return None


def get_seller_data(raw_seller_name: str):
    normalized_seller = normalize(raw_seller_name)
    print(normalized_seller)
    seller_normalized_expr = fn.REPLACE(fn.LOWER(StoreFront.seller_name), " ", "")
    winner_normalized_expr = fn.REPLACE(fn.LOWER(Product.winning_seller), " ", "")
    today = datetime.now().date()
    query = (
        StoreFront
        .select(
            StoreFront.created_at.alias('created_at'),
            StoreFront.data_asin.alias('ASIN'),
            Product.category.alias('Product Category'),
            fn.CONCAT('Product ', StoreFront.id).alias('Description'),
            Value(raw_seller_name).alias('Our Seller'),
            StoreFront.delivery_time.alias('delivery_time_ours'),
            StoreFront.price.alias('Final Price'),
            Product.seller_rating.alias('Ratings'),
            Product.winning_seller.alias('Buybox Winner'),
            Product.delivery_time.alias('delivery_time_winner'),
            Product.price.alias('Winner Final Price'),
            Product.seller_rating.alias('Winner Rating'),
            Product.other_sellers.alias('Other Sellers'),
            Product.best_seller_rating.alias('Best Seller Rating'),
            Product.pincode.alias('Pincode'),
            Product.latitude.alias('Latitude'),
            Product.longitude.alias('Longitude'),
            Product.brand_name.alias('Brand Name'),
            Product.batch_no.alias('Batch No'),
            Product.created_at_p.alias('created_at_p'),
        )
        .join(Product, on=((StoreFront.data_asin == Product.data_asin) &
                           (fn.DATE(StoreFront.created_at) == fn.DATE(Product.created_at_p))))
        .where(fn.REPLACE(fn.REPLACE(fn.LOWER(StoreFront.seller_name), ' ', ''), '.', '') == normalized_seller)
        .order_by(StoreFront.created_at)
    )

    raw_data = list(query.dicts())
    print(f"Raw data count: {len(raw_data)}")
    # print(raw_data)
    # for row in raw_data:
    #     created_date = row['created_at'].date()
    #     delivery_ours = parse_delivery_date(row.get('delivery_time_ours'))
    #     delivery_winner = parse_delivery_date(row.get('delivery_time_winner'))
    #     print(f"Created Date: {created_date}, Delivery Ours: {delivery_ours}, Delivery Winner: {delivery_winner}")
    #     row['Date'] = created_date
    #     row['Delivery Time'] = (delivery_ours - created_date).days if delivery_ours else None
    #     row['Winner Delivery'] = (delivery_winner - created_date).days if delivery_winner else None
    #
    #     # Determine Buybox match
    #     our_normalized = normalize(raw_seller_name)
    #     winner_normalized = normalize(row['Buybox Winner'])
    #     row['Lost Buybox'] = our_normalized != winner_normalized
    #
    #     # Remove raw delivery string columns
    #     del row['created_at']
    #     del row['delivery_time_ours']
    #     del row['delivery_time_winner']
    #
    # return pd.DataFrame(raw_data)
    df = pd.DataFrame(raw_data)

    def process_bsr_column(adf):
        def parse_bsr(bsr_json):
            try:
                bsr_list = json.loads(bsr_json) if isinstance(bsr_json, str) else bsr_json
                if isinstance(bsr_list, list):
                    # Sort the BSR list by category in dictionary order
                    sorted_bsr = sorted(bsr_list[:3], key=lambda x: x.get('category', ''))
                    # Extract categories and ranks
                    categories = [item.get('category', '') for item in sorted_bsr]
                    ranks = [item.get('rank', '') for item in sorted_bsr]
                    # Pad with blanks if fewer than 3 items
                    while len(categories) < 3:
                        categories.append('')
                        ranks.append('')
                    print(categories)
                    print(ranks)
                    return categories[0], categories[1], categories[2], ranks[0], ranks[1], ranks[2]
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
            return '', '', '', '', '', ''

        # Apply the parsing function to the DataFrame
        adf['CAT1'], adf['CAT2'], adf['CAT3'], adf['RANK1'], adf['RANK2'], adf['RANK3'] = zip(
            *adf['Best Seller Rating'].apply(parse_bsr)
        )
        # Drop the original 'Best Seller Rating' column
        # adf.drop(columns=['Best Seller Rating'], inplace=True)
        return adf

    # Example usage
    df = process_bsr_column(df)

    def process_other_sellers_column(adf):
        def parse_other_sellers(other_sellers_json):
            try:
                sellers_list = json.loads(other_sellers_json) if isinstance(other_sellers_json,
                                                                            str) else other_sellers_json
                if isinstance(sellers_list, list):
                    # Extract unique seller names
                    unique_sellers = sorted(set(seller['offer_seller'] for seller in sellers_list))
                    sellers_str = " | ".join(unique_sellers)
                    sellers_count = len(unique_sellers)
                    return sellers_str, sellers_count
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
            return None, 0

        # Apply the parsing function to the DataFrame
        adf['Other Sellers'], adf['Total Seller Count'] = zip(*adf['Other Sellers'].apply(parse_other_sellers))
        return adf

    # Example usage
    df = process_other_sellers_column(df)

    # Keep full datetime for output
    # Filter to only latest date entries
    # df = df[df['Date'] == latest_date]
    # Step 1: Convert to string (if coming from CSV or DB)

    # Now get the max *as string*
    latest_batch_no = df['Batch No'].max()
    print(f"Latest batch no: {latest_batch_no}")
    print("Unique batch nos:", df['Batch No'].unique())
    # Filter to only latest batch no entries
    df = df[df['Batch No'] == latest_batch_no]
    print(df.head(5))
    df['Full Timestamp'] = pd.to_datetime(df['created_at_p'])

    # Extract just the date for filtering
    df['Date'] = df['Full Timestamp'].dt.date

    # Get the latest date (ignore time)
    latest_date = df['Date'].max()
    print(f"Latest date: {latest_date}")
    # Drop duplicates by ASIN and Pincode
    df = df.drop_duplicates(subset=['ASIN', 'Pincode'])

    # Parse delivery times
    for i, row in df.iterrows():
        delivery_ours = parse_delivery_date(row.get('delivery_time_ours'))
        delivery_winner = parse_delivery_date(row.get('delivery_time_winner'))

        df.at[i, 'Delivery Time'] = (delivery_ours - row['Date']).days if delivery_ours else None
        df.at[i, 'Winner Delivery'] = (delivery_winner - row['Date']).days if delivery_winner else None

        # Buybox check
        our_normalized = normalize(raw_seller_name)
        winner_normalized = normalize(row['Buybox Winner'])
        df.at[i, 'Lost Buybox'] = our_normalized not in winner_normalized

    # Clean up columns
    df.drop(columns=['created_at', 'created_at_p', 'delivery_time_ours', 'delivery_time_winner'], inplace=True)
    # Reorder if needed
    df = df[['Full Timestamp'] + [col for col in df.columns if col != 'Full Timestamp']]

    return df


def export_seller_data_to_excel(raw_seller_name: str):
    normalized_seller = normalize(raw_seller_name)
    raw_data = get_seller_data(raw_seller_name)
    df = pd.DataFrame(raw_data)
    df = df[df['Buybox Winner'].notna() & (df['Buybox Winner'].str.strip() != "")]
    filename = f"{raw_seller_name}_output.xlsx"

    # Identify rows where the seller lost the buybox
    lost_buybox_df = df[df["Lost Buybox"] == True].copy()
    lost_buybox_df["Delivery Time"] = lost_buybox_df["Delivery Time"].astype(float)
    lost_buybox_df["Winner Delivery"] = lost_buybox_df["Delivery Time"].astype(float)
    # Determine reasons for losing buybox
    lost_buybox_df["Overpricing"] = lost_buybox_df["Final Price"] > lost_buybox_df["Winner Final Price"]
    lost_buybox_df["Late Delivery"] = lost_buybox_df["Delivery Time"].gt(lost_buybox_df["Winner Delivery"])
    lost_buybox_df["Pincode"] = lost_buybox_df["Pincode"].apply(lambda x: x if isinstance(x, str) else "")
    lost_buybox_df["Bad Sentiment Score"] = lost_buybox_df["Winner Rating"] > lost_buybox_df["Ratings"]

    # Format the final output DataFrame
    lost_output_df = lost_buybox_df[["ASIN", "Overpricing", "Late Delivery", "Bad Sentiment Score"]].copy()
    lost_output_df.rename(columns={"Bad Sentiment Score": "Bad Sentiment Score"}, inplace=True)
    df.rename(columns={
        "Brand Name": "Brand",
        "Buybox Winner": "BB Winner",
        "Our Seller": "Seller",
        "Winner Final Price": "BBW Price",
        "Final Price": "Seller Price",
        "Winner Rating": "BBW Rating",
        "Ratings": "Seller Rating",
        "Delivery Time": "Seller Del Time",
        "Winner Delivery": "BBW Del Time",
    }, inplace=True)
    # Adjusting the logic to handle negative values by taking the absolute value
    df['BBW Del Time'] = df['BBW Del Time'].apply(
        lambda x: abs(x) if x is not None and abs(x) <= 30 else (20 if x is not None else None))
    df['Seller Del Time'] = df['BBW Del Time'].apply(
        lambda x: abs(x) if x is not None and abs(x) <= 30 else (20 if x is not None else None))
    # Aggregate lost buybox information
    lost_output_df = lost_buybox_df.groupby("ASIN").agg({
        "Overpricing": "any",
        "Late Delivery": "any",
        "Bad Sentiment Score": "any",
        "Pincode": lambda x: ", ".join(sorted(set(p for p in x if p)))
    }).reset_index()
    lost_output_df["No. Reasons for the loss"] = lost_output_df[
        ["Overpricing", "Late Delivery", "Bad Sentiment Score"]].sum(axis=1)

    # Reorder the columns
    column_order = [
        "ASIN", "Brand", "Description", "Product Category", "Date", "Full Timestamp",
        "Pincode", "BB Winner", "Seller", "Lost Buybox", "BBW Price", "Seller Price",
        "BBW Rating", "Seller Rating", "BBW Del Time", "Seller Del Time", "RANK1", "CAT1", "RANK2", "CAT2", "RANK3",
        "CAT3", "Other Sellers",
        "Total Seller Count",
        "Latitude", "Longitude"
    ]
    # Replace True/False with 'Y'/'N' in df
    # df = df.replace({True: 'Y', False: 'N'})
    df['Lost Buybox'] = df['Lost Buybox'].replace({True: 'Y', False: 'N'})
    df["Brand"] = df.apply(lambda row: row["Seller"] if pd.isna(row["Brand"]) or row["Brand"] == "" else row["Brand"],
                           axis=1)
    # Replace True/False with 'Y'/'N' in lost_output_df
    lost_output_df = lost_output_df.replace({True: 'Y', False: 'N'})
    # Ensure all columns exist in the DataFrame before reordering
    column_order = [col for col in column_order if col in df.columns]
    final_ordered_df = df[column_order]
    pincode_pivot = final_ordered_df.pivot_table(
        index='Pincode',  # Rows
        columns='Lost Buybox',  # Y/N columns
        values='Seller',  # Any column just to count rows (Seller assumed not null)
        aggfunc='count',  # Counting occurrences
        fill_value=0  # Fill missing with 0
    )
    pincode_pivot.columns.name = None

    # Optional: Rename the columns if you want
    pincode_pivot = pincode_pivot.rename(columns={
        'N': 'BuyBox Won',
        'Y': 'BuyBox Lost'
    })

    # Step 4: Add a final row for column-wise grand totals
    pincode_pivot.loc['Grand Total'] = pincode_pivot.sum(axis=0)
    pincode_pivot = pincode_pivot.reset_index()

    print(pincode_pivot)

    category_pivot = final_ordered_df.pivot_table(
        index='Product Category',  # Rows
        columns='Lost Buybox',  # Y/N columns
        values='Seller',  # To count entries
        aggfunc='count',
        fill_value=0
    )

    category_pivot.columns.name = None

    # Rename columns
    category_pivot = category_pivot.rename(columns={
        'N': 'BuyBox Won',
        'Y': 'BuyBox Lost'
    })

    # Add a Grand Total row
    category_pivot.loc['Grand Total'] = category_pivot.sum(axis=0)

    # Reset index if you want 'Product Category' as a column
    category_pivot = category_pivot.reset_index()

    print(category_pivot)
    competitor_pivot = final_ordered_df.pivot_table(
        index='BB Winner',  # Rows
        columns='Lost Buybox',  # Y/N columns
        values='Seller',  # To count entries
        aggfunc='count',
        fill_value=0
    )

    competitor_pivot.columns.name = None

    # Rename columns
    competitor_pivot = competitor_pivot.rename(columns={
        'Y': 'BuyBox Won'
    })
    del competitor_pivot['N']
    # Add a Grand Total row
    if competitor_pivot.columns.size > 0:
        competitor_pivot.loc['Grand Total'] = competitor_pivot.sum(axis=0)
    else:
        print("No columns to sum — skipping Grand Total")

    # Reset index if you want 'Product Category' as a column
    competitor_pivot = competitor_pivot.reset_index()

    print(competitor_pivot)
    final_ordered_df['Brand'] = final_ordered_df['Brand'].str.lower()  # or .str.upper()
    brand_pivot = final_ordered_df.pivot_table(
        index='Brand',  # Rows
        columns='Lost Buybox',  # Y/N columns
        values='Seller',  # To count entries
        aggfunc='count',
        fill_value=0
    )

    brand_pivot.columns.name = None

    # Rename columns
    brand_pivot = brand_pivot.rename(columns={
        'N': 'BuyBox Won',
        'Y': 'BuyBox Lost'
    })

    # Add a Grand Total row
    brand_pivot.loc['Grand Total'] = brand_pivot.sum(axis=0)

    # Reset index if you want 'Product Category' as a column
    brand_pivot = brand_pivot.reset_index()

    print(brand_pivot)
    final_ordered_df = final_ordered_df.fillna("NA")
    final_ordered_df = final_ordered_df.replace("", "NA")
    # Write both sheets to the Excel file
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        final_ordered_df.to_excel(writer, sheet_name="Amazon Raw Data", index=False)
        lost_output_df.to_excel(writer, sheet_name="AMZ BuyBox Loss Analysis", index=False)

        pincode_pivot.to_excel(writer, sheet_name='AMZ Buybox Performance', startrow=1, startcol=0, index=False,
                               header=True)
        workbook = writer.book
        worksheet = writer.sheets['AMZ Buybox Performance']

        # Formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 12
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9EAD3',  # Light green
            'border': 1,
            'align': 'center'
        })

        # Helper function to format headers manually
        def format_headers(df, worksheet, start_row, start_col):
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(start_row, start_col + col_num, value, header_format)

        # Helper function to auto adjust column widths
        def auto_adjust_column_widths(df, start_col, worksheet):
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
                worksheet.set_column(start_col + i, start_col + i, column_len)

        # Start writing
        current_row = 0

        # 1. Pincode Wise Performance
        worksheet.write(current_row, 0, "PINCODE WISE PERFORMANCE", title_format)
        current_row += 1

        format_headers(pincode_pivot, worksheet, current_row, 0)

        pincode_pivot.to_excel(writer, sheet_name='AMZ Buybox Performance', startrow=current_row + 1, startcol=0,
                               index=False, header=False)

        auto_adjust_column_widths(pincode_pivot, 0, worksheet)

        current_row += len(pincode_pivot) + 4

        # 2. Brand Wise Performance
        worksheet.write(0, 5, "BRAND WISE PERFORMANCE", title_format)

        format_headers(brand_pivot, worksheet, 1, 5)

        brand_pivot.to_excel(writer, sheet_name='AMZ Buybox Performance', startrow=2, startcol=5, index=False,
                             header=False)

        auto_adjust_column_widths(brand_pivot, 5, worksheet)

        # 3. Category Wise Performance
        worksheet.write(current_row, 0, "CATEGORY WISE PERFORMANCE", title_format)
        current_row += 1

        format_headers(category_pivot, worksheet, current_row, 0)

        category_pivot.to_excel(writer, sheet_name='AMZ Buybox Performance', startrow=current_row + 1, startcol=0,
                                index=False, header=False)

        auto_adjust_column_widths(category_pivot, 0, worksheet)

        current_row += len(category_pivot) + 4

        # 4. Competitor Performance
        worksheet.write(current_row, 0, "COMPETITOR PERFORMANCE", title_format)
        current_row += 1

        format_headers(competitor_pivot, worksheet, current_row, 0)

        competitor_pivot.to_excel(writer, sheet_name='AMZ Buybox Performance', startrow=current_row + 1, startcol=0,
                                  index=False, header=False)

        auto_adjust_column_widths(competitor_pivot, 0, worksheet)

        current_row += len(competitor_pivot) + 4

        # # Save the file finally
        # writer.save()

    print(f"✅ Excel file created with lost buybox sheet: {filename}")


def get_insights_from_excel(excel_path):
    df = pd.read_excel(excel_path, sheet_name="Amazon Raw Data")

    # Normalize Lost Buybox field
    df['Lost Buybox'] = df['Lost Buybox'].str.upper().str.strip()
    # Replace "Not Available" with blank
    df = df.replace("NA", None)
    # Separate won and lost rows
    total_won = (df['Lost Buybox'] == 'N').sum()
    df_lost = df[df['Lost Buybox'] == 'Y']
    total_lost = df_lost.shape[0]
    date = df['Full Timestamp'].max().date()
    # Calculate loss reasons
    lost_due_to_price = (df_lost['BBW Price'] < df_lost['Seller Price']).sum()
    lost_due_to_delivery = (df_lost['BBW Del Time'] < df_lost['Seller Del Time']).sum()
    lost_due_to_rating = (df_lost['BBW Rating'] > df_lost['Seller Rating']).sum()

    return {
        'winning_asin_count': total_won,
        'loosing_asin_count': total_lost,
        'lost_due_to_price_count': lost_due_to_price,
        'lost_due_to_rating_count': lost_due_to_rating,
        'lost_due_to_delivery_speed_count': lost_due_to_delivery,
        'date': date.strftime("%Y-%m-%d"),
    }
