-- S Provisions Reconciliation Database Schema
-- Supports backward/forward lookups with 60+ day payment lags

CREATE DATABASE IF NOT EXISTS sprovisions_reconcile;
USE sprovisions_reconcile;

-- Payment Remittances (received from clients like Cox Automotive)
CREATE TABLE IF NOT EXISTS payment_remittances (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payment_date DATE NOT NULL,
    payment_reference VARCHAR(50),
    paper_document_number VARCHAR(50),
    payment_amount DECIMAL(10, 2) NOT NULL,
    source_file VARCHAR(255),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_payment_date (payment_date),
    INDEX idx_payment_ref (payment_reference)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Invoice details from payment remittances
CREATE TABLE IF NOT EXISTS payment_invoices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    remittance_id INT NOT NULL,
    invoice_number VARCHAR(50),
    invoice_date VARCHAR(50),
    invoice_amount DECIMAL(10, 2),
    discount DECIMAL(10, 2),
    amount_paid DECIMAL(10, 2),
    vin VARCHAR(17),
    location VARCHAR(255),
    FOREIGN KEY (remittance_id) REFERENCES payment_remittances(id) ON DELETE CASCADE,
    INDEX idx_vin (vin),
    INDEX idx_invoice_number (invoice_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Bank Transactions (Zelle payments to drivers)
CREATE TABLE IF NOT EXISTS bank_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    description VARCHAR(255),
    recipient VARCHAR(100),
    transaction_type VARCHAR(50),
    source_file VARCHAR(255),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_transaction_date (transaction_date),
    INDEX idx_recipient (recipient)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Driver Schedules (loads assigned to drivers)
CREATE TABLE IF NOT EXISTS driver_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    schedule_date DATE NOT NULL,
    driver VARCHAR(100) NOT NULL,
    company VARCHAR(255),
    pickup VARCHAR(255),
    dropoff VARCHAR(255),
    load_number VARCHAR(100),
    amount DECIMAL(10, 2),
    date_paid DATE,
    notes TEXT,
    source_file VARCHAR(255),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reconciled BOOLEAN DEFAULT FALSE,
    reconciled_with_transaction_id INT,
    INDEX idx_schedule_date (schedule_date),
    INDEX idx_driver (driver),
    INDEX idx_load_number (load_number),
    INDEX idx_reconciled (reconciled),
    FOREIGN KEY (reconciled_with_transaction_id) REFERENCES bank_transactions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Reconciliation matches
CREATE TABLE IF NOT EXISTS reconciliation_matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    driver_schedule_id INT,
    bank_transaction_id INT,
    remittance_id INT,
    match_type ENUM('FULL', 'PARTIAL', 'MANUAL') DEFAULT 'FULL',
    amount_difference DECIMAL(10, 2) DEFAULT 0,
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    matched_by VARCHAR(100),
    notes TEXT,
    FOREIGN KEY (driver_schedule_id) REFERENCES driver_schedules(id) ON DELETE CASCADE,
    FOREIGN KEY (bank_transaction_id) REFERENCES bank_transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (remittance_id) REFERENCES payment_remittances(id) ON DELETE CASCADE,
    INDEX idx_match_type (match_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upload history
CREATE TABLE IF NOT EXISTS upload_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type ENUM('remittance', 'bank_statement', 'driver_schedule', 'unknown') NOT NULL,
    file_size INT,
    uploaded_by VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP NULL,
    records_imported INT DEFAULT 0,
    error_message TEXT,
    INDEX idx_uploaded_at (uploaded_at),
    INDEX idx_processed (processed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Users (simple authentication)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    email VARCHAR(255),
    role ENUM('admin', 'user', 'viewer') DEFAULT 'user',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_username (username),
    INDEX idx_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Create default admin user (password: admin123 - CHANGE THIS!)
INSERT INTO users (username, password_hash, full_name, role)
VALUES ('admin', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'Administrator', 'admin')
ON DUPLICATE KEY UPDATE username=username;

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INT,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_action (action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Views for common queries

-- Unpaid loads (schedules without matching bank transactions)
CREATE OR REPLACE VIEW v_unpaid_loads AS
SELECT
    ds.id,
    ds.schedule_date,
    ds.driver,
    ds.company,
    ds.pickup,
    ds.dropoff,
    ds.load_number,
    ds.amount,
    ds.source_file,
    DATEDIFF(CURRENT_DATE, ds.schedule_date) as days_outstanding
FROM driver_schedules ds
LEFT JOIN reconciliation_matches rm ON ds.id = rm.driver_schedule_id
WHERE rm.id IS NULL
  AND ds.amount IS NOT NULL
  AND ds.amount > 0
ORDER BY ds.schedule_date DESC;

-- Driver summary view
CREATE OR REPLACE VIEW v_driver_summary AS
SELECT
    ds.driver,
    COUNT(DISTINCT ds.id) as total_loads,
    SUM(ds.amount) as total_scheduled,
    COUNT(DISTINCT CASE WHEN rm.id IS NOT NULL THEN ds.id END) as paid_loads,
    SUM(CASE WHEN rm.id IS NOT NULL THEN ds.amount ELSE 0 END) as total_paid,
    COUNT(DISTINCT CASE WHEN rm.id IS NULL THEN ds.id END) as unpaid_loads,
    SUM(CASE WHEN rm.id IS NULL THEN ds.amount ELSE 0 END) as total_unpaid,
    MIN(ds.schedule_date) as earliest_load,
    MAX(ds.schedule_date) as latest_load
FROM driver_schedules ds
LEFT JOIN reconciliation_matches rm ON ds.id = rm.driver_schedule_id
WHERE ds.amount IS NOT NULL AND ds.amount > 0
GROUP BY ds.driver;

-- Recent activity view
CREATE OR REPLACE VIEW v_recent_activity AS
SELECT
    'payment' as activity_type,
    pr.payment_date as activity_date,
    CONCAT('Payment received: $', pr.payment_amount) as description,
    pr.source_file,
    pr.uploaded_at
FROM payment_remittances pr
UNION ALL
SELECT
    'bank_transaction' as activity_type,
    bt.transaction_date as activity_date,
    CONCAT('Payment to ', bt.recipient, ': $', bt.amount) as description,
    bt.source_file,
    bt.uploaded_at
FROM bank_transactions bt
UNION ALL
SELECT
    'schedule' as activity_type,
    ds.schedule_date as activity_date,
    CONCAT(ds.driver, ' - ', ds.company, ' - $', COALESCE(ds.amount, 0)) as description,
    ds.source_file,
    ds.uploaded_at
FROM driver_schedules ds
ORDER BY activity_date DESC, uploaded_at DESC
LIMIT 100;
