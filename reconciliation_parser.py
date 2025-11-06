#!/usr/bin/env python3
"""
Payment Reconciliation Parser
Parses payment remittance data, bank statements, and driver schedules
"""

import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PaymentRemittance:
    """Represents a payment received from a client"""
    payment_date: datetime
    payment_reference: str
    paper_document_number: str
    payment_amount: Decimal
    invoices: List[Dict] = field(default_factory=list)
    source_file: str = ""

    def __repr__(self):
        return f"PaymentRemittance({self.payment_date.strftime('%Y-%m-%d')}, ${self.payment_amount}, {len(self.invoices)} invoices)"


@dataclass
class BankTransaction:
    """Represents a bank transaction (Zelle payment to driver)"""
    transaction_date: datetime
    amount: Decimal
    description: str
    recipient: str
    transaction_type: str
    source_file: str = ""

    def __repr__(self):
        return f"BankTransaction({self.transaction_date.strftime('%Y-%m-%d')}, {self.recipient}, ${self.amount})"


@dataclass
class DriverScheduleEntry:
    """Represents a scheduled load for a driver"""
    date: datetime
    driver: str
    company: str
    pickup: str
    dropoff: str
    load_number: str
    amount: Optional[Decimal]
    date_paid: Optional[datetime] = None
    notes: str = ""
    source_file: str = ""

    def __repr__(self):
        amt = f"${self.amount}" if self.amount else "N/A"
        return f"DriverScheduleEntry({self.driver}, {self.date.strftime('%Y-%m-%d')}, {self.company}, {amt})"


class PaymentRemittanceParser:
    """Parser for Cox Automotive payment remittance emails"""

    def parse_file(self, filepath: str) -> List[PaymentRemittance]:
        """Parse a text file containing payment remittance advice"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        payments = []
        pages = content.split('=' * 80)

        i = 0
        while i < len(pages):
            page = pages[i]

            # Look for payment advice header
            if 'Payment Remittance Advice' in page:
                payment = self._parse_payment_block(pages, i, filepath)
                if payment:
                    payments.append(payment)
            i += 1

        return payments

    def _parse_payment_block(self, pages: List[str], start_idx: int, source_file: str) -> Optional[PaymentRemittance]:
        """Parse a payment block starting at the given page index"""
        header_page = pages[start_idx] if start_idx < len(pages) else ""

        # Extract payment date
        payment_date = None
        date_match = re.search(r'Payment Date\s+([A-Za-z]+\s+\d+,\s+\d{4})', header_page)
        if date_match:
            payment_date = datetime.strptime(date_match.group(1), '%b %d, %Y')

        # Extract payment reference
        ref_match = re.search(r'Payment Reference Number\s+(\d+)', header_page)
        payment_ref = ref_match.group(1) if ref_match else ""

        # Extract paper document number
        doc_match = re.search(r'Paper Document Number\s+(\d+)', header_page)
        doc_number = doc_match.group(1) if doc_match else ""

        # Extract payment amount
        amount_match = re.search(r'Payment Amount\s+(\d+(?:,\d{3})*(?:\.\d{2})?)', header_page)
        payment_amount = Decimal(amount_match.group(1).replace(',', '')) if amount_match else Decimal('0')

        # Look for invoice details in next page
        invoices = []
        if start_idx + 1 < len(pages):
            detail_page = pages[start_idx + 1]
            invoices = self._parse_invoice_details(detail_page)

        if payment_date and payment_ref:
            return PaymentRemittance(
                payment_date=payment_date,
                payment_reference=payment_ref,
                paper_document_number=doc_number,
                payment_amount=payment_amount,
                invoices=invoices,
                source_file=source_file
            )

        return None

    def _parse_invoice_details(self, page: str) -> List[Dict]:
        """Parse invoice detail lines"""
        invoices = []

        # Look for invoice lines (pattern: invoice number, date, amounts, description with VIN)
        lines = page.split('\n')
        for line in lines:
            # Match invoice lines like: 10334718517 Jan 2, 74.23 USD .00 74.23 JN1CF0BB7RM738879:From DENVER
            match = re.search(
                r'(\d+)\s+([A-Za-z]+\s+\d+,)\s+(\d+(?:,\d{3})*(?:\.\d{2})?)\s+USD\s+(\d+(?:\.\d{2})?)\s+(\d+(?:\.\d{2})?)\s+([A-Z0-9]+):From\s+(.+)',
                line
            )
            if match:
                invoice = {
                    'invoice_number': match.group(1),
                    'invoice_date': match.group(2).strip(),
                    'invoice_amount': Decimal(match.group(3).replace(',', '')),
                    'discount': Decimal(match.group(4)),
                    'amount_paid': Decimal(match.group(5)),
                    'vin': match.group(6),
                    'location': match.group(7).strip()
                }
                invoices.append(invoice)

        return invoices


class BankStatementParser:
    """Parser for FirstBank statements"""

    def parse_file(self, filepath: str) -> List[BankTransaction]:
        """Parse a bank statement text file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        transactions = []

        # Look for Zelle transfers
        zelle_pattern = r'(\d+-\d+)\s+([\d,]+\.\d{2})\s+INTERNETTRANSFER#\d+TO([A-Z\-\(\) ]+)\(ZELLE\)'
        matches = re.finditer(zelle_pattern, content)

        for match in matches:
            date_str = match.group(1)
            amount_str = match.group(2).replace(',', '')
            recipient = match.group(3).strip()

            # Parse date - need to extract year from statement
            year_match = re.search(r'STATEMENT (\d+)-\d+-(\d{4})', content)
            year = int(year_match.group(2)) if year_match else datetime.now().year

            month, day = map(int, date_str.split('-'))
            trans_date = datetime(year, month, day)

            transaction = BankTransaction(
                transaction_date=trans_date,
                amount=Decimal(amount_str),
                description=f"Zelle to {recipient}",
                recipient=recipient,
                transaction_type="ZELLE",
                source_file=filepath
            )
            transactions.append(transaction)

        return transactions


