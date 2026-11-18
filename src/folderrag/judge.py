"""Unified judging of every condition's final answers (preregistration §5).

Global context: ArcticSwarm's eval runner has its own judges, but baselines run
outside it, so all conditions are re-judged here with one judge model
(``claude-haiku-5-5``) and identical prompts, which keeps the paired comparisons
fair. Each judgement (prompt + raw output) is written to the results JSONL.

* MultiHop-RAG: the FINAL ANSWER line is extracted and judged for strict semantic
  equivalence with the short gold answer (JSON structured output); normalized exact
  match and the official word-overlap metric are computed deterministically.
  The official metric (MultiHop-RAG ``qa_evaluate.py``) counts a hit if any
  lowercased gold word occurs in the response; it is reported only to show its
  inflation (see reports/literature-review.md).
* SWE-QA: the paper's 5-dimension rubric prompt (copied verbatim, Apache-2.0) is
  applied to the full response; total = sum of five 1-20 scores (0-100 scale).
"""

from __future__ import annotations

import json
import logging
import os
import re
import string
import time
from pathlib import Path
from typing import Any

import anthropic

from folderrag.settings import JUDGE_MODEL

log = logging.getLogger(__name__)
_PROMPTS = Path(__file__).parent / "prompts"
_FINAL_RE = re.compile(r"FINAL ANSWER:\s*(.+)", re.IGNORECASE)

MHR_JUDGE_PROMPT = """You are grading a question-answering system against a gold answer.

Question: {question}
Gold answer: {gold}
System's final answer: {candidate}

Decide whether the system's final answer is semantically equivalent to the gold answer.
Rules:
- Yes/No questions: correct only if the polarity matches.
- Entity answers: correct if it names the same entity (minor spelling, titles or
  qualifiers are fine; a different or additional wrong entity is incorrect).
- "Insufficient information" gold: correct only if the system says the information
  is not available / cannot be determined.
- before/after or other short labels: must match.
- A hedge listing several options is incorrect.
Return JSON."""

_MHR_SCHEMA = {
    "type": "object",
    "properties": {"correct": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["correct", "reason"],
    "additionalProperties": False,
}
_SWEQA_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "integer"} for k in ("correctness", "completeness", "relevance", "clarity", "reasoning")},
    "required": ["correctness", "completeness", "relevance", "clarity", "reasoning"],
    "additionalProperties": False,
}


def client() -> anthropic.Anthropic:
    """Anthropic client with the workspace header the API key requires (see probe)."""
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID", "")
    return anthropic.Anthropic(max_retries=8, default_headers={"anthropic-workspace-id": ws} if ws else None)


def extract_final(text: str) -> str:
    """Last ``FINAL ANSWER:`` line (markdown emphasis/backticks stripped), or ''."""
    matches = _FINAL_RE.findall(text or "")
    if not matches:
        return ""
    return matches[-1].strip().strip("*`_ ").strip()


def normalize(s: str) -> str:
    """SQuAD-style normalisation: lowercase, drop punctuation/articles, squash spaces."""
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def exact_match(candidate: str, gold: str) -> bool:
    """Normalized EM; yes/no and 'insufficient information' match on the leading label."""
    c, g = normalize(candidate), normalize(gold)
    if not c:
        return False
    if g in ("yes", "no"):
        return c.split()[0] == g
    if g.startswith("insufficient information"):
        return c.startswith("insufficient information")
    return c == g


def official_overlap(response: str, gold: str) -> bool:
    """MultiHop-RAG qa_evaluate.py-style hit: any gold word appears in the response words."""
    resp_words = set(normalize(response).split())
    return any(w in resp_words for w in normalize(gold).split())


def _call_json(c: anthropic.Anthropic, prompt: str, schema: dict, effort: str = "medium") -> tuple[dict | None, str, dict]:
    """One judge call with JSON structured output; returns (parsed, raw_text, usage)."""
    for attempt in range(3):
        try:
            r = c.messages.create(
                model=JUDGE_MODEL, max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}}},
            )
            raw = "".join(b.text for b in r.content if b.type == "text")
            usage = {"input": r.usage.input_tokens, "output": r.usage.output_tokens}
            if r.stop_reason == "refusal":
                return None, f"[refusal] {raw}", usage
            return json.loads(raw), raw, usage
        except (anthropic.APIStatusError, anthropic.APIConnectionError, json.JSONDecodeError) as exc:
            log.warning("judge call failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(5 * (attempt + 1))
    return None, "[judge failed]", {}


def judge_mhr(c: anthropic.Anthropic, question: str, gold: str, response: str) -> dict[str, Any]:
    final = extract_final(response)
    out: dict[str, Any] = {
        "final_answer": final,
        "exact_match": exact_match(final, gold),
        "official_overlap": official_overlap(response, gold),
    }
    if not final:  # missing FINAL ANSWER line counts as incorrect (prereg §5)
        out.update(judge_correct=False, judge_reason="no FINAL ANSWER line", judge_prompt="", judge_raw="")
        return out
    prompt = MHR_JUDGE_PROMPT.format(question=question, gold=gold, candidate=final)
    parsed, raw, usage = _call_json(c, prompt, _MHR_SCHEMA)
    out.update(judge_correct=bool(parsed and parsed.get("correct")),
               judge_reason=(parsed or {}).get("reason", raw), judge_prompt=prompt, judge_raw=raw,
               judge_usage=usage)
    return out


def judge_sweqa(c: anthropic.Anthropic, question: str, reference: str, response: str) -> dict[str, Any]:
    tmpl = (_PROMPTS / "sweqa_judge.txt").read_text(encoding="utf-8").split("---\n", 1)[1]
    prompt = tmpl.format(question=question, reference=reference, candidate=response or "(empty)")
    parsed, raw, usage = _call_json(c, prompt, _SWEQA_SCHEMA)
    scores = {k: max(1, min(20, int(parsed[k]))) for k in _SWEQA_SCHEMA["required"]} if parsed else {}
    return {
        "final_answer": extract_final(response),
        "sweqa_scores": scores,
        # 0 when judging failed or the response is empty (prereg §6: failures score 0).
        "sweqa_total": sum(scores.values()) if (scores and (response or "").strip()) else 0,
        "judge_prompt": prompt, "judge_raw": raw, "judge_usage": usage,
    }


def judge_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Judge rows with keys id/dataset/question/answer/response (adds judge fields)."""
    c = client()
    out = []
    for r in rows:
        if r["dataset"] == "MULTIHOPRAG":
            j = judge_mhr(c, r["question"], r["answer"], r.get("response", ""))
        else:
            j = judge_sweqa(c, r["question"], r["answer"], r.get("response", ""))
        log.info("judged %s: %s", r["id"], {k: v for k, v in j.items() if k in ("judge_correct", "exact_match", "sweqa_total")})
        out.append({**r, **j})
    return out
