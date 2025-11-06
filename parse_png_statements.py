#!/usr/bin/env python3
"""
PNG Bank Statement Parser for S Provisions LLC
Extracts transaction data directly from PNG images of bank statements
Uses OCR to parse Thread Bank statements
"""

import re
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional
import json

try:
    from PIL import Image
    import pytesseract
except ImportError:
    print("Installing required packages: pillow and pytesseract...")
    import subprocess
    subprocess.check_call(['pip', 'install', '-q', 'pillow', 'pytesseract'])
    from PIL import Image
    import pytesseract


class BankTransaction:
    """Represents a bank transaction from statement"""
    def __init__(self, date, description, withdrawal, deposit, balance, load_ref=None):
        self.date = date
        self.description = description
        self.withdrawal = withdrawal  # Decimal or None
        self.deposit = deposit  # Decimal or None
        self.balance = balance  # Decimal
        self.load_ref = load_ref  # Extracted load reference (RM25746A, 82401425, etc.)

    def __repr__(self):
        amt = self.deposit if self.deposit else f"-{self.withdrawal}"
        ref = f" [{self.load_ref}]" if self.load_ref else ""
        return f"Transaction({self.date}, ${amt}, {ref})"

    def to_dict(self):
        return {
            'date': self.date,
            'description': self.description,
            'withdrawal': float(self.withdrawal) if self.withdrawal else None,
            'deposit': float(self.deposit) if self.deposit else None,
            'balance': float(self.balance),
            'load_ref': self.load_ref
        }


class PNGStatementParser:
    """Parser for PNG bank statement images"""

    def __init__(self):
        self.transactions = []
        self.statement_period = None

    def parse_png_file(self, png_path: str) -> List[BankTransaction]:
        """Parse a single PNG file and extract transactions"""
        print(f"  Processing: {os.path.basename(png_path)}")

        try:
            # Open image and run OCR
            image = Image.open(png_path)

            # Use pytesseract to extract text
            text = pytesseract.image_to_string(image, config='--psm 6')

            # Parse the extracted text
            transactions = self._parse_text(text, png_path)

            return transactions

        except Exception as e:
            print(f"    Error processing {png_path}: {e}")
            return []

    def _parse_text(self, text: str, source_file: str) -> List[BankTransaction]:
        """Parse OCR text and extract transactions"""
        transactions = []
        lines = text.split('\n')

        # Track statement period for date parsing
        statement_year = None
        statement_month = None

        for line in lines:
            # Extract statement period
            if 'Statement Period' in line:
                # Pattern: "Mar 01 2025 - Mar 31 2025"
                period_match = re.search(r'([A-Z][a-z]{2})\s+\d+\s+(\d{4})', line)
                if period_match:
                    statement_month = period_match.group(1)
                    statement_year = int(period_match.group(2))

            # Skip headers and non-transaction lines
            if any(skip in line for skip in ['DATE', 'DESCRIPTION', 'WITHDRAWALS', 'DEPOSITS', 'BALANCE',
                                              'Opening Balance', 'S PROVISIONS LLC', 'Thread Bank',
                                              'Statement Period', 'Account']):
                continue

            # Look for transaction lines - they start with a date (e.g., "Mar 01", "Apr 01", "May 01")
            date_match = re.match(r'^([A-Z][a-z]{2})\s+(\d{2})\s+(.+)', line)
            if date_match and statement_year:
                month_str = date_match.group(1)
                day = date_match.group(2)
                rest = date_match.group(3).strip()

                # Parse the rest of the line
                # Format: DESCRIPTION [WITHDRAWAL] [DEPOSIT] BALANCE
                # Numbers are at the end, description is at the beginning

                # Extract all numbers from the line
                numbers = re.findall(r'[\d,]+\.\d{2}', rest)

                if len(numbers) == 0:
                    continue

                # Description is everything before the numbers
                # Find the position of the first number
                first_num_pos = rest.find(numbers[0])
                description = rest[:first_num_pos].strip()

                # Extract load reference from description
                load_ref = self._extract_load_ref(description)

                # Parse amounts
                # Last number is always balance
                # If 2 numbers: [amount, balance] where amount is either withdrawal or deposit
                # If 3 numbers: [withdrawal, deposit, balance]

                balance = Decimal(numbers[-1].replace(',', ''))
                withdrawal = None
                deposit = None

                if len(numbers) == 2:
                    # One amount (either withdrawal or deposit)
                    amount = Decimal(numbers[0].replace(',', ''))
                    # Determine if it's withdrawal or deposit based on description
                    if 'Ach transfer' in description or 'ACH transfer' in description:
                        withdrawal = amount
                    else:
                        deposit = amount
                elif len(numbers) >= 3:
                    # Both withdrawal and deposit present
                    withdrawal = Decimal(numbers[0].replace(',', ''))
                    deposit = Decimal(numbers[1].replace(',', ''))
                    if withdrawal == 0:
                        withdrawal = None
                    if deposit == 0:
                        deposit = None

                # Create date string
                date_str = f"{month_str} {day} {statement_year}"

                transaction = BankTransaction(
                    date=date_str,
                    description=description,
                    withdrawal=withdrawal,
                    deposit=deposit,
                    balance=balance,
                    load_ref=load_ref
                )
                transactions.append(transaction)

        return transactions

    def _extract_load_ref(self, description: str) -> Optional[str]:
        """Extract load reference from description"""
        # Pattern 1: Acertus loads with RM prefix (RM25746A, RM27772A)
        rm_match = re.search(r'\(RM\d+[A-Z]?\)', description)
        if rm_match:
            return rm_match.group(0)[1:-1]  # Remove parentheses

        # Pattern 2: Acertus loads with numeric IDs (12390535, 13046089, 13058867)
        acertus_match = re.search(r'Acertus \((\d+)\)', description)
        if acertus_match:
            return acertus_match.group(1)

        # Pattern 3: United Road Logistics loads (82401425, 82393824)
        url_match = re.search(r'United Road Logistics\s+\((\d+)\)', description)
        if url_match:
            return url_match.group(1)

        # Pattern 4: Preowned Auto Logistics loads (627908)
        pal_match = re.search(r'Preowned Auto Logistics\s+\((\d+)\)', description)
        if pal_match:
            return pal_match.group(1)

        return None


