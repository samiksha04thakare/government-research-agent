"""Deployment-Safe Dedicated Worker for Scheduled Scheme and Source Updates.

Can be run in serverless, containerized, or managed job environments:
- Kubernetes CronJob
- Docker container / standalone VM
- Cloud Run Jobs / AWS ECS Scheduled Task / AWS Lambda container
- Local command line: `python -m app.sources.worker --mode once`

Usage:
  python -m app.sources.worker --mode once
  python -m app.sources.worker --mode once --retry-failed
  python -m app.sources.worker --mode daemon --interval 12.0
  python -m app.sources.worker --source "MahaPoCRA Agriculture DBT Catalog"
"""
import argparse
import sys
import time

from app.database.db import init_db
from app.schemes.updater import (
    retry_failed_sources,
    sync_all_registered_sources,
)
from app.sources.scheduler import GovernmentDataScheduler
from app.utils.logging import get_logger

log = get_logger("sources_worker")


def main():
    parser = argparse.ArgumentParser(description="Government Data & Scheme Update Worker")
    parser.add_argument(
        "--mode",
        choices=["once", "daemon"],
        default="once",
        help="Run once and exit (for serverless/cron), or run as a continuous daemon (default: once)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Run sync for a specific source by name",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry failed sources from recent synchronization runs",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=24.0,
        help="Interval in hours for daemon mode (default: 24.0)",
    )

    args = parser.parse_args()

    # Ensure database schema is migrated
    init_db()

    log.info("Starting Scheme Update Worker [mode=%s]", args.mode)

    if args.retry_failed:
        log.info("Worker: Retrying failed sources...")
        res = retry_failed_sources()
        log.info("Worker retry result: %s", res)
        sys.exit(0 if res.get("status") in ("SUCCESS", "PARTIAL") else 1)

    if args.mode == "once":
        sources_filter = [args.source] if args.source else None
        res = sync_all_registered_sources(source_names=sources_filter)
        log.info("Worker completed single run with status: %s", res.get("status"))
        status = res.get("status")
        # Exit with 0 on SUCCESS or PARTIAL, 1 on complete FAILURE
        sys.exit(0 if status in ("SUCCESS", "PARTIAL") else 1)

    elif args.mode == "daemon":
        log.info("Worker running as persistent daemon with %.1fh interval", args.interval)
        sched = GovernmentDataScheduler(interval_hours=args.interval)
        sched.start(run_immediately=True)

        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            log.info("Worker received shutdown signal. Stopping...")
            sched.stop()
            sys.exit(0)


if __name__ == "__main__":
    main()
