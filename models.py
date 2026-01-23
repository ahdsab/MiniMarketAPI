"""
SQLAlchemy database models for Mini Market API.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash (includes salt)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Product(Base):
    """Product model representing items in the supermarket."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(50), nullable=False)  # e.g. "kg", "item", "bottle"
    category = Column(String(100), nullable=False)  # e.g. "fruits", "dairy", "bakery"
    is_available = Column(Boolean, default=True, nullable=False)

    # Relationships
    cart_items = relationship("CartItem", back_populates="product")
    offers = relationship("Offer", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}')>"


class Offer(Base):
    """Offer model representing discounts and special deals."""
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=False)
    old_price = Column(Numeric(10, 2), nullable=False)
    new_price = Column(Numeric(10, 2), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="offers")

    def __repr__(self):
        return f"<Offer(id={self.id}, title='{self.title}')>"


class CartItem(Base):
    """Cart item model linking users to products with quantities."""
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)

    # Unique constraint: one cart item per user-product combination
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product"),
        Index("ix_cart_items_user_id", "user_id"),
    )

    # Relationships
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")

    def __repr__(self):
        return f"<CartItem(id={self.id}, user_id={self.user_id}, product_id={self.product_id}, quantity={self.quantity})>"
