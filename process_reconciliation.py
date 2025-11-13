#!/usr/bin/env python3
"""
Main Reconciliation Processing Script
Processes all payment data and generates comprehensive reports
"""

import sys
from pathlib import Path
from datetime import datetime

from reconciliation_parser import (
    PaymentRemittanceParser,
    BankStatementParser,
    DriverScheduleParser,
    ReconciliationData
)
from reconciliation_engine import ReconciliationEngine
from report_generator import ReportGenerator


def main():
    print("=" * 80)
    print("S PROVISIONS PAYMENT RECONCILIATION SYSTEM")
    print("=" * 80)
    print()

    # Initialize parsers
    remittance_parser = PaymentRemittanceParser()
    bank_parser = BankStatementParser()
    schedule_parser = DriverScheduleParser()

    # Initialize data container
    data = ReconciliationData()

    # Get current directory
    current_dir = Path('.')

    print("Step 1: Parsing Payment Remittance Data...")
    print("-" * 80)

    # Parse remittance files (Jan-Aug.txt, March-Oct.txt, etc.)
    remittance_files = [
        'Jan-Aug.txt',
        'March - September.txt',
        'March-Oct.txt',
    ]

    for filename in remittance_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  Processing: {filename}")
            try:
                payments = remittance_parser.parse_file(str(filepath))
                data.add_payment_remittances(payments)
                print(f"    Found {len(payments)} payment remittances")
            except Exception as e:
                print(f"    Error: {str(e)}")
        else:
            print(f"  Skipping (not found): {filename}")

    print()
    print("Step 2: Parsing Bank Statement Data (TruckSmarter ACH Withdrawals)...")
    print("-" * 80)

    # Parse bank statement files - ONLY TruckSmarter ACH withdrawals
    # Parser looks ONLY for: "S PROVISIONS LLC | Ach transfer via TruckSmarter app"
    bank_files = [
        'March-Oct.txt',  # Contains TruckSmarter PNG bank statement data
    ]

    for filename in bank_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  Processing: {filename}")
            try:
                transactions = bank_parser.parse_file(str(filepath))
                data.add_bank_transactions(transactions)
                print(f"    Found {len(transactions)} TruckSmarter ACH withdrawals")
            except Exception as e:
                print(f"    Error: {str(e)}")

    print()
    print("Step 3: Parsing Driver Schedules...")
    print("-" * 80)

    # Parse driver schedule files
    schedule_files = [
        "Rich - '25 Schedule (1).txt",
        "Little Rich - '25 Schedule (1).txt",
        "Steve - '25 Schedule (1) (1).txt",
        "Steve - '25 Schedule (1).txt",
        "Tony - '25 Schedule (1).txt",
    ]

    for filename in schedule_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  Processing: {filename}")
            try:
                schedules = schedule_parser.parse_file(str(filepath))
                data.add_driver_schedules(schedules)
                print(f"    Found {len(schedules)} scheduled loads")
            except Exception as e:
                print(f"    Error: {str(e)}")
        else:
            print(f"  Skipping (not found): {filename}")

    print()
    print("Step 4: Data Summary...")
    print("-" * 80)

    summary = data.get_summary()
    print(f"  Payment Remittances: {summary['payment_remittances_count']}")
    print(f"    Total Amount: ${summary['payment_remittances_total']:,.2f}")
    print(f"  Bank Transactions: {summary['bank_transactions_count']}")
    print(f"    Total Amount: ${summary['bank_transactions_total']:,.2f}")
    print(f"  Driver Schedule Entries: {summary['driver_schedule_entries']}")
    print(f"    Total Amount: ${summary['driver_schedule_total']:,.2f}")

    print()
    print("Step 5: Running Reconciliation...")
    print("-" * 80)

    # Run reconciliation with 90-day lookback for payment lag
    engine = ReconciliationEngine(data)
    report = engine.reconcile(lookback_days=90)

    print(f"  Full Matches: {len(report.full_matches)}")
    print(f"  Partial Matches: {len(report.partial_matches)}")
    print(f"  Missing Bank Transactions (Unpaid): {len(report.missing_bank_transactions)}")
    print(f"  Orphan Bank Transactions: {len(report.orphan_bank_transactions)}")

    print()
    print("Step 6: Generating Reports...")
    print("-" * 80)

    # Generate reports
    generator = ReportGenerator(engine)

    # Save all report formats
    output_files = generator.save_reports(report, output_dir="reports")

    print(f"  Summary Report: {output_files['summary']}")
    print(f"  Detailed Report: {output_files['detailed']}")
    print(f"  JSON Report: {output_files['json']}")
    print(f"  CSV Report: {output_files['csv']}")
    print(f"  HTML Report: {output_files['html']}")

    print()
    print("=" * 80)
    print("RECONCILIATION COMPLETE")
    print("=" * 80)
    print()

    # Print summary to console
    print(generator.generate_summary_text(report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
