import json
import re
import sys
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import ClassVar
from concurrent.futures import ThreadPoolExecutor

import requests
from crossref.restful import Works, Etiquette

from tack.models import Paper, AuthorOfPaper, Citation
from tack.progress import ProgressBar
from tack import db, helpers


class BaseAPI(ABC):
    API_NAME: ClassVar[str]

    @abstractmethod
    def paper_by_doi(self, doi: str) -> Paper | None:
        raise NotImplementedError()

    @abstractmethod
    def citations_by_doi(self, doi: str) -> list[Citation]:
        raise NotImplementedError()

    @abstractmethod
    def authors_of_paper(self, doi: str) -> list[AuthorOfPaper]:
        raise NotImplementedError()

    @abstractmethod
    def paper_titles_from_doi(self, dois: list[str]) -> list[str]:
        raise NotImplementedError()


class CrossRefApi(BaseAPI):
    API_NAME = "crossref"

    _pool: ThreadPoolExecutor
    _rate_limit: helpers.RateLimiter

    def __init__(self):
        super().__init__()

        self.api = Works(
            etiquette=Etiquette(
                "tack",
                "0.1.0",
                "https://github.com/antonlydike/tack",
                "tack@antonlydike.de",
            )
        )
        self._pool = ThreadPoolExecutor(8)
        self._rate_limit = helpers.RateLimiter(7, 2, random_stagger=1)

    @lru_cache()
    def _fetch_paper(self, doi: str) -> dict | None:
        if (res := db.has_cached_response(f"crossref+{doi}")) is not None:
            return json.loads(res.response)
        else:
            with self._rate_limit.session():
                try:
                    data = self.api.doi(doi)
                except requests.JSONDecodeError as ex:
                    print(f"Error fetching DOI {doi}")
                    print(ex)
                    data = None
            db.cache_response(f"crossref+{doi}", json.dumps(data))
            return data

    def _abstract_of(self, data: dict):
        if "abstract" in data:
            return helpers.html_to_plain(data["abstract"]).strip()
        return None

    def paper_by_doi(self, doi: str) -> Paper | None:
        data = self._fetch_paper(doi)
        if data is None:
            return None

        return Paper(
            doi=doi,
            title=get_paper_title(data),
            conference=get_event_title_short(data),
            year=(
                data["published-print"]["date-parts"][0][0]
                if "published-print" in data
                else None
            ),
            abstract=self._abstract_of(data),
            url=data.get("URL"),
        )

    def citations_by_doi(self, doi: str) -> list[Citation]:
        data = self._fetch_paper(doi)
        if data is None:
            return []

        # fetch all DOIs to get richer info:
        tasks = []
        progress = ProgressBar(0)
        for elm in data.get("reference", []):
            if "DOI" in elm and "article-title" not in elm:

                def tasklet(elm_dict: dict):
                    try:
                        local_data = self._fetch_paper(elm_dict["DOI"])
                        if local_data is None:
                            return
                        elm_dict["year"] = (
                            local_data["published-print"]["date-parts"][0][0]
                            if "published-print" in local_data
                            else None
                        )
                        elm_dict["article-title"] = get_paper_title(local_data)
                        authors = local_data.get("author", [])
                        if authors:
                            author = authors[0]
                            elm_dict["author"] = f"{author['given']} {author['family']}"
                        elm_dict["journal-title"] = get_event_title_short(local_data)
                        progress.increment()
                    except Exception as ex:
                        print(
                            f"Error enriching citation for {elm_dict['DOI']}: {ex}",
                            file=sys.stderr,
                        )

                tasks.append(self._pool.submit(tasklet, elm))

        progress.update_size(len(tasks))
        # await tasks
        for task in tasks:
            task.result()
        print("")

        return [
            db.Citation(
                cite.get("article-title"),
                cite.get("journal-title"),
                cite.get("DOI"),
                cite.get("year"),
                cite.get("author"),
            )
            for cite in data.get("reference", [])
            if "article-title" in cite or "DOI" in cite
        ]

    def authors_of_paper(self, doi: str) -> list[AuthorOfPaper]:
        data = self._fetch_paper(doi)
        if data is None:
            return []

        return [
            db.AuthorOfPaper(
                None,
                author["ORCID"].split("/")[-1] if "ORCID" in author else None,
                f"{author['given']} {author['family']}",
                author["affiliation"][0]["name"] if author["affiliation"] else None,
            )
            for author in data.get("author", [])
        ]

    def paper_titles_from_doi(self, dois: list[str]) -> list[str | None]:
        return list(
            self._pool.map(
                lambda doi: unify_none_and_dict(self._fetch_paper(doi)).get(
                    "title", [None]
                )[0],
                dois,
            )
        )

    def __hash__(self):
        return hash(self.API_NAME)

    def __eq__(self, other):
        return isinstance(other, CrossRefApi) and other.API_NAME == self.API_NAME


def unify_none_and_dict(elm: dict | None) -> dict:
    return elm if elm else {}


def get_event_title_short(res: dict) -> str | None:
    if "event" not in res:
        return None
    if "acronym" in res["event"]:
        return res["event"]["acronym"]
    return shorten_conference(res["event"]["name"])


def get_paper_title(res: dict) -> str | None:
    if "subtitle" not in res or len(res["subtitle"]) == 0:
        if len(res["title"]) == 0:
            return None
        return res["title"][0]
    return f"{res['title'][0]}: {res['subtitle'][0]}"


def shorten_conference(conference_name: str) -> str:
    # look for trailing "CGO 2024."
    match = re.search(r"\.? ([A-Z-_\d+/]+) (\d{4})\.?$", conference_name)
    if match is not None:
        return f"{match.group(1)} '{int(match.group(2)) % 100:02}"

    # look for starting "SC20: ..."
    match = re.match(r"([A-Z-_\d+/]+\d\d):", conference_name)
    if match is not None:
        return match.group(1)

    # look for ^.* <year> .* (conference-shorthand)$
    match = re.search(r"((^|\s)\d\d(\d\d)?)? .*\(([^)]+)\)$", conference_name.strip())
    if match is not None:
        year: int | None = None
        if match.group(1) is not None:
            year = int(match.group(1).strip())

        if year is not None:
            return f"{match.group(4)} '{year % 100:02}"

        return match.group(4)

    return conference_name
