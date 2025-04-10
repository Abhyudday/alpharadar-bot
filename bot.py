import os
import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VYBE_API_KEY = os.getenv("VYBE_API_KEY")
BASE_URL = "https://api.vybe.xyz"

user_wallets = {}  # {user_id: set(wallets)}
latest_tx_hash = {}  # {wallet: last_seen_tx_hash}

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to AlphaRadar!\nUse /commands to view available features."
    )

async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠️ Available Commands:\n"
        "/start - Welcome message\n"
        "/follow <wallet> - Start tracking a wallet\n"
        "/unfollow <wallet> - Stop tracking a wallet\n"
        "/list - Show your tracked wallets\n"
        "/token <symbol> - Get real-time token data\n"
        "/commands - Show this help message"
    )

async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = context.args[0] if context.args else None

    if not wallet:
        await update.message.reply_text("❌ Usage: /follow <wallet_address>")
        return

    user_wallets.setdefault(user_id, set()).add(wallet)
    await update.message.reply_text(f"✅ Now tracking wallet: {wallet}")

async def unfollow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = context.args[0] if context.args else None

    if not wallet:
        await update.message.reply_text("❌ Usage: /unfollow <wallet_address>")
        return

    user_wallets.get(user_id, set()).discard(wallet)
    await update.message.reply_text(f"🛑 Stopped tracking wallet: {wallet}")

async def list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallets = user_wallets.get(user_id, set())

    if not wallets:
        await update.message.reply_text("📭 You're not tracking any wallets.")
    else:
        await update.message.reply_text("📋 Tracked wallets:\n" + "\n".join(wallets))

async def token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /token <symbol>")
        return

    symbol = context.args[0].upper()
    headers = {"x-api-key": VYBE_API_KEY}
    res = requests.get(f"{BASE_URL}/tokens/{symbol}", headers=headers)

    if res.status_code != 200:
        await update.message.reply_text("⚠️ Token not found or API error.")
        return

    data = res.json()
    await update.message.reply_text(
        f"📊 {data.get('name', 'Unknown')} (${data.get('symbol', symbol)})\n"
        f"Price: ${data.get('price', 'N/A')}\n"
        f"Volume (24h): ${data.get('volume_24h', 'N/A')}\n"
        f"Sentiment: {data.get('sentiment', 'N/A')}"
    )

async def monitor_wallets(app):
    await asyncio.sleep(5)
    while True:
        for user_id, wallets in user_wallets.items():
            for wallet in wallets:
                try:
                    headers = {"x-api-key": VYBE_API_KEY}
                    res = requests.get(f"{BASE_URL}/wallets/{wallet}/transactions", headers=headers)

                    if res.status_code == 200:
                        data = res.json()
                        txs = data.get("transactions", [])

                        if txs:
                            latest_tx = txs[0]
                            tx_hash = latest_tx.get("tx_hash")

                            if wallet not in latest_tx_hash or tx_hash != latest_tx_hash[wallet]:
                                latest_tx_hash[wallet] = tx_hash

                                amount = latest_tx.get("amount", "N/A")
                                symbol = latest_tx.get("symbol", "SOL")
                                time = latest_tx.get("timestamp", "Unknown time")

                                msg = (
                                    f"🚨 *New Transaction Detected!*\n"
                                    f"📍 Wallet: `{wallet}`\n"
                                    f"💰 Amount: `{amount}` {symbol}\n"
                                    f"🕒 Time: {time}\n"
                                    f"🔗 Hash: `{tx_hash}`"
                                )
                                await app.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
                    else:
                        logging.warning(f"API failed for {wallet} — {res.status_code}: {res.text}")

                except Exception as e:
                    logging.error(f"Error fetching tx for {wallet}: {e}")
        await asyncio.sleep(60)

async def post_init(app):
    app.create_task(monitor_wallets(app))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("commands", commands))
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("unfollow", unfollow))
    app.add_handler(CommandHandler("list", list_wallets))
    app.add_handler(CommandHandler("token", token))

    logging.info("Bot is live!")
    app.run_polling()

if __name__ == "__main__":
    main()
