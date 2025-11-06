#!/usr/bin/env python3
"""
Clean Reconciliation Script - Improved PNG-quality parsing
Parses bank statements and driver schedules more carefully to avoid duplicates
The text files (March-Oct.txt) actually match the PNG content well
"""

import re
import json
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
from pathlib import Path


class Transaction:
    """Bank transaction from Thread Bank statement"""
    def __init__(self, date, description, deposit, withdrawal, balance, load_ref):
        self.date = date
        self.description = description
        self.deposit = Decimal(str(deposit)) if deposit else None
        self.withdrawal = Decimal(str(withdrawal)) if withdrawal else None
        self.balance = Decimal(str(balance))
        self.load_ref = load_ref  # e.g., RM25746A, 82401425, 627908

    def to_dict(self):
        return {
            'date': self.date,
            'description': self.description,
            'deposit': float(self.deposit) if self.deposit else None,
            'withdrawal': float(self.withdrawal) if self.withdrawal else None,
            'balance': float(self.balance),
            'load_ref': self.load_ref
        }


class DriverLoad:
    """Load from driver schedule"""
    def __init__(self, date, driver, company, pickup, dropoff, load_num, amount):
        self.date = date
        self.driver = driver
        self.company = company
        self.pickup = pickup
        self.dropoff = dropoff
        self.load_num = load_num
        self.amount = Decimal(str(amount)) if amount else Decimal('0')

    def to_dict(self):
        return {
            'date': self.date,
            'driver': self.driver,
            'company': self.company,
            'pickup': self.pickup,
            'dropoff': self.dropoff,
            'load_num': self.load_num,
            'amount': float(self.amount)
        }


def parse_thread_bank_statement(filepath='March-Oct.txt'):
    """Parse Thread Bank statement (matches PNG content)"""
    transactions = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    current_year = 2025  # Default year

    for line in lines:
        # Extract year from statement period
        if 'Statement Period' in line:
            year_match = re.search(r'(\d{4})', line)
            if year_match:
                current_year = int(year_match.group(1))

        # Skip headers and dividers
        if any(skip in line for skip in ['====', 'DATE', 'DESCRIPTION', 'WITHDRAWALS', 'BALANCE',
                                          'Opening Balance', 'S PROVISIONS LLC', 'Thread Bank',
                                          'Statement Period', 'Account', 'Address']):
            continue

        # Parse transaction lines - format: "Apr 01 SmartTrucker SPV, LLC | Purchase | ... 73.12 726.33"
        # Date is at the start (e.g., "Apr 01", "Mar 03")
        date_match = re.match(r'^([A-Z][a-z]{2})\s+(\d{2})\s+(.+)', line)
        if date_match:
            month = date_match.group(1)
            day = date_match.group(2)
            rest = date_match.group(3).strip()

            if not rest:
                continue

            # Extract all numbers (amounts)
            numbers = re.findall(r'[\d,]+\.\d{2}', rest)
            if not numbers:
                continue

            # Find where numbers start to separate description from amounts
            first_num_pos = rest.find(numbers[0])
            description = rest[:first_num_pos].strip()

            if not description or description in ['Interest', 'Opening Balance']:
                continue

            # Extract load reference from description
            load_ref = extract_load_ref(description)

            # Parse amounts
            # Last number is balance
            # If 2 numbers: [amount, balance] - determine withdrawal vs deposit
            # If 3+ numbers: [withdrawal, deposit, balance]
            balance = Decimal(numbers[-1].replace(',', ''))
            withdrawal = None
            deposit = None

            if len(numbers) == 2:
                amount = Decimal(numbers[0].replace(',', ''))
                if 'Ach transfer' in description or 'ACH transfer' in description:
                    withdrawal = amount
                else:
                    deposit = amount
            elif len(numbers) >= 3:
                withdrawal = Decimal(numbers[0].replace(',', ''))
                deposit = Decimal(numbers[1].replace(',', ''))
                if withdrawal == 0 or withdrawal < Decimal('0.01'):
                    withdrawal = None
                if deposit == 0 or deposit < Decimal('0.01'):
                    deposit = None

            date_str = f"{month} {day} {current_year}"

            trans = Transaction(
                date=date_str,
                description=description,
                deposit=float(deposit) if deposit else None,
                withdrawal=float(withdrawal) if withdrawal else None,
                balance=float(balance),
                load_ref=load_ref
            )
            transactions.append(trans)

    return transactions


