<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo e($page_title ?? APP_NAME); ?> - <?php echo e(APP_NAME); ?></title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f7fa;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        nav {
            display: flex;
            gap: 20px;
        }

        nav a {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 4px;
            transition: background 0.3s;
        }

        nav a:hover, nav a.active {
            background: rgba(255,255,255,0.2);
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .btn {
            display: inline-block;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s;
        }

        .btn:hover {
            background: #5568d3;
        }

        .btn-secondary {
            background: #6c757d;
        }

        .btn-secondary:hover {
            background: #5a6268;
        }

        .btn-danger {
            background: #dc3545;
        }

        .btn-danger:hover {
            background: #c82333;
        }

        .btn-success {
            background: #28a745;
        }

        .btn-success:hover {
            background: #218838;
        }

        .card {
            background: white;
            border-radius: 8px;
            padding: 24px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .card h2 {
            margin-bottom: 20px;
            color: #2d3748;
            font-size: 1.5rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }

        .stat-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }

        .stat-card h3 {
            color: #718096;
            font-size: 0.875rem;
            font-weight: 500;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #2d3748;
        }

        .stat-card.positive {
            border-left-color: #48bb78;
        }

        .stat-card.negative {
            border-left-color: #f56565;
        }

        .stat-card.warning {
            border-left-color: #ed8936;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        table th, table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }

        table th {
            background: #f7fafc;
            font-weight: 600;
            color: #4a5568;
        }

        table tr:hover {
            background: #f7fafc;
        }

        .alert {
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }

        .alert-success {
            background: #d4edda;
            border-left: 4px solid #28a745;
            color: #155724;
        }

        .alert-error {
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            color: #721c24;
        }

        .alert-info {
            background: #d1ecf1;
            border-left: 4px solid #17a2b8;
            color: #0c5460;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #4a5568;
        }

        .form-control {
            width: 100%;
            padding: 10px;
            border: 1px solid #cbd5e0;
            border-radius: 5px;
            font-size: 14px;
        }

        .form-control:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
        }

        .upload-area {
            border: 2px dashed #cbd5e0;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            background: #f7fafc;
            cursor: pointer;
            transition: all 0.3s;
        }

        .upload-area:hover {
            border-color: #667eea;
            background: #edf2f7;
        }

        .upload-area.dragover {
            border-color: #667eea;
            background: #e6fffa;
        }

        .text-center {
            text-align: center;
        }

        .mt-20 {
            margin-top: 20px;
        }

        .text-muted {
            color: #718096;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1><?php echo e(APP_NAME); ?></h1>
            <?php if (isset($auth) && $auth->isLoggedIn()): ?>
                <nav>
                    <a href="/reconcile/index.php" class="<?php echo ($current_page ?? '') === 'dashboard' ? 'active' : ''; ?>">Dashboard</a>
                    <a href="/reconcile/upload.php" class="<?php echo ($current_page ?? '') === 'upload' ? 'active' : ''; ?>">Upload</a>
                    <a href="/reconcile/reports.php" class="<?php echo ($current_page ?? '') === 'reports' ? 'active' : ''; ?>">Reports</a>
                    <a href="/reconcile/drivers.php" class="<?php echo ($current_page ?? '') === 'drivers' ? 'active' : ''; ?>">Drivers</a>
                </nav>
                <div class="user-info">
                    <span>Welcome, <?php echo e($_SESSION['full_name'] ?? $_SESSION['username']); ?></span>
                    <a href="/reconcile/logout.php" class="btn btn-secondary">Logout</a>
                </div>
            <?php endif; ?>
        </div>
    </header>

    <div class="container">
        <?php if ($flash = getFlash('success')): ?>
            <div class="alert alert-success"><?php echo e($flash); ?></div>
        <?php endif; ?>

        <?php if ($flash = getFlash('error')): ?>
            <div class="alert alert-error"><?php echo e($flash); ?></div>
        <?php endif; ?>

        <?php if ($flash = getFlash('info')): ?>
            <div class="alert alert-info"><?php echo e($flash); ?></div>
        <?php endif; ?>
