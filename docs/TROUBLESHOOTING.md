# Troubleshooting Guide

This guide covers common issues and solutions for the Sherlock LangChain platform.

## 🚨 Common Issues

### 1. Service Startup Issues

#### **Services Not Starting**
```bash
# Check service status
sudo systemctl status sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service

# View detailed logs
sudo journalctl -u sherlock_api.service -n 50
sudo journalctl -u sherlock_telecaller.service -n 50

# Check for port conflicts
sudo netstat -tlnp | grep -E ":800[0126]"
```

**Common Causes:**
- Port already in use
- Missing environment variables
- Virtual environment issues
- Permission problems

**Solutions:**
```bash
# Kill processes using ports
sudo lsof -t -i:8000 | xargs sudo kill -9
sudo lsof -t -i:8001 | xargs sudo kill -9
sudo lsof -t -i:8002 | xargs sudo kill -9
sudo lsof -t -i:8006 | xargs sudo kill -9

# Fix permissions
sudo chown -R ubuntu:ubuntu /home/ubuntu/sherlock-langchain
sudo chown -R ubuntu:ubuntu /home/ubuntu/logs

# Recreate virtual environment
cd /home/ubuntu/sherlock-langchain
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### **Environment Variables Missing**
```bash
# Check if .env file exists
ls -la /home/ubuntu/sherlock-langchain/.env
ls -la /home/ubuntu/sherlock-langchain/buyscout/.env

# Create missing environment files
cp /home/ubuntu/sherlock-langchain/.env.example /home/ubuntu/sherlock-langchain/.env
# Edit with actual values
nano /home/ubuntu/sherlock-langchain/.env
```

### 2. Database Connection Issues

#### **PostgreSQL Connection Failed**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Test database connection
psql -h localhost -U sherlock -d sherlock_db

# Check connection string in logs
grep -i "database" /home/ubuntu/logs/main.log
```

**Solutions:**
```bash
# Restart PostgreSQL
sudo systemctl restart postgresql

# Reset database connection
sudo -u postgres psql
\l  # List databases
\du # List users

# Create database if missing
sudo -u postgres createdb sherlock_db
sudo -u postgres psql -c "CREATE USER sherlock WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sherlock_db TO sherlock;"
```

### 3. Redis Connection Issues

#### **Redis Queue Not Working**
```bash
# Check Redis status
sudo systemctl status redis

# Test Redis connection
redis-cli ping

# Check Redis logs
sudo journalctl -u redis -n 50
```

**Solutions:**
```bash
# Restart Redis
sudo systemctl restart redis

# Clear Redis if corrupted
redis-cli FLUSHALL

# Check Redis configuration
sudo nano /etc/redis/redis.conf
```

### 4. MCP Service Communication Issues

#### **MCP Servers Not Responding**
```bash
# Test MCP server connectivity
curl -X POST http://localhost:8001/health
curl -X POST http://localhost:8002/health

# Check if MCP processes are running
ps aux | grep mcp_server
ps aux | grep mcp_fraud_server
```

**Solutions:**
```bash
# Restart specific MCP services
sudo systemctl restart sherlock_mcp.service
sudo systemctl restart sherlock_fraud.service

# Check MCP server logs for errors
tail -f /home/ubuntu/logs/mcp_server.log
tail -f /home/ubuntu/logs/fraud_server.log
```

### 5. Playwright/Browser Issues

#### **Fraud Detection Browser Errors**
```bash
# Check if Playwright browsers are installed
ls /home/ubuntu/.cache/ms-playwright/

# Check for browser dependencies
ldd /home/ubuntu/.cache/ms-playwright/chromium-*/chrome-linux/chrome
```

**Solutions:**
```bash
# Reinstall Playwright browsers
cd /home/ubuntu/sherlock-langchain/buyscout
source .venv/bin/activate
playwright uninstall
playwright install chromium
playwright install-deps

# For missing system dependencies
sudo apt-get update
sudo apt-get install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1 libasound2
```

### 6. API Response Issues

#### **Slow Response Times**
```bash
# Check system resources
htop
free -h
df -h

# Check database performance
sudo -u postgres psql sherlock_db -c "SELECT * FROM pg_stat_activity;"

# Monitor API requests
tail -f /home/ubuntu/logs/main.log | grep -E "(POST|GET)"
```

**Solutions:**
```bash
# Increase worker processes if needed
# Edit systemd service file to add environment variables
sudo nano /etc/systemd/system/sherlock_api.service

# Add under [Service]:
Environment=WORKERS=4
Environment=MAX_REQUESTS=1000

# Restart service
sudo systemctl daemon-reload
sudo systemctl restart sherlock_api.service
```

