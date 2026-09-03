import sqlite3
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

# Initialize Faker with Indian locale for realistic data
fake = Faker('en_IN')

# ============================================================
# CONNECTION
# ============================================================
conn = sqlite3.connect('ecommerce.db')
cursor = conn.cursor()

# ============================================================
# CONFIGURATION
# ============================================================
NUM_CUSTOMERS = 5000
NUM_PRODUCTS = 1000
NUM_ORDERS = 15000
NUM_ORDER_ITEMS = 40000
NUM_REVIEWS = 8000
REFUND_PERCENTAGE = 0.08  # 8% of orders get refunds

# ============================================================
# DROP TABLES (clean slate)
# ============================================================
cursor.executescript('''
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS addresses;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS categories;
''')

# ============================================================
# CREATE TABLES
# ============================================================
cursor.executescript('''
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    date_of_birth TEXT,
    gender TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE addresses (
    address_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    country TEXT NOT NULL,
    pincode TEXT,
    is_default INTEGER DEFAULT 1,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    brand TEXT,
    description TEXT,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    delivery_date TEXT,
    total_amount REAL NOT NULL,
    status TEXT DEFAULT 'Pending',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    payment_status TEXT DEFAULT 'Pending',
    payment_date TEXT,
    transaction_id TEXT UNIQUE,
    amount REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE TABLE shipments (
    shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    courier TEXT,
    tracking_number TEXT UNIQUE,
    status TEXT DEFAULT 'Pending',
    shipped_date TEXT,
    delivered_date TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE TABLE reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    review_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    refund_amount REAL NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'Pending',
    refund_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
''')

# ============================================================
# STATIC DATA
# ============================================================
states = [
    "Karnataka", "Maharashtra", "Tamil Nadu", "Kerala", "Delhi",
    "Telangana", "Gujarat", "Rajasthan", "Punjab", "West Bengal",
    "Uttar Pradesh", "Bihar", "Odisha", "Madhya Pradesh", "Haryana"
]

cities = [
    "Bengaluru", "Mysuru", "Mumbai", "Pune", "Chennai",
    "Hyderabad", "Ahmedabad", "Jaipur", "Kolkata", "Delhi",
    "Lucknow", "Patna", "Bhubaneswar", "Indore", "Chandigarh"
]

payment_methods = [
    "UPI", "Credit Card", "Debit Card", "Net Banking", "Cash on Delivery", "Wallet"
]

payment_statuses = ["Success", "Pending", "Failed", "Refunded"]

order_statuses = [
    "Pending", "Processing", "Shipped", "Delivered", "Cancelled", "Returned"
]

shipment_statuses = [
    "Pending", "Shipped", "Out for Delivery", "Delivered"
]

couriers = [
    "Blue Dart", "Delhivery", "DTDC", "India Post", "FedEx", "Ekart", "Amazon Logistics"
]

brands = [
    "Apple", "Samsung", "Sony", "Boat", "HP", "Dell", "Nike", "Adidas",
    "Puma", "Lenovo", "Asus", "OnePlus", "Xiaomi", "Realme", "Vivo", "Oppo",
    "LG", "Philips", "Panasonic", "Bose", "JBL", "Skullcandy", "Sennheiser",
    "Reebok", "Under Armour", "Puma", "Fossil", "Titan", "Casio", "Rolex"
]

# ============================================================
# 1. CATEGORIES
# ============================================================
categories = [
    ("Mobiles", "Smartphones and accessories"),
    ("Laptops", "Computers and accessories"),
    ("Tablets", "Tablets and e-readers"),
    ("Headphones", "Audio and headphones"),
    ("Speakers", "Bluetooth and home speakers"),
    ("Cameras", "Digital cameras and lenses"),
    ("Televisions", "LED and smart TVs"),
    ("Watches", "Smartwatches and traditional watches"),
    ("Footwear", "Shoes and sneakers"),
    ("Clothing", "Apparel and fashion"),
    ("Bags", "Backpacks and handbags"),
    ("Furniture", "Home and office furniture"),
    ("Kitchen", "Kitchen appliances"),
    ("Beauty", "Cosmetics and personal care"),
    ("Fitness", "Gym and fitness equipment"),
    ("Gaming", "Gaming consoles and accessories"),
    ("Books", "Books and stationery"),
    ("Groceries", "Daily essentials"),
    ("Toys", "Kids toys and games"),
    ("Automotive", "Car accessories"),
    ("Tools", "Hardware and tools"),
    ("Garden", "Garden and outdoor"),
    ("Jewelry", "Fashion jewelry"),
    ("Electronics", "General electronics"),
    ("Sports", "Sports equipment")
]

