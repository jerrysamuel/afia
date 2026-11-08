from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.models.users import Customer
from app.schemas.auth import AuthResponse, CustomerAccountRead, LoginRequest, SignupRequest, WalletLinkRequest
from app.services.auth import authenticate, customer_id_from_token, issue_token, link_wallet, signup
from app.services.catalog import CatalogConflictError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

def _account(customer: Customer) -> CustomerAccountRead:
    return CustomerAccountRead(id=customer.id, username=customer.username or customer.name, email=customer.email, wallet_address=customer.wallet_address)

def current_customer(authorization: str | None, session: Session) -> Customer:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    customer_id = customer_id_from_token(authorization[7:].strip())
    customer = session.get(Customer, customer_id) if customer_id else None
    if customer is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return customer

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup_endpoint(data: SignupRequest, session: Session = Depends(get_session)):
    try:
        customer = signup(session, data.username, data.email, data.password)
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AuthResponse(access_token=issue_token(customer.id), customer=_account(customer))

@router.post("/login", response_model=AuthResponse)
def login_endpoint(data: LoginRequest, session: Session = Depends(get_session)):
    customer = authenticate(session, data.login, data.password)
    if customer is None:
        raise HTTPException(status_code=401, detail="invalid login or password")
    return AuthResponse(access_token=issue_token(customer.id), customer=_account(customer))

@router.get("/me", response_model=CustomerAccountRead)
def me_endpoint(authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
    return _account(current_customer(authorization, session))

@router.post("/wallet", response_model=CustomerAccountRead)
def link_wallet_endpoint(data: WalletLinkRequest, authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
    try:
        return _account(link_wallet(session, current_customer(authorization, session), data.wallet_address))
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
