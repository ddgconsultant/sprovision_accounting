#!/usr/bin/env python3
"""
Load Payment Matching System

This script matches loads from driver schedules to:
1. TruckSmarter PNG statements (for non-Ready loads)
2. Ready Statements CSV (for Ready company loads)

Then matches payments to bank deposits to find deposit dates.
"""

import os
import csv
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import pytesseract
from PIL import Image

class LoadMatchingSystem:
    def __init__(self):
        self.driver_loads = defaultdict(list)  # driver -> list of loads
        self.trucksmarter_loads = {}  # load_number -> {amount, date, ...}
        self.trucksmarter_transfers = []  # List of S PROVISIONS LLC transfers
        self.ready_loads = {}  # invoice_number -> {amount, date, ...}
        self.bank_statements = []  # List of bank transactions

    def parse_driver_schedules(self, schedules_dir):
        """Parse all driver schedule CSV files to extract Load #s"""
        print("=" * 80)
        print("PARSING DRIVER SCHEDULES")
        print("=" * 80)

        schedules_path = Path(schedules_dir)

        for csv_file in sorted(schedules_path.glob("*.csv")):
            driver_name = self._extract_driver_name(csv_file.name)
            print(f"\nProcessing: {csv_file.name}")
            print(f"Driver: {driver_name}")

            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Handle files with different structures
                for row in reader:
                    load_number = row.get('Load #', '').strip()
                    company = row.get('Company', '').strip()
                    date = row.get('Date', '').strip()
                    amount = row.get('Amount', '').strip()

                    if load_number and load_number != '':
                        self.driver_loads[driver_name].append({
                            'load_number': load_number,
                            'company': company,
                            'date': date,
                            'amount': amount,
                            'driver': driver_name,
                            'source_file': csv_file.name
                        })

            print(f"  Found {len([l for l in self.driver_loads[driver_name] if csv_file.name in l['source_file']])} loads")

    def _extract_driver_name(self, filename):
        """Extract driver name from filename"""
        # E.g., "Tony - '25 Schedule - September.csv" -> "Tony"
        match = re.match(r"^([^-]+)", filename)
        if match:
            return match.group(1).strip()
        return filename

    def parse_trucksmarter_pngs(self, png_dirs):
        """Parse TruckSmarter PNG files using OCR"""
        print("\n" + "=" * 80)
        print("PARSING TRUCKSMARTER PNG FILES")
        print("=" * 80)

        base_path = Path(png_dirs)

        # Find all month directories
        month_dirs = [d for d in base_path.iterdir() if d.is_dir()]

        for month_dir in sorted(month_dirs):
            month_name = month_dir.name
            print(f"\nProcessing: {month_name}")

            png_files = sorted(month_dir.glob("*.png"))
            print(f"  Found {len(png_files)} PNG files")

            for png_file in png_files:
                print(f"  Reading: {png_file.name}")
                self._parse_single_trucksmarter_png(png_file, month_name)

    def _parse_single_trucksmarter_png(self, png_file, month_name):
        """Parse a single TruckSmarter PNG using OCR"""
        try:
            # Read image
            img = Image.open(png_file)

            # Perform OCR
            text = pytesseract.image_to_string(img)

            # Parse the text to extract loads and transfers
            lines = text.split('\n')

            for line in lines:
                # Look for load entries: "SmartTrucker SPV, LLC | Purchase | Acertus (LOAD#)" or similar
                # Pattern: contains load number in parentheses
                load_match = re.search(r'Purchase\s+\|\s+(?:Acertus|Preowned Auto Logistics)\s+\(([^\)]+)\)', line, re.IGNORECASE)
                if load_match:
                    load_number = load_match.group(1).strip()

                    # Extract amount from the line (look for decimal numbers)
                    amount_match = re.search(r'(\d+\.\d{2})\s*$', line)
                    if amount_match:
                        amount = float(amount_match.group(1))

                        # Extract date if present
                        date_match = re.match(r'([A-Z][a-z]{2}\s+\d{2})', line)
                        date_str = date_match.group(1) if date_match else ""

                        self.trucksmarter_loads[load_number] = {
                            'load_number': load_number,
                            'amount': amount,
                            'date': date_str,
                            'month': month_name,
                            'source_file': png_file.name
                        }
                        print(f"    Found load: {load_number} = ${amount}")

                # Look for S PROVISIONS LLC transfers
                transfer_match = re.search(r'S\s+PROVISIONS\s+LLC\s+\|\s+Ach\s+transfer\s+via\s+TruckSmarter\s+app', line, re.IGNORECASE)
                if transfer_match:
                    # Extract withdrawal amount
                    amount_match = re.search(r'(\d+\.\d{2})', line)
                    if amount_match:
                        amount = float(amount_match.group(1))

                        # Extract date
                        date_match = re.match(r'([A-Z][a-z]{2}\s+\d{2})', line)
                        date_str = date_match.group(1) if date_match else ""

                        self.trucksmarter_transfers.append({
                            'amount': amount,
                            'date': date_str,
                            'month': month_name,
                            'source_file': png_file.name,
                            'loads': []  # Will be filled later
                        })
                        print(f"    Found transfer: ${amount} on {date_str}")

        except Exception as e:
            print(f"    Error parsing {png_file}: {e}")

    def parse_ready_statements(self, ready_dir):
        """Parse Ready Statements CSV files"""
        print("\n" + "=" * 80)
        print("PARSING READY STATEMENTS CSV FILES")
        print("=" * 80)

        ready_path = Path(ready_dir)
        csv_files = list(ready_path.glob("*.csv"))

        print(f"Found {len(csv_files)} Ready Statement CSV files")

        for csv_file in csv_files:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    invoice_number = row.get('Invoice Number', '').strip()
                    invoice_amount = row.get('Invoice Amount', '').strip()
                    payment_date = row.get('Payment Date', '').strip()
                    payment_amount = row.get('Payment Amount', '').strip()

                    if invoice_number and invoice_number != '':
                        # Clean up invoice number (remove tabs/whitespace)
                        invoice_number = invoice_number.replace('\t', '').strip()

                        if invoice_number not in self.ready_loads:
                            self.ready_loads[invoice_number] = {
                                'invoice_number': invoice_number,
                                'invoice_amount': invoice_amount,
                                'payment_date': payment_date,
                                'payment_amount': payment_amount,
                                'source_file': csv_file.name
                            }

        print(f"Total Ready loads found: {len(self.ready_loads)}")

    def parse_bank_statements(self, bank_csv):
        """Parse bank statement CSV"""
        print("\n" + "=" * 80)
        print("PARSING BANK STATEMENTS")
        print("=" * 80)

        with open(bank_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)

            for row in reader:
                if len(row) >= 4:
                    date = row[0].strip()
                    description = row[1].strip()
                    transaction_type = row[2].strip()
                    amount = row[3].strip()

                    self.bank_statements.append({
                        'date': date,
                        'description': description,
                        'type': transaction_type,
                        'amount': amount
                    })

        print(f"Total bank transactions: {len(self.bank_statements)}")

    def match_loads(self):
        """Match driver loads to TruckSmarter or Ready statements"""
        print("\n" + "=" * 80)
        print("MATCHING DRIVER LOADS TO STATEMENTS")
        print("=" * 80)

        matched_loads = []
        missing_loads = []

        for driver, loads in self.driver_loads.items():
            print(f"\n{driver}:")

            for load in loads:
                load_number = load['load_number']
                company = load['company']

                if company.upper() == 'READY':
                    # Check Ready Statements
                    if load_number in self.ready_loads:
                        matched_loads.append({
                            **load,
                            'matched_source': 'Ready Statements',
                            'matched_data': self.ready_loads[load_number]
                        })
                        print(f"  ✓ {load_number} found in Ready Statements")
                    else:
                        missing_loads.append({
                            **load,
                            'missing_from': 'Ready Statements'
                        })
                        print(f"  ✗ {load_number} NOT FOUND in Ready Statements")
                else:
                    # Check TruckSmarter
                    if load_number in self.trucksmarter_loads:
                        matched_loads.append({
                            **load,
                            'matched_source': 'TruckSmarter',
                            'matched_data': self.trucksmarter_loads[load_number]
                        })
                        print(f"  ✓ {load_number} found in TruckSmarter")
                    else:
                        missing_loads.append({
                            **load,
                            'missing_from': 'TruckSmarter'
                        })
                        print(f"  ✗ {load_number} NOT FOUND in TruckSmarter")

        return matched_loads, missing_loads

    def match_payments_to_bank(self):
        """Match TruckSmarter transfers and Ready payments to bank deposits"""
        print("\n" + "=" * 80)
        print("MATCHING PAYMENTS TO BANK DEPOSITS")
        print("=" * 80)

        matches = []

        # Match S PROVISIONS LLC transfers
        print("\nS PROVISIONS LLC Transfers:")
        for transfer in self.trucksmarter_transfers:
            transfer_amount = transfer['amount']

            # Find matching bank deposit
            for bank_txn in self.bank_statements:
                if 'S PROVISIONS LLC' in bank_txn['description'] or 'Ach transf S PROVISIONS LLC' in bank_txn['description']:
                    try:
                        bank_amount = float(bank_txn['amount'])
                        if abs(bank_amount - transfer_amount) < 0.01:  # Allow small differences
                            print(f"  ✓ ${transfer_amount} matched to bank deposit on {bank_txn['date']}")
                            matches.append({
                                'type': 'TruckSmarter Transfer',
                                'amount': transfer_amount,
                                'bank_date': bank_txn['date'],
                                'transfer_data': transfer
                            })
                            break
                    except ValueError:
                        pass

        # Match Ready payments
        print("\nReady Payments:")
        ready_payments = defaultdict(list)
        for invoice_num, ready_load in self.ready_loads.items():
            payment_amount = ready_load['payment_amount']
            if payment_amount:
                ready_payments[payment_amount].append(ready_load)

        for payment_amount, loads in ready_payments.items():
            # Find in bank statements
            for bank_txn in self.bank_statements:
                if 'EDI PYMNTS' in bank_txn['description'] or 'READY' in bank_txn['description'].upper():
                    try:
                        bank_amount = float(bank_txn['amount'])
                        pay_amt = float(payment_amount)
                        if abs(bank_amount - pay_amt) < 0.01:
                            print(f"  ✓ ${payment_amount} matched to bank deposit on {bank_txn['date']}")
                            matches.append({
                                'type': 'Ready Payment',
                                'amount': payment_amount,
                                'bank_date': bank_txn['date'],
                                'loads': loads
                            })
                            break
                    except ValueError:
                        pass

        return matches

    def generate_report(self, output_file):
        """Generate comprehensive report"""
        matched_loads, missing_loads = self.match_loads()
        payment_matches = self.match_payments_to_bank()

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("LOAD PAYMENT MATCHING REPORT\n")
            f.write("=" * 100 + "\n\n")

            # Summary
            total_driver_loads = sum(len(loads) for loads in self.driver_loads.values())
            f.write(f"Total loads in driver schedules: {total_driver_loads}\n")
            f.write(f"Matched loads: {len(matched_loads)}\n")
            f.write(f"Missing loads: {len(missing_loads)}\n")
            f.write(f"TruckSmarter loads found: {len(self.trucksmarter_loads)}\n")
            f.write(f"Ready loads found: {len(self.ready_loads)}\n")
            f.write(f"TruckSmarter transfers: {len(self.trucksmarter_transfers)}\n")
            f.write(f"Payment matches to bank: {len(payment_matches)}\n\n")

            # Missing loads detail
            f.write("=" * 100 + "\n")
            f.write("MISSING LOADS DETAIL\n")
            f.write("=" * 100 + "\n\n")

            for driver in ['Steve', 'Tony', 'Rich', 'Little Rich']:
                driver_missing = [l for l in missing_loads if l['driver'].startswith(driver)]
                if driver_missing:
                    f.write(f"\n{driver}:\n")
                    f.write("-" * 100 + "\n")
                    for load in driver_missing:
                        f.write(f"  Load #: {load['load_number']}\n")
                        f.write(f"    Company: {load['company']}\n")
                        f.write(f"    Date: {load['date']}\n")
                        f.write(f"    Missing from: {load['missing_from']}\n")
                        f.write(f"    Source: {load['source_file']}\n\n")

            # Payment matches
            f.write("\n" + "=" * 100 + "\n")
            f.write("PAYMENT TO BANK DEPOSIT MATCHES\n")
            f.write("=" * 100 + "\n\n")

            for match in payment_matches:
                f.write(f"{match['type']}: ${match['amount']}\n")
                f.write(f"  Deposited: {match['bank_date']}\n\n")

            # Matched loads detail
            f.write("\n" + "=" * 100 + "\n")
            f.write("MATCHED LOADS DETAIL\n")
            f.write("=" * 100 + "\n\n")

            for driver in ['Steve', 'Tony', 'Rich', 'Little Rich']:
                driver_matched = [l for l in matched_loads if l['driver'].startswith(driver)]
                if driver_matched:
                    f.write(f"\n{driver}: {len(driver_matched)} matched loads\n")
                    f.write("-" * 100 + "\n")

        print(f"\n\nReport generated: {output_file}")

def main():
    system = LoadMatchingSystem()

    # Parse all data sources
    system.parse_driver_schedules('dataset_20251117/dataset_20251117__schedules')
    system.parse_trucksmarter_pngs('pdf2png')
    system.parse_ready_statements('dataset_20251117/dataset_20251117__Ready Statements CSV')
    system.parse_bank_statements('dataset_20251117/dataset_20251117__.csv')

    # Generate report
    system.generate_report('load_matching_report.txt')

if __name__ == '__main__':
    main()
