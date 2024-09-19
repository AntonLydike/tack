import json
import os.path
import shutil

from tack import db
from tack.api import BaseAPI, CrossRefApi
from tack.colors import FMT
from tack.docs import MarkdownFile, write_markdown, build_refs, read_markdown
from tack.helpers import path_safe_doi, normalize_doi
import argparse


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
            authors = self._api.authors_of_paper(doi)

            for author in authors:
                if author.orcid is None:
                    matches = db.similar_authors(author.name)
                    if not matches:
                        continue
                    print(
                        f"No ORCID associated with {author.name}, but possible matches found in local database:"
                    )
                    last_id = -1
                    idx_to_author_id = {}
                    for id, name, title, year in matches:
                        if last_id != id:
                            idx_to_author_id[len(idx_to_author_id) + 1] = id
                            print(f"({len(idx_to_author_id)}): {name}")
                        print(f"  {title} ({year})")
                    selection = input(
                        "\nSelect author id, or press enter to create a new author:"
                    )
                    if not selection:
                        continue
                    if int(selection) not in idx_to_author_id:
                        print("Invalid ID entered.")
                    author.id = idx_to_author_id[int(selection)]

            db.add_authors(doi, authors)

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
        agency, number = path_safe_doi(doi)
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

        doc = MarkdownFile(
            os.path.join(repo_dir, agency, f"{number}.md"),
            build_paper_meta_dict(
                doi,
                title,
                year,
                conference,
                authors,
                url,
            ),
            title,
            abstract,
            "",
            list(build_refs(db.get_paper_citations(doi))),
        )

        # don't overwrite added metadata and notes
        if (existing_doc := read_markdown(doc.path)) is not None:
            print("loading notes and metadata from existing doc...")
            doc.notes = existing_doc.notes
            doc.meta = {**existing_doc.meta, **doc.meta}

        write_markdown(doc)

        print("Generated paper entry!")

    def remove(self, doi: str):
        with db.cursor() as cur:
            cur.execute("DELETE FROM paper_authors WHERE doi = ?", (doi,))
            cur.execute("DELETE FROM tags WHERE doi = ?", (doi,))
            cur.execute("DELETE FROM cites WHERE source_doi = ?", (doi,))
            cur.execute("DELETE FROM papers WHERE doi = ?", (doi,))
            # delete trailing authors
            cur.execute(
                "DELETE FROM authors WHERE orcid is null and id not in (SELECT author_id FROM paper_authors)"
            )

        print("Removed paper from db, not removing local file though.")

    def list(self, args: list[str]):
        parser = argparse.ArgumentParser("tack list")
        parser.add_argument("--json", action="store_true")
        opts = parser.parse_args(args)

        with db.cursor() as cur:
            cur.execute("SELECT doi, title, conference, year FROM papers")

            while batch := cur.fetchmany(100):
                for line in batch:
                    doi, title, conference, year = [
                        x if x is not None else "-" for x in line
                    ]
                    if opts.json:
                        print(
                            json.dumps(
                                dict(
                                    doi=doi,
                                    conference=conference,
                                    year=year,
                                    title=title,
                                )
                            )
                        )
                    else:
                        print(f"{doi:<32} | {conference:<25} | {year:>4} | {title}")

    def run(self, cmd: str, *args: str) -> int:
        match (cmd, args):
            case ("migrate", []):
                self.migrate_db()
                return 0
            case ("add", [doi]):
                self.add(normalize_doi(doi))
                return 0
            case ("remove", [doi]):
                self.remove(normalize_doi(doi))
                return 0
            case ("delete", [doi]):
                self.remove(normalize_doi(doi))
                return 0
            case ("list", args):
                self.list(args)
                return 0
            case ("read-md", [doi]):
                self.read_md(normalize_doi(doi))
                return 0
            case ("pdf", [doi, path]):
                self.add_pdf(normalize_doi(doi), path)
            case ("grep", args):
                import subprocess

                subprocess.run(
                    ["rg", *args],
                    cwd=db.get_paper_dir(),
                )
                return 0
            case ("git", args):
                import subprocess

                subprocess.run(
                    ["git", *args],
                    cwd=db.get_paper_dir(),
                )
                return 0
            case ("help", _):
                CLI.help()
                return 0

        print("unknown command")
        return 1

    @classmethod
    def help(self):
        pass

    def read_md(self, doi: str):
        repo_dir = db.get_paper_dir()
        agency, number = path_safe_doi(doi)
        fpath = os.path.join(repo_dir, agency, f"{number}.md")
        doc = read_markdown(fpath)

        if doc is None:
            print(
                f'{FMT.RED | FMT.BOLD}Error: Could not locate file at "{fpath}"{FMT.RESET}'
            )
            return

        with db.cursor() as cur:
            cur.execute(
                "UPDATE papers SET title = ?, conference = ?, year = ?, abstract = ?, url = ? WHERE doi = ?",
                (
                    doc.title,
                    doc.meta["conference"],
                    doc.meta["year"],
                    doc.abstract,
                    doc.meta["url"],
                    doi,
                ),
            )
            non_special_attrs = {"aliases", "authors", "conference", "year", "url"}
            cur.execute("DELETE FROM tags WHERE doi = ?", (doi,))

            for key, val in doc.meta.items():
                if key in non_special_attrs:
                    continue
                cur.execute(
                    "INSERT OR REPLACE INTO tags (`doi`, `name`, `value`) VALUES (?,?,?)",
                    (doi, key, json.dumps(val)),
                )
                print(f"Read metadata {key} = {val}")

    def add_pdf(self, doi, path):
        agency, number = path_safe_doi(doi)
        dest = db.get_paper_dir()
        os.makedirs((os.path.join(dest, 'pdf')), exist_ok=True)
        shutil.copy(path, os.path.join(dest, "pdf", f"{agency}_{number}.pdf"))
        with db.cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO tags (doi, name, value) VALUES (?,?,?)",
                (doi, "pdf", f'"[[pdf/{agency}_{number}.pdf]]"'),
            )
        self.create_note(doi)


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
        **dict((k, json.loads(v)) for k, v in extra_tags),
    }


def main():
    import sys

    if len(sys.argv) < 2:
        CLI.help()
        sys.exit(1)

    name, cmd, *args = sys.argv

    sys.exit(CLI(name).run(cmd, *args))
