"""Persistent page units, bounded HTTP concurrency and serial SQLite commits."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Event
import json
import logging
import time
import uuid
from queue import Queue,Empty
from app.database.database import connect
from app.tasks.service import TaskService, now
from .profiles import TranslationError
from .providers import provider_for
from .service import TranslationService


def create_translation_task(db, page_ids, profile_id, options=None):
    """Snapshot allowed task options; persist profile IDs, never credentials or clients."""
    safe = {k: v for k, v in (options or {}).items() if k in ("include_ai_draft", "overwrite_protected", "block_ids", "scope", "target_blocks", "skipped_manual", "skipped_reviewed", "provider", "model", "settings")}
    if "settings" in safe:
        from .service import DEFAULTS
        safe["settings"]={k:v for k,v in safe["settings"].items() if k in DEFAULTS}
    safe.setdefault("target_blocks",TranslationService(db).preview(page_ids,safe)["blocks"])
    safe["provider_profile_id"] = profile_id
    return TaskService(db).create("AI_TRANSLATION", page_ids, options=safe)


def run_translation_task(project, store, task_id, progress=lambda *a: None, stop=None,
                         retry_failed=False, factory=None, retry_page_id=None):
    stop = stop or Event()
    db = connect(project / "project.sqlite3")
    tasks = TaskService(db)
    try:
        task = db.execute("SELECT * FROM tasks WHERE id=? AND kind='AI_TRANSLATION'", (task_id,)).fetchone()
        if not task:
            raise TranslationError("task_missing")
        if task["status"] in ("completed","cancelled"):
            return {**tasks.summary(task_id), "task_id": task_id}
        options = json.loads(task["options_json"])
        profile = store.get(options["provider_profile_id"])
        if profile.provider_type == "manual":
            raise TranslationError("manual_mode")
        if not store.consented(profile):
            raise TranslationError("cloud_consent_required")
        if retry_failed:
            with db:
                db.execute("UPDATE task_items SET status='pending',last_error=NULL WHERE task_id=? AND status='failed' AND (? IS NULL OR page_id=?)", (task_id,retry_page_id,retry_page_id))
        from dataclasses import replace
        if options.get("model"):profile=replace(profile,model=options["model"])
        provider = factory(profile) if factory else provider_for(profile, store.key(profile))
        run_started=time.monotonic()
        previous_elapsed=options.get("elapsed_ms",0)
        options["run_base_elapsed_ms"]=previous_elapsed
        options["run_started_at"]=now()
        with db:db.execute("UPDATE tasks SET options_json=? WHERE id=?",(json.dumps(options),task_id))
        tasks.set_status(task_id, "running")
        rows = list(db.execute("SELECT * FROM task_items WHERE task_id=? AND status IN ('pending','interrupted','running') ORDER BY rowid", (task_id,)))
        service = TranslationService(db)
        events=Queue()
        options["live_request_counts"]={}
        metrics=getattr(provider,"metrics",None)
        if metrics is not None:
            provider.on_request=lambda count:events.put((provider.metrics.item_id,count))
        def translate(item_id,payload):
            if metrics is not None:provider.metrics.item_id=item_id
            else:events.put((item_id,1))
            try:return provider.translate(payload,stop)
            except TranslationError as exc:
                request_metrics=getattr(provider,"metrics",None)
                if request_metrics is not None:exc.request_count=getattr(request_metrics,"requests",1)
                raise
        pending = iter(rows)
        active = {}
        exhausted = False
        paused = False
        with ThreadPoolExecutor(max_workers=profile.max_concurrency, thread_name_prefix="LMW-translation") as pool:
            while active or not exhausted:
                state = db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
                paused = (stop.is_set() or state == "paused") and state != "cancel_requested"
                cancelled = state == "cancel_requested"
                if paused or cancelled:
                    stop.set()
                    exhausted = True
                while not exhausted and len(active) < profile.max_concurrency:
                    row = next(pending, None)
                    if row is None:
                        exhausted = True
                        break
                    payload, snapshots = service.prepare(row["page_id"], options)
                    if not snapshots:
                        with db:
                            db.execute("UPDATE task_items SET status='completed',finished_at=? WHERE id=?", (now(), row["id"]))
                            db.execute("UPDATE tasks SET completed_units=completed_units+1 WHERE id=?", (task_id,))
                        continue
                    with db:
                        db.execute("UPDATE task_items SET status='running',attempts=attempts+1,started_at=? WHERE id=?", (now(), row["id"]))
                    active[pool.submit(translate, row["id"], payload)] = (row, snapshots, time.monotonic())
                    progress(tasks.summary(task_id)["completed"], task["total_units"], "status.ai_translation")
                if not active:
                    continue
                done, _ = wait(active, timeout=.2, return_when=FIRST_COMPLETED)
                changed=False
                while True:
                    try:item_id,count=events.get_nowait()
                    except Empty:break
                    options["live_request_counts"][item_id]=count;changed=True
                if changed:
                    with db:db.execute("UPDATE tasks SET options_json=?,updated_at=? WHERE id=?",(json.dumps(options),now(),task_id))
                for future in done:
                    row, snapshots, started = active.pop(future)
                    result = None
                    request_count = 1
                    code = None
                    try:
                        result = future.result()
                        service.apply(snapshots, result, profile)
                    except TranslationError as exc:
                        code = exc.code
                        request_count = getattr(exc, "request_count", 1)
                    except Exception:
                        # Never persist/log provider exceptions or raw outputs; they can echo secrets/text.
                        code = "translation_failed"
                    with db:
                        status = "pending" if code == "paused" else "failed" if code else "completed"
                        db.execute("UPDATE task_items SET status=?,last_error=?,finished_at=?,usage_json=?,duration_ms=? WHERE id=?",
                            (status, code, now(), json.dumps(result.usage) if not code else '{}',
                             result.duration_ms if not code else 0, row["id"]))
                        db.execute("INSERT INTO translation_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                            str(uuid.uuid4()), task_id, row["id"], row["page_id"], profile.provider_type, profile.model,
                            len(snapshots), result.request_count if result else request_count, status, code,
                            json.dumps(result.usage if result else {}), round((time.monotonic()-started)*1000), now()))
                        if not code:
                            db.execute("UPDATE tasks SET completed_units=completed_units+1 WHERE id=?", (task_id,))
                    options["live_request_counts"].pop(row["id"],None)
                    options["elapsed_ms"]=previous_elapsed+round((time.monotonic()-run_started)*1000)
                    with db:db.execute("UPDATE tasks SET options_json=? WHERE id=?",(json.dumps(options),task_id))
                    logging.info("AI translation provider=%s model=%s status=%s duration_ms=%s",
                                 profile.provider_type, profile.model, status, result.duration_ms if not code else 0)
                    summary = tasks.summary(task_id)
                    progress(summary["completed"], summary["total"], "status.ai_translation")
        summary = tasks.summary(task_id)
        state = db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
        tasks.set_status(task_id, "cancelled" if state == "cancel_requested" else "paused" if paused or stop.is_set() else
                         "completed" if summary["completed"] == summary["total"] else "failed")
        options["elapsed_ms"]=previous_elapsed+round((time.monotonic()-run_started)*1000)
        options.pop("run_started_at",None)
        with db:db.execute("UPDATE tasks SET options_json=? WHERE id=?",(json.dumps(options),task_id))
        usage = {}
        for row in db.execute("SELECT usage_json FROM task_items WHERE task_id=?", (task_id,)):
            for key, value in json.loads(row[0]).items():
                usage[key] = usage.get(key, 0) + value
        return {**tasks.summary(task_id), "task_id": task_id, "usage": usage}
    except TranslationError:
        tasks.set_status(task_id, "paused")
        raise
    except Exception:
        tasks.set_status(task_id, "paused")
        raise TranslationError("translation_failed") from None
    finally:
        db.close()
