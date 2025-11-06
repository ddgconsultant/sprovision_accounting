#!/usr/bin/env python3
"""
Reconciliation Script for S Provisions LLC
Matches LOADS # to PAYMENTS to DEPOSITS

This script:
1. Parses load schedules (various driver schedules)
2. Parses payment remittance advice (from Cox Automotive)
3. Parses bank deposits (Thread Bank statements)
4. Reconciles all three data sources
5. Generates reports of matched and unmatched items
"""

import re
import os
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
import json


class Load:
    """Represents a single load/transport job"""
    def __init__(self, date, company, pickup, dropoff, load_num, amount, date_paid=None, notes=None, source_file=None):
        self.date = date
        self.company = company
        self.pickup = pickup
        self.dropoff = dropoff
        self.load_num = load_num
        self.amount = amount
        self.date_paid = date_paid
        self.notes = notes
        self.source_file = source_file

    def __repr__(self):
        return f"Load({self.date}, {self.company}, {self.load_num}, ${self.amount})"

    def to_dict(self):
        return {
            'date': self.date,
            'company': self.company,
            'pickup': self.pickup,
            'dropoff': self.dropoff,
            'load_num': self.load_num,
            'amount': float(self.amount),
            'date_paid': self.date_paid,
            'notes': self.notes,
            'source_file': self.source_file
        }


class Payment:
    """Represents a payment from Cox Automotive"""
    def __init__(self, payment_ref, paper_doc_num, payment_date, payment_amount, invoices, source_file=None):
        self.payment_ref = payment_ref
        self.paper_doc_num = paper_doc_num
        self.payment_date = payment_date
        self.payment_amount = payment_amount
        self.invoices = invoices  # List of invoice dicts
        self.source_file = source_file

    def __repr__(self):
        return f"Payment({self.payment_date}, ${self.payment_amount}, Invoices: {len(self.invoices)})"

    def to_dict(self):
        return {
            'payment_ref': self.payment_ref,
            'paper_doc_num': self.paper_doc_num,
            'payment_date': self.payment_date,
            'payment_amount': float(self.payment_amount),
            'invoices': self.invoices,
            'source_file': self.source_file
        }


class Deposit:
    """Represents a bank deposit/transaction"""
    def __init__(self, date, description, amount, balance, load_ref=None, source_file=None):
        self.date = date
        self.description = description
        self.amount = amount
        self.balance = balance
        self.load_ref = load_ref  # Extracted from description (e.g., RN25746A)
        self.source_file = source_file

    def __repr__(self):
        return f"Deposit({self.date}, {self.load_ref or 'No Ref'}, ${self.amount})"

    def to_dict(self):
        return {
            'date': self.date,
            'description': self.description,
            'amount': float(self.amount),
            'balance': float(self.balance),
            'load_ref': self.load_ref,
            'source_file': self.source_file
        }


class Reconciliation:
    """Represents a reconciled match between load, payment, and deposit"""
    def __init__(self, load=None, payment=None, deposit=None, match_confidence=None, match_reason=None):
        self.load = load
        self.payment = payment
        self.deposit = deposit
        self.match_confidence = match_confidence  # 'high', 'medium', 'low'
        self.match_reason = match_reason

    def is_complete(self):
        """Returns True if all three items are matched"""
        return self.load is not None and self.payment is not None and self.deposit is not None

    def to_dict(self):
        return {
            'load': self.load.to_dict() if self.load else None,
            'payment': self.payment.to_dict() if self.payment else None,
            'deposit': self.deposit.to_dict() if self.deposit else None,
            'match_confidence': self.match_confidence,
            'match_reason': self.match_reason
        }


def parse_amount(amount_str):
    """Parse amount string like '$130.00' to Decimal"""
    if not amount_str:
        return Decimal('0.00')
    # Remove $, commas, and whitespace
    cleaned = amount_str.replace('$', '').replace(',', '').strip()
    try:
        return Decimal(cleaned)
    except:
        return Decimal('0.00')


