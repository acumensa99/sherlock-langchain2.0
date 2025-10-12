# BuyScout - Amazon Intelligence Suite

BuyScout is a comprehensive Amazon e-commerce intelligence platform that provides automated product scraping, competitive analysis, fraud detection, and business insights.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BuyScout Services                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ MCP Scraper │    │ Fraud Detect│    │Redis Worker │              │
│  │ Port: 8001  │    │ Port: 8002  │    │ Background  │              │
│  │             │    │             │    │ Processor   │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  Playwright │    │    Redis    │    │ PostgreSQL  │              │
│  │  Browsers   │    │   Pub/Sub   │    │  Database   │              │
│  │             │    │   Queue     │    │   Models    │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Service Components

### 1. **MCP Scraper Server** (`mcp_server.py`)
- **Port**: 8001
- **Purpose**: Amazon ASIN data extraction via MCP protocol
- **Features**:
  - Async Redis pub/sub messaging
  - ASIN batch processing
  - Real-time scraping status updates
  - Queue management and completion tracking

### 2. **Fraud Detection Server** (`mcp_fraud_server.py`)
- **Port**: 8002
- **Purpose**: Phone number verification across e-commerce platforms
- **Features**:
  - Playwright-based browser automation
  - Stealth browsing with proxy support
  - Amazon & Flipkart account association checks
  - Anti-detection mechanisms

### 3. **Redis Worker** (`server.py`)
- **Purpose**: Background job processor for async tasks
- **Features**:
  - Listens to Redis pub/sub channels
  - Processes ASIN scraping requests
  - Orchestrates scraping workflows
  - Publishes completion notifications

### 4. **Main Orchestrator** (`main.py`)
- **Purpose**: Complete workflow automation
- **Features**:
  - Storefront product discovery
  - ASIN extraction and processing
  - Data export to Excel
  - Email notifications

## 🔄 Data Flow Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client    │───▶│  MCP Scraper    │───▶│   Redis Queue   │
│   Request   │    │  (Port 8001)    │    │   Publishing    │
└─────────────┘    └─────────────────┘    └─────────────────┘
                            │                       │
                            ▼                       ▼
                   ┌─────────────────┐    ┌─────────────────┐
                   │ Status Updates  │    │ Redis Worker    │
                   │ & Notifications │    │ (server.py)     │
                   └─────────────────┘    └─────────────────┘
                            │                       │
                            ▼                       ▼
                   ┌─────────────────┐    ┌─────────────────┐
                   │   Client Gets   │    │   Playwright    │
                   │  Scraped Data   │    │   Scraping      │
                   └─────────────────┘    └─────────────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │   Database      │
                                          │   Storage       │
                                          └─────────────────┘
```

## 🗃️ Database Models

### Product Model (`models/product.py`)
```python
class Product(BaseModel):
    id = AutoField(primary_key=True)
    batch_no = BigIntegerField(null=True)
    data_asin = CharField()                 # Amazon ASIN
    price = FloatField(null=True)           # Current price
    brand_name = CharField(null=True)       # Product brand
    delivery_time = CharField(null=True)    # Estimated delivery
    winning_seller = CharField(null=True)   # Buybox winner
    seller_rating = FloatField(null=True)   # Seller rating
    other_sellers = JSONField(null=True)    # Alternative sellers
    best_seller_rating = JSONField(null=True) # Best seller data
    category = CharField(null=True)         # Product category
    pincode = CharField(null=True)          # Location pincode
    latitude = FloatField(null=True)        # Geo coordinates
    longitude = FloatField(null=True)
    created_at_p = DateTimeField(default=datetime.datetime.now)
```

### Seller Model (`models/seller.py`)
```python
class Seller(BaseModel):
    id = AutoField(primary_key=True)
    seller_name = CharField(unique=True)
    storefront_url = CharField(null=True)
    total_products = IntegerField(default=0)
    avg_rating = FloatField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
