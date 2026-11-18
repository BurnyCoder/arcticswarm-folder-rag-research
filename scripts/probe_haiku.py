"""Phase-0 probe: which Messages-API request shapes does claude-haiku-5-5 accept?

Global context
--------------
ArcticSwarm was written for Claude Sonnet 4.5 / Opus 4.6 and GPT-5. Before patching its
LLM client for Claude Haiku 5.5 we measure, with real (cheap) API calls, which request
shapes the model accepts, so every patch is grounded in observed behaviour rather than
assumptions. The Haiku 5.5 rules being tested come from Anthropic's model-migration guide
(claude-api skill, "Migrating to Claude Haiku 5.5"): budget_tokens thinking -> 400,
non-default sampling params -> 400, adaptive thinking on by default, and a
history-editing check on replayed thinking blocks.

Each probe prints PASS/FAIL plus the HTTP error text and appends the full request and
response to a timestamped JSONL log under logs/ (prompts/outputs are never truncated).

Run: uv run python scripts/probe_haiku.py
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import anthropic  # official SDK (pinned to ArcticSwarm's validated 0.109.0)
from dotenv import load_dotenv  # reads ANTHROPIC_API_KEY from the project .env

MODEL = "claude-haiku-5-5"  # current-generation Haiku (claude-api skill model table)
ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / f"probe_haiku_{dt.datetime.now():%Y%m%d_%H%M%S}.jsonl"

# A tiny tool so we can exercise a real tool-use loop with thinking blocks.
TOOLS = [{
    "name": "lookup_file",
    "description": "Return the contents of a file in the local folder by relative path.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Relative file path."}},
        "required": ["path"],
    },
}]
FAKE_FILE = "notes/plan.md:\nThe project codename is BLUE HERON. Launch date: 2026-12-01."


def log(record: dict[str, Any]) -> None:
    """Append one probe record (request + response/error) to the JSONL log."""
    record["ts"] = dt.datetime.now().isoformat()
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def call(client: anthropic.Anthropic, name: str, **kwargs: Any) -> Any | None:
    """Make one Messages call; print PASS/FAIL and log full request/response."""
    try:
        resp = client.messages.create(model=MODEL, **kwargs)
        types = [b.type for b in resp.content]
        print(f"PASS  {name}: stop={resp.stop_reason} blocks={types} usage_in={resp.usage.input_tokens} out={resp.usage.output_tokens}")
        log({"probe": name, "request": kwargs, "response": resp.model_dump()})
        return resp
    except anthropic.APIStatusError as exc:  # 4xx/5xx with a body
        print(f"FAIL  {name}: HTTP {exc.status_code}: {exc.message[:300]}")
        log({"probe": name, "request": kwargs, "error": {"status": exc.status_code, "message": exc.message}})
        return None


def strip_thinking(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove thinking/redacted_thinking blocks from every assistant turn."""
    out = copy.deepcopy(messages)
    for m in out:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            m["content"] = [b for b in m["content"] if b.get("type") not in ("thinking", "redacted_thinking")]
    return out


