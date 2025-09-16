# Deployment Guide

This guide covers deployment strategies for the Sherlock LangChain platform across different environments.

## �️ Production Ubuntu Deployment (Current Setup)

### Current Production Architecture

The production system runs on Ubuntu with systemd services managing all components:

```
/home/ubuntu/langchain_microservice/
├── main.py                        # Main API service
├── mcp_telecaller_server.py       # Telecaller service  
├── .venv/                         # Python virtual environment
├── buyscout/
│   ├── server.py                  # Redis listener/worker
│   ├── mcp_server.py              # Amazon scraper MCP server
│   ├── mcp_fraud_server.py        # Fraud detection MCP server
│   └── .venv/                     # BuyScout virtual environment
└── logs/                          # Service logs directory
```

### Systemd Services Configuration

#### 1. Main API Service
**File**: `/etc/systemd/system/sherlock_api.service`
```ini
[Unit]
Description=Sherlock Langchain FastAPI (uvicorn)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/langchain_microservice
ExecStart=/home/ubuntu/langchain_microservice/.venv/bin/uvicorn main:app --host 0.0.0.0
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/main.log
StandardError=append:/home/ubuntu/logs/main.log

[Install]
WantedBy=multi-user.target
```

#### 2. Telecaller Service
**File**: `/etc/systemd/system/sherlock_telecaller.service`
```ini
[Unit]
Description=Sherlock Langchain mcp_telecaller_server.py
After=network.target

[Service]
User=ubuntu
ExecStart=/home/ubuntu/langchain_microservice/.venv/bin/python -u /home/ubuntu/langchain_microservice/mcp_telecaller_server.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/mcp_telecaller_server.log
StandardError=append:/home/ubuntu/logs/mcp_telecaller_server.log

[Install]
WantedBy=multi-user.target
```

#### 3. Redis Worker Service
**File**: `/etc/systemd/system/sherlock_server.service`
```ini
[Unit]
Description=Sherlock Langchain server.py
After=network.target

[Service]
User=ubuntu
ExecStart=/home/ubuntu/langchain_microservice/buyscout/.venv/bin/python -u /home/ubuntu/langchain_microservice/buyscout/server.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/server.log
StandardError=append:/home/ubuntu/logs/server.log

[Install]
WantedBy=multi-user.target
```

#### 4. Fraud Detection Service
**File**: `/etc/systemd/system/sherlock_fraud.service`
```ini
[Unit]
Description=Sherlock Langchain mcp_fraud_server.py
After=network.target

[Service]
User=ubuntu
ExecStart=/home/ubuntu/langchain_microservice/buyscout/.venv/bin/python -u /home/ubuntu/langchain_microservice/buyscout/mcp_fraud_server.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/fraud_server.log
StandardError=append:/home/ubuntu/logs/fraud_server.log

[Install]
WantedBy=multi-user.target
```

#### 5. Amazon Scraper MCP Service
**File**: `/etc/systemd/system/sherlock_mcp.service`
```ini
[Unit]
Description=Sherlock Langchain mcp_server.py
After=network.target

[Service]
User=ubuntu
ExecStart=/home/ubuntu/langchain_microservice/buyscout/.venv/bin/python -u /home/ubuntu/langchain_microservice/buyscout/mcp_server.py
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/mcp_server.log
StandardError=append:/home/ubuntu/logs/mcp_server.log

[Install]
WantedBy=multi-user.target
```


#### 5. Whatsapp Bot Service
**File**: `/etc/systemd/system/sherlock_whatsapp_bot.service`
```ini
[Unit]
Description=Sherlock Whatsapp Bot (uvicorn)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/langchain_microservice
ExecStart=/home/ubuntu/langchain_microservice/.venv/bin/uvicorn whatsapp_bot:app --host 0.0.0.0 --port 8005
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/logs/whatsapp_bot.log
StandardError=append:/home/ubuntu/logs/whatsapp_bot.log

[Install]
WantedBy=multi-user.target
```

### Production Deployment Commands

