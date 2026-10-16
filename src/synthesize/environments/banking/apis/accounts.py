"""
Account and transaction API for the Retail Banking environment.

Business rules enforced:
  - account_type must be one of: checking, savings, loan
  - status transitions: active → frozen → active (unfreeze); active → closed
  - Withdrawals require sufficient balance unless overdraft_allowed=1 (checking only)
  - Loan accounts cannot have overdraft_allowed=1
  - Closed accounts cannot be modified
  - balance must be zero before closing a non-loan account

Auto-managed fields: status, balance (updated by deposit/withdraw/transfer),
                      balance_after stored per transaction
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.banking.db.db import get_conn

VALID_ACCOUNT_TYPES = {"checking", "savings", "loan"}
VALID_TXN_TYPES = {"deposit", "withdrawal", "transfer_in", "transfer_out", "fee"}


def _today() -> str:
    return datetime.date.today().isoformat()


def _txn_id() -> str:
    return "TXN-" + str(uuid.uuid4())[:8].upper()


def _acc_id() -> str:
    return "ACC-" + str(uuid.uuid4())[:8].upper()


# ── Read ──────────────────────────────────────────────────────────────────────


def get_account(account_id: str) -> Dict[str, Any]:
    """Return a single account record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM account WHERE account_id = ?", (account_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Account not found: {account_id!r}")
    return dict(row)


