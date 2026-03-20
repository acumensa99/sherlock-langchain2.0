import asyncio
import base64
import io
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

pd.set_option("future.no_silent_downcasting", True)

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import AgentType, initialize_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

# Local module imports
from models_config import (
    AUTOCOMPLETE_ENABLED,
    DATABASE_URL,
    GROQ_API_KEY,
    llama3_8b,
    llama_groq,
    models_dict,
)
from prompts import (
    AUTOCOMPLETE_BUSINESS_PROMPT,
    GENERAL_CHAT_PROMPT,
    TITLE_GENERATION_PROMPT,
    get_query_prompt,
)
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from token_tracking_class import BUFFER_TOKENS, get_pricing
from utils import get_db_schema_summary, get_sample_data, truncate_dataframe

# Add webhook service path
sys.path.append(os.path.join(os.path.dirname(__file__), "rekogniton-webhook-service"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Load .env variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Video Analysis Router Integration
VIDEO_ANALYSIS_AVAILABLE = False
try:
    from router import router as video_analysis_router

    VIDEO_ANALYSIS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Video analysis router not available: {e}")

if VIDEO_ANALYSIS_AVAILABLE:
    app.include_router(video_analysis_router)
    logging.info("Video analysis router included successfully")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*",
    ],  # Allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Engine
if not DATABASE_URL:
    logging.error("DATABASE_URL not found in environment variables")
    raise RuntimeError("DATABASE_URL is missing")

engine = create_engine(DATABASE_URL)

# MCP Client Configuration
client = MultiServerMCPClient(
    {
        "AmazonBuyBoxScraper": {"url": "http://localhost:8001/sse", "transport": "sse"},
        "FraudDetection": {"url": "http://localhost:8002/sse", "transport": "sse"},
        "SephoraService": {"url": "http://localhost:8003/sse", "transport": "sse"},
        "InstagramService": {"url": "http://localhost:8004/sse", "transport": "sse"},
        "TelecallerServer": {"url": "http://localhost:8005/sse", "transport": "sse"},
    }
)


# --- Pydantic Models ---
class QueryRequest(BaseModel):
    question: str
    model_id: str = "llama3-70b-8192"  # Default
    miniAppType: str = "BBCHAMPS"
    seller_name: str = "Unknown"
    rls_context: Optional[Dict[str, Any]] = None


class QueryRequestAutocomplete(BaseModel):
    question: str


# --- Helper Functions ---


async def generate_reason(
    question: str, model_id: str, data_context: str, seller_name: str
):
    """
    Generates a natural language summary/reasoning based on the data retrieved.
    """
    try:
        logging.info("Generating summary for retrieved data...")
        model = models_dict.get(model_id)
        if not model:
            # Fallback if model not found
            from models_config import llama3_70b

            model = llama3_70b

        prompt = f"""
        You are a data analyst assistant for seller "{seller_name}".
        User Question: "{question}"

        Data Retrieved (JSON):
        {data_context}

        Analyze the data and provide a helpful, natural language answer.
        If the data is empty or indicates failure, explain that clearly.
        """

        response = await model.ainvoke(prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        usage = getattr(response, "usage_metadata", {})

        return response_text, usage
    except Exception as e:
        logging.error(f"Error generating reason: {e}")
        return "I found the data but couldn't generate a summary at this moment.", {}


# --- Endpoints ---


@app.get("/")
async def root():
    return {"message": "Sherlock Backend is running"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/enabled_models")
async def get_enabled_models():
    """Return list of available model IDs."""
    return list(models_dict.keys())


@app.post("/generate_title")
async def generate_title(request: QueryRequest):
    """
    Generates a chat title. Fails gracefully if LLM is down.
    """
    try:
        # Use Llama 3 8B (AWS) for fast title generation, fallback to Groq if needed
        model = llama3_8b if llama3_8b else llama_groq

        if not model:
            logging.warning(
                "No model available for title generation. Returning default."
            )
            return {"title": "New Chat"}

        logging.info(f"Generating title for: {request.question}")
        formatted_prompt = TITLE_GENERATION_PROMPT.format(question=request.question)

        # Async invoke
        response = await model.ainvoke(formatted_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Extract title
        title_match = re.search(r"ANSWER:\s*(.*)", response_text, re.DOTALL)
        title = (
            title_match.group(1).strip().strip('"').strip("'")
            if title_match
            else "New Chat"
        )

        return {"title": title}

    except Exception as e:
        # Log error but don't crash frontend flow
        logging.error(f"Error generating chat title: {e}")
        return {"title": "New Chat"}


@app.post("/general")
async def general(request: QueryRequest):
    if request.model_id not in models_dict:
        raise HTTPException(
            status_code=400, detail=f"Invalid model_id: {request.model_id}"
        )

    try:
        logging.info(f"General chat request. Model: {request.model_id}")
        formatted_prompt = GENERAL_CHAT_PROMPT.format(question=request.question)

        model = models_dict.get(request.model_id)

        # Async invoke
        response = await model.ainvoke(formatted_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Token usage calculation
        usage = getattr(response, "usage_metadata", {})
        input_tokens = usage.get("input_tokens", 0) + BUFFER_TOKENS
        output_tokens = usage.get("output_tokens", 0) + BUFFER_TOKENS

        pricing = get_pricing(request.model_id, input_tokens, output_tokens)

        # Extract answer
        answer_match = re.search(r"ANSWER:\s*(.*)", response_text, re.DOTALL)
        answer = answer_match.group(1).strip() if answer_match else response_text

        return {
            "answer": answer,
            "output": None,
            "chart": None,
            "sql": None,
            "python_code": None,
            "pricing": pricing,
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    except Exception as e:
        logging.exception("Error in general chat")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/autocomplete")
async def autocomplete_business(request: QueryRequestAutocomplete):
    """
    Provides business question suggestions.
    Returns empty list on failure or if disabled.
    """
    if not AUTOCOMPLETE_ENABLED:
        return {"completions": []}

    try:
        # Use Llama 3 8B (AWS) for fast autocomplete
        model = llama3_8b if llama3_8b else llama_groq

        if not model:
            logging.warning("No model available for autocomplete. Skipping.")
            return {"completions": []}

        formatted_prompt = AUTOCOMPLETE_BUSINESS_PROMPT.format(
            question=request.question
        )

        # Async invoke
        response = await model.ainvoke(formatted_prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Extract completions
        suggestions = re.findall(r"\d+\.\s*(.*)", response_text)
        return {"completions": suggestions[:5]}

    except Exception as e:
        logging.error(f"Error generating autocomplete: {e}")
        # Return empty list instead of 500 error
        return {"completions": []}


@app.post("/general_streaming")
async def general_streaming(request: QueryRequest):
    if request.model_id not in models_dict:
        raise HTTPException(
            status_code=400, detail=f"Invalid model_id: {request.model_id}"
        )

    try:
        model = models_dict.get(request.model_id)

        # We need an async generator wrapper for streaming response
        async def generate_chunks():
            yield "ANSWER:\n"
            # Note: Many LangChain models support async streaming via .astream
            if hasattr(model, "astream"):
                async for chunk in model.astream(request.question):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    else:
                        yield str(chunk)
            elif hasattr(model, "stream"):
                # Fallback to sync stream if async not available (blocking, but better than nothing)
                for chunk in model.stream(request.question):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    else:
                        yield str(chunk)
            else:
                yield "Streaming not supported for this model."

        return StreamingResponse(generate_chunks(), media_type="text/plain")

    except Exception as e:
        logging.exception("Error in streaming")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query(request: QueryRequest):
    logging.info(
        f"Received query request for seller: {request.seller_name}, App: {request.miniAppType}"
    )

    # Sanitize inputs to prevent JS serialization artifacts
    if str(request.seller_name) == "[object Object]":
        logging.warning("Sanitized [object Object] in seller_name to 'Unknown'")
        request.seller_name = "Unknown"

    if str(request.question) == "[object Object]":
        logging.warning("Sanitized [object Object] in question")
        raise HTTPException(status_code=400, detail="Invalid question: [object Object]")

    if request.model_id not in models_dict:
        raise HTTPException(
            status_code=400, detail=f"Invalid model_id: {request.model_id}"
        )

    try:
        # 1. Schema & Context Preparation
        # Determine tables based on miniAppType to save context window
        insta_tables = ["posts", "creators", "brands"]
        if request.miniAppType in ["INSTAGRAM_ANALYZER", "INSTAGRAM"]:
            schema_info = get_db_schema_summary(engine, target_tables=insta_tables)
        else:
            schema_info = get_db_schema_summary(engine)

        sample_data = get_sample_data(engine)

        # NOTE: Intent classification removed. We trust the frontend's miniAppType.

        # 2. Construct Prompt
        base_prompt = get_query_prompt(
            schema_info, sample_data, request.seller_name, request.miniAppType
        )
        base_prompt += f'\nThe user asked the following question about seller "{request.seller_name}":\n"{request.question}"\n'

        # Token Tracking
        total_tokens = 0
        total_input_tokens = 0
        total_output_tokens = 0

        # 3. Inner Pipeline Function (Async)
        async def run_pipeline(prompt_text, attempt_fix=False, error_msg=""):
            full_prompt = prompt_text
            if attempt_fix and error_msg:
                full_prompt += f"\nThe previous attempt failed with error:\n{error_msg}\nPlease correct the SQL/Python code."

            model_to_use = models_dict.get(request.model_id)

            # --- MCP / Agent Routing ---
            if request.miniAppType == "SCRAPING":
                async with client.session("AmazonBuyBoxScraper") as session:
                    tools = await load_mcp_tools(session)
                    agent = initialize_agent(
                        tools,
                        model_to_use,  # Or specific model if needed
                        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                        verbose=True,
                    )
                    response = await agent.ainvoke(full_prompt)

            elif request.miniAppType == "FRAUD_DETECTION":
                async with client.session("FraudDetection") as session:
                    tools = await load_mcp_tools(session)
                    agent = initialize_agent(
                        tools,
                        model_to_use,
                        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                        verbose=True,
                    )
                    response = await agent.ainvoke(full_prompt)

            elif request.miniAppType == "SEPHORA":
                async with client.session("SephoraService") as session:
                    tools = await load_mcp_tools(session)
                    agent = initialize_agent(
                        tools,
                        model_to_use,
                        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                        verbose=True,
                    )
                    response = await agent.ainvoke(full_prompt)

            elif request.miniAppType in ["INSTAGRAM_ANALYZER", "INSTAGRAM"]:
                async with client.session("InstagramService") as session:
                    tools = await load_mcp_tools(session)
                    agent = initialize_agent(
                        tools,
                        model_to_use,
                        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                        verbose=True,
                    )
                    response = await agent.ainvoke(full_prompt)
            else:
                # Check for Telecaller intent
                if (
                    "call" in request.question.lower()
                    or "telecall" in request.question.lower()
                ):
                    try:
                        async with client.session("TelecallerServer") as session:
                            tools = await load_mcp_tools(session)
                            agent = initialize_agent(
                                tools,
                                model_to_use,
                                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                                verbose=True,
                            )
                            response = await agent.ainvoke(full_prompt)
                    except Exception as e:
                        logging.warning(f"Telecaller error, falling back: {e}")
                        response = await model_to_use.ainvoke(full_prompt)
                else:
                    # Standard SQL/Data query
                    response = await model_to_use.ainvoke(full_prompt)

            # Process Response
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Update Tokens
            usage = getattr(response, "usage_metadata", {})
            t_in = usage.get("input_tokens", 0) + BUFFER_TOKENS
            t_out = usage.get("output_tokens", 0) + BUFFER_TOKENS

            nonlocal total_tokens, total_input_tokens, total_output_tokens
            total_input_tokens += t_in
            total_output_tokens += t_out
            total_tokens += t_in + t_out

            # Parse Output using Regex
            # Assuming standard format: ANSWER: ... SQL: ... PYTHON: ...
            answer_match = re.search(
                r"ANSWER:\s*(.*?)\s*(SQL:|$)", response_text, re.DOTALL
            )
            sql_match = re.search(
                r"SQL:\s*(.*?)\s*(PYTHON:|$)", response_text, re.DOTALL
            )
            py_match = re.search(r"PYTHON:\s*(.*)", response_text, re.DOTALL)

            reasoning_text = (
                answer_match.group(1).strip() if answer_match else response_text
            )
            sql_code_text = sql_match.group(1).strip().strip("`") if sql_match else ""
            py_code_text = py_match.group(1).strip().strip("`") if py_match else ""

            return reasoning_text, sql_code_text, py_code_text

        # 4. Execute Pipeline
        reasoning, sql_code, py_code = await run_pipeline(base_prompt)

        df = None
        encoded_img = None

        # 5. SQL Execution with Retry
        if sql_code:
            for attempt in range(3):
                try:
                    logging.info(f"Executing SQL attempt {attempt + 1}")
                    with engine.begin() as conn:
                        # RLS Setup (Row Level Security)
                        if request.rls_context:
                            rls = request.rls_context
                            conn.execute(
                                text(
                                    f"SET LOCAL app.user_role = '{rls.get('user_role', 'user')}'"
                                )
                            )
                            if rls.get("company_id"):
                                conn.execute(
                                    text(
                                        f"SET LOCAL app.current_company_id = '{rls.get('company_id')}'"
                                    )
                                )

                            # Set Allowed Categories
                            allowed_cats = rls.get("allowed_categories", [])
                            if allowed_cats:
                                if "*" in allowed_cats:
                                    cats_json = '["*"]'
                                else:
                                    # Format as JSON string for RLS policy (expecting jsonb array)
                                    cats_json = json.dumps(allowed_cats)

                                safe_json = cats_json.replace("'", "''")
                                conn.execute(
                                    text(
                                        f"SET LOCAL app.allowed_categories = '{safe_json}'"
                                    )
                                )

                            # Set Allowed Locations
                            allowed_locs = rls.get("allowed_locations", [])
                            if allowed_locs:
                                if "*" in allowed_locs:
                                    locs_json = '["*"]'
                                else:
                                    # Format as JSON string for RLS policy (expecting jsonb array)
                                    locs_json = json.dumps(allowed_locs)

                                safe_loc_json = locs_json.replace("'", "''")
                                conn.execute(
                                    text(
                                        f"SET LOCAL app.allowed_locations = '{safe_loc_json}'"
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
                    logging.info(f"SQL Success. Rows: {len(df)}")
                    break
                except Exception as sql_e:
                    logging.warning(f"SQL Attempt {attempt + 1} failed: {sql_e}")
                    if attempt < 2:
                        reasoning, sql_code, py_code = await run_pipeline(
                            base_prompt, attempt_fix=True, error_msg=str(sql_e)
                        )
                    else:
                        # Don't crash, just report error in reasoning
                        reasoning += (
                            f"\n\n(Note: Failed to execute data query: {str(sql_e)})"
                        )

        # 6. Python Execution with Retry (for Charts)
        if py_code and df is not None and not df.empty:
            for attempt in range(3):
                try:
                    # Prepare Safe Exec Environment
                    exec_env = {
                        "df": truncate_dataframe(df),
                        "plt": plt,
                        "pd": pd,
                        "np": np,
                    }
                    py_code_clean = py_code.replace("plt.show()", "")

                    exec(py_code_clean, exec_env)

                    fig = plt.gcf()
                    if fig and fig.get_axes():
                        buf = io.BytesIO()
                        plt.savefig(buf, format="png")
                        buf.seek(0)
                        encoded_img = base64.b64encode(buf.read()).decode("utf-8")
                        buf.close()
                        plt.close(fig)
                        logging.info("Chart generated successfully")
                    break
                except Exception as py_e:
                    logging.warning(f"Python Attempt {attempt + 1} failed: {py_e}")
                    if attempt < 2:
                        reasoning, sql_code, py_code = await run_pipeline(
                            base_prompt, attempt_fix=True, error_msg=str(py_e)
                        )

        # 7. Final Formatting & Summarization
        output_dict = None
        if df is not None:
            # Clean dataframe for JSON serialization
            df.replace([np.inf, -np.inf], np.nan, inplace=True)
            df = df.astype(object).fillna("null")

            # Remove sensitive or tech columns like ID if preferred, though usually ID is useful
            # df = df.loc[:, ~df.columns.str.contains("^id$")]

            # Format dates
            df = df.map(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x)

            output_dict = truncate_dataframe(df).to_dict(orient="records")

            # If we have data, we might want to re-summarize it to make sure the answer matches the data
            if request.miniAppType in ["BBCHAMPS", "SCRAPING"]:
                summ_reason, summ_usage = await generate_reason(
                    request.question,
                    request.model_id,
                    json.dumps(output_dict)[:10000],  # Limit context size
                    request.seller_name,
                )
                reasoning = (
                    summ_reason  # Replace initial reasoning with data-aware reasoning
                )
                total_tokens += summ_usage.get("total_tokens", 0)

        # 8. Pricing
        pricing = get_pricing(request.model_id, total_input_tokens, total_output_tokens)

        return {
            "answer": reasoning,
            "output": output_dict,
            "chart": encoded_img,
            "sql": sql_code if sql_code else None,
            "python_code": py_code if py_code else None,
            "pricing": pricing,
            "miniAppType": request.miniAppType,
            "token_usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
            },
        }

    except Exception as e:
        logging.exception("Critical error in query endpoint")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
