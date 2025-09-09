# Sherlock LangChain Backend

**Sherlock** is a comprehensive AI-powered data analytics and automation platform built with FastAPI and LangChain. It provides multiple services for data analysis, Amazon product scraping, fraud detection, and telecalling capabilities.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Sherlock Platform                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Main API  │    │  BuyScout   │    │  WhatsApp   │              │
│  │  Port: 8000 │    │  Services   │    │    Bot      │              │
│  │   (main.py) │    │   Various   │    │             │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ MCP Servers │    │   Redis     │    │ PostgreSQL  │              │
│  │ 8001, 8002, │    │   Queue     │    │  Database   │              │
│  │   8006      │    │             │    │             │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Services Overview

### 1. **Main API Service** (Port 8000)
- **File**: `main.py`
- **Purpose**: Central FastAPI application providing AI-powered data analytics
- **Features**:
  - Multi-LLM support (Claude, Llama, DeepSeek)
  - Database query generation and execution
  - Chart generation with matplotlib
  - Token tracking and cost calculation
  - Intent classification for routing requests

### 2. **BuyScout Services** (buyscout/)
Amazon product scraping and competitive analysis platform:

#### MCP Scraper Server (Port 8001)
- **File**: `buyscout/mcp_server.py`
- **Purpose**: Amazon ASIN scraping via MCP (Model Context Protocol)
- **Features**: Async Redis pub/sub, ASIN processing queue

#### MCP Fraud Detection Server (Port 8002)
- **File**: `buyscout/mcp_fraud_server.py`  
- **Purpose**: Phone number verification across Amazon/Flipkart
- **Features**: Playwright automation, proxy support, stealth browsing

#### Telecaller Server (Port 8006)
- **File**: `mcp_telecaller_server.py`
- **Purpose**: Automated calling via ElevenLabs API
- **Features**: Voice AI integration, call triggering

### 3. **WhatsApp Bot Service**
- **File**: `whatsapp_bot.py`
- **Purpose**: WhatsApp integration via Twilio
- **Features**: Multi-app routing, session management, message handling

## 📊 Data Flow Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Client    │───▶│   Main API      │───▶│ Intent Classifier│
│   Request   │    │   (Port 8000)   │    │   (LLM Based)    │
└─────────────┘    └─────────────────┘    └──────────────────┘
                            │                       │
                            ▼                       ▼
                   ┌─────────────────┐    ┌─────────────────┐
                   │   Database      │    │   MCP Servers   │
                   │   Queries       │    │  (8001/8002/    │
                   │   & Analysis    │    │      8006)      │
                   └─────────────────┘    └─────────────────┘
                            │                       │
                            ▼                       ▼
                   ┌─────────────────┐    ┌─────────────────┐
                   │ Chart Generation│    │ External APIs   │
                   │   & Response    │    │ (Amazon/Redis/  │
                   │   Formatting    │    │  ElevenLabs)    │
                   └─────────────────┘    └─────────────────┘
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file with:
```env
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# LLM APIs
GROQ_API_KEY=your_groq_api_key

# AWS Bedrock (for Claude models)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# Redis
REDIS_URL=redis://username:password@host:port

# Twilio (for WhatsApp)
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token

# ElevenLabs (for voice calls)
ELEVENLABS_API_KEY=your_elevenlabs_key
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Redis server
- AWS credentials (for Bedrock models)

### Installation
```bash
# Clone the repository
git clone https://github.com/acumensa99/sherlock-langchain
cd sherlock-langchain

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run database migrations (if applicable)
# Setup your PostgreSQL database schema
```

### Running Services (Production Ubuntu Setup)

**Current Production Environment**: Ubuntu with systemd services

1. **Check All Services Status**:
```bash
sudo systemctl status sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service
```

2. **Start All Services**:
```bash
sudo systemctl start sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service
```

3. **Restart All Services**:
```bash
sudo systemctl restart sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service
```

4. **View Service Logs**:
```bash
# Real-time logs
tail -f /home/ubuntu/logs/main.log
tail -f /home/ubuntu/logs/mcp_telecaller_server.log
tail -f /home/ubuntu/logs/server.log
tail -f /home/ubuntu/logs/fraud_server.log
tail -f /home/ubuntu/logs/mcp_server.log

# Service logs via systemctl
sudo journalctl -u sherlock_api.service -f
sudo journalctl -u sherlock_telecaller.service -f
```

### Service Port Mapping
```
sherlock_api         → Port 8000 (Main FastAPI application)
sherlock_mcp         → Port 8001 (Amazon scraper MCP server)
sherlock_fraud       → Port 8002 (Fraud detection MCP server) 
sherlock_telecaller  → Port 8006 (Telecaller MCP server)
sherlock_server      → Background worker (Redis listener, no port)
```

### Development Setup (Alternative)

For local development, you can also run services individually:

1. **Start Main API**:
```bash
cd /home/ubuntu/langchain_microservice
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

