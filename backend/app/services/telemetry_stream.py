from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from backend.app.db.models import DeviceData
from backend.app.db.session import get_session_factory
from backend.app.schemas.telemetry import TelemetryIngestRequest
from backend.app.services.alerts import maybe_store_alert_for_telemetry
from backend.app.services.anomaly_detection import infer_telemetry_record
from backend.app.services.intrusion_detection import detect_intrusion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceStreamContext:
    id: int
    device_identifier: str
    device_type: str
    location: str | None


@dataclass(frozen=True)
class QueuedTelemetryRecord:
    device: DeviceStreamContext
    payload: TelemetryIngestRequest


@dataclass
class TelemetryStreamStats:
    queued: int = 0
    ingested: int = 0
    alerts: int = 0
    anomalies: int = 0
    intrusions: int = 0
    failed_batches: int = 0


class TelemetryStreamService:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueuedTelemetryRecord] = asyncio.Queue(maxsize=20000)
        self._worker_task: asyncio.Task | None = None
        self._running = False
        self._batch_size = 250
        self._flush_interval_seconds = 1.0
        self._stats = TelemetryStreamStats()

    @property
    def is_running(self) -> bool:
        return self._running and self._worker_task is not None and not self._worker_task.done()

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def stats(self) -> TelemetryStreamStats:
        return self._stats

    async def start(self, *, batch_size: int, flush_interval_seconds: float) -> None:
        if self.is_running:
            return

        self._batch_size = max(1, batch_size)
        self._flush_interval_seconds = max(0.05, flush_interval_seconds)
        self._running = True
        self._worker_task = asyncio.create_task(self._run_worker(), name="telemetry-stream-worker")
        logger.info(
            "Telemetry stream worker started (batch_size=%s, flush_interval=%.2fs).",
            self._batch_size,
            self._flush_interval_seconds,
        )

    async def stop(self) -> None:
        if self._worker_task is None:
            self._running = False
            return

        self._running = False
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        finally:
            self._worker_task = None

        logger.info(
            "Telemetry stream worker stopped (queued=%s, ingested=%s, failed_batches=%s).",
            self._stats.queued,
            self._stats.ingested,
            self._stats.failed_batches,
        )

    async def enqueue(self, records: list[QueuedTelemetryRecord]) -> tuple[int, int]:
        accepted = 0
        for record in records:
            try:
                self._queue.put_nowait(record)
                accepted += 1
                self._stats.queued += 1
            except asyncio.QueueFull:
                logger.warning("Telemetry stream queue is full; dropping incoming records.")
                break

        return accepted, self._queue.qsize()

    async def _run_worker(self) -> None:
        pending: list[QueuedTelemetryRecord] = []
        try:
            while True:
                try:
                    record = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._flush_interval_seconds,
                    )
                    pending.append(record)
                except asyncio.TimeoutError:
                    record = None

                if pending and (
                    len(pending) >= self._batch_size
                    or record is None
                ):
                    await self._flush_batch(pending)
                    for _ in pending:
                        self._queue.task_done()
                    pending.clear()
        except asyncio.CancelledError:
            if pending:
                await self._flush_batch(pending)
                for _ in pending:
                    self._queue.task_done()
            raise

    async def _flush_batch(self, records: list[QueuedTelemetryRecord]) -> None:
        if not records:
            return

        session = get_session_factory()()
        try:
            for record in records:
                telemetry_record = {
                    "device_id": record.device.id,
                    "device_identifier": record.device.device_identifier,
                    "device_type": record.device.device_type,
                    "location": record.device.location,
                    "recorded_at": record.payload.recorded_at,
                    "metric_name": record.payload.metric_name,
                    "metric_type": record.payload.metric_type,
                    "value_numeric": record.payload.value_numeric,
                    "value_text": record.payload.value_text,
                    "unit": record.payload.unit,
                    "payload": record.payload.payload or {},
                }
                inference_result = infer_telemetry_record(telemetry_record)
                intrusion_result = detect_intrusion(telemetry_record, inference_result)

                telemetry = DeviceData(
                    device_id=record.device.id,
                    recorded_at=record.payload.recorded_at,
                    metric_name=record.payload.metric_name,
                    metric_type=record.payload.metric_type,
                    value_numeric=record.payload.value_numeric,
                    value_text=record.payload.value_text,
                    unit=record.payload.unit,
                    payload=record.payload.payload,
                    anomaly_flag=inference_result.is_anomaly if inference_result else False,
                    anomaly_score=inference_result.anomaly_score if inference_result else None,
                    confidence_score=inference_result.confidence_score if inference_result else None,
                    model_name=inference_result.model_name if inference_result else None,
                    intrusion_flag=intrusion_result.intrusion_flag,
                    intrusion_score=intrusion_result.intrusion_score,
                    intrusion_type=(
                        intrusion_result.intrusion_type
                        if intrusion_result.intrusion_flag
                        else None
                    ),
                    intrusion_reason=(
                        intrusion_result.intrusion_reason
                        if intrusion_result.intrusion_flag
                        else None
                    ),
                )
                session.add(telemetry)
                session.flush()

                alert = maybe_store_alert_for_telemetry(session, telemetry)
                self._stats.ingested += 1
                if telemetry.anomaly_flag:
                    self._stats.anomalies += 1
                if telemetry.intrusion_flag:
                    self._stats.intrusions += 1
                if alert is not None:
                    self._stats.alerts += 1

            session.commit()
        except Exception:
            session.rollback()
            self._stats.failed_batches += 1
            logger.exception("Failed to flush telemetry stream batch of size %s.", len(records))
        finally:
            session.close()


_telemetry_stream_service = TelemetryStreamService()


def get_telemetry_stream_service() -> TelemetryStreamService:
    return _telemetry_stream_service

