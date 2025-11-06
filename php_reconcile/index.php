<?php
require_once 'includes/config.php';
require_once 'includes/database.php';
require_once 'includes/auth.php';
require_once 'includes/functions.php';

$auth = new Auth();
$auth->requireLogin();

$db = Database::getInstance();

// Get summary data
$summary = getFinancialSummary();
$drivers = getDriverSummary();
$unpaid = getUnpaidLoads(null, null, null, 10);

$page_title = 'Dashboard';
$current_page = 'dashboard';

require_once 'includes/header.php';
?>

<div class="card">
    <h2>Welcome to the Reconciliation System</h2>
    <p class="text-muted">Overview of payment reconciliation status</p>
</div>

<div class="stats-grid">
    <div class="stat-card positive">
        <h3>Total Remittances Received</h3>
        <div class="value"><?php echo formatCurrency($summary['total_remittances']); ?></div>
    </div>

    <div class="stat-card">
        <h3>Total Paid to Drivers</h3>
        <div class="value"><?php echo formatCurrency($summary['total_paid']); ?></div>
    </div>

    <div class="stat-card">
        <h3>Total Scheduled</h3>
        <div class="value"><?php echo formatCurrency($summary['total_scheduled']); ?></div>
    </div>

    <div class="stat-card <?php echo $summary['unpaid_amount'] > 0 ? 'warning' : ''; ?>">
        <h3>Unpaid Loads</h3>
        <div class="value"><?php echo number_format($summary['unpaid_count']); ?></div>
        <p class="text-muted"><?php echo formatCurrency($summary['unpaid_amount']); ?></p>
    </div>
</div>

<div class="card">
    <h2>Driver Summary</h2>
    <table>
        <thead>
            <tr>
                <th>Driver</th>
                <th>Total Loads</th>
                <th>Scheduled</th>
                <th>Paid</th>
                <th>Unpaid</th>
                <th>Outstanding Amount</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            <?php foreach ($drivers as $driver): ?>
                <tr>
                    <td><strong><?php echo e($driver['driver']); ?></strong></td>
                    <td><?php echo number_format($driver['total_loads']); ?></td>
                    <td><?php echo formatCurrency($driver['total_scheduled']); ?></td>
                    <td><?php echo formatCurrency($driver['total_paid']); ?></td>
                    <td><?php echo number_format($driver['unpaid_loads']); ?></td>
                    <td><?php echo formatCurrency($driver['total_unpaid']); ?></td>
                    <td>
                        <a href="drivers.php?driver=<?php echo urlencode($driver['driver']); ?>" class="btn btn-secondary" style="padding: 5px 10px; font-size: 12px;">View Details</a>
                    </td>
                </tr>
            <?php endforeach; ?>
        </tbody>
    </table>
</div>

<div class="card">
    <h2>Recent Unpaid Loads</h2>
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
        <div style="margin-top: 15px;">
            <a href="reports.php?type=unpaid" class="btn">View All Unpaid Loads</a>
        </div>
    <?php else: ?>
        <p class="text-muted">No unpaid loads found. All drivers are up to date!</p>
    <?php endif; ?>
</div>

<div class="card">
    <h2>Quick Actions</h2>
    <div style="display: flex; gap: 15px; margin-top: 15px;">
        <a href="upload.php" class="btn btn-success">Upload New Documents</a>
        <a href="reports.php" class="btn">Generate Reports</a>
        <a href="drivers.php" class="btn btn-secondary">View All Drivers</a>
    </div>
</div>

<?php require_once 'includes/footer.php'; ?>
