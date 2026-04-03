# MATARANPUTANA - Getting Started Guide

## 1. System Requirements

### Minimum
- **OS**: Ubuntu 20.04+ / Debian 11+ / Any Linux with Python 3.8+
- **CPU**: 2 cores
- **RAM**: 2GB
- **Disk**: 10GB free space
- **Network**: Outbound HTTPS (443)

### Recommended
- **OS**: Ubuntu 22.04 LTS
- **CPU**: 4 cores
- **RAM**: 4GB+
- **Disk**: 20GB+ SSD
- **Network**: Stable broadband, low latency to Binance servers

---

## 2. Quick Start (5 Minutes)

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/MATARANPUTANA.git
cd MATARANPUTANA
```

### Step 2: Run Setup

```bash
chmod +x setup.sh && ./setup.sh
```

The setup script will:
1. Check Python version (requires 3.8+)
2. Create virtual environment (`venv/`)
3. Install all Python dependencies from `requirements.txt`
4. Create required directories (`logs/`, `memory/`, etc.)
5. Copy `.env.example` to `.env` for configuration
6. Set file permissions

### Step 3: Configure Environment

Edit the `.env` file:

```bash
cp .env.example .env
nano .env
```

Required fields:
```bash
# For Binance Testnet (free, no real money)
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret

# For Telegram notifications (optional but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
```

### Step 4: Start Trading Engine

```bash
python run_paper_trading.py
```

You should see output like:
```
2024-01-01 12:00:00 | INFO | PaperTradingEngine initialized: capital=$10000, leverage=5x
2024-01-01 12:00:00 | INFO | All layers initialized with VNPyDataBridge
2024-01-01 12:00:00 | INFO | PaperTradingEngine started with VNPyDataBridge
```

### Step 5: Monitor

```bash
# View live logs
tail -f logs/paper_trading.log

# Check system status (if Telegram is configured)
# Send /status to your bot
```

---

## 3. Docker Deployment (Recommended for Production)

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### Start All Services

```bash
docker-compose up -d
```

This starts:
- **Redis** (port 6379) - Event bus and trade logging
- **PostgreSQL** (port 5432) - Persistent storage
- **VNPY Engine** (port 8000) - Trading engine backend
- **Orchestrator** (ports 5000-5001) - Main orchestration
- **Dashboard** (port 8080) - Web monitoring UI
- **Prometheus** (port 9090) - Metrics collection
- **Grafana** (port 3000) - Metrics visualization
- **Loki** (port 3100) - Log aggregation

### Verify

```bash
docker-compose ps
docker-compose logs -f orchestrator
```

### Access Services

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| Dashboard | http://localhost:8080 | None |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | None |

### Stop

```bash
docker-compose down
```

### Stop and Remove Volumes

```bash
docker-compose down -v
```

---

## 4. EC2 Deployment (AWS)

### Step 1: Launch EC2 Instance

1. Go to AWS EC2 Console
2. Launch Instance
3. Choose **Ubuntu Server 22.04 LTS**
4. Instance type: **t3.medium** (2 vCPU, 4GB RAM) minimum
5. Storage: **20GB gp3** minimum
6. Security Group:
   - Inbound: SSH (22) from your IP
   - Inbound: 8080 (Dashboard) from your IP (optional)
   - Inbound: 3000 (Grafana) from your IP (optional)
7. Create/download key pair

### Step 2: Connect to Instance

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
```

### Step 3: One-Line Deployment

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/MATARANPUTANA/main/scripts/deploy.sh | bash
```

### Step 4: Verify

```bash
# Check engine is running
ps aux | grep paper_trading

# View logs
tail -f /home/ubuntu/MATARANPUTANA/logs/paper_trading.log

# Check Docker services (if using Docker)
docker-compose ps
```

---

## 5. Configuration Before First Run

### 5.1 Trading Mode

Edit `paper_trading/config.yaml`:

```yaml
trading:
  mode: testnet  # Start with testnet, NOT live
```

**IMPORTANT**: Always start with `testnet` mode. Never deploy with `live` mode until you have:
- Verified all components work on testnet
- Monitored at least 100 trades
- Confirmed risk management triggers correctly
- Backtested with historical data

### 5.2 Binance Testnet Setup

1. Go to https://testnet.binancefuture.com
2. Register and get API keys
3. Copy keys to `.env`:
   ```bash
   BINANCE_API_KEY=your_testnet_key
   BINANCE_API_SECRET=your_testnet_secret
   ```

### 5.3 Telegram Bot Setup

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow prompts to create bot
4. Copy the bot token to `.env`:
   ```bash
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
5. Message your bot to get your chat ID
6. Add chat ID to config:
   ```yaml
   telegram:
     admin_chat_id: YOUR_CHAT_ID
   ```

