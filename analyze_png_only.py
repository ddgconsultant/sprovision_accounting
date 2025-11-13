#!/usr/bin/env python3
"""
Analyze ONLY the PNG bank statement data
Does NOT pull from database or driver schedules
"""

from reconciliation_parser import BankStatementParser
from decimal import Decimal
from pathlib import Path
import sys

def analyze_bank_statement(filepath):
    """Analyze a single bank statement file"""
    parser = BankStatementParser()

    print("=" * 80)
    print(f"ANALYZING FILE: {filepath}")
    print("=" * 80)
    print()

    transactions = parser.parse_file(filepath)

    if not transactions:
        print("⚠️  No TruckSmarter ACH withdrawals found in this file!")
        print()
        print("The parser ONLY looks for transactions that match:")
        print('  "S PROVISIONS LLC | Ach transfer via TruckSmarter app"')
        return

    print(f"✅ Found {len(transactions)} TruckSmarter ACH withdrawal(s)")
    print()

    # Calculate totals
    total_withdrawals = sum(t.amount for t in transactions)

    # Group by month
    from collections import defaultdict
    by_month = defaultdict(list)
    for trans in transactions:
        month_key = trans.transaction_date.strftime('%Y-%m (%b)')
        by_month[month_key].append(trans)

    # Display summary
    print("WITHDRAWAL SUMMARY BY MONTH:")
    print("-" * 80)
    for month in sorted(by_month.keys()):
        month_trans = by_month[month]
        month_total = sum(t.amount for t in month_trans)
        print(f"  {month}: {len(month_trans):2d} withdrawals = ${month_total:>12,.2f}")

    print("-" * 80)
    print(f"  TOTAL WITHDRAWALS: ${total_withdrawals:>12,.2f}")
    print("=" * 80)
    print()

    # Show detailed transactions
    print("DETAILED TRANSACTIONS:")
    print("-" * 80)
    for i, trans in enumerate(transactions, 1):
        print(f"{i:2d}. {trans.transaction_date.strftime('%Y-%m-%d')} | ${trans.amount:>10,.2f}")
    print()

    return {
        'transaction_count': len(transactions),
        'total_withdrawals': float(total_withdrawals),
        'transactions': transactions
    }

def main():
    """Main entry point"""

    # Check if file path provided
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not Path(filepath).exists():
            print(f"Error: File not found: {filepath}")
            sys.exit(1)
        analyze_bank_statement(filepath)
        return

    # Otherwise, analyze the default file
    print("=" * 80)
    print("BANK STATEMENT ANALYZER")
    print("Extracts ONLY TruckSmarter ACH withdrawals from bank statements")
    print("=" * 80)
    print()

    # Look for the March-Oct.txt file (the one with PNG data)
    default_file = '/home/user/sprovision_accounting/March-Oct.txt'

    if Path(default_file).exists():
        analyze_bank_statement(default_file)
    else:
        print("Usage: python3 analyze_png_only.py <bank_statement_file.txt>")
        print()
        print("Available files:")
        for txt_file in sorted(Path('/home/user/sprovision_accounting').glob('*.txt')):
            if txt_file.name not in ['reconciliation_full_report.txt', 'test_parser.py']:
                print(f"  - {txt_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()
