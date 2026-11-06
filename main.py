from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(title="Afia", version="0.1.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
# In dev the Vite proxy handles /api, so CORS isn't needed for localhost.
# For production set CORS_ORIGINS=https://your-frontend.com in .env
_origins = list(settings.cors_origins) or [
    "http://localhost:3000",   # Next.js dev server
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.endpoints.catalog import router as catalog_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.payments import router as payments_router
from app.api.v1.endpoints.carts import router as carts_router
from app.api.v1.endpoints.agent import router as agent_router
from app.api.v1.endpoints.agent_shopping import router as agent_shopping_router
from app.api.v1.endpoints.auth import router as auth_router

# FastAPI 0.141 keeps included routers as deferred route groups. Registering
# this small application router directly keeps OpenAPI generation and local
# ASGI testing compatible across the supported FastAPI versions.
app.router.routes.extend(catalog_router.routes)
app.router.routes.extend(orders_router.routes)
app.router.routes.extend(payments_router.routes)
app.router.routes.extend(carts_router.routes)
app.router.routes.extend(agent_router.routes)
app.router.routes.extend(agent_shopping_router.routes)
app.router.routes.extend(auth_router.routes)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root():
    return {}
