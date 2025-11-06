<?php
require_once 'includes/config.php';
require_once 'includes/database.php';
require_once 'includes/auth.php';
require_once 'includes/functions.php';

$auth = new Auth();
$auth->requireLogin();

$db = Database::getInstance();

// Get driver from query parameter
$selectedDriver = $_GET['driver'] ?? null;
$startDate = $_GET['start_date'] ?? null;
$endDate = $_GET['end_date'] ?? null;

$page_title = $selectedDriver ? "Driver: $selectedDriver" : 'All Drivers';
$current_page = 'drivers';

require_once 'includes/header.php';
?>

<?php if (!$selectedDriver): ?>
    <!-- All Drivers View -->
    <div class="card">
        <h2>All Drivers</h2>
        <p class="text-muted">Select a driver to view detailed information</p>
    </div>

    <?php
    $drivers = getDriverSummary();
    ?>

    <div class="stats-grid">
        <?php foreach ($drivers as $driver): ?>
            <div class="stat-card">
                <h3><?php echo e($driver['driver']); ?></h3>
                <div style="margin-top: 15px;">
                    <p><strong>Total Loads:</strong> <?php echo number_format($driver['total_loads']); ?></p>
                    <p><strong>Scheduled:</strong> <?php echo formatCurrency($driver['total_scheduled']); ?></p>
                    <p><strong>Paid:</strong> <?php echo formatCurrency($driver['total_paid']); ?></p>
                    <p style="color: #dc3545;"><strong>Unpaid:</strong> <?php echo formatCurrency($driver['total_unpaid']); ?></p>
                    <a href="?driver=<?php echo urlencode($driver['driver']); ?>" class="btn" style="margin-top: 10px; width: 100%;">View Details</a>
                </div>
            </div>
        <?php endforeach; ?>
    </div>

<?php else: ?>
    <!-- Single Driver View -->
    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h2><?php echo e($selectedDriver); ?></h2>
                <p class="text-muted">Detailed driver information and payment history</p>
            </div>
            <a href="drivers.php" class="btn btn-secondary">← Back to All Drivers</a>
        </div>

        <form method="GET" action="" style="margin-top: 30px;">
            <input type="hidden" name="driver" value="<?php echo e($selectedDriver); ?>">
            <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 15px;">
                <div class="form-group">
                    <label for="start_date">Start Date (optional)</label>
                    <input type="date" id="start_date" name="start_date" class="form-control"
                           value="<?php echo e($startDate); ?>">
                </div>

                <div class="form-group">
                    <label for="end_date">End Date (optional)</label>
                    <input type="date" id="end_date" name="end_date" class="form-control"
                           value="<?php echo e($endDate); ?>">
                </div>

                <div class="form-group">
                    <label>&nbsp;</label>
                    <button type="submit" class="btn">Filter</button>
                </div>
            </div>
        </form>
    </div>

    <?php
    $summary = getDriverSummary($selectedDriver);
    ?>

    <div class="stats-grid">
        <div class="stat-card">
            <h3>Total Loads</h3>
            <div class="value"><?php echo number_format($summary['total_loads']); ?></div>
        </div>

        <div class="stat-card positive">
            <h3>Total Scheduled</h3>
            <div class="value"><?php echo formatCurrency($summary['total_scheduled']); ?></div>
        </div>

        <div class="stat-card">
            <h3>Total Paid</h3>
            <div class="value"><?php echo formatCurrency($summary['total_paid']); ?></div>
        </div>

        <div class="stat-card warning">
            <h3>Unpaid Amount</h3>
            <div class="value"><?php echo formatCurrency($summary['total_unpaid']); ?></div>
            <p class="text-muted"><?php echo number_format($summary['unpaid_loads']); ?> loads</p>
        </div>
    </div>

    <?php
    // Get schedules
    $scheduleSql = "SELECT * FROM driver_schedules WHERE driver = :driver";
    $params = ['driver' => $selectedDriver];

    if ($startDate) {
        $scheduleSql .= " AND schedule_date >= :start";
        $params['start'] = $startDate;
    }
    if ($endDate) {
        $scheduleSql .= " AND schedule_date <= :end";
        $params['end'] = $endDate;
    }

    $scheduleSql .= " ORDER BY schedule_date DESC LIMIT 100";
    $schedules = $db->fetchAll($scheduleSql, $params);

    // Get transactions
    $transSql = "SELECT * FROM bank_transactions WHERE recipient LIKE :driver";
    $transParams = ['driver' => '%' . $selectedDriver . '%'];

    if ($startDate) {
        $transSql .= " AND transaction_date >= :start";
        $transParams['start'] = $startDate;
    }
    if ($endDate) {
        $transSql .= " AND transaction_date <= :end";
        $transParams['end'] = $endDate;
    }

    $transSql .= " ORDER BY transaction_date DESC LIMIT 100";
    $transactions = $db->fetchAll($transSql, $transParams);
    ?>

    <div class="card">
        <h2>Scheduled Loads</h2>
        <?php if (count($schedules) > 0): ?>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Company</th>
                        <th>Load #</th>
                        <th>Route</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($schedules as $schedule): ?>
                        <tr>
                            <td><?php echo formatDate($schedule['schedule_date']); ?></td>
                            <td><?php echo e($schedule['company']); ?></td>
                            <td><?php echo e($schedule['load_number']); ?></td>
                            <td><?php echo e($schedule['pickup'] . ' → ' . $schedule['dropoff']); ?></td>
                            <td><?php echo $schedule['amount'] ? formatCurrency($schedule['amount']) : 'N/A'; ?></td>
                            <td>
                                <?php if ($schedule['reconciled']): ?>
                                    <span style="color: #28a745;">✓ Paid</span>
                                <?php else: ?>
                                    <span class="text-muted">Unpaid</span>
                                <?php endif; ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        <?php else: ?>
            <p class="text-muted">No scheduled loads found.</p>
        <?php endif; ?>
    </div>

    <div class="card">
        <h2>Payment History (Bank Transactions)</h2>
        <?php if (count($transactions) > 0): ?>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Amount</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($transactions as $trans): ?>
                        <tr>
                            <td><?php echo formatDate($trans['transaction_date']); ?></td>
                            <td><?php echo e($trans['description']); ?></td>
                            <td><?php echo formatCurrency($trans['amount']); ?></td>
                            <td><?php echo e($trans['transaction_type']); ?></td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
            <p class="text-muted" style="margin-top: 15px;">
                <strong>Total Paid:</strong> <?php echo formatCurrency(array_sum(array_column($transactions, 'amount'))); ?>
            </p>
        <?php else: ?>
            <p class="text-muted">No payment transactions found.</p>
        <?php endif; ?>
    </div>

<?php endif; ?>

<?php require_once 'includes/footer.php'; ?>
