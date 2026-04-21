from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx


VITALS = (
    ("heart_rate", "bpm", 72.0, 8.0),
    ("spo2", "%", 97.0, 1.5),
    ("respiratory_rate", "rpm", 16.0, 2.5),
    ("temperature", "C", 36.8, 0.3),
)


@dataclass
class LoadStats:
    started_at: float = field(default_factory=time.perf_counter)
    sent_requests: int = 0
    failed_requests: int = 0
    sent_records: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0001, time.perf_counter() - self.started_at)


def _build_record() -> dict:
    metric_name, unit, mean_value, std_dev = random.choice(VITALS)
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "metric_name": metric_name,
        "metric_type": "vital_sign",
        "value_numeric": round(random.gauss(mean_value, std_dev), 2),
        "unit": unit,
        "payload": {"source": "load-test"},
    }


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * ratio))
    return ordered[index]


async def _resolve_device_token(
    client: httpx.AsyncClient,
    api_key: str | None,
    explicit_token: str | None,
) -> str:
    if explicit_token:
        return explicit_token
    if not api_key:
        raise ValueError("Either --device-token or --api-key must be provided.")

    response = await client.post("/api/v1/devices/token", headers={"X-API-Key": api_key})
    response.raise_for_status()
    return response.json()["access_token"]


async def _worker(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    endpoint: str,
    batch_size: int,
    stop_at: float,
    stats: LoadStats,
) -> None:
    while time.perf_counter() < stop_at:
        if batch_size == 1:
            payload = _build_record()
        else:
            payload = {"items": [_build_record() for _ in range(batch_size)]}

        started = time.perf_counter()
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            if response.status_code >= 400:
                stats.failed_requests += 1
            else:
                stats.sent_requests += 1
                stats.sent_records += batch_size
                stats.latencies_ms.append((time.perf_counter() - started) * 1000.0)
        except Exception:
            stats.failed_requests += 1


def _print_report(stats: LoadStats, *, concurrency: int, endpoint: str, batch_size: int) -> None:
    elapsed = stats.elapsed_seconds
    total_requests = stats.sent_requests + stats.failed_requests
    request_rps = total_requests / elapsed
    record_rps = stats.sent_records / elapsed
    error_rate = (stats.failed_requests / total_requests * 100.0) if total_requests else 0.0
    avg_latency = statistics.mean(stats.latencies_ms) if stats.latencies_ms else 0.0
    p50_latency = _percentile(stats.latencies_ms, 0.50)
    p95_latency = _percentile(stats.latencies_ms, 0.95)
    p99_latency = _percentile(stats.latencies_ms, 0.99)

    print("\n=== Load Test Report ===")
    print(f"Endpoint: {endpoint}")
    print(f"Concurrency: {concurrency}")
    print(f"Batch size: {batch_size}")
    print(f"Duration (s): {elapsed:.2f}")
    print(f"Total requests: {total_requests}")
    print(f"Successful requests: {stats.sent_requests}")
    print(f"Failed requests: {stats.failed_requests}")
    print(f"Records ingested: {stats.sent_records}")
    print(f"Request throughput (req/s): {request_rps:.2f}")
    print(f"Record throughput (records/s): {record_rps:.2f}")
    print(f"Error rate (%): {error_rate:.2f}")
    print(f"Latency avg (ms): {avg_latency:.2f}")
    print(f"Latency p50 (ms): {p50_latency:.2f}")
    print(f"Latency p95 (ms): {p95_latency:.2f}")
    print(f"Latency p99 (ms): {p99_latency:.2f}")


async def _run(args: argparse.Namespace) -> None:
    endpoint = "/api/v1/telemetry" if args.mode == "single" else "/api/v1/telemetry/batch"
    batch_size = 1 if args.mode == "single" else max(1, args.batch_size)
    stats = LoadStats()

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)
    limits = httpx.Limits(
        max_connections=max(50, args.concurrency * 4),
        max_keepalive_connections=max(10, args.concurrency * 2),
    )

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=timeout,
        limits=limits,
    ) as client:
        token = await _resolve_device_token(client, args.api_key, args.device_token)
        headers = {"Authorization": f"Bearer {token}"}
        stop_at = time.perf_counter() + args.duration_seconds

        workers = [
            asyncio.create_task(
                _worker(
                    client=client,
                    headers=headers,
                    endpoint=endpoint,
                    batch_size=batch_size,
                    stop_at=stop_at,
                    stats=stats,
                )
            )
            for _ in range(args.concurrency)
        ]
        await asyncio.gather(*workers)

    _print_report(
        stats,
        concurrency=args.concurrency,
        endpoint=endpoint,
        batch_size=batch_size,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run concurrent ingestion load tests against the IoMT backend API."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("single", "batch"), default="batch")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--device-token", default=None)
    parser.add_argument("--api-key", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
