import asyncio
import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import VAULT_PATH
from app.db import SessionLocal
from app.ingest import ingest_file

logger = logging.getLogger("watcher")


class VaultChangeHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def _handle(self, path_str: str):
        p = Path(path_str)
        if p.suffix != ".md":
            return
        # Schedule the async ingest on the main event loop from this watcher thread
        asyncio.run_coroutine_threadsafe(self._ingest(p), self.loop)

    async def _ingest(self, p: Path):
        db = SessionLocal()
        try:
            status = await ingest_file(db, p)
            if status != "skipped":
                logger.info(f"Auto-reindexed ({status}): {p}")
        except Exception as e:
            logger.warning(f"Failed to auto-index {p}: {e}")
        finally:
            db.close()

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)


def start_watcher(loop: asyncio.AbstractEventLoop) -> Observer:
    handler = VaultChangeHandler(loop)
    observer = Observer()
    observer.schedule(handler, VAULT_PATH, recursive=True)
    observer.start()
    logger.info(f"Watching vault for changes: {VAULT_PATH}")
    return observer
