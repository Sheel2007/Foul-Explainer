"""Add or update a clip's label.

Usage:
  uv run python -m foulcheck.eval.label 2.mp4 --verdict foul --card yellow --restart direct_free_kick \\
      --sections 12.1,12.4 --difficulty clear --source "league review panel"
  uv run python -m foulcheck.eval.label 2.mp4 --contact 1.3,3.8,5.9 --contact-source "checked frame by frame"
  uv run python -m foulcheck.eval.label --list
"""

import argparse
import sys
from typing import get_args

from foulcheck.decision.schema import Card, Restart, Verdict
from foulcheck.eval.labels import Label, list_labels, load_label, save_label


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m foulcheck.eval.label")
    ap.add_argument("clip", nargs="?")
    ap.add_argument("--verdict", choices=get_args(Verdict))
    ap.add_argument("--card", choices=get_args(Card))
    ap.add_argument("--restart", choices=get_args(Restart))
    ap.add_argument("--sections", help="comma-separated Law sections a correct answer must cite")
    ap.add_argument("--difficulty", choices=["clear", "hard"])
    ap.add_argument("--source", help="where the ruling label came from")
    ap.add_argument("--contact", help="comma-separated contact times in seconds, one per view")
    ap.add_argument("--contact-source")
    ap.add_argument("--notes")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for lb in list_labels():
            print(f"{lb.clip}: verdict={lb.verdict} card={lb.card} restart={lb.restart} "
                  f"sections={lb.required_sections} difficulty={lb.difficulty} contact={lb.contact_times}")
        return 0
    if not args.clip:
        ap.error("clip is required unless --list")

    label = load_label(args.clip)
    updates = {k: v for k, v in {
        "verdict": args.verdict, "card": args.card, "restart": args.restart, "difficulty": args.difficulty,
        "ruling_source": args.source, "contact_source": args.contact_source, "notes": args.notes,
        "required_sections": args.sections and [s.strip() for s in args.sections.split(",")],
        "contact_times": args.contact and [float(t) for t in args.contact.split(",")],
    }.items() if v is not None}
    label = label.model_copy(update=updates)
    print(f"Saved {save_label(Label.model_validate(label.model_dump()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