#### **Token/Cost Calculation Errors**
```bash
# Check for API key issues
grep -i "api.*key" /home/ubuntu/logs/main.log
grep -i "unauthorized\|forbidden" /home/ubuntu/logs/main.log
```

**Solutions:**
```bash
# Verify API keys in environment
source /home/ubuntu/sherlock-langchain/.venv/bin/activate
python3 -c "import os; print('GROQ_API_KEY:', 'SET' if os.getenv('GROQ_API_KEY') else 'NOT SET')"

# Test API connectivity
curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
```

## 🔍 Debugging Tools

### 1. Log Analysis Scripts

Create `/home/ubuntu/scripts/analyze_logs.sh`:
```bash
#!/bin/bash

echo "=== Recent Errors in All Services ==="
grep -i error /home/ubuntu/logs/*.log | tail -20

echo ""
echo "=== Service Restart Events ==="
grep -i "restart\|started\|stopped" /home/ubuntu/logs/*.log | tail -10

echo ""
echo "=== Performance Issues ==="
grep -i "timeout\|slow\|performance" /home/ubuntu/logs/*.log | tail -10

echo ""
echo "=== API Request Volume ==="
echo "Main API requests in last hour:"
grep "$(date '+%Y-%m-%d %H')" /home/ubuntu/logs/main.log | grep -c "POST\|GET"

echo ""
echo "=== Memory Usage Patterns ==="
ps aux --sort=-%mem | head -10
```

### 2. Health Check Script

Create `/home/ubuntu/scripts/health_check.sh`:
```bash
#!/bin/bash

echo "=== Sherlock Health Check ==="
date

# Function to check HTTP endpoint
check_endpoint() {
    local url=$1
    local name=$2
    local timeout=${3:-5}
    
    if curl -s --max-time $timeout "$url" > /dev/null; then
        echo "✅ $name: OK"
    else
        echo "❌ $name: FAILED"
    fi
}

# Check main endpoints
check_endpoint "http://localhost:8000/enabled_models" "Main API"

# Check if services are responsive
services=("sherlock_api" "sherlock_telecaller" "sherlock_server" "sherlock_fraud" "sherlock_mcp")
for service in "${services[@]}"; do
    if systemctl is-active --quiet $service.service; then
        echo "✅ $service: Running"
    else
        echo "❌ $service: Not running"
    fi
done

# Check system resources
echo ""
echo "=== System Resources ==="
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
echo "Load: $(uptime | awk -F'load average:' '{print $2}')"

# Check database connectivity
echo ""
echo "=== Database Check ==="
if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "✅ PostgreSQL: Connected"
else
    echo "❌ PostgreSQL: Connection failed"
fi

# Check Redis connectivity
echo ""
echo "=== Redis Check ==="
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: Connected"
else
    echo "❌ Redis: Connection failed"
fi
```

### 3. Performance Monitoring

Create `/home/ubuntu/scripts/performance_monitor.sh`:
```bash
#!/bin/bash

# Monitor API response times
echo "=== API Performance Test ==="
time curl -s -X POST "http://localhost:8000/enabled_models" > /dev/null
echo "Enabled models endpoint response time: ^^^"

# Monitor memory usage of each service
echo ""
echo "=== Memory Usage by Service ==="
for service in sherlock_api sherlock_telecaller sherlock_server sherlock_fraud sherlock_mcp; do
    pid=$(systemctl show --property MainPID --value $service.service)
    if [ "$pid" != "0" ]; then
        mem=$(ps -o pid,comm,pmem --pid=$pid --no-headers)
        echo "$service: $mem"
    fi
done

# Check log file sizes
echo ""
echo "=== Log File Sizes ==="
du -sh /home/ubuntu/logs/*.log

# Check for memory leaks
echo ""
echo "=== Top Memory Consumers ==="
ps aux --sort=-%mem | head -5
```

## 🔧 Maintenance Tasks

### 1. Log Rotation Setup

Create `/etc/logrotate.d/sherlock`:
```
/home/ubuntu/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    postrotate
        systemctl reload sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service
    endscript
}
```

### 2. Backup Scripts

Create `/home/ubuntu/scripts/backup.sh`:
```bash
#!/bin/bash

BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration files
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    /home/ubuntu/sherlock-langchain/.env \
    /home/ubuntu/sherlock-langchain/buyscout/.env \
    /etc/systemd/system/sherlock_*.service

# Backup database (if using local PostgreSQL)
sudo -u postgres pg_dump sherlock_db > "$BACKUP_DIR/database_$DATE.sql"

# Backup logs (last 7 days)
find /home/ubuntu/logs -name "*.log" -mtime -7 -exec tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" {} +

# Clean old backups (keep last 30 days)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

### 3. Update Procedures

Create `/home/ubuntu/scripts/safe_update.sh`:
```bash
#!/bin/bash