#### Service Management
```bash
# Enable and start all services
sudo systemctl enable sherlock_api.service
sudo systemctl enable sherlock_telecaller.service
sudo systemctl enable sherlock_server.service
sudo systemctl enable sherlock_fraud.service
sudo systemctl enable sherlock_mcp.service
sudo systemctl enable sherlock_whatsapp_bot.service

# Start all services
sudo systemctl start sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service sherlock_whatsapp_bot.service

# Check service status
sudo systemctl status sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service sherlock_whatsapp_bot.service

# Restart all services
sudo systemctl restart sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service sherlock_whatsapp_bot.service

# Stop all services
sudo systemctl stop sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service sherlock_whatsapp_bot.service
```

#### Log Management
```bash
# View real-time logs
tail -f /home/ubuntu/logs/main.log
tail -f /home/ubuntu/logs/mcp_telecaller_server.log
tail -f /home/ubuntu/logs/server.log
tail -f /home/ubuntu/logs/fraud_server.log
tail -f /home/ubuntu/logs/mcp_server.log
tail -f /home/ubuntu/logs/sherlock_whatsapp_bot.log

# View service logs via systemctl
sudo journalctl -u sherlock_api.service -f
sudo journalctl -u sherlock_telecaller.service -f
sudo journalctl -u sherlock_server.service -f
sudo journalctl -u sherlock_fraud.service -f
sudo journalctl -u sherlock_mcp.service -f
sudo journalctl -u sherlock_whatsapp_bot.service -f

# Log rotation setup (add to crontab)
# 0 2 * * * /usr/sbin/logrotate /etc/logrotate.d/sherlock
```

#### Environment Setup
```bash
# Create logs directory
mkdir -p /home/ubuntu/logs

# Set up virtual environments
cd /home/ubuntu/langchain_microservice
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd /home/ubuntu/langchain_microservice/buyscout
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers for fraud detection
source /home/ubuntu/langchain_microservice/buyscout/.venv/bin/activate
playwright install chromium
playwright install-deps
```

### Service Port Mapping
```
sherlock_api         → Port 8000 (Main FastAPI application)
sherlock_mcp         → Port 8001 (Amazon scraper MCP server)
sherlock_fraud       → Port 8002 (Fraud detection MCP server)
sherlock_telecaller  → Port 8006 (Telecaller MCP server)
sherlock_server      → Background worker (Redis listener, no port)
```

### Production Monitoring Script

Create `/home/ubuntu/scripts/monitor_sherlock.sh`:
```bash
#!/bin/bash

# Sherlock Services Health Check
echo "=== Sherlock Services Status ==="
date

services=("sherlock_api" "sherlock_telecaller" "sherlock_server" "sherlock_fraud" "sherlock_mcp" "sherlock_whatsapp_bot")

for service in "${services[@]}"; do
    status=$(systemctl is-active $service.service)
    if [ "$status" = "active" ]; then
        echo "✅ $service: $status"
    else
        echo "❌ $service: $status"
        # Restart failed service
        sudo systemctl restart $service.service
        echo "🔄 Restarted $service"
    fi
done

echo ""
echo "=== Port Status ==="
ss -tlnp | grep -E ":800[01268]"

echo ""
echo "=== Recent Errors ==="
tail -n 5 /home/ubuntu/logs/*.log | grep -i error

# Check disk space
echo ""
echo "=== Disk Usage ==="
df -h | grep -E "(/$|/home)"

# Check memory usage
echo ""
echo "=== Memory Usage ==="
free -h
```

Make it executable and add to crontab:
```bash
sudo chmod +x /home/ubuntu/scripts/monitor_sherlock.sh

# Add to crontab for monitoring every 5 minutes
# */5 * * * * /home/ubuntu/scripts/monitor_sherlock.sh >> /home/ubuntu/logs/monitor.log 2>&1
```

### Quick Deployment Update Script

