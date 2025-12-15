"""
Mini Market API - FastAPI REST API for Mini Market UI

SETUP INSTRUCTIONS:
==================

1. Create a virtual environment (optional but recommended):
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

2. Install dependencies:
   pip install fastapi uvicorn[standard] email-validator

3. Run the server:
   uvicorn main:app --reload

   The API will be available at: http://localhost:8000
   API documentation (Swagger UI): http://localhost:8000/docs
   Alternative docs (ReDoc): http://localhost:8000/redoc

4. For React/Vite integration:
   - React app should run on: http://localhost:5173
   - CORS is configured to allow requests from http://localhost:5173
   - Example fetch URLs:
     * GET http://localhost:8000/api/products
     * GET http://localhost:8000/api/products?category=fruits&available_only=true
     * GET http://localhost:8000/api/products/1
     * GET http://localhost:8000/api/offers
     * GET http://localhost:8000/api/offers/1
     * POST http://localhost:8000/api/contact
     * POST http://localhost:8000/api/cart

ARCHITECTURE:
=============
- Uses in-memory storage (lists/dicts) for simplicity
- Easy to refactor to use a real database later
- All data models use Pydantic for validation
- CORS enabled for React frontend integration
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Initialize FastAPI app
app = FastAPI(
    title="Mini Market API",
    description="REST API for Mini Market supermarket website",
    version="1.0.0"
)

# Configure CORS for React frontend
# This allows the React app running on localhost:5173 to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default port
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class Product(BaseModel):
    """Product model representing items in the supermarket."""
    id: int
    name: str
    description: str
    price: float
    unit: str  # e.g. "kg", "item", "bottle"
    category: str  # e.g. "fruits", "dairy", "bakery"
    is_available: bool

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Fresh Apples",
                "description": "Crisp and juicy red apples",
                "price": 2.99,
                "unit": "kg",
                "category": "fruits",
                "is_available": True
            }
        }


class Offer(BaseModel):
    """Offer model representing discounts and special deals."""
    id: int
    title: str
    description: str
    old_price: float
    new_price: float
    product_id: Optional[int] = None  # If offer is tied to a specific product
    is_active: bool

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "title": "Summer Sale",
                "description": "20% off on all fruits",
                "old_price": 2.99,
                "new_price": 2.39,
                "product_id": 1,
                "is_active": True
            }
        }


class ContactMessage(BaseModel):
    """Contact form message model."""
    name: str
    email: EmailStr
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "message": "I love your store!"
            }
        }


class CartItem(BaseModel):
    """Cart item request model."""
    product_id: int
    quantity: int


class CartResponse(BaseModel):
    """Cart response model."""
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    unit: str


# ============================================================================
# IN-MEMORY DATABASE (Sample Data)
# ============================================================================

# Sample products matching common supermarket items
products_db: List[Product] = [
    Product(
        id=1,
        name="Fresh Apples",
        description="Crisp and juicy red apples, locally sourced",
        price=2.99,
        unit="kg",
        category="fruits",
        is_available=True
    ),
    Product(
        id=2,
        name="Whole Milk",
        description="Fresh whole milk, 1 liter bottle",
        price=3.49,
        unit="bottle",
        category="dairy",
        is_available=True
    ),
    Product(
        id=3,
        name="White Bread",
        description="Freshly baked white bread, 500g loaf",
        price=1.99,
        unit="item",
        category="bakery",
        is_available=True
    ),
    Product(
        id=4,
        name="Free Range Eggs",
        description="12 large free-range eggs",
        price=4.99,
        unit="item",
        category="dairy",
        is_available=True
    ),
    Product(
        id=5,
        name="Potato Chips",
        description="Crunchy salted potato chips, 200g bag",
        price=2.49,
        unit="item",
        category="snacks",
        is_available=True
    ),
    Product(
        id=6,
        name="Orange Juice",
        description="100% pure orange juice, 1 liter carton",
        price=3.99,
        unit="bottle",
        category="drinks",
        is_available=True
    ),
    Product(
        id=7,
        name="Bananas",
        description="Sweet yellow bananas, organic",
        price=1.99,
        unit="kg",
        category="fruits",
        is_available=True
    ),
    Product(
        id=8,
        name="Extra Virgin Olive Oil",
        description="Premium olive oil, 500ml bottle",
        price=8.99,
        unit="bottle",
        category="pantry",
        is_available=True
    ),
    Product(
        id=9,
        name="Chocolate Cookies",
        description="Homemade chocolate chip cookies, 300g pack",
        price=4.49,
        unit="item",
        category="bakery",
        is_available=False  # Out of stock
    ),
    Product(
        id=10,
        name="Sparkling Water",
        description="Natural sparkling mineral water, 750ml",
        price=1.29,
        unit="bottle",
        category="drinks",
        is_available=True
    ),
]

# Sample offers/discounts
offers_db: List[Offer] = [
    Offer(
        id=1,
        title="Fruits Special",
        description="20% off on all fresh fruits this week",
        old_price=2.99,
        new_price=2.39,
        product_id=1,  # Tied to apples
        is_active=True
    ),
    Offer(
        id=2,
        title="Dairy Discount",
        description="Buy 2 get 1 free on dairy products",
        old_price=3.49,
        new_price=2.33,
        product_id=2,  # Tied to milk
        is_active=True
    ),
    Offer(
        id=3,
        title="Bakery Sale",
        description="15% off on all bakery items",
        old_price=1.99,
        new_price=1.69,
        product_id=3,  # Tied to bread
        is_active=True
    ),
    Offer(
        id=4,
        title="Summer Drinks",
        description="Special price on refreshing drinks",
        old_price=3.99,
        new_price=2.99,
        product_id=6,  # Tied to orange juice
        is_active=True
    ),
    Offer(
        id=5,
        title="Expired Offer",
        description="This offer is no longer active",
        old_price=5.99,
        new_price=4.99,
        product_id=None,  # General offer
        is_active=False
    ),
]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to Mini Market API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "products": "/api/products",
            "offers": "/api/offers",
            "contact": "/api/contact (POST)",
            "cart": "/api/cart (POST)"
        }
    }


@app.get("/api/products", response_model=List[Product])
async def get_products(
    category: Optional[str] = Query(None, description="Filter by product category"),
    available_only: bool = Query(False, description="Only return available products")
):
    """
    Get all products with optional filtering.
    
    Query Parameters:
    - category: Filter products by category (e.g., "fruits", "dairy", "bakery")
    - available_only: If True, only return products where is_available is True
    
    Returns:
    - List of Product objects
    """
    filtered_products = products_db.copy()
    
    # Filter by category if provided
    if category:
        filtered_products = [p for p in filtered_products if p.category.lower() == category.lower()]
    
    # Filter by availability if requested
    if available_only:
        filtered_products = [p for p in filtered_products if p.is_available]
    
    return filtered_products


@app.get("/api/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    """
    Get a single product by ID.
    
    Parameters:
    - product_id: The ID of the product to retrieve
    
    Returns:
    - Product object
    
    Raises:
    - 404 if product not found
    """
    product = next((p for p in products_db if p.id == product_id), None)
    
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return product


@app.get("/api/offers", response_model=List[Offer])
async def get_offers(
    include_inactive: bool = Query(False, description="Include inactive offers")
):
    """
    Get all offers with optional filtering.
    
    Query Parameters:
    - include_inactive: If True, include inactive offers in the response
    
    Returns:
    - List of Offer objects (only active by default)
    """
    if include_inactive:
        return offers_db
    
    return [offer for offer in offers_db if offer.is_active]


@app.get("/api/offers/{offer_id}", response_model=Offer)
async def get_offer(offer_id: int):
    """
    Get a single offer by ID.
    
    Parameters:
    - offer_id: The ID of the offer to retrieve
    
    Returns:
    - Offer object
    
    Raises:
    - 404 if offer not found
    """
    offer = next((o for o in offers_db if o.id == offer_id), None)
    
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    return offer


@app.post("/api/contact")
async def submit_contact(message: ContactMessage):
    """
    Submit a contact form message.
    
    This endpoint accepts contact form submissions, validates the data,
    and logs it to the console (simulating email sending or database storage).
    
    Request Body:
    - name: Sender's name (required)
    - email: Valid email address (required)
    - message: Message content (required)
    
    Returns:
    - Success response with status message
    """
    # Log the message to console (simulate saving/sending)
    print(f"\n{'='*60}")
    print(f"NEW CONTACT MESSAGE RECEIVED")
    print(f"{'='*60}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Name: {message.name}")
    print(f"Email: {message.email}")
    print(f"Message: {message.message}")
    print(f"{'='*60}\n")
    
    # In a real application, you would:
    # - Save to database
    # - Send email notification
    # - Add to queue for processing
    
    return {
        "status": "ok",
        "message": "Thank you for contacting Mini Market."
    }


@app.post("/api/cart", response_model=CartResponse)
async def add_to_cart(item: CartItem):
    """
    Add an item to the cart and calculate total price.
    
    This endpoint simulates adding a product to the cart and returns
    a summary with the total price for that item.
    
    Request Body:
    - product_id: ID of the product to add
    - quantity: Quantity of the product
    
    Returns:
    - CartResponse with product details and calculated total
    
    Raises:
    - 404 if product not found
    - 400 if quantity is invalid
    """
    # Validate quantity
    if item.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0"
        )
    
    # Find the product
    product = next((p for p in products_db if p.id == item.product_id), None)
    
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check availability
    if not product.is_available:
        raise HTTPException(
            status_code=400,
            detail=f"Product '{product.name}' is currently not available"
        )
    
    # Calculate total price
    total_price = product.price * item.quantity
    
    return CartResponse(
        product_id=product.id,
        product_name=product.name,
        quantity=item.quantity,
        unit_price=product.price,
        total_price=round(total_price, 2),
        unit=product.unit
    )


# ============================================================================
# RUN THE APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

