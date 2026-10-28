# Rexco Tg Seller — Black & Gold

A clean Telegram storefront starter for legitimate digital products. It is a separate safe implementation, not a drop-in rebrand of the uploaded account/OTP marketplace code.

## Included
- `/start`, `/products`, `/orders`, `/help`
- Product catalog with prices/descriptions
- Admin `/addproduct Name | Price | Description | Delivery URL`
- Admin `/deactivate PRODUCT_ID`
- Order creation and order history
- Admin `/orders_pending` and `/deliver ORDER_ID`
- Delivery only after an admin independently verifies payment
- MongoDB persistence, environment-based configuration, Docker Compose deployment

## Not included
- Automated UPI/crypto payment verification or wallet balance/recharge
- Account/OTP/session selling, harvesting or management
- Existing database migration from the original bot

## Setup (Docker Compose on a VPS)
1. Install Docker Engine and Docker Compose plugin on your VPS.
2. Copy `.env.example` to `.env` and set `BOT_TOKEN`, `ADMIN_IDS`, support details, and payment instructions.
3. Keep `.env` private; do not commit it to Git. Restrict VPS SSH and keep the OS/Docker updated.
4. Run `docker compose up -d --build`.
5. Check logs with `docker compose logs -f bot`.
6. Add a product as an admin in Telegram:
   `/addproduct PDF Starter Pack | 199 | Beginner digital guide | https://your-domain.example/delivery/file`
7. A buyer creates an order. Verify payment using your payment provider/bank records before running `/deliver ORDER_ID`.

MongoDB is only exposed inside the Compose network. For production, use a strong private VPS, backups, monitoring, and HTTPS-hosted delivery URLs with access controls. Do not place private files on publicly guessable URLs.

## Important notes
- This starter has no automated payment gateway. A payment reference or screenshot alone is not proof of settlement; verify through your payment provider before delivery.
- `Delivery URL` is stored as text and sent to the buyer after approval. Use per-order expiring links if the file is sensitive.
- Before using any third-party source code, verify its license and preserve required notices. This clean starter does not copy the original bot's source.
- This is a starter and has not been connected to your Telegram bot or VPS. Test in a private test bot before production.
