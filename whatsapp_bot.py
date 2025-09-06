from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import httpx
import json
import re
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
import uvicorn

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Bot with MiniApps", version="1.0.0")

# Twilio credentials (replace with your actual credentials)
TWILIO_ACCOUNT_SID = 'AC22598b35cb515baa0626d5f229889f9b'
TWILIO_AUTH_TOKEN = 'acd4223358f85b39ecf607b2e022cae8'
TWILIO_PHONE_NUMBER = 'whatsapp:+14155238886'  # Twilio sandbox number

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# User session storage (in production, use Redis or a database)
user_sessions: Dict[str, Dict] = {}


# Pydantic models for request/response validation
class SendMessageRequest(BaseModel):
    to: str
    message: str


class SendMessageResponse(BaseModel):
    success: bool
    message_sid: str
    status: str


class StatusResponse(BaseModel):
    status: str
    active_sessions: int
    miniapp_usage: Dict[str, int]
    available_miniapps: list


class HealthResponse(BaseModel):
    status: str
    timestamp: str


def clean_message_for_whatsapp(message: str) -> str:
    """Clean message for WhatsApp: remove markdown, brackets, bullets, and newlines"""

    # Remove markdown formatting
    message = re.sub(r'\*\*(.*?)\*\*', r'\1', message)  # bold
    message = re.sub(r'\*(.*?)\*', r'\1', message)      # italic
    message = re.sub(r'`(.*?)`', r'\1', message)        # code

    # Remove all types of brackets
    message = re.sub(r'[\{\}\[\]\(\)<>]', '', message)

    # Replace bullets with dashes
    message = re.sub(r'[•▪◦]', '-', message)

    # Replace all newlines (actual and escaped)
    message = re.sub(r'(\\[rn]|[\r\n\u2028\u2029])+', ' ', message)

    # Collapse extra spaces
    message = re.sub(r'\s+', ' ', message).strip()

    return message


def truncate_message(message: str, max_length: int = 1600) -> str:
    """Truncate message if it exceeds WhatsApp limits"""
    # First clean the message
    message = clean_message_for_whatsapp(message)

    if len(message) <= max_length:
        return message

    # Truncate and add indicator
    truncated = message[:max_length - 50]
    return truncated + "\n\n... (message truncated due to length)"


