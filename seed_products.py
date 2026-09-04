import logging
from database import SessionLocal, engine, Base
import models
from models import Product, MerchantPolicy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("payguard.seed")

# 15 realistic products (6 Laptops, 4 Smartphones, 5 Headphones)
PRODUCTS_DATA = [
    # --- 6 Laptops ---
    {
        "name": "Apple MacBook Pro 14 (M3)",
        "category": "Laptops",
        "description": "Apple M3 chip with 8-core CPU, 10-core GPU, 16GB Unified Memory, 512GB SSD, Liquid Retina XDR display.",
        "base_price": 169900.0,
        "shipping_charge": 0.0,
        "tax": 30582.0,
        "stock": 12,
    },
    {
        "name": "Dell XPS 15 9530",
        "category": "Laptops",
        "description": "Intel Core i7-13700H, 16GB DDR5, 1TB NVMe SSD, 15.6-inch OLED 3.5K Touchscreen, NVIDIA RTX 4060.",
        "base_price": 145000.0,
        "shipping_charge": 500.0,
        "tax": 26100.0,
        "stock": 8,
    },
    {
        "name": "Lenovo ThinkPad X1 Carbon Gen 11",
        "category": "Laptops",
        "description": "Intel Core i7-1365U vPro, 16GB LPDDR5, 512GB SSD, 14-inch WUXGA IPS anti-glare display, ultra-lightweight carbon fiber.",
        "base_price": 125000.0,
        "shipping_charge": 0.0,
        "tax": 22500.0,
        "stock": 15,
    },
    {
        "name": "ASUS ROG Zephyrus G14",
        "category": "Laptops",
        "description": "AMD Ryzen 9 7940HS, 16GB DDR5, 1TB SSD, 14-inch QHD+ 165Hz ROG Nebula Display, NVIDIA RTX 4070.",
        "base_price": 138000.0,
        "shipping_charge": 350.0,
        "tax": 24840.0,
        "stock": 10,
    },
    {
        "name": "HP Spectre x360 14",
        "category": "Laptops",
        "description": "Intel Core Ultra 7 155H, 16GB RAM, 1TB SSD, 14-inch 2.8K OLED Touch 2-in-1 convertible with tilt pen.",
        "base_price": 115000.0,
        "shipping_charge": 0.0,
        "tax": 20700.0,
        "stock": 14,
    },
    {
        "name": "Acer Swift Go 14",
        "category": "Laptops",
        "description": "Intel Core i5-13500H, 16GB LPDDR5, 512GB SSD, 14-inch 2.8K 90Hz OLED lightweight productivity laptop.",
        "base_price": 59990.0,
        "shipping_charge": 250.0,
        "tax": 10798.2,
        "stock": 20,
    },

    # --- 4 Smartphones ---
    {
        "name": "Apple iPhone 15 Pro",
        "category": "Smartphones",
        "description": "A17 Pro chip, Aerospace-grade titanium design, 128GB, Action button, 48MP main camera with 3x Telephoto.",
        "base_price": 124900.0,
        "shipping_charge": 0.0,
        "tax": 22482.0,
        "stock": 25,
    },
    {
        "name": "Samsung Galaxy S24 Ultra",
        "category": "Smartphones",
        "description": "Snapdragon 8 Gen 3, 12GB RAM, 256GB, Titanium frame, 200MP camera with Galaxy AI and integrated S-Pen.",
        "base_price": 129999.0,
        "shipping_charge": 0.0,
        "tax": 23399.82,
        "stock": 18,
    },
    {
        "name": "Google Pixel 8 Pro",
        "category": "Smartphones",
        "description": "Google Tensor G3, 12GB RAM, 128GB, Super Actua display, Pro triple camera system with Magic Editor & Audio Magic Eraser.",
        "base_price": 94999.0,
        "shipping_charge": 150.0,
        "tax": 17099.82,
        "stock": 12,
    },
    {
        "name": "OnePlus 12 5G",
        "category": "Smartphones",
        "description": "Snapdragon 8 Gen 3, 16GB RAM, 512GB, 5400mAh battery with 100W SUPERVOOC charging, 4th Gen Hasselblad Camera.",
        "base_price": 64999.0,
        "shipping_charge": 100.0,
        "tax": 11699.82,
        "stock": 30,
    },

    # --- 5 Headphones ---
    {
        "name": "Sony WH-1000XM5",
        "category": "Headphones",
        "description": "Industry-leading noise canceling wireless headphones with Auto NC Optimizer, 30hr battery life, and LDAC high-res audio.",
        "base_price": 29990.0,
        "shipping_charge": 0.0,
        "tax": 5398.2,
        "stock": 35,
    },
    {
        "name": "Bose QuietComfort Ultra",
        "category": "Headphones",
        "description": "World-class active noise cancellation with CustomTune technology, spatial audio, and ultra-comfortable plush earcups.",
        "base_price": 34900.0,
        "shipping_charge": 0.0,
        "tax": 6282.0,
        "stock": 22,
    },
    {
        "name": "Apple AirPods Max",
        "category": "Headphones",
        "description": "Apple-designed dynamic driver, active noise cancellation with Transparency mode, Personalized Spatial Audio with dynamic head tracking.",
        "base_price": 59900.0,
        "shipping_charge": 0.0,
        "tax": 10782.0,
        "stock": 16,
    },
    {
        "name": "Sennheiser Momentum 4 Wireless",
        "category": "Headphones",
        "description": "Audiophile-inspired 42mm transducer system, adaptive noise cancellation, and exceptional up to 60-hour battery life.",
        "base_price": 26990.0,
        "shipping_charge": 150.0,
        "tax": 4858.2,
        "stock": 20,
    },
    {
        "name": "Audio-Technica ATH-M50xBT2",
        "category": "Headphones",
        "description": "Proprietary 45mm large-aperture drivers, exceptional clarity throughout an extended frequency range, Bluetooth 5.0 wireless.",
        "base_price": 17490.0,
        "shipping_charge": 200.0,
        "tax": 3148.2,
        "stock": 40,
    },
]