def parse_loads_file(filepath):
    """Parse a load schedule file and extract all loads"""
    loads = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match load entries
    # Example: 10/1/2025 RPM Tulsa OKC 31594-20217 $130.00
    # Pattern: Date Company Pickup Dropoff LoadNum Amount [DatePaid] [Notes]

    lines = content.split('\n')
    for line in lines:
        # Skip page markers and headers
        if '=====' in line or 'Page' in line or 'Date Company' in line:
            continue

        # Look for lines starting with a date
        date_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{4})\s+(.+)', line)
        if date_match:
            date_str = date_match.group(1)
            rest = date_match.group(2).strip()

            # Split the rest of the line
            parts = rest.split()
            if len(parts) < 5:
                continue

            # Extract fields
            company = parts[0]

            # Find the amount (should have $ sign)
            amount_idx = None
            for i, part in enumerate(parts):
                if '$' in part:
                    amount_idx = i
                    break

            if amount_idx is None:
                continue

            amount = parse_amount(parts[amount_idx])

            # Load number is just before the amount
            if amount_idx > 0:
                load_num = parts[amount_idx - 1]
            else:
                continue

            # Pickup and dropoff are between company and load_num
            pickup_dropoff = parts[1:amount_idx-1]
            if len(pickup_dropoff) >= 2:
                pickup = pickup_dropoff[0]
                dropoff = pickup_dropoff[1]
            elif len(pickup_dropoff) == 1:
                pickup = pickup_dropoff[0]
                dropoff = ''
            else:
                pickup = ''
                dropoff = ''

            # Date paid and notes are after amount
            date_paid = None
            notes = None
            if amount_idx + 1 < len(parts):
                remaining = ' '.join(parts[amount_idx + 1:])
                notes = remaining

            load = Load(
                date=date_str,
                company=company,
                pickup=pickup,
                dropoff=dropoff,
                load_num=load_num,
                amount=amount,
                date_paid=date_paid,
                notes=notes,
                source_file=os.path.basename(filepath)
            )
            loads.append(load)

    return loads


def parse_payments_file(filepath):
    """Parse payment remittance advice file"""
    payments = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by page markers
    pages = content.split('='*80)

    current_payment = None
    payment_ref = None
    paper_doc_num = None
    payment_date = None
    payment_amount = None
    invoices = []

    for page in pages:
        lines = page.split('\n')

        for i, line in enumerate(lines):
            # Look for payment details
            if 'Payment Reference Number' in line:
                # Extract payment reference
                match = re.search(r'Payment Reference Number\s+(\d+)', line)
                if match:
                    payment_ref = match.group(1)

            if 'Paper Document Number' in line:
                match = re.search(r'Paper Document Number\s+(\d+)', line)
                if match:
                    paper_doc_num = match.group(1)

            if 'Payment Date' in line and 'Invoice' not in line:
                # Extract payment date
                match = re.search(r'Payment Date\s+(.+)', line)
                if match:
                    payment_date = match.group(1).strip()

            if 'Payment Amount' in line and 'Invoice' not in line:
                # Extract payment amount
                match = re.search(r'Payment Amount\s+([\d,\.]+)', line)
                if match:
                    payment_amount = parse_amount(match.group(1))

            # Look for invoice details
            if re.match(r'^\d{10,}', line):  # Invoice number starts the line
                # Parse invoice line
                # Example: 10334718517 Jan 2, 74.23 USD .00 74.23 JN1CF0BB7RM738879:From DENVER
                parts = line.split()
                if len(parts) >= 6:
                    invoice_num = parts[0]
                    # Find USD to locate amounts
                    try:
                        usd_idx = parts.index('USD')
                        if usd_idx >= 2:
                            invoice_date = ' '.join(parts[1:usd_idx-1])
                            invoice_amount = parse_amount(parts[usd_idx - 1])
                            amount_paid = parse_amount(parts[usd_idx + 2])
                            description = ' '.join(parts[usd_idx + 3:])

                            invoices.append({
                                'invoice_num': invoice_num,
                                'invoice_date': invoice_date,
                                'invoice_amount': float(invoice_amount),
                                'amount_paid': float(amount_paid),
                                'description': description
                            })
                    except ValueError:
                        pass

            # Check if we've completed a payment record
            if 'Total' in line and payment_ref:
                # Save the payment
                payment = Payment(
                    payment_ref=payment_ref,
                    paper_doc_num=paper_doc_num,
                    payment_date=payment_date,
                    payment_amount=payment_amount,
                    invoices=invoices.copy(),
                    source_file=os.path.basename(filepath)
                )
                payments.append(payment)

                # Reset for next payment
                payment_ref = None
                paper_doc_num = None
                payment_date = None
                payment_amount = None
                invoices = []

    return payments


