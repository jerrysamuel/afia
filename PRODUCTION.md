# Afia production deployment

Set the hosting service root directory to `afia`.

Build command:

```bash
pip install .
```

Start command:

```bash
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
CORS_ORIGINS=https://your-frontend-domain.example
AUTH_SECRET=<long-random-secret>
X402_API_KEY=<live-key-from-x402.celo.org>
X402_FACILITATOR_URL=https://api.x402.celo.org
X402_NETWORK=eip155:42220
X402_ASSET=0xD2ab3C9A02DBBAB236BfEC45D1d755DF4267F771
X402_ASSET_NAME=Tether America USD
X402_ASSET_VERSION=1
X402_MAX_TIMEOUT_SECONDS=300
```

`X402_PAY_TO` is optional in production and is only a development fallback.
Every merchant must be created with a valid Celo wallet address. Payment
records snapshot that address, and x402 requirements use the snapshot for the
order's merchant.

Do not set `X402_PAYER_PRIVATE_KEY` in the production service. Buyer wallets
sign in the browser; the backend never needs a buyer private key.

After deployment, check `/health`, then create a merchant with
`wallet_address`, create its store and product, and test the complete checkout
flow before creating the hackathon attribution tag.
