#!/usr/bin/env python3
"""
Reconciliation Engine
Matches payments, bank transactions, and driver schedules
Identifies discrepancies and generates reports
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from reconciliation_parser import (
    PaymentRemittance,
    BankTransaction,
    DriverScheduleEntry,
    ReconciliationData
)


@dataclass
class ReconciliationMatch:
    """Represents a matched set of payment, schedule, and bank transaction"""
    driver_entry: Optional[DriverScheduleEntry] = None
    payment_remittance: Optional[PaymentRemittance] = None
    bank_transaction: Optional[BankTransaction] = None
    match_type: str = "UNKNOWN"  # FULL, PARTIAL, MISSING_PAYMENT, MISSING_BANK, ORPHAN
    discrepancy: Optional[str] = None
    amount_difference: Decimal = Decimal('0')


@dataclass
class ReconciliationReport:
    """Comprehensive reconciliation report"""
    report_date: datetime = field(default_factory=datetime.now)
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None

    # Statistics
    total_remittances_received: Decimal = Decimal('0')
    total_paid_to_drivers: Decimal = Decimal('0')
    total_scheduled_amount: Decimal = Decimal('0')

    # Matches and discrepancies
    full_matches: List[ReconciliationMatch] = field(default_factory=list)
    partial_matches: List[ReconciliationMatch] = field(default_factory=list)
    missing_payments: List[DriverScheduleEntry] = field(default_factory=list)
    missing_bank_transactions: List[DriverScheduleEntry] = field(default_factory=list)
    orphan_payments: List[PaymentRemittance] = field(default_factory=list)
    orphan_bank_transactions: List[BankTransaction] = field(default_factory=list)
    amount_discrepancies: List[ReconciliationMatch] = field(default_factory=list)

    # Driver summaries
    driver_summaries: Dict[str, Dict] = field(default_factory=dict)


class ReconciliationEngine:
    """
    Engine to reconcile payments, schedules, and bank transactions
    Handles the 60+ day lag in payment processing
    """

    def __init__(self, data: ReconciliationData):
        self.data = data
        self.driver_name_map = {
            'RICH-LITTLE': 'Little Rich',
            'BIGRICH': 'Rich',
            'BIG RICH': 'Rich',
            'STEVEMARTIN': 'Steve',
            'STEVE MARTIN': 'Steve',
            'TONY': 'Tony',
        }

    def normalize_driver_name(self, name: str) -> str:
        """Normalize driver names for matching"""
        name_upper = name.upper().replace(' ', '').replace('-', '')
        for key, value in self.driver_name_map.items():
            if key.replace(' ', '').replace('-', '') == name_upper:
                return value
        return name

    def reconcile(self, lookback_days: int = 90) -> ReconciliationReport:
        """
        Perform full reconciliation
        lookback_days: How far back to look for matching payments (default 90 for 60+ day lag)
        """
        report = ReconciliationReport()

        # Sort all data by date
        self.data.payment_remittances.sort(key=lambda x: x.payment_date)
        self.data.bank_transactions.sort(key=lambda x: x.transaction_date)
        self.data.driver_schedules.sort(key=lambda x: x.date)

        # Calculate date ranges
        all_dates = []
        if self.data.payment_remittances:
            all_dates.extend([p.payment_date for p in self.data.payment_remittances])
        if self.data.bank_transactions:
            all_dates.extend([t.transaction_date for t in self.data.bank_transactions])
        if self.data.driver_schedules:
            all_dates.extend([s.date for s in self.data.driver_schedules])

        if all_dates:
            report.date_range_start = min(all_dates)
            report.date_range_end = max(all_dates)

        # Calculate totals
        report.total_remittances_received = sum(
            p.payment_amount for p in self.data.payment_remittances
        )
        report.total_paid_to_drivers = sum(
            t.amount for t in self.data.bank_transactions
        )
        report.total_scheduled_amount = sum(
            s.amount for s in self.data.driver_schedules if s.amount
        )

        # Match driver schedules with bank transactions
        matched_schedules = set()
        matched_bank_trans = set()

        for schedule_entry in self.data.driver_schedules:
            if not schedule_entry.amount:
                continue

            driver_normalized = self.normalize_driver_name(schedule_entry.driver)

            # Look for matching bank transaction
            best_match = None
            best_match_score = 0

            for i, bank_trans in enumerate(self.data.bank_transactions):
                if i in matched_bank_trans:
                    continue

                # Check if recipient matches driver
                recipient_normalized = self.normalize_driver_name(bank_trans.recipient)
                if driver_normalized != recipient_normalized:
                    continue

                # Check if amounts match
                if abs(bank_trans.amount - schedule_entry.amount) < Decimal('0.01'):
                    # Check if dates are within reasonable range
                    date_diff = abs((bank_trans.transaction_date - schedule_entry.date).days)

                    if date_diff <= lookback_days:
                        score = 100 - date_diff  # Closer dates score higher
                        if score > best_match_score:
                            best_match = i
                            best_match_score = score

            if best_match is not None:
                match = ReconciliationMatch(
                    driver_entry=schedule_entry,
                    bank_transaction=self.data.bank_transactions[best_match],
                    match_type="FULL",
                )
                report.full_matches.append(match)
                matched_schedules.add(id(schedule_entry))
                matched_bank_trans.add(best_match)
            else:
                # No matching bank transaction found
                report.missing_bank_transactions.append(schedule_entry)

        # Find orphan bank transactions
        for i, bank_trans in enumerate(self.data.bank_transactions):
            if i not in matched_bank_trans:
                report.orphan_bank_transactions.append(bank_trans)

        # Build driver summaries
        report.driver_summaries = self._build_driver_summaries(report)

        # Find orphan payment remittances (payments received but not allocated)
        # This is more complex and may require business logic
        report.orphan_payments = self._find_orphan_payments()

        return report

    def _build_driver_summaries(self, report: ReconciliationReport) -> Dict[str, Dict]:
        """Build per-driver summary statistics"""
        summaries = defaultdict(lambda: {
            'scheduled_loads': 0,
            'scheduled_amount': Decimal('0'),
            'paid_loads': 0,
            'paid_amount': Decimal('0'),
            'unpaid_loads': 0,
            'unpaid_amount': Decimal('0'),
        })

        # Count scheduled loads
        for schedule_entry in self.data.driver_schedules:
            driver = self.normalize_driver_name(schedule_entry.driver)
            summaries[driver]['scheduled_loads'] += 1
            if schedule_entry.amount:
                summaries[driver]['scheduled_amount'] += schedule_entry.amount

        # Count paid loads
        for match in report.full_matches:
            if match.driver_entry:
                driver = self.normalize_driver_name(match.driver_entry.driver)
                summaries[driver]['paid_loads'] += 1
                if match.driver_entry.amount:
                    summaries[driver]['paid_amount'] += match.driver_entry.amount

        # Count unpaid loads
        for schedule_entry in report.missing_bank_transactions:
            driver = self.normalize_driver_name(schedule_entry.driver)
            summaries[driver]['unpaid_loads'] += 1
            if schedule_entry.amount:
                summaries[driver]['unpaid_amount'] += schedule_entry.amount

        return dict(summaries)

    def _find_orphan_payments(self) -> List[PaymentRemittance]:
        """
        Find payment remittances that haven't been allocated to driver schedules
        This is complex because payments are for invoices, not individual loads
        """
        # For now, return empty list - this requires business logic to map
        # invoices to loads
        return []

    def get_driver_detail(self, driver_name: str,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Dict:
        """
        Get detailed information for a specific driver
        Useful for the PHP interface to show driver-specific reports
        """
        driver_normalized = self.normalize_driver_name(driver_name)

        # Filter schedules for this driver
        schedules = [
            s for s in self.data.driver_schedules
            if self.normalize_driver_name(s.driver) == driver_normalized
        ]

        # Apply date filters if provided
        if start_date:
            schedules = [s for s in schedules if s.date >= start_date]
        if end_date:
            schedules = [s for s in schedules if s.date <= end_date]

        # Get matching bank transactions
        bank_trans = [
            t for t in self.data.bank_transactions
            if self.normalize_driver_name(t.recipient) == driver_normalized
        ]

        if start_date:
            bank_trans = [t for t in bank_trans if t.transaction_date >= start_date]
        if end_date:
            bank_trans = [t for t in bank_trans if t.transaction_date <= end_date]

        # Calculate summary
        total_scheduled = sum(s.amount for s in schedules if s.amount)
        total_paid = sum(t.amount for t in bank_trans)

        return {
            'driver': driver_normalized,
            'date_range': {
                'start': start_date,
                'end': end_date,
            },
            'schedules': schedules,
            'bank_transactions': bank_trans,
            'summary': {
                'total_scheduled': total_scheduled,
                'total_paid': total_paid,
                'difference': total_scheduled - total_paid,
                'schedule_count': len(schedules),
                'payment_count': len(bank_trans),
            }
        }

    def find_transactions_by_date_range(self,
                                        start_date: datetime,
                                        end_date: datetime,
                                        transaction_type: str = 'all') -> Dict:
        """
        Find all transactions within a date range
        Useful for backward/forward lookup in the PHP interface
        """
        results = {
            'date_range': {'start': start_date, 'end': end_date},
            'payment_remittances': [],
            'bank_transactions': [],
            'driver_schedules': [],
        }

        if transaction_type in ('all', 'remittances'):
            results['payment_remittances'] = [
                p for p in self.data.payment_remittances
                if start_date <= p.payment_date <= end_date
            ]

        if transaction_type in ('all', 'bank'):
            results['bank_transactions'] = [
                t for t in self.data.bank_transactions
                if start_date <= t.transaction_date <= end_date
            ]

        if transaction_type in ('all', 'schedules'):
            results['driver_schedules'] = [
                s for s in self.data.driver_schedules
                if start_date <= s.date <= end_date
            ]

        return results
