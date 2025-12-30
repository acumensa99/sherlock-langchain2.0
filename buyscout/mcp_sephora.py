import os
import re
import json
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate
from mcp.server.fastmcp import FastMCP

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sephora_mcp")

# Initialize MCP Server
# This automatically handles /sse and connection logic
mcp = FastMCP("Sephora Inventory")

# ================= CONFIGURATION =================

# Database Setup (NeonDB)
SEPHORA_DB_URL = os.getenv("SEPHORA_DATABASE_URL", "postgresql://neondb_owner:npg_2B6QXDatPwlp@ep-sparkling-lab-a15aax1d-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
engine = create_engine(SEPHORA_DB_URL)

# Bedrock Model Setup
try:
    llm_sql = ChatBedrock(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", 
        region_name="us-east-1",
        model_kwargs={"temperature": 0} 
    )

    llm_chat = ChatBedrock(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name="us-east-1", 
        model_kwargs={"temperature": 0.5}
    )
except Exception as e:
    logger.warning(f"Bedrock init failed: {e}")
    llm_sql = None
    llm_chat = None

# ================= PROMPTS =================

SCHEMA_CONTEXT = """
Database Schema (Sephora Inventory):
1. store_inventory (Main table)
   - id, sku_id (links to products.product_id), zipcode, store, address, availability
2. products
   - product_id, brand, name, price, source_url, image
"""

SQL_TEMPLATE = """
You are a PostgreSQL expert. Convert the request to a SQL query.
{schema}
Request: "{query}"

RULES:
1. Return ONLY the raw SQL.
2. JOIN store_inventory and products on sku_id = product_id.
3. Use ILIKE for text.
4. Limit to 20 results.
"""

ANSWER_TEMPLATE = """
User Request: "{query}"
Data Found: 
{data}

Summarize this for a shopper. Mention specific products, prices, and store locations if available. 
"""

# ================= HELPER FUNCTIONS =================

def generate_sql(user_query: str) -> str:
    prompt = PromptTemplate.from_template(SQL_TEMPLATE)
    chain = prompt | llm_sql
    response = chain.invoke({"schema": SCHEMA_CONTEXT, "query": user_query})
    sql = response.content.strip().replace('```sql', '').replace('```', '')
    return sql.strip()

def generate_summary(user_query: str, results: list) -> str:
    if not results:
        return "I checked the inventory, but I couldn't find any products matching your request."
    
    data_str = json.dumps(results[:15], default=str)
    prompt = PromptTemplate.from_template(ANSWER_TEMPLATE)
    chain = prompt | llm_chat
    response = chain.invoke({"query": user_query, "data": data_str})
    return response.content.strip()

# ================= MCP TOOL DEFINITION =================

# @mcp.tool()
# async def query_sephora_inventory(query: str) -> str:
#     """
#     Queries the Sephora database for product stock, prices, and store availability.
#     Use this tool when the user asks about Sephora products, beauty items, makeup stock, or specific brands like Fenty, Rare Beauty, etc.
    
#     Args:
#         query: The user's natural language question (e.g., "Do you have Fenty lip gloss?").
#     """
#     logger.info(f"Received query: {query}")
#     try:
#         # 1. Generate SQL
#         sql_query = generate_sql(query)
#         logger.info(f"Generated SQL: {sql_query}")

#         # 2. Execute SQL
#         with engine.connect() as conn:
#             df = pd.read_sql(text(sql_query), conn)
        
#         results = df.to_dict(orient="records")
        
#         # 3. Summarize
#         answer = generate_summary(query, results)
#         return answer

#     except Exception as e:
#         return f"Error querying Sephora data: {str(e)}"
@mcp.tool()
async def query_sephora_inventory(query: str) -> str:
    """
    Queries the Sephora database for product stock, prices, and store availability.
    Use this tool when the user asks about Sephora products, beauty items, makeup stock, or specific brands like Fenty, Rare Beauty, etc.
    
    Args:
        query: The user's natural language question (e.g., "Do you have Fenty lip gloss?").
    """
    logger.info(f"Received query: {query}")
    try:
        # 1. Generate SQL
        sql_query = generate_sql(query)
        logger.info(f"Generated SQL: {sql_query}")

        # 2. Execute SQL
        with engine.connect() as conn:
            df = pd.read_sql(text(sql_query), conn)
        
        results = df.to_dict(orient="records")
        
        # 3. Summarize
        answer = generate_summary(query, results)
        
        # 4. [NEW] Append Hidden Data Block for Frontend Graphs
        # If we have results, we append them as a JSON string with a special delimiter.
        if results and len(results) > 0:
            # Convert full results to JSON string
            json_payload = json.dumps(results, default=str)
            
            # Append the keyword and data. The frontend will Regex search for this block.
            # Format: ANSWER + \n\n + DELIMITER_START + JSON + DELIMITER_END
            return f"{answer}\n\n__SEPHORA_DATA_START__\n{json_payload}\n__SEPHORA_DATA_END__"

        return answer

    except Exception as e:
        return f"Error querying Sephora data: {str(e)}"
# Start the server
if __name__ == "__main__":
    import uvicorn
    
    # 1. Extract the internal FastAPI app from the MCP server
    app = app = mcp.sse_app()
    # 2. Run it just like a normal FastAPI app
    print("Starting Sephora MCP Server on port 8007...")
    uvicorn.run(app, host="0.0.0.0", port=8007)
