"""Safe task/request metrics; unknown usage is never represented as zero."""
import json
from datetime import datetime, timezone

TOKEN_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")

def aggregate_usage(rows):
    values = {k: 0 for k in TOKEN_KEYS}
    coverage = {k: 0 for k in TOKEN_KEYS}
    for row in rows:
        usage = row if isinstance(row, dict) else json.loads(row)
        for key in TOKEN_KEYS:
            if type(usage.get(key)) is int and usage[key] >= 0:
                values[key] += usage[key]
                coverage[key] += 1
    return {"values": {k: values[k] if coverage[k] else None for k in TOKEN_KEYS},
            "partial": any(coverage[k] != len(rows) for k in TOKEN_KEYS), "coverage": coverage}

def task_metrics(db, task_id):
    task = dict(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
    options = json.loads(task["options_json"])
    rows = [dict(r) for r in db.execute("SELECT ti.*,p.page_uid,p.display_order FROM task_items ti JOIN pages p ON p.id=ti.page_id WHERE task_id=? ORDER BY ti.rowid", (task_id,))]
    requests = [dict(r) for r in db.execute("SELECT * FROM translation_requests WHERE task_id=? ORDER BY rowid", (task_id,))]
    # One current result per item; request history retains retry usage independently.
    latest = {r["item_id"]: r for r in requests}
    success = sum(latest[r["id"]]["block_count"] for r in rows if r["status"] == "completed" and r["id"] in latest)
    failed = sum(latest[r["id"]]["block_count"] for r in rows if r["status"] == "failed" and r["id"] in latest)
    total = options.get("target_blocks") or sum(r["block_count"] for r in latest.values())
    running = [r for r in rows if r["status"] == "running"]
    total_ms = sum(r["duration_ms"] for r in requests)
    elapsed=options.get("elapsed_ms",total_ms)/1000
    if task["status"] in ("running","cancel_requested") and options.get("run_started_at"):
        # Last completed request refreshes elapsed_ms; do not add the same time twice.
        elapsed=options.get("run_base_elapsed_ms",0)/1000+(datetime.now(timezone.utc)-datetime.fromisoformat(options["run_started_at"])).total_seconds()
    return {**task, "options": options, "pages": rows, "requests": requests,
            "success": success, "failed": failed, "blocks": total,
            "current": running, "request_count": sum(r["request_count"] for r in requests)+sum(options.get("live_request_counts",{}).get(r["id"],0) for r in running),
            "usage": aggregate_usage([r["usage_json"] for r in requests]), "elapsed": elapsed}
