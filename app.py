"""
Mini Market API - FastAPI REST API for Mini Market UI

SETUP INSTRUCTIONS
==================
1) (Optional) Create a virtual environment:
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate

2) Install dependencies:
   pip install -r requirements.txt

3) Set up environment variables (copy .env.example to .env):
   - DATABASE_URL: PostgreSQL connection string
   - JWT_SECRET_KEY: Secret key for JWT tokens
   - FRONTEND_ORIGIN: Frontend URL (default: http://localhost:5173)

4) Run the server:
   uvicorn app:app --reload --port 8000

Frontend integration (Vite):
- React dev server: http://localhost:5173
- CORS is configured to allow requests from FRONTEND_ORIGIN
- If you use a Vite proxy (recommended), the UI can call /api/... directly.

AUTH
====
This API implements JWT-based authentication with Postgres storage.
- Register: POST /api/auth/register
- Login:    POST /api/auth/login  -> returns JWT access_token
- Use:      Authorization: Bearer <access_token>

NOTE: All data is persisted in Postgres database.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import engine, get_db
from models import Base, User, Product as DBProduct, Offer as DBOffer, CartItem
from auth import hash_password, verify_password, create_access_token, get_current_user

# Load environment variables
load_dotenv()


# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="Mini Market API",
    description="REST API for Mini Market supermarket website",
    version="1.1.0",
)

# CORS configuration - allow frontend origin from environment variable
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# STARTUP: CREATE TABLES AND SEED DATA
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Create database tables and seed initial data on startup."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Seed initial data if tables are empty
    db = next(get_db())
    try:
        # Check if products exist
        product_count = db.query(DBProduct).count()
        if product_count == 0:
            # Seed products
            initial_products = [
                DBProduct(
                    name="Fresh Red Apples",
                    description="Crisp and juicy red apples, perfect for snacks and desserts",
                    price=2.49,
                    unit="kg",
                    category="fruits",
                    is_available=True,
                ),
                DBProduct(
                    name="Whole Milk 1L",
                    description="Rich and creamy whole milk, ideal for coffee and cereal",
                    price=1.39,
                    unit="bottle",
                    category="dairy",
                    is_available=True,
                ),
                DBProduct(
                    name="White Bread",
                    description="Freshly baked white bread, 500g loaf",
                    price=1.99,
                    unit="item",
                    category="bakery",
                    is_available=True,
                ),
                DBProduct(
                    name="Free Range Eggs",
                    description="12 large free-range eggs",
                    price=3.29,
                    unit="item",
                    category="dairy",
                    is_available=True,
                ),
                DBProduct(
                    name="Potato Chips",
                    description="Crispy salted potato chips, 150g bag",
                    price=0.99,
                    unit="item",
                    category="snacks",
                    is_available=True,
                ),
                DBProduct(
                    name="Orange Juice",
                    description="Fresh orange juice, 1L bottle",
                    price=2.99,
                    unit="bottle",
                    category="drinks",
                    is_available=True,
                ),
            ]
            db.add_all(initial_products)
            db.commit()
        
        # Check if offers exist
        offer_count = db.query(DBOffer).count()
        if offer_count == 0:
            # Seed offers
            initial_offers = [
                DBOffer(
                    title="Organic Bananas",
                    description="This week only — perfectly ripe and full of flavor.",
                    old_price=1.99,
                    new_price=1.29,
                    product_id=None,
                    is_active=True,
                ),
                DBOffer(
                    title="Olive Oil",
                    description="Premium extra virgin olive oil — limited stock.",
                    old_price=12.50,
                    new_price=9.99,
                    product_id=None,
                    is_active=True,
                ),
                DBOffer(
                    title="Breakfast Bundle",
                    description="Milk + eggs + bread combo discount.",
                    old_price=10.49,
                    new_price=7.99,
                    product_id=None,
                    is_active=True,
                ),
            ]
            db.add_all(initial_offers)
            db.commit()
    finally:
        db.close()


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
    access_token: str
    token_type: str = "bearer"
    username: str


class MeResponse(BaseModel):
    id: int
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


class CartItemSimple(BaseModel):
    """Simplified cart item for GET /api/cart response."""
    product_id: int
    name: str
    price: float
    quantity: int
    line_total: float


class CartResponse(BaseModel):
    """Cart response format matching UI expectations."""
    items: List[CartItemSimple]
    total: float


class CartSummary(BaseModel):
    """Full cart summary with username and timestamp."""
    username: str
    items: List[CartItemOut]
    total: float
    updated_at: str


# =============================================================================
# AUTH HELPERS (moved to auth.py)
# =============================================================================
# All authentication functions are now in auth.py


# =============================================================================
# PUBLIC ENDPOINTS (NO AUTH)
# =============================================================================

@app.get("/api/products", response_model=List[Product])
async def list_products(
    category: Optional[str] = Query(default=None, description="Filter products by category"),
    available_only: bool = Query(default=False, description="Return only products in stock"),
    db: Session = Depends(get_db),
):
    """Get list of products from database, optionally filtered by category and availability."""
    query = db.query(DBProduct)
    
    if category:
        # Case-insensitive exact match for category
        query = query.filter(DBProduct.category.ilike(category))
    
    if available_only:
        query = query.filter(DBProduct.is_available == True)
    
    db_products = query.all()
    
    # Convert SQLAlchemy models to Pydantic models
    return [
        Product(
            id=p.id,
            name=p.name,
            description=p.description,
            price=float(p.price),
            unit=p.unit,
            category=p.category,
            is_available=p.is_available,
        )
        for p in db_products
    ]


@app.get("/api/products/{product_id}", response_model=Product)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a single product by ID from database."""
    db_product = db.query(DBProduct).filter(DBProduct.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Convert SQLAlchemy model to Pydantic model
    return Product(
        id=db_product.id,
        name=db_product.name,
        description=db_product.description,
        price=float(db_product.price),
        unit=db_product.unit,
        category=db_product.category,
        is_available=db_product.is_available,
    )


@app.get("/api/offers", response_model=List[Offer])
async def list_offers(
    include_inactive: bool = Query(default=False, description="Include inactive offers"),
    db: Session = Depends(get_db),
):
    """Get list of offers from database. Returns active offers by default."""
    query = db.query(DBOffer)
    
    if not include_inactive:
        query = query.filter(DBOffer.is_active == True)
    
    db_offers = query.all()
    
    # Convert SQLAlchemy models to Pydantic models
    return [
        Offer(
            id=o.id,
            title=o.title,
            description=o.description,
            old_price=float(o.old_price),
            new_price=float(o.new_price),
            product_id=o.product_id,
            is_active=o.is_active,
        )
        for o in db_offers
    ]


@app.get("/api/offers/{offer_id}", response_model=Offer)
async def get_offer(offer_id: int, db: Session = Depends(get_db)):
    """Get a single offer by ID from database."""
    db_offer = db.query(DBOffer).filter(DBOffer.id == offer_id).first()
    if not db_offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Convert SQLAlchemy model to Pydantic model
    return Offer(
        id=db_offer.id,
        title=db_offer.title,
        description=db_offer.description,
        old_price=float(db_offer.old_price),
        new_price=float(db_offer.new_price),
        product_id=db_offer.product_id,
        is_active=db_offer.is_active,
    )


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
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    username = req.username.strip()
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username.ilike(username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user with hashed password
    user = User(
        username=username,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"status": "ok"}


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    username = req.username.strip()
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Create JWT token
    access_token = create_access_token(data={"sub": username})
    return AuthResponse(access_token=access_token, username=username)


@app.get("/api/auth/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(id=current_user.id, username=current_user.username)


@app.post("/api/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint (stateless JWT).
    Since JWT is stateless, logout is handled client-side by discarding the token.
    This endpoint exists for API consistency.
    """
    return {"status": "ok"}


# =============================================================================
# CART ENDPOINTS (AUTH REQUIRED, PER-USER)
# =============================================================================

def _get_cart_items(user: User, db: Session) -> tuple[List[CartItemSimple], float]:
    """Get cart items and total for current user."""
    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    items: List[CartItemSimple] = []
    total = 0.0

    for cart_item in cart_items:
        product = cart_item.product
        if not product:
            continue
        unit_price = float(product.price)
        line_total = round(unit_price * cart_item.quantity, 2)
        total += line_total
        items.append(
            CartItemSimple(
                product_id=product.id,
                name=product.name,
                price=unit_price,
                quantity=cart_item.quantity,
                line_total=line_total,
            )
        )

    total = round(total, 2)
    return items, total


def _cart_summary(user: User, db: Session) -> CartSummary:
    """Build full cart summary from database cart items."""
    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    items: List[CartItemOut] = []
    total = 0.0

    for cart_item in cart_items:
        product = cart_item.product
        if not product:
            continue
        unit_price = float(product.price)
        line_total = round(unit_price * cart_item.quantity, 2)
        total += line_total
        items.append(
            CartItemOut(
                product_id=product.id,
                name=product.name,
                unit=product.unit,
                unit_price=unit_price,
                quantity=cart_item.quantity,
                line_total=line_total,
            )
        )

    total = round(total, 2)
    updated_at = datetime.utcnow().isoformat()
    return CartSummary(username=user.username, items=items, total=total, updated_at=updated_at)


@app.get("/api/cart", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get cart items for current authenticated user."""
    items, total = _get_cart_items(current_user, db)
    return CartResponse(items=items, total=total)


@app.post("/api/cart/items", response_model=CartResponse)
async def add_cart_item(
    item: CartItemIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add or update item in cart (upsert).
    If item exists, increases quantity; otherwise creates new cart item.
    """
    product = db.query(DBProduct).filter(DBProduct.id == item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_available:
        raise HTTPException(status_code=400, detail=f"Product '{product.name}' is currently not available")

    # Check if cart item already exists (unique constraint on user_id, product_id)
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == item.product_id
    ).first()

    if cart_item:
        # Update quantity (upsert behavior: increase existing)
        cart_item.quantity += item.quantity
    else:
        # Create new cart item
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=item.product_id,
            quantity=item.quantity,
        )
        db.add(cart_item)
    
    db.commit()
    items, total = _get_cart_items(current_user, db)
    return CartResponse(items=items, total=total)


@app.patch("/api/cart/items/{product_id}", response_model=CartResponse)
async def update_cart_item(
    product_id: int,
    quantity: int = Query(..., ge=0, le=999),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update cart item quantity.
    If quantity <= 0, removes the item from cart.
    """
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    if quantity <= 0:
        # Remove item if quantity is 0 or negative
        db.delete(cart_item)
    else:
        # Update quantity
        cart_item.quantity = quantity
    
    db.commit()
    items, total = _get_cart_items(current_user, db)
    return CartResponse(items=items, total=total)


@app.delete("/api/cart/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove item from cart if it exists."""
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    db.delete(cart_item)
    db.commit()
    items, total = _get_cart_items(current_user, db)
    return CartResponse(items=items, total=total)


# =============================================================================
# BACKWARD COMPATIBILITY ENDPOINTS
# =============================================================================

@app.post("/api/cart")
async def add_to_cart_backward_compat(
    item: CartItemIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Backward compatibility endpoint for POST /api/cart.
    Treats it as alias for POST /api/cart/items (add item to cart).
    Prefer using /api/cart/items for new code.
    """
    # Reuse the add_cart_item logic
    return await add_cart_item(item, current_user, db)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