class DriverScheduleParser:
    """Parser for driver schedule files"""

    def parse_file(self, filepath: str) -> List[DriverScheduleEntry]:
        """Parse a driver schedule text file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract driver name from filename
        import os
        filename = os.path.basename(filepath)
        driver = filename.split(' - ')[0] if ' - ' in filename else "Unknown"

        entries = []
        lines = content.split('\n')

        for line in lines:
            # Skip header lines
            if 'Date' in line and 'Company' in line and 'Pick-Up' in line:
                continue

            # Skip month headers and page markers
            if re.match(r'^([A-Z][a-z]+)$', line.strip()):
                continue
            if line.strip().startswith('Page ') or line.strip().startswith('===='):
                continue
            if not line.strip():
                continue

            # Parse schedule entry lines using regex for better accuracy
            # Pattern: Date Company Pick-Up Drop-off Load# Amount [Date Paid] [Notes]
            # Use regex to extract components more reliably
            # Require $ sign or decimal point to identify amount column
            match = re.match(
                r'(\d{1,2}/\d{1,2}/\d{4})\s+(.+?)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+\$?([\d,]+\.\d{2}))?',
                line
            )

            if match:
                try:
                    entry_date = datetime.strptime(match.group(1), '%m/%d/%Y')
                    company = match.group(2).strip()
                    pickup = match.group(3)
                    dropoff = match.group(4)
                    load_number = match.group(5)

                    # Parse amount if present (group 6 is optional)
                    amount = None
                    if match.group(6):
                        amount_str = match.group(6).replace(',', '')
                        try:
                            amount = Decimal(amount_str)
                        except:
                            amount = None

                    entry = DriverScheduleEntry(
                        date=entry_date,
                        driver=driver,
                        company=company,
                        pickup=pickup,
                        dropoff=dropoff,
                        load_number=load_number,
                        amount=amount,
                        source_file=filepath
                    )
                    entries.append(entry)

                except Exception as e:
                    # Skip malformed lines
                    continue

        return entries


class ReconciliationData:
    """Container for all parsed reconciliation data"""

    def __init__(self):
        self.payment_remittances: List[PaymentRemittance] = []
        self.bank_transactions: List[BankTransaction] = []
        self.driver_schedules: List[DriverScheduleEntry] = []

    def add_payment_remittances(self, payments: List[PaymentRemittance]):
        self.payment_remittances.extend(payments)

    def add_bank_transactions(self, transactions: List[BankTransaction]):
        self.bank_transactions.extend(transactions)

    def add_driver_schedules(self, schedules: List[DriverScheduleEntry]):
        self.driver_schedules.extend(schedules)

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        total_remittances = sum(p.payment_amount for p in self.payment_remittances)
        total_bank_payments = sum(t.amount for t in self.bank_transactions)
        total_scheduled = sum(s.amount for s in self.driver_schedules if s.amount)

        return {
            'payment_remittances_count': len(self.payment_remittances),
            'payment_remittances_total': total_remittances,
            'bank_transactions_count': len(self.bank_transactions),
            'bank_transactions_total': total_bank_payments,
            'driver_schedule_entries': len(self.driver_schedules),
            'driver_schedule_total': total_scheduled,
        }
