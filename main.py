import asyncio
import base64
import io
import json
import logging
import os
import re

# Import video analysis router
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import AgentType, initialize_agent
from langchain_aws import BedrockLLM, ChatBedrock
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import BaseModel
from sqlalchemy import create_engine, inspect, text
from token_tracking_class import BUFFER_TOKENS, TokenTrackingCallback, get_pricing

sys.path.append(os.path.join(os.path.dirname(__file__), "rekogniton-webhook-service"))

try:
    from router import router as video_analysis_router

    VIDEO_ANALYSIS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Video analysis router not available: {e}")
    VIDEO_ANALYSIS_AVAILABLE = False

# Load .env variables
load_dotenv()

# FastAPI app
app = FastAPI()

# Include video analysis router if available
if VIDEO_ANALYSIS_AVAILABLE:
    app.include_router(video_analysis_router)
    logging.info("Video analysis router included successfully")

# Add CORS middleware for video analysis frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# LLM
llama_groq = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
    # callbacks=[TokenTrackingCallback()],
)

claude_opus_4 = ChatBedrock(
    model_id="us.anthropic.claude-opus-4-20250514-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)
claude_sonnet_4 = ChatBedrock(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)

claude_3_7_sonnet = ChatBedrock(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)

claude_3_7_sonnet_mcp = ChatBedrock(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)

client = MultiServerMCPClient(
    {
        "AmazonBuyBoxScraper": {"url": "http://localhost:8001/sse", "transport": "sse"},
        "FraudDetection": {"url": "http://localhost:8002/sse", "transport": "sse"},
        "TelecallerServer": {"url": "http://localhost:8006/sse", "transport": "sse"},
        "SephoraService": {"url": "http://localhost:8007/sse", "transport": "sse"},
        "InstagramService": {"url": "http://localhost:8008/sse", "transport": "sse"},
    }
)


async def run_agent():
    import asyncio

    async def main():
        async with client.session("AmazonBuyBoxScraper") as session:
            tools = await load_mcp_tools(session)

            # Create and run the agent (inside session context!)
            mcp_agent = initialize_agent(
                tools,
                claude_3_7_sonnet_mcp,
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
            )
            return mcp_agent

    # Run the async function in a synchronous context
    return await main()


# 2. Open session to Playwright server and load tools


deepseek_r1 = ChatBedrock(
    model_id="us.deepseek.r1-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)
llama3_70b = ChatBedrock(
    model_id="meta.llama3-70b-instruct-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)
llama3_8b = ChatBedrock(
    model_id="meta.llama3-8b-instruct-v1:0",  # or claude-v3 if you have access
    # credentials_profile_name="default",
    region_name="us-east-1",  # your region
    # callbacks=[TokenTrackingCallback()],
)

models_dict = {
    "llama3-70b-8192": llama_groq,
    "anthropic.claude-opus-4-20250514-v1:0": claude_opus_4,
    "anthropic.claude-sonnet-4-20250514-v1:0": claude_sonnet_4,
    "anthropic.claude-3-7-sonnet-20250219-v1:0": claude_sonnet_4,
    "deepseek.r1-v1:0": deepseek_r1,
    "meta.llama3-70b-instruct-v1:0": llama3_70b,
    "meta.llama3-8b-instruct-v1:0": llama3_8b,
}

# DB connection
engine = create_engine(DATABASE_URL)


# Request model
class QueryRequest(BaseModel):
    seller_name: str
    question: str
    model_id: str
    miniAppType: str
    rls_context: Optional[Dict[str, Any]] = None


# Request model
class QueryRequestAutocomplete(BaseModel):
    question: str


# Helper: Get DB schema
# def get_db_schema_summary(engine):
#     inspector = inspect(engine)
#     schema = ""

#     for table_name in inspector.get_table_names():
#         columns = inspector.get_columns(table_name)
#         schema += f"\nTable: {table_name}\n"
#         for col in columns:
#             schema += f"  - {col['name']} ({col['type']})\n"

#     return schema.strip()


def get_db_schema_summary(engine, target_tables=None):
    inspector = inspect(engine)
    schema = ""

    all_tables = inspector.get_table_names()

    # Filter if target_tables is provided
    if target_tables:
        tables_to_process = [t for t in all_tables if t in target_tables]
    else:
        tables_to_process = all_tables

    for table_name in tables_to_process:
        columns = inspector.get_columns(table_name)
        schema += f"\nTable: {table_name}\n"
        for col in columns:
            schema += f"  - {col['name']} ({col['type']})\n"

    return schema.strip()


# Helper: Get sample data
def get_sample_data(engine, row_limit=3):
    inspector = inspect(engine)
    samples = ""

    for table in inspector.get_table_names():
        try:
            df = pd.read_sql(f"SELECT * FROM {table} LIMIT {row_limit}", engine)
            samples += f"\nSample data from `{table}`:\n{df.to_markdown(index=False)}\n"
        except Exception as e:
            samples += f"\nSample data from `{table}`: [ERROR fetching sample: {e}]\n"

    return samples.strip()


logging.basicConfig(level=logging.INFO)


@app.get("/")
async def root():
    """Root endpoint showing available services"""
    services = {
        "status": "running",
        "service": "sherlock-langchain-api",
        "available_endpoints": {
            "data_analytics": [
                "/query",
                "/general",
                "/generate_title",
                "/autocomplete",
            ],
            "models": ["/enabled_models"],
        },
    }

    if VIDEO_ANALYSIS_AVAILABLE:
        services["available_endpoints"]["video_analysis"] = [
            "/video-analysis/upload",
            "/video-analysis/status/{job_id}",
            "/video-analysis/chat/{job_id}",
            "/video-analysis/summary/{job_id}",
            "/video-analysis/files/filtered",
            "/video-analysis/chat-file",
        ]

    return services


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "data_analytics": "active",
            "video_analysis": "active" if VIDEO_ANALYSIS_AVAILABLE else "not_available",
        },
    }


@app.get("/enabled_models")
async def get_enabled_models():
    try:
        return {"models": list(models_dict.keys())}

    except Exception as e:
        return {"error": str(e)}


@app.post("/query")
async def query(request: QueryRequest):
    logging.info(
        f"Received query request {request}",
    )
    # Validate model_id
    if request.model_id not in models_dict:
        raise HTTPException(
            status_code=400, detail=f"Invalid model_id: {request.model_id}"
        )
    try:
        # Initialize the agent
        # mcp_agent = await run_agent()
        logging.info(f"Received request for seller: {request.seller_name}")
        logging.info(f"Question: {request.question}")
        logging.info(f"Using model: {request.model_id}")

        # Determine which tables strictly belong to which app
        insta_tables = ["posts", "creators", "brands"]

        if request.miniAppType in ["INSTAGRAM_ANALYZER", "INSTAGRAM"]:
            schema_info = get_db_schema_summary(engine, target_tables=insta_tables)
        else:
            # Exclude instagram tables for other apps to save tokens/confusion
            schema_info = get_db_schema_summary(engine)
        sample_data = get_sample_data(engine)
        if (
            request.miniAppType == "BBCHAMPS"
            or request.miniAppType == "SCRAPPER"
            or request.miniAppType == "FRAUD_DETECTION"
        ):
            # question intent classifier (either buybox or scraping) using llm
            print("Classifying question intent using LLM...")
            response = llama3_70b.invoke(f"""
    You are a helpful assistant. Classify the following question into one of the following categories:
    1. BUYBOX
    2. SEPHORA
    3. FRAUDDETECTION
    4. INSTAGRAM_ANALYZER
    Question: "{request.question}"

    Give the output in the format specified below including the serial number, category number and name:
    Also Do not give SCRAPING AND FRAUDDETECTION unless explicitly asked for scraping or fraud detection in the question.

    ANSWER:
    1. <category number> - <category name>

            """)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            print(f"Response from model: {response_text}")
            usage = getattr(response, "usage_metadata", {})
            input_tokens = usage.get("input_tokens", 0) + BUFFER_TOKENS
            output_tokens = usage.get("output_tokens", 0) + BUFFER_TOKENS
            total_tokens = input_tokens + output_tokens
            # create a token object
            token_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
            logging.info(
                f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}"
            )
            # get pricing
            #            "input_cost": input_cost,
            #    "output_cost": output_cost,
            #    "total_cost": total_cost
            pricing = get_pricing(request.model_id, input_tokens, output_tokens)
            logging.info(f"Pricing: {pricing}")
            print("Response Text:\n", response_text)
            # Extract category from response
            # answer_match = re.search(r"ANSWER:\s*\d+\.\s*(\d+)\s*-\s*(.+)", response_text, re.DOTALL)
            # if answer_match:
            #     category_number = int(answer_match.group(1).strip())
            #     category_name = answer_match.group(2).strip()
            # else:
            #     raise HTTPException(status_code=400, detail="Invalid response format from LLM")

            if "SCRAPPER" in request.miniAppType:
                request.miniAppType = "SCRAPING"
            elif "FRAUD_DETECTION" in request.miniAppType:
                request.miniAppType = "FRAUD_DETECTION"
            elif "SEPHORA" in request.miniAppType:
                request.miniAppType = "SEPHORA"
            elif "INSTAGRAM_ANALYZER" in request.miniAppType:
                request.miniAppType = "INSTAGRAM_ANALYZER"
            elif "BUYBOX" in response_text:
                request.miniAppType = "BBCHAMPS"
            elif "SCRAPING" in response_text:
                request.miniAppType = "SCRAPING"
            elif "FRAUDDETECTION" in response_text:
                request.miniAppType = "FRAUD_DETECTION"
            elif "SEPHORA" in response_text:
                request.miniAppType = "SEPHORA"
            elif "INSTAGRAM_ANALYZER" in response_text:
                request.miniAppType = "INSTAGRAM_ANALYZER"
            else:
                raise HTTPException(
                    status_code=400, detail="Invalid category number from LLM"
                )

            logging.info(f"Classified as: {request.miniAppType}")

        base_prompt = f"""
You are a helpful data analyst assistant called Sherlock. You have access to the following PostgreSQL database schema and sample data:

{
            f'''
## SCHEMA:
{schema_info}

## SAMPLE DATA:
{sample_data}

Do NOT wrap SQL or Python code in triple backticks. Ensure valid syntax.
Do NOT use psycopg2 or raw connections — data is already in a DataFrame called `df`.
Only use pandas and matplotlib to analyze or plot `df`.
Do not leak other seller's data or any other information, if asked about another seller other than {request.seller_name} say UnAuthorized.


## TASK TYPE: {request.miniAppType}

### CRITICAL SQL RULES FOR SEPHORA:
**DO NOT ADD LIMIT CLAUSE** - Fetch ALL matching rows without any LIMIT
Only use LIMIT if user explicitly requests "top X" or "show me X items"

### SEPHORA INVENTORY HANDLING:
If the task involves Sephora inventory data (TASK: SEPHORA or similar):

1. **Always format responses in clear, structured tables** when presenting product listings, inventory counts, or store data
2. **Use markdown table format** with pipes (|) for all tabular data:
   ```
   | Column1 | Column2 | Column3 |
   |---------|---------|---------|
   | Value1  | Value2  | Value3  |
   ```
3. **Include these key columns when available:**
   - Product Name
   - Brand
   - Store/Location
   - Address (including ZIP code)
   - Stock Status (In Stock, Out of Stock, Limited Stock)
   - Price (if available)

4. **For inventory queries, provide:**
   - Summary statistics (total products, in-stock count, out-of-stock count)
   - Detailed table of matching products
   - Group by store/location when comparing multiple locations

5. **For out-of-stock queries:**
   - Always include ZIP codes in the address column
   - Sort by location for better readability
   - Add a summary line at the end (e.g., "Total: X products out of stock across Y locations")

6. **For store comparison queries:**
   - Create summary tables showing aggregated counts per store
   - Include both numerical values and percentages where relevant
   - Example format:
   ```
   | Store Name | In Stock | Out of Stock | Limited Stock | Total Products |
   |------------|----------|--------------|---------------|----------------|
   | Store 1    | 45       | 3            | 2             | 50             |
   ```

7. **Always provide context before tables:**
   - Brief summary of what the data shows
   - Total counts or key insights
   - Then present the detailed table

8. **SQL Query Rules:**
   - DO NOT add LIMIT 20 or any LIMIT clause to SQL queries
   - Retrieve ALL matching products from the database
   - Only use LIMIT if user explicitly says "show me 10 products" or similar
   - The complete inventory must be analyzed, not just a sample

    '''
            if request.miniAppType == "SEPHORA"
            else f'''
## SCHEMA:
{schema_info}

## SAMPLE DATA:
{sample_data}
## TASK TYPE: {request.miniAppType}

### CRITICAL SQL RULES FOR INSTAGRAM:

1. **DEDUPLICATION IS MANDATORY:** The `posts` table has DUPLICATE rows (time-series snapshots).
   - You MUST deduplicate using:
     `INNER JOIN (SELECT post_id, MAX(id) as latest_id FROM posts GROUP BY post_id) latest ON p.post_id = latest.post_id AND p.id = latest.latest_id`
2. **COST DATA:** ALWAYS `LEFT JOIN creators c ON p.creator_id = c.creator_id` to fetch `c.cost`.
3. **SEARCHING:** - Use `ILIKE` for text search (case-insensitive).
   - If searching for a creator, check both `name` column and `creator_id`.
   - Handle partial matches (e.g., if user asks for "Rohit", match "Rohit Chauhan-fitness coach").
4. **NO LIMIT:** Do NOT add LIMIT unless user explicitly requests "top X".
5. Most important the key from the user input could be either creator name or creator id so always make sure to check both the columns while filtering.
6. Instagram specific data is only in the `posts` table, not in `creators` or `brands` tables.
### INSTAGRAM DATA HANDLING:
1. **Always format responses in clear, structured tables**:
2. **Calculations:**
- If `payment_structure` is available in context, calculate exact amounts (e.g., (Views/1000) * Rate) and show the math.
3. **Analysis Style:**
- Provide natural, conversational analysis.
- Use emojis: 📸 (posts), 👤 (creators), 🏆 (top), 📊 (stats), 📈 (growth), 💬 (engagement).
4. **Key Columns to Return:**
- post_id, creator_id/name, caption (truncated), views, likes, comments, shares, c.cost, date_posted.

Do NOT wrap SQL or Python code in triple backticks. Ensure valid syntax.
     '''
            if request.miniAppType == "INSTAGRAM_ANALYZER"
            else f'''
## SCHEMA:
{schema_info}

## SAMPLE DATA:
{sample_data}

Do NOT wrap SQL or Python code in triple backticks. Ensure valid syntax.
Do NOT use psycopg2 or raw connections — data is already in a DataFrame called `df`.
Only use pandas and matplotlib to analyze or plot `df`.
Do not leak other seller's data or any other information, if asked about another seller other than {request.seller_name} say UnAuthorized.

Do NOT wrap SQL or Python code in triple backticks. Ensure valid syntax.
Do NOT use psycopg2 or raw connections — data is already in a DataFrame called `df`.
Only use pandas and matplotlib to analyze or plot `df`.
Do not leak other seller's data or any other information, if asked about another seller other than {request.seller_name} say UnAuthorized.
    '''
        }

{
            '''
### BBCHAMPS SPECIFIC RULES:
If the user asks for data (buybox, sales, inventory, etc.), YOU MUST GENERATE SQL to fetch it.
Do NOT say "I don't see any data". Query the database first.
INTERPRETATION RULE: "Buy Box Data" means Market Analysis. Show ALL visible products and their `winning_seller` column.
Do NOT filter by the current user's seller name automatically. We want to see competitors.
Only write Python code if a chart/plot is requested.
    '''
            if request.miniAppType == "BBCHAMPS"
            else '''
### GENERAL RULES:
1. If asked about prices or scraping some data (ASIN), trigger the scraper. DO NOT WRITE SQL OR PYTHON CODE - only provide answers based on scraper info
2. If retrieved scraping data has price as N/A or many attributes as N/A, the scraping failed - inform the user and suggest trying again
3. If it's scraped data, format it in a tabular format using markdown tables
4. For non-scraping questions (greetings, general questions), respond as an assistant without SQL/Python code
5. If a greeting is done (Hi, Hello), just respond as an assistant and greet back
6. No scraping should happen unless the input is clearly a scraping request
7. Do not make assumptions; only scrape if the input demands product info
8. IF THE GIVEN QUESTION IS GIBBERISH, DO NOT TRIGGER THE SCRAPER - just say INVALID QUESTION

### FRAUD DETECTION:
If asked about fraud detection with a phone number:
- Trigger the fraud detection tool
- Only output the status (present in Amazon/Flipkart)
- DO NOT draw conclusions about legitimacy
- DO NOT WRITE SQL OR PYTHON CODE
- Keep Python and SQL sections blank

### TELECALLING:
You can make calls using the MCP tool if requested (phone numbers must start with +91)
    '''
        }

The user asked the following question about seller "{request.seller_name}":

"{request.question}"

### RESPONSE FORMAT:

Please provide:
1. **ANSWER:** A clear, natural language insight or summary
2. **If the query involves tabular data (inventory lists, product comparisons, store statistics):**
   - Format the response using markdown tables
   - Include all relevant columns with proper headers
   - Ensure numeric values are clearly displayed
   - Add summary statistics where applicable

3. **Context-aware responses:**
   - Use database as primary source
   - Use context if provided or for scraping-related questions
   - Don't hallucinate column names or tables
   - Match schema case exactly

3.5. **SQL Generation for SEPHORA tasks:**
   - Never add LIMIT clause unless explicitly requested by user
   - Fetch complete dataset for accurate inventory analysis
   - Example: Use `SELECT * FROM products WHERE condition` NOT `SELECT * FROM products WHERE condition LIMIT 20`

4. **Code generation (only when needed):**
   - SQL: Do NOT automatically filter by seller_name or winning_seller unless explicitly requested.
   - For "Buy Box" queries, select ALL visible rows and include the `winning_seller` column.
   - Python: Only for charts/visualizations when explicitly requested
   - Don't write code for greetings or simple queries

Do NOT wrap SQL or Python code in triple backticks. Ensure valid syntax.
Return your output in the format:

ANSWER:
<your insight with tables when applicable>
{
            '''
SQL:
<optional query - NO LIMIT clause for SEPHORA tasks

PYTHON:
<optional matplotlib code>
    '''
            if request.miniAppType not in ["FRAUD_DETECTION", "SEPHORA"]
            else ""
        }
"""
        total_tokens = 0
        total_input_tokens = 0
        total_output_tokens = 0

        async def run_pipeline(prompt, attempt_fix=False, error_msg=""):
            full_prompt = prompt
            if attempt_fix and error_msg:
                full_prompt += f"""

The previous attempt failed with the following error:
{error_msg}

Please correct the SQL or Python code accordingly and return the updated versions.
"""
                response = models_dict.get(request.model_id).invoke(full_prompt)
            else:
                if request.miniAppType == "SCRAPING":
                    async with client.session("AmazonBuyBoxScraper") as session:
                        tools = await load_mcp_tools(session)

                        # Create and run the agent (inside session context!)
                        mcp_agent = initialize_agent(
                            tools,
                            claude_3_7_sonnet_mcp,
                            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                            verbose=True,
                        )
                        response = await mcp_agent.ainvoke(full_prompt)
                elif request.miniAppType == "FRAUD_DETECTION":
                    print("Running Fraud Detection Agent...")
                    async with client.session("FraudDetection") as session:
                        tools = await load_mcp_tools(session)

                        # Create and run the agent (inside session context!)
                        mcp_agent = initialize_agent(
                            tools,
                            claude_3_7_sonnet_mcp,
                            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                            verbose=True,
                        )
                        response = await mcp_agent.ainvoke(full_prompt)
                elif request.miniAppType == "SEPHORA":
                    print("Running Sephora Intelligence Agent...")
                    async with client.session("SephoraService") as session:
                        tools = await load_mcp_tools(session)

                        mcp_agent = initialize_agent(
                            tools,
                            claude_3_7_sonnet_mcp,
                            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                            verbose=True,
                        )
                        response = await mcp_agent.ainvoke(full_prompt)
                elif request.miniAppType == "INSTAGRAM_ANALYZER":
                    print("Running Instagram Intelligence Agent...")
                    async with client.session("InstagramService") as session:
                        tools = await load_mcp_tools(session)

                        mcp_agent = initialize_agent(
                            tools,
                            claude_3_7_sonnet_mcp,
                            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                            verbose=True,
                        )
                        response = await mcp_agent.ainvoke(full_prompt)
                else:
                    # Check for explicit calling intent in user question to avoid false positives from system prompt
                    if (
                        "call" in request.question.lower()
                        or "telecall" in request.question.lower()
                    ):
                        print("Running Telecaller Agent...")
                        try:
                            async with client.session("TelecallerServer") as session:
                                tools = await load_mcp_tools(session)

                                # Create and run the agent (inside session context!)
                                mcp_agent = initialize_agent(
                                    tools,
                                    claude_3_7_sonnet_mcp,
                                    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                                    verbose=True,
                                )
                                response = await mcp_agent.ainvoke(full_prompt)
                        except Exception as e:
                            logging.warning(
                                f"Telecaller unreachable, falling back to standard model: {e}"
                            )
                            response = models_dict.get(request.model_id).invoke(
                                full_prompt
                            )
                    else:
                        response = models_dict.get(request.model_id).invoke(full_prompt)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            print(f"Response from model: {response_text}")
            usage = getattr(response, "usage_metadata", {})
            input_tokens1 = usage.get("input_tokens", 0) + BUFFER_TOKENS
            output_tokens1 = usage.get("output_tokens", 0) + BUFFER_TOKENS
            total_tokens1 = input_tokens1 + output_tokens1
            logging.info(
                f"Input tokens: {input_tokens1}, Output tokens: {output_tokens1}, Total tokens: {total_tokens1}"
            )
            # Update total tokens
            nonlocal total_tokens, total_input_tokens, total_output_tokens
            total_tokens += total_tokens1
            total_input_tokens += input_tokens1
            total_output_tokens += output_tokens1

            # create a token object

            answer_match = re.search(
                r"ANSWER:\s*(.*?)\s*(SQL:|$)", response_text, re.DOTALL
            )
            sql_match = re.search(
                r"SQL:\s*(.*?)\s*(PYTHON:|$)", response_text, re.DOTALL
            )
            py_match = re.search(r"PYTHON:\s*(.*)", response_text, re.DOTALL)

            reasoning = response_text.rsplit("ANSWER:", 1)[-1]
            sql_code = sql_match.group(1).strip() if sql_match else ""
            py_code = py_match.group(1).strip() if py_match else ""

            return reasoning, sql_code.strip("`").strip(), py_code.strip("`").strip()

        # Initial LLM response
        reasoning, sql_code, py_code = await run_pipeline(base_prompt)
        logging.info(f"Initial reasoning: {reasoning}")
        df = None
        encoded_img = None

        # Retry SQL execution up to 3 times
        if request.miniAppType == "BBCHAMPS":
            for attempt in range(10):
                try:
                    if sql_code:
                        logging.info(f"Executing SQL attempt {attempt + 1}...")
                        with engine.begin() as conn:
                            # Apply RLS Context if present
                            if request.rls_context:
                                rls = request.rls_context
                                # Set Role
                                role = rls.get("user_role", "user")
                                conn.execute(
                                    text(f"SET LOCAL app.user_role = '{role}'")
                                )

                                # Set Company ID
                                company_id = rls.get("company_id")
                                if company_id:
                                    conn.execute(
                                        text(
                                            f"SET LOCAL app.current_company_id = '{company_id}'"
                                        )
                                    )

                                # Set Allowed Categories
                                allowed_cats = rls.get("allowed_categories", [])
                                if allowed_cats and "*" not in allowed_cats:
                                    # Format as JSON string for RLS policy (expecting jsonb array)
                                    cats_json = json.dumps(allowed_cats)
                                    safe_json = cats_json.replace("'", "''")
                                    conn.execute(
                                        text(
                                            f"SET LOCAL app.allowed_categories = '{safe_json}'"
                                        )
                                    )

                                # Set Max Days
                                max_days = rls.get("max_days")
                                if max_days:
                                    conn.execute(
                                        text(f"SET LOCAL app.max_days = '{max_days}'")
                                    )

                                # Set Access Start Date
                                start_date = rls.get("access_start_date")
                                if start_date:
                                    conn.execute(
                                        text(
                                            f"SET LOCAL app.access_start_date = '{start_date}'"
                                        )
                                    )

                                # Set Access End Date
                                end_date = rls.get("access_end_date")
                                if end_date:
                                    conn.execute(
                                        text(
                                            f"SET LOCAL app.access_end_date = '{end_date}'"
                                        )
                                    )

                            df = pd.read_sql(text(sql_code), conn)
                        logging.info(f"SQL returned {len(df)} rows.")
                        break  # Success
                except Exception as e_sql:
                    logging.warning(f"SQL error (attempt {attempt + 1}): {e_sql}")
                    if attempt < 9:
                        reasoning, sql_code, py_code = await run_pipeline(
                            base_prompt, attempt_fix=True, error_msg=str(e_sql)
                        )
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail=f"SQL failed after 3 attempts: {e_sql}",
                        )

        # Retry Python execution up to 3 times
        if py_code and df is not None and not df.empty:
            for attempt in range(6):
                try:
                    if py_code and df is not None and not df.empty:
                        logging.info(f"Executing Python attempt {attempt + 1}...")
                        exec_env = {
                            "df": truncate_dataframe(df, token_limit=5000),
                            "plt": plt,
                            "pd": pd,
                        }
                        py_code = py_code.replace(
                            "plt.show()", ""
                        )  # Avoid showing plots in Jupyter
                        exec(py_code, exec_env)

                        fig = plt.gcf()
                        if fig and fig.get_axes():
                            buf = io.BytesIO()
                            plt.savefig(buf, format="png")  # Save directly to buffer
                            buf.seek(0)
                            encoded_img = base64.b64encode(buf.read()).decode(
                                "utf-8"
                            )  # Encode as base64
                            buf.close()
                            plt.close(fig)  # Clear figure
                            logging.info("Chart successfully encoded as base64.")
                        break  # Success
                except Exception as e_py:
                    logging.warning(f"Python error (attempt {attempt + 1}): {e_py}")
                    if attempt < 5:
                        reasoning, sql_code, py_code = await run_pipeline(
                            base_prompt, attempt_fix=True, error_msg=str(e_py)
                        )
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Python failed after 3 attempts: {e_py}",
                        )
        if df is not None:
            df.replace([np.inf, -np.inf], np.nan, inplace=True)  # Replace inf with NaN
            df.fillna("null", inplace=True)  # Replace NaN with a string
            output_dict = df.to_dict()
        else:
            output_dict = None
        if output_dict:
            df = df.applymap(
                lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x
            )
            # remove id column from df
            df = df.loc[:, ~df.columns.str.contains("^id$")]

            output_dict = truncate_dataframe(df, token_limit=5000).to_dict(
                orient="records"
            )
            if request.miniAppType == "BBCHAMPS":
                reasoning, token_usage = await generate_reason(
                    request.question,
                    request.model_id,
                    json.dumps(output_dict),
                    request.seller_name,
                )
            if request.miniAppType == "SCRAPING":
                reasoning, token_usage = await generate_reason(
                    request.question, request.model_id, reasoning, request.seller_name
                )
            total_output_tokens += token_usage.get("output_tokens", 0)
            total_input_tokens += token_usage.get("input_tokens", 0)
            total_tokens += token_usage.get("total_tokens", 0)

        token_usage = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
        }

        # get pricing
        #            "input_cost": input_cost,
        #    "output_cost": output_cost,
        #    "total_cost": total_cost
        pricing = get_pricing(request.model_id, total_input_tokens, total_output_tokens)

        return {
            "answer": reasoning,
            "output": output_dict if df is not None else None,
            "chart": encoded_img,
            "sql": sql_code or None,
            "python_code": py_code or None,
            "pricing": pricing,
            "miniAppType": request.miniAppType,
            "token_usage": token_usage,
        }

    except Exception as e:
        logging.exception("Final processing error")
        raise HTTPException(status_code=500, detail=str(e))


