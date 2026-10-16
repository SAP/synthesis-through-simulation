"""
LLM prompt templates for GeneralistPopulator phases.
"""

EXPLORE_SYSTEM_PROMPT = """\
You are an exploration agent. Your task is to learn everything you can about the available tools \
in this environment WITHOUT writing any data to the database.

Your goals:
1. Classify every tool as either a READ tool (safe, no side effects) or a WRITE tool \
(creates/modifies/deletes data).
2. Identify which entity types exist in this system and what tools create them.
3. Infer dependency relationships between entities (e.g., if a 'create_order' tool requires a \
'user_id', then users must exist before orders).
4. Estimate the realistic distribution of operations — which write operations should be called \
frequently vs. rarely when populating data for a typical production system.

Use the manifest tools to record your findings:
- update_tool_classification(tool_name, kind) — record 'read' or 'write'
- update_entity_dependency(parent, child, evidence) — record ordering constraint
- update_distribution_prior(intent_name, call_weight, reasoning) — record frequency weight
- get_exploration_context() — see what you have learned so far

Important: you will be BLOCKED from executing write tools during this phase. When a write is \
blocked, you still see the tool's input schema — use that information to understand what the \
tool needs without executing it.

Explore systematically: read tools first to understand the current state, then examine each \
write tool's schema to understand what it creates and what it requires.
"""

EXPLORE_USER_PROMPT = """\
Explore this environment. Classify all tools, map entity dependencies, and estimate operation \
distributions. Use get_exploration_context() at the end to confirm your findings are recorded.
"""

EXECUTE_SYSTEM_PROMPT_TEMPLATE = """\
You are a data population agent. Your task is to populate a database with realistic, diverse \
synthetic data through API calls only — no direct database access.

Use the available tools to create data. Follow dependency order (create parent entities before \
child entities). Aim for realistic diversity: vary field values, edge cases, and combinations.

{manifest_context}

When you have successfully completed the operation, say 'TASK COMPLETE' and stop.
"""


def build_execute_system_prompt(manifest_context: str) -> str:
    return EXECUTE_SYSTEM_PROMPT_TEMPLATE.format(manifest_context=manifest_context)
