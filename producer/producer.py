"""High-rate producer: POST fake publications in a loop until Ctrl+C (SIGINT)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import threading
import time
import uuid
from datetime import datetime, timezone
from uuid import UUID

import httpx
from faker import Faker
from pydantic import BaseModel, HttpUrl

DEFAULT_PUBLICATIONS_URL = "http://localhost:8000/publications"
DEFAULT_CONCURRENT_WORKERS = 10


class _RequestCounter:
    """Thread-safe count of completed POST attempts (success or failure)."""

    __slots__ = ("_lock", "_n")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._n = 0

    def add(self, delta: int = 1) -> None:
        with self._lock:
            self._n += delta

    def get(self) -> int:
        with self._lock:
            return self._n


class Metrics(BaseModel):
    likes: int
    views: int
    comments: int
    shares: int
    follower_count_at_post: int


def random_instagram_publication_url(fake: Faker) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    shortcode = fake.bothify(text="???????????", letters=letters)
    return f"https://www.instagram.com/p/{shortcode}/"


class Publication(BaseModel):
    publication_url: HttpUrl
    title: str
    author_name: str
    author_id: UUID
    published_at: datetime
    description: str
    media_url: HttpUrl
    metrics: Metrics
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


def random_publication(fake: Faker) -> Publication:
    now = datetime.now(timezone.utc)
    return Publication(
        publication_url=random_instagram_publication_url(fake),
        title=fake.sentence(nb_words=6).rstrip("."),
        author_name=fake.name(),
        author_id=uuid.uuid7(),
        published_at=fake.date_time_between(
            start_date="-6y", end_date="now", tzinfo=timezone.utc
        ),
        description=fake.text(max_nb_chars=800),
        media_url=fake.image_url(),
        metrics=Metrics(
            likes=fake.random_int(min=0, max=500_000),
            views=fake.random_int(min=0, max=10_000_000),
            comments=fake.random_int(min=0, max=50_000),
            shares=fake.random_int(min=0, max=100_000),
            follower_count_at_post=fake.random_int(min=0, max=50_000_000),
        ),
        created_at=now,
        updated_at=(
            fake.date_time_between(
                start_date="-6y", end_date="now", tzinfo=timezone.utc
            )
            if fake.boolean()
            else None
        ),
        deleted_at=None,
    )


async def _post_publication(
    client: httpx.AsyncClient, url: str, publication: Publication
) -> None:
    payload = publication.model_dump(mode="json")
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logging.warning(
            "Failed to POST publication %r: %s", publication.title[:80], exc
        )


async def run_forever(url: str, workers: int) -> None:
    """Many concurrent async workers; each posts as fast as the network allows."""
    fake = Faker()
    faker_lock = threading.Lock()

    def next_publication() -> Publication:
        with faker_lock:
            return random_publication(fake)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        loop.call_soon_threadsafe(stop.set)

    try:
        loop.add_signal_handler(signal.SIGINT, request_stop)
        loop.add_signal_handler(signal.SIGTERM, request_stop)
    except NotImplementedError:
        logging.warning(
            "Signal handlers not available on this platform; use Ctrl+C "
            "(shutdown may wait for in-flight HTTP requests)."
        )

    limits = httpx.Limits(
        max_keepalive_connections=workers,
        max_connections=workers + 32,
    )
    timeout = httpx.Timeout(60.0, connect=10.0)

    logging.info(
        "Flooding %s with %s concurrent POST workers (Ctrl+C / SIGTERM to stop).",
        url,
        workers,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        counter = _RequestCounter()

        async def rps_reporter() -> None:
            prev_n = 0
            prev_t = time.perf_counter()
            while not stop.is_set():
                await asyncio.sleep(1.0)
                if stop.is_set():
                    break
                now_n = counter.get()
                now_t = time.perf_counter()
                elapsed = now_t - prev_t
                delta = now_n - prev_n
                rps = delta / elapsed if elapsed > 0 else 0.0
                prev_n, prev_t = now_n, now_t
                logging.info(
                    "Throughput: %.1f req/s (%d completed POSTs in %.2fs)",
                    rps,
                    delta,
                    elapsed,
                )

        async def worker() -> None:
            try:
                while not stop.is_set():
                    pub = next_publication()
                    await _post_publication(client, url, pub)
                    counter.add(1)
            except asyncio.CancelledError:
                raise

        reporter = asyncio.create_task(rps_reporter())
        tasks = [asyncio.create_task(worker()) for _ in range(workers)]
        try:
            await asyncio.gather(*tasks)
        finally:
            reporter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reporter
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    logging.info("Stopped.")


async def main(url: str, workers: int) -> None:
    logging.info(
        "Started at %s",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    await run_forever(url=url, workers=workers)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="POST fake publications in an infinite loop until interrupted.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_PUBLICATIONS_URL,
        help=f"POST target URL (default: {DEFAULT_PUBLICATIONS_URL})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_CONCURRENT_WORKERS,
        metavar="N",
        help=(
            "Number of concurrent asyncio tasks posting as fast as possible "
            f"(default: {DEFAULT_CONCURRENT_WORKERS}). Raise for more throughput "
            "until the server or your machine limits you."
        ),
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return args


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = _parse_args()
    try:
        asyncio.run(main(url=args.url, workers=args.workers))
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt — exiting.")
