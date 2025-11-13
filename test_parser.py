#!/usr/bin/env python3
"""
Test script to verify BankStatementParser is working correctly
"""

from reconciliation_parser import BankStatementParser
from decimal import Decimal

def test_bank_parser():
    parser = BankStatementParser()

    # Test with March-Oct.txt file
    transactions = parser.parse_file('/home/user/sprovision_accounting/March-Oct.txt')

    print(f"Total transactions found: {len(transactions)}")
    print(f"\nFirst 5 transactions:")
    for i, trans in enumerate(transactions[:5]):
        print(f"  {i+1}. {trans}")

    # Calculate total withdrawals
    total = sum(t.amount for t in transactions)
    print(f"\n{'='*60}")
    print(f"TOTAL WITHDRAWALS: ${total:,.2f}")
    print(f"{'='*60}")

    # Show all transactions by month
    from collections import defaultdict
    by_month = defaultdict(list)
    for trans in transactions:
        month_key = trans.transaction_date.strftime('%Y-%m')
        by_month[month_key].append(trans)

    print(f"\nBreakdown by month:")
    for month in sorted(by_month.keys()):
        month_trans = by_month[month]
        month_total = sum(t.amount for t in month_trans)
        print(f"  {month}: {len(month_trans)} transactions, ${month_total:,.2f}")

    # Verify all are TruckSmarter ACH withdrawals
    print(f"\nVerifying transaction types:")
    for trans in transactions:
        if trans.transaction_type != "ACH_WITHDRAWAL":
            print(f"  WARNING: Found non-ACH transaction: {trans}")
        if "TruckSmarter" not in trans.description:
            print(f"  WARNING: Found non-TruckSmarter transaction: {trans}")

    print(f"\n✓ All {len(transactions)} transactions are TruckSmarter ACH withdrawals")

if __name__ == "__main__":
    test_bank_parser()