Create `/home/ubuntu/scripts/deploy_sherlock.sh`:
```bash
#!/bin/bash

echo "🚀 Deploying Sherlock Update..."

# Navigate to project directory
cd /home/ubuntu/langchain_microservice

# Pull latest changes
git pull origin main

# Update main service dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Update buyscout dependencies
cd buyscout
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Restart all services
echo "🔄 Restarting services..."
sudo systemctl restart sherlock_api.service
sudo systemctl restart sherlock_telecaller.service
sudo systemctl restart sherlock_server.service
sudo systemctl restart sherlock_fraud.service
sudo systemctl restart sherlock_mcp.service

# Wait a moment for services to start
sleep 10

# Check service status
echo "📊 Service Status:"
sudo systemctl status sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service --no-pager

echo "✅ Deployment complete!"
```

### Troubleshooting Commands

```bash
# Check if ports are in use
sudo ss -tlnp | grep -E ":800[0126]"

# Check service dependencies
sudo systemctl list-dependencies sherlock_api.service

# View service configuration
sudo systemctl show sherlock_api.service

# Check system resources
htop
sudo iotop

# Check disk space
du -sh /home/ubuntu/langchain_microservice/
du -sh /home/ubuntu/logs/

# Test service endpoints
curl http://localhost:8000/enabled_models
curl http://localhost:8001/health  # if health endpoint exists
curl http://localhost:8002/health  # if health endpoint exists
```


---
---
---
---
---
---
---

<h1 align='center'> Future Considerations</h1>


## 🏗️ Deployment Architecture

```
                    ┌─────────────────────────────────────┐
                    │            Load Balancer            │
                    │         (nginx/ALB/CloudFlare)      │
                    └─────────────────┬───────────────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │   Main Service  │   │  MCP Services   │   │   Background    │
    │   (Port 8000)   │   │ (8001/8002/8006)│   │    Workers      │
    │                 │   │                 │   │                 │
    └─────────────────┘   └─────────────────┘   └─────────────────┘
                │                   │                       │
                └───────────────────┼───────────────────────┘
                                    │
    ┌─────────────────────────────────────────────────────────────┐
    │                External Dependencies                        │
    ├─────────────────┬─────────────────┬─────────────────────────┤
    │   PostgreSQL    │     Redis       │    External APIs        │
    │   Database      │     Queue       │ (AWS/Groq/ElevenLabs)   │
    └─────────────────┴─────────────────┴─────────────────────────┘
```

## 🐳 Docker Deployment

### 1. Main Service Dockerfile

Create `Dockerfile` in the root directory:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 sherlock && chown -R sherlock:sherlock /app
USER sherlock

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. BuyScout Services Dockerfile

Create `buyscout/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install system dependencies including Playwright
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 buyscout && chown -R buyscout:buyscout /app
USER buyscout

# Expose ports for MCP services
EXPOSE 8001 8002 8006

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default command (can be overridden)
CMD ["python", "mcp_server.py"]
```

