#!/usr/bin/env python3
"""
Driver Load Reconciliation Script
Reconciles driver loads across TruckSmarter statements, Ready CSV files, and bank statements
"""

import pandas as pd
import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import glob
import json

# Try to import OCR libraries
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: OCR libraries not available. Install Pillow and pytesseract for PNG processing")


class LoadReconciliation:
    def __init__(self, dataset_path="dataset_20251117"):
        self.dataset_path = dataset_path
        self.drivers = ["Steve", "Tony", "Rich", "Little Rich"]

        # Data storage
        self.driver_schedules = {}  # {driver: [{load_num, company, amount, date_paid, ...}]}
        self.ready_payments = []  # [{invoice_number, invoice_amount, payment_date, ...}]
        self.trucksmarter_loads = []  # [{load_num, amount, date, company}]
        self.trucksmarter_withdrawals = []  # [{date, amount, loads: []}]
        self.bank_deposits = []  # [{date, amount, description}]

        # Results
        self.missing_loads = []
        self.driver_summaries = {}

    def parse_driver_schedules(self):
        """Parse all driver schedule CSV files"""
        print("\n=== Parsing Driver Schedules ===")
        schedules_path = os.path.join(self.dataset_path, "dataset_20251117__schedules")

        for driver in self.drivers:
            self.driver_schedules[driver] = []

            # Find all schedule files for this driver
            pattern = os.path.join(schedules_path, f"{driver} - '25 Schedule*.csv")
            schedule_files = glob.glob(pattern)

            print(f"\n{driver}: Found {len(schedule_files)} schedule files")

            for file_path in schedule_files:
                try:
                    # Skip the first row (month header) and use the second row as headers
                    df = pd.read_csv(file_path, skiprows=1)

                    # Filter out any remaining header-like rows
                    df = df[df['Date'].notna()]
                    df = df[df['Date'] != 'Date']  # Remove repeated header rows

                    for _, row in df.iterrows():
                        if pd.notna(row.get('Load #')):
                            load_entry = {
                                'driver': driver,
                                'date': row.get('Date'),
                                'company': str(row.get('Company', '')).strip(),
                                'load_num': str(row.get('Load #', '')).strip(),
                                'amount': self._parse_amount(row.get('Amount')),
                                'date_paid': row.get('Date Paid'),
                                'pickup': row.get('Pick-Up'),
                                'dropoff': row.get('Drop-off'),
                                'notes': row.get('Notes', ''),
                                'source_file': os.path.basename(file_path)
                            }
                            self.driver_schedules[driver].append(load_entry)

                except Exception as e:
                    print(f"  Error parsing {file_path}: {e}")

            print(f"  Total loads for {driver}: {len(self.driver_schedules[driver])}")

    def parse_ready_statements(self):
        """Parse all Ready Statements CSV files"""
        print("\n=== Parsing Ready Statements ===")
        ready_path = os.path.join(self.dataset_path, "dataset_20251117__Ready Statements CSV")

        csv_files = glob.glob(os.path.join(ready_path, "*.csv"))
        print(f"Found {len(csv_files)} Ready statement files")

        for file_path in csv_files:
            try:
                df = pd.read_csv(file_path)

                for _, row in df.iterrows():
                    if pd.notna(row.get('Invoice Number')):
                        invoice_num = str(row.get('Invoice Number', '')).strip()

                        # Skip empty or header rows
                        if invoice_num and invoice_num != 'Invoice Number':
                            payment_entry = {
                                'invoice_number': invoice_num,
                                'invoice_amount': self._parse_amount(row.get('Invoice Amount')),
                                'payment_amount': self._parse_amount(row.get('Payment Amount')),
                                'payment_date': row.get('Payment Date'),
                                'invoice_date': row.get('Invoice Date'),
                                'invoice_description': row.get('Invoice Description'),
                                'vin': row.get('VIN'),
                                'source_file': os.path.basename(file_path)
                            }
                            self.ready_payments.append(payment_entry)

            except Exception as e:
                print(f"  Error parsing {file_path}: {e}")

        print(f"Total Ready payments: {len(self.ready_payments)}")

    def parse_trucksmarter_pngs(self):
        """Parse TruckSmarter PNG files using OCR"""
        print("\n=== Parsing TruckSmarter PNGs ===")

        if not OCR_AVAILABLE:
            print("OCR not available. Skipping TruckSmarter PNG processing.")
            print("To enable: pip install Pillow pytesseract")
            print("Also ensure tesseract is installed: apt-get install tesseract-ocr")
            return

        png_folders = glob.glob("pdf2png/*trucksmarter")
        print(f"Found {len(png_folders)} TruckSmarter folders")

        for folder in png_folders:
            month = os.path.basename(folder).replace(" trucksmarter", "")
            print(f"\nProcessing {month}...")

            png_files = sorted(glob.glob(os.path.join(folder, "*.png")))

            for png_file in png_files:
                try:
                    self._process_trucksmarter_png(png_file, month)
                except Exception as e:
                    print(f"  Error processing {png_file}: {e}")

        print(f"\nTotal TruckSmarter loads extracted: {len(self.trucksmarter_loads)}")
        print(f"Total TruckSmarter withdrawals: {len(self.trucksmarter_withdrawals)}")

    def _process_trucksmarter_png(self, png_file, month):
        """Extract data from a single TruckSmarter PNG using OCR"""
        image = Image.open(png_file)
        text = pytesseract.image_to_string(image)

        lines = text.split('\n')
        current_withdrawal = None
        current_loads = []

        for line in lines:
            line = line.strip()

            # Look for withdrawal lines
            if 'S PROVISIONS LLC' in line and 'Ach transfer via TruckSmarter app' in line:
                # Save previous withdrawal if exists
                if current_withdrawal and current_loads:
                    current_withdrawal['loads'] = current_loads.copy()
                    self.trucksmarter_withdrawals.append(current_withdrawal)

                # Extract amount and date
                amount_match = re.search(r'([\d,]+\.\d{2})', line)
                date_match = re.search(r'(Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', line)

                if amount_match and date_match:
                    current_withdrawal = {
                        'date': f"{date_match.group(1)} {date_match.group(2)}",
                        'amount': float(amount_match.group(1).replace(',', '')),
                        'loads': []
                    }
                    current_loads = []

            # Look for load lines (Purchase entries)
            elif 'Purchase' in line:
                # Extract load number and amount
                load_match = re.search(r'\(([A-Z0-9-]+)\)', line)
                amount_match = re.search(r'([\d,]+\.\d{2})', line)
                date_match = re.search(r'(Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', line)
                company_match = re.search(r'Purchase \| ([A-Za-z\s&]+)', line)

                if load_match and amount_match:
                    load_entry = {
                        'load_num': load_match.group(1),
                        'amount': float(amount_match.group(1).replace(',', '')),
                        'date': f"{date_match.group(1)} {date_match.group(2)}" if date_match else month,
                        'company': company_match.group(1).strip() if company_match else 'Unknown',
                        'source_file': os.path.basename(png_file)
                    }
                    self.trucksmarter_loads.append(load_entry)
                    current_loads.append(load_entry)

        # Save last withdrawal
        if current_withdrawal and current_loads:
            current_withdrawal['loads'] = current_loads
            self.trucksmarter_withdrawals.append(current_withdrawal)

    def parse_bank_statement(self):
        """Parse bank statement CSV"""
        print("\n=== Parsing Bank Statement ===")
        bank_file = os.path.join(self.dataset_path, "dataset_20251117__.csv")

        try:
            # Read without header to see the structure
            df = pd.read_csv(bank_file, header=None)

            # Assume columns are: Date, Description, Type, Amount
            df.columns = ['Date', 'Description', 'Type', 'Amount']

            for _, row in df.iterrows():
                if pd.notna(row['Date']) and pd.notna(row['Amount']):
                    try:
                        amount = float(str(row['Amount']).replace('$', '').replace(',', ''))

                        # Only track deposits (positive amounts)
                        if amount > 0:
                            deposit_entry = {
                                'date': row['Date'],
                                'description': str(row['Description']),
                                'type': str(row['Type']),
                                'amount': amount
                            }
                            self.bank_deposits.append(deposit_entry)
                    except (ValueError, AttributeError):
                        pass

            print(f"Total bank deposits: {len(self.bank_deposits)}")

        except Exception as e:
            print(f"Error parsing bank statement: {e}")

    def match_trucksmarter_to_bank(self):
        """Match TruckSmarter withdrawals to bank deposits"""
        print("\n=== Matching TruckSmarter Withdrawals to Bank Deposits ===")

        matched = 0
        for withdrawal in self.trucksmarter_withdrawals:
            amount = withdrawal['amount']

            # Look for matching deposit in bank statement
            for deposit in self.bank_deposits:
                if abs(deposit['amount'] - amount) < 0.01:  # Allow for rounding
                    if 'S PROVISIONS LLC' in deposit['description'] or 'Ach transf' in deposit['description']:
                        withdrawal['bank_date'] = deposit['date']
                        withdrawal['matched'] = True
                        matched += 1
                        break

        print(f"Matched {matched}/{len(self.trucksmarter_withdrawals)} TruckSmarter withdrawals")

    def match_ready_to_bank(self):
        """Match Ready payments to bank deposits"""
        print("\n=== Matching Ready Payments to Bank Deposits ===")

        # Group Ready payments by payment date and amount
        ready_by_payment = defaultdict(list)

        for payment in self.ready_payments:
            if payment['payment_amount'] > 0:
                key = (payment['payment_date'], payment['payment_amount'])
                ready_by_payment[key].append(payment)

        # Match to bank deposits
        matched = 0
        for deposit in self.bank_deposits:
            # Look for Ready-related deposits (usually come as larger grouped payments)
            for (payment_date, payment_amount), payments in ready_by_payment.items():
                if abs(deposit['amount'] - payment_amount) < 0.01:
                    for payment in payments:
                        payment['bank_date'] = deposit['date']
                        payment['matched'] = True
                    matched += len(payments)

        print(f"Matched approximately {matched} Ready payments")

    def identify_missing_loads(self):
        """Identify missing loads between schedules and payment records"""
        print("\n=== Identifying Missing Loads ===")

        # Collect all load numbers from different sources
        schedule_loads = {}  # {load_num: {driver, company, amount, ...}}
        trucksmarter_load_nums = set()
        ready_load_nums = set()

        # From schedules
        for driver, loads in self.driver_schedules.items():
            for load in loads:
                load_num = load['load_num']
                schedule_loads[load_num] = {
                    'driver': driver,
                    'company': load['company'],
                    'amount': load['amount'],
                    'date': load['date'],
                    'date_paid': load['date_paid']
                }

        # From TruckSmarter
        for load in self.trucksmarter_loads:
            trucksmarter_load_nums.add(load['load_num'])

        # From Ready
        for payment in self.ready_payments:
            ready_load_nums.add(payment['invoice_number'])

        # Find missing loads
        for load_num, info in schedule_loads.items():
            company = info['company'].lower()
            found_in_trucksmarter = load_num in trucksmarter_load_nums
            found_in_ready = load_num in ready_load_nums

            missing_from = []

            # Check if it should be in Ready
            if 'ready' in company:
                if not found_in_ready:
                    missing_from.append('Ready Statements')
            else:
                # Should be in TruckSmarter
                if not found_in_trucksmarter:
                    missing_from.append('TruckSmarter')

            if missing_from:
                self.missing_loads.append({
                    'load_num': load_num,
                    'driver': info['driver'],
                    'company': info['company'],
                    'amount': info['amount'],
                    'date': info['date'],
                    'missing_from': ', '.join(missing_from),
                    'found_in_schedule': True
                })

        # Also check for loads in payment systems not in schedules
        all_schedule_nums = set(schedule_loads.keys())

        for load_num in trucksmarter_load_nums:
            if load_num not in all_schedule_nums:
                self.missing_loads.append({
                    'load_num': load_num,
                    'driver': 'Unknown',
                    'company': 'TruckSmarter',
                    'amount': 0,
                    'date': '',
                    'missing_from': 'Driver Schedules',
                    'found_in_trucksmarter': True
                })

        for load_num in ready_load_nums:
            if load_num not in all_schedule_nums:
                self.missing_loads.append({
                    'load_num': load_num,
                    'driver': 'Unknown',
                    'company': 'Ready',
                    'amount': 0,
                    'date': '',
                    'missing_from': 'Driver Schedules',
                    'found_in_ready': True
                })

        print(f"Total missing/mismatched loads: {len(self.missing_loads)}")

    def generate_driver_summaries(self):
        """Generate summary tables for each driver"""
        print("\n=== Generating Driver Summaries ===")

        for driver in self.drivers:
            summary = []

            loads = self.driver_schedules.get(driver, [])

            for load in loads:
                load_num = load['load_num']
                company = load['company'].lower()

                # Find payment information
                bank_date = None
                amount_paid = load['amount']

                # Check if it's a Ready load
                if 'ready' in company:
                    for payment in self.ready_payments:
                        if payment['invoice_number'] == load_num:
                            amount_paid = payment['invoice_amount']
                            bank_date = payment.get('bank_date') or payment.get('payment_date')
                            break
                else:
                    # Check TruckSmarter
                    for ts_load in self.trucksmarter_loads:
                        if ts_load['load_num'] == load_num:
                            # Find which withdrawal this belongs to
                            for withdrawal in self.trucksmarter_withdrawals:
                                if any(l['load_num'] == load_num for l in withdrawal.get('loads', [])):
                                    bank_date = withdrawal.get('bank_date')
                                    break
                            break

                # Use date_paid from schedule if no bank date found
                if not bank_date:
                    bank_date = load.get('date_paid', '')

                summary.append({
                    'Load #': load_num,
                    'Company': load['company'],
                    'Amount Paid': f"${amount_paid:.2f}" if amount_paid else '',
                    'Date Paid': bank_date or 'Not Found'
                })

            self.driver_summaries[driver] = summary
            print(f"{driver}: {len(summary)} loads")

    def _parse_amount(self, amount_str):
        """Parse amount from string to float"""
        if pd.isna(amount_str):
            return 0.0

        try:
            # Remove $ and , then convert
            cleaned = str(amount_str).replace('$', '').replace(',', '').strip()
            return float(cleaned) if cleaned else 0.0
        except (ValueError, AttributeError):
            return 0.0

    def save_results(self, output_dir="reconciliation_results"):
        """Save all results to files"""
        print(f"\n=== Saving Results to {output_dir} ===")

        os.makedirs(output_dir, exist_ok=True)

        # Save missing loads report
        if self.missing_loads:
            missing_df = pd.DataFrame(self.missing_loads)
            missing_file = os.path.join(output_dir, "missing_loads_report.csv")
            missing_df.to_csv(missing_file, index=False)
            print(f"Saved: {missing_file}")

        # Save driver summaries
        for driver, summary in self.driver_summaries.items():
            if summary:
                summary_df = pd.DataFrame(summary)
                filename = f"{driver.replace(' ', '_')}_summary.csv"
                summary_file = os.path.join(output_dir, filename)
                summary_df.to_csv(summary_file, index=False)
                print(f"Saved: {summary_file}")

        # Save raw data for reference
        raw_data = {
            'total_driver_loads': sum(len(loads) for loads in self.driver_schedules.values()),
            'total_ready_payments': len(self.ready_payments),
            'total_trucksmarter_loads': len(self.trucksmarter_loads),
            'total_trucksmarter_withdrawals': len(self.trucksmarter_withdrawals),
            'total_bank_deposits': len(self.bank_deposits),
            'total_missing_loads': len(self.missing_loads)
        }

        with open(os.path.join(output_dir, "reconciliation_summary.json"), 'w') as f:
            json.dump(raw_data, f, indent=2)

        print("\nReconciliation complete!")

    def print_summary_tables(self):
        """Print summary tables to console"""
        print("\n" + "="*80)
        print("DRIVER SUMMARIES")
        print("="*80)

        for driver in self.drivers:
            summary = self.driver_summaries.get(driver, [])
            if summary:
                print(f"\n{driver}'s Summary")
                print("-" * 60)
                df = pd.DataFrame(summary)
                print(df.to_string(index=False))

        if self.missing_loads:
            print("\n" + "="*80)
            print("MISSING LOADS REPORT")
            print("="*80)
            missing_df = pd.DataFrame(self.missing_loads)
            print(missing_df.to_string(index=False))

    def run_full_reconciliation(self, skip_trucksmarter_pngs=False):
        """Run the complete reconciliation process"""
        print("="*80)
        print("STARTING LOAD RECONCILIATION")
        print("="*80)

        self.parse_driver_schedules()
        self.parse_ready_statements()

        if not skip_trucksmarter_pngs:
            self.parse_trucksmarter_pngs()
        else:
            print("\n=== Skipping TruckSmarter PNG Processing ===")
            print("TruckSmarter data will need to be added manually")

        self.parse_bank_statement()

        if self.trucksmarter_withdrawals:
            self.match_trucksmarter_to_bank()

        self.match_ready_to_bank()

        self.identify_missing_loads()
        self.generate_driver_summaries()

        self.save_results()
        self.print_summary_tables()


def main():
    reconciler = LoadReconciliation()
    # Skip TruckSmarter PNG processing if OCR is not available
    reconciler.run_full_reconciliation(skip_trucksmarter_pngs=(not OCR_AVAILABLE))


if __name__ == "__main__":
    main()
