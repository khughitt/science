from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class UnsupportedPathType(RuntimeError):
    pass


class StateFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existed: bool
    type: Literal["file", "dir", "symlink"] | None
    content_sha256: str | None
    mode: int | None
    symlink_target: str | None

    @model_validator(mode="after")
    def _coherent(self) -> StateFingerprint:
        if not self.existed:
            if any(v is not None for v in
                   (self.type, self.content_sha256, self.mode, self.symlink_target)):
                raise ValueError("absent fingerprint must carry all attributes None")
            return self
        if self.type is None:
            raise ValueError("present fingerprint requires a type")
        if self.mode is None:
            raise ValueError("present fingerprint requires a mode")
        if self.type == "file":
            if self.content_sha256 is None or self.symlink_target is not None:
                raise ValueError("file fingerprint needs content_sha256 and no symlink_target")
        elif self.type == "dir":
            if self.content_sha256 is not None or self.symlink_target is not None:
                raise ValueError("dir fingerprint carries neither content nor symlink_target")
        else:  # symlink
            if self.symlink_target is None or self.content_sha256 is not None:
                raise ValueError("symlink fingerprint needs symlink_target and no content_sha256")
        return self


def fingerprint(path: Path) -> StateFingerprint:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return StateFingerprint(existed=False, type=None, content_sha256=None,
                                mode=None, symlink_target=None)
    mode = stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        return StateFingerprint(existed=True, type="symlink", content_sha256=None,
                                mode=mode, symlink_target=os.readlink(path))
    if stat.S_ISDIR(st.st_mode):
        return StateFingerprint(existed=True, type="dir", content_sha256=None,
                                mode=mode, symlink_target=None)
    if not stat.S_ISREG(st.st_mode):
        # A FIFO, socket, or device: fail early -- read_bytes() on a FIFO blocks forever,
        # and none of these are things this transaction machinery ever legitimately touches.
        raise UnsupportedPathType(
            f"unsupported filesystem object at {path}: not a regular file, directory, or symlink"
        )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return StateFingerprint(existed=True, type="file", content_sha256=sha,
                            mode=mode, symlink_target=None)


def matches(fp: StateFingerprint, path: Path) -> bool:
    return fingerprint(path) == fp
