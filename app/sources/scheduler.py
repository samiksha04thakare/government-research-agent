"""Configurable Background Scheduler for Official Government Data Sources.

Executes periodic checks of enabled official sources every 24 hours by default.
Features:
- Configurable interval via UPDATE_INTERVAL_HOURS (default 24h)
- Controlled lifecycle: start(), stop(), run_once()
- Thread-safe non-overlapping execution (via run lock)
- Non-destructive updates: never deletes valid documents upon failure
- Accurate check time recording without date fabrication
- Full status introspection and reporting
"""
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.sources.config import (
    SCHEDULER_ENABLED,
    UPDATE_INTERVAL_HOURS,
)
from app.sources.pipeline import (
    ingest_all_registered_sources,
    is_ingestion_running,
)
from app.utils.logging import get_logger

log = get_logger("sources_scheduler")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernmentDataScheduler:
    """Manages periodic updates of official government data sources."""

    def __init__(
        self,
        interval_hours: float | None = None,
        dry_run: bool = False,
    ):
        self.interval_hours = (
            float(interval_hours)
            if interval_hours is not None
            else UPDATE_INTERVAL_HOURS
        )
        self.dry_run = dry_run
        self._interval_seconds = max(1.0, self.interval_hours * 3600.0)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._last_run_time: str | None = None
        self._next_run_time: str | None = None
        self._last_result: dict[str, Any] | None = None
        self._run_count: int = 0

    @property
    def interval_seconds(self) -> float:
        return self._interval_seconds

    def set_interval_hours(self, hours: float) -> None:
        """Update scheduler interval in hours."""
        with self._lock:
            self.interval_hours = float(hours)
            self._interval_seconds = max(1.0, self.interval_hours * 3600.0)
            if self.is_running() and self._last_run_time:
                try:
                    last_dt = datetime.fromisoformat(self._last_run_time)
                    next_dt = last_dt + timedelta(seconds=self._interval_seconds)
                    self._next_run_time = next_dt.isoformat()
                except Exception:
                    pass
            log.info("Scheduler interval updated to %.2f hours", self.interval_hours)

    def is_running(self) -> bool:
        """Check if background scheduler thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def run_once(
        self,
        dry_run: bool | None = None,
        category_filter: str | None = None,
        source_filter: str | None = None,
    ) -> dict[str, Any]:
        """Execute a single ingestion cycle immediately."""
        is_dry = self.dry_run if dry_run is None else dry_run
        run_ts = _now_iso()
        log.info("GovernmentDataScheduler: Triggering single run at %s (dry_run=%s)", run_ts, is_dry)

        result = ingest_all_registered_sources(
            dry_run=is_dry,
            category_filter=category_filter,
            source_filter=source_filter,
        )

        with self._lock:
            self._last_run_time = run_ts
            self._last_result = result
            self._run_count += 1
            next_dt = datetime.now(timezone.utc) + timedelta(seconds=self._interval_seconds)
            self._next_run_time = next_dt.isoformat()

        return result

    def _worker_loop(self, run_immediately: bool = False):
        """Internal background loop running until stop event is signaled."""
        log.info(
            "Scheduler background worker started. Interval: %.2f hours (%.0f seconds)",
            self.interval_hours,
            self._interval_seconds,
        )

        if run_immediately and not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                log.error("Error in initial scheduler run: %s", e)

        while not self._stop_event.is_set():
            with self._lock:
                next_dt = datetime.now(timezone.utc) + timedelta(seconds=self._interval_seconds)
                self._next_run_time = next_dt.isoformat()

            # Wait in increments to allow fast responsive shutdown
            wait_time = self._interval_seconds
            log.info("Scheduler sleeping until next check at %s (%.1fs)", self._next_run_time, wait_time)

            interrupted = self._stop_event.wait(timeout=wait_time)
            if interrupted or self._stop_event.is_set():
                break

            try:
                self.run_once()
            except Exception as e:
                log.error("Unhandled exception during scheduled source run: %s", e)

        log.info("Scheduler background worker stopped cleanly.")

    def start(self, run_immediately: bool = False) -> bool:
        """Start the background scheduler thread if not already running."""
        with self._lock:
            if self.is_running():
                log.warning("Scheduler start requested but it is already running.")
                return False

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                kwargs={"run_immediately": run_immediately},
                daemon=True,
                name="GovDataSchedulerThread",
            )
            self._thread.start()
            log.info("Scheduler started successfully.")
            return True

    def stop(self, timeout: float = 5.0) -> bool:
        """Signal the background scheduler to stop and wait for termination."""
        with self._lock:
            if not self.is_running():
                return True

            log.info("Stopping GovernmentDataScheduler...")
            self._stop_event.set()
            thread = self._thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout)

        with self._lock:
            self._thread = None
            self._next_run_time = None

        log.info("GovernmentDataScheduler stopped.")
        return True

    def get_status(self) -> dict[str, Any]:
        """Retrieve current scheduler runtime status and history."""
        with self._lock:
            return {
                "running": self.is_running(),
                "interval_hours": self.interval_hours,
                "interval_seconds": self._interval_seconds,
                "last_run_time": self._last_run_time,
                "next_run_time": self._next_run_time,
                "run_count": self._run_count,
                "is_locked": is_ingestion_running(),
                "last_result": self._last_result,
            }


# Global scheduler instance
scheduler = GovernmentDataScheduler()


def start_scheduler(run_immediately: bool = False) -> bool:
    return scheduler.start(run_immediately=run_immediately)


def stop_scheduler(timeout: float = 5.0) -> bool:
    return scheduler.stop(timeout=timeout)


def get_scheduler_status() -> dict[str, Any]:
    return scheduler.get_status()


def trigger_scheduled_run(dry_run: bool = False) -> dict[str, Any]:
    return scheduler.run_once(dry_run=dry_run)
