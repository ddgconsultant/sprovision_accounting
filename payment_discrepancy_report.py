#!/usr/bin/env python3
"""
Payment Discrepancy Report
Identifies loads where the amount paid doesn't match the expected amount
"""

import sys
import json
from pathlib import Path
from decimal import Decimal

# Import from reconcile_loads_payments
import reconcile_loads_payments as reconcile

def analyze_discrepancies(reconciled_matches):
    """Analyze reconciled matches for payment discrepancies"""

    discrepancies = []
    exact_matches = []

    for match in reconciled_matches:
        if not match.load or not match.deposit:
            continue

        expected = match.load.amount
        actual = match.deposit.amount
        difference = actual - expected

        # Consider anything over 1 cent a discrepancy
        if abs(difference) > Decimal('0.01'):
            discrepancies.append({
                'load': match.load,
                'deposit': match.deposit,
                'expected': expected,
                'actual': actual,
                'difference': difference,
                'percentage': (difference / expected * 100) if expected > 0 else 0,
                'match_confidence': match.match_confidence,
                'match_reason': match.match_reason
            })
        else:
            exact_matches.append(match)

    return discrepancies, exact_matches


def print_discrepancy_report(discrepancies):
    """Print formatted discrepancy report"""

    print("="*120)
    print("PAYMENT DISCREPANCY REPORT - S PROVISIONS LLC")
    print("="*120)
    print()

    if not discrepancies:
        print("✓ NO DISCREPANCIES FOUND - All payments match expected amounts!")
        print()
        return

    # Separate into underpayments and overpayments
    underpayments = [d for d in discrepancies if d['difference'] < 0]
    overpayments = [d for d in discrepancies if d['difference'] > 0]

    # Sort by absolute difference (largest first)
    underpayments.sort(key=lambda x: abs(x['difference']), reverse=True)
    overpayments.sort(key=lambda x: abs(x['difference']), reverse=True)

    total_underpaid = sum(abs(d['difference']) for d in underpayments)
    total_overpaid = sum(d['difference'] for d in overpayments)

    print(f"⚠️  FOUND {len(discrepancies)} PAYMENT DISCREPANCIES")
    print(f"   - {len(underpayments)} Underpayments (Total: ${total_underpaid:.2f} short)")
    print(f"   - {len(overpayments)} Overpayments (Total: ${total_overpaid:.2f} extra)")
    print()
    print("="*120)

    # Print underpayments
    if underpayments:
        print()
        print("🔴 UNDERPAYMENTS (You received LESS than expected)")
        print("="*120)
        print()

        for i, disc in enumerate(underpayments, 1):
            print(f"{i}. Load # {disc['load'].load_num}")
            print(f"   Date: {disc['load'].date} | Company: {disc['load'].company}")
            print(f"   Route: {disc['load'].pickup} → {disc['load'].dropoff}")
            print(f"   Expected: ${disc['expected']:.2f}")
            print(f"   Actually Paid: ${disc['actual']:.2f}")
            print(f"   🔴 SHORT BY: ${abs(disc['difference']):.2f} ({abs(disc['percentage']):.1f}% underpaid)")
            print(f"   Date Paid: {disc['deposit'].date}")
            print(f"   Bank Description: {disc['deposit'].description}")
            print(f"   Source: {disc['load'].source_file}")
            print()

    # Print overpayments
    if overpayments:
        print()
        print("🟢 OVERPAYMENTS (You received MORE than expected)")
        print("="*120)
        print()

        for i, disc in enumerate(overpayments, 1):
            print(f"{i}. Load # {disc['load'].load_num}")
            print(f"   Date: {disc['load'].date} | Company: {disc['load'].company}")
            print(f"   Route: {disc['load'].pickup} → {disc['load'].dropoff}")
            print(f"   Expected: ${disc['expected']:.2f}")
            print(f"   Actually Paid: ${disc['actual']:.2f}")
            print(f"   🟢 EXTRA: ${disc['difference']:.2f} ({disc['percentage']:.1f}% overpaid)")
            print(f"   Date Paid: {disc['deposit'].date}")
            print(f"   Bank Description: {disc['deposit'].description}")
            print(f"   Source: {disc['load'].source_file}")
            print()

    # Summary
    print("="*120)
    print("SUMMARY")
    print("="*120)
    print(f"Total Discrepancies: {len(discrepancies)}")
    print(f"Total Amount Underpaid: ${total_underpaid:.2f}")
    print(f"Total Amount Overpaid: ${total_overpaid:.2f}")
    print(f"Net Difference: ${total_overpaid - total_underpaid:.2f}")
    print()


