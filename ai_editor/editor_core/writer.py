"""Writer — local disk write utilities for session buf files and derived artifacts.

Writer has two distinct responsibilities:
  write_buf: atomic write for session buf files only; no backup.
  write_result: backup + atomic write + read-back for local derived artifacts only.

Neither method writes project files. Project files are written only via
CodeAnalysisClient.upload_content.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


class Writer:
    """Local disk write utilities for session buf files and derived artifacts.

    Neither write_buf nor write_result writes project files. Project files
    are written only via CodeAnalysisClient.upload_content.
    """

    def write_buf(self, content: str | bytes, path: Path) -> None:
        """Atomically write content to a session buf file.

        No backup is created. Uses a temp file + os.replace for atomicity.

        Args:
            content: String or bytes to write.
            path: Absolute path to the destination buf file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8") if isinstance(content, str) else content
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)

    def write_result(
        self,
        content: str | bytes,
        path: Path,
        backup_suffix: str = ".bak",
    ) -> str:
        """Backup, atomically write, and read back content to a local derived artifact.

        Steps:
          1. If path exists, copy it to path + backup_suffix (overwriting any prior bak).
          2. Write content atomically via temp file + os.replace.
          3. Read back the written file and return its text content.

        Args:
            content: String or bytes to write.
            path: Absolute path to the destination artifact file.
            backup_suffix: Suffix for the backup copy. Default '.bak'.

        Returns:
            The text content read back from path after writing.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = path.with_suffix(path.suffix + backup_suffix)
        if path.exists():
            shutil.copy2(path, backup)
        encoded = content.encode("utf-8") if isinstance(content, str) else content
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
        return path.read_text(encoding="utf-8")
