"""
PropertyKING — Sync Scheduler

Runs the distressed-property sync on the interval the admin configured (default
every 5 days). The scheduler checks hourly whether `next_run_at` has arrived,
rather than holding a fixed cron, so an admin changing the interval takes effect
immediately without a restart.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timezone

from app.database import get_database
from app.models.sync import SyncTrigger
from app.services.property_sync import (
    get_sync_settings, get_sync_settings_doc, compute_next_run, run_sync, SETTINGS_KEY
)
from app.utils.helpers import now_utc

_scheduler: AsyncIOScheduler | None = None
# Must be well under the smallest interval an admin can configure
# (1 hour), or a short interval would drift by up to a whole tick.
CHECK_INTERVAL_MINUTES = 5


async def _tick():
    """Fire the sync if the configured interval has elapsed."""
    try:
        settings = await get_sync_settings()
        if not settings.enabled:
            return

        db = get_database()
        doc = await get_sync_settings_doc()
        next_run = doc.get("next_run_at")

        # First boot, or settings saved before a next_run was computed
        if not next_run:
            computed = compute_next_run(settings, doc.get("last_run_at"))
            await db.sync_settings.update_one(
                {"_id": SETTINGS_KEY}, {"$set": {"next_run_at": computed}}
            )
            # Never synced at all — do an initial run so the site isn't empty
            if not doc.get("last_run_at"):
                print("[SCHEDULER] No previous sync found, running initial import")
                await run_sync(trigger=SyncTrigger.SCHEDULE.value, triggered_by="scheduler")
            return

        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        if next_run <= now_utc():
            print(f"[SCHEDULER] Sync due (was scheduled for {next_run.isoformat()})")
            await run_sync(trigger=SyncTrigger.SCHEDULE.value, triggered_by="scheduler")

    except Exception as exc:
        print(f"[SCHEDULER] Tick failed: {exc}")


def start_scheduler():
    """Start the background scheduler. Safe to call once at app startup."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _tick,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINUTES),
        id="distressed_sync_tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now_utc(),   # run one check right away on boot
    )
    _scheduler.start()
    print(f"[OK] Sync scheduler started (checks every {CHECK_INTERVAL_MINUTES} min)")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[X] Sync scheduler stopped")
    _scheduler = None
