"""
Telegram Bot Commands for Paper Trading
Layer 7: Command & Control
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_PATH = Path(__file__).parent / "config.yaml"

engine_instance = None


def load_config() -> Dict[str, Any]:
    """Load paper trading config."""
    if yaml and CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {}


def set_engine(engine):
    """Set the trading engine instance."""
    global engine_instance
    engine_instance = engine


async def start_command(update: Update, context: CallbackContext):
    """Handle /start command."""
    await update.message.reply_text(
        "🚀 *Paper Trading Bot Active*\n\n"
        "Commands:\n"
        "/status - System status\n"
        "/positions - Open positions\n"
        "/pnl - P&L report\n"
        "/strategy - Current strategy\n"
        "/regime - Market regime\n"
        "/learning - Model learning status\n"
        "/start_trading - Resume trading\n"
        "/stop_trading - Pause trading\n"
        "/emergency - Emergency stop\n"
        "/health - Health report",
        parse_mode='Markdown'
    )


async def status_command(update: Update, context: CallbackContext):
    """Handle /status command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    status = engine_instance.get_status()
    
    message = f"""
📊 *System Status*
━━━━━━━━━━━━━━━━
🟢 Running: {status.get('running', False)}
💰 Capital: ${status.get('capital', 0):,.2f}
⚡ Leverage: {status.get('leverage', 1)}x
📈 Daily PnL: ${status.get('daily_pnl', 0):,.2f}
🎯 Strategy: {status.get('active_strategy', 'N/A')}
🔄 Regime: {status.get('current_regime', 'N/A')}
⏰ {status.get('timestamp', '')}
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def positions_command(update: Update, context: CallbackContext):
    """Handle /positions command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    positions = engine_instance.get_positions()
    
    if not positions:
        await update.message.reply_text("📭 No open positions")
        return
    
    message = "📋 *Open Positions*\n━━━━━━━━━━━━━━━━\n"
    
    for symbol, pos in positions.items():
        size = pos.get('size', 0)
        entry = pos.get('entry_price', 0)
        pnl = pos.get('pnl', 0)
        
        emoji = "🟢" if pnl >= 0 else "🔴"
        
        message += f"{emoji} {symbol}\n"
        message += f"   Size: {size:.4f}\n"
        message += f"   Entry: ${entry:,.2f}\n"
        message += f"   PnL: ${pnl:,.2f}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def pnl_command(update: Update, context: CallbackContext):
    """Handle /pnl command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    pnl = engine_instance.get_pnl()
    status = engine_instance.get_status()
    capital = status.get('capital', 10000)
    
    pnl_pct = (pnl / capital * 100) if capital > 0 else 0
    
    emoji = "🟢" if pnl >= 0 else "🔴"
    
    message = f"""
💰 *P&L Report*
━━━━━━━━━━━━━━━━
{emoji} Daily PnL: ${pnl:,.2f}
{emoji} Return: {pnl_pct:.2f}%
💵 Capital: ${capital:,.2f}
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def strategy_command(update: Update, context: CallbackContext):
    """Handle /strategy command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    status = engine_instance.get_status()
    
    active = status.get('active_strategy', 'N/A')
    regime = status.get('current_regime', 'N/A')
    
    message = f"""
🎯 *Strategy Info*
━━━━━━━━━━━━━━━━
Current: `{active}`
Regime: `{regime}`

Available strategies:
• MomentumCtaStrategy (bull)
• MeanReversionCtaStrategy (bear)
• BreakoutCtaStrategy (volatile)
• RlEnhancedCtaStrategy (sideways)
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def regime_command(update: Update, context: CallbackContext):
    """Handle /regime command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    status = engine_instance.get_status()
    regime = status.get('current_regime', 'unknown')
    
    regime_emojis = {
        'bull': '🐂',
        'bear': '🐻',
        'volatile': '⚡',
        'sideways': '➡️'
    }
    
    emoji = regime_emojis.get(regime, '❓')
    
    message = f"""
