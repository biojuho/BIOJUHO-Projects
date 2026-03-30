import random
import uuid
from datetime import UTC, datetime, timedelta

import models
from database import SessionLocal, initialize_database

initialize_database()


def seed_db():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(models.User).count() > 0:
            print("Database already seeded.")
            return

        print("Seeding database...")
        # 1. Create Farmers (Users)
        farmers = []
        for i in range(120):  # Simulate ~120 farms
            user = models.User(
                id=str(uuid.uuid4()),
                role="Farmer",
                name=f"Farm Operator {i}",
                organization=f"AgriGreen {i}",
                created_at=datetime.now(UTC) - timedelta(days=random.randint(10, 365)),
            )
            farmers.append(user)
            db.add(user)

        db.commit()

        # 2. Create Products
        products = []
        categories = ["Corn", "Wheat", "Soybeans", "Tomatoes", "Apples"]
        for i in range(500):
            owner = random.choice(farmers)
            harvested = random.choice([True, False])
            created_at = datetime.now(UTC) - timedelta(days=random.randint(1, 100))

            product = models.Product(
                id=str(uuid.uuid4()),
                name=f"Batch {i} - {random.choice(categories)}",
                description="High quality organic produce",
                category=random.choice(categories),
                origin="Farmville Region",
                harvest_date=created_at + timedelta(days=60) if harvested else None,
                requires_cold_chain=random.choice([True, False]),
                owner_id=owner.id,
                is_verified=True,
                qr_code=f"agri://verify/mock-{i}",
            )
            products.append(product)
            db.add(product)

        db.commit()

        # 3. Create Tracking Events
        statuses = ["Planted", "Harvested", "In Transit", "Delivered to Warehouse", "Quality Check Passed"]
        for i in range(1500):
            product = random.choice(products)
            event = models.TrackingEvent(
                id=str(uuid.uuid4()),
                product_id=product.id,
                timestamp=datetime.now(UTC) - timedelta(hours=random.randint(1, 720)),
                status=random.choice(statuses),
                location=f"Zone {random.choice(['A', 'B', 'C', 'North', 'South'])}",
                handler_id=random.choice(farmers).id,
            )
            db.add(event)

        db.commit()
        print("Database seeded successfully with Users, Products, and Events.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
