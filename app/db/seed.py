"""Create tables and insert sample data. Run: python -m app.db.seed"""
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal, init_db
from app.models import Customer, Order, OrderItem, OrderStatus, Product


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(Customer.id).limit(1)) is not None:
            print("Database already seeded, skipping.")
            return

        customers = [
            Customer(name="Alice Nguyen", email="alice@example.com"),
            Customer(name="Bob Tran", email="bob@example.com"),
        ]
        products = [
            Product(name="Keyboard", price=Decimal("49.90"), stock=50),
            Product(name="Mouse", price=Decimal("19.99"), stock=100),
            Product(name="Monitor", price=Decimal("199.00"), stock=20),
            Product(name="USB Cable", price=Decimal("4.50"), stock=0),
        ]
        db.add_all(customers + products)
        db.flush()

        def make_order(customer, status, lines):
            order = Order(customer_id=customer.id, status=status)
            for product, qty in lines:
                order.items.append(
                    OrderItem(product_id=product.id, quantity=qty, unit_price=product.price)
                )
                if status != OrderStatus.CANCELLED:
                    product.stock -= qty
            order.total = sum((i.unit_price * i.quantity for i in order.items), Decimal("0.00"))
            db.add(order)

        kb, mouse, monitor, _ = products
        make_order(customers[0], OrderStatus.PENDING, [(kb, 1), (mouse, 2)])
        make_order(customers[1], OrderStatus.PAID, [(monitor, 1)])
        make_order(customers[0], OrderStatus.CANCELLED, [(mouse, 3)])
        db.commit()
        print("Seeded 2 customers, 4 products, 3 orders.")


if __name__ == "__main__":
    seed()
    print("Tables ready.")