cursor.executemany(
    "INSERT INTO categories (category_name, description) VALUES (?, ?)",
    categories
)
print(f"✅ Inserted {len(categories)} categories")

# ============================================================
# 2. CUSTOMERS
# ============================================================
print("Generating customers...")
customers = []
for _ in range(NUM_CUSTOMERS):
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = f"{first_name.lower()}.{last_name.lower()}.{random.randint(100,999)}@example.com"
    phone = f"+91{random.randint(6000000000, 9999999999)}"
    dob = fake.date_of_birth(minimum_age=18, maximum_age=65)
    gender = random.choice(["Male", "Female", "Other"])
    customers.append((first_name, last_name, email, phone, dob, gender))

cursor.executemany(
    "INSERT INTO customers (first_name, last_name, email, phone, date_of_birth, gender) VALUES (?,?,?,?,?,?)",
    customers
)
print(f"✅ Inserted {NUM_CUSTOMERS} customers")

# ============================================================
# 3. ADDRESSES
# ============================================================
print("Generating addresses...")
addresses = []
for customer_id in range(1, NUM_CUSTOMERS + 1):
    num_addresses = random.randint(1, 3)
    for i in range(num_addresses):
        is_default = 1 if i == 0 else 0
        addresses.append((
            customer_id,
            fake.street_address(),
            fake.building_number() if random.random() > 0.5 else None,
            random.choice(cities),
            random.choice(states),
            "India",
            fake.postcode(),
            is_default
        ))

cursor.executemany(
    "INSERT INTO addresses (customer_id, address_line1, address_line2, city, state, country, pincode, is_default) VALUES (?,?,?,?,?,?,?,?)",
    addresses
)
print(f"✅ Inserted {len(addresses)} addresses")

# ============================================================
# 4. PRODUCTS
# ============================================================
print("Generating products...")
products = []
product_name_templates = [
    "Premium {brand} {category} {model}",
    "{brand} {category} Pro {model}",
    "{brand} {category} Lite {model}",
    "Smart {brand} {category} {model}",
    "{brand} {category} X {model}"
]

for product_id in range(1, NUM_PRODUCTS + 1):
    category_id = random.randint(1, len(categories))
    brand = random.choice(brands)
    category_name = categories[category_id - 1][0]
    model = random.randint(100, 999)
    template = random.choice(product_name_templates)
    product_name = template.format(brand=brand, category=category_name, model=model)

    # Realistic pricing: base price depends on category
    if category_id in [1, 2, 6, 7]:  # Electronics
        price = random.randint(5000, 150000)
    elif category_id in [4, 5]:  # Audio
        price = random.randint(500, 25000)
    elif category_id in [9, 10, 23]:  # Fashion
        price = random.randint(500, 15000)
    else:
        price = random.randint(200, 50000)

    price = round(price, 2)
    stock = random.randint(0, 500)
    rating = round(random.uniform(2.5, 5.0), 1)
    is_active = 1 if random.random() > 0.1 else 0

    products.append((
        category_id, product_name, brand,
        fake.sentence(nb_words=10),
        price, stock, rating, is_active
    ))

cursor.executemany(
    "INSERT INTO products (category_id, product_name, brand, description, price, stock, rating, is_active) VALUES (?,?,?,?,?,?,?,?)",
    products
)
print(f"✅ Inserted {NUM_PRODUCTS} products")

# ============================================================
# 5. ORDERS
# ============================================================
print("Generating orders...")
orders = []
start_date = datetime(2024, 1, 1)
end_date = datetime(2025, 6, 30)
date_range = (end_date - start_date).days

