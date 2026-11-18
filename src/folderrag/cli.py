"""``folderrag`` — one wrapper CLI that calls the harness phases in order.

    folderrag sandbox            # configure + verify the WSL tool sandbox
    folderrag prepare            # build corpora folders + the day-1 sample
    folderrag run M [--tag day1] [--limit K] [--folders a b]   # ArcticSwarm swarm
    folderrag run B2 ...                                       # single-agent baseline
    folderrag ask "question" --folder D:\docs [--mode M|B2]   # any folder of your own
    folderrag judge --tag day1   # unified judge for every condition found
    folderrag analyze --tag day1 # metrics, tests, tables, figures (results/)
"""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout)
    ap = argparse.ArgumentParser(prog="folderrag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sandbox")
    sub.add_parser("prepare")
    r = sub.add_parser("run")
    r.add_argument("condition", help="M | B2 | M_capN (swarm with at most N subagents)")
    r.add_argument("--tag", default="day1")
    r.add_argument("--limit", type=int, default=None, help="first K questions per folder (smoke tests)")
    r.add_argument("--folders", nargs="*", default=None)
    q = sub.add_parser("ask", help="answer one question over any local folder")
    q.add_argument("question")
    q.add_argument("--folder", required=True)
    q.add_argument("--mode", default="M", help="M (swarm, default) | B2 (single agent, ~50x cheaper) | M_capN")
    for name in ("judge", "analyze"):
        p = sub.add_parser(name)
        p.add_argument("--tag", default="day1")
    a = ap.parse_args(argv)

    if a.cmd == "sandbox":
        from folderrag import sandbox
        sandbox.setup()
        print(sandbox.check_isolation())
    elif a.cmd == "prepare":
        from folderrag.datasets import prepare_all
        prepare_all()
    elif a.cmd == "run":
        from folderrag.run import run_condition
        run_condition(a.condition, tag=a.tag, limit_per_folder=a.limit, folders=a.folders)
    elif a.cmd == "ask":
        from folderrag.run import ask
        answer = ask(a.question, a.folder, a.mode)
        print("\n===== ANSWER =====\n" + answer)
    elif a.cmd == "judge":
        from folderrag.collect import judge_tag
        judge_tag(a.tag)
    elif a.cmd == "analyze":
        from folderrag.analyze import analyze_tag
        analyze_tag(a.tag)


if __name__ == "__main__":
    main()
