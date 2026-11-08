import base64
import hashlib
import hmac
import json
import secrets
import time

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.models.users import Customer, Merchant
from app.services.catalog import CatalogConflictError

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return f"pbkdf2_sha256$260000${salt.hex()}${digest.hex()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def _sign(value: str) -> str:
    return hmac.new(settings.auth_secret.encode(), value.encode(), hashlib.sha256).hexdigest()

def issue_token(subject_id: int, role: str = "customer") -> str:
    body = base64.urlsafe_b64encode(json.dumps({"sub": subject_id, "role": role, "exp": int(time.time()) + 60 * 60 * 24 * 30}, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{body}.{_sign(body)}"

def customer_id_from_token(token: str) -> int | None:
    return subject_id_from_token(token, "customer")

def subject_id_from_token(token: str, role: str) -> int | None:
    try:
        body, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(body)):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(time.time()) or payload.get("role", "customer") != role:
            return None
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

def merchant_signup(session: Session, name: str, slug: str, email: str, username: str, password: str, wallet_address: str) -> Merchant:
    merchant = Merchant(name=name, slug=slug.lower(), email=email.lower(), username=username.lower(), password_hash=hash_password(password), wallet_address=wallet_address.lower())
    session.add(merchant)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("merchant slug, username, email, or wallet already exists") from exc
    session.refresh(merchant)
    return merchant

def merchant_authenticate(session: Session, login: str, password: str) -> Merchant | None:
    merchant = session.exec(select(Merchant).where((Merchant.username == login.lower()) | (Merchant.email == login.lower()))).first()
    if merchant is None or not merchant.password_hash or not verify_password(password, merchant.password_hash):
        return None
    return merchant

def link_merchant_wallet(session: Session, merchant: Merchant, wallet_address: str) -> Merchant:
    merchant.wallet_address = wallet_address.lower()
    session.add(merchant)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("wallet is already linked to another account") from exc
    session.refresh(merchant)
    return merchant

def signup(session: Session, username: str, email: str, password: str) -> Customer:
    customer = Customer(name=username, username=username.lower(), email=email.lower(), password_hash=hash_password(password))
    session.add(customer)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("username or email already exists") from exc
    session.refresh(customer)
    return customer

def authenticate(session: Session, login: str, password: str) -> Customer | None:
    customer = session.exec(select(Customer).where((Customer.username == login.lower()) | (Customer.email == login.lower()))).first()
    if customer is None or not customer.password_hash or not verify_password(password, customer.password_hash):
        return None
    return customer

def link_wallet(session: Session, customer: Customer, wallet_address: str) -> Customer:
    customer.wallet_address = wallet_address.lower()
    session.add(customer)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("wallet is already linked to another account") from exc
    session.refresh(customer)
    return customer
