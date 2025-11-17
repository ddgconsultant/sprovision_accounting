# Quick Start Guide - Load Reconciliation

## What You Get Immediately

Run this command to see your reconciliation:
```bash
python3 reconcile_loads_enhanced.py
```

This will show you:
1. **All 1,152 driver loads** across Steve, Tony, Rich, and Little Rich
2. **Ready payment matching** for loads serviced by Ready
3. **April TruckSmarter withdrawals** matched to bank deposits
4. **Missing loads report** showing discrepancies

## View Your Results

All results are in `reconciliation_results/` folder:

### Driver Summaries
- `Steve_summary.csv` - 388 loads
- `Tony_summary.csv` - 172 loads
- `Rich_summary.csv` - 395 loads
- `Little_Rich_summary.csv` - 197 loads

**Each shows**: Load #, Company, Amount Paid, Date Paid

### Other Reports
- `missing_loads_report.csv` - 234 loads needing attention
- `trucksmarter_withdrawals_matched.csv` - April TruckSmarter → Bank matches
- `reconciliation_summary.json` - Overall statistics

## Example Driver Summary

**Tony's Summary** (first few loads):
| Load # | Company | Amount Paid | Date Paid |
|--------|---------|-------------|-----------|
| RP31500A | RCG | $75.00 | Not Found |
| RP31495A | RCG | $75.00 | Not Found |
| 10411536594 | Ready | $80.00 | 10/3/2025 |

## TruckSmarter Bank Deposits (April)

| TruckSmarter Withdrawal | Deposited in Bank | Amount |
|------------------------|-------------------|---------|
| Apr 03 | 4/4/2025 | $4,085.55 |
| Apr 04 | 4/8/2025 | $1,389.36 |
| Apr 06 | 4/8/2025 | $467.98 |
| Apr 07 | 4/9/2025 | $875.53 |
| Apr 09 | 4/11/2025 | $424.97 |
| Apr 15 | 4/16/2025 | $2,213.32 |
| Apr 18 | 4/21/2025 | $2,120.57 |
| Apr 30 | 5/1/2025 | $4,716.36 |

## What's Missing?

The script found **234 loads** that don't match:
- Some loads in schedules but not in payment records
- Some payments without matching schedule entries

Check `reconciliation_results/missing_loads_report.csv` for the full list.

## To Complete Full Reconciliation

You need to extract TruckSmarter withdrawal data for the remaining months. See `RECONCILIATION_README.md` for detailed instructions.

### Quick Version:
1. Open PNG files in `pdf2png/[Month] trucksmarter/`
2. Find lines with "S PROVISIONS LLC | Ach transfer via TruckSmarter app"
3. Add the date and amount to `trucksmarter_withdrawals_manual.csv`
4. Re-run `python3 reconcile_loads_enhanced.py`

---

**Need help?** See `RECONCILIATION_README.md` for complete documentation.
