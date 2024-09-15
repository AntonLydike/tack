import os.path
import re

import yaml

from tack import db
from tack.api import BaseAPI, CrossRefApi
from tack.colors import FMT
from crossref.restful import Works, Etiquette


class CLI:
    _name: str
    _api: BaseAPI

    def __init__(self, name: str = "tack"):
        self._name = name
        self._api = CrossRefApi()

    def add(self, doi: str):
        print(f"fetching {doi}...")
        paper = self._api.paper_by_doi(doi)
        if paper is None:
            print(
                f'{FMT.RED | FMT.BOLD}Error: Could not locate work with doi "{doi}"{FMT.RESET}'
            )
            return
        else:
            print(
                f'found it on {self._api.API_NAME}, title "{paper.title}"! inserting....'
            )

        new_paper = db.add_paper(paper)

        if new_paper:
            db.add_authors(doi, self._api.authors_of_paper(doi))

            print("fetching citations...")

            db.add_citations(doi, self._api.citations_by_doi(doi))
        else:
            print("Existing paper, not adding authors and citations to db...")

        print("generating doc...")
        self.create_note(doi)

    def migrate_db(self):
        db.migrate()

    def create_note(self, doi: str):
        repo_dir = db.get_paper_dir()
        agency, number = doi.split('/', 1)
        os.makedirs(os.path.join(repo_dir, agency), exist_ok=True)

        with db.cursor() as cur:
            paper = cur.execute(
                "SELECT `title`, `conference`, `year`, `abstract`, `url` FROM papers WHERE `doi` = ?",
                (doi,),
            ).fetchone()
            if not paper:
                print(
                    f'{FMT.RED | FMT.BOLD}Error: Could not locate work with doi "{doi}"{FMT.RESET}'
                )
                return
            title, conference, year, abstract, url = paper

        authors = db.get_authors(doi)

        with open(os.path.join(repo_dir, agency, f"{number}.md"), "w") as f:
            yaml_str = yaml.safe_dump(
                build_paper_meta_dict(
                    doi,
                    title,
                    year,
                    conference,
                    authors,
                    url,
                )
            )
            f.write(f"""---\n{yaml_str}\n---""")
            f.write(f"\n# {title}")

            if abstract:
                f.write("\n## Abstract\n")
                f.write(abstract)
            f.write("\n## Notes\n")
            f.write("\n## References\n")
            for cite in db.get_paper_citations(doi):
                suffix = " ("
                if cite.author:
                    suffix += f"{cite.author} et. al. "
                if cite.journal:
                    suffix += f"at {cite.journal} "
                if cite.year:
                    suffix += f"- {cite.year}"
                if suffix == " (":
                    suffix = ""
                else:
                    suffix += ")"

                if cite.doi:
                    fancy = ""
                    if cite.title:
                        fancy = f"|{cite.title}"
                    f.write(f"- [[{cite.doi}{fancy}]]{suffix}\n")
                elif cite.title:
                    f.write(f"- {cite.title}{suffix}\n")
        print("Generated paper entry!")

    def remove(self, doi: str):
        with db.cursor() as cur:
            cur.execute("DELETE FROM paper_authors WHERE doi = ?", (doi,))
            cur.execute("DELETE FROM tags WHERE doi = ?", (doi, ))
            cur.execute("DELETE FROM cites WHERE source_doi = ?", (doi, ))
            cur.execute("DELETE FROM papers WHERE doi = ?", (doi, ))

        print("Removed paper from db, not removing local file though.")

    def list(self):
        with db.cursor() as cur:
            cur.execute("SELECT doi, title, conference, year FROM papers")

            while batch := cur.fetchmany(100):
                for line in batch:
                    doi, title, conference, year = [
                        x if x is not None else "-" for x in line
                    ]
                    print(f"{doi:<32} | {conference:<25} | {year:>4} | {title}")

    def run(self, cmd: str, *args: str) -> int:
        match (cmd, args):
            case ("migrate", []):
                self.migrate_db()
                return 0
            case ("add", [doi]):
                self.add(doi)
                return 0
            case ("remove", [doi]):
                self.remove(doi)
                return 0
            case ("delete", [doi]):
                self.remove(doi)
                return 0
            case ("list", _):
                self.list()
                return 0
            case ("help", _):
                CLI.help()
                return 0

        print("unknown command")
        return 1

    @classmethod
    def help(self):
        pass


def build_paper_meta_dict(
    doi: str,
    title: str,
    year: int | str,
    conference: str | None,
    authors: list[db.AuthorOfPaper],
    url: str | None,
) -> dict:
    with db.cursor() as cur:
        extra_tags = cur.execute(
            "SELECT `name`, `value` FROM tags WHERE `doi` = ?", (doi,)
        ).fetchall()
    return {
        "aliases": [title],
        "year": int(year),
        "conference": conference,
        "authors": [a.name for a in authors],
        "url": url,
        **dict(extra_tags),
    }


def main():
    import sys
    if len(sys.argv) < 2:
        CLI.help()
        sys.exit(1)

    name, cmd, *args = sys.argv

    sys.exit(
        CLI(name).run(cmd, *args)
    )