def truncate_dataframe(df, token_limit=3000):
    try:
        # Convert DataFrame to JSON string for token calculation
        dataframe_json = df.to_json(orient="records")
        token_count = len(dataframe_json)

        # If token count exceeds the limit, truncate rows
        if token_count > token_limit:
            max_rows = max(1, int(len(df) * (token_limit / token_count)))
            df = df.iloc[:max_rows]

        # Convert truncated DataFrame to JSON-serializable format
        df = df.applymap(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x)
        return df

    except Exception as e:
        logging.exception("Error truncating DataFrame")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_title")
async def generate_title(request: QueryRequest):
    print("test")
    try:
        logging.info(
            f"Received request to generate title for question: {request.question}"
        )

        # Prompt for generating chat title
        title_prompt = f"""
        You are a helpful assistant. Generate a concise and descriptive chat title based on the following question:

        "{request.question}"

        Ensure the title is short, relevant, and captures the essence of the question.
        Give the output as the format specified below:

        ANSWER:
        <your title>
        """

        # Invoke LLM to generate title
        response = llama_groq.invoke(title_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Extract title from response
        title_match = re.search(r"ANSWER:\s*(.*)", response_text, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = "Introduction and Capabilities"

        chat_title = f"{title}"

        return {"title": chat_title}

    except Exception as e:
        logging.exception("Error generating chat title")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/general")
async def general(request: QueryRequest):
    if request.model_id not in models_dict:
        raise HTTPException(
            status_code=400, detail=f"Invalid model_id: {request.model_id}"
        )
    try:
        logging.info(f"Received request for general chat")
        logging.info(f"Using model: {request.model_id}")
        # Prompt for generating chat title
        title_prompt = f"""
        You are a helpful personal assistant. Give a concise and descriptive answer based on the following question:
        Do not include a title in your answers, keep the answers long and descriptive and in points
        Style the answers using md styling.

        "{request.question}"

        Give the output as the format specified below:
        MAKE SURE TO GIVE YOUR ANSWER IN THE FORMAT SPECIFIED BELOW

        ANSWER:
        <your output>
        """

        # Invoke LLM to generate title
        response = models_dict.get(request.model_id).invoke(title_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )
        print(f"Response from model: {response_text}")
        usage = getattr(response, "usage_metadata", {})
        input_tokens = usage.get("input_tokens", 0) + BUFFER_TOKENS
        output_tokens = usage.get("output_tokens", 0) + BUFFER_TOKENS
        total_tokens = input_tokens + output_tokens
        # create a token object
        token_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        logging.info(
            f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}"
        )
        # get pricing
        #            "input_cost": input_cost,
        #    "output_cost": output_cost,
        #    "total_cost": total_cost
        pricing = get_pricing(request.model_id, input_tokens, output_tokens)
        logging.info(f"Pricing: {pricing}")
        # Extract title from response
        answer_match = re.search(r"ANSWER:\s*(.*)", response_text, re.DOTALL)
        answer = ""
        if answer_match:
            answer = answer_match.group(1).strip()

        answer = f"{answer}"

        return {
            "answer": answer,
            "output": None,
            "chart": None,
            "sql": None,
            "python_code": None,
            "pricing": pricing,
            "token_usage": token_usage,
        }

    except Exception as e:
        logging.exception("Error generating chat title")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/autocomplete")
async def autocomplete_business(request: QueryRequestAutocomplete):
    try:
        # Business-specific autocomplete prompt
        business_prompt = f"""
        You are a helpful and intelligent autocomplete assistant specialized in business topics.

        The user has started a business-related question. Suggest 5 possible complete business-focused questions that the user might be trying to ask.

        Incomplete question:
        "{request.question}"

        Your response should be formatted like this:
        SUGGESTIONS:
        1. <business completion 1>
        2. <business completion 2>
        3. <business completion 3>
        4. <business completion 4>
        5. <business completion 5>
        """

        # Call the LLM
        response = llama_groq.invoke(business_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )
        print(response_text)

        # Extract 5 completions
        suggestions = re.findall(r"\d+\.\s*(.*)", response_text)

        return {"completions": suggestions[:5]}

    except Exception as e:
        logging.exception("Error generating business autocomplete suggestions")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/general-streaming")
async def general_streaming(request: QueryRequest):
    if request.model_id not in models_dict:
        raise HTTPException(
            status_code=400, detail=f"Invalid model_id: {request.model_id}"
        )

    try:
        logging.info(f"Received request for general chat")
        logging.info(f"Using model: {request.model_id}")

        title_prompt = f"""
        You are a helpful personal assistant. Give a concise and descriptive answer based on the following question:
        Do not include a title in your answers, keep the answers long and descriptive and in points
        Style the answers using md styling.

        "{request.question}"

        Give the output as the format specified below:
        MAKE SURE TO GIVE YOUR ANSWER IN THE FORMAT SPECIFIED BELOW

        ANSWER:
        <your output>
        """

        # Get the model instance
        model = models_dict.get(request.model_id)

        # Ensure the model supports streaming
        if not hasattr(model, "stream"):
            raise HTTPException(
                status_code=500, detail="Streaming not supported for this model."
            )

        # Streaming generator
        def generate_chunks():
            yield "ANSWER:\n"
            for chunk in model.stream(title_prompt):  # sync iterator
                if hasattr(chunk, "content"):
                    yield chunk.content
                else:
                    yield str(chunk)

        return StreamingResponse(generate_chunks(), media_type="text/plain")

    except Exception as e:
        logging.exception("Error generating streamed response")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_reason(question, model_id, dataframe_json, seller_name):
    print("dataframe_json: ", dataframe_json)
    try:
        logging.info(f"Received request to generate reasoning for question: {question}")

        # Prompt for generating reasoning
        reasoning_prompt = f"""
        You are a helpful assistant. Based on the following question and the provided JSON data, generate a concise and descriptive reasoning:

        QUESTION:
        "{question}"

        DATAFRAME:
        {dataframe_json}

        Ensure the reasoning is short, relevant, and captures the essence of the question.
        Do not leak other seller's data or any other information, if asked about another seller other than {seller_name} say UnAuthorized. Return your output in the format:
        Give the output as the format specified below:
        ANSWER:
        <your reasoning>
        """

        # Invoke LLM to generate reasoning
        response = models_dict.get(model_id).invoke(reasoning_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )
        print(f"Response from model: {response_text}")
        usage = getattr(response, "usage_metadata", {})
        input_tokens = usage.get("input_tokens", 0) + BUFFER_TOKENS
        output_tokens = usage.get("output_tokens", 0) + BUFFER_TOKENS
        total_tokens = input_tokens + output_tokens
        logging.info(
            f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}"
        )

        # Extract reasoning from response
        reasoning_match = re.search(r"ANSWER:\s*(.*)", response_text, re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        else:
            reasoning = "No reasoning generated."

        return reasoning, {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    except Exception as e:
        logging.exception("Error generating reasoning")
        return "No reasoning generated due to an error."
