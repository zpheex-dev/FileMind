"""Write local, per-action reports without modifying the scanned folder."""

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


def write_action_log(directory: Path, action: str, **details) -> Path:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    finished = datetime.now(timezone.utc)
    filename = f"{finished:%Y%m%dT%H%M%S.%fZ}-{action}-{uuid4().hex[:8]}.json"
    destination = directory / filename
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", errors="backslashreplace",
                                dir=directory, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"action": action, "logged_at": finished.isoformat(), **details},
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination
