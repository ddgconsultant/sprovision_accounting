#!/usr/bin/env python3
"""
Enhanced Reconciliation Script for S Provisions LLC
Cross-references SmartTrucker SPV with actual bank statement CSV
to find REAL deposit dates and load numbers

Process:
1. Parse SmartTrucker SPV deposits (from March-Oct.txt)
2. Parse ACTUAL bank statement CSV (dataset_20251117/dataset_20251117__.csv)
3. For each SmartTrucker amount, find matching amount in bank CSV
4. Use bank CSV date as the ACTUAL paid date
5. Also search bank CSV for load numbers directly
"""

import re
import os
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
import json


class SmartTruckerDeposit:
    """Represents a deposit from SmartTrucker SPV"""
    def __init__(self, date, description, amount, load_ref=None):
        self.date = date
        self.description = description
        self.amount = amount
        self.load_ref = load_ref  # e.g., RP31500A, RN25746A
        self.bank_deposit_date = None  # Will be filled from bank CSV

    def __repr__(self):
        return f"SmartTrucker({self.date}, {self.load_ref or 'No Ref'}, ${self.amount})"


class BankDeposit:
    """Represents an actual bank deposit from CSV"""
    def __init__(self, date, description, transaction_type, amount):
        self.date = date  # datetime object
        self.description = description
        self.transaction_type = transaction_type
        self.amount = amount
        self.load_ref = self.extract_load_ref()

    def extract_load_ref(self):
        """Extract load reference from description"""
        # Look for patterns like: EF-58366, RP31500A, RN25746A, etc.
        patterns = [
            r'(EF-\d+)',           # Expedited Freight: EF-58366
            r'(R[NP]\d+[A-Z]?)',   # Load refs: RP31500A, RN25746A
            r'(\d+-\d+)',          # Load refs: 31594-20217
            r'(ETR\d+)',           # Express: ETR13355
            r'(\d{6,})',           # Long numbers: 250603267
        ]

        for pattern in patterns:
            match = re.search(pattern, self.description)
            if match:
                return match.group(1)
        return None

    def __repr__(self):
        return f"BankDeposit({self.date.strftime('%m/%d/%Y')}, {self.load_ref or 'No Ref'}, ${self.amount})"


def parse_smarttrucker_spv(filepath):
    """Parse SmartTrucker SPV WITHDRAWALS (payments OUT to S PROVISIONS LLC) from March-Oct.txt"""
    withdrawals = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    for line in lines:
        # Skip page markers and headers
        if '=====' in line or 'Page' in line or 'DATE DESCRIPTION' in line:
            continue

        # Look for WITHDRAWAL transactions (payments TO S PROVISIONS LLC)
        # Pattern: Date S PROVISIONS LLC | Description Amount Balance
        # Example: Aug 06 S PROVISIONS LLC | Ach transfer via TruckSmarter app 2,899.39 0.00

        # Check if line starts with a date (e.g., "Aug 06")
        date_match = re.match(r'^([A-Z][a-z]{2}\s+\d{2})\s+(.+)', line)
        if date_match:
            date_str = date_match.group(1)
            rest = date_match.group(2).strip()

            # Only process lines with "S PROVISIONS LLC" (these are withdrawals/payments to us)
            if 'S PROVISIONS LLC' not in rest:
                continue

            # Skip if it's a Purchase (those are incoming deposits to SmartTrucker)
            if '| Purchase |' in rest:
                continue

            # Extract load reference from description (in parentheses)
            load_ref_match = re.search(r'\(([^)]+)\)', rest)
            load_ref = load_ref_match.group(1) if load_ref_match else None

            # Extract amounts - typically last two numbers
            # Balance is last, amount is second to last
            numbers = re.findall(r'[\d,]+\.\d{2}', rest)
            if len(numbers) >= 2:
                amount = Decimal(numbers[-2].replace(',', ''))

                # Description is everything except the last two numbers
                description = rest
                for num in numbers[-2:]:
                    description = description.replace(num, '', 1)
                description = description.strip()

                withdrawal = SmartTruckerDeposit(  # Still using same class, just different meaning
                    date=date_str,
                    description=description,
                    amount=amount,
                    load_ref=load_ref
                )
                withdrawals.append(withdrawal)

    return withdrawals


