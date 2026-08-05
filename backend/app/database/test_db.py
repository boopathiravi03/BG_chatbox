from .db import SessionLocal
from .models import Customer, Product, Order

db = SessionLocal()

print("\nCustomers")
for c in db.query(Customer).all():
    print(c.customer_id, c.name, c.city)

print("\nProducts")
for p in db.query(Product).all():
    print(p.product_id, p.name, p.price)

print("\nOrders")
for o in db.query(Order).all():
    print(o.order_id, o.customer_id, o.product_id, o.quantity)

db.close()
