# S Provisions Payment Reconciliation System

A comprehensive payment reconciliation system designed to manage and reconcile payments between client remittances, driver schedules, and bank transactions. Handles the 60+ day payment processing lag common in the logistics industry.

## Features

### Python Processing Engine
- **Multi-format Parser**: Parses payment remittances (PDF/TXT), bank statements, and driver schedules
- **Intelligent Reconciliation**: Matches payments with schedules across 60+ day time windows
- **Comprehensive Reports**: Generates text, HTML, JSON, and CSV reports
- **Automated Processing**: Batch processes all data files and identifies discrepancies

### PHP Web Interface
- **Ad-hoc File Upload**: Upload and process reconciliation documents on demand
- **Backward/Forward Lookup**: Query data across extended date ranges to track delayed payments
- **Real-time Dashboard**: View current reconciliation status and financial summaries
- **Driver Management**: Track individual driver schedules, payments, and outstanding balances
- **Advanced Reporting**: Generate customizable reports with flexible date range filtering
- **Secure Authentication**: Role-based access control (Admin, User, Viewer)

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Sources                              │
├──────────────────┬──────────────────┬───────────────────────┤
│ Payment          │ Bank Statements  │ Driver Schedules      │
│ Remittances      │ (Zelle)          │                       │
│ (Cox Automotive) │                  │                       │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ├──────────────────┴─────────────────────┤
         │        Python Parsing Engine           │
         │  ┌────────────────────────────────┐    │
         │  │ PaymentRemittanceParser        │    │
         │  │ BankStatementParser            │    │
         │  │ DriverScheduleParser           │    │
         │  └────────────────────────────────┘    │
         └──────────────────┬─────────────────────┘
                            │
         ┌──────────────────┴─────────────────────┐
         │   Reconciliation Engine                 │
         │  ┌────────────────────────────────┐    │
         │  │ Match payments with schedules  │    │
         │  │ Handle 60+ day lags            │    │
         │  │ Identify discrepancies         │    │
         │  └────────────────────────────────┘    │
         └──────────────────┬─────────────────────┘
                            │
         ┌──────────────────┴─────────────────────┐
         │          MySQL Database                 │
         │  ┌────────────────────────────────┐    │
         │  │ payment_remittances            │    │
         │  │ bank_transactions              │    │
         │  │ driver_schedules               │    │
         │  │ reconciliation_matches         │    │
         │  └────────────────────────────────┘    │
         └──────────────────┬─────────────────────┘
                            │
         ┌──────────────────┴─────────────────────┐
         │         PHP Web Interface               │
         │  ┌────────────────────────────────┐    │
         │  │ Dashboard                      │    │
         │  │ Upload & Process              │    │
         │  │ Reports & Analytics           │    │
         │  │ Driver Management             │    │
         │  └────────────────────────────────┘    │
         └─────────────────────────────────────────┘
```

## Installation

### Prerequisites
- Python 3.7+
- PHP 7.4+ with PDO MySQL extension
- MySQL 5.7+ or MariaDB 10.2+
- Web server (Apache/Nginx)
- pip (Python package manager)

### Python Dependencies
```bash
pip install pdfplumber
```

### Database Setup

1. Create the database:
```bash
mysql -u root -p < php_reconcile/schema.sql
```

2. Create a database user:
```sql
CREATE USER 'sprovisions_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON sprovisions_reconcile.* TO 'sprovisions_user'@'localhost';
FLUSH PRIVILEGES;
```

3. Update the configuration:
Edit `php_reconcile/includes/config.php` and set your database credentials.

### Web Server Configuration

#### Apache (.htaccess)
```apache
RewriteEngine On
RewriteBase /reconcile/

