<?php
/**
 * Data Query API Endpoint
 * Supports backward/forward lookup with date ranges
 */

require_once '../includes/config.php';
require_once '../includes/database.php';
require_once '../includes/auth.php';
require_once '../includes/functions.php';

header('Content-Type: application/json');

$auth = new Auth();
$auth->requireLogin();

$db = Database::getInstance();

try {
    $action = $_GET['action'] ?? 'summary';

    switch ($action) {
        case 'summary':
            // Get financial summary
            $startDate = $_GET['start_date'] ?? null;
            $endDate = $_GET['end_date'] ?? null;

            $summary = getFinancialSummary($startDate, $endDate);
            $drivers = getDriverSummary();

            echo json_encode([
                'success' => true,
                'summary' => $summary,
                'drivers' => $drivers,
                'date_range' => [
                    'start' => $startDate,
                    'end' => $endDate
                ]
            ]);
            break;

        case 'unpaid':
            // Get unpaid loads
            $driver = $_GET['driver'] ?? null;
            $startDate = $_GET['start_date'] ?? null;
            $endDate = $_GET['end_date'] ?? null;
            $limit = $_GET['limit'] ?? RECORDS_PER_PAGE;

            $unpaid = getUnpaidLoads($driver, $startDate, $endDate, $limit);

            echo json_encode([
                'success' => true,
                'unpaid_loads' => $unpaid,
                'count' => count($unpaid)
            ]);
            break;

        case 'driver':
            // Get driver detail
            $driver = $_GET['driver'] ?? null;
            if (!$driver) {
                throw new Exception('Driver name required');
            }

            $summary = getDriverSummary($driver);

            $startDate = $_GET['start_date'] ?? null;
            $endDate = $_GET['end_date'] ?? null;

            // Get schedules
            $scheduleSql = "SELECT * FROM driver_schedules WHERE driver = :driver";
            $params = ['driver' => $driver];

            if ($startDate) {
                $scheduleSql .= " AND schedule_date >= :start";
                $params['start'] = $startDate;
            }
            if ($endDate) {
                $scheduleSql .= " AND schedule_date <= :end";
                $params['end'] = $endDate;
            }

            $scheduleSql .= " ORDER BY schedule_date DESC";
            $schedules = $db->fetchAll($scheduleSql, $params);

            // Get matching bank transactions
            $transSql = "SELECT * FROM bank_transactions WHERE recipient LIKE :driver";
            $transParams = ['driver' => '%' . $driver . '%'];

            if ($startDate) {
                $transSql .= " AND transaction_date >= :start";
                $transParams['start'] = $startDate;
            }
            if ($endDate) {
                $transSql .= " AND transaction_date <= :end";
                $transParams['end'] = $endDate;
            }

            $transSql .= " ORDER BY transaction_date DESC";
            $transactions = $db->fetchAll($transSql, $transParams);

            echo json_encode([
                'success' => true,
                'driver' => $driver,
                'summary' => $summary,
                'schedules' => $schedules,
                'transactions' => $transactions
            ]);
            break;

        case 'date_range':
            // Get all data for a date range
            $startDate = $_GET['start_date'] ?? null;
            $endDate = $_GET['end_date'] ?? null;
            $type = $_GET['type'] ?? 'all';

            if (!$startDate || !$endDate) {
                throw new Exception('Start and end dates required');
            }

            $data = getDateRangeData($startDate, $endDate, $type);

            echo json_encode([
                'success' => true,
                'date_range' => [
                    'start' => $startDate,
                    'end' => $endDate
                ],
                'data' => $data
            ]);
            break;

        case 'search':
            // Search by load number, VIN, or invoice number
            $query = $_GET['q'] ?? '';
            if (strlen($query) < 3) {
                throw new Exception('Search query must be at least 3 characters');
            }

            $searchPattern = '%' . $query . '%';

            $results = [
                'schedules' => $db->fetchAll(
                    "SELECT * FROM driver_schedules
                     WHERE load_number LIKE :q OR company LIKE :q
                     ORDER BY schedule_date DESC LIMIT 50",
                    ['q' => $searchPattern]
                ),
                'invoices' => $db->fetchAll(
                    "SELECT pi.*, pr.payment_date, pr.payment_amount
                     FROM payment_invoices pi
                     JOIN payment_remittances pr ON pi.remittance_id = pr.id
                     WHERE pi.invoice_number LIKE :q OR pi.vin LIKE :q
                     ORDER BY pr.payment_date DESC LIMIT 50",
                    ['q' => $searchPattern]
                ),
                'transactions' => $db->fetchAll(
                    "SELECT * FROM bank_transactions
                     WHERE description LIKE :q OR recipient LIKE :q
                     ORDER BY transaction_date DESC LIMIT 50",
                    ['q' => $searchPattern]
                )
            ];

            echo json_encode([
                'success' => true,
                'query' => $query,
                'results' => $results
            ]);
            break;

        case 'recent':
            // Get recent activity
            $limit = $_GET['limit'] ?? 100;

            $activity = $db->fetchAll(
                "SELECT * FROM v_recent_activity ORDER BY activity_date DESC, uploaded_at DESC LIMIT :limit",
                ['limit' => (int)$limit]
            );

            echo json_encode([
                'success' => true,
                'activity' => $activity
            ]);
            break;

        default:
            throw new Exception('Invalid action');
    }

} catch (Exception $e) {
    http_response_code(400);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
}
