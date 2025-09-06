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
import difflib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Bot with MiniApps", version="1.0.0")

# Twilio credentials (replace with your actual credentials)
TWILIO_ACCOUNT_SID = 'AC22598b35cb515baa0626d5f229889f9b'
TWILIO_AUTH_TOKEN = 'acd4223358f85b39ecf607b2e022cae8'
TWILIO_PHONE_NUMBER = 'whatsapp:+14155238886'  # Twilio sandbox number
TEMPLATE_SID = 'HXec689d802eb9363db0841348ed61e6cb'  # Your content template SID for responses
MENU_TEMPLATE_SID = 'HXb19107b3338fa68690021f6b6bd2448d'  # Your menu template SID for main menu
MESSAGING_SERVICE_SID = 'MG8a790e05621ae3a101f2a8a8ef60363f'  # Replace with your actual Messaging Service SID

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


async def send_template_message(to_number: str, response_content: str) -> dict:
    """Send a message using Twilio content template for responses"""
    try:
        # Ensure proper WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        # Clean and truncate the response content
        clean_content = truncate_message(response_content)
        #clean_content = "The phone number 8145874011 is present in our fraud detection database and is associated with Amazon and Flipkart accounts."
        print("CONTENT: ")
        print(clean_content)
        # Send message using content template - Correct API format
        message = client.messages.create(
            content_sid=TEMPLATE_SID,
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            content_variables=json.dumps({
                "1": clean_content  # Put response in {{2}} variable
            }),
            messaging_service_sid=MESSAGING_SERVICE_SID
        )
        
        logger.info(f"Template message sent successfully. SID: {message.sid}")
        return {
            "success": True,
            "message_sid": message.sid,
            "status": message.status
        }
        
    except Exception as e:
        logger.error(f"Error sending template message: {str(e)}")
        # Fallback to regular message if template fails
        try:
            logger.info("Attempting fallback to regular message...")
            fallback_message = client.messages.create(
                body=clean_content,
                from_=TWILIO_PHONE_NUMBER,
                to=to_number
            )
            logger.info(f"Fallback message sent successfully. SID: {fallback_message.sid}")
            return {
                "success": True,
                "message_sid": fallback_message.sid,
                "status": fallback_message.status,
                "fallback_used": True
            }
        except Exception as fallback_error:
            logger.error(f"Fallback message also failed: {str(fallback_error)}")
            return {
                "success": False,
                "error": str(e),
                "fallback_error": str(fallback_error)
            }


async def send_menu_template(to_number: str) -> dict:
    """Send the main menu using the menu template with buttons"""
    try:
        # Ensure proper WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        # Send menu using menu template
        message = client.messages.create(
            content_sid=MENU_TEMPLATE_SID,
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            messaging_service_sid=MESSAGING_SERVICE_SID
        )
        
        logger.info(f"Menu template message sent successfully. SID: {message.sid}")
        return {
            "success": True,
            "message_sid": message.sid,
            "status": message.status
        }
        
    except Exception as e:
        logger.error(f"Error sending menu template message: {str(e)}")
        # Fallback to regular message if template fails
        try:
            logger.info("Attempting fallback to regular menu message...")
            fallback_menu = """🤖 Welcome to the Bot! Choose a MiniApp:

🔹 BuyBox - Product recommendations
🔹 Scrapper - Web scraping services  
🔹 Fraud Detection - Security analysis
🔹 Default - General assistance

Reply with the MiniApp name to select it.
Type '/menu' anytime to return to this menu.
Type '/switch' to change miniapps."""

            fallback_message = client.messages.create(
                body=fallback_menu,
                from_=TWILIO_PHONE_NUMBER,
                to=to_number
            )
            logger.info(f"Fallback menu message sent successfully. SID: {fallback_message.sid}")
            return {
                "success": True,
                "message_sid": fallback_message.sid,
                "status": fallback_message.status,
                "fallback_used": True
            }
        except Exception as fallback_error:
            logger.error(f"Fallback menu message also failed: {str(fallback_error)}")
            return {
                "success": False,
                "error": str(e),
                "fallback_error": str(fallback_error)
            }


