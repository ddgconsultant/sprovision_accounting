#!/usr/bin/env python3
"""
CORRECT Load Payment Matching System

Follows the exact instructions:
1. Parse driver schedules (Steve, Tony, Rich, Little Rich) - extract Load # column
2. For each load:
   - If Company = "Ready", find in Ready Statements CSV by Invoice Number
   - If Company != "Ready", find in TruckSmarter PNG
3. For TruckSmarter loads, group by "S PROVISIONS LLC | Ach transfer" withdrawals
4. Match S PROVISIONS LLC transfers to bank deposits to find deposit dates
5. Report missing loads and discrepancies
"""

import os
import csv
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import pytesseract
from PIL import Image

class CorrectLoadMatching:
    def __init__(self):
        self.driver_loads = []  # All loads from all driver schedules
        self.ready_invoices = {}  # invoice_number -> {amount, payment_date, etc}
        self.trucksmarter_loads = {}  # load_number -> {amount, date, etc}
        self.truck_smarter_transfers = []  # S PROVISIONS LLC transfers
        self.bank_transactions = []

    def parse_driver_schedules(self, schedules_dir):
        """Parse driver schedule CSV files - extract Load # column"""
        print("="*80)
        print("STEP 1: PARSING DRIVER SCHEDULES")
        print("="*80)

        schedules_path = Path(schedules_dir)
        csv_files = list(schedules_path.glob("*.csv"))

        print(f"Found {len(csv_files)} schedule files\n")

        for csv_file in sorted(csv_files):
            driver_name = self._extract_driver_name(csv_file.name)
            month = self._extract_month(csv_file.name)

            print(f"Processing: {csv_file.name}")
            print(f"  Driver: {driver_name}, Month: {month}")

            try:
                with open(csv_file, 'r', encoding='utf-8', errors='replace') as f:
                    # Read all lines
                    lines = f.readlines()

                    # Find the header row (contains "Load #")
                    header_idx = None
                    for i, line in enumerate(lines):
                        if 'Load #' in line:
                            header_idx = i
                            break

                    if header_idx is None:
                        print(f"  WARNING: No 'Load #' header found\n")
                        continue

                    # Parse from header onwards
                    headers = [h.strip() for h in lines[header_idx].split(',')]
                    count = 0

                    for line_idx in range(header_idx + 1, len(lines)):
                        values = [v.strip() for v in lines[line_idx].split(',')]

                        # Create row dict
                        row = {}
                        for i, header in enumerate(headers):
                            if i < len(values):
                                row[header] = values[i]
                            else:
                                row[header] = ''

                        load_num = row.get('Load #', '').strip()
                        company = row.get('Company', '').strip()
                        date = row.get('Date', '').strip()
                        amount_str = row.get('Amount', '').strip()

                        # Only process rows with a Load # (skip empty rows)
                        if load_num and load_num != '':
                            self.driver_loads.append({
                                'driver': driver_name,
                                'month': month,
                                'date': date,
                                'company': company,
                                'load_number': load_num,
                                'amount_on_schedule': amount_str,
                                'source_file': csv_file.name
                            })
                            count += 1

                    print(f"  Extracted {count} loads with Load #s\n")

            except Exception as e:
                print(f"  ERROR: {e}\n")

        print(f"TOTAL LOADS FROM ALL SCHEDULES: {len(self.driver_loads)}\n")

    def _extract_driver_name(self, filename):
        """Extract driver name from filename like 'Tony - '25 Schedule - September.csv'"""
        match = re.match(r"^([^-]+)", filename)
        if match:
            name = match.group(1).strip()
            # Normalize names
            if 'Little' in name or 'little' in name:
                return "Little Rich"
            return name
        return filename

    def _extract_month(self, filename):
        """Extract month from filename"""
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        for month in months:
            if month in filename:
                return month
        return "Unknown"

    def parse_ready_statements(self, ready_dir):
        """Parse Ready Statements CSV files - map Invoice Number to Invoice Amount"""
        print("="*80)
        print("STEP 2: PARSING READY STATEMENTS CSV")
        print("="*80)

        ready_path = Path(ready_dir)
        csv_files = list(ready_path.glob("*.csv"))

        print(f"Found {len(csv_files)} Ready Statement CSV files\n")

        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8', errors='replace') as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        invoice_num = row.get('Invoice Number', '').strip()
                        invoice_amount = row.get('Invoice Amount', '').strip()
                        payment_date = row.get('Payment Date', '').strip()
                        payment_amount = row.get('Payment Amount', '').strip()

                        if invoice_num:
                            # Clean invoice number (remove tabs)
                            invoice_num = invoice_num.replace('\t', '').strip()

                            self.ready_invoices[invoice_num] = {
                                'invoice_number': invoice_num,
                                'invoice_amount': invoice_amount,
                                'payment_date': payment_date,
                                'payment_amount': payment_amount,
                                'source_file': csv_file.name
                            }
            except Exception as e:
                print(f"ERROR parsing {csv_file.name}: {e}")

        print(f"TOTAL READY INVOICES: {len(self.ready_invoices)}\n")

    def parse_trucksmarter_pngs(self, png_base_dir):
        """Parse TruckSmarter PNG files using OCR to extract load numbers and amounts"""
        print("="*80)
        print("STEP 2.5: PARSING TRUCKSMARTER PNG FILES WITH OCR")
        print("="*80)

        png_path = Path(png_base_dir)
        month_dirs = [d for d in png_path.iterdir() if d.is_dir() and 'trucksmarter' in d.name.lower()]

        print(f"Found {len(month_dirs)} TruckSmarter month directories\n")

        current_transfer = None

        for month_dir in sorted(month_dirs):
            month_name = month_dir.name
            print(f"Processing: {month_name}")

            png_files = sorted(month_dir.glob("*.png"))
            print(f"  Found {len(png_files)} PNG files")

            for png_file in png_files:
                try:
                    # Read image and perform OCR
                    img = Image.open(png_file)
                    text = pytesseract.image_to_string(img)

                    lines = text.split('\n')

                    for line in lines:
                        # Look for S PROVISIONS LLC transfers (withdrawals)
                        if 'S PROVISIONS LLC' in line and 'Ach transfer' in line and 'TruckSmarter' in line:
                            # Extract the withdrawal amount
                            amounts = re.findall(r'(\d+(?:,\d{3})*\.\d{2})', line)
                            if amounts:
                                amount = float(amounts[0].replace(',', ''))
                                # Extract date
                                date_match = re.match(r'([A-Z][a-z]{2}\s+\d{2})', line)
                                date_str = date_match.group(1) if date_match else ""

                                self.truck_smarter_transfers.append({
                                    'amount': amount,
                                    'date': date_str,
                                    'month': month_name,
                                    'source_file': png_file.name,
                                    'loads': []  # Will be filled with loads that contribute to this transfer
                                })
                                print(f"    Found transfer: ${amount:,.2f} on {date_str}")
                                current_transfer = self.truck_smarter_transfers[-1]

                        # Look for load entries: "SmartTrucker SPV, LLC | Purchase | Acertus (LOAD#)"
                        # or "SmartTrucker SPV, LLC | Purchase | Preowned Auto Logistics (LOAD#)"
                        load_match = re.search(r'SmartTrucker\s+SPV.*?\|\s*Purchase\s*\|\s*(?:Acertus|Preowned Auto Logistics)\s*\(([^\)]+)\)', line, re.IGNORECASE)

                        if load_match:
                            load_number = load_match.group(1).strip()

                            # Extract amount (should be in DEPOSITS/CREDIT column)
                            amounts = re.findall(r'(\d+(?:,\d{3})*\.\d{2})', line)
                            if amounts:
                                # The amount is usually the last number on the line after the load number
                                amount = float(amounts[-1].replace(',', ''))

                                # Extract date
                                date_match = re.match(r'([A-Z][a-z]{2}\s+\d{2})', line)
                                date_str = date_match.group(1) if date_match else ""

                                self.trucksmarter_loads[load_number] = {
                                    'load_number': load_number,
                                    'amount': amount,
                                    'date': date_str,
                                    'month': month_name,
                                    'source_file': png_file.name
                                }

                                # If we're within a transfer group, associate this load with the current transfer
                                if current_transfer:
                                    current_transfer['loads'].append(load_number)

                except Exception as e:
                    print(f"    Error parsing {png_file.name}: {e}")

            print()

        print(f"TOTAL TRUCKSMARTER LOADS: {len(self.trucksmarter_loads)}")
        print(f"TOTAL S PROVISIONS LLC TRANSFERS: {len(self.truck_smarter_transfers)}\n")

    def parse_bank_statements(self, bank_csv):
        """Parse bank statement CSV"""
        print("="*80)
        print("STEP 3: PARSING BANK STATEMENTS")
        print("="*80)

        with open(bank_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)

            for row in reader:
                if len(row) >= 4:
                    self.bank_transactions.append({
                        'date': row[0].strip(),
                        'description': row[1].strip(),
                        'type': row[2].strip(),
                        'amount': row[3].strip()
                    })

        print(f"TOTAL BANK TRANSACTIONS: {len(self.bank_transactions)}\n")

    def match_loads_to_statements(self):
        """Match each driver load to either Ready Statements or TruckSmarter"""
        print("="*80)
        print("STEP 4: MATCHING LOADS TO STATEMENTS")
        print("="*80)

        matched = []
        missing = []

        # Group by driver for reporting
        by_driver = defaultdict(list)
        for load in self.driver_loads:
            by_driver[load['driver']].append(load)

        for driver in sorted(by_driver.keys()):
            loads = by_driver[driver]
            print(f"\n{driver}: {len(loads)} loads")
            print("-"*80)

            for load in loads:
                load_num = load['load_number']
                company = load['company']

                if company.upper() == 'READY':
                    # Check Ready Statements
                    if load_num in self.ready_invoices:
                        ready_data = self.ready_invoices[load_num]
                        matched.append({
                            **load,
                            'matched_source': 'Ready Statements',
                            'invoice_amount': ready_data['invoice_amount'],
                            'payment_date': ready_data['payment_date']
                        })
                        print(f"  ✓ {load_num} found in Ready Statements (Invoice Amount: ${ready_data['invoice_amount']})")
                    else:
                        missing.append({
                            **load,
                            'missing_from': 'Ready Statements'
                        })
                        print(f"  ✗ {load_num} NOT FOUND in Ready Statements")
                else:
                    # Check TruckSmarter (for now, mark as needing TruckSmarter data)
                    if load_num in self.trucksmarter_loads:
                        ts_data = self.trucksmarter_loads[load_num]
                        matched.append({
                            **load,
                            'matched_source': 'TruckSmarter',
                            'trucksmarter_amount': ts_data['amount']
                        })
                        print(f"  ✓ {load_num} found in TruckSmarter")
                    else:
                        missing.append({
                            **load,
                            'missing_from': 'TruckSmarter PNG'
                        })
                        print(f"  ⚠ {load_num} - Needs TruckSmarter PNG data")

        print(f"\n\nMATCH SUMMARY:")
        print(f"  Matched: {len(matched)}")
        print(f"  Missing/Needs Data: {len(missing)}\n")

        return matched, missing

    def generate_report(self, output_file='correct_load_matching_report.txt'):
        """Generate comprehensive report"""
        matched, missing = self.match_loads_to_statements()

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*100 + "\n")
            f.write("LOAD PAYMENT MATCHING REPORT (CORRECT VERSION)\n")
            f.write("="*100 + "\n\n")

            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Summary
            f.write("SUMMARY\n")
            f.write("-"*100 + "\n")
            f.write(f"Total loads in driver schedules: {len(self.driver_loads)}\n")
            f.write(f"Loads matched to Ready Statements: {len([m for m in matched if m.get('matched_source') == 'Ready Statements'])}\n")
            f.write(f"Loads matched to TruckSmarter: {len([m for m in matched if m.get('matched_source') == 'TruckSmarter'])}\n")
            f.write(f"Loads missing/needing data: {len(missing)}\n")
            f.write(f"Ready invoices in system: {len(self.ready_invoices)}\n")
            f.write(f"TruckSmarter loads in system: {len(self.trucksmarter_loads)}\n\n")

            # Missing loads by driver
            f.write("\n" + "="*100 + "\n")
            f.write("MISSING LOADS BY DRIVER\n")
            f.write("="*100 + "\n\n")

            for driver in ['Steve', 'Tony', 'Rich', 'Little Rich']:
                driver_missing = [m for m in missing if m['driver'] == driver]
                if driver_missing:
                    f.write(f"\n{driver}: {len(driver_missing)} missing loads\n")
                    f.write("-"*100 + "\n")
                    for m in driver_missing:
                        f.write(f"  Load #: {m['load_number']}\n")
                        f.write(f"    Company: {m['company']}\n")
                        f.write(f"    Date: {m['date']}\n")
                        f.write(f"    Month: {m['month']}\n")
                        f.write(f"    Missing from: {m['missing_from']}\n")
                        f.write(f"    Source file: {m['source_file']}\n\n")

            # Matched loads summary
            f.write("\n" + "="*100 + "\n")
            f.write("MATCHED LOADS SUMMARY\n")
            f.write("="*100 + "\n\n")

            for driver in ['Steve', 'Tony', 'Rich', 'Little Rich']:
                driver_matched = [m for m in matched if m['driver'] == driver]
                if driver_matched:
                    f.write(f"\n{driver}: {len(driver_matched)} matched loads\n")

            # Detailed matched loads
            f.write("\n\n" + "="*100 + "\n")
            f.write("DETAILED MATCHED LOADS\n")
            f.write("="*100 + "\n\n")

            for m in matched:
                f.write(f"Load #: {m['load_number']}\n")
                f.write(f"  Driver: {m['driver']}\n")
                f.write(f"  Company: {m['company']}\n")
                f.write(f"  Date: {m['date']}\n")
                f.write(f"  Matched in: {m['matched_source']}\n")
                if 'invoice_amount' in m:
                    f.write(f"  Invoice Amount: ${m['invoice_amount']}\n")
                    f.write(f"  Payment Date: {m['payment_date']}\n")
                f.write("\n")

        print(f"\n{'='*80}")
        print(f"REPORT GENERATED: {output_file}")
        print(f"{'='*80}\n")

        return matched, missing

