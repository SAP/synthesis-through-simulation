"""
Default (domain-agnostic) agent synthesizer.

Parameterized by tool_registry and intents — can be reused for any environment.
Subclass DefaultAgentSynthesizer and supply those two arguments to onboard a new domain.
"""

from __future__ import annotations

import argparse
import json
import random
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from synthesize.synthesizer.agent_synthesizer import (
    MAX_STEPS,
    MODEL,
    PROXY_BASE_URL,
    IntentDef,
    Step,
    Trajectory,
    _serialize,
)
from synthesize.synthesizer.base import SynthesisResult, Synthesizer


def _make_client() -> OpenAI:
    return OpenAI(base_url=PROXY_BASE_URL, api_key="anything")


def _tool_definition(name: str, tool_registry: dict) -> dict:
    entry = tool_registry[name]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": entry["description"],
            "parameters": entry["input_schema"],
        },
    }


def _call_tool(name: str, args: dict, tool_registry: dict) -> Tuple[Any, bool]:
    entry = tool_registry.get(name)
    if entry is None:
        return {"error": f"Unknown tool: {name}"}, True
    # Strip null values — LLMs often emit `"field": null` for optional params they
    # don't want to set, which would override function defaults with None.
    filtered = {k: v for k, v in args.items() if v is not None}
    try:
        raw = entry["fn"](**filtered)
        return _serialize(raw), False
    except (ValueError, LookupError) as exc:
        return {"error": str(exc)}, True
    except Exception as exc:
        return {"error": f"Unexpected error: {exc}"}, True


def _build_system_prompt(mode: str, intent_def: IntentDef, env_name: str) -> str:
    data_gen_context = (
        "Your purpose is to populate a realistic enterprise database with diverse, "
        "high-quality synthetic data through task execution. "
        "Execute the assigned task to completion, making whatever API calls are required — "
        "including creating, updating, or closing records as the task demands. "
        "Vary your choices (values, options, combinations) across runs to maximise dataset diversity. "
        "Do not always pick the same safe default — explore the full range of valid options.\n\n"
    )
    execution_reminder = (
        "IMPORTANT: You must actually call the write API — do not just describe what you would do. "
        "Gathering context is only preparation; the task is not complete until the required "
        "write/update/close operation has been executed via an API call.\n"
    )
    if mode == "blind":
        return (
            data_gen_context
            + f"You are a {env_name} agent. You will be given a task to complete by making "
            "API calls. You have no prior knowledge of the system's business rules — "
            "learn from the API's error responses and adjust your calls accordingly. "
            + execution_reminder
            + "When you have successfully completed the task, say 'TASK COMPLETE' and stop."
        )
    return (
        data_gen_context
        + f"You are a {env_name} agent. You will be given a task to complete by making "
        f"API calls. You have full knowledge of the relevant business rules:\n\n"
        + intent_def.informed_rules
        + "\n"
        + execution_reminder
        + "Make the required API calls to complete the task. "
        "When you have successfully completed the task, say 'TASK COMPLETE' and stop."
    )


def run_agent(
    intent_def: IntentDef,
    params: Dict[str, Any],
    mode: str,
    client: OpenAI,
    tool_registry: dict,
    env_name: str = "enterprise",
    system_prompt: Optional[str] = None,
) -> Trajectory:
    """Execute one intent run; return a recorded Trajectory."""
    assert mode in ("blind", "informed"), f"mode must be 'blind' or 'informed', got {mode!r}"

    system = (
        system_prompt
        if system_prompt is not None
        else _build_system_prompt(mode, intent_def, env_name)
    )
    task_prompt = intent_def.task_prompt(params)
    tools = [_tool_definition(t, tool_registry) for t in intent_def.tools]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task_prompt},
    ]
    steps: List[Step] = []

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=messages,
            tools=tools,
        )

        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "stop":
            break
        if choice.finish_reason != "tool_calls":
            break

        for tc in choice.message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result, is_error = _call_tool(tc.function.name, args, tool_registry)
            steps.append(Step(tool=tc.function.name, args=args, result=result, is_error=is_error))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    post = intent_def.postconditions(params, steps)
    success = bool(post) and all(post.values())

    traj = Trajectory(
        intent=intent_def.name,
        mode=mode,
        params=params,
        steps=steps,
        success=success,
        postconditions=post,
    )
    traj.compute_metrics()
    return traj


class DefaultAgentSynthesizer(Synthesizer):
    """
    Domain-agnostic agentic synthesizer.
    Supply tool_registry + intents to create an agent for any environment.
    """

    supports_batch = True

    def __init__(
        self,
        name: str,
        description: str,
        tool_registry: dict,
        intents: Dict[str, IntentDef],
        env_name: str = "enterprise",
    ) -> None:
        self.name = name
        self.description = description
        self.tool_registry = tool_registry
        self.intents = intents
        self.env_name = env_name

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        try:
            parser.add_argument(
                "--intent",
                help="Intent to run. If omitted in batch, cycles through all intents.",
            )
        except argparse.ArgumentError:
            pass
        try:
            parser.add_argument(
                "--mode",
                choices=["blind", "informed"],
                default="blind",
                help="blind: no rules in prompt; informed: full rules in prompt (default: blind)",
            )
        except argparse.ArgumentError:
            pass

    def params_from_args(self, args: argparse.Namespace) -> dict:
        return {
            "intent": getattr(args, "intent", None),
            "mode": getattr(args, "mode", "blind"),
        }

    def sample_params(
        self, intent: Optional[str] = None, mode: str = "blind", **kwargs
    ) -> Optional[dict]:
        intent_name = intent.upper() if intent else random.choice(list(self.intents.keys()))
        if intent_name not in self.intents:
            raise ValueError(f"Unknown intent: {intent_name!r}")
        run_params = self.intents[intent_name].sampler()
        if run_params is None:
            return None
        return {"intent": intent_name, "mode": mode, "run_params": run_params}

    def run(self, params: dict) -> SynthesisResult:
        seed = params.get("seed")
        if seed is not None:
            random.seed(seed)

        intent_name = (params.get("intent") or "").upper()
        if not intent_name:
            raise ValueError("params must include 'intent'")
        if intent_name not in self.intents:
            raise ValueError(f"Unknown intent: {intent_name!r}")

        mode = params.get("mode", "blind")
        intent_def = self.intents[intent_name]

        run_params = params.get("run_params")
        if run_params is None:
            run_params = intent_def.sampler()
            if run_params is None:
                raise ValueError(f"No eligible records in DB for intent {intent_name!r}")

        client = _make_client()
        traj = run_agent(intent_def, run_params, mode, client, self.tool_registry, self.env_name)

        return SynthesisResult(
            synthesizer=self.name,
            params={**params, "run_params": run_params},
            trajectories=[traj.to_dict()],
        )

    def list_intents(self) -> List[str]:
        return list(self.intents.keys())
