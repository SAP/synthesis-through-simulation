"""
Validation script: business rules for the E-commerce DB.

Run directly:
    python -m synthesize.environments.ecommerce.validate
    python -m synthesize.environments.ecommerce.validate --db path/to/ecommerce.db
    python -m synthesize.environments.ecommerce.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "ecommerce.db"
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


@check("Orders", "status must be pending/confirmed/shipped/delivered/cancelled")
def check_order_status():
    return rows(
        "SELECT order_id, status FROM shop_order "
        "WHERE status NOT IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')"
    )


@check("Orders", "All orders belong to a known active customer")
def check_order_customer_fk():
    return rows(
        """SELECT o.order_id, o.customer_id
           FROM shop_order o
           LEFT JOIN customer c ON o.customer_id = c.customer_id
           WHERE c.customer_id IS NULL OR c.is_active = 0"""
    )


@check("Orders", "total_amount matches sum of order items")
def check_order_total_consistent():
    return rows(
        """SELECT o.order_id, o.total_amount AS stored,
                  COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS calculated
           FROM shop_order o
           LEFT JOIN order_item oi ON o.order_id = oi.order_id
           GROUP BY o.order_id
           HAVING ABS(stored - calculated) > 0.01"""
    )


@check("Orders", "shipping_address must be non-empty")
def check_order_has_address():
    return rows(
        "SELECT order_id, shipping_address FROM shop_order "
        "WHERE shipping_address IS NULL OR TRIM(shipping_address) = ''"
    )


@check("Products", "price must be positive")
def check_product_price_positive():
    return rows("SELECT product_id, price FROM product WHERE price <= 0")


@check("Products", "stock_qty must be non-negative")
def check_product_stock_non_negative():
    return rows("SELECT product_id, stock_qty FROM product WHERE stock_qty < 0")


@check("Order Items", "quantity must be positive")
def check_item_quantity_positive():
    return rows(
        "SELECT order_item_id, quantity FROM order_item WHERE quantity <= 0"
    )


@check("Order Items", "unit_price must be positive")
def check_item_price_positive():
    return rows(
        "SELECT order_item_id, unit_price FROM order_item WHERE unit_price <= 0"
    )


@check("Order Items", "All items reference known orders and active products")
def check_item_fks():
    violations = []
    violations += rows(
        """SELECT oi.order_item_id, oi.order_id
           FROM order_item oi
           LEFT JOIN shop_order o ON oi.order_id = o.order_id
           WHERE o.order_id IS NULL"""
    )
    violations += rows(
        """SELECT oi.order_item_id, oi.product_id
           FROM order_item oi
           LEFT JOIN product p ON oi.product_id = p.product_id
           WHERE p.product_id IS NULL OR p.is_active = 0"""
    )
    return violations


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
    parser = argparse.ArgumentParser(description="Validate E-commerce DB business rules")
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