def parse_bank_csv(filepath):
    """Parse actual bank statement CSV"""
    deposits = []

    with open(filepath, 'r', encoding='utf-8') as f:
        # Read CSV - format: Date,Description,Type,Amount
        reader = csv.reader(f)

        for row in reader:
            if len(row) < 4:
                continue

            date_str = row[0].strip()
            description = row[1].strip()
            trans_type = row[2].strip()
            amount_str = row[3].strip()

            # Skip empty or header rows
            if not date_str or date_str == 'Date' or not amount_str:
                continue

            try:
                # Parse date: 4/1/2025 or 8/7/2025
                date = datetime.strptime(date_str, '%m/%d/%Y')

                # Parse amount
                amount = Decimal(amount_str.replace(',', ''))

                # Only process deposits (positive amounts)
                if amount > 0:
                    deposit = BankDeposit(
                        date=date,
                        description=description,
                        transaction_type=trans_type,
                        amount=amount
                    )
                    deposits.append(deposit)
            except (ValueError, IndexError) as e:
                # Skip invalid rows
                continue

    return deposits


def match_smarttrucker_to_bank(st_deposits, bank_deposits):
    """Match SmartTrucker deposits to actual bank deposits"""
    matches = []
    unmatched_st = []
    unmatched_bank = []

    matched_bank_ids = set()

    # Index bank deposits by amount for quick lookup
    bank_by_amount = defaultdict(list)
    for i, bank_dep in enumerate(bank_deposits):
        bank_by_amount[bank_dep.amount].append((i, bank_dep))

    # Also index by load_ref
    bank_by_ref = defaultdict(list)
    for i, bank_dep in enumerate(bank_deposits):
        if bank_dep.load_ref:
            bank_by_ref[bank_dep.load_ref].append((i, bank_dep))

    for st_dep in st_deposits:
        matched = False
        match_type = None
        bank_match = None

        # Try to match by load reference first (highest confidence)
        if st_dep.load_ref and st_dep.load_ref in bank_by_ref:
            for bank_idx, bank_dep in bank_by_ref[st_dep.load_ref]:
                if bank_idx not in matched_bank_ids:
                    st_dep.bank_deposit_date = bank_dep.date.strftime('%m/%d/%Y')
                    matched = True
                    match_type = f"Load ref match: {st_dep.load_ref}"
                    bank_match = bank_dep
                    matched_bank_ids.add(bank_idx)
                    break

        # Try to match by amount (within date range)
        if not matched and st_dep.amount in bank_by_amount:
            # Parse SmartTrucker date (e.g., "Aug 06" -> need to add year)
            # Assume 2025 for now
            try:
                st_date = datetime.strptime(st_dep.date + " 2025", '%b %d %Y')
            except ValueError:
                st_date = None

            for bank_idx, bank_dep in bank_by_amount[st_dep.amount]:
                if bank_idx in matched_bank_ids:
                    continue

                # Check if dates are close (within 3 days)
                if st_date:
                    date_diff = abs((bank_dep.date - st_date).days)
                    if date_diff <= 3:
                        st_dep.bank_deposit_date = bank_dep.date.strftime('%m/%d/%Y')
                        matched = True
                        match_type = f"Amount match (${st_dep.amount}) within {date_diff} days"
                        bank_match = bank_dep
                        matched_bank_ids.add(bank_idx)
                        break

        if matched:
            matches.append({
                'smarttrucker': st_dep,
                'bank': bank_match,
                'match_type': match_type
            })
        else:
            unmatched_st.append(st_dep)

    # Find unmatched bank deposits
    for i, bank_dep in enumerate(bank_deposits):
        if i not in matched_bank_ids:
            # Filter for relevant deposits (S PROVISIONS, Expedited Freight, etc.)
            if any(keyword in bank_dep.description for keyword in [
                'S PROVISIONS', 'Expedited Freigh', 'CARVANA', 'Logistic Transit',
                'ANEW TRANSPORT', 'LR Auto Brokers'
            ]):
                unmatched_bank.append(bank_dep)

    return matches, unmatched_st, unmatched_bank


