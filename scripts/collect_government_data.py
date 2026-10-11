"""Government Data Ingestion & Scheduled Update Command.

Usage:
    # Manual Ingestion
    python scripts/collect_government_data.py
    python scripts/collect_government_data.py --dry-run
    python scripts/collect_government_data.py --source "PM-KISAN Official Guidelines"
    python scripts/collect_government_data.py --category government_schemes

    # Scheduled Execution
    python scripts/collect_government_data.py --schedule
    python scripts/collect_government_data.py --schedule --interval 12
    python scripts/collect_government_data.py --status
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.sources.config import UPDATE_INTERVAL_HOURS
from app.sources.pipeline import ingest_all_registered_sources
from app.sources.scheduler import GovernmentDataScheduler, scheduler


def print_ingestion_summary(result: dict):
    """Format and print the standard source-by-source summary table."""
    summary = result.get("summary", {})
    details = result.get("details", [])

    print("\n---------------- INGESTION RESULTS BY SOURCE ----------------\n")
    tot_new = 0
    tot_upd = 0
    tot_unc = 0
    tot_fail = 0

    detail_map = {d.get("source_name"): d for d in details}

    for source_name, counts in summary.items():
        n = counts.get("new", 0)
        u = counts.get("updated", 0)
        un = counts.get("unchanged", 0)
        f = counts.get("failed", 0)

        tot_new += n
        tot_upd += u
        tot_unc += un
        tot_fail += f

        detail = detail_map.get(source_name, {})
        extra_note = ""
        if detail.get("status") == "UNCONFIGURED":
            extra_note = " (DATA_GOV_API_KEY not configured)"
        elif detail.get("error"):
            extra_note = f" ({detail['error']})"

        print(f"Source: {source_name}")
        print(f"New documents: {n}")
        print(f"Updated documents: {u}")
        print(f"Unchanged documents: {un}")
        print(f"Failed: {f}{extra_note}")
        print()

    print("==================================================================")
    print("SUMMARY")
    print("==================================================================")
    print(f"Total sources evaluated: {result.get('total_sources_evaluated', 0)}")
    print(f"Total new documents:       {tot_new}")
    print(f"Total updated documents:   {tot_upd}")
    print(f"Total unchanged documents: {tot_unc}")
    print(f"Total failed / skipped:    {tot_fail}")
    print("==================================================================")


def main():
    parser = argparse.ArgumentParser(
        description="Collect, update, and schedule official government data sources into ChromaDB."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Filter ingestion to a specific source name.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter ingestion to a specific category.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate collection and change detection without modifying ChromaDB.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the background scheduler to periodically check sources.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help=f"Scheduler check interval in hours (default: {UPDATE_INTERVAL_HOURS}h).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show scheduler status and last/next check timestamps.",
    )
    args = parser.parse_args()

    if args.status:
        st = scheduler.get_status()
        print("==================================================================")
        print("GOVERNMENT DATA SCHEDULER STATUS")
        print("==================================================================")
        print(f"Running:        {st['running']}")
        print(f"Interval:       {st['interval_hours']} hours ({st['interval_seconds']:.0f} seconds)")
        print(f"Run count:      {st['run_count']}")
        print(f"Last run time:  {st['last_run_time'] or 'Never'}")
        print(f"Next run time:  {st['next_run_time'] or 'Not scheduled'}")
        print(f"Currently locked: {st['is_locked']}")
        print("==================================================================")
        return

    if args.schedule:
        interval = args.interval if args.interval is not None else UPDATE_INTERVAL_HOURS
        print("==================================================================")
        print(f"STARTING GOVERNMENT DATA SCHEDULER (Interval: {interval} hours)")
        print("Press CTRL+C to stop the scheduler.")
        print("==================================================================")

        sched = GovernmentDataScheduler(interval_hours=interval, dry_run=args.dry_run)
        sched.start(run_immediately=True)
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nShutting down scheduler...")
            sched.stop(timeout=3.0)
            print("Scheduler stopped successfully.")
        return

    # Default: Manual single execution
    print("==================================================================")
    print("AI GOVERNMENT RESEARCH AGENT - OFFICIAL SOURCE COLLECTOR")
    print("==================================================================")
    if args.dry_run:
        print("[MODE: DRY-RUN (No changes will be written to ChromaDB)]")

    result = ingest_all_registered_sources(
        dry_run=args.dry_run,
        category_filter=args.category,
        source_filter=args.source,
    )

    if result.get("status") == "skipped":
        print(f"\n[NOTICE] {result.get('message')}")
        return

    print_ingestion_summary(result)


if __name__ == "__main__":
    main()
