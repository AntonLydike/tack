import math
import shutil
import time
from dataclasses import dataclass, field
import threading


@dataclass
class ProgressBar:
    size: int

    state: int = field(default=0)

    _cli_width: int = field(default=0, init=False)
    _reserved_space: int = field(default=0, init=False)
    _print_lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self):
        self._cli_width = min(shutil.get_terminal_size((80, 20)).columns, 100)
        # calculate free space
        # 2 for []
        # log10(size)*2 + 1 for n/size
        # 2 for () surrounding progress
        # 1 for one extra space
        # somehow I missed two somewhere?

        if self.size == 0:
            self._reserved_space = 9
            return
        self._reserved_space = 2 + 1 + math.ceil(math.log10(self.size))*2 + 2 + 1 + 2

    def update_size(self, new_size: int):
        self.size = new_size
        self._reserved_space = 2 + 1 + math.ceil(math.log10(self.size))*2 + 2 + 1 + 2
        self.draw()

    def increment(self):
        self.state += 1
        self.draw()

    def draw(self):
        if self.state > self.size or self.size == 0:
            print("done!", end="", flush=True)
            return

        progress_width = self._cli_width - self._reserved_space

        status = f"({self.state:>{math.ceil(math.log10(self.size))}}/{self.size})"
        bar = "=" * int(progress_width * self.state / self.size)

        with self._print_lock:
            print(f"\r", end=f"[{bar:<{progress_width}}] {status}", flush=True)



if __name__ == '__main__':
    p = ProgressBar(100)
    for _ in range(100):
        p.increment()
        time.sleep(0.01)