# Redirect to login if not authenticated
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ index.php [L,QSA]
```

#### Nginx
```nginx
location /reconcile/ {
    try_files $uri $uri/ /reconcile/index.php?$query_string;

    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php7.4-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
    }
}
```

### File Permissions
```bash
chmod 755 php_reconcile/
chmod 777 php_reconcile/uploads/
chmod 777 php_reconcile/data/
chmod 644 php_reconcile/includes/*.php
```

## Usage

### Command Line Processing

#### Process all existing data:
```bash
python3 process_reconciliation.py
```

This will:
1. Parse all payment remittances, bank statements, and driver schedules
2. Run reconciliation with 90-day lookback
3. Generate comprehensive reports in `reports/` directory

#### Convert PDFs to text:
```bash
python3 convert_pdfs_to_text.py
```

### Web Interface

#### Access the system:
```
http://office.sprovisions.com/reconcile/
```

#### Default Login:
- **Username**: admin
- **Password**: admin123
- ⚠️ **IMPORTANT**: Change this password immediately after first login!

#### Upload Documents:
1. Navigate to Upload page
2. Select document type (Remittance, Bank Statement, or Driver Schedule)
3. Upload PDF, TXT, or CSV file
4. System will automatically parse and import data

#### Generate Reports:
1. Navigate to Reports page
2. Select date range (supports backward/forward lookup)
3. Choose report type (Summary, Unpaid Loads, etc.)
4. View or export results

#### View Driver Details:
1. Navigate to Drivers page
2. Click on a driver to see detailed history
3. Filter by date range to analyze specific periods

## Data Formats

### Payment Remittance (Cox Automotive)
- Email-based payment advice
- Contains: Payment date, reference number, amount, invoice details
- Parsed fields: Invoice numbers, VINs, locations, amounts

### Bank Statements (FirstBank)
- Zelle transfers to drivers
- Contains: Transaction date, recipient, amount
- Parsed fields: Driver name normalization, payment amounts

### Driver Schedules
- Tab or space-delimited format
- Contains: Date, driver, company, pickup, dropoff, load number, amount
- Parsed fields: All schedule details with optional amounts

## Database Schema

### Core Tables
- `payment_remittances` - Payments received from clients
- `payment_invoices` - Invoice details from remittances
- `bank_transactions` - Zelle payments to drivers
- `driver_schedules` - Scheduled loads for drivers
- `reconciliation_matches` - Matched payments and schedules
- `upload_history` - File upload tracking
- `users` - System users and authentication
- `audit_log` - Activity tracking

### Views
- `v_unpaid_loads` - All unpaid driver loads
- `v_driver_summary` - Per-driver statistics
- `v_recent_activity` - Recent system activity

## API Endpoints

### POST /reconcile/api/upload.php
Upload and process a new file
- Parameters: `file` (file upload), `file_type` (remittance|bank_statement|driver_schedule)
- Returns: JSON with success status and record count

### GET /reconcile/api/query.php
Query reconciliation data
- Actions:
  - `summary` - Get financial summary
  - `unpaid` - Get unpaid loads
  - `driver` - Get driver details
  - `date_range` - Get data for date range
  - `search` - Search by load number, VIN, or invoice
  - `recent` - Get recent activity

## Reconciliation Logic

### Driver Name Normalization
The system normalizes driver names to match across different data sources:
- "RICH-LITTLE" → "Little Rich"
- "BIGRICH" → "Rich"
- "STEVEMARTIN" → "Steve"

### Payment Matching
1. Match driver name from bank transaction to schedule entry
2. Match amount within $0.01 tolerance
3. Match date within 90-day window (configurable)
4. Score matches based on date proximity

### 60+ Day Lag Handling
- Default lookback: 90 days
- Configurable in `config.php` (DEFAULT_LOOKBACK_DAYS)
- Reports show "Days Outstanding" for each unpaid load
- Backward/forward lookup in reports supports full date range queries

## Security

### Authentication
- Session-based authentication with timeout (1 hour default)
- Password hashing with bcrypt (cost: 10)
- Role-based access control (Admin, User, Viewer)

### File Upload Security
- File type validation (PDF, TXT, CSV only)
- File size limit (50MB default)
- Unique filename generation
- Upload directory outside web root (recommended)

### SQL Injection Prevention
- Prepared statements for all database queries
- PDO with parameter binding

### XSS Prevention
- Output escaping with `htmlspecialchars()`
- CSP headers (recommended in production)

## Troubleshooting

### PDF Parsing Issues
If PDFs aren't parsing correctly:
1. Check that `pdfplumber` is installed: `pip install pdfplumber`
2. Verify PDF is text-based (not scanned images)
3. Check Python path in `config.php`

### Driver Name Matching Issues
If drivers aren't matching:
1. Check driver name normalization in `reconciliation_engine.py`
2. Add new mappings to `driver_name_map` dictionary
3. Update case-insensitive matching logic

### Database Connection Issues
1. Verify MySQL credentials in `config.php`
2. Check database user permissions
3. Ensure MySQL is running: `systemctl status mysql`

### Upload Failures
1. Check directory permissions: `chmod 777 php_reconcile/uploads/`
2. Verify PHP file upload settings in `php.ini`:
   - `upload_max_filesize = 50M`
   - `post_max_size = 50M`
3. Check error logs: `tail -f /var/log/apache2/error.log`

## Production Deployment

### Security Checklist
- [ ] Change default admin password
- [ ] Update database credentials
- [ ] Set `display_errors = 0` in PHP
- [ ] Enable HTTPS
- [ ] Configure firewall rules
- [ ] Set appropriate file permissions
- [ ] Enable audit logging
- [ ] Configure backup strategy
- [ ] Set session security flags
- [ ] Implement rate limiting

### Performance Optimization
- [ ] Enable PHP OpCache
- [ ] Add database indexes
- [ ] Configure query caching
- [ ] Optimize large file uploads
- [ ] Use CDN for static assets (if needed)

### Backup Strategy
```bash
# Database backup
mysqldump -u root -p sprovisions_reconcile > backup_$(date +%Y%m%d).sql

# File backup
tar -czf uploads_$(date +%Y%m%d).tar.gz php_reconcile/uploads/
```

## File Structure

```
sprovision_accounting/
├── README.md
├── convert_pdfs_to_text.py          # PDF to text converter
├── reconciliation_parser.py          # Data parsers
├── reconciliation_engine.py          # Reconciliation logic
├── report_generator.py               # Report generation
├── process_reconciliation.py         # Main processing script
├── reports/                          # Generated reports
│   ├── summary_*.txt
│   ├── detailed_*.txt
│   ├── report_*.html
│   ├── report_*.json
│   └── driver_summary_*.csv
└── php_reconcile/                    # Web interface
    ├── index.php                     # Dashboard
    ├── login.php                     # Login page
    ├── logout.php                    # Logout handler
    ├── upload.php                    # File upload interface
    ├── reports.php                   # Reports interface
    ├── drivers.php                   # Driver management
    ├── schema.sql                    # Database schema
    ├── includes/
    │   ├── config.php                # Configuration
    │   ├── database.php              # Database connection
    │   ├── auth.php                  # Authentication
    │   ├── functions.php             # Utility functions
    │   ├── header.php                # Page header
    │   └── footer.php                # Page footer
    ├── api/
    │   ├── upload.php                # Upload API endpoint
    │   └── query.php                 # Query API endpoint
    ├── uploads/                      # Uploaded files
    └── data/                         # Processed data
```

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review error logs
3. Contact system administrator

## License

Copyright © 2025 S Provisions LLC. All rights reserved.

## Version History

### v1.0.0 (2025-11-06)
- Initial release
- Python parsing engine with multi-format support
- PHP web interface with role-based access
- 60+ day payment lag handling
- Backward/forward date range lookup
- Comprehensive reporting system
- Ad-hoc file upload and processing
