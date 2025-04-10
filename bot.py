import os
import logging
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
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
    keyboard = [
        [InlineKeyboardButton("📋 Commands", callback_data='commands')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 *Welcome to AlphaRadar!*

Stay updated with your favorite wallets & tokens in real time!",
        parse_mode='Markdown', reply_markup=reply_markup
    )

async def commands_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Follow Wallet", callback_data='follow_help')],
        [InlineKeyboardButton("➖ Unfollow Wallet", callback_data='unfollow_help')],
        [InlineKeyboardButton("📜 List Wallets", callback_data='list_wallets')],
        [InlineKeyboardButton("💰 Token Info", callback_data='token_help')],
    ]
    await query.edit_message_text(
        "🛠️ *Available Commands:*", parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def follow_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("ℹ️ Usage: /follow <wallet_address>")

async def unfollow_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("ℹ️ Usage: /unfollow <wallet_address>")

async def token_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("ℹ️ Usage: /token <symbol>")

async def list_wallets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallets = user_wallets.get(user_id, set())
    msg = "📭 You're not tracking any wallets." if not wallets else "📋 *Tracked wallets:*\n" + "\n".join(wallets)
    await update.callback_query.edit_message_text(msg, parse_mode='Markdown')

async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_wallets:
        user_wallets[user_id] = set()

    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /follow <wallet_address>")
        return

    wallet = context.args[0]
    user_wallets[user_id].add(wallet)
    await update.message.reply_text(f"✅ Now tracking wallet: `{wallet}`", parse_mode='Markdown')

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
    await update.message.reply_text(f"🛑 Stopped tracking wallet: `{wallet}`", parse_mode='Markdown')

async def list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallets = user_wallets.get(user_id, set())
    if not wallets:
        await update.message.reply_text("📭 You're not tracking any wallets.")
    else:
        await update.message.reply_text("📋 *Tracked wallets:*\n" + "\n".join(wallets), parse_mode='Markdown')

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
    await asyncio.sleep(5)  # ensure bot is fully ready
    while True:
        for user_id, wallets in user_wallets.items():
            for wallet in wallets:
                try:
                    headers = {"x-api-key": VYBE_API_KEY}
                    res = requests.get(f"{BASE_URL}/wallets/{wallet}/transactions", headers=headers)
                    if res.status_code == 200:
                        txs = res.json().get("transactions", [])
                        if txs:
                            latest_tx = txs[0]
                            tx_hash = latest_tx.get("tx_hash")
                            if wallet not in latest_tx_hash or tx_hash != latest_tx_hash[wallet]:
                                latest_tx_hash[wallet] = tx_hash
                                message = (
                                    f"🚨 *New transaction detected*\n\n"
                                    f"👜 Wallet: `{wallet}`\n"
                                    f"🔗 Txn Hash: `{tx_hash}`\n"
                                    f"💸 Amount: {latest_tx.get('amount')} {latest_tx.get('symbol')}"
                                )
                                try:
                                    await app.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
                                except Exception as e:
                                    logging.warning(f"Failed to send message to {user_id}: {e}")
                except Exception as e:
                    logging.error(f"Error checking wallet {wallet}: {e}")
        await asyncio.sleep(60)

async def post_init(app):
    app.create_task(monitor_wallets(app))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("unfollow", unfollow))
    app.add_handler(CommandHandler("list", list_wallets))
    app.add_handler(CommandHandler("token", token))
    app.add_handler(CallbackQueryHandler(commands_menu, pattern='commands'))
    app.add_handler(CallbackQueryHandler(follow_help, pattern='follow_help'))
    app.add_handler(CallbackQueryHandler(unfollow_help, pattern='unfollow_help'))
    app.add_handler(CallbackQueryHandler(token_help, pattern='token_help'))
    app.add_handler(CallbackQueryHandler(list_wallets_menu, pattern='list_wallets'))

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
