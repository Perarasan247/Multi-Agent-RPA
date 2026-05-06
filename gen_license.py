"""License generator — run on your dev machine ONLY. Never ship this file.

Usage:
    python gen_license.py "Bajaj Motors Pune" 2027-03-31
    python gen_license.py "ABC Dealers" 2026-12-31 --out licenses\abc.key
"""

import argparse
from datetime import date
from pathlib import Path

# IMPORTANT: This value MUST match LICENSE_SECRET in .secrets exactly.
# If they differ, every generated license.key will be rejected by the exe.
# To rotate the secret: update BOTH this line AND .secrets, then rebuild the exe.
SECRET = "c7fd2c5b7f3b789f3fc364c3b12177e19571d69841814f27f505b0ea74cb7e2e"


def main():
    parser = argparse.ArgumentParser(description="Generate a license.key for a client.")
    parser.add_argument("client_name", help='Client name, e.g. "Bajaj Motors Pune"')
    parser.add_argument("expiry", help="Expiry date in YYYY-MM-DD format, e.g. 2027-03-31")
    parser.add_argument("--out", default="license.key", help="Output file path (default: license.key)")
    args = parser.parse_args()

    try:
        expiry = date.fromisoformat(args.expiry)
    except ValueError:
        print(f"ERROR: Invalid date '{args.expiry}'. Use YYYY-MM-DD format.")
        raise SystemExit(1)

    from config.license import generate_license
    token = generate_license(SECRET, args.client_name, expiry)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(token)

    days = (expiry - date.today()).days
    print(f"License generated!")
    print(f"  Client : {args.client_name}")
    print(f"  Expiry : {expiry.strftime('%d %b %Y')} ({days} days from today)")
    print(f"  File   : {out_path.resolve()}")
    print(f"\nEmail '{out_path}' to the client. They drop it in the exe folder.")


if __name__ == "__main__":
    main()
