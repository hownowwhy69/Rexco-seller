import asyncio
import html
import logging
import os
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("rexco")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "rexco_tg_seller").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
BRAND_NAME = os.getenv("BRAND_NAME", "Rexco Tg Seller")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")
PAYMENT_INSTRUCTIONS = os.getenv("PAYMENT_INSTRUCTIONS", "Contact support for payment instructions.")
CURRENCY = os.getenv("CURRENCY", "INR")

if not BOT_TOKEN or not MONGO_URI or not ADMIN_IDS:
    raise RuntimeError("Set BOT_TOKEN, MONGO_URI and ADMIN_IDS in .env before starting")

mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo[DB_NAME]
users = db.users
products = db.products
orders = db.orders
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

GOLD = "🟡"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def home_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ Browse Products", callback_data="products")],
        [InlineKeyboardButton(text="📦 My Orders", callback_data="myorders"), InlineKeyboardButton(text="💳 Payment Help", callback_data="payhelp")],
        [InlineKeyboardButton(text="🆘 Support", url=f"https://t.me/{SUPPORT_USERNAME}")] if SUPPORT_USERNAME else [InlineKeyboardButton(text="ℹ️ About", callback_data="about")]
    ])

@dp.message(CommandStart())
async def start(message: Message):
    users.update_one({"_id": message.from_user.id}, {"$set": {
        "username": message.from_user.username,
        "full_name": message.from_user.full_name,
        "last_seen": datetime.now(timezone.utc)
    }, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
    await message.answer(
        f"<b>🖤 {html.escape(BRAND_NAME)}</b>\n"
        f"<i>Premium digital products • Secure order handling</i>\n\n"
        "Welcome! Browse the catalog, select a product and follow the payment instructions. "
        "Your order is delivered after an administrator verifies payment.",
        reply_markup=home_keyboard()
    )

async def show_products(target, edit=False):
    items = list(products.find({"active": True}).sort("created_at", -1).limit(40))
    if not items:
        text = "🛍️ <b>Rexco Catalog</b>\n\nNo products are listed yet. Please check back later."
        if edit: await target.edit_text(text, reply_markup=home_keyboard())
        else: await target.answer(text, reply_markup=home_keyboard())
        return
    rows = [[InlineKeyboardButton(text=f"{GOLD} {p['name']} — {CURRENCY} {p['price']:.2f}", callback_data=f"product:{p['_id']}")] for p in items]
    rows.append([InlineKeyboardButton(text="⬅️ Home", callback_data="home")])
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    text = f"<b>🖤 {html.escape(BRAND_NAME)} | Catalog</b>\nChoose a digital product below:"
    if edit: await target.edit_text(text, reply_markup=markup)
    else: await target.answer(text, reply_markup=markup)

@dp.callback_query(F.data == "products")
async def products_menu(cq: CallbackQuery):
    await cq.answer(); await show_products(cq.message, edit=True)

@dp.callback_query(F.data.startswith("product:"))
async def product_detail(cq: CallbackQuery):
    await cq.answer()
    from bson import ObjectId
    try: product_id = ObjectId(cq.data.split(":", 1)[1])
    except Exception: return await cq.answer("Invalid product.", show_alert=True)
    p = products.find_one({"_id": product_id, "active": True})
    if not p: return await cq.answer("This product is unavailable.", show_alert=True)
    text = (f"<b>{html.escape(p['name'])}</b>\n\n{html.escape(p.get('description', 'Digital product'))}\n\n"
            f"<b>Price:</b> {CURRENCY} {p['price']:.2f}\n\n"
            "To order, press the button. Complete payment using the instructions and send the reference to support/admin.")
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Place Order", callback_data=f"order:{p['_id']}")],
        [InlineKeyboardButton(text="⬅️ Catalog", callback_data="products")]
    ])
    await cq.message.edit_text(text, reply_markup=markup)

@dp.callback_query(F.data.startswith("order:"))
async def place_order(cq: CallbackQuery):
    await cq.answer()
    from bson import ObjectId
    try: pid = ObjectId(cq.data.split(":", 1)[1])
    except Exception: return await cq.answer("Invalid product.", show_alert=True)
    p = products.find_one({"_id": pid, "active": True})
    if not p: return await cq.answer("Product unavailable.", show_alert=True)
    order = {"user_id": cq.from_user.id, "username": cq.from_user.username, "product_id": p["_id"],
             "product_name": p["name"], "price": p["price"], "status": "awaiting_payment",
             "created_at": datetime.now(timezone.utc)}
    result = orders.insert_one(order)
    await cq.message.answer(
        f"<b>🧾 Order created</b>\nOrder: <code>{result.inserted_id}</code>\n"
        f"Product: {html.escape(p['name'])}\nAmount: <b>{CURRENCY} {p['price']:.2f}</b>\n\n"
        f"{html.escape(PAYMENT_INSTRUCTIONS)}\n\nAfter paying, send the order ID and payment proof to support. Delivery is sent after verification.")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🛒 <b>New order</b>\nID: <code>{result.inserted_id}</code>\n"
                f"Product: {html.escape(p['name'])}\nAmount: {CURRENCY} {p['price']:.2f}\n"
                f"Buyer: {html.escape(cq.from_user.full_name)} (<code>{cq.from_user.id}</code>)\n"
                f"Use /orders_pending to review. Approve only after independently verifying payment.")
        except Exception: log.exception("Could not notify admin %s", admin_id)

