"""
ReviewBot — Telegram bot for approving AI-generated review responses.

Flow:
1. Owner sends /add_review or forwards a review screenshot
2. Bot asks for details (or owner types: "John, 4 stars, Great food loved the pizza")
3. AI generates a response
4. Owner sees: review + proposed response
5. Owner taps: ✅ Approve (copies text) | ✏️ Regenerate | ⏭ Skip
"""
import os
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from ai_responder import generate_response

load_dotenv(Path(__file__).parent.parent / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# --- Data storage (JSON file for MVP) ---
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "businesses.json"
HISTORY_FILE = DATA_DIR / "history.json"


def load_businesses() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_businesses(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_history() -> list:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return []


def save_history(data: list):
    HISTORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_default_business() -> dict | None:
    businesses = load_businesses()
    if businesses:
        return list(businesses.values())[0]
    return None


# --- Conversation states ---
SETUP_NAME, SETUP_TYPE, SETUP_LOCATION, SETUP_TONE = range(4)
REVIEW_INPUT = 10


# --- /start ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    biz = get_default_business()
    if biz:
        await update.message.reply_text(
            f"👋 ReviewBot ready!\n\n"
            f"Business: <b>{biz['name']}</b>\n"
            f"Type: {biz['type']}\n"
            f"Location: {biz['location']}\n"
            f"Tone: {biz['tone']}\n\n"
            f"Send me a review to generate a response.\n"
            f"Format: <code>Author, stars, review text</code>\n\n"
            f"Example:\n<code>Sarah, 5, Absolutely loved it! The staff were so friendly and the food was incredible.</code>\n\n"
            f"Commands:\n"
            f"/review — add a review\n"
            f"/setup — configure business\n"
            f"/stats — view stats",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "👋 Welcome to ReviewBot!\n\n"
            "Let's set up your business first.\n"
            "Use /setup to get started."
        )


# --- /setup ---
async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Let's set up your business.\n\n"
        "What's your <b>business name</b>?",
        parse_mode="HTML",
    )
    return SETUP_NAME


async def setup_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["biz_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"Got it: <b>{context.user_data['biz_name']}</b>\n\n"
        "What <b>type of business</b> is it?\n"
        "(e.g., restaurant, hair salon, dental clinic, plumber, hotel)",
        parse_mode="HTML",
    )
    return SETUP_TYPE


async def setup_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["biz_type"] = update.message.text.strip()
    await update.message.reply_text(
        "Where is it <b>located</b>?\n"
        "(e.g., Canterbury, Kent or London, UK)",
        parse_mode="HTML",
    )
    return SETUP_LOCATION


async def setup_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["biz_location"] = update.message.text.strip()

    keyboard = [
        [
            InlineKeyboardButton("🤝 Friendly", callback_data="tone_friendly"),
            InlineKeyboardButton("👔 Professional", callback_data="tone_professional"),
        ],
        [
            InlineKeyboardButton("😊 Casual", callback_data="tone_casual"),
            InlineKeyboardButton("✨ Warm", callback_data="tone_warm"),
        ],
    ]
    await update.message.reply_text(
        "What <b>tone</b> should responses have?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SETUP_TONE


async def setup_tone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tone_map = {
        "tone_friendly": "friendly and professional",
        "tone_professional": "formal and professional",
        "tone_casual": "casual and friendly",
        "tone_warm": "warm and personal",
    }
    tone = tone_map.get(query.data, "friendly and professional")

    biz = {
        "name": context.user_data["biz_name"],
        "type": context.user_data["biz_type"],
        "location": context.user_data["biz_location"],
        "tone": tone,
    }

    businesses = load_businesses()
    businesses[biz["name"]] = biz
    save_businesses(businesses)

    await query.edit_message_text(
        f"✅ Business configured!\n\n"
        f"<b>{biz['name']}</b>\n"
        f"Type: {biz['type']}\n"
        f"Location: {biz['location']}\n"
        f"Tone: {tone}\n\n"
        f"Now send me a review to generate a response.\n"
        f"Format: <code>Author, stars, review text</code>",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def setup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Setup cancelled.")
    return ConversationHandler.END


# --- Handle review input ---
async def handle_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse review from message and generate AI response."""
    biz = get_default_business()
    if not biz:
        await update.message.reply_text("Set up your business first with /setup")
        return

    text = update.message.text.strip()

    # Parse format: "Author, stars, review text"
    parts = text.split(",", 2)
    if len(parts) < 3:
        await update.message.reply_text(
            "Please use this format:\n"
            "<code>Author, stars, review text</code>\n\n"
            "Example:\n"
            "<code>Sarah, 5, Absolutely loved it! The staff were so friendly.</code>",
            parse_mode="HTML",
        )
        return

    author = parts[0].strip()
    try:
        rating = int(parts[1].strip().replace("stars", "").replace("star", "").strip())
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Rating should be a number 1-5. Try again.")
        return

    review_text = parts[2].strip()

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Generate AI response
    try:
        ai_response = generate_response(
            review_text=review_text,
            rating=rating,
            author=author,
            business_name=biz["name"],
            business_type=biz["type"],
            location=biz["location"],
            tone=biz["tone"],
            api_key=ANTHROPIC_KEY,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ AI generation failed: {e}")
        return

    # Store in context for callback
    review_id = str(hash(f"{author}{review_text}"))
    context.user_data[f"review_{review_id}"] = {
        "author": author,
        "rating": rating,
        "text": review_text,
        "ai_response": ai_response,
        "business": biz["name"],
    }

    # Stars display
    stars = "⭐" * rating + "☆" * (5 - rating)

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{review_id}"),
            InlineKeyboardButton("🔄 Regenerate", callback_data=f"regen_{review_id}"),
        ],
        [
            InlineKeyboardButton("⏭ Skip", callback_data=f"skip_{review_id}"),
        ],
    ]

    await update.message.reply_text(
        f"📝 <b>Review from {author}</b>\n"
        f"{stars}\n\n"
        f"<i>\"{review_text}\"</i>\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"💬 <b>Suggested response:</b>\n\n"
        f"<code>{ai_response}</code>\n\n"
        f"☝️ Tap the response to copy it",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# --- Callback handlers ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, review_id = data.split("_", 1)

    review_data = context.user_data.get(f"review_{review_id}")
    if not review_data:
        await query.edit_message_text("Review data expired. Send the review again.")
        return

    if action == "approve":
        # Save to history
        history = load_history()
        history.append({
            **review_data,
            "status": "approved",
        })
        save_history(history)

        await query.edit_message_text(
            f"✅ <b>Approved!</b>\n\n"
            f"Response for {review_data['author']}'s review:\n\n"
            f"<code>{review_data['ai_response']}</code>\n\n"
            f"☝️ Tap to copy → paste on Google",
            parse_mode="HTML",
        )

    elif action == "regen":
        biz = get_default_business()
        if not biz:
            return

        await query.edit_message_text("🔄 Regenerating...")

        try:
            new_response = generate_response(
                review_text=review_data["text"],
                rating=review_data["rating"],
                author=review_data["author"],
                business_name=biz["name"],
                business_type=biz["type"],
                location=biz["location"],
                tone=biz["tone"],
                api_key=ANTHROPIC_KEY,
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Regeneration failed: {e}")
            return

        review_data["ai_response"] = new_response
        context.user_data[f"review_{review_id}"] = review_data

        stars = "⭐" * review_data["rating"] + "☆" * (5 - review_data["rating"])

        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{review_id}"),
                InlineKeyboardButton("🔄 Regenerate", callback_data=f"regen_{review_id}"),
            ],
            [
                InlineKeyboardButton("⏭ Skip", callback_data=f"skip_{review_id}"),
            ],
        ]

        await query.edit_message_text(
            f"📝 <b>Review from {review_data['author']}</b>\n"
            f"{stars}\n\n"
            f"<i>\"{review_data['text']}\"</i>\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"💬 <b>Suggested response (new):</b>\n\n"
            f"<code>{new_response}</code>\n\n"
            f"☝️ Tap the response to copy it",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action == "skip":
        history = load_history()
        history.append({
            **review_data,
            "status": "skipped",
        })
        save_history(history)
        await query.edit_message_text("⏭ Skipped.")


# --- /stats ---
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = load_history()
    total = len(history)
    approved = sum(1 for h in history if h.get("status") == "approved")
    skipped = sum(1 for h in history if h.get("status") == "skipped")

    biz = get_default_business()
    biz_name = biz["name"] if biz else "Not configured"

    await update.message.reply_text(
        f"📊 <b>ReviewBot Stats</b>\n\n"
        f"Business: {biz_name}\n"
        f"Total reviews: {total}\n"
        f"Approved: {approved}\n"
        f"Skipped: {skipped}\n"
        f"Approval rate: {approved / total * 100:.0f}%" if total > 0 else
        f"📊 <b>ReviewBot Stats</b>\n\nNo reviews processed yet.",
        parse_mode="HTML",
    )


# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Setup conversation
    setup_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", setup_start)],
        states={
            SETUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_name)],
            SETUP_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_type)],
            SETUP_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_location)],
            SETUP_TONE: [CallbackQueryHandler(setup_tone, pattern="^tone_")],
        },
        fallbacks=[CommandHandler("cancel", setup_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(setup_handler)
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(handle_callback))
    # Any text message = review input
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_review))

    log.info("ReviewBot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