def list_customer_accounts(customer_id: str) -> List[Dict[str, Any]]:
    """Return all accounts for a customer."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM account WHERE customer_id = ? ORDER BY account_id",
            (customer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_accounts_by_type(account_type: str) -> List[Dict[str, Any]]:
    """Return all accounts of the given type.

    Raises ValueError for unknown types.
    """
    if account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError(f"account_type must be one of {sorted(VALID_ACCOUNT_TYPES)}")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM account WHERE account_type = ? ORDER BY account_id",
            (account_type,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_balance(account_id: str) -> float:
    """Return the current balance of an account.

    Raises LookupError if not found.
    Raises ValueError if account is not active.
    """
    acc = get_account(account_id)
    if acc["status"] != "active":
        raise ValueError(
            f"Account {account_id!r} is {acc['status']!r}; only active accounts can be queried"
        )
    return acc["balance"]


def list_transactions(account_id: str) -> List[Dict[str, Any]]:
    """Return all transactions for an account, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM txn WHERE account_id = ? ORDER BY created_date DESC, txn_id",
            (account_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Write ─────────────────────────────────────────────────────────────────────


def open_account(
    customer_id: str,
    account_type: str,
    initial_deposit: float = 0.0,
    currency: str = "USD",
    overdraft_allowed: bool = False,
) -> Dict[str, Any]:
    """Open a new bank account for a customer.

    Raises LookupError if customer not found.
    Raises ValueError for invalid inputs or business rule violations.
    """
    if account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError(f"account_type must be one of {sorted(VALID_ACCOUNT_TYPES)}")
    if initial_deposit < 0:
        raise ValueError("initial_deposit cannot be negative")
    if account_type == "loan" and overdraft_allowed:
        raise ValueError("Loan accounts cannot have overdraft enabled")

    with get_conn() as conn:
        customer = conn.execute(
            "SELECT is_active FROM customer WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if customer is None:
            raise LookupError(f"Customer not found: {customer_id!r}")
        if not customer["is_active"]:
            raise ValueError(f"Customer {customer_id!r} is not active")

        account_id = _acc_id()
        conn.execute(
            """INSERT INTO account
               (account_id, customer_id, account_type, balance, currency, status, overdraft_allowed, opening_date)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?)""",
            (account_id, customer_id, account_type, initial_deposit, currency,
             1 if overdraft_allowed else 0, _today()),
        )
        if initial_deposit > 0:
            conn.execute(
                """INSERT INTO txn (txn_id, account_id, txn_type, amount, balance_after, description, created_date)
                   VALUES (?, ?, 'deposit', ?, ?, 'Initial deposit', ?)""",
                (_txn_id(), account_id, initial_deposit, initial_deposit, _today()),
            )
    return get_account(account_id)


def deposit(account_id: str, amount: float, description: Optional[str] = None) -> Dict[str, Any]:
    """Credit funds to an active account.

    Raises LookupError if not found.
    Raises ValueError if amount ≤ 0 or account is not active.
    """
    if amount <= 0:
        raise ValueError(f"Deposit amount must be positive, got {amount}")
    with get_conn() as conn:
        acc = conn.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()
        if acc is None:
            raise LookupError(f"Account not found: {account_id!r}")
        if acc["status"] != "active":
            raise ValueError(f"Cannot deposit to {acc['status']!r} account {account_id!r}")
        new_balance = acc["balance"] + amount
        conn.execute(
            "UPDATE account SET balance = ? WHERE account_id = ?", (new_balance, account_id)
        )
        conn.execute(
            """INSERT INTO txn (txn_id, account_id, txn_type, amount, balance_after, description, created_date)
               VALUES (?, ?, 'deposit', ?, ?, ?, ?)""",
            (_txn_id(), account_id, amount, new_balance, description, _today()),
        )
    return get_account(account_id)


def withdraw(account_id: str, amount: float, description: Optional[str] = None) -> Dict[str, Any]:
    """Debit funds from an active account.

    Raises LookupError if not found.
    Raises ValueError if amount ≤ 0, account not active, or insufficient funds.
    """
    if amount <= 0:
        raise ValueError(f"Withdrawal amount must be positive, got {amount}")
    with get_conn() as conn:
        acc = conn.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()
        if acc is None:
            raise LookupError(f"Account not found: {account_id!r}")
        if acc["status"] != "active":
            raise ValueError(f"Cannot withdraw from {acc['status']!r} account {account_id!r}")
        new_balance = acc["balance"] - amount
        if new_balance < 0 and not acc["overdraft_allowed"]:
            raise ValueError(
                f"Insufficient funds: balance is {acc['balance']:.2f}, requested {amount:.2f}"
            )
        conn.execute(
            "UPDATE account SET balance = ? WHERE account_id = ?", (new_balance, account_id)
        )
        conn.execute(
            """INSERT INTO txn (txn_id, account_id, txn_type, amount, balance_after, description, created_date)
               VALUES (?, ?, 'withdrawal', ?, ?, ?, ?)""",
            (_txn_id(), account_id, amount, new_balance, description, _today()),
        )
    return get_account(account_id)


def transfer(
    from_account_id: str, to_account_id: str, amount: float, description: Optional[str] = None
) -> Dict[str, Any]:
    """Transfer funds between two active accounts.

    Returns the updated source account.
    Raises LookupError if either account not found.
    Raises ValueError for invalid amount or insufficient funds.
    """
    if amount <= 0:
        raise ValueError(f"Transfer amount must be positive, got {amount}")
    if from_account_id == to_account_id:
        raise ValueError("Source and destination accounts must be different")

    with get_conn() as conn:
        src = conn.execute("SELECT * FROM account WHERE account_id = ?", (from_account_id,)).fetchone()
        if src is None:
            raise LookupError(f"Source account not found: {from_account_id!r}")
        dst = conn.execute("SELECT * FROM account WHERE account_id = ?", (to_account_id,)).fetchone()
        if dst is None:
            raise LookupError(f"Destination account not found: {to_account_id!r}")

        for acc, label in [(src, "source"), (dst, "destination")]:
            if acc["status"] != "active":
                raise ValueError(f"Cannot transfer: {label} account {acc['account_id']!r} is {acc['status']!r}")

        src_new = src["balance"] - amount
        if src_new < 0 and not src["overdraft_allowed"]:
            raise ValueError(
                f"Insufficient funds in {from_account_id!r}: balance {src['balance']:.2f}, requested {amount:.2f}"
            )
        dst_new = dst["balance"] + amount
        today = _today()
        note = description or f"Transfer to {to_account_id}"

        conn.execute("UPDATE account SET balance = ? WHERE account_id = ?", (src_new, from_account_id))
        conn.execute("UPDATE account SET balance = ? WHERE account_id = ?", (dst_new, to_account_id))
        conn.execute(
            """INSERT INTO txn (txn_id, account_id, txn_type, amount, balance_after, description, created_date)
               VALUES (?, ?, 'transfer_out', ?, ?, ?, ?)""",
            (_txn_id(), from_account_id, amount, src_new, note, today),
        )
        conn.execute(
            """INSERT INTO txn (txn_id, account_id, txn_type, amount, balance_after, description, created_date)
               VALUES (?, ?, 'transfer_in', ?, ?, ?, ?)""",
            (_txn_id(), to_account_id, amount, dst_new, f"Transfer from {from_account_id}", today),
        )
    return get_account(from_account_id)


def freeze_account(account_id: str) -> Dict[str, Any]:
    """Freeze an active account (restrict all operations).

    Raises LookupError if not found.
    Raises ValueError if account is not active.
    """
    with get_conn() as conn:
        acc = conn.execute("SELECT status FROM account WHERE account_id = ?", (account_id,)).fetchone()
        if acc is None:
            raise LookupError(f"Account not found: {account_id!r}")
        if acc["status"] != "active":
            raise ValueError(f"Cannot freeze account {account_id!r}: status is {acc['status']!r}")
        conn.execute("UPDATE account SET status = 'frozen' WHERE account_id = ?", (account_id,))
    return get_account(account_id)


def unfreeze_account(account_id: str) -> Dict[str, Any]:
    """Reactivate a frozen account.

    Raises LookupError if not found.
    Raises ValueError if account is not frozen.
    """
    with get_conn() as conn:
        acc = conn.execute("SELECT status FROM account WHERE account_id = ?", (account_id,)).fetchone()
        if acc is None:
            raise LookupError(f"Account not found: {account_id!r}")
        if acc["status"] != "frozen":
            raise ValueError(f"Cannot unfreeze account {account_id!r}: status is {acc['status']!r}")
        conn.execute("UPDATE account SET status = 'active' WHERE account_id = ?", (account_id,))
    return get_account(account_id)


def close_account(account_id: str) -> Dict[str, Any]:
    """Close an account.

    For non-loan accounts the balance must be zero first.
    Loan accounts can be closed when balance = 0 (fully repaid).

    Raises LookupError if not found.
    Raises ValueError if account is already closed or balance is non-zero.
    """
    with get_conn() as conn:
        acc = conn.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()
        if acc is None:
            raise LookupError(f"Account not found: {account_id!r}")
        if acc["status"] == "closed":
            raise ValueError(f"Account {account_id!r} is already closed")
        if acc["balance"] != 0.0:
            raise ValueError(
                f"Account {account_id!r} must have zero balance to close (current: {acc['balance']:.2f})"
            )
        conn.execute("UPDATE account SET status = 'closed' WHERE account_id = ?", (account_id,))
    return get_account(account_id)


def set_overdraft(account_id: str, overdraft_allowed: bool) -> Dict[str, Any]:
    """Enable or disable overdraft protection for a checking account.

    Raises LookupError if not found.
    Raises ValueError if account type is not checking or account is not active.
    """
    with get_conn() as conn:
        acc = conn.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()
        if acc is None:
            raise LookupError(f"Account not found: {account_id!r}")
        if acc["account_type"] != "checking":
            raise ValueError(
                f"Overdraft can only be set on checking accounts, not {acc['account_type']!r}"
            )
        if acc["status"] != "active":
            raise ValueError(f"Cannot modify {acc['status']!r} account {account_id!r}")
        conn.execute(
            "UPDATE account SET overdraft_allowed = ? WHERE account_id = ?",
            (1 if overdraft_allowed else 0, account_id),
        )
    return get_account(account_id)