2. **Start BuyScout Services**:
```bash
cd /home/ubuntu/langchain_microservice/buyscout
source .venv/bin/activate

# Start scraper server
python mcp_server.py

# Start fraud detection server  
python mcp_fraud_server.py

# Start background worker
python server.py
```

3. **Start Telecaller Server**:
```bash
cd /home/ubuntu/langchain_microservice
source .venv/bin/activate
python mcp_telecaller_server.py
```

## 📁 Project Structure

```
sherlock-langchain/
├── README.md                      # This file
├── main.py                        # Main FastAPI application (Port 8000)
├── mcp_telecaller_server.py       # Telecaller MCP server (Port 8006)
├── token_tracking_class.py        # Token usage and cost tracking
├── whatsapp_bot.py               # WhatsApp integration service
├── requirements.txt              # Python dependencies
│
├── buyscout/                     # Amazon scraping & analysis suite
│   ├── README.md                 # BuyScout documentation
│   ├── main.py                   # BuyScout workflow orchestrator
│   ├── mcp_server.py            # Scraper MCP server (Port 8001)
│   ├── mcp_fraud_server.py      # Fraud detection server (Port 8002)
│   ├── server.py                # Redis listener for async processing
│   ├── chatbot.py               # Data analysis & insights engine
│   ├── db.py                    # Database connection utilities
│   │
│   ├── models/                  # Database models (Peewee ORM)
│   │   ├── base.py
│   │   ├── product.py
│   │   ├── seller.py
│   │   ├── storefront.py
│   │   └── ...
│   │
│   ├── asin_scrapper/           # Amazon ASIN scraping logic
│   │   └── single_asin_scrapper.py
│   │
│   ├── products_lister/         # Storefront product discovery
│   │   └── products_listing_scrapper.py
│   │
│   ├── workers/                 # Background job processors
│   │   ├── email_sender.py
│   │   └── update_products.py
│   │
│   ├── input/                   # Input data files
│   └── output/                  # Generated output files
│
└── docs/                        # Additional documentation
    ├── API.md                   # API endpoint documentation
    ├── DEPLOYMENT.md            # Deployment instructions
    └── TROUBLESHOOTING.md       # Common issues and solutions
```

## 🔑 Key Features

### 🤖 Multi-LLM Support
- **Groq**: Llama 3.3 70B (fast inference)
- **AWS Bedrock**: Claude Opus/Sonnet 4, DeepSeek R1, Llama models
- **Automatic routing**: Based on task complexity and requirements

### 📊 Data Analytics
- **SQL Generation**: Natural language to SQL conversion
- **Chart Creation**: Matplotlib-based visualizations
- **Data Insights**: AI-powered analysis and recommendations

### 🛒 E-commerce Intelligence
- **Product Scraping**: Amazon ASIN data extraction
- **Competitive Analysis**: Price monitoring and buybox tracking
- **Fraud Detection**: Phone number verification across platforms

### 🔄 Async Processing
- **Redis Queue**: Background job processing
- **MCP Protocol**: Model Context Protocol for service communication
- **Webhook Support**: Real-time notifications and updates

## 🔗 API Endpoints

### Main Service (Port 8000)
- `POST /query` - Main analytics endpoint
- `POST /general` - General AI chat
- `POST /generate_title` - Chat title generation
- `POST /autocomplete` - Business query suggestions
- `GET /enabled_models` - List available LLM models

### Service Health Checks
- `GET /health` - Service health status
- `GET /metrics` - Performance metrics

## 📈 Usage Examples

### Data Analytics Query
```python
import requests

response = requests.post("http://localhost:8000/query", json={
    "seller_name": "MyCompany",
    "question": "Show me top 10 products by revenue this month",
    "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
    "miniAppType": "BBCHAMPS"
})
```

### Product Scraping
```python
# Triggers async scraping via MCP
response = requests.post("http://localhost:8000/query", json={
    "seller_name": "Competitor",
    "question": "Scrape prices for ASIN B08N5WRWNW",
    "model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "miniAppType": "SCRAPING"
})
```

### Fraud Detection
```python
# Check phone number across platforms
response = requests.post("http://localhost:8000/query", json={
    "seller_name": "Security",
    "question": "Check fraud status for +919876543210",
    "model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0", 
    "miniAppType": "FRAUD_DETECTION"
})
```

## 🛠️ Technology Stack

- **Framework**: FastAPI (Python)
- **AI/ML**: LangChain, AWS Bedrock, Groq
- **Database**: PostgreSQL with Peewee ORM
- **Queue**: Redis pub/sub
- **Scraping**: Playwright with stealth mode
- **Communication**: Twilio (WhatsApp), ElevenLabs (Voice)
- **Deployment**: Docker-ready, cloud-native

## 📞 Support

For issues and questions:
1. Check [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
2. Review logs in service terminals
3. Verify environment configuration
4. Contact development team

## 🔄 Development Workflow

1. **Local Development**: Run all services locally
2. **Testing**: Use individual service endpoints
3. **Monitoring**: Check Redis queues and database logs
4. **Deployment**: Follow [DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

**Built with ❤️ by the Acumensa Team**
