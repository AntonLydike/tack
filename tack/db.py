import os
import sqlite3
from contextlib import contextmanager
from tack.models import Paper, AuthorOfPaper, Citation, CachedResponse
import time
from typing import ContextManager
import logging

log = logging.getLogger(__name__)

_CONNECTIONS: list[sqlite3.Connection] = list()


def get_local_db_file_path() -> str:
    if "XDG_DATA_HOME" in os.environ:
        data_dir = os.environ.get("XDG_DATA_HOME")
    else:
        data_dir = os.path.join(os.environ.get("HOME"), ".local", "share")
    conf_dir = os.path.join(data_dir, "tack")
    os.makedirs(conf_dir, exist_ok=True)
    return os.path.join(conf_dir, "tack.db")


@contextmanager
def cursor(read_only: bool = False) -> ContextManager[sqlite3.Cursor]:
    """
    Hand out a new cursor on a connection. Connections are re-used in a connection pool.

    Connections are automatically committed if no exception occurred.
    """
    if not _CONNECTIONS:
        conn = sqlite3.connect(get_local_db_file_path(), check_same_thread=False)
    else:
        conn = _CONNECTIONS.pop()
    cur = conn.cursor()
    try:
        yield cur
        if not read_only:
            conn.commit()
    except Exception as ex:
        conn.rollback()
        raise ex


def migrate():
    with cursor() as cur:
        res = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tack_settings';"
        ).fetchone()
        if res is None:
            _create_schema(cur)


def add_paper(paper: Paper) -> bool:
    with cursor() as cur:
        id = cur.execute(
            "INSERT OR IGNORE INTO papers (`doi`, `title`, `conference`, `year`, `abstract`, `url`) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING doi",
            (
                paper.doi,
                paper.title,
                paper.conference,
                paper.year,
                paper.abstract,
                paper.url,
            ),
        ).fetchone()
        return id is not None


def add_authors(doi: str, authors: list[AuthorOfPaper]):
    with cursor() as cur:
        author_ids = []
        for author in authors:
            if author.id is None:
                result = cur.execute(
                    "INSERT OR IGNORE INTO authors (`orcid`, `name`) VALUES (?, ?) RETURNING id",
                    (author.orcid, author.name),
                ).fetchone()
                if result is None:
                    result = cur.execute(
                        "SELECT id FROM authors WHERE orcid = ? LIMIT 1",
                        (author.orcid,),
                    ).fetchone()
                author_ids.append(result[0])
            else:
                author_ids.append(author.id)

        cur.executemany(
            "INSERT OR IGNORE INTO paper_authors (`doi`, `author_id`, `idx`, `affiliation`) VALUES (?, ?, ?, ?)",
            (
                (doi, id, i, a.affiliation)
                for i, (id, a) in enumerate(zip(author_ids, authors))
            ),
        )


def add_citations(doi: str, citations: list[Citation]):
    with cursor() as cur:
        cur.executemany(
            "INSERT INTO cites (source_doi, title, journal, doi, year, author) VALUES (?,?,?,?,?,?)",
            ((doi, c.title, c.journal, c.doi, c.year, c.author) for c in citations),
        )


def similar_authors(name: str) -> list[tuple[int, str, str, int]]:
    with cursor(read_only=True) as cur:
        return cur.execute(
            "SELECT authors.id, authors.name, papers.title, papers.year "
            "FROM authors "
            "CROSS JOIN paper_authors "
            "CROSS JOIN papers "
            "WHERE paper_authors.doi = papers.doi "
            "  AND paper_authors.author_id = authors.id "
            "  AND name = ? COLLATE NOCASE "
            "ORDER BY authors.id, papers.year DESC",
            (name,),
        ).fetchall()


def get_paper_dir() -> str:
    with cursor(read_only=True) as cur:
        home: str = cur.execute(
            "SELECT `folder` from tack_settings ORDER BY `schema_version` DESC LIMIT 1"
        ).fetchone()[0]

    # perform replacement of `~`
    if home.startswith("~/"):
        return os.environ.get("HOME") + home[1:]
    return home


def get_authors(doi: str) -> list[AuthorOfPaper]:
    with cursor(read_only=True) as cur:
        authors = cur.execute(
            "SELECT authors.`id`, authors.`orcid`, authors.`name`, paper_authors.`affiliation` "
            "FROM authors JOIN paper_authors ON authors.id = paper_authors.author_id "
            "WHERE paper_authors.doi = ? "
            "ORDER BY paper_authors.idx",
            (doi,),
        ).fetchall()
    return [AuthorOfPaper(*args) for args in authors]


def get_paper_citations(doi: str) -> list[Citation]:
    with cursor(read_only=True) as cur:
        cites = cur.execute(
            "SELECT `title`, `journal`, `doi`, `year`, `author` FROM cites WHERE source_doi = ? ORDER BY rowid",
            (doi,),
        ).fetchall()
    return [Citation(*args) for args in cites]


def cache_response(
    id: str, response: str, meta: str | None = None
) -> CachedResponse | None:
    with cursor() as cur:
        res = cur.execute(
            "INSERT OR REPLACE INTO query_cache(id, extra, time, response) VALUES (?,?,?,?)",
            (id, meta, int(time.time()), response),
        ).fetchone()
        if res is None:
            return None
        return CachedResponse(*res)


def has_cached_response(
    id: str, meta: str | None = None, timeout: int = -1
) -> CachedResponse | None:
    with cursor(read_only=True) as cur:
        query_args = [id]
        query = "SELECT id, time, extra, response FROM query_cache WHERE id = ?"
        if meta is not None:
            query_args.append(meta)
            query += " AND meta = ?"
        if timeout > 0:
            query_args.append(int(time.time()) - timeout)
            query += " AND time > ?"

        data = cur.execute(query, query_args).fetchone()
        if data is None:
            return None
        return CachedResponse(*data)


def _create_schema(cur: sqlite3.Cursor):
    cur.executescript(
        """
        CREATE TABLE papers (
          doi char(32) primary key not null,
          title text not null,
          conference text,
          year integer,
          abstract text,
          url text
        );
        
        CREATE INDEX paper_doi ON papers(doi);
        
        CREATE TABLE tack_settings (
            schema_version integer not null,
            folder text not null
        );
        
        INSERT INTO tack_settings(`schema_version`, `folder`) VALUES (1, "~/papers");
        
        CREATE TABLE tags (
            doi char(32) not null,
            name text not null,
            value text not null,
            UNIQUE(doi, name)
        );
        
        CREATE INDEX tags_doi ON tags(doi);
        
        CREATE TABLE authors (
            id integer primary key autoincrement not null,
            orcid char(32),
            name text not null,
            UNIQUE(orcid)
        );
        
        CREATE INDEX authors_id ON authors(id);
        CREATE INDEX authors_orcid ON authors(orcid);
        
        CREATE TABLE paper_authors (
            doi char(32) not null,
            author_id char(32) not null,
            idx integer not null,
            affiliation text,
            UNIQUE(doi, author_id)
        );
        
        CREATE INDEX paper_authors_doi ON paper_authors(doi);
        
        CREATE TABLE cites (
            source_doi char(32),
            title text,
            journal text,
            doi text,
            year integer,
            author text
        );
        
        CREATE INDEX cites_source_doi ON cites(source_doi);
        CREATE INDEX cites_doi ON cites(doi);
        
        CREATE TABLE query_cache (
            id text primary key not null,
            time integer not null,
            extra text,
            response text
        );
        
        CREATE INDEX query_cache_id ON query_cache(id);
    """
    )
    log.info("Created database schema")
