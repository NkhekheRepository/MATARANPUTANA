# MATARANPUTANA - Deployment Guide

## Single-Line Deployment (Linux / EC2)

This command provisions, installs, configures, and starts the entire MATARANPUTANA autonomous trading system from a fresh Linux/EC2 instance:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/MATARANPUTANA/main/scripts/deploy.sh | bash
```

---

## What the Deploy Script Does

1. **System Preparation**
   - Updates system packages (`apt update && apt upgrade`)
   - Installs Python 3.8+, pip, git, Redis, build essentials
   - Creates `mataranputana` user (non-root)

2. **Application Installation**
   - Clones MATARANPUTANA repository to `/home/ubuntu/MATARANPUTANA`
   - Creates Python virtual environment
   - Installs all dependencies from `requirements.txt`

3. **Service Configuration**
   - Starts and enables Redis service
   - Creates systemd service for the trading engine
   - Configures log rotation

4. **Environment Setup**
   - Creates `.env` from template
   - Sets proper file permissions
   - Creates required directories

5. **Engine Startup**
   - Starts the trading engine via systemd
   - Verifies engine is running
   - Displays status and log locations

---

## Manual EC2 Deployment (Step-by-Step)

### Step 1: Launch EC2 Instance

```
AMI: Ubuntu Server 22.04 LTS
Instance Type: t3.medium (2 vCPU, 4GB RAM)
Storage: 20GB gp3
Security Group:
  - SSH (22) from your IP
  - 8080 (Dashboard) from your IP (optional)
Key Pair: Download and save
```

### Step 2: Connect

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
```

### Step 3: Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10 python3.10-venv python3-pip git redis-server curl
```

### Step 4: Clone & Setup

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/MATARANPUTANA.git
cd MATARANPUTANA

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure Environment

```bash
# Create .env file
cat > .env << 'ENVEOF'
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
TRADING_MODE=testnet
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF
```

### Step 6: Start Redis

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # Should return PONG
```

### Step 7: Start Trading Engine

```bash
# Option A: Foreground (for testing)
python run_paper_trading.py

# Option B: Background with nohup
nohup python run_paper_trading.py > logs/engine_nohup.log 2>&1 &

# Option C: systemd (production - see below)
```

---

## systemd Service (Production)

### Create Service File

```bash
sudo tee /etc/systemd/system/mataranputana.service << 'SVCEOF'
[Unit]
Description=MATARANPUTANA Autonomous Trading Engine
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/MATARANPUTANA
Environment=PATH=/home/ubuntu/MATARANPUTANA/venv/bin:/usr/bin
ExecStart=/home/ubuntu/MATARANPUTANA/venv/bin/python run_paper_trading.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/ubuntu/MATARANPUTANA/logs/engine_systemd.log
StandardError=append:/home/ubuntu/MATARANPUTANA/logs/engine_systemd.log

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/ubuntu/MATARANPUTANA/logs /home/ubuntu/MATARANPUTANA/memory
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SVCEOF
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable mataranputana
sudo systemctl start mataranputana

# Check status
sudo systemctl status mataranputana

# View logs
sudo journalctl -u mataranputana -f
```

### Management Commands

```bash
# Start
sudo systemctl start mataranputana

# Stop
sudo systemctl stop mataranputana

# Restart
sudo systemctl restart mataranputana

# Reload config (SIGHUP)
sudo systemctl reload mataranputana

# Check status
sudo systemctl status mataranputana

# View logs
sudo journalctl -u mataranputana --since "1 hour ago"
sudo journalctl -u mataranputana -n 100
```

---

## Docker Deployment

### docker-compose.yml

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mataranputana
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  orchestrator:
    build:
      context: .
      dockerfile: Dockerfile.orchestrator
    ports:
      - "5000:5000"
      - "5001:5001"
    environment:
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
      - TRADING_MODE=testnet
    env_file:
      - .env
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.orchestrator
    command: python paper_trading/dashboard/app.py
    ports:
      - "8080:8080"
    environment:
      - REDIS_HOST=redis
    depends_on:
      - orchestrator
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    restart: unless-stopped

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki.yml:/etc/loki/local-config.yaml
      - loki_data:/loki
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
  prometheus_data:
  grafana_data:
  loki_data:
