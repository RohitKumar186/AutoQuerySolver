CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


INSERT INTO customers (name, phone) VALUES ('Rahul Sharma', '+91-9876543210'), ('Jane Doe', '+1-5551234567');


CREATE TABLE IF NOT EXISTS audit_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    worker       VARCHAR(20) NOT NULL,
    op           VARCHAR(10) NOT NULL,
    record_id    INT,
    original     JSON,
    fixed        JSON,
    issues       JSON,
    confidence   FLOAT,
    fix_valid    BOOLEAN,
    approved_by  VARCHAR(100),
    ts           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;