#!/usr/bin/env python3
"""
Manual TruckSmarter data extraction helper
This script assists in manually extracting data from TruckSmarter PNG files
"""

import pandas as pd
from pathlib import Path

def create_trucksmarter_template():
    """Create a template CSV for manual TruckSmarter data entry"""

    # This will be filled in by reading the PNG files
    template_data = {
        'date': [],
        'load_number': [],
        'company': [],
        'amount': [],
        'withdrawal_date': [],
        'withdrawal_amount': [],
        'month': []
    }

    df = pd.DataFrame(template_data)
    df.to_csv('trucksmarter_manual_data.csv', index=False)
    print("Created trucksmarter_manual_data.csv template")

    instructions = """
    Instructions for filling in trucksmarter_manual_data.csv:

    1. Open each TruckSmarter PNG file
    2. For each "Purchase" line, record:
       - date: The date from the DATE column
       - load_number: The number in parentheses (e.g., RN25746A, 12620359)
       - company: The company name after "Purchase |" (e.g., Acertus, United Road Logistics)
       - amount: The amount from DEPOSITS / CREDIT column
       - month: The month (April, May, etc.)

    3. For each "S PROVISIONS LLC | Ach transfer via TruckSmarter app" line:
       - Record the withdrawal_date and withdrawal_amount
       - All purchases ABOVE this line (until the previous withdrawal) belong to this withdrawal
       - Fill in the withdrawal_date and withdrawal_amount for those purchase rows

    Example rows:
    date,load_number,company,amount,withdrawal_date,withdrawal_amount,month
    Apr 01,RN25746A,Acertus,73.12,Apr 03,4085.55,April
    Apr 01,RN27772A,Acertus,73.12,Apr 03,4085.55,April
    Apr 03,,,,Apr 03,4085.55,April
    Apr 07,RN31482A,Acertus,73.12,Apr 09,424.97,April
    """

    with open('trucksmarter_extraction_instructions.txt', 'w') as f:
        f.write(instructions)

    print("\nCreated trucksmarter_extraction_instructions.txt")
    print("\nYou can now manually fill in the CSV by viewing the PNG files")

if __name__ == "__main__":
    create_trucksmarter_template()
