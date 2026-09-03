PRAGMA foreign_keys = ON;

----------------------------------------------------
-- CUSTOMERS
----------------------------------------------------
CREATE TABLE Customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    date_of_birth DATE,
    gender TEXT CHECK(gender IN ('Male','Female','Other')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

----------------------------------------------------
-- ADDRESSES
----------------------------------------------------
CREATE TABLE Addresses (
    address_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT 'India',
    pincode TEXT,
    FOREIGN KEY(customer_id) REFERENCES Customers(customer_id)
);

----------------------------------------------------
-- CATEGORIES
----------------------------------------------------
CREATE TABLE Categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT UNIQUE NOT NULL,
    description TEXT
);

----------------------------------------------------
-- PRODUCTS
----------------------------------------------------
CREATE TABLE Products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    brand TEXT,
    description TEXT,
    price REAL NOT NULL CHECK(price >= 0),
    stock INTEGER DEFAULT 0 CHECK(stock >= 0),
    rating REAL DEFAULT 0 CHECK(rating BETWEEN 0 AND 5),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(category_id) REFERENCES Categories(category_id)
);

----------------------------------------------------
-- ORDERS
----------------------------------------------------
CREATE TABLE Orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_date DATE,
    total_amount REAL DEFAULT 0 CHECK(total_amount >= 0),
    order_status TEXT CHECK(
        order_status IN (
            'Pending',
            'Processing',
            'Shipped',
            'Delivered',
            'Cancelled',
            'Returned'
        )
    ),
    FOREIGN KEY(customer_id) REFERENCES Customers(customer_id)
);

----------------------------------------------------
-- ORDER ITEMS
----------------------------------------------------
CREATE TABLE Order_Items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    FOREIGN KEY(order_id) REFERENCES Orders(order_id),
    FOREIGN KEY(product_id) REFERENCES Products(product_id)
);

----------------------------------------------------
-- PAYMENTS
----------------------------------------------------
CREATE TABLE Payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    payment_method TEXT CHECK(
        payment_method IN (
            'UPI',
            'Credit Card',
            'Debit Card',
            'Net Banking',
            'Cash on Delivery'
        )
    ),
    payment_status TEXT CHECK(
        payment_status IN (
            'Success',
            'Pending',
            'Failed',
            'Refunded'
        )
    ),
    payment_date TIMESTAMP,
    transaction_id TEXT UNIQUE,
    FOREIGN KEY(order_id) REFERENCES Orders(order_id)
);

----------------------------------------------------
-- SHIPMENTS
----------------------------------------------------
CREATE TABLE Shipments (
    shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    courier_name TEXT,
    tracking_number TEXT UNIQUE,
    shipped_date DATE,
    expected_delivery DATE,
    delivered_date DATE,
    shipment_status TEXT CHECK(
        shipment_status IN (
            'Pending',
            'Shipped',
            'Out for Delivery',
            'Delivered'
        )
    ),
    FOREIGN KEY(order_id) REFERENCES Orders(order_id)
);

----------------------------------------------------
-- REVIEWS
----------------------------------------------------
CREATE TABLE Reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    review_text TEXT,
    review_date DATE,
    FOREIGN KEY(customer_id) REFERENCES Customers(customer_id),
    FOREIGN KEY(product_id) REFERENCES Products(product_id)
);

----------------------------------------------------
-- REFUNDS
----------------------------------------------------
CREATE TABLE Refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    refund_amount REAL NOT NULL CHECK(refund_amount >= 0),
    refund_reason TEXT,
    refund_status TEXT CHECK(
        refund_status IN (
            'Requested',
            'Approved',
            'Rejected',
            'Processed'
        )
    ),
    refund_date DATE,
    FOREIGN KEY(order_id) REFERENCES Orders(order_id)
);