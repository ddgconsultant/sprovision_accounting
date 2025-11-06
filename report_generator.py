#!/usr/bin/env python3
"""
Report Generator
Generates various report formats from reconciliation data
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from pathlib import Path

from reconciliation_engine import ReconciliationReport, ReconciliationEngine


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ReportGenerator:
    """Generates reports in various formats"""

    def __init__(self, engine: ReconciliationEngine):
        self.engine = engine

    def generate_summary_text(self, report: ReconciliationReport) -> str:
        """Generate a text summary report"""
        lines = []
        lines.append("=" * 80)
        lines.append("RECONCILIATION SUMMARY REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {report.report_date.strftime('%Y-%m-%d %H:%M:%S')}")

        if report.date_range_start and report.date_range_end:
            lines.append(f"Date Range: {report.date_range_start.strftime('%Y-%m-%d')} to {report.date_range_end.strftime('%Y-%m-%d')}")

        lines.append("")
        lines.append("FINANCIAL SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Remittances Received:     ${report.total_remittances_received:>15,.2f}")
        lines.append(f"Total Paid to Drivers:          ${report.total_paid_to_drivers:>15,.2f}")
        lines.append(f"Total Scheduled Amount:         ${report.total_scheduled_amount:>15,.2f}")
        lines.append(f"Difference (Received - Paid):   ${(report.total_remittances_received - report.total_paid_to_drivers):>15,.2f}")

        lines.append("")
        lines.append("RECONCILIATION STATISTICS")
        lines.append("-" * 80)
        lines.append(f"Fully Matched Transactions:     {len(report.full_matches):>10}")
        lines.append(f"Partial Matches:                {len(report.partial_matches):>10}")
        lines.append(f"Missing Bank Transactions:      {len(report.missing_bank_transactions):>10}")
        lines.append(f"Orphan Bank Transactions:       {len(report.orphan_bank_transactions):>10}")
        lines.append(f"Orphan Payment Remittances:     {len(report.orphan_payments):>10}")
        lines.append(f"Amount Discrepancies:           {len(report.amount_discrepancies):>10}")

        # Driver summaries
        if report.driver_summaries:
            lines.append("")
            lines.append("DRIVER SUMMARIES")
            lines.append("-" * 80)
            lines.append(f"{'Driver':<15} {'Scheduled':<12} {'Paid':<12} {'Unpaid':<12} {'Difference':<12}")
            lines.append("-" * 80)

            for driver, summary in sorted(report.driver_summaries.items()):
                scheduled = summary['scheduled_amount']
                paid = summary['paid_amount']
                unpaid = summary['unpaid_amount']
                diff = scheduled - paid

                lines.append(
                    f"{driver:<15} "
                    f"${scheduled:>10,.2f} "
                    f"${paid:>10,.2f} "
                    f"${unpaid:>10,.2f} "
                    f"${diff:>10,.2f}"
                )

        # Missing bank transactions (unpaid loads)
        if report.missing_bank_transactions:
            lines.append("")
            lines.append("UNPAID LOADS (Missing Bank Transactions)")
            lines.append("-" * 80)
            lines.append(f"{'Date':<12} {'Driver':<15} {'Company':<20} {'Load #':<15} {'Amount':<12}")
            lines.append("-" * 80)

            for entry in sorted(report.missing_bank_transactions, key=lambda x: x.date):
                lines.append(
                    f"{entry.date.strftime('%Y-%m-%d'):<12} "
                    f"{entry.driver:<15} "
                    f"{entry.company:<20} "
                    f"{entry.load_number:<15} "
                    f"${entry.amount:>10,.2f}" if entry.amount else "N/A"
                )

        # Orphan bank transactions
        if report.orphan_bank_transactions:
            lines.append("")
            lines.append("ORPHAN BANK TRANSACTIONS (Paid but not scheduled)")
            lines.append("-" * 80)
            lines.append(f"{'Date':<12} {'Recipient':<20} {'Description':<30} {'Amount':<12}")
            lines.append("-" * 80)

            for trans in sorted(report.orphan_bank_transactions, key=lambda x: x.transaction_date):
                lines.append(
                    f"{trans.transaction_date.strftime('%Y-%m-%d'):<12} "
                    f"{trans.recipient:<20} "
                    f"{trans.description:<30} "
                    f"${trans.amount:>10,.2f}"
                )

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_detailed_text(self, report: ReconciliationReport) -> str:
        """Generate a detailed text report with all matches"""
        lines = []
        lines.append("=" * 80)
        lines.append("DETAILED RECONCILIATION REPORT")
        lines.append("=" * 80)

        # Add summary first
        lines.append(self.generate_summary_text(report))

        # Full matches
        if report.full_matches:
            lines.append("")
            lines.append("FULLY MATCHED TRANSACTIONS")
            lines.append("-" * 80)

            for match in sorted(report.full_matches,
                              key=lambda x: x.driver_entry.date if x.driver_entry else datetime.min):
                if match.driver_entry and match.bank_transaction:
                    lines.append(f"\nSchedule Date: {match.driver_entry.date.strftime('%Y-%m-%d')}")
                    lines.append(f"  Driver: {match.driver_entry.driver}")
                    lines.append(f"  Company: {match.driver_entry.company}")
                    lines.append(f"  Load #: {match.driver_entry.load_number}")
                    lines.append(f"  Scheduled Amount: ${match.driver_entry.amount:,.2f}" if match.driver_entry.amount else "  Scheduled Amount: N/A")
                    lines.append(f"  Payment Date: {match.bank_transaction.transaction_date.strftime('%Y-%m-%d')}")
                    lines.append(f"  Paid Amount: ${match.bank_transaction.amount:,.2f}")
                    lines.append(f"  Days to Payment: {(match.bank_transaction.transaction_date - match.driver_entry.date).days}")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_json_report(self, report: ReconciliationReport) -> str:
        """Generate a JSON report for API/web interface"""
        data = {
            'report_date': report.report_date,
            'date_range': {
                'start': report.date_range_start,
                'end': report.date_range_end,
            },
            'financial_summary': {
                'total_remittances_received': report.total_remittances_received,
                'total_paid_to_drivers': report.total_paid_to_drivers,
                'total_scheduled_amount': report.total_scheduled_amount,
                'difference': report.total_remittances_received - report.total_paid_to_drivers,
            },
            'statistics': {
                'full_matches': len(report.full_matches),
                'partial_matches': len(report.partial_matches),
                'missing_bank_transactions': len(report.missing_bank_transactions),
                'orphan_bank_transactions': len(report.orphan_bank_transactions),
                'orphan_payments': len(report.orphan_payments),
                'amount_discrepancies': len(report.amount_discrepancies),
            },
            'driver_summaries': report.driver_summaries,
            'unpaid_loads': [
                {
                    'date': entry.date,
                    'driver': entry.driver,
                    'company': entry.company,
                    'load_number': entry.load_number,
                    'amount': entry.amount,
                    'pickup': entry.pickup,
                    'dropoff': entry.dropoff,
                }
                for entry in report.missing_bank_transactions
            ],
            'orphan_bank_transactions': [
                {
                    'date': trans.transaction_date,
                    'recipient': trans.recipient,
                    'amount': trans.amount,
                    'description': trans.description,
                }
                for trans in report.orphan_bank_transactions
            ],
        }

        return json.dumps(data, indent=2, cls=DecimalEncoder)

    def generate_csv_driver_summary(self, report: ReconciliationReport) -> str:
        """Generate CSV format driver summary"""
        lines = []
        lines.append("Driver,Scheduled Loads,Scheduled Amount,Paid Loads,Paid Amount,Unpaid Loads,Unpaid Amount,Difference")

        for driver, summary in sorted(report.driver_summaries.items()):
            lines.append(
                f"{driver},"
                f"{summary['scheduled_loads']},"
                f"{summary['scheduled_amount']},"
                f"{summary['paid_loads']},"
                f"{summary['paid_amount']},"
                f"{summary['unpaid_loads']},"
                f"{summary['unpaid_amount']},"
                f"{summary['scheduled_amount'] - summary['paid_amount']}"
            )

        return "\n".join(lines)

    def generate_html_report(self, report: ReconciliationReport) -> str:
        """Generate HTML report for web display"""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reconciliation Report - {report.report_date.strftime('%Y-%m-%d')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1, h2 {{
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .summary-box {{
            background-color: #e7f3fe;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        .amount {{
            text-align: right;
            font-family: monospace;
        }}
        .positive {{
            color: green;
        }}
        .negative {{
            color: red;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Reconciliation Report</h1>
        <p><strong>Generated:</strong> {report.report_date.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Date Range:</strong> {report.date_range_start.strftime('%Y-%m-%d') if report.date_range_start else 'N/A'} to {report.date_range_end.strftime('%Y-%m-%d') if report.date_range_end else 'N/A'}</p>

        <div class="summary-box">
            <h2>Financial Summary</h2>
            <table>
                <tr>
                    <td>Total Remittances Received:</td>
                    <td class="amount">${report.total_remittances_received:,.2f}</td>
                </tr>
                <tr>
                    <td>Total Paid to Drivers:</td>
                    <td class="amount">${report.total_paid_to_drivers:,.2f}</td>
                </tr>
                <tr>
                    <td>Total Scheduled Amount:</td>
                    <td class="amount">${report.total_scheduled_amount:,.2f}</td>
                </tr>
                <tr>
                    <td><strong>Difference (Received - Paid):</strong></td>
                    <td class="amount {'positive' if (report.total_remittances_received - report.total_paid_to_drivers) >= 0 else 'negative'}">
                        <strong>${(report.total_remittances_received - report.total_paid_to_drivers):,.2f}</strong>
                    </td>
                </tr>
            </table>
        </div>

        <h2>Driver Summaries</h2>
        <table>
            <thead>
                <tr>
                    <th>Driver</th>
                    <th>Scheduled</th>
                    <th>Paid</th>
                    <th>Unpaid</th>
                    <th>Difference</th>
                </tr>
            </thead>
            <tbody>
        """

        for driver, summary in sorted(report.driver_summaries.items()):
            diff = summary['scheduled_amount'] - summary['paid_amount']
            diff_class = 'negative' if diff < 0 else 'positive' if diff > 0 else ''

            html += f"""
                <tr>
                    <td>{driver}</td>
                    <td class="amount">${summary['scheduled_amount']:,.2f}</td>
                    <td class="amount">${summary['paid_amount']:,.2f}</td>
                    <td class="amount">${summary['unpaid_amount']:,.2f}</td>
                    <td class="amount {diff_class}">${diff:,.2f}</td>
                </tr>
            """

        html += """
            </tbody>
        </table>
        """

        # Unpaid loads
        if report.missing_bank_transactions:
            html += """
        <div class="warning">
            <h2>Unpaid Loads</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Driver</th>
                        <th>Company</th>
                        <th>Load #</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
            """

            for entry in sorted(report.missing_bank_transactions, key=lambda x: x.date):
                amount_str = f"${entry.amount:,.2f}" if entry.amount else "N/A"
                html += f"""
                    <tr>
                        <td>{entry.date.strftime('%Y-%m-%d')}</td>
                        <td>{entry.driver}</td>
                        <td>{entry.company}</td>
                        <td>{entry.load_number}</td>
                        <td class="amount">{amount_str}</td>
                    </tr>
                """

            html += """
                </tbody>
            </table>
        </div>
            """

        html += """
    </div>
</body>
</html>
        """

        return html

    def save_reports(self, report: ReconciliationReport, output_dir: str = "reports"):
        """Save all report formats to files"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        timestamp = report.report_date.strftime('%Y%m%d_%H%M%S')

        # Save text summary
        summary_file = output_path / f"summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write(self.generate_summary_text(report))

        # Save detailed text
        detailed_file = output_path / f"detailed_{timestamp}.txt"
        with open(detailed_file, 'w') as f:
            f.write(self.generate_detailed_text(report))

        # Save JSON
        json_file = output_path / f"report_{timestamp}.json"
        with open(json_file, 'w') as f:
            f.write(self.generate_json_report(report))

        # Save CSV
        csv_file = output_path / f"driver_summary_{timestamp}.csv"
        with open(csv_file, 'w') as f:
            f.write(self.generate_csv_driver_summary(report))

        # Save HTML
        html_file = output_path / f"report_{timestamp}.html"
        with open(html_file, 'w') as f:
            f.write(self.generate_html_report(report))

        return {
            'summary': str(summary_file),
            'detailed': str(detailed_file),
            'json': str(json_file),
            'csv': str(csv_file),
            'html': str(html_file),
        }
