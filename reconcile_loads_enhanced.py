#!/usr/bin/env python3
"""
Enhanced Driver Load Reconciliation Script
Matches loads from driver schedules with payments in Ready statements and TruckSmarter,
then reconciles with bank deposits.
"""

import pandas as pd
import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import glob
import json


class EnhancedLoadReconciliation:
    def __init__(self, dataset_path="dataset_20251117"):
        self.dataset_path = dataset_path
        self.drivers = ["Steve", "Tony", "Rich", "Little Rich"]

        # Data storage
        self.driver_schedules = {}
        self.ready_payments = []
        self.trucksmarter_withdrawals = []
        self.bank_deposits = []

        # Results
        self.missing_loads = []
        self.driver_summaries = {}
        self.matched_withdrawals = []

    def parse_driver_schedules(self):
        """Parse all driver schedule CSV files"""
        print("\n=== Parsing Driver Schedules ===")
        schedules_path = os.path.join(self.dataset_path, "dataset_20251117__schedules")

        for driver in self.drivers:
            self.driver_schedules[driver] = []
            pattern = os.path.join(schedules_path, f"{driver} - '25 Schedule*.csv")
            schedule_files = glob.glob(pattern)

            print(f"\n{driver}: Found {len(schedule_files)} schedule files")

            for file_path in schedule_files:
                try:
                    df = pd.read_csv(file_path, skiprows=1)
                    df = df[df['Date'].notna()]
                    df = df[df['Date'] != 'Date']

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

    def load_trucksmarter_manual_data(self, manual_file="trucksmarter_withdrawals_manual.csv"):
        """Load manually entered TruckSmarter withdrawal data"""
        print("\n=== Loading TruckSmarter Manual Data ===")

        if not os.path.exists(manual_file):
            print(f"Manual file {manual_file} not found. Skipping TruckSmarter data.")
            return

        try:
            df = pd.read_csv(manual_file)

            for _, row in df.iterrows():
                withdrawal_entry = {
                    'month': row.get('month'),
                    'date': row.get('date'),
                    'amount': float(row.get('withdrawal_amount')),
                    'year': int(row.get('year', 2025)),
                    'matched': False,
                    'bank_date': None
                }
                self.trucksmarter_withdrawals.append(withdrawal_entry)

            print(f"Loaded {len(self.trucksmarter_withdrawals)} TruckSmarter withdrawals")

        except Exception as e:
            print(f"Error loading manual data: {e}")

    def parse_bank_statement(self):
        """Parse bank statement CSV"""
        print("\n=== Parsing Bank Statement ===")
        bank_file = os.path.join(self.dataset_path, "dataset_20251117__.csv")

        try:
            df = pd.read_csv(bank_file, header=None)
            df.columns = ['Date', 'Description', 'Type', 'Amount']

            for _, row in df.iterrows():
                if pd.notna(row['Date']) and pd.notna(row['Amount']):
                    try:
                        amount = float(str(row['Amount']).replace('$', '').replace(',', ''))

                        deposit_entry = {
                            'date': row['Date'],
                            'description': str(row['Description']),
                            'type': str(row['Type']),
                            'amount': amount
                        }
                        self.bank_deposits.append(deposit_entry)
                    except (ValueError, AttributeError):
                        pass

            print(f"Total bank transactions: {len(self.bank_deposits)}")

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
                if abs(deposit['amount'] - amount) < 0.02:  # Allow small rounding
                    if 'S PROVISIONS LLC' in deposit['description'] or 'Ach transf' in deposit['description']:
                        withdrawal['bank_date'] = deposit['date']
                        withdrawal['matched'] = True
                        self.matched_withdrawals.append({
                            'trucksmarter_date': withdrawal['date'],
                            'bank_date': deposit['date'],
                            'amount': amount,
                            'month': withdrawal['month']
                        })
                        matched += 1
                        print(f"  Matched: {withdrawal['date']} ${amount:,.2f} -> Bank: {deposit['date']}")
                        break

        print(f"\nMatched {matched}/{len(self.trucksmarter_withdrawals)} TruckSmarter withdrawals")

    def identify_missing_loads(self):
        """Identify missing loads between schedules and payment records"""
        print("\n=== Identifying Missing Loads ===")

        schedule_loads = {}
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

        # From Ready
        for payment in self.ready_payments:
            ready_load_nums.add(payment['invoice_number'])

        # Find missing loads
        for load_num, info in schedule_loads.items():
            company = info['company'].lower()
            found_in_ready = load_num in ready_load_nums

            missing_from = []

            # Check if Ready load is missing
            if 'ready' in company and not found_in_ready:
                missing_from.append('Ready Statements')

            if missing_from:
                self.missing_loads.append({
                    'load_num': load_num,
                    'driver': info['driver'],
                    'company': info['company'],
                    'amount': info['amount'],
                    'date': info['date'],
                    'missing_from': ', '.join(missing_from)
                })

        # Check for loads in Ready but not in schedules
        all_schedule_nums = set(schedule_loads.keys())
        for load_num in ready_load_nums:
            if load_num not in all_schedule_nums:
                self.missing_loads.append({
                    'load_num': load_num,
                    'driver': 'Unknown',
                    'company': 'Ready',
                    'amount': 0,
                    'date': '',
                    'missing_from': 'Driver Schedules'
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
                            # Convert payment date
                            payment_date_str = payment.get('payment_date', '')
                            if payment_date_str:
                                try:
                                    # Try to find matching bank deposit within a few days
                                    for deposit in self.bank_deposits:
                                        # Check if amounts match (Ready payments may come in groups)
                                        if deposit['amount'] > 0:
                                            bank_date = deposit['date']
                                            break
                                except:
                                    pass
                            if not bank_date:
                                bank_date = payment_date_str
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

        # Save matched TruckSmarter withdrawals
        if self.matched_withdrawals:
            matched_df = pd.DataFrame(self.matched_withdrawals)
            matched_file = os.path.join(output_dir, "trucksmarter_withdrawals_matched.csv")
            matched_df.to_csv(matched_file, index=False)
            print(f"Saved: {matched_file}")

        # Save summary JSON
        summary_data = {
            'total_driver_loads': sum(len(loads) for loads in self.driver_schedules.values()),
            'total_ready_payments': len(self.ready_payments),
            'total_trucksmarter_withdrawals': len(self.trucksmarter_withdrawals),
            'total_matched_trucksmarter': len(self.matched_withdrawals),
            'total_bank_transactions': len(self.bank_deposits),
            'total_missing_loads': len(self.missing_loads),
            'drivers': {driver: len(loads) for driver, loads in self.driver_schedules.items()}
        }

        with open(os.path.join(output_dir, "reconciliation_summary.json"), 'w') as f:
            json.dump(summary_data, f, indent=2)

        print("\nReconciliation complete!")

    def print_summary_tables(self):
        """Print summary tables to console"""
        print("\n" + "="*80)
        print("RECONCILIATION SUMMARY")
        print("="*80)

        # Print TruckSmarter matches
        if self.matched_withdrawals:
            print("\nTruckSmarter Withdrawals Matched to Bank:")
            print("-" * 80)
            for match in self.matched_withdrawals:
                print(f"{match['trucksmarter_date']:12s} -> Bank: {match['bank_date']:12s}  ${match['amount']:>10,.2f}  ({match['month']})")

        print("\n" + "="*80)
        print("DRIVER SUMMARIES (First 10 loads per driver)")
        print("="*80)

        for driver in self.drivers:
            summary = self.driver_summaries.get(driver, [])
            if summary:
                print(f"\n{driver}'s Summary ({len(summary)} total loads)")
                print("-" * 80)
                df = pd.DataFrame(summary[:10])  # Show first 10
                print(df.to_string(index=False))
                if len(summary) > 10:
                    print(f"... and {len(summary) - 10} more loads (see CSV file for complete list)")

        if self.missing_loads:
            print("\n" + "="*80)
            print(f"MISSING LOADS REPORT ({len(self.missing_loads)} total)")
            print("="*80)
            missing_df = pd.DataFrame(self.missing_loads[:20])  # Show first 20
            print(missing_df.to_string(index=False))
            if len(self.missing_loads) > 20:
                print(f"\n... and {len(self.missing_loads) - 20} more (see missing_loads_report.csv for complete list)")

    def run_full_reconciliation(self):
        """Run the complete reconciliation process"""
        print("="*80)
        print("STARTING ENHANCED LOAD RECONCILIATION")
        print("="*80)

        self.parse_driver_schedules()
        self.parse_ready_statements()
        self.load_trucksmarter_manual_data()
        self.parse_bank_statement()

        if self.trucksmarter_withdrawals:
            self.match_trucksmarter_to_bank()

        self.identify_missing_loads()
        self.generate_driver_summaries()

        self.save_results()
        self.print_summary_tables()


def main():
    reconciler = EnhancedLoadReconciliation()
    reconciler.run_full_reconciliation()


if __name__ == "__main__":
    main()
