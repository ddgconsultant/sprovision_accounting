<?php
/**
 * File Upload API Endpoint
 * Handles ad-hoc file uploads and processing
 */

require_once '../includes/config.php';
require_once '../includes/database.php';
require_once '../includes/auth.php';
require_once '../includes/functions.php';

header('Content-Type: application/json');

$auth = new Auth();
$auth->requireRole('user');  // Only users and admins can upload

$db = Database::getInstance();

try {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        throw new Exception('Invalid request method');
    }

    // Process file upload
    $uploadedFile = processFileUpload('file');

    // Determine file type
    $fileType = $_POST['file_type'] ?? 'unknown';

    if (!in_array($fileType, ['remittance', 'bank_statement', 'driver_schedule'])) {
        throw new Exception('Invalid file type specified');
    }

    // Log upload
    $uploadId = $db->insert('upload_history', [
        'filename' => $uploadedFile['original_name'],
        'file_type' => $fileType,
        'file_size' => $uploadedFile['size'],
        'uploaded_by' => $_SESSION['username']
    ]);

    $auth->logAction('file_upload', 'upload', $uploadId, "Uploaded file: {$uploadedFile['original_name']}");

    // Convert PDF to text if needed
    $filePath = $uploadedFile['path'];
    if ($uploadedFile['extension'] === 'pdf') {
        $filePath = convertPdfToText($filePath);
    }

    // Parse the file using Python parsers
    $parsedData = parseUploadedFile($filePath, $fileType);

    // Import data into database
    $db->beginTransaction();

    try {
        $recordsImported = 0;

        switch ($fileType) {
            case 'remittance':
                foreach ($parsedData as $remittance) {
                    $remittanceId = $db->insert('payment_remittances', [
                        'payment_date' => $remittance['payment_date'],
                        'payment_reference' => $remittance['payment_reference'],
                        'paper_document_number' => $remittance['paper_document_number'],
                        'payment_amount' => $remittance['payment_amount'],
                        'source_file' => $uploadedFile['original_name']
                    ]);

                    // Insert invoices
                    if (isset($remittance['invoices'])) {
                        foreach ($remittance['invoices'] as $invoice) {
                            $db->insert('payment_invoices', [
                                'remittance_id' => $remittanceId,
                                'invoice_number' => $invoice['invoice_number'] ?? null,
                                'invoice_date' => $invoice['invoice_date'] ?? null,
                                'invoice_amount' => $invoice['invoice_amount'] ?? null,
                                'discount' => $invoice['discount'] ?? 0,
                                'amount_paid' => $invoice['amount_paid'] ?? null,
                                'vin' => $invoice['vin'] ?? null,
                                'location' => $invoice['location'] ?? null
                            ]);
                        }
                    }

                    $recordsImported++;
                }
                break;

            case 'bank_statement':
                foreach ($parsedData as $transaction) {
                    $db->insert('bank_transactions', [
                        'transaction_date' => $transaction['transaction_date'],
                        'amount' => $transaction['amount'],
                        'description' => $transaction['description'],
                        'recipient' => $transaction['recipient'],
                        'transaction_type' => $transaction['transaction_type'],
                        'source_file' => $uploadedFile['original_name']
                    ]);
                    $recordsImported++;
                }
                break;

            case 'driver_schedule':
                foreach ($parsedData as $schedule) {
                    $db->insert('driver_schedules', [
                        'schedule_date' => $schedule['date'],
                        'driver' => $schedule['driver'],
                        'company' => $schedule['company'],
                        'pickup' => $schedule['pickup'],
                        'dropoff' => $schedule['dropoff'],
                        'load_number' => $schedule['load_number'],
                        'amount' => $schedule['amount'],
                        'notes' => $schedule['notes'] ?? null,
                        'source_file' => $uploadedFile['original_name']
                    ]);
                    $recordsImported++;
                }
                break;
        }

        // Update upload history
        $db->update(
            'upload_history',
            [
                'processed' => 1,
                'processed_at' => date(DATETIME_FORMAT),
                'records_imported' => $recordsImported
            ],
            'id = :id',
            ['id' => $uploadId]
        );

        $db->commit();

        echo json_encode([
            'success' => true,
            'message' => "Successfully processed {$recordsImported} records",
            'upload_id' => $uploadId,
            'records_imported' => $recordsImported
        ]);

    } catch (Exception $e) {
        $db->rollBack();
        throw $e;
    }

} catch (Exception $e) {
    http_response_code(400);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);

    if (isset($uploadId)) {
        $db->update(
            'upload_history',
            ['error_message' => $e->getMessage()],
            'id = :id',
            ['id' => $uploadId]
        );
    }
}
