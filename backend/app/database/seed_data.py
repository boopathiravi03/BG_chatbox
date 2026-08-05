from datetime import date
from .db import SessionLocal
from .models import Customer, Product, Order, Inventory

db = SessionLocal()

if db.query(Customer).first():
    print("Sample data already exists. Skipping seed.")
    db.close()
    exit()

customers = [
    Customer(name="Arun", email="arun@gmail.com", city="Chennai"),
    Customer(name="Priya", email="priya@gmail.com", city="Coimbatore"),
    Customer(name="Rahul", email="rahul@gmail.com", city="Madurai"),
]

products = [
    Product(name="Laptop", category="Electronics", price=75000),
    Product(name="Phone", category="Electronics", price=30000),
    Product(name="Headphones", category="Accessories", price=2500),
]

db.add_all(customers)
db.add_all(products)
db.commit()

inventory = [
    Inventory(product_id=1, stock=20),
    Inventory(product_id=2, stock=35),
    Inventory(product_id=3, stock=50),
]

db.add_all(inventory)
db.commit()

orders = [
    Order(customer_id=1, product_id=1, quantity=1, order_date=date(2026, 8, 1)),
    Order(customer_id=2, product_id=2, quantity=2, order_date=date(2026, 8, 2)),
    Order(customer_id=3, product_id=3, quantity=3, order_date=date(2026, 8, 3)),
    Order(customer_id=1, product_id=2, quantity=1, order_date=date(2026, 8, 3)),
]

db.add_all(orders)
db.commit()

db.close()

print("Sample data inserted successfully!")