def parse_deposits_file(filepath):
    """Parse bank statement file for deposits"""
    deposits = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    for line in lines:
        # Skip page markers and headers
        if '=====' in line or 'Page' in line or 'DATE DESCRIPTION' in line:
            continue

        # Look for deposit transactions
        # Pattern: Date Description Amount Balance
        # Example: Apr 01 SmartTrucker SPV, LLC | Purchase | Acertus (RN25746A) 73.12 726.33

        # Check if line starts with a date (e.g., "Apr 01")
        date_match = re.match(r'^([A-Z][a-z]{2}\s+\d{2})\s+(.+)', line)
        if date_match:
            date_str = date_match.group(1)
            rest = date_match.group(2).strip()

            # Extract load reference from description (in parentheses)
            load_ref_match = re.search(r'\(([^)]+)\)', rest)
            load_ref = load_ref_match.group(1) if load_ref_match else None

            # Extract amounts - typically last two numbers
            # Balance is last, amount is second to last
            numbers = re.findall(r'[\d,]+\.\d{2}', rest)
            if len(numbers) >= 2:
                amount = parse_amount(numbers[-2])
                balance = parse_amount(numbers[-1])

                # Description is everything except the last two numbers
                # Remove the numbers from the end
                description = rest
                for num in numbers[-2:]:
                    description = description.replace(num, '', 1)
                description = description.strip()

                deposit = Deposit(
                    date=date_str,
                    description=description,
                    amount=amount,
                    balance=balance,
                    load_ref=load_ref,
                    source_file=os.path.basename(filepath)
                )
                deposits.append(deposit)

    return deposits


def reconcile_data(loads, payments, deposits):
    """Reconcile loads, payments, and deposits"""
    reconciled = []
    unmatched_loads = []
    unmatched_payments = []
    unmatched_deposits = []

    # Create lookup dictionaries
    loads_by_num = {load.load_num: load for load in loads}
    deposits_by_ref = {dep.load_ref: dep for dep in deposits if dep.load_ref}

    # Try to match loads to deposits first
    for load in loads:
        matched_deposit = None
        match_reason = None
        confidence = None

        # Direct match by load number
        if load.load_num in deposits_by_ref:
            matched_deposit = deposits_by_ref[load.load_num]
            match_reason = f"Load # {load.load_num} matched to deposit reference"
            confidence = 'high'
        else:
            # Try partial match
            for dep_ref, deposit in deposits_by_ref.items():
                if dep_ref and load.load_num and (dep_ref in load.load_num or load.load_num in dep_ref):
                    matched_deposit = deposit
                    match_reason = f"Partial load # match: {load.load_num} ~ {dep_ref}"
                    confidence = 'medium'
                    break

        if not matched_deposit:
            # Try amount match
            for deposit in deposits:
                if abs(deposit.amount - load.amount) < Decimal('0.01'):
                    if deposit not in [r.deposit for r in reconciled]:
                        matched_deposit = deposit
                        match_reason = f"Amount match: ${load.amount}"
                        confidence = 'low'
                        break

        if matched_deposit:
            recon = Reconciliation(
                load=load,
                deposit=matched_deposit,
                match_confidence=confidence,
                match_reason=match_reason
            )
            reconciled.append(recon)
        else:
            unmatched_loads.append(load)

    # Track which deposits are already matched
    matched_deposits = {r.deposit for r in reconciled if r.deposit}

    # Add unmatched deposits
    for deposit in deposits:
        if deposit not in matched_deposits:
            unmatched_deposits.append(deposit)

    # Payments are harder to match - they contain multiple invoices
    # For now, add them to unmatched
    unmatched_payments = payments

    return reconciled, unmatched_loads, unmatched_payments, unmatched_deposits