### 3. Docker Compose Configuration

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Main Application
  sherlock-main:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://sherlock:password@postgres:5432/sherlock_db
      - REDIS_URL=redis://redis:6379
      - GROQ_API_KEY=${GROQ_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    networks:
      - sherlock-network

  # MCP Scraper Service
  sherlock-scraper:
    build: 
      context: .
      dockerfile: buyscout/Dockerfile
    ports:
      - "8001:8001"
    environment:
      - REDIS_URL=redis://redis:6379
    command: ["python", "mcp_server.py"]
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - sherlock-network

  # MCP Fraud Detection Service
  sherlock-fraud:
    build:
      context: .
      dockerfile: buyscout/Dockerfile
    ports:
      - "8002:8002"
    environment:
      - REDIS_URL=redis://redis:6379
    command: ["python", "mcp_fraud_server.py"]
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - sherlock-network

  # Telecaller Service
  sherlock-telecaller:
    build: .
    ports:
      - "8006:8006"
    environment:
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
    command: ["python", "mcp_telecaller_server.py"]
    restart: unless-stopped
    networks:
      - sherlock-network

  # Background Worker
  sherlock-worker:
    build:
      context: .
      dockerfile: buyscout/Dockerfile
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://sherlock:password@postgres:5432/sherlock_db
    command: ["python", "server.py"]
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    networks:
      - sherlock-network

  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=sherlock_db
      - POSTGRES_USER=sherlock
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped
    networks:
      - sherlock-network

  # Redis Cache & Queue
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    networks:
      - sherlock-network

  # Nginx Load Balancer
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - sherlock-main
    restart: unless-stopped
    networks:
      - sherlock-network

volumes:
  postgres_data:
  redis_data:

networks:
  sherlock-network:
    driver: bridge
```

### 4. Environment Configuration

Create `.env.production`:

```env
# Database
DATABASE_URL=postgresql://sherlock:secure_password@postgres:5432/sherlock_db

# Redis
REDIS_URL=redis://redis:6379

# LLM APIs
GROQ_API_KEY=your_production_groq_key
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-1

# External Services
ELEVENLABS_API_KEY=your_elevenlabs_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token

# Application Settings
LOG_LEVEL=INFO
MAX_WORKERS=4
DEBUG=false
```

## ☁️ Cloud Deployment

### AWS ECS Deployment

#### 1. Task Definition

Create `ecs-task-definition.json`:

```json
{
  "family": "sherlock-main",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "sherlock-main",
      "image": "your-ecr-repo/sherlock:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "REDIS_URL", "value": "redis://..."}
      ],
      "secrets": [
        {"name": "GROQ_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "AWS_ACCESS_KEY_ID", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/sherlock",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 2. Service Definition

Create `ecs-service.json`:

```json
{
  "serviceName": "sherlock-main-service",
  "cluster": "sherlock-cluster",
  "taskDefinition": "sherlock-main",
  "desiredCount": 2,
  "launchType": "FARGATE",
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": ["subnet-12345", "subnet-67890"],
      "securityGroups": ["sg-12345"],
      "assignPublicIp": "ENABLED"
    }
  },
  "loadBalancers": [
    {
      "targetGroupArn": "arn:aws:elasticloadbalancing:...",
      "containerName": "sherlock-main",
      "containerPort": 8000
    }
  ]
}
```

### Kubernetes Deployment

#### 1. Main Application Deployment

Create `k8s/sherlock-main-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sherlock-main
  labels:
    app: sherlock-main
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sherlock-main
  template:
    metadata:
      labels:
        app: sherlock-main
    spec:
      containers:
      - name: sherlock-main
        image: your-registry/sherlock:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: sherlock-secrets
              key: database-url
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: GROQ_API_KEY
          valueFrom:
            secretKeyRef:
              name: sherlock-secrets
              key: groq-api-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: sherlock-main-service
spec:
  selector:
    app: sherlock-main
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
```

#### 2. Secrets Configuration

Create `k8s/secrets.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: sherlock-secrets
type: Opaque
data:
  database-url: <base64-encoded-database-url>
  groq-api-key: <base64-encoded-groq-key>
  aws-access-key-id: <base64-encoded-aws-key>
  aws-secret-access-key: <base64-encoded-aws-secret>
  elevenlabs-api-key: <base64-encoded-elevenlabs-key>
```

#### 3. Redis Deployment

Create `k8s/redis-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379
```

## �🔧 Additional Production Configuration

### 1. Nginx Configuration

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream sherlock_main {
        server sherlock-main:8000;
    }
    
    upstream sherlock_scraper {
        server sherlock-scraper:8001;
    }
    
    upstream sherlock_fraud {
        server sherlock-fraud:8002;
    }
    
    upstream sherlock_telecaller {
        server sherlock-telecaller:8006;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    server {
        listen 80;
        server_name your-domain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name your-domain.com;
        
        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        
        # Main API
        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://sherlock_main;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_timeout 60s;
        }
        
        # MCP Services (internal only)
        location /mcp/ {
            internal;
            proxy_pass http://sherlock_scraper;
        }
        
        # Health checks
        location /health {
            proxy_pass http://sherlock_main/health;
            access_log off;
        }
    }
}
```

### 2. Database Migration Script

Create `scripts/migrate.py`:

```python
#!/usr/bin/env python3
import os
import sys
import asyncio
from sqlalchemy import create_engine, text
from buyscout.models.base import database
from buyscout.models import *

async def run_migrations():
    """Run database migrations"""
    try:
        # Connect to database
        database.connect()
        
        # Create tables
        tables = [Product, Seller, Storefront, ProductReview]
        database.create_tables(tables, safe=True)
        
        print("✅ Database migration completed successfully")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        database.close()

if __name__ == "__main__":
    asyncio.run(run_migrations())
```

## 🚀 Deployment Commands

### Docker Deployment

```bash
# 1. Build and start all services
docker-compose up -d

# 2. Check service health
docker-compose ps
docker-compose logs sherlock-main

# 3. Scale services
docker-compose up -d --scale sherlock-main=3

# 4. Update single service
docker-compose build sherlock-main
docker-compose up -d sherlock-main

# 5. View logs
docker-compose logs -f sherlock-main
```

### Kubernetes Deployment

```bash
# 1. Create namespace
kubectl create namespace sherlock

# 2. Apply configurations
kubectl apply -f k8s/ -n sherlock

# 3. Check deployment status
kubectl get pods -n sherlock
kubectl get services -n sherlock

# 4. View logs
kubectl logs -f deployment/sherlock-main -n sherlock

# 5. Scale deployment
kubectl scale deployment sherlock-main --replicas=5 -n sherlock

# 6. Rolling update
kubectl set image deployment/sherlock-main sherlock-main=your-registry/sherlock:v2 -n sherlock
```

### AWS ECS Deployment

```bash
# 1. Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# 2. Create or update service
aws ecs create-service --cli-input-json file://ecs-service.json

# 3. Check service status
aws ecs describe-services --cluster sherlock-cluster --services sherlock-main-service

# 4. View logs
aws logs tail /ecs/sherlock --follow
```

## 📊 Monitoring & Observability

### 1. Health Checks

Add to `main.py`:

```python
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    checks = {
        "database": False,
        "redis": False,
        "mcp_services": False
    }
    
    try:
        # Database check
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except:
        pass
    
    try:
        # Redis check
        redis = from_url(REDIS_URL)
        await redis.ping()
        checks["redis"] = True
    except:
        pass
    
    try:
        # MCP services check
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8001/health", timeout=5)
            checks["mcp_services"] = response.status_code == 200
    except:
        pass
    
    healthy = all(checks.values())
    status_code = 200 if healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
            "version": "1.0.0"
        }
    )
