"""
Mini Market API - FastAPI REST API for Mini Market UI

SETUP INSTRUCTIONS
==================
1) (Optional) Create a virtual environment:
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate

2) Install dependencies:
   pip install -r requirements.txt

3) Run the server:
   uvicorn app:app --reload --port 8000

Frontend integration (Vite):
- React dev server: http://localhost:5173
- If you use a Vite proxy (recommended), the UI can call /api/... directly.

AUTH
====
This API implements a simple in-memory user system with token-based auth.
- Register: POST /api/auth/register
- Login:    POST /api/auth/login  -> returns Bearer token
- Use:      Authorization: Bearer <token>

NOTE: Storage is in-memory (resets when the server restarts). Swap it for a DB later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import hashlib
import hmac
import secrets

from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="Mini Market API",
    description="REST API for Mini Market supermarket website",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# MODELS
# =============================================================================

class Product(BaseModel):
    """Product model representing items in the supermarket."""
    id: int
    name: str
    description: str
    price: float
    unit: str  # e.g. "kg", "item", "bottle"
    category: str  # e.g. "fruits", "dairy", "bakery"
    is_available: bool


class Offer(BaseModel):
    """Offer model representing discounts and special deals."""
    id: int
    title: str
    description: str
    old_price: float
    new_price: float
    product_id: Optional[int] = None
    is_active: bool


class ContactMessage(BaseModel):
    """Contact form message model."""
    name: str
    email: EmailStr
    message: str


class ContactResponse(BaseModel):
    status: str
    message: str
    received_at: str


# ---- Auth models ----

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=200)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    username: str


class MeResponse(BaseModel):
    username: str


# ---- Cart models (per user) ----

class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=999)


class CartItemOut(BaseModel):
    product_id: int
    name: str
    unit: str
    unit_price: float
    quantity: int
    line_total: float


class CartSummary(BaseModel):
    username: str
    items: List[CartItemOut]
    total: float
    updated_at: str


# =============================================================================
# IN-MEMORY STORAGE
# =============================================================================

PRODUCTS: List[Product] = [
    Product(
        id=1,
        name="Fresh Red Apples",
        description="Crisp and juicy red apples, perfect for snacks and desserts",
        price=2.49,
        unit="kg",
        category="fruits",
        is_available=True,
    ),
    Product(
        id=2,
        name="Whole Milk 1L",
        description="Rich and creamy whole milk, ideal for coffee and cereal",
        price=1.39,
        unit="bottle",
        category="dairy",
        is_available=True,
    ),
    Product(
        id=3,
        name="White Bread",
        description="Freshly baked white bread, 500g loaf",
        price=1.99,
        unit="item",
        category="bakery",
        is_available=True,
    ),
    Product(
        id=4,
        name="Free Range Eggs",
        description="12 large free-range eggs",
        price=3.29,
        unit="item",
        category="dairy",
        is_available=True,
    ),
    Product(
        id=5,
        name="Potato Chips",
        description="Crispy salted potato chips, 150g bag",
        price=0.99,
        unit="item",
        category="snacks",
        is_available=True,
    ),
    Product(
        id=6,
        name="Orange Juice",
        description="Fresh orange juice, 1L bottle",
        price=2.99,
        unit="bottle",
        category="drinks",
        is_available=True,
    ),
]

OFFERS: List[Offer] = [
    Offer(
        id=1,
        title="Organic Bananas",
        description="This week only — perfectly ripe and full of flavor.",
        old_price=1.99,
        new_price=1.29,
        product_id=None,
        is_active=True,
    ),
    Offer(
        id=2,
        title="Olive Oil",
        description="Premium extra virgin olive oil — limited stock.",
        old_price=12.50,
        new_price=9.99,
        product_id=None,
        is_active=True,
    ),
    Offer(
        id=3,
        title="Breakfast Bundle",
        description="Milk + eggs + bread combo discount.",
        old_price=10.49,
        new_price=7.99,
        product_id=None,
        is_active=True,
    ),
]

def _product_by_id(pid: int) -> Optional[Product]:
    return next((p for p in PRODUCTS if p.id == pid), None)

def _offer_by_id(oid: int) -> Optional[Offer]:
    return next((o for o in OFFERS if o.id == oid), None)


# ---- Users + tokens (in-memory) ----

@dataclass
class UserRecord:
    username: str
    password_salt: str
    password_hash: str  # hex
    created_at: str

USERS: Dict[str, UserRecord] = {}
TOKENS: Dict[str, str] = {}  # token -> username

# ---- Cart per user (in-memory) ----
# username -> product_id -> quantity
CARTS: Dict[str, Dict[int, int]] = {}
CART_UPDATED_AT: Dict[str, str] = {}


# =============================================================================
# AUTH HELPERS
# =============================================================================

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return dk.hex()

def _verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    actual = _hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash_hex)

def _issue_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    TOKENS[token] = username
    return token

def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1]
    if scheme != "bearer":
        return None
    return token

def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    token = _extract_bearer_token(authorization)
    if not token or token not in TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return TOKENS[token]


# =============================================================================
# PUBLIC ENDPOINTS (NO AUTH)
# =============================================================================

@app.get("/api/products", response_model=List[Product])
async def list_products(
    category: Optional[str] = Query(default=None, description="Filter products by category"),
    available_only: bool = Query(default=False, description="Return only products in stock"),
):
    items = PRODUCTS
    if category:
        items = [p for p in items if p.category.lower() == category.lower()]
    if available_only:
        items = [p for p in items if p.is_available]
    return items


@app.get("/api/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    product = _product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/api/offers", response_model=List[Offer])
async def list_offers(include_inactive: bool = Query(default=False)):
    if include_inactive:
        return OFFERS
    return [o for o in OFFERS if o.is_active]


@app.get("/api/offers/{offer_id}", response_model=Offer)
async def get_offer(offer_id: int):
    offer = _offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@app.post("/api/contact", response_model=ContactResponse)
async def contact(message: ContactMessage):
    # Simulate saving / emailing by printing
    print("CONTACT MESSAGE:", message.model_dump())
    return ContactResponse(
        status="ok",
        message="Thank you for contacting Mini Market.",
        received_at=datetime.utcnow().isoformat(),
    )


# =============================================================================
# AUTH ENDPOINTS
# =============================================================================

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    username = req.username.strip()
    if username.lower() in (u.lower() for u in USERS.keys()):
        raise HTTPException(status_code=400, detail="Username already exists")

    salt = secrets.token_bytes(16)
    record = UserRecord(
        username=username,
        password_salt=salt.hex(),
        password_hash=_hash_password(req.password, salt),
        created_at=datetime.utcnow().isoformat(),
    )
    USERS[username] = record

    # Initialize empty cart for the user
    CARTS[username] = {}
    CART_UPDATED_AT[username] = datetime.utcnow().isoformat()

    return {"status": "ok", "message": "User registered successfully"}


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    username = req.username.strip()
    # Case-sensitive usernames (simpler), but allow matching existing key
    if username not in USERS:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    record = USERS[username]
    if not _verify_password(req.password, record.password_salt, record.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _issue_token(username)
    return AuthResponse(token=token, username=username)


@app.get("/api/auth/me", response_model=MeResponse)
async def me(current_user: str = Depends(get_current_user)):
    return MeResponse(username=current_user)


@app.post("/api/auth/logout")
async def logout(current_user: str = Depends(get_current_user), authorization: Optional[str] = Header(default=None)):
    token = _extract_bearer_token(authorization)
    if token and token in TOKENS:
        del TOKENS[token]
    return {"status": "ok", "message": "Logged out"}


# =============================================================================
# CART ENDPOINTS (AUTH REQUIRED, PER-USER)
# =============================================================================

def _cart_summary(username: str) -> CartSummary:
    cart = CARTS.get(username, {})
    items: List[CartItemOut] = []
    total = 0.0

    for pid, qty in cart.items():
        product = _product_by_id(pid)
        if not product:
            continue
        unit_price = float(product.price)
        line_total = round(unit_price * qty, 2)
        total += line_total
        items.append(
            CartItemOut(
                product_id=pid,
                name=product.name,
                unit=product.unit,
                unit_price=unit_price,
                quantity=qty,
                line_total=line_total,
            )
        )

    total = round(total, 2)
    updated_at = CART_UPDATED_AT.get(username, datetime.utcnow().isoformat())
    return CartSummary(username=username, items=items, total=total, updated_at=updated_at)


@app.get("/api/cart", response_model=CartSummary)
async def get_cart(current_user: str = Depends(get_current_user)):
    if current_user not in CARTS:
        CARTS[current_user] = {}
    return _cart_summary(current_user)


@app.post("/api/cart/items", response_model=CartSummary)
async def add_cart_item(item: CartItemIn, current_user: str = Depends(get_current_user)):
    product = _product_by_id(item.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_available:
        raise HTTPException(status_code=400, detail=f"Product '{product.name}' is currently not available")

    CARTS.setdefault(current_user, {})
    CARTS[current_user][item.product_id] = CARTS[current_user].get(item.product_id, 0) + item.quantity
    CART_UPDATED_AT[current_user] = datetime.utcnow().isoformat()
    return _cart_summary(current_user)


@app.patch("/api/cart/items/{product_id}", response_model=CartSummary)
async def update_cart_item(product_id: int, quantity: int = Query(..., ge=1, le=999), current_user: str = Depends(get_current_user)):
    if current_user not in CARTS or product_id not in CARTS[current_user]:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    CARTS[current_user][product_id] = quantity
    CART_UPDATED_AT[current_user] = datetime.utcnow().isoformat()
    return _cart_summary(current_user)


@app.delete("/api/cart/items/{product_id}", response_model=CartSummary)
async def remove_cart_item(product_id: int, current_user: str = Depends(get_current_user)):
    if current_user not in CARTS or product_id not in CARTS[current_user]:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    del CARTS[current_user][product_id]
    CART_UPDATED_AT[current_user] = datetime.utcnow().isoformat()
    return _cart_summary(current_user)


# Backwards compatibility: keep old endpoint but require auth and route it to /api/cart/items
class CartItemLegacy(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=999)

class CartResponseLegacy(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    unit: str

@app.post("/api/cart/legacy", response_model=CartResponseLegacy)
async def add_to_cart_legacy(item: CartItemLegacy, current_user: str = Depends(get_current_user)):
    product = _product_by_id(item.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_available:
        raise HTTPException(status_code=400, detail=f"Product '{product.name}' is currently not available")

    total_price = round(product.price * item.quantity, 2)
    # also store it in the user's cart
    CARTS.setdefault(current_user, {})
    CARTS[current_user][item.product_id] = CARTS[current_user].get(item.product_id, 0) + item.quantity
    CART_UPDATED_AT[current_user] = datetime.utcnow().isoformat()

    return CartResponseLegacy(
        product_id=product.id,
        product_name=product.name,
        quantity=item.quantity,
        unit_price=product.price,
        total_price=total_price,
        unit=product.unit,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