echo "🔄 Starting safe update procedure..."

# Create backup before update
/home/ubuntu/scripts/backup.sh

# Stop services gracefully
echo "Stopping services..."
sudo systemctl stop sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service

# Wait for services to stop
sleep 10

# Pull latest code
cd /home/ubuntu/sherlock-langchain
git stash  # Save local changes
git pull origin main

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt

cd buyscout
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Start services
echo "Starting services..."
sudo systemctl start sherlock_api.service sherlock_telecaller.service sherlock_server.service sherlock_fraud.service sherlock_mcp.service

# Wait for startup
sleep 15

# Verify services are running
echo "Verifying services..."
/home/ubuntu/scripts/health_check.sh

echo "✅ Update completed!"
```

## 📊 Monitoring Dashboard (Optional)

### Simple Web Dashboard

Create `/home/ubuntu/scripts/status_dashboard.py`:
```python
#!/usr/bin/env python3
from flask import Flask, render_template_string
import subprocess
import json
import requests
from datetime import datetime

app = Flask(__name__)

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sherlock Status Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .status-ok { color: green; }
        .status-error { color: red; }
        .service-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .service-card { border: 1px solid #ccc; padding: 15px; border-radius: 8px; }
    </style>
</head>
<body>
    <h1>Sherlock Platform Status</h1>
    <p>Last updated: {{ timestamp }}</p>
    
    <div class="service-grid">
        {% for service in services %}
        <div class="service-card">
            <h3>{{ service.name }}</h3>
            <p class="{{ 'status-ok' if service.status == 'active' else 'status-error' }}">
                Status: {{ service.status }}
            </p>
            {% if service.port %}
            <p>Port: {{ service.port }}</p>
            {% endif %}
            {% if service.response_time %}
            <p>Response Time: {{ service.response_time }}ms</p>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    
    <h2>System Resources</h2>
    <ul>
        <li>Memory: {{ resources.memory }}</li>
        <li>Disk: {{ resources.disk }}</li>
        <li>Load: {{ resources.load }}</li>
    </ul>
</body>
</html>
'''

@app.route('/')
def dashboard():
    services = []
    
    # Check systemd services
    service_names = [
        ('sherlock_api', 8000),
        ('sherlock_telecaller', 8006),
        ('sherlock_server', None),
        ('sherlock_fraud', 8002),
        ('sherlock_mcp', 8001)
    ]
    
    for name, port in service_names:
        try:
            result = subprocess.run(['systemctl', 'is-active', f'{name}.service'], 
                                  capture_output=True, text=True)
            status = result.stdout.strip()
            
            response_time = None
            if port and status == 'active':
                try:
                    import time
                    start = time.time()
                    requests.get(f'http://localhost:{port}/health', timeout=5)
                    response_time = int((time.time() - start) * 1000)
                except:
                    pass
            
            services.append({
                'name': name.replace('sherlock_', '').title(),
                'status': status,
                'port': port,
                'response_time': response_time
            })
        except:
            services.append({
                'name': name.replace('sherlock_', '').title(),
                'status': 'unknown',
                'port': port,
                'response_time': None
            })
    
    # Get system resources
    try:
        memory = subprocess.run(['free', '-h'], capture_output=True, text=True)
        disk = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        load = subprocess.run(['uptime'], capture_output=True, text=True)
        
        resources = {
            'memory': memory.stdout.split('\n')[1].split()[2:4],
            'disk': disk.stdout.split('\n')[1].split()[2:4],
            'load': load.stdout.split('load average:')[1].strip()
        }
    except:
        resources = {'memory': 'N/A', 'disk': 'N/A', 'load': 'N/A'}
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                services=services,
                                resources=resources,
                                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=False)
```

Run the dashboard:
```bash
cd /home/ubuntu/scripts
python3 status_dashboard.py
# Access at http://your-server-ip:9999
```

## 🆘 Emergency Procedures

### Service Recovery
```bash
# Emergency restart all services
sudo systemctl restart sherlock_*.service

# If all else fails, reboot the server
sudo reboot
```

### Data Recovery
```bash
# Restore from backup
cd /home/ubuntu/backups
# Find latest backup
ls -la *.tar.gz | tail -5

# Restore configuration
tar -xzf config_YYYYMMDD_HHMMSS.tar.gz -C /

# Restore database
sudo -u postgres psql sherlock_db < database_YYYYMMDD_HHMMSS.sql
```

### Contact Information
- **System Administrator**: [Your contact info]
- **Emergency Contact**: [Emergency contact]
- **Documentation**: This guide and `/home/ubuntu/sherlock-langchain/README.md`

---

**💡 Pro Tip**: Always test changes in a staging environment before applying to production!
