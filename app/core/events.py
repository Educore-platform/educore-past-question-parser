import logging
from pathlib import Path

from blinker import signal

logger = logging.getLogger(__name__)

# Fired after a PDF has been fully parsed and persisted.
# Senders pass: path (str) — absolute path to the upload on disk.
file_processed = signal("file-processed")


@file_processed.connect
def _delete_upload(sender: str, *, path: str, **_) -> None:
    """Remove the temporary upload once processing is complete."""
    try:
        p = Path(path)
        if p.exists():
            p.unlink()
            logger.info("upload deleted after processing | file=%s sender=%s", p.name, sender)
        else:
            logger.warning("upload already gone | file=%s", path)
    except OSError as exc:
        logger.error("could not delete upload | file=%s error=%s", path, exc)
