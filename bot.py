import os
import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VYBE_API_KEY = os.getenv("VYBE_API_KEY")
BASE_URL = "https://api.vybe.xyz"

# In-memory storage for tracked wallets per user
user_wallets = {}  # {user_id: set(wallets)}
latest_tx_hash = {}  # {wallet: last_seen_tx_hash}

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Telegram command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to AlphaRadar!\nUse /commands to view all available features."
    )

async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛠️ *Available Commands:*\n"
        "/start - Welcome message\n"
        "/follow <wallet> - Start tracking a wallet\n"
        "/unfollow <wallet> - Stop tracking a wallet\n"
        "/list - Show your tracked wallets\n"
        "/token <symbol> - Get real-time token data\n"
        "/commands - Show this help message"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_wallets:
        user_wallets[user_id] = set()

    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /follow <wallet_address>")
        return

    wallet = context.args[0]
    user_wallets[user_id].add(wallet)
    await update.message.reply_text(f"✅ Now tracking wallet: {wallet}")

async def unfollow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_wallets or not user_wallets[user_id]:
        await update.message.reply_text("You have no wallets being tracked.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /unfollow <wallet_address>")
        return

    wallet = context.args[0]
    user_wallets[user_id].discard(wallet)
    await update.message.reply_text(f"🛑 Stopped tracking wallet: {wallet}")

async def list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallets = user_wallets.get(user_id, set())
    if not wallets:
        await update.message.reply_text("📭 You're not tracking any wallets.")
    else:
        await update.message.reply_text("📋 Tracked wallets:\n" + "\n".join(wallets))

async def token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /token <symbol>")
        return

    symbol = context.args[0].upper()
    headers = {"x-api-key": VYBE_API_KEY}
    response = requests.get(f"{BASE_URL}/tokens/{symbol}", headers=headers)

    if response.status_code != 200:
        await update.message.reply_text("⚠️ Token not found or API error.")
        return

    data = response.json()
    msg = (
        f"📊 *{data.get('name', 'Unknown')}* (${data.get('symbol', symbol)})\n"
        f"Price: ${data.get('price', 'N/A')}\n"
        f"Volume (24h): ${data.get('volume_24h', 'N/A')}\n"
        f"Sentiment: {data.get('sentiment', 'N/A')}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def monitor_wallets(app):
    while True:
        for user_id, wallets in user_wallets.items():
            for wallet in wallets:
                try:
                    headers = {"x-api-key": VYBE_API_KEY}
                    res = requests.get(f"{BASE_URL}/wallets/{wallet}/transactions", headers=headers)
                    if res.status_code == 200:
                        txs = res.json()
                        if txs:
                            latest_tx = txs[0]
                            tx_hash = latest_tx.get("tx_hash")
                            if wallet not in latest_tx_hash or tx_hash != latest_tx_hash[wallet]:
                                latest_tx_hash[wallet] = tx_hash
                                message = (
                                    f"🚨 New transaction detected for wallet `{wallet}`\n"
                                    f"Hash: `{tx_hash}`\n"
                                    f"Amount: {latest_tx.get('amount')} {latest_tx.get('symbol')}"
                                )
                                try:
                                    await app.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
                                except Exception as e:
                                    logging.warning(f"Failed to send message to {user_id}: {e}")
                except Exception as e:
                    logging.error(f"Error checking wallet {wallet}: {e}")
        await asyncio.sleep(60)  # check every 60 seconds

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("commands", commands))
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("unfollow", unfollow))
    app.add_handler(CommandHandler("list", list_wallets))
    app.add_handler(CommandHandler("token", token))

    app.create_task(monitor_wallets(app))

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