class MiniAppBot:
    def __init__(self):
        self.miniapps = {
            'buybox': 'buybox',
            'scrapper': 'scrapper',
            'fraud detection': 'fraud_detection',
            'default': 'default'
        }
        self.timeout = 50  # API call timeout

    def get_main_menu(self) -> str:
        return """🤖 Welcome to the Bot! Choose a MiniApp:

🔹 BuyBox - Product recommendations
🔹 Scrapper - Web scraping services  
🔹 Fraud Detection - Security analysis
🔹 Default - General assistance

Reply with the MiniApp name to select it.
Type '/menu' anytime to return to this menu.
Type '/switch' to change miniapps."""

    def normalize_message(self, message: str) -> str:
        """Normalize message to handle button responses"""
        message = re.sub(r'\*\*(.*?)\*\*', r'\1', message.strip().lower())
        return message

    def get_closest_miniapp(self, msg: str) -> Optional[str]:
        """Fuzzy match to handle variations in button/text input"""
        matches = difflib.get_close_matches(msg, self.miniapps.keys(), n=1, cutoff=0.8)
        return matches[0] if matches else None

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
                'last_activity': datetime.now()
            }

        user_sessions[user_id]['last_activity'] = datetime.now()

        # Handle commands
        if normalized_message in ['/menu', '/switch']:
            user_sessions[user_id]['current_miniapp'] = None
            return "", True
        elif normalized_message == '/status':
            current = user_sessions[user_id]['current_miniapp']
            return (
                f"📍 Currently using: {current.upper()} miniapp" if current
                else "⚠️ No miniapp selected. Type /menu to choose one.",
                False
            )
        elif normalized_message == '/help':
            return self.get_main_menu(), False

        # Check if selecting miniapp
        current_miniapp = user_sessions[user_id]['current_miniapp']
        if not current_miniapp:
            selected_app = self.miniapps.get(normalized_message)
            if not selected_app:
                # Try fuzzy match
                match = self.get_closest_miniapp(normalized_message)
                if match:
                    selected_app = self.miniapps[match]
            if selected_app:
                user_sessions[user_id]['current_miniapp'] = selected_app
                return (
                    f"{selected_app.upper()} miniapp activated!",
                    False
                )
            else:
                return "", True  # Invalid miniapp, show menu

        # Handle miniapp query
        if current_miniapp == 'buybox':
            response = await self.handle_buybox_query(message, user_id)
        elif current_miniapp == 'scrapper':
            response = await self.handle_scrapper_query(message, user_id)
        elif current_miniapp == 'fraud_detection':
            response = await self.handle_fraud_detection_query(message, user_id)
        elif current_miniapp == 'default':
            response = await self.handle_default_query(message, user_id)
        else:
            response = "Unknown miniapp. Type /menu to restart."

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
                timeout=50
            )
            print(f"response_text: {response_text}")
        except asyncio.TimeoutError:
            response_text = "⏱️ Request took too long. Please try again."
            should_send_menu = False
            logger.warning(f"Timeout processing message: {incoming_msg}")

        logger.info(f"Generated response for {user_id}: should_send_menu={should_send_menu}")

        # Send appropriate message based on response type
        if should_send_menu:
            # Send menu template
            template_result = await send_menu_template(from_number)
            if template_result["success"]:
                logger.info(f"Menu template sent successfully to {user_id}. Message SID: {template_result['message_sid']}")
            else:
                logger.error(f"Failed to send menu template to {user_id}: {template_result.get('error')}")
        else:
            # Send regular response template
            template_result = await send_template_message(from_number, response_text)
            if template_result["success"]:
                logger.info(f"Response template sent successfully to {user_id}. Message SID: {template_result['message_sid']}")
            else:
                logger.error(f"Failed to send response template to {user_id}: {template_result.get('error')}")

        return ""

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        
        # Try to send error message using template
        try:
            await send_template_message(from_number, "❌ Sorry, I encountered an error. Please try again.")
        except:
            logger.error("Failed to send error message via template")
        
        # Return empty TwiML response
        resp = MessagingResponse()
        return str(resp)


@app.post("/send_message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Send a message to a WhatsApp number (for testing)"""
    try:
        to_number = request.to
        message_body = request.message

        # Ensure proper WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )

        return SendMessageResponse(
            success=True,
            message_sid=message.sid,
            status=message.status
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send_template_message")
async def send_template_message_endpoint(to: str, content: str):
    """Send a template message (for testing)"""
    try:
        result = await send_template_message(to, content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send_menu_template")
async def send_menu_template_endpoint(to: str):
    """Send a menu template message (for testing)"""
    try:
        result = await send_menu_template(to)
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
        available_miniapps=list(bot.miniapps.values())
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
        "message": "WhatsApp Bot with MiniApps API",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook (POST) - Handle incoming WhatsApp messages",
            "send_message": "/send_message (POST) - Send messages to WhatsApp",
            "send_template_message": "/send_template_message (POST) - Send template messages",
            "send_menu_template": "/send_menu_template (POST) - Send menu template",
            "status": "/status (GET) - Get bot status",
            "health": "/health (GET) - Health check",
            "docs": "/docs - Interactive API documentation"
        },
        "miniapps": list(bot.miniapps.values()),
        "template_sid": TEMPLATE_SID,
        "menu_template_sid": MENU_TEMPLATE_SID,
        "messaging_service_sid": MESSAGING_SERVICE_SID
    }


@app.get("/sessions")
async def get_sessions():
    """Get current user sessions (for debugging)"""
    return {
        "total_sessions": len(user_sessions),
        "sessions": {
            user_id: {
                "current_miniapp": session.get('current_miniapp'),
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
async def test_webhook(message: str = "BuyBox", test_number: str = "whatsapp:+1234567890"):
    """Test webhook processing with template message"""
    user_id = "test_user"

    try:
        response_text, should_send_menu = await asyncio.wait_for(
            bot.process_message(message, user_id),
            timeout=12
        )

        if should_send_menu:
            # Test sending menu template
            template_result = await send_menu_template(test_number)
            return {
                "original_message": message,
                "action": "menu_template_sent",
                "template_result": template_result
            }
        else:
            # Test sending response template
            template_result = await send_template_message(test_number, response_text)
            return {
                "original_message": message,
                "bot_response": response_text,
                "action": "response_template_sent",
                "template_result": template_result,
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
    print("🤖 WhatsApp Bot starting with FastAPI...")
    print("📱 Available MiniApps:", list(bot.miniapps.values()))
    print("🔗 Webhook endpoint: /webhook")
    print("📊 Status endpoint: /status")
    print("📚 API docs: http://localhost:8000/docs")
    print(f"📧 Response Template SID: {TEMPLATE_SID}")
    print(f"📋 Menu Template SID: {MENU_TEMPLATE_SID}")
    print(f"📨 Messaging Service SID: {MESSAGING_SERVICE_SID}")

    # Run the FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
