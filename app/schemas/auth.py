from pydantic import BaseModel, Field

class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

class WalletLinkRequest(BaseModel):
    wallet_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")

class CustomerAccountRead(BaseModel):
    id: int
    username: str
    email: str
    wallet_address: str | None = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerAccountRead

class MerchantSignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    wallet_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")

class MerchantAccountRead(BaseModel):
    id: int
    name: str
    slug: str
    username: str
    email: str
    wallet_address: str | None = None

class MerchantAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    merchant: MerchantAccountRead