def main() -> int:
    load_dotenv(ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY missing (expected in .env)")
        return 2
    # Keys that are not scoped to a workspace must name one via the
    # anthropic-workspace-id header (observed 400 otherwise); .env supplies it.
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID", "")
    client = anthropic.Anthropic(max_retries=4, default_headers={"anthropic-workspace-id": ws} if ws else None)
    print(f"anthropic SDK {anthropic.__version__}; model {MODEL}; log -> {LOG_PATH}")

    q = [{"role": "user", "content": "In one sentence: what is BM25?"}]
    # 1) Baseline: no thinking param (Haiku 5.5 runs adaptive thinking by default).
    call(client, "1_basic_no_thinking_param", max_tokens=2048, messages=q)
    # 2) Adaptive thinking + effort, sent the way ArcticSwarm sends effort (extra_body.output_config).
    call(client, "2_adaptive_effort_high", max_tokens=4096, thinking={"type": "adaptive"},
         extra_body={"output_config": {"effort": "high"}}, messages=q)
    # 3) What ArcticSwarm currently sends to non-Opus models: budget thinking (expected 400).
    call(client, "3_budget_tokens_expected_400", max_tokens=8192,
         thinking={"type": "enabled", "budget_tokens": 4000}, messages=q)
    # 4) Non-default temperature (expected 400; ArcticSwarm never sends it for Anthropic).
    call(client, "4_temperature0_expected_400", max_tokens=1024, temperature=0.0, messages=q)
    # 5) thinking disabled at effort medium (documented as accepted at <= high).
    call(client, "5_thinking_disabled_medium", max_tokens=1024, thinking={"type": "disabled"},
         extra_body={"output_config": {"effort": "medium"}}, messages=q)

    # 6) Tool loop with thinking replayed unchanged.
    sys_prompt = "You answer questions about a local folder. Use lookup_file to read files."
    msgs: list[dict[str, Any]] = [{"role": "user", "content": "What is the project codename? Read notes/plan.md."}]
    r1 = call(client, "6a_tool_call_turn", max_tokens=4096, system=sys_prompt, tools=TOOLS,
              thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=msgs)
    if r1 is None or r1.stop_reason != "tool_use":
        print("tool loop could not start; stopping")
        return 1
    tool_use = next(b for b in r1.content if b.type == "tool_use")
    msgs.append({"role": "assistant", "content": [b.model_dump() for b in r1.content]})
    msgs.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": FAKE_FILE}]})
    has_thinking = any(b.type == "thinking" for b in r1.content)
    print(f"      turn-1 assistant has thinking block: {has_thinking}")
    call(client, "6b_tool_result_replay_unchanged", max_tokens=4096, system=sys_prompt, tools=TOOLS,
         thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=msgs)

    # 7) Replay after editing an EARLIER turn (what compaction/clear_history does) with thinking kept.
    edited = copy.deepcopy(msgs)
    edited[0]["content"] = "[compacted] What is the project codename? Read notes/plan.md."
    call(client, "7_edit_earlier_turn_keep_thinking", max_tokens=4096, system=sys_prompt, tools=TOOLS,
         thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=edited)
    # 8) Same edit, thinking blocks stripped (mitigation candidate).
    call(client, "8_edit_earlier_turn_strip_thinking", max_tokens=4096, system=sys_prompt, tools=TOOLS,
         thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=strip_thinking(edited))
    # 9) Changed system prompt (ArcticSwarm injects skills / budget notices) with thinking kept.
    call(client, "9_changed_system_keep_thinking", max_tokens=4096, system=sys_prompt + "\nBudget notice: wrap up.",
         tools=TOOLS, thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=msgs)
    # 10) Unchanged history but thinking omitted on the latest assistant turn.
    call(client, "10_unchanged_strip_thinking", max_tokens=4096, system=sys_prompt, tools=TOOLS,
         thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=strip_thinking(msgs))
    # 11) Synthetic assistant tool_use turn with no thinking (agent.py injects BBS updates this way).
    synth = copy.deepcopy(msgs) + [
        {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_synthetic01", "name": "lookup_file", "input": {"path": "notes/other.md"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_synthetic01", "content": "BBS update: a teammate confirmed the launch date."}]},
    ]
    r11 = call(client, "11_synthetic_tool_turn_no_thinking", max_tokens=4096, system=sys_prompt, tools=TOOLS,
               thinking={"type": "adaptive"}, extra_body={"output_config": {"effort": "medium"}}, messages=synth)

    # 12-14) History-editing check with a REAL thinking block in the replayed history.
    # Probes 7/9 only test it if turn 1 happened to think; adaptive thinking often skips
    # thinking on easy turns, so here we reuse r11's response, which (if it thought)
    # contains a thinking block, then (12) append-only follow-up, (13) edit an earlier
    # turn while keeping the thinking block, (14) same edit with thinking stripped.
    if r11 is not None and any(b.type == "thinking" for b in r11.content):
        hist = synth + [
            {"role": "assistant", "content": [b.model_dump() for b in r11.content]},
            {"role": "user", "content": "Now also tell me the launch date, citing the file."},
        ]
        kw = dict(max_tokens=4096, system=sys_prompt, tools=TOOLS, thinking={"type": "adaptive"},
                  extra_body={"output_config": {"effort": "medium"}})
        call(client, "12_append_only_keep_real_thinking", messages=hist, **kw)
        hist_edit = copy.deepcopy(hist)
        hist_edit[0]["content"] = "[compacted summary] User asked for the codename in notes/plan.md."
        call(client, "13_edit_earlier_keep_real_thinking", messages=hist_edit, **kw)
        call(client, "14_edit_earlier_strip_real_thinking", messages=strip_thinking(hist_edit), **kw)
        hist_sys = dict(kw, system=sys_prompt + "\nBudget notice: wrap up now.")
        call(client, "15_changed_system_keep_real_thinking", messages=hist, **hist_sys)
    else:
        print("SKIP  12-15: r11 produced no thinking block; history-editing check not exercised")
    print(f"log written to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