def extract_load_ref(description):
    """Extract load reference from description"""
    # Pattern 1: RM prefix in parentheses (RM25746A, RM70477A)
    rm_match = re.search(r'\(RM\d+[A-Z]?\)', description)
    if rm_match:
        return rm_match.group(0)[1:-1]

    # Pattern 2: RN prefix in parentheses (RN25746A, RN27772A)
    rn_match = re.search(r'\(RN\d+[A-Z]?\)', description)
    if rn_match:
        return rn_match.group(0)[1:-1]

    # Pattern 3: Numeric IDs in parentheses - Acertus, United Road Logistics, etc.
    num_match = re.search(r'\((\d+)\)', description)
    if num_match:
        return num_match.group(1)

    return None


def parse_driver_schedules(driver_files):
    """Parse driver schedule files, avoiding duplicates"""
    all_loads = []
    seen_loads = set()  # Track (driver, date, load_num) to avoid duplicates

    for filepath in driver_files:
        if not Path(filepath).exists():
            print(f"Warning: {filepath} not found")
            continue

        # Extract driver name from filename
        filename = Path(filepath).stem
        driver_name = filename.split(' - ')[0] if ' - ' in filename else filename

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')

        for line in lines:
            # Skip headers, dividers, and empty lines
            if not line.strip() or '====' in line or 'Page ' in line:
                continue
            if re.match(r'^(Date|Company|Pick)', line):
                continue
            if re.match(r'^[A-Z][a-z]+$', line.strip()):  # Month names
                continue

            # Parse load line: Date Company Pickup Dropoff LoadNum Amount
            # Pattern: 10/1/2025 RPM OKC Tulsa 31544-10482 $390.00
            date_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{4})\s+(.+)', line)
            if not date_match:
                continue

            date_str = date_match.group(1)
            rest = date_match.group(2).strip()

            # Split and find amount (has $ or decimal)
            parts = rest.split()
            if len(parts) < 5:
                continue

            # Find amount (contains $ or is last number-like field)
            amount_idx = None
            for i, part in enumerate(parts):
                if '$' in part or (i > 3 and re.match(r'[\d,]+\.\d{2}', part)):
                    amount_idx = i
                    break

            if amount_idx is None or amount_idx == 0:
                continue

            # Parse amount
            amount_str = parts[amount_idx].replace('$', '').replace(',', '')
            try:
                amount = Decimal(amount_str)
            except:
                continue

            # Load number is before amount
            load_num = parts[amount_idx - 1]

            # Company is first part
            company = parts[0]

            # Pickup and dropoff are between company and load_num
            pickup = parts[1] if len(parts) > 1 else ''
            dropoff = parts[2] if len(parts) > 2 else ''

            # Check for duplicate
            load_key = (driver_name, date_str, load_num)
            if load_key in seen_loads:
                print(f"  Skipping duplicate: {driver_name} - {date_str} - {load_num}")
                continue

            seen_loads.add(load_key)

            load = DriverLoad(
                date=date_str,
                driver=driver_name,
                company=company,
                pickup=pickup,
                dropoff=dropoff,
                load_num=load_num,
                amount=float(amount)
            )
            all_loads.append(load)

    return all_loads