def save_discrepancy_csv(discrepancies, filename='payment_discrepancies.csv'):
    """Save discrepancies to CSV file"""

    with open(filename, 'w') as f:
        # Header
        f.write("Load Number,Date,Company,Pickup,Dropoff,Expected,Actually Paid,Difference,Percentage,Date Paid,Bank Description,Source File\n")

        # Sort by load number
        discrepancies.sort(key=lambda x: x['load'].load_num)

        for disc in discrepancies:
            f.write(f'"{disc["load"].load_num}",')
            f.write(f'"{disc["load"].date}",')
            f.write(f'"{disc["load"].company}",')
            f.write(f'"{disc["load"].pickup}",')
            f.write(f'"{disc["load"].dropoff}",')
            f.write(f'{disc["expected"]:.2f},')
            f.write(f'{disc["actual"]:.2f},')
            f.write(f'{disc["difference"]:.2f},')
            f.write(f'{disc["percentage"]:.2f}%,')
            f.write(f'"{disc["deposit"].date}",')
            f.write(f'"{disc["deposit"].description}",')
            f.write(f'"{disc["load"].source_file}"\n')

    print(f"✓ Discrepancy data saved to: {filename}")


def save_discrepancy_json(discrepancies, filename='payment_discrepancies.json'):
    """Save discrepancies to JSON file"""

    json_data = {
        'underpayments': [],
        'overpayments': [],
        'summary': {
            'total_discrepancies': len(discrepancies),
            'total_underpaid': 0.0,
            'total_overpaid': 0.0,
            'net_difference': 0.0
        }
    }

    for disc in discrepancies:
        item = {
            'load_number': disc['load'].load_num,
            'date': disc['load'].date,
            'company': disc['load'].company,
            'pickup': disc['load'].pickup,
            'dropoff': disc['load'].dropoff,
            'expected': float(disc['expected']),
            'actually_paid': float(disc['actual']),
            'difference': float(disc['difference']),
            'percentage': float(disc['percentage']),
            'date_paid': disc['deposit'].date,
            'bank_description': disc['deposit'].description,
            'source_file': disc['load'].source_file
        }

        if disc['difference'] < 0:
            json_data['underpayments'].append(item)
            json_data['summary']['total_underpaid'] += abs(float(disc['difference']))
        else:
            json_data['overpayments'].append(item)
            json_data['summary']['total_overpaid'] += float(disc['difference'])

    json_data['summary']['net_difference'] = (
        json_data['summary']['total_overpaid'] -
        json_data['summary']['total_underpaid']
    )

    with open(filename, 'w') as f:
        json.dump(json_data, f, indent=2)

    print(f"✓ Discrepancy data saved to: {filename}")


def main():
    """Main execution"""

    print("Analyzing payment data for discrepancies...\n")

    # Run the reconciliation to get fresh data
    load_files = [
        'Little Rich - \'25 Schedule (1).txt',
        'Rich - \'25 Schedule (1).txt',
        'Steve - \'25 Schedule (1).txt',
        'Tony - \'25 Schedule (1).txt',
    ]

    deposit_files = ['March-Oct.txt']
    payment_files = ['Jan-Aug.txt']

    all_loads = []
    all_deposits = []
    all_payments = []

    # Parse files
    for filename in load_files:
        if Path(filename).exists():
            loads = reconcile.parse_loads_file(filename)
            all_loads.extend(loads)

    for filename in deposit_files:
        if Path(filename).exists():
            deposits = reconcile.parse_deposits_file(filename)
            all_deposits.extend(deposits)

    for filename in payment_files:
        if Path(filename).exists():
            payments = reconcile.parse_payments_file(filename)
            all_payments.extend(payments)

    print(f"Loaded {len(all_loads)} loads, {len(all_deposits)} deposits, {len(all_payments)} payments\n")

    # Reconcile
    reconciled, unmatched_loads, unmatched_payments, unmatched_deposits = reconcile.reconcile_data(
        all_loads, all_payments, all_deposits
    )

    print(f"Reconciled {len(reconciled)} transactions\n")

    # Analyze discrepancies
    discrepancies, exact_matches = analyze_discrepancies(reconciled)

    # Print report
    print_discrepancy_report(discrepancies)

    # Save to files
    if discrepancies:
        save_discrepancy_csv(discrepancies)
        save_discrepancy_json(discrepancies)
        print()

    print(f"✓ Analysis complete")
    print(f"  - {len(exact_matches)} loads paid exactly as expected")
    print(f"  - {len(discrepancies)} loads with payment discrepancies")
    print()


if __name__ == '__main__':
    main()