def print_report(matches, unmatched_st, unmatched_bank):
    """Print reconciliation report"""

    print("="*120)
    print("ENHANCED RECONCILIATION REPORT - SMARTTRUCKER SPV WITHDRAWALS vs ACTUAL BANK DEPOSITS")
    print("="*120)
    print()

    # Matched items
    print(f"MATCHED PAYMENTS ({len(matches)} total)")
    print("-"*120)
    print()

    for i, match in enumerate(matches, 1):
        st = match['smarttrucker']
        bank = match['bank']
        match_type = match['match_type']

        print(f"{i}. MATCH: {match_type}")
        print(f"   SmartTrucker SPV Withdrawal (Payment Sent):")
        print(f"      Date (SPV sent):   {st.date}")
        print(f"      Load Ref:          {st.load_ref or 'N/A'}")
        print(f"      Description:       {st.description[:80]}")
        print(f"      Amount Sent:       ${st.amount}")
        print()
        print(f"   Actual Bank Deposit (Payment Received):")
        print(f"      Date (RECEIVED):   {bank.date.strftime('%m/%d/%Y')} ← THIS IS THE ACTUAL PAID DATE!")
        print(f"      Load Ref:          {bank.load_ref or 'N/A'}")
        print(f"      Description:       {bank.description[:80]}")
        print(f"      Amount Received:   ${bank.amount}")
        print(f"      Type:              {bank.transaction_type}")

        # Show date difference
        try:
            st_date = datetime.strptime(st.date + " 2025", '%b %d %Y')
            days_diff = (bank.date - st_date).days
            if days_diff != 0:
                print(f"      *** NOTICE: Bank deposit was {abs(days_diff)} day(s) {'after' if days_diff > 0 else 'before'} SPV date ***")
        except:
            pass

        print()
        print("-"*120)

    # Unmatched SmartTrucker
    print()
    print("="*120)
    print(f"UNMATCHED SMARTTRUCKER SPV DEPOSITS ({len(unmatched_st)} total)")
    print("="*120)
    print("These deposits appear in SmartTrucker SPV but couldn't be matched to bank deposits")
    print("-"*120)

    for i, st in enumerate(unmatched_st, 1):
        print(f"{i}. {st.date} | {st.load_ref or 'No Ref':12} | ${st.amount:>10} | {st.description[:60]}")

    # Unmatched Bank
    print()
    print("="*120)
    print(f"UNMATCHED BANK DEPOSITS ({len(unmatched_bank)} total)")
    print("="*120)
    print("These deposits appear in bank statement but couldn't be matched to SmartTrucker SPV")
    print("-"*120)

    for i, bank in enumerate(unmatched_bank, 1):
        print(f"{i}. {bank.date.strftime('%m/%d/%Y')} | {bank.load_ref or 'No Ref':12} | ${bank.amount:>10} | {bank.description[:60]}")

    # Summary
    print()
    print("="*120)
    print("SUMMARY")
    print("="*120)
    print(f"Total Matched:                    {len(matches)}")
    print(f"Unmatched SmartTrucker Deposits:  {len(unmatched_st)}")
    print(f"Unmatched Bank Deposits:          {len(unmatched_bank)}")
    print()
    print("="*120)