def print_reconciliation_report(reconciled, unmatched_loads, unmatched_payments, unmatched_deposits, limit=None):
    """Print reconciliation report"""

    print("="*100)
    print("RECONCILIATION REPORT - S PROVISIONS LLC")
    print("="*100)
    print()

    # Reconciled items
    print(f"RECONCILED ITEMS ({len(reconciled)} total)")
    print("-"*100)

    display_reconciled = reconciled[:limit] if limit else reconciled

    for i, recon in enumerate(display_reconciled, 1):
        print(f"\n{i}. MATCHED TRANSACTION")
        print(f"   Match Confidence: {recon.match_confidence.upper()}")
        print(f"   Match Reason: {recon.match_reason}")

        if recon.load:
            print(f"   LOAD:")
            print(f"      Date: {recon.load.date}")
            print(f"      Company: {recon.load.company}")
            print(f"      Route: {recon.load.pickup} → {recon.load.dropoff}")
            print(f"      Load #: {recon.load.load_num}")
            print(f"      Amount: ${recon.load.amount}")
            if recon.load.notes:
                print(f"      Notes: {recon.load.notes}")
            print(f"      Source: {recon.load.source_file}")

        if recon.deposit:
            print(f"   DEPOSIT:")
            print(f"      Date: {recon.deposit.date}")
            print(f"      Description: {recon.deposit.description}")
            print(f"      Load Ref: {recon.deposit.load_ref}")
            print(f"      Amount: ${recon.deposit.amount}")
            print(f"      Balance After: ${recon.deposit.balance}")
            print(f"      Source: {recon.deposit.source_file}")

        print()

    if limit and len(reconciled) > limit:
        print(f"   ... and {len(reconciled) - limit} more reconciled items")
        print()

    print("="*100)
    print(f"UNRECONCILED ITEMS")
    print("="*100)
    print()

    # Unmatched Loads
    print(f"UNMATCHED LOADS ({len(unmatched_loads)} total)")
    print("-"*100)

    display_unmatched_loads = unmatched_loads[:limit] if limit else unmatched_loads

    for i, load in enumerate(display_unmatched_loads, 1):
        print(f"{i}. Load #{load.load_num} | {load.date} | {load.company} | {load.pickup}→{load.dropoff} | ${load.amount} | [{load.source_file}]")

    if limit and len(unmatched_loads) > limit:
        print(f"   ... and {len(unmatched_loads) - limit} more unmatched loads")
    print()

    # Unmatched Deposits
    print(f"UNMATCHED DEPOSITS ({len(unmatched_deposits)} total)")
    print("-"*100)

    display_unmatched_deposits = unmatched_deposits[:limit] if limit else unmatched_deposits

    for i, deposit in enumerate(display_unmatched_deposits, 1):
        ref_str = f"Ref: {deposit.load_ref}" if deposit.load_ref else "No Ref"
        print(f"{i}. {deposit.date} | {ref_str} | ${deposit.amount} | {deposit.description[:60]}... | [{deposit.source_file}]")

    if limit and len(unmatched_deposits) > limit:
        print(f"   ... and {len(unmatched_deposits) - limit} more unmatched deposits")
    print()

    # Unmatched Payments
    print(f"UNMATCHED PAYMENTS ({len(unmatched_payments)} total)")
    print("-"*100)

    display_unmatched_payments = unmatched_payments[:limit] if limit else unmatched_payments

    for i, payment in enumerate(display_unmatched_payments, 1):
        print(f"{i}. {payment.payment_date} | Doc #{payment.paper_doc_num} | ${payment.payment_amount} | {len(payment.invoices)} invoices | [{payment.source_file}]")
        for inv in payment.invoices[:2]:  # Show first 2 invoices
            print(f"      Invoice: {inv['invoice_num']} | ${inv['amount_paid']} | {inv['description'][:50]}...")

    if limit and len(unmatched_payments) > limit:
        print(f"   ... and {len(unmatched_payments) - limit} more unmatched payments")
    print()

    # Summary
    print("="*100)
    print("SUMMARY")
    print("="*100)
    print(f"Total Reconciled: {len(reconciled)}")
    print(f"Total Unmatched Loads: {len(unmatched_loads)}")
    print(f"Total Unmatched Deposits: {len(unmatched_deposits)}")
    print(f"Total Unmatched Payments: {len(unmatched_payments)}")
    print()