for _ in range(NUM_ORDERS):
    customer_id = random.randint(1, NUM_CUSTOMERS)
    order_date = start_date + timedelta(days=random.randint(0, date_range))
    status = random.choice(order_statuses)
    # Delivery date: between 2-15 days after order
    if status in ["Shipped", "Delivered", "Returned"]:
        delivery_days = random.randint(2, 15)
        delivery_date = order_date + timedelta(days=delivery_days)
    else:
        delivery_date = None
    # Total amount will be updated after order items are generated
    orders.append((customer_id, order_date.isoformat(), delivery_date.isoformat() if delivery_date else None, 0, status))

cursor.executemany(
    "INSERT INTO orders (customer_id, order_date, delivery_date, total_amount, status) VALUES (?,?,?,?,?)",
    orders
)
print(f"✅ Inserted {NUM_ORDERS} orders")

# ============================================================
# 6. ORDER ITEMS
# ============================================================
print("Generating order items...")
order_items = []
order_totals = {}

for order_id in range(1, NUM_ORDERS + 1):
    num_items = random.randint(1, 5)
    total = 0
    # Get random products (avoid duplicates within same order)
    product_ids = random.sample(range(1, NUM_PRODUCTS + 1), min(num_items, NUM_PRODUCTS))
    for product_id in product_ids:
        quantity = random.randint(1, 5)
        # Get price from products table
        cursor.execute("SELECT price FROM products WHERE product_id=?", (product_id,))
        price = cursor.fetchone()[0]
        order_items.append((order_id, product_id, quantity, price))
        total += quantity * price

    order_totals[order_id] = round(total, 2)

cursor.executemany(
    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
    order_items
)
print(f"✅ Inserted {len(order_items)} order items")

# Update order totals
for order_id, total in order_totals.items():
    cursor.execute("UPDATE orders SET total_amount=? WHERE order_id=?", (total, order_id))

# ============================================================
# 7. PAYMENTS
# ============================================================
print("Generating payments...")
payments = []
for order_id in range(1, NUM_ORDERS + 1):
    method = random.choice(payment_methods)
    status = random.choices(payment_statuses, weights=[0.7, 0.1, 0.1, 0.1])[0]
    payment_date = None
    if status != "Pending":
        # Payment date is within 2 days of order
        cursor.execute("SELECT order_date FROM orders WHERE order_id=?", (order_id,))
        order_date = cursor.fetchone()[0]
        if order_date:
            date_obj = datetime.fromisoformat(order_date)
            payment_date = date_obj + timedelta(days=random.randint(1, 5))
            payment_date = payment_date.isoformat()
    transaction_id = str(uuid.uuid4())
    amount = order_totals[order_id]
    payments.append((order_id, method, status, payment_date, transaction_id, amount))

cursor.executemany(
    "INSERT INTO payments (order_id, payment_method, payment_status, payment_date, transaction_id, amount) VALUES (?,?,?,?,?,?)",
    payments
)
print(f"✅ Inserted {len(payments)} payments")

# ============================================================
# 8. SHIPMENTS
# ============================================================
print("Generating shipments...")
shipments = []
for order_id in range(1, NUM_ORDERS + 1):
    courier = random.choice(couriers)
    tracking = "TRK" + str(uuid.uuid4())[:12].upper()
    status = random.choices(shipment_statuses, weights=[0.1, 0.2, 0.3, 0.4])[0]
    shipped_date = None
    delivered_date = None

    cursor.execute("SELECT order_date FROM orders WHERE order_id=?", (order_id,))
    order_date = cursor.fetchone()[0]
    if order_date:
        date_obj = datetime.fromisoformat(order_date)
        if status in ["Shipped", "Out for Delivery", "Delivered"]:
            shipped_date = date_obj + timedelta(days=random.randint(1, 5))
            shipped_date = shipped_date.isoformat()
        if status == "Delivered":
            del_date = datetime.fromisoformat(shipped_date) + timedelta(days=random.randint(1, 7))
            delivered_date = del_date.isoformat()

    shipments.append((order_id, courier, tracking, status, shipped_date, delivered_date))

cursor.executemany(
    "INSERT INTO shipments (order_id, courier, tracking_number, status, shipped_date, delivered_date) VALUES (?,?,?,?,?,?)",
    shipments
)
print(f"✅ Inserted {len(shipments)} shipments")

