"""
Helpers for autocompletions.

Aimed at being as fast as possible, not importing all the other things.
"""

import json
import sys

from tack import db


def list_papers(mode: str):
    with db.cursor() as cur:
        results = cur.execute(
            "SELECT doi, title, year, conference FROM papers"
        ).fetchall()
    segments = ("doi", "title", "year", "conference")

    if mode == "csv":
        print("doi,title,yera,conference")
        print(
            "\n".join(f'doi,"{title}",{year},"{conf}"')
            for doi, title, year, conf in results
        )
    elif mode == "json":
        json.dump([dict(zip(segments, line)) for line in results], sys.stdout)
    elif mode == "jsonl":
        for line in results:
            print(json.dumps(dict(zip(segments, line))))


def main():
    if len(sys.argv) < 2:
        print("Usage: list (json|csv|jsonl)")
        sys.exit(1)

    name, func, *args = sys.argv
    if func == "list" and len(args) == 1:
        list_papers(*args)
    else:
        print("unknown cmd")
        sys.exit(1)


if __name__ == "__main__":
    main()
