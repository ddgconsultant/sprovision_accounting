<?php
require_once 'includes/config.php';
require_once 'includes/database.php';
require_once 'includes/auth.php';
require_once 'includes/functions.php';

$auth = new Auth();
$auth->requireLogin();

$db = Database::getInstance();

// Get date range from query parameters
$startDate = $_GET['start_date'] ?? date('Y-m-01'); // First day of current month
$endDate = $_GET['end_date'] ?? date('Y-m-d'); // Today
$reportType = $_GET['type'] ?? 'summary';

// Get data based on date range
$summary = getFinancialSummary($startDate, $endDate);
$data = getDateRangeData($startDate, $endDate);

$page_title = 'Reports';
$current_page = 'reports';

require_once 'includes/header.php';
?>

<div class="card">
    <h2>Reconciliation Reports</h2>
    <p class="text-muted">View reconciliation data with backward and forward lookups (60+ day payment lag supported)</p>

    <form method="GET" action="" style="margin-top: 30px;">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
            <div class="form-group">
                <label for="start_date">Start Date</label>
                <input type="date" id="start_date" name="start_date" class="form-control"
                       value="<?php echo e($startDate); ?>">
            </div>

            <div class="form-group">
                <label for="end_date">End Date</label>
                <input type="date" id="end_date" name="end_date" class="form-control"
                       value="<?php echo e($endDate); ?>">
            </div>

            <div class="form-group">
                <label for="type">Report Type</label>
                <select id="type" name="type" class="form-control">
                    <option value="summary" <?php echo $reportType === 'summary' ? 'selected' : ''; ?>>Summary</option>
                    <option value="unpaid" <?php echo $reportType === 'unpaid' ? 'selected' : ''; ?>>Unpaid Loads</option>
                    <option value="remittances" <?php echo $reportType === 'remittances' ? 'selected' : ''; ?>>Payment Remittances</option>
                    <option value="transactions" <?php echo $reportType === 'transactions' ? 'selected' : ''; ?>>Bank Transactions</option>
                    <option value="schedules" <?php echo $reportType === 'schedules' ? 'selected' : ''; ?>>Driver Schedules</option>
                </select>
            </div>

            <div class="form-group">
                <label>&nbsp;</label>
                <button type="submit" class="btn btn-success">Generate Report</button>
            </div>
        </div>
    </form>

    <div style="margin-top: 15px; padding: 10px; background: #edf2f7; border-radius: 5px;">
        <strong>Date Range:</strong> <?php echo formatDate($startDate); ?> to <?php echo formatDate($endDate); ?>
        (<?php echo abs((strtotime($endDate) - strtotime($startDate)) / 86400); ?> days)
    </div>
</div>

<?php if ($reportType === 'summary'): ?>
    <div class="stats-grid">
        <div class="stat-card positive">
            <h3>Total Remittances</h3>
            <div class="value"><?php echo formatCurrency($summary['total_remittances']); ?></div>
        </div>

        <div class="stat-card">
            <h3>Total Paid</h3>
            <div class="value"><?php echo formatCurrency($summary['total_paid']); ?></div>
        </div>

        <div class="stat-card">
            <h3>Total Scheduled</h3>
            <div class="value"><?php echo formatCurrency($summary['total_scheduled']); ?></div>
        </div>

        <div class="stat-card warning">
            <h3>Unpaid</h3>
            <div class="value"><?php echo number_format($summary['unpaid_count']); ?></div>
            <p class="text-muted"><?php echo formatCurrency($summary['unpaid_amount']); ?></p>
        </div>
    </div>

    <div class="card">
        <h2>Driver Breakdown</h2>
        <?php
        $drivers = $db->fetchAll(
            "SELECT
                ds.driver,
                COUNT(DISTINCT ds.id) as total_loads,
                SUM(ds.amount) as total_amount,
                COUNT(DISTINCT CASE WHEN rm.id IS NULL THEN ds.id END) as unpaid_loads,
                SUM(CASE WHEN rm.id IS NULL THEN ds.amount ELSE 0 END) as unpaid_amount
            FROM driver_schedules ds
            LEFT JOIN reconciliation_matches rm ON ds.id = rm.driver_schedule_id
            WHERE ds.schedule_date BETWEEN :start AND :end
              AND ds.amount IS NOT NULL
            GROUP BY ds.driver
            ORDER BY unpaid_amount DESC",
            ['start' => $startDate, 'end' => $endDate]
        );
        ?>

        <table>
            <thead>
                <tr>
                    <th>Driver</th>
                    <th>Total Loads</th>
                    <th>Total Amount</th>
                    <th>Unpaid Loads</th>
                    <th>Unpaid Amount</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($drivers as $driver): ?>
                    <tr>
                        <td><strong><?php echo e($driver['driver']); ?></strong></td>
                        <td><?php echo number_format($driver['total_loads']); ?></td>
                        <td><?php echo formatCurrency($driver['total_amount']); ?></td>
                        <td><?php echo number_format($driver['unpaid_loads']); ?></td>
                        <td><?php echo formatCurrency($driver['unpaid_amount']); ?></td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
