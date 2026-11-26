"""Writing the files paraText keeps (cache, linked files, settings) safely."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` (UTF-8) through a unique temporary file in the same folder.

    Readers never see a half-written file, and writers in other threads or windows never share a temporary file
    (a shared ``NAME.tmp`` made concurrent saves fail). The file is readable only by the user, as ``mkstemp``
    creates it; settings may hold API keys.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
