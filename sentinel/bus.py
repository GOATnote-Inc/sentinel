"""Event bus: fans every UI-visible event out to SSE clients + keeps a replay buffer.

Thread-safe publish (the engine runs in a worker thread; SSE clients live on the
asyncio loop). A broken/slow client can never block the loop — full queues drop.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque


class Bus:
    def __init__(self, replay: int = 250):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[asyncio.Queue] = set()
        self.buffer: deque[dict] = deque(maxlen=replay)
        self.audit: list[dict] = []           # audit entries (also published)
        self.stats = {"resolved": 0, "needs_human": 0, "blocked": 0,
                      "last_elapsed_s": None, "elapsed": []}

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    # -- publish from any thread ------------------------------------------
    def publish(self, channel: str, **data) -> dict:
        item = {"channel": channel, "ts": time.time(), **data}
        self.buffer.append(item)
        if channel == "audit":
            self.audit.append(item)
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._fanout, item)
        return item

    def _fanout(self, item: dict) -> None:
        for q in list(self.clients):
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                pass  # slow client: drop rather than stall the demo

    # -- SSE client lifecycle ---------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        for item in self.buffer:  # replay so a late-opened browser shows history
            q.put_nowait(item)
        self.clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.clients.discard(q)


def sse_format(item: dict) -> str:
    return f"data: {json.dumps(item)}\n\n"
