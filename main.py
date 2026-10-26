from fastapi import FastAPI

app = FastAPI()

from app.api.v1.endpoints.catalog import router as catalog_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.payments import router as payments_router
from app.api.v1.endpoints.carts import router as carts_router
from app.api.v1.endpoints.agent import router as agent_router
from app.api.v1.endpoints.agent_shopping import router as agent_shopping_router

# FastAPI 0.141 keeps included routers as deferred route groups. Registering
# this small application router directly keeps OpenAPI generation and local
# ASGI testing compatible across the supported FastAPI versions.
app.router.routes.extend(catalog_router.routes)
app.router.routes.extend(orders_router.routes)
app.router.routes.extend(payments_router.routes)
app.router.routes.extend(carts_router.routes)
app.router.routes.extend(agent_router.routes)
app.router.routes.extend(agent_shopping_router.routes)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root():
    return {}
