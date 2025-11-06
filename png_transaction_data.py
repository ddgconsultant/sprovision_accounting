#!/usr/bin/env python3
"""
Manual PNG Transaction Data Extraction
Contains transaction data extracted from PNG bank statements
"""

from decimal import Decimal
import json


# Transaction data extracted from PNG files
# Format: (date, description, deposit, withdrawal, balance, load_ref, source_file)

PNG_TRANSACTIONS = []

# This will be populated with actual transaction data from PNGs
# Each transaction follows this structure:
# {
#     'date': 'Mar 01 2025',
#     'description': 'SmartTrucker SPV, LLC | Purchase | Acertus (RM25746A)',
#     'deposit': 73.12,
#     'withdrawal': None,
#     'balance': 726.33,
#     'load_ref': 'RM25746A',
#     'source': 'April trucksmarter-01.png'
# }


def add_transaction(date, description, deposit=None, withdrawal=None, balance=0, load_ref=None, source=''):
    """Helper to add a transaction"""
    PNG_TRANSACTIONS.append({
        'date': date,
        'description': description,
        'deposit': float(deposit) if deposit else None,
        'withdrawal': float(withdrawal) if withdrawal else None,
        'balance': float(balance),
        'load_ref': load_ref,
        'source': source
    })


def get_transactions():
    """Return all transactions"""
    return PNG_TRANSACTIONS


def save_to_json(filename='png_transactions_manual.json'):
    """Save transactions to JSON file"""
    with open(filename, 'w') as f:
        json.dump({
            'transactions': PNG_TRANSACTIONS,
            'count': len(PNG_TRANSACTIONS)
        }, f, indent=2)
    print(f"Saved {len(PNG_TRANSACTIONS)} transactions to {filename}")


if __name__ == '__main__':
    print(f"Total transactions loaded: {len(PNG_TRANSACTIONS)}")
    save_to_json()
