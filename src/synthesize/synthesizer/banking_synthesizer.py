"""
Banking synthesizers.

BankingAgentSynthesizer — LLM agent executes banking intents via Banking APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.banking.apis.accounts import (
    deposit,
    get_account,
    get_balance,
    list_accounts_by_type,
    list_customer_accounts,
    list_transactions,
    open_account,
    transfer,
    withdraw,
)
from synthesize.environments.banking.apis.customers import list_customers
from synthesize.environments.banking.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

BANKING_TOOL_REGISTRY: Dict[str, dict] = {
    "list_customers": {
        "fn": list_customers,
        "description": "List all customers, optionally filtered by active status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "is_active": {"type": "boolean", "description": "Filter by active status"},
            },
            "required": [],
        },
    },
    "list_customer_accounts": {
        "fn": list_customer_accounts,
        "description": "List all accounts for a customer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
            },
            "required": ["customer_id"],
        },
    },
    "list_accounts_by_type": {
        "fn": list_accounts_by_type,
        "description": "List all accounts of a given type (checking, savings, loan).",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_type": {
                    "type": "string",
                    "enum": ["checking", "savings", "loan"],
                },
            },
            "required": ["account_type"],
        },
    },
    "get_account": {
        "fn": get_account,
        "description": "Get a single account record by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
            },
            "required": ["account_id"],
        },
    },
    "get_balance": {
        "fn": get_balance,
        "description": "Get the current balance of an active account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
            },
            "required": ["account_id"],
        },
    },
    "list_transactions": {
        "fn": list_transactions,
        "description": "List all transactions for an account, newest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
            },
            "required": ["account_id"],
        },
    },
    "open_account": {
        "fn": open_account,
        "description": (
            "Open a new bank account for a customer. "
            "account_type must be one of: checking, savings, loan. "
            "Loan accounts cannot have overdraft_allowed=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "account_type": {
                    "type": "string",
                    "enum": ["checking", "savings", "loan"],
                },
                "initial_deposit": {"type": "number", "description": "Initial deposit amount (default 0)"},
                "currency": {"type": "string", "description": "Currency code (default USD)"},
                "overdraft_allowed": {"type": "boolean", "description": "Enable overdraft (checking only)"},
            },
            "required": ["customer_id", "account_type"],
        },
    },
    "deposit": {
        "fn": deposit,
        "description": "Credit funds to an active account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "amount": {"type": "number", "description": "Amount to deposit (must be positive)"},
                "description": {"type": "string", "description": "Optional transaction note"},
            },
            "required": ["account_id", "amount"],
        },
    },
    "withdraw": {
        "fn": withdraw,
        "description": "Debit funds from an active account. Requires sufficient balance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "amount": {"type": "number", "description": "Amount to withdraw (must be positive)"},
                "description": {"type": "string", "description": "Optional transaction note"},
            },
            "required": ["account_id", "amount"],
        },
    },
    "transfer": {
        "fn": transfer,
        "description": "Transfer funds between two active accounts. Both must be active.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_account_id": {"type": "string", "description": "Source account ID"},
                "to_account_id": {"type": "string", "description": "Destination account ID"},
                "amount": {"type": "number", "description": "Amount to transfer (must be positive)"},
                "description": {"type": "string", "description": "Optional note"},
            },
            "required": ["from_account_id", "to_account_id", "amount"],
        },
    },
}

# Generic alias required by GeneralistPopulatorSynthesizer
TOOL_REGISTRY = BANKING_TOOL_REGISTRY

# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_open_account() -> Optional[dict]:
    """Sample an active customer to open a new account."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT customer_id FROM customer WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"customer_id": row["customer_id"]}


def _sample_deposit() -> Optional[dict]:
    """Sample an active account to deposit into."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT account_id, customer_id FROM account WHERE status = 'active' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"account_id": row["account_id"], "customer_id": row["customer_id"]}


def _sample_withdraw() -> Optional[dict]:
    """Sample an active account with positive balance for withdrawal."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT account_id, customer_id, balance FROM account WHERE status = 'active' AND balance > 0 ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "account_id": row["account_id"],
        "customer_id": row["customer_id"],
        "balance": row["balance"],
    }