def main():
    """Main reconciliation process"""

    print("Enhanced Reconciliation Process")
    print("="*120)
    print()

    # Parse SmartTrucker SPV
    print("Step 1: Parsing SmartTrucker SPV WITHDRAWALS (payments to S PROVISIONS LLC from March-Oct.txt)...")
    st_deposits = parse_smarttrucker_spv('March-Oct.txt')
    print(f"   Found {len(st_deposits)} SmartTrucker SPV withdrawal payments")
    print()

    # Parse actual bank CSV
    print("Step 2: Parsing actual bank statement CSV (dataset_20251117/dataset_20251117__.csv)...")
    bank_deposits = parse_bank_csv('dataset_20251117/dataset_20251117__.csv')
    print(f"   Found {len(bank_deposits)} bank deposits")
    print()

    # Match them
    print("Step 3: Matching SmartTrucker SPV withdrawals to actual bank deposits...")
    matches, unmatched_st, unmatched_bank = match_smarttrucker_to_bank(st_deposits, bank_deposits)
    print(f"   Matched: {len(matches)}")
    print(f"   Unmatched SmartTrucker Withdrawals: {len(unmatched_st)}")
    print(f"   Unmatched Bank: {len(unmatched_bank)}")
    print()

    # Print report
    print_report(matches, unmatched_st, unmatched_bank)

    # Save to file
    with open('reconciliation_bank_csv.txt', 'w') as f:
        import sys
        old_stdout = sys.stdout
        sys.stdout = f
        print_report(matches, unmatched_st, unmatched_bank)
        sys.stdout = old_stdout

    print("\n✓ Full report saved to: reconciliation_bank_csv.txt")

    # Save JSON
    json_data = {
        'matches': [
            {
                'smarttrucker_date': m['smarttrucker'].date,
                'bank_date': m['bank'].date.strftime('%m/%d/%Y'),
                'load_ref': m['smarttrucker'].load_ref,
                'amount': float(m['smarttrucker'].amount),
                'match_type': m['match_type'],
                'smarttrucker_description': m['smarttrucker'].description,
                'bank_description': m['bank'].description
            }
            for m in matches
        ],
        'unmatched_smarttrucker': [
            {
                'date': st.date,
                'load_ref': st.load_ref,
                'amount': float(st.amount),
                'description': st.description
            }
            for st in unmatched_st
        ],
        'unmatched_bank': [
            {
                'date': bank.date.strftime('%m/%d/%Y'),
                'load_ref': bank.load_ref,
                'amount': float(bank.amount),
                'description': bank.description
            }
            for bank in unmatched_bank
        ],
        'summary': {
            'total_matched': len(matches),
            'total_unmatched_smarttrucker': len(unmatched_st),
            'total_unmatched_bank': len(unmatched_bank)
        }
    }

    with open('reconciliation_bank_csv.json', 'w') as f:
        json.dump(json_data, f, indent=2)

    print("✓ JSON data saved to: reconciliation_bank_csv.json")
    print()

    # Show specific example for RP31500A
    print()
    print("="*120)
    print("EXAMPLE: RP31500A (the load you mentioned)")
    print("="*120)
    for match in matches:
        if match['smarttrucker'].load_ref == 'RP31500A':
            st = match['smarttrucker']
            bank = match['bank']
            print(f"SmartTrucker SPV shows:  Aug 06 with ${st.amount}")
            print(f"Bank statement shows:    {bank.date.strftime('%B %d, %Y')} with ${bank.amount}")
            print(f"\n*** The ACTUAL paid date is: {bank.date.strftime('%B %d, %Y')} (August 7, 2025) ***")
            break
    else:
        print("RP31500A not found in matches. Checking unmatched...")
        for st in unmatched_st:
            if st.load_ref == 'RP31500A':
                print(f"RP31500A found in unmatched SmartTrucker deposits:")
                print(f"   Date: {st.date}, Amount: ${st.amount}")
                print(f"   Need to check bank CSV manually for ${st.amount} near Aug 06")
    print("="*120)


if __name__ == '__main__':
    main()
