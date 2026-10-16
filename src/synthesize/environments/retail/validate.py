"""
Validation script: checks all business rules against the Retail DB.

Each check function returns a list of violation dicts.
Run directly:
    python -m synthesize.environments.retail.validate
    python -m synthesize.environments.retail.validate --db path/to/retail.db
    python -m synthesize.environments.retail.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "retail.db"
DB_PATH = _DEFAULT_DB


def set_db(path: Path) -> None:
    """Point the validator at a different DB file."""
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


# ── Check registry ────────────────────────────────────────────────────────────

CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ── Orders ────────────────────────────────────────────────────────────────────


@check("Orders", "Status must be a valid order status")
def check_order_status():
    return rows(
        """SELECT order_id, status FROM orders
           WHERE status NOT IN (
               'pending', 'pending (item modified)', 'processed',
               'delivered', 'cancelled', 'exchange requested', 'return requested'
           )"""
    )


@check("Orders", "order_id must start with '#W'")
def check_order_id_format():
    return rows("SELECT order_id FROM orders WHERE order_id NOT LIKE '#W%'")


@check("Orders", "Cancelled orders must have cancel_reason")
def check_cancelled_has_reason():
    return rows(
        "SELECT order_id, status FROM orders WHERE status = 'cancelled' AND cancel_reason IS NULL"
    )


@check("Orders", "cancel_reason only set on cancelled orders")
def check_reason_only_on_cancelled():
    return rows(
        "SELECT order_id, status, cancel_reason FROM orders "
        "WHERE cancel_reason IS NOT NULL AND status != 'cancelled'"
    )


@check("Orders", "Exchange requested orders have all exchange fields set")
def check_exchange_fields_complete():
    return rows(
        """SELECT order_id FROM orders
           WHERE status = 'exchange requested'
             AND (exchange_items IS NULL
                  OR exchange_new_items IS NULL
                  OR exchange_payment_method_id IS NULL
                  OR exchange_price_difference IS NULL)"""
    )


@check("Orders", "Return requested orders have all return fields set")
def check_return_fields_complete():
    return rows(
        """SELECT order_id FROM orders
           WHERE status = 'return requested'
             AND (return_items IS NULL OR return_payment_method_id IS NULL)"""
    )


@check("Orders", "All order user references point to valid users")
def check_order_user_refs():
    return rows(
        """SELECT o.order_id, o.user_id FROM orders o
           LEFT JOIN users u ON o.user_id = u.user_id
           WHERE u.user_id IS NULL"""
    )


# ── Order Items ───────────────────────────────────────────────────────────────


@check("Order Items", "All order_id references point to valid orders")
def check_order_items_order_ref():
    return rows(
        """SELECT oi.id, oi.order_id FROM order_items oi
           LEFT JOIN orders o ON oi.order_id = o.order_id
           WHERE o.order_id IS NULL"""
    )


@check("Order Items", "Price must be positive")
def check_order_item_price():
    return rows("SELECT id, order_id, item_id, price FROM order_items WHERE price <= 0")


@check("Order Items", "Name must be non-empty")
def check_order_item_name():
    return rows(
        "SELECT id, order_id FROM order_items WHERE name IS NULL OR TRIM(name) = ''"
    )


# ── Payment Methods ───────────────────────────────────────────────────────────


@check("Payment Methods", "source must be credit_card, gift_card, or paypal")
def check_pm_source():
    return rows(
        "SELECT payment_method_id, source FROM payment_methods "
        "WHERE source NOT IN ('credit_card', 'gift_card', 'paypal')"
    )


@check("Payment Methods", "credit_card must have brand and last_four")
def check_credit_card_fields():
    return rows(
        """SELECT payment_method_id FROM payment_methods
           WHERE source = 'credit_card'
             AND (brand IS NULL OR TRIM(brand) = ''
                  OR last_four IS NULL OR TRIM(last_four) = '')"""
    )


@check("Payment Methods", "gift_card must have balance >= 0")
def check_gift_card_balance():
    return rows(
        "SELECT payment_method_id, balance FROM payment_methods "
        "WHERE source = 'gift_card' AND (balance IS NULL OR balance < 0)"
    )


@check("Payment Methods", "All payment methods belong to valid users")
def check_pm_user_refs():
    return rows(
        """SELECT pm.payment_method_id, pm.user_id FROM payment_methods pm
           LEFT JOIN users u ON pm.user_id = u.user_id
           WHERE u.user_id IS NULL"""
    )


# ── Payment History ───────────────────────────────────────────────────────────


@check("Payment History", "transaction_type must be payment or refund")
def check_payment_transaction_type():
    return rows(
        "SELECT id, order_id, transaction_type FROM payment_history "
        "WHERE transaction_type NOT IN ('payment', 'refund')"
    )


@check("Payment History", "Amount must be positive")
def check_payment_amount():
    return rows("SELECT id, order_id, amount FROM payment_history WHERE amount <= 0")


@check("Payment History", "All payment history order references are valid")
def check_payment_order_refs():
    return rows(
        """SELECT ph.id, ph.order_id FROM payment_history ph
           LEFT JOIN orders o ON ph.order_id = o.order_id
           WHERE o.order_id IS NULL"""
    )


# ── Variants ──────────────────────────────────────────────────────────────────


@check("Variants", "Price must be positive")
def check_variant_price():
    return rows("SELECT item_id, product_id, price FROM variants WHERE price <= 0")


@check("Variants", "All variant product_id references point to valid products")
def check_variant_product_refs():
    return rows(
        """SELECT v.item_id, v.product_id FROM variants v
           LEFT JOIN products p ON v.product_id = p.product_id
           WHERE p.product_id IS NULL"""
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
                    print(
                        f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)"
                    )
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Retail DB business rules")
    parser.add_argument("--db", type=Path, default=None, help="Path to DB file")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)

    if args.json:
        print(json.dumps(results, indent=2))

    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