---

## 6. Running the System

### 6.1 Start Engine

```bash
# Option 1: Direct Python
python run_paper_trading.py

# Option 2: Using start script
./start_system.sh

# Option 3: Background with nohup
nohup python run_paper_trading.py > logs/engine_nohup.log 2>&1 &

# Option 4: Using systemd (production)
sudo systemctl start mataranputana
```

### 6.2 Stop Engine

```bash
# Option 1: Ctrl+C (if running in foreground)

# Option 2: Kill process
pkill -f paper_trading

# Option 3: Using stop script
./stop_system.sh

# Option 4: Using systemd
sudo systemctl stop mataranputana
```

### 6.3 Restart Engine

```bash
./restart.sh
```

### 6.4 Monitor

```bash
# Live logs
tail -f logs/paper_trading.log

# Filter for errors
grep -i "error\|critical\|fail" logs/paper_trading.log | tail -20

# Filter for Black Swan events
grep -i "black swan\|expectancy\|defensive\|fail-safe\|ruin" logs/paper_trading.log | tail -20

# Check process
ps aux | grep paper_trading

# Web dashboard
# Open http://YOUR_SERVER_IP:8080
```

---

## 7. Verifying System Health

### 7.1 Check Engine Status

```python
python -c "
from paper_trading.engine import get_engine
engine = get_engine()
status = engine.get_status()
print(f'Running: {status[\"running\"]}')
print(f'Capital: ${status[\"capital\"]:.2f}')
print(f'Regime: {status[\"current_regime\"]}')
print(f'Strategy: {status[\"active_strategy\"]}')
"
```

### 7.2 Check Risk Status

```python
python -c "
from paper_trading.engine import get_engine
engine = get_engine()
risk = engine.risk_engine.get_risk_status()
print(f'Peak Capital: ${risk[\"peak_capital\"]:.2f}')
print(f'Defensive Mode: {risk[\"black_swan\"][\"defensive_mode\"]}')
print(f'Consecutive Losses: {risk[\"black_swan\"][\"consecutive_losses\"]}')
"
```

### 7.3 Check Learning Status

```python
python -c "
from paper_trading.engine import get_engine
engine = get_engine()
learning = engine.get_learning_status()
print(f'HMM Trained: {learning[\"hmm\"][\"trained\"]}')
print(f'Self-Learning Buffer: {learning[\"self_learning\"][\"buffer_size\"]}')
print(f'Model Accuracy: {learning[\"self_learning\"][\"model_accuracy\"]:.2f}')
"
```

---

## 8. First Run Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with API keys
- [ ] Trading mode set to `testnet`
- [ ] Telegram bot configured (optional)
- [ ] Engine starts without errors
- [ ] Data connection established (check logs for "connected")
- [ ] HMM regime detector initializing
- [ ] Risk engine loaded with Black Swan parameters
- [ ] Expectancy gate active (will block trades until models trained)
- [ ] Telegram notification received (if configured)
- [ ] Web dashboard accessible at http://localhost:8080

---

## 9. Next Steps After First Run

1. **Monitor for 24 hours** - Watch logs for any errors or unexpected behavior
2. **Verify Black Swan gates** - Confirm expectancy gate is blocking trades (expected behavior initially)
3. **Check Telegram alerts** - Ensure notifications are being received
4. **Review risk parameters** - Adjust if needed based on market conditions
5. **Run test suite** - Execute all tests to verify system integrity
6. **Gradually increase exposure** - Only after system proves stable

---

## 10. Moving from Testnet to Live

**WARNING**: This transition involves real financial risk.

1. **Minimum 30 days on testnet** with consistent performance
2. **At least 500 trades executed** on testnet
3. **Positive expectancy** confirmed over extended period
4. **All Black Swan features verified** to trigger correctly
5. **Reduce position_size_pct** to 2-5% for initial live deployment
6. **Set lower leverage** (2-3x) for live trading
7. **Monitor continuously** for the first week of live trading
8. **Have emergency stop procedure** ready

```yaml
# Live configuration (conservative start)
trading:
  mode: live
  leverage: 2
  position_size_pct: 5

risk:
  max_daily_loss_pct: 5
  max_drawdown_pct: 10
  stop_loss_pct: 2.0
```
