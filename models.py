from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    base_price = Column(Float, nullable=False, default=0.0)
    shipping_charge = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    stock = Column(Integer, nullable=False, default=0)

    # Relationships
    transactions = relationship("Transaction", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.base_price})>"


class IntentContract(Base):
    __tablename__ = "intent_contracts"

    id = Column(Integer, primary_key=True, index=True)
    raw_request = Column(Text, nullable=True)
    product_type = Column(String(100), nullable=True)
    purpose = Column(String(255), nullable=True)
    max_budget = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    payment_authorized = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    transactions = relationship("Transaction", back_populates="intent_contract")

    def __repr__(self):
        return f"<IntentContract(id={self.id}, product_type='{self.product_type}', max_budget={self.max_budget})>"


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id = Column(Integer, primary_key=True, index=True)
    max_transaction_amount = Column(Float, nullable=False)
    high_value_threshold = Column(Float, nullable=False)
    max_automated_retries = Column(Integer, nullable=False, default=3)
    duplicate_purchase_block = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    def __repr__(self):
        return f"<MerchantPolicy(id={self.id}, max_tx={self.max_transaction_amount}, high_val={self.high_value_threshold})>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    intent_contract_id = Column(Integer, ForeignKey("intent_contracts.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    product_price = Column(Float, nullable=False)
    shipping = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    final_amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")
    razorpay_order_id = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    intent_contract = relationship("IntentContract", back_populates="transactions")
    product = relationship("Product", back_populates="transactions")
    audit_logs = relationship("AuditLog", back_populates="transaction")

    def __repr__(self):
        return f"<Transaction(id={self.id}, final_amount={self.final_amount}, status='{self.status}')>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    agent = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    decision = Column(String(50), nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    transaction = relationship("Transaction", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, agent='{self.agent}', decision='{self.decision}')>"
