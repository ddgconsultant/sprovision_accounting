<?php
/**
 * S Provisions Reconciliation System - Configuration
 */

// Error reporting (set to 0 in production)
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Timezone
date_default_timezone_set('America/Denver');

// Database Configuration
define('DB_HOST', 'localhost');
define('DB_NAME', 'sprovisions_reconcile');
define('DB_USER', 'sprovisions_user');
define('DB_PASS', 'your_secure_password_here');  // CHANGE THIS!

// Application Settings
define('APP_NAME', 'S Provisions Reconciliation System');
define('APP_VERSION', '1.0.0');
define('SESSION_NAME', 'sprov_reconcile_session');

// File Upload Settings
define('UPLOAD_DIR', __DIR__ . '/../uploads/');
define('DATA_DIR', __DIR__ . '/../data/');
define('MAX_FILE_SIZE', 50 * 1024 * 1024); // 50MB
define('ALLOWED_EXTENSIONS', ['txt', 'pdf', 'csv']);

// Python Integration
define('PYTHON_EXECUTABLE', '/usr/bin/python3');
define('PARSER_SCRIPT', __DIR__ . '/../../reconciliation_parser.py');
define('ENGINE_SCRIPT', __DIR__ . '/../../reconciliation_engine.py');

// Lookback Settings (for payment lag handling)
define('DEFAULT_LOOKBACK_DAYS', 90);  // 60+ days for payment processing
define('MAX_LOOKBACK_DAYS', 365);

// Security
define('SESSION_TIMEOUT', 3600); // 1 hour
define('PASSWORD_MIN_LENGTH', 8);
define('BCRYPT_COST', 10);

// Pagination
define('RECORDS_PER_PAGE', 50);

// Date Format
define('DATE_FORMAT', 'Y-m-d');
define('DATETIME_FORMAT', 'Y-m-d H:i:s');
define('DISPLAY_DATE_FORMAT', 'M d, Y');

// Ensure required directories exist
if (!file_exists(UPLOAD_DIR)) {
    mkdir(UPLOAD_DIR, 0755, true);
}
if (!file_exists(DATA_DIR)) {
    mkdir(DATA_DIR, 0755, true);
}
