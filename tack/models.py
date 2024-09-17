from dataclasses import dataclass

@dataclass
class AuthorOfPaper:
    id: int | None
    orcid: str
    name: str
    affiliation: str


@dataclass
class Citation:
    title: str | None
    journal: str | None
    doi: str | None
    year: int | str | None
    author: str | None


@dataclass
class Paper:
    doi: str
    title: str
    conference: str | None
    year: int | None
    abstract: str | None
    url: str | None



@dataclass
class CachedResponse:
    id: str
    meta: str | None
    timestamp: int
    response: str