def reconcile(transactions, driver_loads):
    """Reconcile bank transactions with driver loads"""
    matched = []
    unmatched_transactions = []
    unmatched_loads = []

    # Create lookup by load reference
    trans_by_ref = {t.load_ref: t for t in transactions if t.load_ref and t.deposit}
    loads_by_num = {l.load_num: l for l in driver_loads}

    # Match loads to transactions
    for load in driver_loads:
        matched_trans = None

        # Try exact match by load number
        if load.load_num in trans_by_ref:
            matched_trans = trans_by_ref[load.load_num]
            matched.append({
                'load': load.to_dict(),
                'transaction': matched_trans.to_dict(),
                'match_type': 'exact_load_number'
            })
        else:
            # Try partial match
            for ref, trans in trans_by_ref.items():
                if ref and load.load_num and (ref in load.load_num or load.load_num in ref):
                    matched_trans = trans
                    matched.append({
                        'load': load.to_dict(),
                        'transaction': matched_trans.to_dict(),
                        'match_type': 'partial_load_number'
                    })
                    break

        if not matched_trans:
            unmatched_loads.append(load.to_dict())

    # Find unmatched transactions
    matched_refs = {m['transaction']['load_ref'] for m in matched if m['transaction']['load_ref']}
    for trans in transactions:
        if trans.deposit and trans.load_ref and trans.load_ref not in matched_refs:
            unmatched_transactions.append(trans.to_dict())

    return matched, unmatched_transactions, unmatched_loads


def main():
    print("="*80)
    print("CLEAN RECONCILIATION - PNG-QUALITY PARSING")
    print("="*80)
    print()

    # Parse Thread Bank statement (this matches the PNG content)
    print("Parsing Thread Bank statement (March-Oct 2025)...")
    transactions = parse_thread_bank_statement('March-Oct.txt')
    print(f"  Found {len(transactions)} transactions")

    # Calculate totals
    total_deposits = sum(t.deposit for t in transactions if t.deposit)
    total_withdrawals = sum(t.withdrawal for t in transactions if t.withdrawal)
    deposits_with_refs = [t for t in transactions if t.deposit and t.load_ref]

    print(f"  Total deposits: ${total_deposits:,.2f}")
    print(f"  Total withdrawals: ${total_withdrawals:,.2f}")
    print(f"  Deposits with load references: {len(deposits_with_refs)}")

    # Parse driver schedules
    print("\nParsing driver schedules...")
    driver_files = [
        "Little Rich - '25 Schedule (1).txt",
        "Rich - '25 Schedule (1).txt",
        "Steve - '25 Schedule (1).txt",
        "Tony - '25 Schedule (1).txt",
    ]

    driver_loads = parse_driver_schedules(driver_files)
    print(f"  Found {len(driver_loads)} unique loads (duplicates removed)")

    # Calculate driver totals
    driver_totals = defaultdict(Decimal)
    for load in driver_loads:
        driver_totals[load.driver] += load.amount

    print("\n  Driver schedule totals:")
    for driver, total in sorted(driver_totals.items()):
        print(f"    {driver}: ${total:,.2f}")

    # Reconcile
    print("\nReconciling...")
    matched, unmatched_trans, unmatched_loads = reconcile(transactions, driver_loads)

    print(f"  Matched: {len(matched)}")
    print(f"  Unmatched transactions: {len(unmatched_trans)}")
    print(f"  Unmatched loads: {len(unmatched_loads)}")

    # Save results
    results = {
        'summary': {
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'net_deposits': float(total_deposits - total_withdrawals),
            'total_scheduled': float(sum(driver_totals.values())),
            'matched_count': len(matched),
            'unmatched_transactions': len(unmatched_trans),
            'unmatched_loads': len(unmatched_loads),
            'match_rate': f"{len(matched) / len(driver_loads) * 100:.1f}%" if driver_loads else "0%"
        },
        'driver_totals': {driver: float(total) for driver, total in driver_totals.items()},
        'matched': matched,
        'unmatched_transactions': unmatched_trans,
        'unmatched_loads': unmatched_loads
    }

    with open('clean_reconciliation.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total deposits received:      ${total_deposits:,.2f}")
    print(f"Total withdrawals:            ${total_withdrawals:,.2f}")
    print(f"Net deposits:                 ${total_deposits - total_withdrawals:,.2f}")
    print(f"Total scheduled (drivers):    ${sum(driver_totals.values()):,.2f}")
    print(f"Match rate:                   {len(matched) / len(driver_loads) * 100:.1f}%" if driver_loads else "0%")
    print()
    print(f"✓ Results saved to: clean_reconciliation.json")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
