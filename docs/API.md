# API Documentation

## Main Service API (Port 8000)

The main service provides AI-powered data analytics and multi-service routing capabilities.

### Base URL
```
http://localhost:8000
```

---

## Endpoints

### 1. **POST /query**
Main analytics endpoint with intelligent routing based on intent classification.

#### Request Body
```json
{
    "seller_name": "string",      // Seller/company name for data filtering
    "question": "string",         // Natural language query
    "model_id": "string",         // LLM model identifier
    "miniAppType": "string"       // Service type: BBCHAMPS, SCRAPING, FRAUD_DETECTION
}
```

#### Supported Models
- `anthropic.claude-opus-4-20250514-v1:0`
- `anthropic.claude-sonnet-4-20250514-v1:0`
- `anthropic.claude-3-7-sonnet-20250219-v1:0`
- `deepseek.r1-v1:0`
- `meta.llama3-70b-instruct-v1:0`
- `meta.llama3-8b-instruct-v1:0`
- `llama3-70b-8192` (Groq)

#### Service Types
- **BBCHAMPS**: Database analytics and buybox analysis
- **SCRAPING**: Amazon product data extraction
- **FRAUD_DETECTION**: Phone number verification

#### Response
```json
{
    "answer": "string",           // Natural language response
    "output": "object[]",         // Structured data results
    "chart": "string",            // Base64 encoded chart image
    "sql": "string",              // Generated SQL query
    "python_code": "string",      // Generated Python visualization code
    "pricing": {                  // Cost breakdown
        "input_cost": "number",
        "output_cost": "number", 
        "total_cost": "number"
    },
    "miniAppType": "string",      // Resolved service type
    "token_usage": {              // Token consumption
        "input_tokens": "number",
        "output_tokens": "number",
        "total_tokens": "number"
    }
}
```

#### Example Usage

**Database Analytics Query:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "seller_name": "MyCompany",
    "question": "Show top 10 products by revenue",
    "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
    "miniAppType": "BBCHAMPS"
  }'
```

**Product Scraping Query:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "seller_name": "Competitor",
    "question": "Scrape price for ASIN B08N5WRWNW",
    "model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "miniAppType": "SCRAPING"
  }'
```

**Fraud Detection Query:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "seller_name": "Security",
    "question": "Check fraud status for +919876543210",
    "model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "miniAppType": "FRAUD_DETECTION"
  }'
```

---

### 2. **POST /general**
General AI assistant for non-analytics conversations.

#### Request Body
```json
{
    "seller_name": "string",      // Optional context
    "question": "string",         // General question
    "model_id": "string",         // LLM model identifier
    "miniAppType": "string"       // Can be any value
}
```

#### Response
```json
{
    "answer": "string",           // Formatted markdown response
    "output": null,
    "chart": null,
    "sql": null,
    "python_code": null,
    "pricing": {
        "input_cost": "number",
        "output_cost": "number",
        "total_cost": "number"
    },
    "token_usage": {
        "input_tokens": "number",
        "output_tokens": "number", 
        "total_tokens": "number"
    }
}
```

---

### 3. **POST /general-streaming**
Streaming version of general AI assistant.

#### Request Body
Same as `/general`

#### Response
Server-Sent Events (SSE) stream with `text/plain` content.

#### Example Usage
```javascript
const response = await fetch('/general-streaming', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        question: "Explain machine learning",
        model_id: "anthropic.claude-sonnet-4-20250514-v1:0"
    })
});

