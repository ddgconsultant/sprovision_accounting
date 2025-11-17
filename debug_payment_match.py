#!/usr/bin/env python3
"""
Debug Payment Matching Tool
Shows exactly what the system found when matching a load to a payment
"""

import sys
import re
import json
from pathlib import Path

def find_load_in_schedule(load_number, schedule_files):
    """Find the load in schedule files"""
    print(f"\n{'='*80}")
    print(f"SEARCHING FOR LOAD# {load_number} IN SCHEDULES")
    print(f"{'='*80}\n")

    for schedule_file in schedule_files:
        if not Path(schedule_file).exists():
            continue

        with open(schedule_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if load_number in line:
                    print(f"✓ FOUND in {schedule_file} (line {line_num}):")
                    print(f"  {line.strip()}")

                    # Try to parse the line
                    parts = line.strip().split('\t') if '\t' in line else line.strip().split()
                    if len(parts) >= 6:
                        try:
                            # Remove $ and commas from amount
                            amount_str = parts[5].replace('$', '').replace(',', '')
                            amount = float(amount_str)

                            print(f"\n  Parsed Schedule Data:")
                            print(f"    Date: {parts[0]}")
                            print(f"    Company: {parts[1]}")
                            print(f"    Pickup: {parts[2]}")
                            print(f"    Dropoff: {parts[3]}")
                            print(f"    Load #: {parts[4]}")
                            print(f"    Amount: ${amount:.2f}")

                            return {
                                'file': schedule_file,
                                'line_num': line_num,
                                'line': line.strip(),
                                'date': parts[0],
                                'company': parts[1],
                                'load_number': parts[4],
                                'amount': amount
                            }
                        except (ValueError, IndexError) as e:
                            print(f"    (Could not fully parse: {e})")

                    return {
                        'file': schedule_file,
                        'line_num': line_num,
                        'line': line.strip()
                    }

    print(f"✗ NOT FOUND in any schedule files")
    return None

def find_load_in_bank_statement(load_number, bank_files):
    """Find the load reference in bank statement files"""
    print(f"\n{'='*80}")
    print(f"SEARCHING FOR LOAD# {load_number} IN BANK STATEMENTS")
    print(f"{'='*80}\n")

    matches = []

    for bank_file in bank_files:
        if not Path(bank_file).exists():
            continue

        with open(bank_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                # Look for the load number in parentheses (how the system extracts it)
                if f"({load_number})" in line or load_number in line:
                    print(f"✓ FOUND in {bank_file} (line {line_num}):")
                    print(f"  {line.strip()}")

                    # Extract details using the same logic as the system
                    load_ref = None
                    amount = None
                    date = None
                    description = None

                    # Try to parse the line
                    # Pattern: "Apr 01 SmartTrucker SPV, LLC | Purchase | Acertus (RN25746A) 73.12 726.33"
                    date_match = re.match(r'^([A-Za-z]{3}\s+\d{2})\s+(.+)', line)
                    if date_match:
                        date = date_match.group(1)
                        rest = date_match.group(2)

                        # Extract load reference from parentheses
                        load_ref_match = re.search(r'\(([^)]+)\)', rest)
                        if load_ref_match:
                            load_ref = load_ref_match.group(1)

                        # Extract description (everything before the last two numbers)
                        desc_match = re.search(r'^(.+?)\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s*$', rest)
                        if desc_match:
                            description = desc_match.group(1).strip()

                        # Extract amount (second to last number)
                        numbers = re.findall(r'[\d,]+\.\d{2}', rest)
                        if len(numbers) >= 2:
                            amount_str = numbers[-2].replace(',', '')
                            amount = float(amount_str)

                    print(f"\n  What the System Extracted:")
                    print(f"    Date Paid: {date or 'NOT FOUND'}")
                    print(f"    Description: {description or line.strip()}")
                    print(f"    Load Ref: {load_ref or 'NOT FOUND'} {'✓ MATCHES' if load_ref == load_number else '✗ PARTIAL MATCH' if load_ref and load_number in load_ref else '✗ NO MATCH'}")
                    print(f"    Amount Paid: ${amount:.2f}" if amount else "    Amount: NOT FOUND")

                    matches.append({
                        'file': bank_file,
                        'line_num': line_num,
                        'line': line.strip(),
                        'date': date,
                        'description': description,
                        'load_ref': load_ref,
                        'amount': amount
                    })

    if not matches:
        print(f"✗ NOT FOUND in any bank statement files")

    return matches

def check_reconciliation_json(load_number):
    """Check what's in the reconciliation JSON output"""
    json_file = Path('/home/user/sprovision_accounting/reconciliation_data.json')

    if not json_file.exists():
        return None

    print(f"\n{'='*80}")
    print(f"CHECKING RECONCILIATION OUTPUT")
    print(f"{'='*80}\n")

    with open(json_file, 'r') as f:
        data = json.load(f)

    # Look through matched transactions
    if 'matched_transactions' in data:
        for match in data['matched_transactions']:
            if match.get('load', {}).get('load_num') == load_number:
                print(f"✓ FOUND in reconciliation_data.json:")
                print(f"\n  Load Info:")
                print(f"    Date: {match['load'].get('date')}")
                print(f"    Company: {match['load'].get('company')}")
                print(f"    Load #: {match['load'].get('load_num')}")
                print(f"    Expected Amount: ${match['load'].get('amount'):.2f}")
                print(f"    Date Paid: {match['load'].get('date_paid') or 'NULL ✗'}")

                if 'deposit' in match:
                    print(f"\n  Bank Deposit Info:")
                    print(f"    Date: {match['deposit'].get('date')}")
                    print(f"    Description: {match['deposit'].get('description')}")
                    print(f"    Amount Paid: ${match['deposit'].get('amount'):.2f}")
                    print(f"    Load Ref: {match['deposit'].get('load_ref')}")

                    # Calculate difference
                    expected = match['load'].get('amount', 0)
                    actual = match['deposit'].get('amount', 0)
                    diff = actual - expected

                    print(f"\n  Match Details:")
                    print(f"    Confidence: {match.get('match_confidence', 'unknown').upper()}")
                    print(f"    Reason: {match.get('match_reason')}")

                    if abs(diff) > 0.01:
                        print(f"\n  ⚠️  AMOUNT MISMATCH:")
                        print(f"    Expected: ${expected:.2f}")
                        print(f"    Actually Paid: ${actual:.2f}")
                        print(f"    Difference: ${diff:.2f} ({'OVERPAID' if diff > 0 else 'UNDERPAID'})")

                return match

    print(f"✗ NOT FOUND in reconciliation output")
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_payment_match.py <load_number>")
        print("Example: python debug_payment_match.py RP31500A")
        sys.exit(1)

    load_number = sys.argv[1].strip().upper()

    print(f"\n{'#'*80}")
    print(f"# PAYMENT MATCH DEBUGGER FOR LOAD# {load_number}")
    print(f"{'#'*80}")

    # Define file locations
    schedule_files = [
        '/home/user/sprovision_accounting/Tony - \'25 Schedule (1).txt',
        '/home/user/sprovision_accounting/Steve - \'25 Schedule (1).txt',
        '/home/user/sprovision_accounting/Rich - \'25 Schedule (1).txt',
        '/home/user/sprovision_accounting/Little Rich - \'25 Schedule (1).txt',
    ]

    bank_files = [
        '/home/user/sprovision_accounting/March-Oct.txt',
        '/home/user/sprovision_accounting/March - September.txt',
        '/home/user/sprovision_accounting/Jan-Aug.txt',
    ]

    # Search for the load
    schedule_info = find_load_in_schedule(load_number, schedule_files)
    bank_matches = find_load_in_bank_statement(load_number, bank_files)
    recon_match = check_reconciliation_json(load_number)

    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY FOR LOAD# {load_number}")
    print(f"{'='*80}\n")

    if schedule_info and bank_matches:
        schedule_amount = schedule_info.get('amount')
        bank_amount = bank_matches[0].get('amount')
        bank_date = bank_matches[0].get('date')

        print(f"Status: ✓ MATCHED")
        print(f"\nSchedule says:")
        print(f"  Company: {schedule_info.get('company')} (shows as '{bank_matches[0].get('description', '').split('|')[-1].split('(')[0].strip()}' in bank)")
        print(f"  Expected amount: ${schedule_amount:.2f}" if schedule_amount else "  Expected amount: Unknown")

        print(f"\nBank statement says:")
        print(f"  Date paid: {bank_date}")
        print(f"  Actually paid: ${bank_amount:.2f}" if bank_amount else "  Actually paid: Unknown")

        if schedule_amount and bank_amount:
            diff = bank_amount - schedule_amount
            if abs(diff) > 0.01:
                print(f"\n⚠️  DISCREPANCY: ${abs(diff):.2f} {'overpaid' if diff > 0 else 'underpaid'}")
            else:
                print(f"\n✓ Amounts match")

    elif schedule_info and not bank_matches:
        print(f"Status: ✗ UNPAID")
        print(f"  Found in schedule but NO bank deposit found")

    elif not schedule_info and bank_matches:
        print(f"Status: ⚠️  ORPHAN PAYMENT")
        print(f"  Found in bank statement but NOT in any schedule")

    else:
        print(f"Status: ✗ NOT FOUND")
        print(f"  Not found in schedules or bank statements")

    print(f"\n{'#'*80}\n")

if __name__ == '__main__':
    main()
