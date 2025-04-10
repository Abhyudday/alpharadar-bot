import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VYBE_API_KEY = os.getenv("VYBE_API_KEY")
BASE_URL = "https://api.vybe.xyz"

# In-memory storage for tracked wallets per user
user_wallets = {}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to AlphaRadar!\nUse /follow <wallet> to track a wallet.\nUse /list to view tracked wallets."
    )

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
        f"📊 *{data['name']}* (${data['symbol']})\n"
        f"Price: ${data['price']}\n"
        f"Volume (24h): ${data['volume_24h']}\n"
        f"Sentiment: {data['sentiment']}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("unfollow", unfollow))
    app.add_handler(CommandHandler("list", list_wallets))
    app.add_handler(CommandHandler("token", token))

    print("Bot is running...")
    app.run_polling()