async def send_plain_message(to_number: str, message_content: str) -> dict:
    """Send a plain text message via Twilio"""
    try:
        # Ensure proper WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        # Clean and truncate the message content
        clean_content = truncate_message(message_content)
        print("CONTENT: ")
        print(clean_content)
        
        # Send regular message
        message = client.messages.create(
            body=clean_content,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )
        
        logger.info(f"Plain message sent successfully. SID: {message.sid}")
        return {
            "success": True,
            "message_sid": message.sid,
            "status": message.status
        }
        
    except Exception as e:
        logger.error(f"Error sending plain message: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def send_menu_message(to_number: str) -> dict:
    """Send the main menu with numbered options"""
    menu_text = """🤖 Welcome to the Bot! Choose a MiniApp:

1. BuyBox - Product recommendations
2. Scrapper - Web scraping services  
3. Fraud Detection - Security analysis
4. Default - General assistance

Reply with 1, 2, 3, or 4 to select a MiniApp.

Commands:
- Type 'menu' to return to this menu
- Type 'switch' to change miniapps
- Type 'status' to see current miniapp"""

    return await send_plain_message(to_number, menu_text)


class MiniAppBot:
    def __init__(self):
        self.miniapps = {
            '1': ('buybox', 'BuyBox'),
            '2': ('scrapper', 'Scrapper'),
            '3': ('fraud detection', 'Fraud Detection'),
            '4': ('default', 'Default')
        }
        self.timeout = 5000  # API call timeout

    def get_main_menu(self) -> str:
        return """🤖 Welcome to the Bot! Choose a MiniApp:

1. BuyBox - Product recommendations
2. Scrapper - Web scraping services  
3. Fraud Detection - Security analysis
4. Default - General assistance

Reply with 1, 2, 3, or 4 to select a MiniApp.

Commands:
- Type 'menu' to return to this menu
- Type 'switch' to change miniapps
- Type 'status' to see current miniapp"""

    def normalize_message(self, message: str) -> str:
        """Normalize message to handle user input"""
        return message.strip().lower()

    async def make_api_call(self, url: str, payload: dict) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                response_json = response.json()
                logger.info(f"API Response: {response_json}")
                return response_json.get("answer", "❌ No valid response from API.")
        except httpx.TimeoutException:
            logger.warning(f"API call timeout for URL: {url}")
            return "⏱️ Request timeout. Please try again."
        except httpx.RequestError as e:
            logger.error(f"Connection error: {e}")
            return f"❌ Connection error: {e}"
        except Exception as e:
            logger.error(f"Error in API call: {e}")
            return f"❌ Error: {e}"

    async def handle_buybox_query(self, query: str, user_id: str) -> str:
        return await self.make_api_call("http://0.0.0.0:8000/query", {
            "seller_name": "Clicktech Retail",
            "question": query,
            "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
            "miniAppType": "BBCHAMPS"
        })

    async def handle_scrapper_query(self, query: str, user_id: str) -> str:
        return await self.make_api_call("http://0.0.0.0:8000/query", {
            "seller_name": "Clicktech Retail",
            "question": query,
            "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
            "miniAppType": "SCRAPPER"
        })

    async def handle_fraud_detection_query(self, query: str, user_id: str) -> str:
        return await self.make_api_call("http://0.0.0.0:8000/query", {
            "seller_name": "Clicktech Retail",
            "question": query,
            "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
            "miniAppType": "FRAUD_DETECTION"
        })

    async def handle_default_query(self, query: str, user_id: str) -> str:
        return await self.make_api_call("http://0.0.0.0:8000/general", {
            "seller_name": "Clicktech Retail",
            "question": query + ' KEEP THE RESPONSE VERY SHORT AND CONCISE',
            "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
            "miniAppType": "DEFAULT"
        })

    async def process_message(self, message: str, user_id: str) -> tuple[str, bool]:
        message = message.strip()
        normalized_message = self.normalize_message(message)

        logger.info(f"Normalized message: '{normalized_message}'")

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                'current_miniapp': None,
                'current_miniapp_name': None,
                'last_activity': datetime.now()
            }

        user_sessions[user_id]['last_activity'] = datetime.now()

        # Handle commands
        if normalized_message in ['menu', 'switch']:
            user_sessions[user_id]['current_miniapp'] = None
            user_sessions[user_id]['current_miniapp_name'] = None
            return "", True  # Show menu
        elif normalized_message == 'status':
            current = user_sessions[user_id].get('current_miniapp_name')
            return (
                f"📍 Currently using: {current} miniapp\n\nType 'menu' to change miniapps." if current
                else "⚠️ No miniapp selected. Type 'menu' to choose one.",
                False
            )
        elif normalized_message == 'help':
            return self.get_main_menu(), False

        # Check if selecting miniapp by number
        current_miniapp = user_sessions[user_id]['current_miniapp']
        if not current_miniapp:
            if normalized_message in self.miniapps:
                miniapp_id, miniapp_name = self.miniapps[normalized_message]
                user_sessions[user_id]['current_miniapp'] = miniapp_id
                user_sessions[user_id]['current_miniapp_name'] = miniapp_name
                return (
                    f"✅ {miniapp_name} miniapp activated!\n\nYou can now ask questions related to {miniapp_name.lower()}.\n\nType 'menu' anytime to switch miniapps.",
                    False
                )
            else:
                return "❌ Invalid option. Please reply with 1, 2, 3, or 4 to select a miniapp.", True

        # Handle miniapp query
        if current_miniapp == 'buybox':
            response = await self.handle_buybox_query(message, user_id)
        elif current_miniapp == 'scrapper':
            response = await self.handle_scrapper_query(message, user_id)
        elif current_miniapp == 'fraud detection':
            response = await self.handle_fraud_detection_query(message, user_id)
        elif current_miniapp == 'default':
            response = await self.handle_default_query(message, user_id)
        else:
            response = "❌ Unknown miniapp. Type 'menu' to restart."

        return response, False

# Initialize the bot
bot = MiniAppBot()


@app.post("/webhook", response_class=PlainTextResponse)
async def webhook(
        Body: str = Form(...),
        From: str = Form(...),
        To: Optional[str] = Form(None)
):
    """Handle incoming WhatsApp messages and send appropriate response"""
    try:
        # Get the message details
        incoming_msg = Body.strip()
        from_number = From
        user_id = from_number.replace('whatsapp:', '')

        logger.info(f"Received message from {user_id}: {incoming_msg}")

        # Process the message with timeout
        try:
            response_text, should_send_menu = await asyncio.wait_for(
                bot.process_message(incoming_msg, user_id),
                timeout=500
            )
            print(f"response_text: {response_text}")
        except asyncio.TimeoutError:
            response_text = "⏱️ Request took too long. Please try again."
            should_send_menu = False
            logger.warning(f"Timeout processing message: {incoming_msg}")

        logger.info(f"Generated response for {user_id}: should_send_menu={should_send_menu}")

        # Send appropriate message based on response type
        if should_send_menu:
            # Send menu message
            menu_result = await send_menu_message(from_number)
            if menu_result["success"]:
                logger.info(f"Menu sent successfully to {user_id}. Message SID: {menu_result['message_sid']}")
            else:
                logger.error(f"Failed to send menu to {user_id}: {menu_result.get('error')}")
        else:
            # Send regular response
            message_result = await send_plain_message(from_number, response_text)
            if message_result["success"]:
                logger.info(f"Response sent successfully to {user_id}. Message SID: {message_result['message_sid']}")
            else:
                logger.error(f"Failed to send response to {user_id}: {message_result.get('error')}")

        return ""

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        
        # Try to send error message
        try:
            await send_plain_message(from_number, "❌ Sorry, I encountered an error. Please try again or type 'menu' to restart.")
        except:
            logger.error("Failed to send error message")
        
        # Return empty TwiML response
        resp = MessagingResponse()
        return str(resp)