```

### Storefront Model (`models/storefront.py`)
```python
class Storefront(BaseModel):
    id = AutoField(primary_key=True)
    seller_name = CharField()
    storefront_url = CharField()
    page_number = IntegerField()
    total_products_found = IntegerField(null=True)
    scraped_at = DateTimeField(default=datetime.datetime.now)
```

## 🛠️ Core Features

### 1. **Amazon Product Scraping**
- **ASIN Extraction**: Automated product identifier collection
- **Price Monitoring**: Real-time price tracking
- **Buybox Analysis**: Winning seller identification
- **Competitive Intelligence**: Multi-seller comparison
- **Geographic Pricing**: Location-based price variations

### 2. **Fraud Detection**
- **Phone Verification**: Cross-platform account checking
- **Stealth Operations**: Anti-detection browser automation
- **Proxy Support**: Geo-distributed verification
- **Platform Coverage**: Amazon, Flipkart integration

### 3. **Workflow Automation**
- **Batch Processing**: Bulk ASIN handling
- **Queue Management**: Redis-based job distribution
- **Email Reports**: Automated result delivery
- **Excel Export**: Structured data reporting

### 4. **Real-time Processing**
- **Async Operations**: Non-blocking request handling
- **Status Tracking**: Real-time progress monitoring
- **Notification System**: Pub/sub event messaging
- **Error Recovery**: Automatic retry mechanisms

## 🚀 Usage Examples

### 1. **Scraping Product Data**
```python
import asyncio
from asin_scrapper.single_asin_scrapper import process_asins

# Process specific ASINs
await process_asins('output/product_asins.json', 'CompetitorName')

# Process ASINs dynamically
asins = ['B08N5WRWNW', 'B07XJ8C8F7', 'B09WD9XK3M']
await process_asins_dynamic(asins)
```

### 2. **Fraud Detection**
```python
# Via MCP tool (called through main API)
response = await check_amazon_flipkart_phone_number_fraud_detection(
    phone_number="+919876543210",
    topicId="fraud_check_123",
    userId="user_456"
)
```

### 3. **Complete Workflow**
```python
import asyncio
from main import run_full_flow

# Run complete competitive analysis
await run_full_flow("CompetitorSellerName")
```

### 4. **Manual Data Analysis**
```python
from chatbot import EcommerceAnalyzer

# Initialize analyzer
analyzer = EcommerceAnalyzer(model_name="llama3-8b-8192")

# Load data and analyze
data = get_seller_data("seller_name")
analyzer.load_data(data)

# Generate insights
insights = analyzer.generate_buybox_insights()
print(insights)

# Create visualizations
chart = analyzer.visualize_data("price_distribution")
```

## 📊 Output Formats

### 1. **JSON Data Structure**
```json
{
    "asin": "B08N5WRWNW",
    "price": 2999.00,
    "brand_name": "Samsung",
    "delivery_time": "Tomorrow by 10 AM",
    "winning_seller": "Amazon",
    "seller_rating": 4.5,
    "other_sellers": [
        {
            "name": "ElectroWorld",
            "price": 3199.00,
            "rating": 4.2,
            "delivery": "2-3 days"
        }
    ],
    "category": "Electronics > Smartphones",
    "location": {
        "pincode": "751024",
        "latitude": 20.2961,
        "longitude": 85.8245
    }
}
```

### 2. **Excel Export Structure**
- **Product Details**: ASIN, Brand, Category, Price
- **Seller Information**: Name, Rating, Delivery Time
- **Competitive Analysis**: Price Comparison, Market Position
- **Geographic Data**: Location-based Pricing Variations

### 3. **Fraud Detection Response**
```json
{
    "phone_number": "+919876543210",
    "platforms": {
        "amazon": {
            "status": "Present",
            "associated": true,
            "responseTimeMs": 1250
        },
        "flipkart": {
            "status": "Absent", 
            "associated": false,
            "responseTimeMs": 980
        }
    },
    "overall_risk": "Medium",
    "checked_at": "2025-01-XX 10:30:45"
}
```

## 🔧 Configuration

### Environment Variables
```bash
# Redis Configuration
REDIS_URL=redis://username:password@host:port

