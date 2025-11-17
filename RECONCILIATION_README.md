# Load Reconciliation Report

## Overview
This reconciliation matches driver loads across three data sources:
1. **Driver Schedules** - Individual schedules for Steve, Tony, Rich, and Little Rich
2. **Ready Statements** - CSV files with Invoice Numbers and Payment Amounts
3. **TruckSmarter Statements** - PNG images showing load payments and withdrawals to bank
4. **Bank Statements** - CSV showing all deposits and withdrawals

## Summary Statistics

### Total Loads Processed
- **Steve**: 388 loads
- **Tony**: 172 loads
- **Rich**: 395 loads
- **Little Rich**: 197 loads
- **TOTAL**: 1,152 driver loads

### Payment Records
- **Ready Payments**: 664 invoice records
- **TruckSmarter Withdrawals** (April only): 8 withdrawals matched to bank deposits
- **Bank Transactions**: 649 total transactions

### Missing/Unmatched
- **234 loads** are missing from payment records or driver schedules

## Key Findings

### TruckSmarter Withdrawals Successfully Matched to Bank Deposits (April 2025)

| TruckSmarter Date | Bank Deposit Date | Amount | Status |
|-------------------|-------------------|---------|--------|
| Apr 03 | 4/4/2025 | $4,085.55 | ✓ Matched |
| Apr 04 | 4/8/2025 | $1,389.36 | ✓ Matched |
| Apr 06 | 4/8/2025 | $467.98 | ✓ Matched |
| Apr 07 | 4/9/2025 | $875.53 | ✓ Matched |
| Apr 09 | 4/11/2025 | $424.97 | ✓ Matched |
| Apr 15 | 4/16/2025 | $2,213.32 | ✓ Matched |
| Apr 18 | 4/21/2025 | $2,120.57 | ✓ Matched |
| Apr 30 | 5/1/2025 | $4,716.36 | ✓ Matched |

**All 8 April TruckSmarter withdrawals successfully matched to bank deposits!**

### Missing Loads Summary

The reconciliation found 234 loads that are either:
1. In driver schedules but NOT in Ready/TruckSmarter payment records
2. In Ready/TruckSmarter payment records but NOT in driver schedules

See `reconciliation_results/missing_loads_report.csv` for complete details.

## Generated Files

### Driver Summary Files
Each driver has a CSV file showing all their loads with payment information:
- `reconciliation_results/Steve_summary.csv`
- `reconciliation_results/Tony_summary.csv`
- `reconciliation_results/Rich_summary.csv`
- `reconciliation_results/Little_Rich_summary.csv`

**Format**: Load #, Company, Amount Paid, Date Paid

### TruckSmarter Matched Withdrawals
- `reconciliation_results/trucksmarter_withdrawals_matched.csv`

Shows TruckSmarter withdrawal dates matched to actual bank deposit dates.

### Missing Loads Report
- `reconciliation_results/missing_loads_report.csv`

Lists all loads that couldn't be matched between systems.

### Overall Summary
- `reconciliation_results/reconciliation_summary.json`

JSON file with high-level statistics.

## How the Reconciliation Works

### For Ready Loads
1. Script reads driver schedules and identifies loads with company = "Ready"
2. Matches Load # from schedule to Invoice Number in Ready CSV files
3. Gets Invoice Amount from Ready statements
4. Attempts to match Payment Date from Ready to bank deposits

### For TruckSmarter Loads
1. TruckSmarter withdrawal data is manually extracted from PNG files
2. Script matches withdrawal amounts to bank deposits by amount and description
3. When matched, shows which date the TruckSmarter withdrawal deposited into the bank

### Current Limitations
- **TruckSmarter data is only complete for April 2025**
- Remaining months (March, May, June, July, August, September, October) need manual extraction
- Some schedule files for September/October had parsing errors and may need review

## Next Steps to Complete Full Reconciliation

### 1. Extract Remaining TruckSmarter Data

For each month, manually read the PNG files in `pdf2png/` and extract withdrawal data:

**Folders to process:**
- `pdf2png/March trucksmarter/` (20 files)
- `pdf2png/May trucksmarter/` (9 files)
- `pdf2png/June trucksmarter/` (13 files)
- `pdf2png/July trucksmarter/` (18 files)
- `pdf2png/August trucksmarter/` (19 files)
- `pdf2png/Sept trucksmarter/` (17 files)
- `pdf2png/Oct. trucksmarter/` (16 files)

**For each PNG file:**
- Look for lines saying "S PROVISIONS LLC | Ach transfer via TruckSmarter app"
- Record the date and withdrawal amount
- Add to `trucksmarter_withdrawals_manual.csv` following the same format as April

**Example CSV format:**
```csv
month,date,withdrawal_amount,year
March,Mar 15,2543.21,2025
March,Mar 22,1876.54,2025
...
```

### 2. Fix Schedule Parsing Errors

Some schedule files couldn't be parsed (September/October for some drivers):
- Check if these files have a different format
- May need to manually verify data or adjust the parsing logic

### 3. Re-run Enhanced Reconciliation

After adding more TruckSmarter data:
```bash
python3 reconcile_loads_enhanced.py
```

This will regenerate all reports with the updated information.

## Usage Instructions

### Run Basic Reconciliation (CSV data only)
```bash
python3 reconcile_loads.py
```

### Run Enhanced Reconciliation (includes TruckSmarter matching)
```bash
python3 reconcile_loads_enhanced.py
```

### View Results
All results are saved in the `reconciliation_results/` directory.

## Technical Details

### Required Dependencies
- pandas
- Python 3.7+

Install with:
```bash
pip install pandas
```

### Input Data Locations
- Driver Schedules: `dataset_20251117/dataset_20251117__schedules/`
- Ready Statements: `dataset_20251117/dataset_20251117__Ready Statements CSV/`
- Bank Statement: `dataset_20251117/dataset_20251117__.csv`
- TruckSmarter PNGs: `pdf2png/`
- Manual TruckSmarter Data: `trucksmarter_withdrawals_manual.csv`

### Key Scripts
1. **reconcile_loads.py** - Basic reconciliation (CSV data only)
2. **reconcile_loads_enhanced.py** - Enhanced reconciliation with TruckSmarter matching
3. **extract_trucksmarter_manual.py** - Helper for manual TruckSmarter data extraction

## Questions or Issues?

If you encounter missing data or discrepancies:
1. Check the `missing_loads_report.csv` for specific loads
2. Verify the source files in `dataset_20251117/`
3. Review TruckSmarter PNG files for manual verification
4. Cross-reference with bank statements for deposit dates

## Current Completion Status

✅ **Completed:**
- Driver schedule parsing (1,152 loads)
- Ready statement parsing (664 payments)
- Bank statement parsing (649 transactions)
- April TruckSmarter withdrawal matching (8/8 matched)
- Missing loads identification (234 found)
- Driver summary generation

⏳ **Pending:**
- TruckSmarter data extraction for March, May-October (7 months)
- Resolution of 234 missing/unmatched loads
- September/October schedule parsing errors

---

**Report Generated**: November 17, 2025
**Data Period**: March - October 2025
**Last Updated**: After April TruckSmarter matching