<?php endif; ?>

<?php if ($reportType === 'unpaid'): ?>
    <div class="card">
        <h2>Unpaid Loads</h2>
        <?php
        $unpaid = getUnpaidLoads(null, $startDate, $endDate);
        ?>

        <?php if (count($unpaid) > 0): ?>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Driver</th>
                        <th>Company</th>
                        <th>Load #</th>
                        <th>Route</th>
                        <th>Amount</th>
                        <th>Days Outstanding</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($unpaid as $load): ?>
                        <tr>
                            <td><?php echo formatDate($load['schedule_date']); ?></td>
                            <td><?php echo e($load['driver']); ?></td>
                            <td><?php echo e($load['company']); ?></td>
                            <td><?php echo e($load['load_number']); ?></td>
                            <td><?php echo e($load['pickup'] . ' → ' . $load['dropoff']); ?></td>
                            <td><?php echo formatCurrency($load['amount']); ?></td>
                            <td>
                                <span style="<?php echo $load['days_outstanding'] > 60 ? 'color: #dc3545; font-weight: bold;' : ''; ?>">
                                    <?php echo number_format($load['days_outstanding']); ?> days
                                </span>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
            <p class="text-muted" style="margin-top: 15px;">
                <strong>Total:</strong> <?php echo number_format(count($unpaid)); ?> unpaid loads,
                <?php echo formatCurrency(array_sum(array_column($unpaid, 'amount'))); ?>
            </p>
        <?php else: ?>
            <p class="text-muted">No unpaid loads found in this date range.</p>
        <?php endif; ?>
    </div>
<?php endif; ?>

<?php if ($reportType === 'remittances'): ?>
    <div class="card">
        <h2>Payment Remittances</h2>
        <?php if (count($data['remittances']) > 0): ?>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Reference #</th>
                        <th>Document #</th>
                        <th>Amount</th>
                        <th>Source</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($data['remittances'] as $remittance): ?>
                        <tr>
                            <td><?php echo formatDate($remittance['payment_date']); ?></td>
                            <td><?php echo e($remittance['payment_reference']); ?></td>
                            <td><?php echo e($remittance['paper_document_number']); ?></td>
                            <td><?php echo formatCurrency($remittance['payment_amount']); ?></td>
                            <td><?php echo e($remittance['source_file']); ?></td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        <?php else: ?>
            <p class="text-muted">No payment remittances found in this date range.</p>
        <?php endif; ?>
    </div>
<?php endif; ?>

<?php if ($reportType === 'transactions'): ?>
    <div class="card">
        <h2>Bank Transactions (Payments to Drivers)</h2>
        <?php if (count($data['transactions']) > 0): ?>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Recipient</th>
                        <th>Description</th>
                        <th>Amount</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($data['transactions'] as $trans): ?>
                        <tr>
                            <td><?php echo formatDate($trans['transaction_date']); ?></td>
                            <td><?php echo e($trans['recipient']); ?></td>
                            <td><?php echo e($trans['description']); ?></td>
                            <td><?php echo formatCurrency($trans['amount']); ?></td>
                            <td><?php echo e($trans['transaction_type']); ?></td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        <?php else: ?>
            <p class="text-muted">No bank transactions found in this date range.</p>
        <?php endif; ?>
    </div>
<?php endif; ?>

<?php if ($reportType === 'schedules'): ?>
    <div class="card">
        <h2>Driver Schedules</h2>
        <?php if (count($data['schedules']) > 0): ?>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Driver</th>
                        <th>Company</th>
                        <th>Load #</th>
                        <th>Route</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($data['schedules'] as $schedule): ?>
                        <tr>
                            <td><?php echo formatDate($schedule['schedule_date']); ?></td>
                            <td><?php echo e($schedule['driver']); ?></td>
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
            <p class="text-muted">No driver schedules found in this date range.</p>
        <?php endif; ?>
    </div>
<?php endif; ?>

<?php require_once 'includes/footer.php'; ?>