@dp.callback_query(F.data == "myorders")
async def my_orders(cq: CallbackQuery):
    await cq.answer()
    found = list(orders.find({"user_id": cq.from_user.id}).sort("created_at", -1).limit(10))
    if not found: return await cq.message.edit_text("📦 You don't have any orders yet.", reply_markup=home_keyboard())
    lines = ["<b>📦 Your latest orders</b>"]
    for o in found:
        lines.append(f"• <code>{o['_id']}</code> — {html.escape(o['product_name'])} — {html.escape(o['status'])}")
    await cq.message.edit_text("\n".join(lines), reply_markup=home_keyboard())

@dp.callback_query(F.data == "payhelp")
async def pay_help(cq: CallbackQuery):
    await cq.answer(); await cq.message.edit_text(f"<b>💳 Payment Help</b>\n\n{html.escape(PAYMENT_INSTRUCTIONS)}", reply_markup=home_keyboard())

@dp.callback_query(F.data == "about")
async def about(cq: CallbackQuery):
    await cq.answer(); await cq.message.edit_text(f"<b>🖤 {html.escape(BRAND_NAME)}</b>\nDigital products storefront. Orders are manually verified before delivery.", reply_markup=home_keyboard())

@dp.callback_query(F.data == "home")
async def home(cq: CallbackQuery):
    await cq.answer(); await cq.message.edit_text(f"<b>🖤 {html.escape(BRAND_NAME)}</b>\nChoose an option below.", reply_markup=home_keyboard())

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = "/start — open store\n/products — browse catalog\n/orders — see your orders\n"
    if is_admin(message.from_user.id):
        text += ("\n<b>Admin commands</b>\n"
                 "/addproduct Name | Price | Description | Delivery URL\n"
                 "/deactivate PRODUCT_ID\n/orders_pending — list pending orders\n"
                 "/deliver ORDER_ID — deliver after payment verification\n")
    await message.answer(text)

@dp.message(Command("products"))
async def products_cmd(message: Message): await show_products(message)

@dp.message(Command("orders"))
async def orders_cmd(message: Message):
    found = list(orders.find({"user_id": message.from_user.id}).sort("created_at", -1).limit(10))
    if not found: return await message.answer("You don't have any orders yet.")
    await message.answer("<b>Your orders</b>\n" + "\n".join(f"<code>{o['_id']}</code> — {html.escape(o['product_name'])}: {html.escape(o['status'])}" for o in found))

@dp.message(Command("addproduct"))
async def add_product(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("Not authorized.")
    payload = message.text.partition(" ")[2]
    parts = [x.strip() for x in payload.split("|", 3)]
    if len(parts) != 4 or not parts[0]:
        return await message.answer("Format: /addproduct Name | Price | Description | Delivery URL")
    try: price = float(parts[1]); assert price > 0
    except Exception: return await message.answer("Price must be a positive number.")
    result = products.insert_one({"name": parts[0], "price": round(price, 2), "description": parts[2],
        "delivery_url": parts[3], "active": True, "created_at": datetime.now(timezone.utc), "created_by": message.from_user.id})
    await message.answer(f"Added <b>{html.escape(parts[0])}</b>. Product ID: <code>{result.inserted_id}</code>")

@dp.message(Command("deactivate"))
async def deactivate_product(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("Not authorized.")
    from bson import ObjectId
    try: pid = ObjectId(message.text.split(maxsplit=1)[1])
    except Exception: return await message.answer("Usage: /deactivate PRODUCT_ID")
    result = products.update_one({"_id": pid}, {"$set": {"active": False}})
    await message.answer("Product deactivated." if result.modified_count else "Product not found/already inactive.")

@dp.message(Command("orders_pending"))
async def pending_orders(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("Not authorized.")
    found = list(orders.find({"status": "awaiting_payment"}).sort("created_at", 1).limit(20))
    if not found: return await message.answer("No orders awaiting payment.")
    await message.answer("<b>Pending orders</b>\n" + "\n".join(f"<code>{o['_id']}</code> — {html.escape(o['product_name'])} — {CURRENCY} {o['price']:.2f} — user <code>{o['user_id']}</code>" for o in found))

@dp.message(Command("deliver"))
async def deliver_order(message: Message):
    if not is_admin(message.from_user.id): return await message.answer("Not authorized.")
    from bson import ObjectId
    try: oid = ObjectId(message.text.split(maxsplit=1)[1])
    except Exception: return await message.answer("Usage: /deliver ORDER_ID — only after verifying payment.")
    # Conditional update prevents duplicate delivery attempts through this command.
    order = orders.find_one_and_update({"_id": oid, "status": "awaiting_payment"},
        {"$set": {"status": "delivered", "verified_by": message.from_user.id, "delivered_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.BEFORE)
    if not order: return await message.answer("Order not found or not awaiting payment; no delivery sent.")
    product = products.find_one({"_id": order["product_id"]})
    if not product:
        orders.update_one({"_id": oid}, {"$set": {"status": "delivery_error"}})
        return await message.answer("Product record missing. Order marked for manual review.")
    try:
        await bot.send_message(order["user_id"], f"✅ <b>Payment verified — delivery</b>\nOrder: <code>{oid}</code>\nProduct: {html.escape(order['product_name'])}\n\n{html.escape(product['delivery_url'])}")
        await message.answer(f"Delivery sent for order <code>{oid}</code>.")
    except Exception:
        orders.update_one({"_id": oid}, {"$set": {"status": "delivery_error"}})
        await message.answer("Could not send delivery. Order marked for manual review.")

async def main():
    mongo.admin.command("ping")
    log.info("Starting %s", BRAND_NAME)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
