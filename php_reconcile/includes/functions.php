<?php
/**
 * Utility Functions
 */

/**
 * Format currency
 */
function formatCurrency($amount) {
    return '$' . number_format($amount, 2);
}

/**
 * Format date
 */
function formatDate($date, $format = DISPLAY_DATE_FORMAT) {
    if (empty($date)) {
        return '';
    }

    if ($date instanceof DateTime) {
        return $date->format($format);
    }

    return date($format, strtotime($date));
}

/**
 * Sanitize output
 */
function e($string) {
    return htmlspecialchars($string ?? '', ENT_QUOTES, 'UTF-8');
}

/**
 * Redirect
 */
function redirect($url) {
    header("Location: $url");
    exit;
}

/**
 * Get flash message
 */
function getFlash($key) {
    if (isset($_SESSION['flash'][$key])) {
        $message = $_SESSION['flash'][$key];
        unset($_SESSION['flash'][$key]);
        return $message;
    }
    return null;
}

/**
 * Set flash message
 */
function setFlash($key, $message) {
    $_SESSION['flash'][$key] = $message;
}

/**
 * Process file upload
 */
function processFileUpload($fileInputName, $allowedExtensions = ALLOWED_EXTENSIONS) {
    if (!isset($_FILES[$fileInputName]) || $_FILES[$fileInputName]['error'] === UPLOAD_ERR_NO_FILE) {
        throw new Exception('No file uploaded');
    }

    $file = $_FILES[$fileInputName];

    if ($file['error'] !== UPLOAD_ERR_OK) {
        throw new Exception('Upload error: ' . $file['error']);
    }

    if ($file['size'] > MAX_FILE_SIZE) {
        throw new Exception('File too large. Maximum size: ' . (MAX_FILE_SIZE / 1024 / 1024) . 'MB');
    }

    $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, $allowedExtensions)) {
        throw new Exception('Invalid file type. Allowed: ' . implode(', ', $allowedExtensions));
    }

    // Generate unique filename
    $filename = uniqid() . '_' . preg_replace('/[^a-zA-Z0-9._-]/', '_', $file['name']);
    $destination = UPLOAD_DIR . $filename;

    if (!move_uploaded_file($file['tmp_name'], $destination)) {
        throw new Exception('Failed to save uploaded file');
    }

    return [
        'filename' => $filename,
        'original_name' => $file['name'],
        'path' => $destination,
        'size' => $file['size'],
        'extension' => $ext
    ];
}

/**
 * Convert PDF to text using Python script
 */
function convertPdfToText($pdfPath) {
    $txtPath = preg_replace('/\.pdf$/i', '.txt', $pdfPath);

    $cmd = escapeshellcmd(PYTHON_EXECUTABLE . ' ' . dirname(__DIR__) . '/../convert_pdfs_to_text.py ' . dirname($pdfPath));
    exec($cmd, $output, $returnCode);

    if ($returnCode !== 0 || !file_exists($txtPath)) {
        throw new Exception('Failed to convert PDF to text');
    }

    return $txtPath;
}

/**
 * Parse uploaded file using Python parsers
 */
function parseUploadedFile($filePath, $fileType) {
    $pythonScript = __DIR__ . '/../../process_file.py';

    // Create a temporary Python script to parse the file
    $scriptContent = <<<PYTHON
#!/usr/bin/env python3
import sys
import json
from reconciliation_parser import PaymentRemittanceParser, BankStatementParser, DriverScheduleParser

file_path = sys.argv[1]
file_type = sys.argv[2]

try:
    if file_type == 'remittance':
        parser = PaymentRemittanceParser()
        data = parser.parse_file(file_path)
    elif file_type == 'bank_statement':
        parser = BankStatementParser()
        data = parser.parse_file(file_path)
    elif file_type == 'driver_schedule':
        parser = DriverScheduleParser()
        data = parser.parse_file(file_path)
    else:
        print(json.dumps({'error': 'Unknown file type'}))
        sys.exit(1)

    # Convert to JSON
    result = []
    for item in data:
        result.append(item.__dict__)

    print(json.dumps(result, default=str))

except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(1)
PYTHON;

    file_put_contents('/tmp/parse_file_temp.py', $scriptContent);

    $cmd = escapeshellcmd(PYTHON_EXECUTABLE . ' /tmp/parse_file_temp.py ' . escapeshellarg($filePath) . ' ' . escapeshellarg($fileType));
    exec($cmd . ' 2>&1', $output, $returnCode);

    $jsonOutput = implode("\n", $output);
    $data = json_decode($jsonOutput, true);

    if ($returnCode !== 0 || !$data || isset($data['error'])) {
        throw new Exception($data['error'] ?? 'Failed to parse file');
    }

    return $data;
}

