from fastmcp import FastMCP
import json
import logging
from datetime import datetime
from redis.asyncio import from_url  # using redis-py asyncio
import httpx
from elevenlabs import ElevenLabs
REDIS_URL = "redis://default:8UJi1DyhMTXKCC0cA8cKH9Bc3tzuwg7w@redis-17846.crce217.ap-south-1-1.ec2.redns.redis-cloud.com:17846"
CHANNEL = "process_asins_channel"
COMPLETION_CHANNEL = "process_asins_completion_channel"
logging.basicConfig(level=logging.DEBUG)
mcp = FastMCP("TelecallerServer")

@mcp.tool
def trigger_call(phone_number: str) -> str:
    """Uses the ElevenLabs API to trigger a call to the given phone number. Used for telecaller purposes."""
    print(f"Received request for call to phone number: {phone_number}")


    client = ElevenLabs(
        api_key="sk_2c8e69efd0218df4e00aa69dd09acceb89cad2ed8240300b",
    )
    client.conversational_ai.twilio.outbound_call(
        agent_id="agent_4101k0vm612bfmvsn9zfw4pfmn2k",
        agent_phone_number_id="phnum_9601k0vm5nx0e5y9cpp439f5wfr9",
        to_number=phone_number,
    )
    return "Call request sent successfully"


if __name__ == "__main__":
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=8006,
        log_level="debug"
    )
