import html.parser
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


class ExtractHTMLText(html.parser.HTMLParser):
    result: list[str]

    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, d):
        self.result.append(d)

    def get_text(self):
        return "".join(self.result)


def html_to_plain(value: str):
    """
    Converts an HTML encoded string into plain text. Note that this may result in the string containing HTML entities.
    """
    x = ExtractHTMLText()
    x.feed(value)
    return x.get_text()


@dataclass
class RateLimiter:
    num_requests: int
    interval: float | int
    random_stagger: float = field(default=0)
    """
    Introduces a slight delay between requests to stagger them 
    """

    bucket_start: float = field(default_factory=time.time, init=False)
    bucket_count: int = field(default=0, init=False)

    @contextmanager
    def session(self):
        if self.random_stagger > 0:
            time.sleep(self.random_stagger * random.random())
        while self.bucket_count >= self.num_requests:
            if self.bucket_start + self.interval < time.time():
                self.bucket_count = 0
                self.bucket_start = time.time()
                continue
            time.sleep(0.01)
        self.bucket_count += 1
        yield
