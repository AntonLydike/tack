"""
Handles the writing/reading of the markdown files
"""

import os
from dataclasses import dataclass

import yaml
from collections.abc import Iterable, Iterator
from typing import Callable

from tack import db


@dataclass
class MarkdownFile:
    path: str
    meta: dict
    title: str
    """
    Paper title
    """

    abstract: str | None
    """
    Paper abstract, if present
    """

    notes: str | None
    """
    users notes
    """

    references: list[str]
    """
    References, if present
    """


def read_markdown(doi: str) -> MarkdownFile | None:
    folder = db.get_paper_dir()
    agency, id = doi.split("/", maxsplit=1)
    path = os.path.join(folder, agency, f"{id}.md")

    if not os.path.exists(path):
        return None

    with open(path, "r") as f:
        return MarkdownLinesParser(path, f).parse()


class Peekable(Iterator[str]):
    wrapped: Iterator[str]
    next: str | None

    def __init__(self, wrap: Iterator[str]):
        self.wrapped = wrap
        self.next = None

    def __next__(self) -> str:
        if self.next is not None:
            next_item = self.next
            self.next = None
        else:
            next_item = next(self.wrapped)

        return next_item

    def peek(self) -> str | None:
        if self.next is None:
            try:
                self.next = next(self.wrapped)
            except StopIteration:
                pass
        return self.next


class ParseError(ValueError):
    pass


class MarkdownLinesParser:
    lines: Peekable
    fname: str

    def __init__(self, fname: str, lines: Iterable[str]):
        self.lines = Peekable(iter(lines))
        self.fname = fname

    def parse(self):
        meta = self.parse_meta()
        title = self.parse_title()
        abstract = self.parse_abstract()
        notes = self.parse_notes()
        refs = self.parse_references()

        return MarkdownFile(
            self.fname,
            meta,
            title,
            abstract,
            notes,
            refs,
        )

    def parse_meta(self):
        if not self.lines.peek().startswith("---"):
            return {}
        # eat leading ---
        next(self.lines)
        meta = self._take_while(lambda x: not x.startswith("---"))
        # eat trailing ---
        next(self.lines)
        return yaml.safe_load("\n".join(meta))

    def parse_title(self) -> str:
        # eat empty lines
        self._take_empty()

        if not self.lines.peek().strip().startswith("# "):
            raise ParseError(f"Expected title here, got: {self.lines.peek()}")

        return next(self.lines).removeprefix("# ").strip('\n')

    def parse_abstract(self) -> str | None:
        self._take_empty()
        if not self.lines.peek().strip().startswith("## Abstract"):
            return None
        # eat hading
        next(self.lines)
        abstract = self._take_while(lambda x: not x.strip().startswith("## "))
        return "\n".join(abstract).strip('\n')

    def parse_notes(self) -> str | None:
        self._take_empty()
        if not self.lines.peek().strip().startswith("## Notes"):
            raise ParseError(f"Expected notes, got {self.lines.peek()}")

        # eat hading
        next(self.lines)
        notes = self._take_while(lambda x: not x.strip().startswith("## "))
        return "\n".join(notes).strip('\n')

    def parse_references(self) -> list[str]:
        self._take_empty()
        if not self.lines.peek().strip().startswith("## References"):
            raise ParseError(f"Expected References, got {self.lines.peek()}")
        # eat heading
        next(self.lines)

        references = self._take_while(lambda x: x is not None and x.strip().startswith("- "))
        return references

    def _take_while(self, pred: Callable[[str], bool]):
        parts = []
        while pred(self.lines.peek()):
            parts.append(next(self.lines))

        return parts

    def _take_empty(self):
        self._take_while(lambda x: not x.strip())
