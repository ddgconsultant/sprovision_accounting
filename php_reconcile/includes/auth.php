<?php
/**
 * Authentication and Session Management
 */

class Auth {
    private $db;

    public function __construct() {
        $this->db = Database::getInstance();
        $this->startSession();
    }

    private function startSession() {
        if (session_status() === PHP_SESSION_NONE) {
            session_name(SESSION_NAME);
            session_start();

            // Check session timeout
            if (isset($_SESSION['last_activity']) &&
                (time() - $_SESSION['last_activity'] > SESSION_TIMEOUT)) {
                $this->logout();
            }

            $_SESSION['last_activity'] = time();
        }
    }

    public function login($username, $password) {
        $user = $this->db->fetchOne(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            [$username]
        );

        if ($user && password_verify($password, $user['password_hash'])) {
            $_SESSION['user_id'] = $user['id'];
            $_SESSION['username'] = $user['username'];
            $_SESSION['full_name'] = $user['full_name'];
            $_SESSION['role'] = $user['role'];
            $_SESSION['last_activity'] = time();

            // Update last login
            $this->db->update(
                'users',
                ['last_login' => date(DATETIME_FORMAT)],
                'id = :id',
                ['id' => $user['id']]
            );

            // Log login
            $this->logAction('login', null, null, 'User logged in');

            return true;
        }

        return false;
    }

    public function logout() {
        if ($this->isLoggedIn()) {
            $this->logAction('logout', null, null, 'User logged out');
        }

        session_unset();
        session_destroy();
    }

    public function isLoggedIn() {
        return isset($_SESSION['user_id']);
    }

    public function requireLogin() {
        if (!$this->isLoggedIn()) {
            header('Location: /reconcile/login.php');
            exit;
        }
    }

    public function requireRole($role) {
        $this->requireLogin();

        $roles = ['viewer' => 1, 'user' => 2, 'admin' => 3];
        $userRole = $_SESSION['role'] ?? 'viewer';

        if ($roles[$userRole] < $roles[$role]) {
            die('Access denied. Insufficient permissions.');
        }
    }

    public function getCurrentUser() {
        if (!$this->isLoggedIn()) {
            return null;
        }

        return [
            'id' => $_SESSION['user_id'],
            'username' => $_SESSION['username'],
            'full_name' => $_SESSION['full_name'],
            'role' => $_SESSION['role']
        ];
    }

    public function isAdmin() {
        return isset($_SESSION['role']) && $_SESSION['role'] === 'admin';
    }

    public function canEdit() {
        return isset($_SESSION['role']) && in_array($_SESSION['role'], ['admin', 'user']);
    }

    public function logAction($action, $entityType = null, $entityId = null, $details = null) {
        if (!$this->isLoggedIn()) {
            return;
        }

        try {
            $this->db->insert('audit_log', [
                'user_id' => $_SESSION['user_id'],
                'action' => $action,
                'entity_type' => $entityType,
                'entity_id' => $entityId,
                'details' => $details,
                'ip_address' => $_SERVER['REMOTE_ADDR'] ?? null
            ]);
        } catch (Exception $e) {
            error_log("Failed to log action: " . $e->getMessage());
        }
    }

    public static function hashPassword($password) {
        return password_hash($password, PASSWORD_BCRYPT, ['cost' => BCRYPT_COST]);
    }

    public function createUser($username, $password, $fullName, $email, $role = 'user') {
        $this->requireRole('admin');

        if (strlen($password) < PASSWORD_MIN_LENGTH) {
            throw new Exception("Password must be at least " . PASSWORD_MIN_LENGTH . " characters long");
        }

        $userId = $this->db->insert('users', [
            'username' => $username,
            'password_hash' => self::hashPassword($password),
            'full_name' => $fullName,
            'email' => $email,
            'role' => $role
        ]);

        $this->logAction('create_user', 'user', $userId, "Created user: $username");

        return $userId;
    }

    public function changePassword($userId, $newPassword) {
        if ($userId != $_SESSION['user_id'] && !$this->isAdmin()) {
            throw new Exception("Access denied");
        }

        if (strlen($newPassword) < PASSWORD_MIN_LENGTH) {
            throw new Exception("Password must be at least " . PASSWORD_MIN_LENGTH . " characters long");
        }

        $this->db->update(
            'users',
            ['password_hash' => self::hashPassword($newPassword)],
            'id = :id',
            ['id' => $userId]
        );

        $this->logAction('change_password', 'user', $userId, "Password changed");
    }
}