const reader = response.body.getReader();
while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    console.log(new TextDecoder().decode(value));
}
```

---

### 4. **POST /generate_title**
Generate descriptive titles for chat conversations.

#### Request Body
```json
{
    "seller_name": "string",      // Optional context
    "question": "string",         // Question to generate title for
    "model_id": "string",         // LLM model identifier
    "miniAppType": "string"       // Can be any value
}
```

#### Response
```json
{
    "title": "string"             // Generated chat title
}
```

---

### 5. **POST /autocomplete**
Business-focused query autocomplete suggestions.

#### Request Body
```json
{
    "question": "string"          // Partial question
}
```

#### Response
```json
{
    "completions": [              // Array of suggested completions
        "string",
        "string",
        "string",
        "string", 
        "string"
    ]
}
```

#### Example
```bash
curl -X POST "http://localhost:8000/autocomplete" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top"}'
```

---

### 6. **GET /enabled_models**
List all available LLM models.

#### Response
```json
{
    "models": [
        "anthropic.claude-opus-4-20250514-v1:0",
        "anthropic.claude-sonnet-4-20250514-v1:0",
        "anthropic.claude-3-7-sonnet-20250219-v1:0",
        "deepseek.r1-v1:0",
        "meta.llama3-70b-instruct-v1:0",
        "meta.llama3-8b-instruct-v1:0",
        "llama3-70b-8192"
    ]
}
```

---

## MCP Service APIs

### Amazon Scraper Service (Port 8001)
Accessible via MCP protocol through main service `/query` endpoint with `miniAppType: "SCRAPING"`.

**Tool**: `scrape_asins`
- **Input**: seller_name, product_asins[], topicId, userId
- **Output**: Scraped product data with prices, ratings, sellers

### Fraud Detection Service (Port 8002)  
Accessible via MCP protocol through main service `/query` endpoint with `miniAppType: "FRAUD_DETECTION"`.

**Tool**: `check_amazon_flipkart_phone_number_fraud_detection`
- **Input**: phone_number, topicId, userId
- **Output**: Account association status for Amazon and Flipkart

### Telecaller Service (Port 8006)
Accessible via MCP protocol when query contains "call" keyword.

**Tool**: `trigger_call`
- **Input**: phone_number (must start with +91)
- **Output**: Call initiation status

---

## Error Handling

### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (invalid model_id, malformed request)
- `500`: Internal Server Error (SQL/Python execution failures, LLM errors)

### Error Response Format
```json
{
    "detail": "string"            // Error description
}
```

### Common Errors
- **Invalid model_id**: Model not supported or misconfigured
- **SQL execution failed**: Database query syntax or permission errors  
- **Python execution failed**: Chart generation or data processing errors
- **MCP service unavailable**: External service connection issues

---

## Rate Limiting & Performance

### Token Limits
- DataFrames are automatically truncated to 5000 tokens for response optimization
- Messages are limited to prevent context overflow
- Chart generation has built-in timeouts

### Cost Optimization
- Automatic model routing based on query complexity
- Token usage tracking for cost monitoring
- Buffer tokens added for accurate cost calculation

### Retry Logic
- SQL queries: Up to 10 retry attempts with error feedback
- Python execution: Up to 6 retry attempts with error correction
- MCP services: Built-in connection retry and fallback

---

## Database Schema Access

The `/query` endpoint automatically provides:
- **Schema Information**: All table structures and column types
- **Sample Data**: First 3 rows from each table for context
- **Security**: Seller-based data filtering to prevent unauthorized access

### Supported SQL Operations
- SELECT queries with aggregations
- JOINs across multiple tables
- WHERE clauses with seller filtering
- ORDER BY and LIMIT clauses
- Date/time filtering and grouping

---

## Integration Examples

### Python SDK
```python
import requests

class SherlockClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def query(self, seller_name, question, model_id="anthropic.claude-sonnet-4-20250514-v1:0", miniapp_type="BBCHAMPS"):
        response = requests.post(f"{self.base_url}/query", json={
            "seller_name": seller_name,
            "question": question,
            "model_id": model_id,
            "miniAppType": miniapp_type
        })
        return response.json()
    
    def scrape_products(self, asins):
        return self.query("scraper", f"Scrape ASINs: {', '.join(asins)}", miniapp_type="SCRAPING")
    
    def detect_fraud(self, phone_number):
        return self.query("security", f"Check fraud for {phone_number}", miniapp_type="FRAUD_DETECTION")

# Usage
client = SherlockClient()
result = client.query("MyCompany", "Show revenue trends")
```

### JavaScript/Node.js
```javascript
class SherlockAPI {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
    }
    
    async query(sellerName, question, modelId = 'anthropic.claude-sonnet-4-20250514-v1:0', miniAppType = 'BBCHAMPS') {
        const response = await fetch(`${this.baseURL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                seller_name: sellerName,
                question: question,
                model_id: modelId,
                miniAppType: miniAppType
            })
        });
        return await response.json();
    }
    
    async getModels() {
        const response = await fetch(`${this.baseURL}/enabled_models`);
        return await response.json();
    }
}

// Usage
const sherlock = new SherlockAPI();
const result = await sherlock.query('MyCompany', 'Analyze sales performance');
```

---

## WebSocket Support (Future)
Currently, the API uses HTTP requests. WebSocket support for real-time streaming and bidirectional communication is planned for future releases.

---

## Authentication (Future)
Current version operates without authentication. API key-based authentication and role-based access control are planned for production deployment.
