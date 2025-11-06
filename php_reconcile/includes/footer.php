    </div> <!-- .container -->

    <footer style="background: #2d3748; color: white; padding: 20px 0; margin-top: 40px; text-align: center;">
        <div class="container">
            <p>&copy; <?php echo date('Y'); ?> S Provisions LLC. All rights reserved. | Version <?php echo APP_VERSION; ?></p>
        </div>
    </footer>

    <script>
        // Add any global JavaScript here
        document.addEventListener('DOMContentLoaded', function() {
            // Auto-hide alerts after 5 seconds
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                setTimeout(() => {
                    alert.style.transition = 'opacity 0.5s';
                    alert.style.opacity = '0';
                    setTimeout(() => alert.remove(), 500);
                }, 5000);
            });
        });
    </script>
</body>
</html>