```

### 2. Logging Configuration

Create `logging.yaml`:

```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  detailed:
    format: '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout
    
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: detailed
    filename: /app/logs/sherlock.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  sherlock:
    level: DEBUG
    handlers: [console, file]
    propagate: no
    
  uvicorn:
    level: INFO
    handlers: [console]
    propagate: no

root:
  level: INFO
  handlers: [console]
```

### 3. Metrics Collection

Consider integrating:
- **Prometheus**: For metrics collection
- **Grafana**: For visualization
- **Jaeger**: For distributed tracing
- **ELK Stack**: For log aggregation

## 🔐 Security Considerations

### 1. Environment Security
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Rotate API keys regularly
- Implement least-privilege access

### 2. Network Security
- Use VPCs/VNets for isolation
- Implement proper security groups/firewalls
- Enable TLS/SSL for all communications

### 3. Application Security
- Add authentication middleware
- Implement rate limiting
- Validate all inputs
- Use HTTPS everywhere

### 4. Database Security
- Use connection pooling
- Implement read replicas for scaling
- Regular backups and testing
- Encrypt data at rest

## 🔄 CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Sherlock

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest
    - name: Run tests
      run: pytest tests/

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v3
    - name: Build and push Docker image
      uses: docker/build-push-action@v3
      with:
        context: .
        push: true
        tags: your-registry/sherlock:${{ github.sha }},your-registry/sherlock:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - name: Deploy to production
      run: |
        # Update Kubernetes deployment
        kubectl set image deployment/sherlock-main sherlock-main=your-registry/sherlock:${{ github.sha }}
        kubectl rollout status deployment/sherlock-main
```

---

**🎯 Next Steps**: After deployment, refer to [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and monitoring best practices.
