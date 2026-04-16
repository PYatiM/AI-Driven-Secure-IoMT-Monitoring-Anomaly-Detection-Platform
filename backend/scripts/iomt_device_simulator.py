from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


VITAL_METRICS = (
    "heart_rate",
    "systolic_bp",
    "diastolic_bp",
    "spo2",
    "respiratory_rate",
    "temperature",
)


@dataclass
class SimulatorStats:
    sent_requests: int = 0
    failed_requests: int = 0
    sent_records: int = 0
    anomaly_records: int = 0
    queue_drops: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    started_at: float = field(default_factory=time.perf_counter)
    finished_at: float = 0.0

    def finish(self) -> None:
        self.finished_at = time.perf_counter()

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at if self.finished_at > 0 else time.perf_counter()
        return max(0.0, end - self.started_at)


@dataclass
class SimulatedDevice:
    index: int
    identifier: str
    name: str
    api_key: str
    token: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normal_value(metric: str) -> float:
    if metric == "heart_rate":
        return round(random.gauss(72, 5), 2)
    if metric == "systolic_bp":
        return round(random.gauss(120, 10), 2)
    if metric == "diastolic_bp":
        return round(random.gauss(78, 8), 2)
    if metric == "spo2":
        return round(random.gauss(97, 1), 2)
    if metric == "respiratory_rate":
        return round(random.gauss(16, 2), 2)
    if metric == "temperature":
        return round(random.gauss(36.8, 0.3), 2)
    return round(random.gauss(1, 0.1), 2)


def _anomalous_value(metric: str) -> float:
    if metric == "heart_rate":
        return round(random.choice([random.uniform(30, 45), random.uniform(140, 190)]), 2)
    if metric == "systolic_bp":
        return round(random.choice([random.uniform(60, 85), random.uniform(180, 230)]), 2)
    if metric == "diastolic_bp":
        return round(random.choice([random.uniform(35, 55), random.uniform(110, 145)]), 2)
    if metric == "spo2":
        return round(random.uniform(70, 86), 2)
    if metric == "respiratory_rate":
        return round(random.choice([random.uniform(6, 9), random.uniform(28, 40)]), 2)
    if metric == "temperature":
        return round(random.choice([random.uniform(33, 35), random.uniform(39, 41)]), 2)
    return round(random.uniform(0, 5), 2)


def _metric_unit(metric: str) -> str:
    units = {
        "heart_rate": "bpm",
        "systolic_bp": "mmHg",
        "diastolic_bp": "mmHg",
        "spo2": "%",
        "respiratory_rate": "rpm",
        "temperature": "C",
    }
    return units.get(metric, "unit")


def generate_telemetry_records(
    *,
    anomaly_rate: float,
    records_per_cycle: int,
) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    anomaly_count = 0

    for _ in range(records_per_cycle):
        for metric_name in VITAL_METRICS:
            inject_anomaly = random.random() < anomaly_rate
            if inject_anomaly:
                value = _anomalous_value(metric_name)
                anomaly_count += 1
            else:
                value = _normal_value(metric_name)

            payload: dict[str, Any] = {
                "source": "simulator",
            }
            if inject_anomaly:
                payload.update(
                    {
                        "anomaly_detected": True,
                        "anomaly_score": round(random.uniform(0.8, 0.99), 2),
                    }
                )

            records.append(
                {
                    "recorded_at": _now_iso(),
                    "metric_name": metric_name,
                    "metric_type": "vital_sign",
                    "value_numeric": value,
                    "unit": _metric_unit(metric_name),
                    "payload": payload,
                }
            )

    return records, anomaly_count