def main():
    print("\n" + "="*80)
    print("CORRECT LOAD PAYMENT MATCHING SYSTEM")
    print("="*80 + "\n")

    matcher = CorrectLoadMatching()

    # Step 1: Parse driver schedules
    matcher.parse_driver_schedules('dataset_20251117/dataset_20251117__schedules')

    # Step 2: Parse Ready Statements
    matcher.parse_ready_statements('dataset_20251117/dataset_20251117__Ready Statements CSV')

    # Step 2.5: Parse TruckSmarter PNGs
    matcher.parse_trucksmarter_pngs('pdf2png')

    # Step 3: Parse bank statements
    matcher.parse_bank_statements('dataset_20251117/dataset_20251117__.csv')

    # Step 4: Match and generate report
    matched, missing = matcher.generate_report()

    # Step 5: Match transfers to bank deposits
    print("\n" + "="*80)
    print("MATCHING S PROVISIONS LLC TRANSFERS TO BANK DEPOSITS")
    print("="*80 + "\n")

    for transfer in matcher.truck_smarter_transfers:
        transfer_amt = transfer['amount']
        transfer_date = transfer['date']

        # Find matching bank deposit
        for bank_txn in matcher.bank_transactions:
            if 'S PROVISIONS LLC' in bank_txn['description'] or 'Ach transf S PROVISIONS LLC' in bank_txn['description']:
                try:
                    bank_amt = float(bank_txn['amount'])
                    if abs(bank_amt - transfer_amt) < 0.01:  # Allow small rounding differences
                        print(f"✓ Transfer ${transfer_amt:,.2f} ({transfer_date}) -> Bank deposit on {bank_txn['date']}")
                        print(f"  Includes {len(transfer['loads'])} loads")
                        break
                except ValueError:
                    pass

    print("\nNEXT STEPS:")
    print("-"*80)
    print("1. Review the generated report: correct_load_matching_report.txt")
    print("2. Check for any missing loads")
    print("3. Verify bank deposit dates match")
    print()

if __name__ == '__main__':
    main()
