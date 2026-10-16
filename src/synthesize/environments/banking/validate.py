"""
Validation script: business rules for the Retail Banking DB.

Run directly:
    python -m synthesize.environments.banking.validate
    python -m synthesize.environments.banking.validate --db path/to/banking.db
    python -m synthesize.environments.banking.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "banking.db"
DB_PATH = _DEFAULT_DB


def set_db(path: Path) -> None:
    global DB_PATH
    DB_PATH = Path(path)


def conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def rows(sql: str, params: tuple = ()) -> list:
    c = conn()
    result = c.execute(sql, params).fetchall()
    c.close()
    return [dict(r) for r in result]


def scalar(sql: str, params: tuple = ()) -> int:
    c = conn()
    result = c.execute(sql, params).fetchone()[0]
    c.close()
    return result


CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ── Checks ────────────────────────────────────────────────────────────────────


@check("Accounts", "account_type must be checking/savings/loan")
def check_account_type():
    return rows(
        "SELECT account_id, account_type FROM account "
        "WHERE account_type NOT IN ('checking', 'savings', 'loan')"
    )


@check("Accounts", "status must be active/frozen/closed")
def check_account_status():
    return rows(
        "SELECT account_id, status FROM account "
        "WHERE status NOT IN ('active', 'frozen', 'closed')"
    )


@check("Accounts", "All accounts belong to a known active customer")
def check_account_customer_fk():
    return rows(
        """SELECT a.account_id, a.customer_id
           FROM account a
           LEFT JOIN customer c ON a.customer_id = c.customer_id
           WHERE c.customer_id IS NULL OR c.is_active = 0"""
    )


@check("Accounts", "Non-overdraft accounts have non-negative balance")
def check_balance_non_negative():
    return rows(
        "SELECT account_id, account_type, balance, overdraft_allowed FROM account "
        "WHERE overdraft_allowed = 0 AND balance < 0"
    )


@check("Accounts", "Loan accounts do not have overdraft_allowed=1")
def check_loan_no_overdraft():
    return rows(
        "SELECT account_id, account_type, overdraft_allowed FROM account "
        "WHERE account_type = 'loan' AND overdraft_allowed = 1"
    )


@check("Accounts", "Closed accounts have zero balance")
def check_closed_zero_balance():
    return rows(
        "SELECT account_id, status, balance FROM account "
        "WHERE status = 'closed' AND balance != 0.0"
    )


@check("Accounts", "Overdraft only allowed on checking accounts")
def check_overdraft_only_checking():
    return rows(
        "SELECT account_id, account_type, overdraft_allowed FROM account "
        "WHERE overdraft_allowed = 1 AND account_type != 'checking'"
    )


@check("Transactions", "txn_type must be deposit/withdrawal/transfer_in/transfer_out/fee")
def check_txn_type():
    return rows(
        "SELECT txn_id, txn_type FROM txn "
        "WHERE txn_type NOT IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'fee')"
    )


@check("Transactions", "Transaction amount must be positive")
def check_txn_amount_positive():
    return rows("SELECT txn_id, amount FROM txn WHERE amount <= 0")


@check("Transactions", "All transactions link to a known account")
def check_txn_account_fk():
    return rows(
        """SELECT t.txn_id, t.account_id
           FROM txn t
           LEFT JOIN account a ON t.account_id = a.account_id
           WHERE a.account_id IS NULL"""
    )


# ── Runner ────────────────────────────────────────────────────────────────────


def run(as_json: bool = False, show_sample: int = 3) -> list:
    results = []
    for chk in CHECKS:
        violations = chk["fn"]()
        status = "PASS" if not violations else "FAIL"
        results.append(
            {
                "category": chk["category"],
                "rule": chk["rule"],
                "status": status,
                "violation_count": len(violations),
                "sample": violations[:show_sample] if show_sample else [],
            }
        )
        if not as_json:
            mark = "\033[32m✓\033[0m" if status == "PASS" else "\033[31m✗\033[0m"
            print(f"  {mark}  [{chk['category']}] {chk['rule']}")
            if violations and show_sample:
                for v in violations[:show_sample]:
                    print(f"       ↳ {v}")

    if not as_json:
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = total - passed
        print("\n" + "─" * 60)
        print(f"  Checks:  {total}")
        print(f"  Passed:  \033[32m✓\033[0m {passed}")
        print(f"  Failed:    {failed}")
        if failed:
            print("\n  Failing checks:")
            for r in results:
                if r["status"] == "FAIL":
                    print(f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)")
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Banking DB business rules")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)

    if args.json:
        print(json.dumps(results, indent=2))

    sys.exit(1 if any(r["status"] == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