/**
 * Get unpaid loads
 */
function getUnpaidLoads($driver = null, $startDate = null, $endDate = null, $limit = null) {
    $db = Database::getInstance();

    $sql = "SELECT * FROM v_unpaid_loads WHERE 1=1";
    $params = [];

    if ($driver) {
        $sql .= " AND driver = :driver";
        $params['driver'] = $driver;
    }

    if ($startDate) {
        $sql .= " AND schedule_date >= :start_date";
        $params['start_date'] = $startDate;
    }

    if ($endDate) {
        $sql .= " AND schedule_date <= :end_date";
        $params['end_date'] = $endDate;
    }

    $sql .= " ORDER BY schedule_date DESC";

    if ($limit) {
        $sql .= " LIMIT :limit";
        $params['limit'] = (int)$limit;
    }

    return $db->fetchAll($sql, $params);
}

/**
 * Get driver summary
 */
function getDriverSummary($driver = null) {
    $db = Database::getInstance();

    $sql = "SELECT * FROM v_driver_summary";
    $params = [];

    if ($driver) {
        $sql .= " WHERE driver = :driver";
        $params['driver'] = $driver;
    }

    $sql .= " ORDER BY driver";

    return $driver ? $db->fetchOne($sql, $params) : $db->fetchAll($sql, $params);
}

/**
 * Get date range data
 */
function getDateRangeData($startDate, $endDate, $type = 'all') {
    $db = Database::getInstance();
    $data = [];

    $params = ['start' => $startDate, 'end' => $endDate];

    if (in_array($type, ['all', 'remittances'])) {
        $data['remittances'] = $db->fetchAll(
            "SELECT * FROM payment_remittances WHERE payment_date BETWEEN :start AND :end ORDER BY payment_date",
            $params
        );
    }

    if (in_array($type, ['all', 'transactions'])) {
        $data['transactions'] = $db->fetchAll(
            "SELECT * FROM bank_transactions WHERE transaction_date BETWEEN :start AND :end ORDER BY transaction_date",
            $params
        );
    }

    if (in_array($type, ['all', 'schedules'])) {
        $data['schedules'] = $db->fetchAll(
            "SELECT * FROM driver_schedules WHERE schedule_date BETWEEN :start AND :end ORDER BY schedule_date",
            $params
        );
    }

    return $data;
}

/**
 * Get financial summary
 */
function getFinancialSummary($startDate = null, $endDate = null) {
    $db = Database::getInstance();

    $dateFilter = '';
    $params = [];

    if ($startDate && $endDate) {
        $dateFilter = " AND schedule_date BETWEEN :start AND :end";
        $params = ['start' => $startDate, 'end' => $endDate];
    }

    return [
        'total_remittances' => $db->fetchColumn(
            "SELECT COALESCE(SUM(payment_amount), 0) FROM payment_remittances" .
            ($startDate && $endDate ? " WHERE payment_date BETWEEN :start AND :end" : ""),
            $params
        ),
        'total_paid' => $db->fetchColumn(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions" .
            ($startDate && $endDate ? " WHERE transaction_date BETWEEN :start AND :end" : ""),
            $params
        ),
        'total_scheduled' => $db->fetchColumn(
            "SELECT COALESCE(SUM(amount), 0) FROM driver_schedules WHERE amount IS NOT NULL" . $dateFilter,
            $params
        ),
        'unpaid_count' => $db->fetchColumn(
            "SELECT COUNT(*) FROM v_unpaid_loads" .
            ($startDate && $endDate ? " WHERE schedule_date BETWEEN :start AND :end" : ""),
            $params
        ),
        'unpaid_amount' => $db->fetchColumn(
            "SELECT COALESCE(SUM(amount), 0) FROM v_unpaid_loads" .
            ($startDate && $endDate ? " WHERE schedule_date BETWEEN :start AND :end" : ""),
            $params
        )
    ];
}

/**
 * Pagination helper
 */
function paginate($totalRecords, $currentPage = 1, $perPage = RECORDS_PER_PAGE) {
    $totalPages = ceil($totalRecords / $perPage);
    $currentPage = max(1, min($currentPage, $totalPages));
    $offset = ($currentPage - 1) * $perPage;

    return [
        'total_records' => $totalRecords,
        'total_pages' => $totalPages,
        'current_page' => $currentPage,
        'per_page' => $perPage,
        'offset' => $offset,
        'has_prev' => $currentPage > 1,
        'has_next' => $currentPage < $totalPages
    ];
}
