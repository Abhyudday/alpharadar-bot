import os
import logging
import asyncio
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VYBE_API_KEY = os.getenv("VYBE_API_KEY")

BASE_URL = "https://api.vybe.xyz/v1/solana"

# Enable logging
logging.basicConfig(level=logging.INFO)

# In-memory storage
user_wallets = {}  # {user_id: set(wallets)}
latest_tx_hash = {}  # {wallet: last_seen_tx_hash}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to AlphaRadar!\nUse /commands to see all available features."
    )

async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛠️ Available Commands:\n"
        "/start - Welcome message\n"
        "/follow <wallet> - Start tracking a wallet\n"
        "/unfollow <wallet> - Stop tracking a wallet\n"
        "/list - Show your tracked wallets\n"
        "/commands - Show this help message"
    )
    await update.message.reply_text(msg)

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
        await update.message.reply_text("❌ You're not tracking any wallets.")
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

async def monitor_wallets(app):
    await asyncio.sleep(5)
    async with httpx.AsyncClient() as client:
        while True:
            for user_id, wallets in user_wallets.items():
                for wallet in wallets:
                    try:
                        url = f"{BASE_URL}/wallets/{wallet}/txs"
                        headers = {"x-api-key": VYBE_API_KEY}
                        res = await client.get(url, headers=headers)

                        if res.status_code == 200:
                            txs = res.json().get("transactions", [])
                            if txs:
                                latest = txs[0]
                                tx_hash = latest.get("signature")
                                if wallet not in latest_tx_hash or tx_hash != latest_tx_hash[wallet]:
                                    latest_tx_hash[wallet] = tx_hash
                                    amount = latest.get("amount", "N/A")
                                    token = latest.get("symbol", "SOL")
                                    link = f"https://solscan.io/tx/{tx_hash}"

                                    message = (
                                        f"🚨 New transaction for `{wallet}`\n"
                                        f"*Amount*: {amount} {token}\n"
                                        f"[View on Solscan]({link})"
                                    )
                                    await app.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown", disable_web_page_preview=True)
                    except Exception as e:
                        logging.warning(f"Error monitoring wallet {wallet}: {e}")
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

    logging.info("🚀 Bot is now running.")
    app.run_polling()

if __name__ == "__main__":
    main()
