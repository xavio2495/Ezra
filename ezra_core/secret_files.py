"""Load GKE Secret Manager CSI file mounts into EZRA_* environment variables.

The GKE Secret Manager add-on mounts each secret as a FILE (it does not sync a
Kubernetes Secret). This reads that mount and exports each file under the
matching ``EZRA_*`` name (``ezra-mongodb-uri`` -> ``EZRA_MONGODB_URI``).
``setdefault`` means an explicit env var still wins, and the whole thing is a
no-op when the mount is absent (local/dev). Used by both the API entrypoint and
the data-ingestion job.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_secret_files(directory: str | None = None) -> None:
    directory = directory or os.environ.get("EZRA_SECRETS_DIR", "/mnt/secrets-store")
    path = Path(directory)
    if not path.is_dir():
        return
    for entry in path.iterdir():
        if entry.is_file():
            os.environ.setdefault(entry.name.upper().replace("-", "_"), entry.read_text().strip())
