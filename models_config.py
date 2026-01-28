import logging
import os

from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
# Default to True for autocomplete, but allow disabling via env var
AUTOCOMPLETE_ENABLED = os.getenv("AUTOCOMPLETE", "True").lower() == "true"


def get_groq_model():
    """Initialize Groq model safely."""
    # Check for missing or dummy keys (e.g. empty string or very short)
    if not GROQ_API_KEY or len(str(GROQ_API_KEY)) < 10:
        logging.warning(
            "GROQ_API_KEY is missing or invalid. Groq-based features will be disabled."
        )
        return None
    try:
        return ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
        )
    except Exception as e:
        logging.error(f"Failed to initialize Groq model: {e}")
        return None


def get_bedrock_model(model_id, region_name="us-east-1"):
    """Initialize Bedrock model safely."""
    try:
        return ChatBedrock(
            model_id=model_id,
            region_name=region_name,
        )
    except Exception as e:
        logging.error(f"Failed to initialize Bedrock model {model_id}: {e}")
        return None


# Initialize Models
llama_groq = get_groq_model()

claude_opus_4 = get_bedrock_model("us.anthropic.claude-opus-4-20250514-v1:0")
claude_sonnet_4 = get_bedrock_model("us.anthropic.claude-sonnet-4-20250514-v1:0")
claude_3_7_sonnet = get_bedrock_model("us.anthropic.claude-3-7-sonnet-20250219-v1:0")
deepseek_r1 = get_bedrock_model("us.deepseek.r1-v1:0")
llama3_70b = get_bedrock_model("meta.llama3-70b-instruct-v1:0")
llama3_8b = get_bedrock_model("meta.llama3-8b-instruct-v1:0")

# Model Dictionary Registry
models_dict = {
    # If Groq is unavailable, fallback to Bedrock Llama 3 (meta.llama3-70b-instruct-v1:0)
    "llama3-70b-8192": llama_groq if llama_groq is not None else llama3_70b,
    "anthropic.claude-opus-4-20250514-v1:0": claude_opus_4,
    "anthropic.claude-sonnet-4-20250514-v1:0": claude_sonnet_4,
    "anthropic.claude-3-7-sonnet-20250219-v1:0": claude_3_7_sonnet,
    "deepseek.r1-v1:0": deepseek_r1,
    "meta.llama3-70b-instruct-v1:0": llama3_70b,
    "meta.llama3-8b-instruct-v1:0": llama3_8b,
}