DEFAULT_MERCHANT_POLICY = {
    "max_transaction_amount": 100000.0,
    "high_value_threshold": 50000.0,
    "max_automated_retries": 2,
    "duplicate_purchase_block": True,
}


def seed_database():
    """Seeds the PostgreSQL database with initial products catalog and merchant policy."""
    logger.info("Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed or update Merchant Policy
        policy = db.query(MerchantPolicy).first()
        if not policy:
            logger.info("Inserting default Merchant Policy...")
            policy = MerchantPolicy(**DEFAULT_MERCHANT_POLICY)
            db.add(policy)
            db.commit()
            logger.info("Default Merchant Policy inserted successfully.")
        else:
            logger.info(f"Merchant Policy already exists (ID: {policy.id}). Updating to default values...")
            for key, val in DEFAULT_MERCHANT_POLICY.items():
                setattr(policy, key, val)
            db.commit()

        # Seed Products
        inserted_count = 0
        updated_count = 0
        for item in PRODUCTS_DATA:
            existing = db.query(Product).filter(Product.name == item["name"]).first()
            if not existing:
                prod = Product(**item)
                db.add(prod)
                inserted_count += 1
            else:
                for key, val in item.items():
                    setattr(existing, key, val)
                updated_count += 1

        db.commit()
        logger.info(f"Products seeding complete: {inserted_count} inserted, {updated_count} updated.")

        # Verification summary
        all_products = db.query(Product).all()
        logger.info(f"Total products in PostgreSQL: {len(all_products)}")
        for p in all_products:
            logger.info(f"  [{p.id}] {p.name} ({p.category}) - Price: ₹{p.base_price:.2f}, Stock: {p.stock}")

        current_policy = db.query(MerchantPolicy).first()
        logger.info(
            f"Active Policy -> Max Tx: ₹{current_policy.max_transaction_amount:.2f}, "
            f"High Value Threshold: ₹{current_policy.high_value_threshold:.2f}, "
            f"Max Retries: {current_policy.max_automated_retries}, "
            f"Duplicate Block: {current_policy.duplicate_purchase_block}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