# Database Configuration  
DATABASE_URL=postgresql://user:pass@host:port/db

# Proxy Configuration (for fraud detection)
PROXY_URL=http://proxy-server:port
PROXY_CREDENTIALS=username:password

# Browser Configuration
HEADLESS_BROWSER=true
BROWSER_TIMEOUT=30000
```

### Systemd Service Configuration
```ini
# /etc/systemd/system/sherlock_mcp.service
[Unit]
Description=Sherlock BuyScout Amazon Scraper MCP Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/sherlock-langchain/buyscout
ExecStart=/home/ubuntu/sherlock-langchain/buyscout/.venv/bin/python -u mcp_server.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/mcp_server.log
StandardError=append:/home/ubuntu/logs/mcp_server.log
Environment=PYTHONPATH=/home/ubuntu/sherlock-langchain

[Install]
WantedBy=multi-user.target
```

## 📈 Performance Considerations

### 1. **Scraping Optimization**
- **Rate Limiting**: Intelligent request throttling
- **Concurrent Processing**: Multi-threaded ASIN handling
- **Caching Strategy**: Reduce redundant requests
- **Proxy Rotation**: Distribute load across IPs

### 2. **Database Optimization**
- **Indexing**: Optimized queries on ASIN and seller fields
- **Batch Inserts**: Bulk data insertion for performance
- **Connection Pooling**: Efficient database connections
- **Data Archival**: Historical data management

### 3. **Memory Management**
- **Browser Cleanup**: Proper Playwright resource disposal
- **Queue Monitoring**: Redis memory usage tracking
- **Garbage Collection**: Python memory optimization
- **Resource Limits**: Container/service constraints

## 🔍 Monitoring & Debugging

### Service Health Checks
```bash
# Check MCP server status
curl http://localhost:8001/health

# Monitor Redis queue
redis-cli LLEN process_asins_channel

# View scraping logs
tail -f /home/ubuntu/logs/mcp_server.log

# Check service status
systemctl status sherlock_mcp.service sherlock_fraud.service sherlock_server.service
```

### Performance Metrics
```bash
# Monitor scraping performance
grep "Processing time" /home/ubuntu/logs/mcp_server.log | tail -10

# Check fraud detection success rate
grep -c "Present\|Absent" /home/ubuntu/logs/fraud_server.log

# Monitor memory usage
ps aux | grep -E "(mcp_server|mcp_fraud|server\.py)"
```

## 🚦 API Integration

### MCP Tool Integration
BuyScout services integrate with the main Sherlock API through MCP (Model Context Protocol):

```python
# Main API automatically routes to BuyScout based on intent
POST /query
{
    "seller_name": "CompetitorName",
    "question": "Scrape prices for ASIN B08N5WRWNW",
    "model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "miniAppType": "SCRAPING"
}

# Fraud detection routing
POST /query  
{
    "seller_name": "SecurityTeam",
    "question": "Check fraud status for +919876543210",
    "model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "miniAppType": "FRAUD_DETECTION"
}
```

## 🔄 Maintenance Tasks

### Daily Operations
```bash
# Check queue health
redis-cli INFO keyspace

# Monitor scraping success rate
grep -c "SUCCESS\|FAILED" /home/ubuntu/logs/mcp_server.log

# Clean up old data
python3 -c "from models.queries import cleanup_old_data; cleanup_old_data(days=30)"
```

### Weekly Maintenance
```bash
# Update Playwright browsers
source .venv/bin/activate
playwright install

# Database maintenance
python3 -c "from models.base import database; database.execute_sql('VACUUM ANALYZE;')"

# Log rotation
sudo logrotate -f /etc/logrotate.d/sherlock
```

## 🔗 Related Documentation

- **Main Platform**: [../README.md](../README.md)
- **API Documentation**: [../docs/API.md](../docs/API.md)  
- **Deployment Guide**: [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)
- **Troubleshooting**: [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)

---

**Built for competitive intelligence and e-commerce automation by the Acumensa Team** 🚀