```

### Start

```bash
docker-compose up -d
```

### Verify

```bash
docker-compose ps
docker-compose logs -f orchestrator
```

---

## Production Hardening

### Security Checklist

- [ ] Running as non-root user (`ubuntu`)
- [ ] systemd service with `NoNewPrivileges=true`
- [ ] `ProtectSystem=strict` (read-only filesystem)
- [ ] `PrivateTmp=true` (isolated temp directory)
- [ ] API keys in `.env` (not in config files)
- [ ] `.env` in `.gitignore`
- [ ] Redis bound to localhost only
- [ ] Firewall rules configured (only necessary ports open)
- [ ] SSH key authentication only (no passwords)
- [ ] Regular system updates scheduled

### Log Rotation

```bash
sudo tee /etc/logrotate.d/mataranputana << 'LREOF'
/home/ubuntu/MATARANPUTANA/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
    sharedscripts
    postrotate
        systemctl reload mataranputana > /dev/null 2>&1 || true
    endscript
}
LREOF
```

### Monitoring Setup

```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Set up log monitoring
tail -f /home/ubuntu/MATARANPUTANA/logs/paper_trading.log | grep -i "error\|critical"

# Set up resource monitoring
watch -n 5 'free -h && df -h / && ps aux --sort=-%mem | head -5'
```

---

## Deployment Verification

### Post-Deploy Checklist

```bash
# 1. Engine is running
ps aux | grep paper_trading | grep -v grep

# 2. Redis is running
redis-cli ping

# 3. Engine responds
python -c "from paper_trading.engine import get_engine; print('Engine OK')"

# 4. Black Swan features loaded
python -c "
from paper_trading.engine import get_engine
e = get_engine()
features = ['check_expectancy', 'check_tail_risk', 'detect_regime_collapse',
            'check_drawdown_defense', 'check_correlation_shock',
            'check_market_liquidity', 'calculate_ruin_probability',
            'check_conservatism']
for f in features:
    assert hasattr(e.risk_engine, f), f'Missing: {f}'
print(f'All {len(features)} Black Swan features loaded: OK')
"

# 5. Logs are being written
ls -la logs/ | grep paper_trading

# 6. No errors in recent logs
grep -c "ERROR\|CRITICAL" logs/paper_trading.log

# 7. Web dashboard accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
```

---

## Rollback Procedure

If a deployment causes issues:

```bash
# 1. Stop engine
sudo systemctl stop mataranputana

# 2. Restore previous config
cp paper_trading/config.yaml.bak paper_trading/config.yaml

# 3. Restore previous code (if using git)
git checkout <previous-commit>

# 4. Restart
sudo systemctl start mataranputana

# 5. Verify
sudo systemctl status mataranputana
tail -f logs/paper_trading.log
```

---

## Scaling

### Horizontal Scaling (Multiple Engines)

For running multiple trading engines:

1. Clone to different directories:
   ```bash
   cp -r MATARANPUTANA MATARANPUTANA_BTC
   cp -r MATARANPUTANA MATARANPUTANA_ETH
   ```

2. Use different Redis databases:
   ```yaml
   # Engine 1
   REDIS_DB=0
   # Engine 2
   REDIS_DB=1
   ```

3. Use different dashboard ports:
   ```yaml
   # Engine 1
   dashboard:
     port: 8080
   # Engine 2
   dashboard:
     port: 8081
   ```

4. Create separate systemd services:
   ```bash
   sudo cp mataranputana.service /etc/systemd/system/mataranputana-btc.service
   sudo cp mataranputana.service /etc/systemd/system/mataranputana-eth.service
   ```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BINANCE_API_KEY` | Yes (testnet/live) | - | Binance API key |
| `BINANCE_API_SECRET` | Yes (testnet/live) | - | Binance API secret |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot token |
| `TELEGRAM_ADMIN_CHAT_ID` | No | - | Admin chat ID |
| `TRADING_MODE` | No | testnet | paper/testnet/live |
| `REDIS_HOST` | No | localhost | Redis host |
| `REDIS_PORT` | No | 6379 | Redis port |
| `REDIS_DB` | No | 0 | Redis database number |
| `POSTGRES_HOST` | No | localhost | PostgreSQL host |
| `POSTGRES_PORT` | No | 5432 | PostgreSQL port |
