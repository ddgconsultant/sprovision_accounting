<?php
require_once 'includes/config.php';
require_once 'includes/database.php';
require_once 'includes/auth.php';
require_once 'includes/functions.php';

$auth = new Auth();
$auth->requireRole('user');

$page_title = 'Upload Documents';
$current_page = 'upload';

require_once 'includes/header.php';
?>

<div class="card">
    <h2>Upload Reconciliation Documents</h2>
    <p class="text-muted">Upload payment remittances, bank statements, or driver schedules for processing</p>

    <form id="uploadForm" enctype="multipart/form-data" style="margin-top: 30px;">
        <div class="form-group">
            <label for="file_type">Document Type</label>
            <select id="file_type" name="file_type" class="form-control" required>
                <option value="">Select document type...</option>
                <option value="remittance">Payment Remittance (Cox Automotive, etc.)</option>
                <option value="bank_statement">Bank Statement (Zelle payments)</option>
                <option value="driver_schedule">Driver Schedule</option>
            </select>
        </div>

        <div class="form-group">
            <label>Upload File (PDF, TXT, or CSV)</label>
            <div class="upload-area" id="uploadArea">
                <svg style="width: 64px; height: 64px; margin: 0 auto; display: block; color: #cbd5e0;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                </svg>
                <p style="margin-top: 15px; color: #4a5568; font-weight: 500;">
                    Drop file here or click to browse
                </p>
                <p class="text-muted" style="font-size: 0.875rem;">
                    Maximum file size: 50MB
                </p>
                <input type="file" id="fileInput" name="file" style="display: none;" accept=".pdf,.txt,.csv">
            </div>
            <div id="fileInfo" style="margin-top: 10px; display: none;">
                <strong>Selected file:</strong> <span id="fileName"></span>
                (<span id="fileSize"></span>)
            </div>
        </div>

        <div id="uploadProgress" style="display: none; margin-top: 20px;">
            <div style="background: #e2e8f0; border-radius: 4px; height: 8px; overflow: hidden;">
                <div id="progressBar" style="background: #667eea; height: 100%; width: 0%; transition: width 0.3s;"></div>
            </div>
            <p id="progressText" class="text-muted" style="margin-top: 5px; font-size: 0.875rem;"></p>
        </div>

        <div id="uploadResult" style="margin-top: 20px;"></div>

        <button type="submit" class="btn btn-success" id="submitBtn" disabled style="margin-top: 20px;">
            Upload and Process
        </button>
    </form>
</div>

<div class="card">
    <h2>Upload History</h2>
    <?php
    $db = Database::getInstance();
    $uploads = $db->fetchAll(
        "SELECT * FROM upload_history ORDER BY uploaded_at DESC LIMIT 20"
    );
    ?>

    <?php if (count($uploads) > 0): ?>
        <table>
            <thead>
                <tr>
                    <th>Date/Time</th>
                    <th>Filename</th>
                    <th>Type</th>
                    <th>Records Imported</th>
                    <th>Status</th>
                    <th>Uploaded By</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($uploads as $upload): ?>
                    <tr>
                        <td><?php echo formatDate($upload['uploaded_at'], DATETIME_FORMAT); ?></td>
                        <td><?php echo e($upload['filename']); ?></td>
                        <td><?php echo e(ucwords(str_replace('_', ' ', $upload['file_type']))); ?></td>
                        <td><?php echo number_format($upload['records_imported']); ?></td>
                        <td>
                            <?php if ($upload['processed']): ?>
                                <span style="color: #28a745; font-weight: 600;">✓ Processed</span>
                            <?php elseif ($upload['error_message']): ?>
                                <span style="color: #dc3545; font-weight: 600;">✗ Error</span>
                                <br><small class="text-muted"><?php echo e($upload['error_message']); ?></small>
                            <?php else: ?>
                                <span class="text-muted">Pending</span>
                            <?php endif; ?>
                        </td>
                        <td><?php echo e($upload['uploaded_by']); ?></td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p class="text-muted">No uploads yet. Upload your first document above!</p>
    <?php endif; ?>
</div>

<script>
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const submitBtn = document.getElementById('submitBtn');
const uploadForm = document.getElementById('uploadForm');
const uploadProgress = document.getElementById('uploadProgress');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const uploadResult = document.getElementById('uploadResult');

// Click to browse
uploadArea.addEventListener('click', () => fileInput.click());

// Drag and drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        handleFileSelect();
    }
});

// File selection
fileInput.addEventListener('change', handleFileSelect);

function handleFileSelect() {
    const file = fileInput.files[0];
    if (file) {
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        fileInfo.style.display = 'block';
        submitBtn.disabled = !document.getElementById('file_type').value;
    }
}

document.getElementById('file_type').addEventListener('change', function() {
    submitBtn.disabled = !fileInput.files.length || !this.value;
});

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Form submission
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(uploadForm);

    submitBtn.disabled = true;
    uploadProgress.style.display = 'block';
    uploadResult.innerHTML = '';

    try {
        progressText.textContent = 'Uploading file...';
        progressBar.style.width = '30%';

        const response = await fetch('/reconcile/api/upload.php', {
            method: 'POST',
            body: formData
        });

        progressBar.style.width = '60%';
        progressText.textContent = 'Processing file...';

        const result = await response.json();

        progressBar.style.width = '100%';

        if (result.success) {
            uploadResult.innerHTML = `
                <div class="alert alert-success">
                    <strong>Success!</strong> ${result.message}<br>
                    Records imported: ${result.records_imported}
                </div>
            `;

            // Reset form
            uploadForm.reset();
            fileInfo.style.display = 'none';
            submitBtn.disabled = true;

            // Reload page after 2 seconds to show new upload in history
            setTimeout(() => location.reload(), 2000);
        } else {
            uploadResult.innerHTML = `
                <div class="alert alert-error">
                    <strong>Error!</strong> ${result.error}
                </div>
            `;
        }
    } catch (error) {
        uploadResult.innerHTML = `
            <div class="alert alert-error">
                <strong>Error!</strong> Failed to upload file: ${error.message}
            </div>
        `;
    } finally {
        progressBar.style.width = '0%';
        uploadProgress.style.display = 'none';
        submitBtn.disabled = false;
    }
});
</script>

<?php require_once 'includes/footer.php'; ?>
