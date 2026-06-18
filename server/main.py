import os
import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ── Wired today: Clerk auth + Postgres orders ──────────────────────────
# ── NOT wired yet: Surge account+campaign setup + send shipped-SMS +
#    receive Surge delivery webhook. See README + AGENT TASK below.

ORDERS_DB_URL = os.environ["ORDERS_DB_URL"]
CLERK_JWT_ISSUER = os.environ["CLERK_JWT_ISSUER"]
CLERK_JWKS_URL = f"{CLERK_JWT_ISSUER}/.well-known/jwks.json"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer_scheme = HTTPBearer()
jwks_client = jwt.PyJWKClient(CLERK_JWKS_URL)


def verify_clerk_jwt(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(creds.credentials).key
        payload = jwt.decode(
            creds.credentials, signing_key, algorithms=["RS256"],
            issuer=CLERK_JWT_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}")
    return payload["sub"]


class OrderRequest(BaseModel):
    sku: str = "acme-pro-49-99"
    quantity: int = 1
    customer_phone: str | None = None  # E.164, needed for SMS shipping notify


@app.post("/api/orders")
def create_order(
    req: OrderRequest, user_id: str = Depends(verify_clerk_jwt),
):
    """Create an order row in Postgres. Clerk-gated."""
    order_id = _insert_order(
        user_id=user_id, sku=req.sku, quantity=req.quantity,
        customer_phone=req.customer_phone,
    )
    return {"order_id": order_id, "user_id": user_id, "sku": req.sku}


@app.get("/api/orders/{order_id}")
def get_order(order_id: str, user_id: str = Depends(verify_clerk_jwt)):
    row = _fetch_order(order_id=order_id, user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row


@app.post("/api/orders/{order_id}/ship")
def mark_shipped(order_id: str, user_id: str = Depends(verify_clerk_jwt)):
    """Flip the order status to shipped. SMS notify is NOT YET wired."""
    row = _fetch_order(order_id=order_id, user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    _update_order(order_id=order_id, status="shipped")
    # TODO: agent will trigger the Surge SMS here
    return {"order_id": order_id, "status": "shipped", "sms_sent": False}


# ══════════════════════════════════════════════════════════════════════
# AGENT TASK — wire Surge here.
#
# Three handlers to add:
#
#   POST /api/surge/setup
#       → Provision a Surge account, register a 10DLC campaign for
#         "transactional order notifications", and attach a phone
#         number. Persist the account_id + phone_number_id so we don't
#         re-provision on every send. Returns the readiness status.
#
#   POST /api/orders/{order_id}/ship  (modify the existing handler)
#       → After flipping status to "shipped", call Surge to send a
#         templated SMS to the customer's phone with the tracking URL.
#         Capture the message_id on the order row so the webhook can
#         link back.
#
#   POST /api/surge-webhook
#       → Receive Surge webhook events (message.sent, message.delivered,
#         message.failed). On message.delivered, mark the order's
#         sms_delivered_at timestamp so support can see the customer
#         was notified. On message.failed, mark sms_failed_reason.
#
# Verify the integration shape FIRST via the fetchsandbox MCP server:
#
#   - mcp__fetchsandbox__list_specs filter="surge"
#   - mcp__fetchsandbox__list_workflows  (spec_id from above)
#   - mcp__fetchsandbox__run_workflow workflow_name="account_setup_with_campaign_and_number"
#   - mcp__fetchsandbox__run_workflow workflow_name="send_message_observe_delivery_lifecycle"
#
# Those two cover the integration end-to-end. Mirror their request /
# response shapes into the three handlers above. No Surge API key
# needed — the sandbox proxies schema-validated responses. When this
# is wired, swap the sandbox base URL for https://api.surge.app and
# your real Bearer token.
#
# COMPLIANCE NOTE: before any production SMS to a NEW contact who
# hasn't previously consented, run the verification_lifecycle_opt_in
# workflow first. TCPA + carrier policy require documented opt-in.
# ══════════════════════════════════════════════════════════════════════


@app.post("/api/surge/setup")
def surge_setup(_user_id: str = Depends(verify_clerk_jwt)):
    """STUB — agent will wire this to Surge."""
    raise HTTPException(
        status_code=501,
        detail="not wired — see README + AGENT TASK in server/main.py",
    )


@app.post("/api/surge-webhook")
async def surge_webhook(_request: Request):
    """STUB — agent will wire this to Surge."""
    raise HTTPException(
        status_code=501,
        detail="not wired — see README + AGENT TASK in server/main.py",
    )


# ── DB helpers (stubs — wire to real Postgres in dev) ──────────────────

def _insert_order(*, user_id: str, sku: str, quantity: int, customer_phone: str | None) -> str:
    response = httpx.post(
        f"{ORDERS_DB_URL}/orders",
        json={"user_id": user_id, "sku": sku, "quantity": quantity,
              "customer_phone": customer_phone, "status": "pending"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["id"]


def _fetch_order(*, order_id: str, user_id: str) -> dict | None:
    response = httpx.get(
        f"{ORDERS_DB_URL}/orders/{order_id}",
        params={"user_id": user_id}, timeout=10.0,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _update_order(*, order_id: str, status: str) -> None:
    response = httpx.patch(
        f"{ORDERS_DB_URL}/orders/{order_id}",
        json={"status": status}, timeout=10.0,
    )
    response.raise_for_status()