def parse_all_png_statements(png_dir: str = 'pdf2png') -> List[BankTransaction]:
    """Parse all PNG files in the directory"""
    all_transactions = []
    parser = PNGStatementParser()

    png_path = Path(png_dir)
    if not png_path.exists():
        print(f"Error: Directory {png_dir} not found")
        return []

    # Get all month directories
    month_dirs = sorted([d for d in png_path.iterdir() if d.is_dir()])

    print(f"\nFound {len(month_dirs)} month directories")
    print("="*80)

    for month_dir in month_dirs:
        print(f"\nProcessing: {month_dir.name}")
        print("-"*80)

        # Get all PNG files in this month
        png_files = sorted(month_dir.glob('*.png'))

        for png_file in png_files:
            transactions = parser.parse_png_file(str(png_file))
            all_transactions.extend(transactions)
            print(f"    Found {len(transactions)} transactions")

    return all_transactions


def main():
    """Main function to parse PNG statements"""
    print("="*80)
    print("PNG BANK STATEMENT PARSER FOR S PROVISIONS LLC")
    print("="*80)
    print()

    # Check if tesseract is installed
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        print("ERROR: Tesseract OCR is not installed!")
        print("Please install tesseract:")
        print("  Ubuntu/Debian: sudo apt-get install tesseract-ocr")
        print("  Mac: brew install tesseract")
        print("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        return 1

    # Parse all PNG files
    all_transactions = parse_all_png_statements()

    print("\n" + "="*80)
    print("PARSING COMPLETE")
    print("="*80)
    print(f"Total transactions extracted: {len(all_transactions)}")

    # Calculate totals
    total_deposits = sum(t.deposit for t in all_transactions if t.deposit)
    total_withdrawals = sum(t.withdrawal for t in all_transactions if t.withdrawal)

    print(f"Total deposits: ${total_deposits:,.2f}")
    print(f"Total withdrawals: ${total_withdrawals:,.2f}")
    print(f"Net: ${total_deposits - total_withdrawals:,.2f}")

    # Count loads by type
    rm_loads = [t for t in all_transactions if t.load_ref and t.load_ref.startswith('RM')]
    numeric_loads = [t for t in all_transactions if t.load_ref and t.load_ref.isdigit()]

    print(f"\nLoad references found:")
    print(f"  RM-prefix loads (Acertus): {len(rm_loads)}")
    print(f"  Numeric loads (URL/PAL/Acertus): {len(numeric_loads)}")

    # Save to JSON
    output_data = {
        'transactions': [t.to_dict() for t in all_transactions],
        'summary': {
            'total_transactions': len(all_transactions),
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'net_amount': float(total_deposits - total_withdrawals),
            'rm_loads_count': len(rm_loads),
            'numeric_loads_count': len(numeric_loads)
        }
    }

    with open('png_transactions.json', 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Transaction data saved to: png_transactions.json")

    # Show sample transactions
    print("\n" + "="*80)
    print("SAMPLE TRANSACTIONS (First 10)")
    print("="*80)
    for i, trans in enumerate(all_transactions[:10], 1):
        ref = f" | Ref: {trans.load_ref}" if trans.load_ref else ""
        amt = f"${trans.deposit:,.2f}" if trans.deposit else f"-${trans.withdrawal:,.2f}"
        print(f"{i}. {trans.date} | {amt} | {trans.description[:50]}{ref}")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