async def login_user(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def register_devices(
    client: httpx.AsyncClient,
    *,
    user_token: str,
    device_count: int,
    run_tag: str,
) -> list[SimulatedDevice]:
    headers = {"Authorization": f"Bearer {user_token}"}
    devices: list[SimulatedDevice] = []

    for index in range(1, device_count + 1):
        identifier = f"SIM-{run_tag}-{index:04d}"
        payload = {
            "device_identifier": identifier,
            "name": f"Simulator Device {index}",
            "device_type": "patient_monitor",
            "manufacturer": "Simulated MedTech",
            "model": "SIM-HEALTH-01",
            "firmware_version": "1.0.0",
            "location": f"Ward-{(index % 12) + 1}",
        }

        response = await client.post(
            "/api/v1/devices/register",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        devices.append(
            SimulatedDevice(
                index=index,
                identifier=identifier,
                name=payload["name"],
                api_key=data["api_key"],
            )
        )

    return devices


async def issue_device_token(client: httpx.AsyncClient, api_key: str) -> str:
    response = await client.post(
        "/api/v1/devices/token",
        headers={"X-API-Key": api_key},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def bootstrap_device_tokens(client: httpx.AsyncClient, devices: list[SimulatedDevice]) -> None:
    for device in devices:
        device.token = await issue_device_token(client, device.api_key)


async def producer_loop(
    *,
    stop_event: asyncio.Event,
    device: SimulatedDevice,
    queue: asyncio.Queue,
    stats: SimulatorStats,
    interval_seconds: float,
    anomaly_rate: float,
    records_per_cycle: int,
) -> None:
    try:
        while not stop_event.is_set():
            records, anomaly_count = generate_telemetry_records(
                anomaly_rate=anomaly_rate,
                records_per_cycle=records_per_cycle,
            )
            queued_item = (device, records, anomaly_count)
            try:
                queue.put_nowait(queued_item)
            except asyncio.QueueFull:
                stats.queue_drops += len(records)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        return


async def sender_loop(
    *,
    stop_event: asyncio.Event,
    client: httpx.AsyncClient,
    queue: asyncio.Queue,
    stats: SimulatorStats,
    ingest_mode: str,
) -> None:
    endpoint = "/api/v1/telemetry/stream" if ingest_mode == "stream" else "/api/v1/telemetry/batch"

    try:
        while not stop_event.is_set() or not queue.empty():
            try:
                device, records, anomaly_count = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            headers = {"Authorization": f"Bearer {device.token}"}
            started = time.perf_counter()
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json={"items": records},
                )
                if response.status_code == 401:
                    device.token = await issue_device_token(client, device.api_key)
                    headers = {"Authorization": f"Bearer {device.token}"}
                    response = await client.post(endpoint, headers=headers, json={"items": records})
                response.raise_for_status()
                stats.sent_requests += 1
                stats.sent_records += len(records)
                stats.anomaly_records += anomaly_count
                stats.latencies_ms.append((time.perf_counter() - started) * 1000.0)
            except Exception:
                stats.failed_requests += 1
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        return


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    index = int(round((len(values_sorted) - 1) * percentile))
    return values_sorted[index]


def print_report(stats: SimulatorStats) -> None:
    stats.finish()
    elapsed = stats.elapsed_seconds
    throughput = stats.sent_records / elapsed if elapsed else 0.0
    error_rate = (
        (stats.failed_requests / (stats.sent_requests + stats.failed_requests)) * 100
        if (stats.sent_requests + stats.failed_requests)
        else 0.0
    )
    p50 = _percentile(stats.latencies_ms, 0.5)
    p95 = _percentile(stats.latencies_ms, 0.95)
    avg_latency = statistics.mean(stats.latencies_ms) if stats.latencies_ms else 0.0

    print("\n=== IoMT Simulator Report ===")
    print(f"Duration (s): {elapsed:.2f}")
    print(f"Requests sent: {stats.sent_requests}")
    print(f"Requests failed: {stats.failed_requests}")
    print(f"Records ingested: {stats.sent_records}")
    print(f"Anomalies injected: {stats.anomaly_records}")
    print(f"Queue drops: {stats.queue_drops}")
    print(f"Error rate (%): {error_rate:.2f}")
    print(f"Throughput (records/s): {throughput:.2f}")
    print(f"Latency avg (ms): {avg_latency:.2f}")
    print(f"Latency p50 (ms): {p50:.2f}")
    print(f"Latency p95 (ms): {p95:.2f}")


async def run_simulation(args: argparse.Namespace) -> None:
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)
    limits = httpx.Limits(max_connections=max(100, args.device_count * 4), max_keepalive_connections=40)
    queue: asyncio.Queue = asyncio.Queue(maxsize=args.queue_maxsize)
    stop_event = asyncio.Event()
    stats = SimulatorStats()

    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=timeout, limits=limits) as client:
        print("Authenticating simulator user...")
        user_token = await login_user(client, args.auth_email, args.auth_password)
        run_tag = f"{int(time.time()) % 100000:05d}"

        print(f"Registering {args.device_count} simulated devices...")
        devices = await register_devices(
            client,
            user_token=user_token,
            device_count=args.device_count,
            run_tag=run_tag,
        )

        print("Issuing device tokens...")
        await bootstrap_device_tokens(client, devices)

        producers = [
            asyncio.create_task(
                producer_loop(
                    stop_event=stop_event,
                    device=device,
                    queue=queue,
                    stats=stats,
                    interval_seconds=args.interval_seconds,
                    anomaly_rate=args.anomaly_rate,
                    records_per_cycle=args.records_per_cycle,
                ),
                name=f"producer-{device.index}",
            )
            for device in devices
        ]
        senders = [
            asyncio.create_task(
                sender_loop(
                    stop_event=stop_event,
                    client=client,
                    queue=queue,
                    stats=stats,
                    ingest_mode=args.ingest_mode,
                ),
                name=f"sender-{index}",
            )
            for index in range(1, args.sender_workers + 1)
        ]

        print(
            "Simulation running: "
            f"devices={args.device_count}, interval={args.interval_seconds}s, "
            f"mode={args.ingest_mode}, duration={args.duration_seconds}s"
        )

        started = time.perf_counter()
        try:
            while (time.perf_counter() - started) < args.duration_seconds:
                await asyncio.sleep(args.progress_seconds)
                elapsed = time.perf_counter() - started
                print(
                    f"[{elapsed:7.2f}s] queue={queue.qsize():4d} sent={stats.sent_records:7d} "
                    f"failed_req={stats.failed_requests:5d}"
                )
        finally:
            stop_event.set()
            for producer in producers:
                producer.cancel()
            await asyncio.gather(*producers, return_exceptions=True)
            await queue.join()
            for sender in senders:
                sender.cancel()
            await asyncio.gather(*senders, return_exceptions=True)

    print_report(stats)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "IoMT device simulator for generating synthetic healthcare telemetry, "
            "injecting random anomalies, and load-testing backend ingestion."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--auth-email", required=True, help="User email for bootstrap auth.")
    parser.add_argument("--auth-password", required=True, help="User password for bootstrap auth.")
    parser.add_argument("--device-count", type=int, default=25, help="Number of simulated devices.")
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=120,
        help="Total simulation duration in seconds.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=1.0,
        help="Telemetry transmission interval per device.",
    )
    parser.add_argument(
        "--records-per-cycle",
        type=int,
        default=1,
        help="How many metric cycles each device emits per interval.",
    )
    parser.add_argument(
        "--sender-workers",
        type=int,
        default=8,
        help="Number of async sender workers.",
    )
    parser.add_argument(
        "--queue-maxsize",
        type=int,
        default=20000,
        help="Maximum local queue size before drops.",
    )
    parser.add_argument(
        "--ingest-mode",
        choices=("batch", "stream"),
        default="batch",
        help="Send telemetry via /telemetry/batch or /telemetry/stream.",
    )
    parser.add_argument(
        "--anomaly-rate",
        type=float,
        default=0.03,
        help="Probability [0,1] of anomaly injection per metric.",
    )
    parser.add_argument(
        "--progress-seconds",
        type=float,
        default=5.0,
        help="Progress log interval in seconds.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_simulation(args))


if __name__ == "__main__":
    main()

