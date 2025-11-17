#!/usr/bin/env python3
"""
Extract paid dates for all loads from the reconciliation
Outputs a CSV: Load#, Amount, SmartTrucker Date, Bank Deposit Date
"""

import re
import csv
from datetime import datetime
from decimal import Decimal

def main():
    results = []

    # Step 1: Parse SmartTrucker SPV withdrawals (batch payments to S PROVISIONS)
    # These don't have individual load numbers, just batch totals
    with open('March-Oct.txt', 'r') as f:
        for line in f:
            date_match = re.match(r'^([A-Z][a-z]{2}\s+\d{2})\s+(.+)', line)
            if date_match:
                date_str = date_match.group(1)
                rest = date_match.group(2).strip()

                if 'S PROVISIONS LLC' in rest and '| Purchase |' not in rest:
                    # This is a withdrawal/payment
                    numbers = re.findall(r'[\d,]+\.\d{2}', rest)
                    if len(numbers) >= 2:
                        amount = Decimal(numbers[-2].replace(',', ''))

                        # Note: We'll match this to bank CSV later
                        # For now, mark it as "Batch Payment"
                        results.append({
                            'load_num': 'BATCH_PAYMENT',
                            'amount': amount,
                            'smarttrucker_date': date_str + ' 2025',
                            'bank_deposit_date': None,
                            'description': 'S PROVISIONS LLC batch payment'
                        })

    # Step 2: Parse bank CSV to get actual deposit dates
    bank_deposits = {}

    with open('dataset_20251117/dataset_20251117__.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 4:
                continue

            date_str = row[0].strip()
            description = row[1].strip()
            trans_type = row[2].strip()
            amount_str = row[3].strip()

            if not date_str or date_str == 'Date' or not amount_str:
                continue

            try:
                date = datetime.strptime(date_str, '%m/%d/%Y')
                amount = Decimal(amount_str.replace(',', ''))

                if amount > 0:  # Only deposits
                    # Extract load reference if present
                    load_ref = None
                    patterns = [
                        r'(EF-\d+)',           # Expedited Freight
                        r'(R[NP]\d+[A-Z]?)',   # Load refs
                        r'(ETR\d+)',           # Express
                        r'(\d{9,})',           # Long numbers
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, description)
                        if match:
                            load_ref = match.group(1)
                            break

                    if load_ref:
                        # Direct load match
                        results.append({
                            'load_num': load_ref,
                            'amount': amount,
                            'smarttrucker_date': None,
                            'bank_deposit_date': date.strftime('%m/%d/%Y'),
                            'description': description
                        })

                    # Also store for batch matching
                    bank_deposits[amount] = date.strftime('%m/%d/%Y')

            except (ValueError, IndexError):
                continue

    # Step 3: Match batch payments to bank deposits
    for result in results:
        if result['load_num'] == 'BATCH_PAYMENT' and result['bank_deposit_date'] is None:
            # Try to find matching amount in bank deposits
            amount = result['amount']
            if amount in bank_deposits:
                result['bank_deposit_date'] = bank_deposits[amount]

    # Step 4: Write CSV output
    with open('loads_with_paid_dates.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Load Number', 'Amount', 'SmartTrucker Date', 'Bank Deposit Date', 'Description'])

        for result in results:
            writer.writerow([
                result['load_num'],
                f"${result['amount']:.2f}",
                result.get('smarttrucker_date', ''),
                result.get('bank_deposit_date', ''),
                result.get('description', '')
            ])

    print(f"✓ Extracted {len(results)} entries")
    print(f"✓ Saved to: loads_with_paid_dates.csv")

    # Print some examples
    print("\nExamples:")
    print("-" * 100)
    for result in results[:10]:
        print(f"{result['load_num']:20} | ${result['amount']:>10.2f} | ST: {result.get('smarttrucker_date', 'N/A'):15} | Bank: {result.get('bank_deposit_date', 'N/A'):12} | {result.get('description', '')[:40]}")
    print(f"\n... and {len(results) - 10} more entries")

    # Show the specific $2899.39 example
    print("\n" + "="*100)
    print("EXAMPLE: $2899.39 payment")
    print("="*100)
    for result in results:
        if result['amount'] == Decimal('2899.39'):
            print(f"Load #: {result['load_num']}")
            print(f"Amount: ${result['amount']}")
            print(f"SmartTrucker Date: {result.get('smarttrucker_date', 'N/A')}")
            print(f"Bank Deposit Date: {result.get('bank_deposit_date', 'N/A')}")
            print(f"Description: {result.get('description', '')}")

if __name__ == '__main__':
    main()