@app.post("/send_message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Send a message to a WhatsApp number (for testing)"""
    try:
        result = await send_plain_message(request.to, request.message)
        if result["success"]:
            return SendMessageResponse(
                success=True,
                message_sid=result["message_sid"],
                status=result["status"]
            )
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send_plain_message")
async def send_plain_message_endpoint(to: str, content: str):
    """Send a plain message (for testing)"""
    try:
        result = await send_plain_message(to, content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send_menu")
async def send_menu_endpoint(to: str):
    """Send a menu message (for testing)"""
    try:
        result = await send_menu_message(to)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get bot status and active sessions"""
    active_sessions = len(user_sessions)
    miniapp_usage = {}

    for user_id, session in user_sessions.items():
        app = session.get('current_miniapp', 'none')
        miniapp_usage[app] = miniapp_usage.get(app, 0) + 1

    return StatusResponse(
        status='active',
        active_sessions=active_sessions,
        miniapp_usage=miniapp_usage,
        available_miniapps=[app[1] for app in bot.miniapps.values()]
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status='healthy',
        timestamp=datetime.now().isoformat()
    )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "WhatsApp Bot with MiniApps API - Plain Text Version",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook (POST) - Handle incoming WhatsApp messages",
            "send_message": "/send_message (POST) - Send messages to WhatsApp",
            "send_plain_message": "/send_plain_message (POST) - Send plain messages",
            "send_menu": "/send_menu (POST) - Send menu",
            "status": "/status (GET) - Get bot status",
            "health": "/health (GET) - Health check",
            "docs": "/docs - Interactive API documentation"
        },
        "miniapps": [app[1] for app in bot.miniapps.values()],
        "menu_options": {
            "1": "BuyBox - Product recommendations",
            "2": "Scrapper - Web scraping services",
            "3": "Fraud Detection - Security analysis",
            "4": "Default - General assistance"
        }
    }


@app.get("/sessions")
async def get_sessions():
    """Get current user sessions (for debugging)"""
    return {
        "total_sessions": len(user_sessions),
        "sessions": {
            user_id: {
                "current_miniapp": session.get('current_miniapp'),
                "current_miniapp_name": session.get('current_miniapp_name'),
                "last_activity": session.get('last_activity').isoformat() if session.get('last_activity') else None
            }
            for user_id, session in user_sessions.items()
        }
    }


@app.delete("/sessions/{user_id}")
async def clear_user_session(user_id: str):
    """Clear a specific user's session"""
    if user_id in user_sessions:
        del user_sessions[user_id]
        return {"message": f"Session cleared for user {user_id}"}
    else:
        raise HTTPException(status_code=404, detail="User session not found")


@app.post("/test_webhook")
async def test_webhook(message: str = "1", test_number: str = "whatsapp:+1234567890"):
    """Test webhook processing with plain message"""
    user_id = "test_user"

    try:
        response_text, should_send_menu = await asyncio.wait_for(
            bot.process_message(message, user_id),
            timeout=12
        )

        if should_send_menu:
            # Test sending menu
            menu_result = await send_menu_message(test_number)
            return {
                "original_message": message,
                "action": "menu_sent",
                "menu_result": menu_result
            }
        else:
            # Test sending response
            message_result = await send_plain_message(test_number, response_text)
            return {
                "original_message": message,
                "bot_response": response_text,
                "action": "response_sent",
                "message_result": message_result,
                "response_length": len(response_text)
            }

    except Exception as e:
        return {"error": str(e)}


@app.delete("/sessions")
async def clear_all_sessions():
    """Clear all user sessions"""
    user_sessions.clear()
    return {"message": "All sessions cleared"}


if __name__ == '__main__':
    print("🤖 WhatsApp Bot starting with FastAPI (Plain Text Version)...")
    print("📱 Available MiniApps:")
    for num, (_, name) in bot.miniapps.items():
        print(f"   {num}. {name}")
    print("🔗 Webhook endpoint: /webhook")
    print("📊 Status endpoint: /status")
    print("📚 API docs: http://localhost:8000/docs")
    print("📝 Using plain text messages with numbered menu options")

    # Run the FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
