from datetime import datetime, timezone

from extensions import db


product_categories = db.Table(
    "product_categories",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
    db.Column("category_id", db.Integer, db.ForeignKey("categories.id"), primary_key=True),
)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Relationship to products 
    products = db.relationship(
        "Product",
        secondary=product_categories,
        back_populates="categories",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    
    categories = db.relationship(
        "Category",
        secondary=product_categories,
        back_populates="products",
        lazy="dynamic",
    )

   
    order_items = db.relationship("OrderItem", back_populates="product", lazy="dynamic")

    def __repr__(self):
        return f"<Product {self.name}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_email = db.Column(db.String(255), nullable=False, index=True)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(64), nullable=False, index=True)  # CREATED, PENDING, COMPLETE
    created_at = db.Column(db.DateTime, nullable=False, default = datetime.now());
    
    # Blockchain fields (optional, nullable)
    contract_address = db.Column(db.String(255), nullable=True)  # one contract per order when WITH_BLOCKCHAIN
    courier_address = db.Column(db.String(255), nullable=True)
    customer_address = db.Column(db.String(255), nullable=True)
    payment_complete = db.Column(db.Boolean, nullable=False, default=False)

    # Relationship to order items
    items = db.relationship("OrderItem", back_populates="order", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.id} - {self.status}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.Numeric(10, 2), nullable=False)  

    # Relationships
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    def __repr__(self):
        return f"<OrderItem order={self.order_id} product={self.product_id} qty={self.quantity}>"


class BlockchainState(db.Model):
    __tablename__ = "blockchain_state"

    id = db.Column(db.Integer, primary_key=True)
    contract_address = db.Column(db.String(255), nullable=False)

