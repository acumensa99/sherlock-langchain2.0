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
logger = logging.getLogger("instagram_mcp")

# Initialize MCP Server
mcp = FastMCP("Instagram Analytics")

# ================= CONFIGURATION =================

# Database Setup (PostgreSQL)
# INSTAGRAM_DB_URL = os.getenv("")
engine = create_engine("postgresql://neondb_owner:npg_OwEd9SNe8AKr@ep-weathered-leaf-a1erpfh5-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

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
Database Schema (Instagram Analytics):
1. posts (Main table with time-series snapshots)
   - id (SERIAL, primary key), post_id (VARCHAR, not unique), brand_id, creator_id
   - caption (TEXT), views, likes, comments, shares (INTEGER)
   - date_posted (DATE), scraped_at (VARCHAR: "September 10th 2025, 2:20:04 pm")
   - cpv, cpe, vpc, epc, cost (FLOAT)
   
2. creators
   - creator_id (SERIAL), name (VARCHAR), isactive (BOOLEAN)
   - cost (FLOAT) - for CPV/CPE/VPC/EPC calculations
   
3. brands
   - brand_id (SERIAL), brand_name (VARCHAR), isactive (BOOLEAN)
   
4. creators_payment
   - creator_id, creator_name, payment_structure (TEXT with payment rules)
5. dont always compare the given key input with name column somtimes user can also input creator_id

6. don't compare the given name with whole as it name for example there is Rohit Chauhan-fitness couch in database as name of creator if user gave Only rohit chauhan then also it should figure out the desired creator and return.
Key Insight: posts table has DUPLICATE rows for same post_id (time-series snapshots)
7. dont put any limit clause unless user explicitly requests top X or show me X items
"""

SQL_TEMPLATE = """
You are a PostgreSQL expert for Instagram analytics. Convert the request to a SQL query.
{schema}
Request: "{query}"

CRITICAL RULES:
1. Return ONLY the raw SQL query (no markdown, no backticks)
2. Posts table has DUPLICATE rows - ALWAYS deduplicate using:
   
   SELECT p.*
   FROM posts p
   INNER JOIN (
     SELECT post_id, MAX(id) as latest_id
     FROM posts
     GROUP BY post_id
   ) latest ON p.post_id = latest.post_id AND p.id = latest.latest_id

3. **MANDATORY**: For EVERY posts query, include c.cost for Excel metrics:
   LEFT JOIN creators c ON p.creator_id = c.creator_id
   SELECT ... p.views, p.likes, p.comments, p.shares, c.cost ...

4. **DO NOT add LIMIT clause** unless user explicitly requests "top X" or "show me X items"
5. For delta/increment queries: Get first and last snapshot, calculate difference
6. Use ILIKE for text search (case-insensitive)
7. scraped_at is VARCHAR format: "Month DDth YYYY, HH12:MI:SS am"

For increment queries between dates (e.g., "10th to 30th October"):
- Use TO_TIMESTAMP to find closest snapshots to start/end dates
- Calculate: (end_snapshot - start_snapshot)

Required columns for posts queries:
- post_id, creator_id, caption (SUBSTRING(caption, 1, 60)), views, likes, comments, shares
- c.cost (CRITICAL for Excel export), date_posted or scraped_at
"""

ANSWER_TEMPLATE = """
User Request: "{query}"
Data Found: 
{data}

Provide a natural, conversational analysis for Instagram marketing:
- Focus on creators, posts, engagement rates, and trends
- Use emojis: 📸 (posts), 👤 (creators), 🏆 (top), 📊 (stats), 📈 (growth), 💬 (engagement)
- Format numbers with commas
- If payment data exists with "Payment Rules", calculate exact amounts:
  * Parse payment_structure (e.g., "500 rupees per 1000 views")
  * Apply to metrics (views, likes, comments, shares)
  * Show calculations: (1,500,000 ÷ 1,000) × ₹500 = ₹7,50,000
- Keep concise (3-5 sentences) but actionable
"""

# ================= HELPER FUNCTIONS =================

def generate_sql(user_query: str) -> str:
    """Generate SQL query from natural language using Claude"""
    prompt = PromptTemplate.from_template(SQL_TEMPLATE)
    chain = prompt | llm_sql
    response = chain.invoke({"schema": SCHEMA_CONTEXT, "query": user_query})
    sql = response.content.strip().replace('```sql', '').replace('```', '')
    return sql.strip()

def generate_summary(user_query: str, results: list) -> str:
    """Generate natural language summary of results"""
    if not results:
        return "I checked the data, but couldn't find any posts matching your request."
    
    # Don't truncate - send all results for proper analysis
    data_str = json.dumps(results, default=str)
    prompt = PromptTemplate.from_template(ANSWER_TEMPLATE)
    chain = prompt | llm_chat
    response = chain.invoke({"query": user_query, "data": data_str})
    return response.content.strip()

# ================= MCP TOOL DEFINITION =================

@mcp.tool()
async def query_instagram_analytics(query: str) -> str:
    """
    Queries the Instagram analytics database for posts, creators, brands, engagement metrics.
    Use this for questions about Instagram performance, creator analytics, post metrics, 
    engagement rates, payment calculations, trend analysis.
    
    Args:
        query: Natural language question (e.g., "Show top 10 posts by views", 
               "Calculate October payment for Saket Gokhale")
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
        
        # 4. Append hidden data for frontend detection
        if results:
            json_data = json.dumps(results, default=str)
            answer += f"\n\n__INSTAGRAM_DATA_START__{json_data}__INSTAGRAM_DATA_END__"
        
        return answer

    except Exception as e:
        logger.error(f"Error querying Instagram data: {str(e)}")
        return f"Error querying Instagram data: {str(e)}"

# Start the server
if __name__ == "__main__":
    import uvicorn
    
    # Extract the internal FastAPI app from the MCP server
    app = mcp.sse_app()
    
    # Run on port 8008 for Instagram Analytics
    print("Starting Instagram Analytics MCP Server on port 8008...")
    uvicorn.run(app, host="0.0.0.0", port=8008)