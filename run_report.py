"""Wrapper to run a report with auto-calculated dates.

Usage:
    python run_report.py sale_statement --date-range month_to_date
    python run_report.py stock_valuation
    python run_report.py purchase_statement --date-range previous_month

Date range options:
    today            — today only
    yesterday        — yesterday only
    week_to_date     — Monday of this week → today
    month_to_date    — 1st of this month → today (default)
    year_to_date     — 1st of January → today
    previous_month   — 1st → last day of previous month
    previous_year    — 1st Jan → 31st Dec of previous year
"""

import argparse
import calendar
from datetime import date, timedelta
from pathlib import Path

DATE_FORMAT = "%d/%m/%Y"

DATE_RANGE_CHOICES = [
    "today",
    "yesterday",
    "week_to_date",
    "month_to_date",
    "year_to_date",
    "previous_month",
    "previous_year",
]


def calculate_dates(date_range: str) -> tuple[str, str]:
    """Return (from_date, to_date) strings in DD/MM/YYYY format."""
    today = date.today()

    if date_range == "today":
        from_date = to_date = today

    elif date_range == "yesterday":
        yesterday = today - timedelta(days=1)
        from_date = to_date = yesterday

    elif date_range == "week_to_date":
        # Monday of the current week
        from_date = today - timedelta(days=today.weekday())
        to_date = today

    elif date_range == "month_to_date":
        from_date = today.replace(day=1)
        to_date = today

    elif date_range == "year_to_date":
        from_date = today.replace(month=1, day=1)
        to_date = today

    elif date_range == "previous_month":
        first_of_current = today.replace(day=1)
        last_of_prev = first_of_current - timedelta(days=1)
        from_date = last_of_prev.replace(day=1)
        to_date = last_of_prev

    elif date_range == "previous_year":
        prev_year = today.year - 1
        from_date = date(prev_year, 1, 1)
        to_date = date(prev_year, 12, 31)

    return from_date.strftime(DATE_FORMAT), to_date.strftime(DATE_FORMAT)


def main():
    from config.license import check_license
    from config.settings import settings
    check_license(settings.license_secret, Path.cwd() / "license.key")

    parser = argparse.ArgumentParser(
        description="Run Excellon RPA pipeline with auto-calculated dates.",
    )
    parser.add_argument("report_key", help="Report key from reports.json")
    parser.add_argument(
        "--date-range",
        default="month_to_date",
        choices=DATE_RANGE_CHOICES,
        help="Date range preset (default: month_to_date)",
    )
    args = parser.parse_args()

    from_date, to_date = calculate_dates(args.date_range)

    print(f"Report:     {args.report_key}")
    print(f"Date range: {args.date_range}")
    print(f"From:       {from_date}")
    print(f"To:         {to_date}")
    print("-" * 50)

    # Import and run directly (works both as script and as packaged .exe)
    from main import _setup_logging, run_full_pipeline
    _setup_logging()
    run_full_pipeline(
        report_key=args.report_key,
        from_date=from_date,
        to_date=to_date,
    )


if __name__ == "__main__":
    main()
