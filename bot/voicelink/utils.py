"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import random
import time
import socket
from timeit import default_timer as timer
from itertools import zip_longest
from typing import Dict, Optional

__all__ = [
    "ExponentialBackoff",
    "NodeStats",
    "NodeInfoVersion",
    "NodeInfo",
    "Plugin",
    "Ping"
]

class ExponentialBackoff:
    def __init__(self, base: int = 1, *, integral: bool = False) -> None:
        self._base = base
        self._exp = 0
        self._max = 10
        self._reset_time = base * 2 ** 11
        self._last_invocation = time.monotonic()
        rand = random.Random()
        rand.seed()
        self._randfunc = rand.randrange if integral else rand.uniform

    def delay(self) -> float:
        invocation = time.monotonic()
        interval = invocation - self._last_invocation
        self._last_invocation = invocation
        if interval > self._reset_time:
            self._exp = 0
        self._exp = min(self._exp + 1, self._max)
        return self._randfunc(0, self._base * 2 ** self._exp)


class NodeStats:
    def __init__(self, data: Dict) -> None:
        memory: Dict = data.get("memory")
        self.used: int = memory.get("used")
        self.free: int = memory.get("free")
        self.reservable: int = memory.get("reservable")
        self.allocated: int = memory.get("allocated")
        cpu: Dict = data.get("cpu")
        self.cpu_cores: int = cpu.get("cores")
        self.cpu_system_load: float = cpu.get("systemLoad")
        self.cpu_process_load: float = cpu.get("lavalinkLoad")
        self.players_active: int = data.get("playingPlayers")
        self.players_total: int = data.get("players")
        self.uptime: int = data.get("uptime")


class NodeInfoVersion:
    def __init__(self, data: Dict) -> None:
        self.semver: str = data.get("semver")
        self.major: int = data.get("major")
        self.minor: int = data.get("minor")
        self.patch: int = data.get("patch")
        self.pre_release: Optional[str] = data.get("preRelease")
        self.build: Optional[str] = data.get("build")


class NodeInfo:
    def __init__(self, data: Dict) -> None:
        self.version: NodeInfoVersion = NodeInfoVersion(data.get("version", {}))
        self.build_time: int = data.get("buildTime")
        self.jvm: str = data.get("jvm")
        self.lavaplayer: str = data.get("lavaplayer")
        self.plugins = [Plugin(p) for p in data.get("plugins", [])]


class Plugin:
    def __init__(self, data: Dict) -> None:
        self.name: str = data.get("name")
        self.version: str = data.get("version")


class Ping:
    def __init__(self, host, port, timeout=5):
        self.timer = self.Timer()
        self._host = host
        self._port = port
        self._timeout = timeout

    class Socket(object):
        def __init__(self, family, type_, timeout):
            s = socket.socket(family, type_)
            s.settimeout(timeout)
            self._s = s

        def connect(self, host, port):
            self._s.connect((host, int(port)))

        def shutdown(self):
            self._s.shutdown(socket.SHUT_RD)

        def close(self):
            self._s.close()

    class Timer(object):
        def __init__(self):
            self._start = 0
            self._stop = 0

        def start(self):
            self._start = timer()

        def stop(self):
            self._stop = timer()

        def cost(self, funcs, args):
            self.start()
            for func, arg in zip_longest(funcs, args):
                if arg:
                    func(*arg)
                else:
                    func()
            self.stop()
            return self._stop - self._start

    def _create_socket(self, family, type_):
        return self.Socket(family, type_, self._timeout)

    def get_ping(self):
        s = self._create_socket(socket.AF_INET, socket.SOCK_STREAM)
        cost_time = self.timer.cost(
            (s.connect, s.shutdown),
            ((self._host, self._port), None))
        return 1000 * cost_time