def main():
    """Main reconciliation process"""

    # Get all load schedule files
    load_files = [
        'Little Rich - \'25 Schedule (1).txt',
        'Rich - \'25 Schedule (1).txt',
        'Steve - \'25 Schedule (1).txt',
        'Tony - \'25 Schedule (1).txt',
        'March - September.txt'
    ]

    payment_files = ['Jan-Aug.txt']
    deposit_files = ['March-Oct.txt']

    all_loads = []
    all_payments = []
    all_deposits = []

    print("Parsing load schedules...")
    for filename in load_files:
        if os.path.exists(filename):
            print(f"  - {filename}")
            loads = parse_loads_file(filename)
            all_loads.extend(loads)
            print(f"    Found {len(loads)} loads")

    print(f"\nParsing payment remittances...")
    for filename in payment_files:
        if os.path.exists(filename):
            print(f"  - {filename}")
            payments = parse_payments_file(filename)
            all_payments.extend(payments)
            print(f"    Found {len(payments)} payments")

    print(f"\nParsing bank deposits...")
    for filename in deposit_files:
        if os.path.exists(filename):
            print(f"  - {filename}")
            deposits = parse_deposits_file(filename)
            all_deposits.extend(deposits)
            print(f"    Found {len(deposits)} deposits")

    print(f"\n{'='*100}")
    print(f"Total Loads: {len(all_loads)}")
    print(f"Total Payments: {len(all_payments)}")
    print(f"Total Deposits: {len(all_deposits)}")
    print(f"{'='*100}\n")

    # Reconcile
    print("Performing reconciliation...\n")
    reconciled, unmatched_loads, unmatched_payments, unmatched_deposits = reconcile_data(
        all_loads, all_payments, all_deposits
    )

    # Print report with examples (limit to 5 of each)
    print("\n" + "="*100)
    print("SHOWING EXAMPLES (First 5 of each category)")
    print("="*100 + "\n")
    print_reconciliation_report(reconciled, unmatched_loads, unmatched_payments, unmatched_deposits, limit=5)

    # Ask if user wants full report
    print("\nTo see the FULL report with all items, the script can generate a detailed report.")
    print("The full report will be saved to 'reconciliation_full_report.txt'")

    # Generate full report to file
    with open('reconciliation_full_report.txt', 'w') as f:
        import sys
        old_stdout = sys.stdout
        sys.stdout = f
        print_reconciliation_report(reconciled, unmatched_loads, unmatched_payments, unmatched_deposits, limit=None)
        sys.stdout = old_stdout

    print("\n✓ Full report saved to: reconciliation_full_report.txt")

    # Save JSON data for further analysis
    json_data = {
        'reconciled': [r.to_dict() for r in reconciled],
        'unmatched_loads': [l.to_dict() for l in unmatched_loads],
        'unmatched_deposits': [d.to_dict() for d in unmatched_deposits],
        'unmatched_payments': [p.to_dict() for p in unmatched_payments],
        'summary': {
            'total_reconciled': len(reconciled),
            'total_unmatched_loads': len(unmatched_loads),
            'total_unmatched_deposits': len(unmatched_deposits),
            'total_unmatched_payments': len(unmatched_payments)
        }
    }

    with open('reconciliation_data.json', 'w') as f:
        json.dump(json_data, f, indent=2)

    print("✓ JSON data saved to: reconciliation_data.json")


if __name__ == '__main__':
    main()