🔄 *Market Regime*
━━━━━━━━━━━━━━━━
{emoji} Current: *{regime.upper()}*
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def learning_command(update: Update, context: CallbackContext):
    """Handle /learning command - show model learning status."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    status = engine_instance.get_status()
    sl = status.get('self_learning', {})
    ml = status.get('meta_learning', {})
    win_rate = status.get('recent_win_rate', 0) * 100
    
    status_text = "🔴 Training" if sl.get('is_training') else (
        "🟢 Ready" if sl.get('buffer_size', 0) >= sl.get('min_samples_required', 50) else "🟡 Collecting"
    )
    
    message = f"""
🧠 *Model Learning Status*
━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Experience Buffer: {sl.get('buffer_size', 0)} / {sl.get('min_samples_required', 50)}
🔄 Retrain Count: {sl.get('retrain_count', 0)}
🎯 Model Accuracy: {(sl.get('model_accuracy', 0) * 100):.1f}%
⏱️ Time to Retrain: {sl.get('time_to_retrain', 0)}s
📈 Win Rate: {win_rate:.1f}%
Status: {status_text}

📊 Meta-Learning:
🔄 Regime: {ml.get('current_regime', 'unknown')}
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def start_trading_command(update: Update, context: CallbackContext):
    """Handle /start_trading command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    if engine_instance.running:
        await update.message.reply_text("⚠️ Trading already running")
        return
    
    engine_instance.start()
    await update.message.reply_text("✅ Trading resumed")


async def stop_trading_command(update: Update, context: CallbackContext):
    """Handle /stop_trading command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    if not engine_instance.running:
        await update.message.reply_text("⚠️ Trading not running")
        return
    
    engine_instance.stop()
    await update.message.reply_text("⏸️ Trading paused")


async def emergency_command(update: Update, context: CallbackContext):
    """Handle /emergency command."""
    if engine_instance is None:
        await update.message.reply_text("❌ Engine not initialized")
        return
    
    await update.message.reply_text("🛑 EMERGENCY STOP TRIGGERED")
    
    engine_instance.emergency_stop()
    
    await update.message.reply_text("✅ All positions closed. Engine stopped.")


async def health_command(update: Update, context: CallbackContext):
    """Handle /health command."""
    from paper_trading.layers.layer6_orchestration.health_monitor import health_monitor
    
    report = health_monitor.get_health_report()
    
    uptime = report.get('uptime_seconds', 0)
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    
    message = f"""
🏥 *Health Report*
━━━━━━━━━━━━━━━━
⏱️ Uptime: {hours}h {minutes}m
🔄 Checks: {report.get('check_count', 0)}
✅ Status: {report.get('overall_status', 'unknown')}

*Components:*
"""
    
    for name, comp in report.get('components', {}).items():
        status = comp.get('status', 'unknown')
        emoji = '✅' if status == 'healthy' else '❌'
        message += f"{emoji} {name}: {status}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def help_command(update: Update, context: CallbackContext):
    """Handle /help command."""
    await update.message.reply_text(
        """
📖 *Help*
━━━━━━━━━━━━━━━━
/start - Start bot
/status - System status
/positions - View positions
/pnl - P&L report
/strategy - Current strategy
/regime - Market regime
/health - Health report
/start_trading - Resume
/stop_trading - Pause
/emergency - Emergency stop
""",
        parse_mode='Markdown'
    )


def setup_bot(token: str = None) -> Application:
    """Setup Telegram bot."""
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = token or os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
        print("⚠️ No Telegram bot token configured")
        return None
    
    app = Application.builder().token(bot_token).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("positions", positions_command))
    app.add_handler(CommandHandler("pnl", pnl_command))
    app.add_handler(CommandHandler("strategy", strategy_command))
    app.add_handler(CommandHandler("regime", regime_command))
    app.add_handler(CommandHandler("learning", learning_command))
    app.add_handler(CommandHandler("start_trading", start_trading_command))
    app.add_handler(CommandHandler("stop_trading", stop_trading_command))
    app.add_handler(CommandHandler("emergency", emergency_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("help", help_command))
    
    print("✅ Telegram bot commands registered")
    
    return app


if __name__ == "__main__":
    print("Testing Telegram bot setup...")
    app = setup_bot()
    if app:
        print("Bot ready - run with: python telegram_commands.py")
    else:
        print("Configure TELEGRAM_BOT_TOKEN to enable bot")