# ============================================================
# 9. REVIEWS
# ============================================================
print("Generating reviews...")
reviews = []
review_texts = [
    "Great product!", "Excellent quality.", "Not worth the money.",
    "Average product.", "Highly recommended.", "Good value for money.",
    "Poor quality.", "Amazing! Will buy again.", "Disappointed.",
    "Works as expected.", "Best purchase ever!", "Could be better.",
    "Fantastic!", "Overpriced.", "Good but not great.",
    "Love it!", "Horrible experience.", "Worth every penny.",
    "Decent product.", "Outstanding quality.", "Never buy again.",
    "Very satisfied.", "Below expectations.", "Perfect!",
    "Not what I expected.", "Great customer service.", "Waste of money."
]

# Generate reviews for random product-customer pairs
reviewed_pairs = set()
for _ in range(NUM_REVIEWS):
    product_id = random.randint(1, NUM_PRODUCTS)
    customer_id = random.randint(1, NUM_CUSTOMERS)
    pair_key = f"{customer_id}_{product_id}"
    if pair_key in reviewed_pairs:
        continue
    reviewed_pairs.add(pair_key)
    rating = random.randint(1, 5)
    review_text = random.choice(review_texts)
    # Review date: random date in last 6 months
    days_ago = random.randint(1, 180)
    review_date = datetime.now() - timedelta(days=days_ago)
    reviews.append((customer_id, product_id, rating, review_text, review_date.isoformat()))

cursor.executemany(
    "INSERT INTO reviews (customer_id, product_id, rating, review_text, review_date) VALUES (?,?,?,?,?)",
    reviews
)
print(f"✅ Inserted {len(reviews)} reviews")

# Update product ratings based on reviews
cursor.execute('''
UPDATE products
SET rating = (
    SELECT COALESCE(AVG(rating), 0)
    FROM reviews
    WHERE reviews.product_id = products.product_id
)
WHERE product_id IN (SELECT DISTINCT product_id FROM reviews)
''')
print("✅ Updated product ratings")

# ============================================================
# 10. REFUNDS
# ============================================================
print("Generating refunds...")
refunds = []
refund_reasons = [
    "Damaged", "Wrong Product", "Late Delivery",
    "Not Satisfied", "Quality Issue", "Wrong Size",
    "Defective Item", "Order Cancelled"
]

# Get delivered orders that can be refunded
cursor.execute(
    "SELECT order_id, customer_id, total_amount FROM orders WHERE status IN ('Delivered', 'Cancelled')"
)
eligible_orders = cursor.fetchall()

# Select ~8% of eligible orders for refunds
num_refunds = int(len(eligible_orders) * REFUND_PERCENTAGE)
selected_orders = random.sample(eligible_orders, min(num_refunds, len(eligible_orders)))

for order_id, customer_id, total_amount in selected_orders:
    refund_amount = round(total_amount * random.uniform(0.3, 1.0), 2)
    reason = random.choice(refund_reasons)
    status = random.choices(["Pending", "Approved", "Rejected", "Processed"], weights=[0.2, 0.4, 0.1, 0.3])[0]
    refund_date = datetime.now() - timedelta(days=random.randint(1, 90))
    refunds.append((order_id, refund_amount, reason, status, refund_date.isoformat()))

cursor.executemany(
    "INSERT INTO refunds (order_id, refund_amount, reason, status, refund_date) VALUES (?,?,?,?,?)",
    refunds
)
print(f"✅ Inserted {len(refunds)} refunds")

# ============================================================
# FINALIZE
# ============================================================
conn.commit()
conn.close()

print("\n" + "="*50)
print("✅ DATABASE GENERATED SUCCESSFULLY!")
print("="*50)
print(f"📊 Tables Created:")
print(f"   Categories: {len(categories)}")
print(f"   Customers: {NUM_CUSTOMERS}")
print(f"   Addresses: {len(addresses)}")
print(f"   Products: {NUM_PRODUCTS}")
print(f"   Orders: {NUM_ORDERS}")
print(f"   Order Items: {len(order_items)}")
print(f"   Payments: {len(payments)}")
print(f"   Shipments: {len(shipments)}")
print(f"   Reviews: {len(reviews)}")
print(f"   Refunds: {len(refunds)}")
print("="*50)
print("📁 Database file: ecommerce.db")