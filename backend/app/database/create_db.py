from .db import Base, engine
from .models import Customer, Product, Order, Inventory


def create_database():
    Base.metadata.create_all(bind=engine)
    print("Database and tables created successfully!")


if __name__ == "__main__":
    create_database()