def _sample_transfer() -> Optional[dict]:
    """Sample a customer with at least 2 active accounts for a transfer."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT customer_id FROM account
            WHERE status = 'active'
            GROUP BY customer_id
            HAVING COUNT(*) >= 2
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        accounts = conn.execute(
            "SELECT account_id, balance FROM account WHERE customer_id = ? AND status = 'active' ORDER BY RANDOM()",
            (row["customer_id"],),
        ).fetchall()
    if len(accounts) < 2:
        return None
    src = accounts[0]
    dst = accounts[1]
    return {
        "customer_id": row["customer_id"],
        "from_account_id": src["account_id"],
        "to_account_id": dst["account_id"],
        "from_balance": src["balance"],
    }


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_open_account(params: dict, steps: List[Step]) -> Dict[str, bool]:
    account_id = None
    for step in steps:
        if step.tool == "open_account" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                account_id = result.get("account_id")
            break
    if not account_id:
        return {"account_created": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT account_id FROM account WHERE account_id = ?", (account_id,)
        ).fetchone()

    return {"account_created": row is not None}


def _postcond_deposit(params: dict, steps: List[Step]) -> Dict[str, bool]:
    for step in steps:
        if step.tool == "deposit" and not step.is_error:
            return {"deposit_recorded": True}
    return {"deposit_recorded": False}


def _postcond_withdraw(params: dict, steps: List[Step]) -> Dict[str, bool]:
    for step in steps:
        if step.tool == "withdraw" and not step.is_error:
            return {"withdraw_recorded": True}
    return {"withdraw_recorded": False}


def _postcond_transfer(params: dict, steps: List[Step]) -> Dict[str, bool]:
    for step in steps:
        if step.tool == "transfer" and not step.is_error:
            return {"transfer_recorded": True}
    return {"transfer_recorded": False}


# ── Intent definitions ────────────────────────────────────────────────────────

BANKING_INTENTS: Dict[str, IntentDef] = {
    "OPEN_ACCOUNT": IntentDef(
        name="OPEN_ACCOUNT",
        brief="Open a new bank account (checking, savings, or loan) for an active customer.",
        informed_rules="""\
Banking Account Opening Rules:
- customer must be active (is_active=true)
- account_type must be one of: checking, savings, loan
- Loan accounts cannot have overdraft_allowed=true
- initial_deposit must be >= 0 (default 0)
- Account ID is auto-generated
""",
        tools=[
            "list_customers",
            "list_customer_accounts",
            "open_account",
        ],
        sampler=_sample_open_account,
        task_prompt=lambda p: (
            f"Open a new bank account for customer '{p['customer_id']}'. "
            "Choose an appropriate account type (checking, savings, or loan) "
            "with a realistic initial deposit."
        ),
        postconditions=_postcond_open_account,
    ),
    "DEPOSIT": IntentDef(
        name="DEPOSIT",
        brief="Deposit funds into an active bank account.",
        informed_rules="""\
Banking Deposit Rules:
- Account must be active (status='active')
- amount must be positive
- No upper limit on deposit amount
""",
        tools=[
            "list_customer_accounts",
            "get_balance",
            "deposit",
        ],
        sampler=_sample_deposit,
        task_prompt=lambda p: (
            f"Make a deposit into account '{p['account_id']}'. "
            "Choose a realistic deposit amount."
        ),
        postconditions=_postcond_deposit,
    ),
    "WITHDRAW": IntentDef(
        name="WITHDRAW",
        brief="Withdraw funds from an active bank account.",
        informed_rules="""\
Banking Withdrawal Rules:
- Account must be active (status='active')
- amount must be positive
- Withdrawal cannot exceed balance unless overdraft_allowed=true (checking only)
- Check balance first with get_balance
""",
        tools=[
            "list_customer_accounts",
            "get_balance",
            "withdraw",
        ],
        sampler=_sample_withdraw,
        task_prompt=lambda p: (
            f"Withdraw an amount from account '{p['account_id']}' "
            f"(current balance: {p['balance']:.2f}). "
            "Check the balance first, then withdraw a realistic amount."
        ),
        postconditions=_postcond_withdraw,
    ),
    "TRANSFER": IntentDef(
        name="TRANSFER",
        brief="Transfer funds between two active accounts of the same customer.",
        informed_rules="""\
Banking Transfer Rules:
- Both accounts must be active
- source and destination accounts must be different
- amount must be positive
- Source account must have sufficient balance (unless overdraft_allowed=true)
""",
        tools=[
            "list_customer_accounts",
            "get_balance",
            "transfer",
        ],
        sampler=_sample_transfer,
        task_prompt=lambda p: (
            f"Transfer funds from account '{p['from_account_id']}' to '{p['to_account_id']}' "
            f"for customer '{p['customer_id']}'. "
            f"Source balance is {p['from_balance']:.2f}. Choose a realistic transfer amount."
        ),
        postconditions=_postcond_transfer,
    ),
}

# ── Synthesizer classes ───────────────────────────────────────────────────────


class BankingAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="banking_agent",
            description="LLM agent executes banking intents via Banking APIs",
            tool_registry=BANKING_TOOL_REGISTRY,
            intents=BANKING_INTENTS,
            env_name="Retail Banking",
        )


class BankingGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "OPEN_ACCOUNT": {"open_account"},
        "DEPOSIT": {"deposit"},
        "WITHDRAW": {"withdraw"},
        "TRANSFER": {"transfer"},
    }

    def __init__(self) -> None:
        super().__init__(
            name="banking_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task."
            ),
            tool_registry=BANKING_TOOL_REGISTRY,
            bootstrap_intents=BANKING_INTENTS,
            env_name="Retail Banking",
        )

    def _init_evolution(self) -> None:
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "banking"
        runs_root.mkdir(parents=True, exist_ok=True)

        store = TrajectoryStore(runs_root / "trajectories.db")
        analyzer = TrajectoryAnalyzer(
            model=MODEL,
            base_url=PROXY_BASE_URL,
            api_key="anything",
        )
        engine = EvolutionEngine(store=store, analyzer=analyzer)

        library_path = runs_root / "intent_library.json"
        if library_path.exists():
            library = IntentLibrary.load(library_path)
        else:
            library = IntentLibrary()
            for name, intent_def in BANKING_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path
