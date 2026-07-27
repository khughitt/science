"""Typed, validated `boundary:` declaration.

Pure: no filesystem access, no git. Grammar is closed because every value here
becomes a git pattern -- pass-through would let a declaration emit rules nobody
audited. See docs/plans/2026-07-26-vcs-storage-boundary-design.md.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoundaryConfigError(Exception):
    """Raised for boundary declaration problems outside pydantic validation."""


class StorageClass(StrEnum):
    PAYLOAD = "payload"
    MANIFEST = "manifest"


_PATH_FORBIDDEN = set("*?[]!\\")
_CONTROL = {chr(c) for c in range(32)}


def _reject_control(value: str, label: str) -> None:
    if any(ch in _CONTROL for ch in value):
        raise ValueError(f"{label} must not contain control characters or newlines: {value!r}")


def _validate_relative(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty")
    _reject_control(value, label)
    if value.startswith("/"):
        raise ValueError(f"{label} must be repo-relative, not absolute: {value!r}")
    if value.endswith("/"):
        raise ValueError(f"{label} must not end with '/': {value!r}")
    if value.endswith("\\"):
        raise ValueError(f"{label} must not end with a dangling escape: {value!r}")
    parts = value.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ValueError(f"{label} must not contain empty, '.' or '..' segments: {value!r}")


def strip_git_trailing_spaces(value: str) -> str:
    """Remove only the trailing ASCII spaces git treats as insignificant.

    A trailing space is preserved when preceded by an odd-length run of
    backslashes: the final backslash quotes it. Remove unescaped spaces one at a
    time because a backslash followed by two spaces has one insignificant final
    space followed by one significant escaped space. Unicode whitespace is
    ordinary pattern text.
    """
    while value.endswith(" "):
        backslashes = 0
        for ch in reversed(value[:-1]):
            if ch != "\\":
                break
            backslashes += 1
        if backslashes % 2:
            break
        value = value[:-1]
    return value


class BoundaryRoot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: str
    storage_class: StorageClass = Field(alias="class")
    tracked: tuple[str, ...] = ()

    @field_validator("path")
    @classmethod
    def _check_path(cls, value: str) -> str:
        _validate_relative(value, "root path")
        if any(ch in _PATH_FORBIDDEN for ch in value):
            raise ValueError(f"root path must not contain glob metacharacters; globs belong in tracked: {value!r}")
        return value

    @field_validator("tracked")
    @classmethod
    def _check_tracked(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for glob in value:
            # Shares the path rules: non-empty, no control characters, not
            # absolute, no trailing '/', and no empty / '.' / '..' segment. The
            # segment rule matters more here than for a path -- PurePosixPath
            # normalises `foo//bar.json` and `foo/./bar.json` away and matches,
            # while git's generated negation does not fire at all.
            _validate_relative(glob, "tracked glob")
            if glob.startswith("!"):
                raise ValueError(f"tracked glob must not start with '!'; negation is the generator's job: {glob!r}")
            if glob.startswith("#"):
                raise ValueError(f"tracked glob must not start with '#': {glob!r}")
            if strip_git_trailing_spaces(glob) != glob:
                raise ValueError(
                    f"tracked glob must not have an unescaped trailing ASCII space: {glob!r}. "
                    f"git strips that space, so the emitted rule would not be the declared glob. "
                    f"Leading and Unicode whitespace are literals and are admitted."
                )
            # PROVEN SHARED SUBSET. The checker matches with
            # PurePosixPath.match; the generator emits `!/root/**/<glob>` and git
            # matches that. Every construct admitted here must mean the SAME
            # thing to both, because a construct they read differently lets the
            # generator emit a WORKING git rule that unreachable-tracked silently
            # never verifies. Exclusions fall into TWO groups, and conflating
            # them is how the last draft mis-stated the rationale:
            #
            # (a) ENGINE DIVERGENCE -- reproduced against real git:
            #   `**`  git's `foo/**/bar.json` matches `foo/bar.json`;
            #         PurePosixPath.match returns False.
            #   `?`   git's `?` matches one BYTE, PurePosixPath's one CHARACTER,
            #         so `?.json` vs `é.json` disagrees.
            #   `\\`   escapes are honoured by git and not by the matcher.
            #   unescaped trailing ASCII space -- git strips it from the pattern.
            #   (empty / `.` segments are the same class, rejected by
            #   _validate_relative above.)
            #
            # (b) PROBE RESTRICTION -- both engines agree, but the tooling
            #     cannot work with it:
            #   `[]`  both match `[ab].json` identically; what fails is probe
            #         generation, which cannot synthesise a witness filename for
            #         a character class, so `boundary check --probe` could not
            #         verify the emitted rule.
            #
            # Literals (including non-ASCII and Unicode whitespace), LEADING
            # whitespace and `*` are byte-for-byte identical in both engines --
            # `!/root/**/ lead.json` re-includes and stages ` lead.json` -- and
            # `*` matches leading dots in both, so those are admitted.
            if "**" in glob:
                raise ValueError(f"tracked glob must not use '**'; a bare '*' already spans one segment: {glob!r}")
            illegal = set(glob) & set("?[]\\")
            if illegal:
                raise ValueError(
                    f"tracked glob must not use {''.join(sorted(illegal))!r} in {glob!r}. "
                    f"'?' is byte-oriented in git and character-oriented in the checker, and "
                    f"escapes are honoured only by git, so both would make the checker disagree "
                    f"with git silently; a character class is matched identically by both but "
                    f"has no synthesisable probe witness. Literals (including leading "
                    f"whitespace) and '*' are admitted."
                )
        if len(set(value)) != len(value):
            raise ValueError("duplicate tracked glob")
        return value

    @model_validator(mode="after")
    def _check_class_pairing(self) -> "BoundaryRoot":
        if self.storage_class is StorageClass.MANIFEST and not self.tracked:
            raise ValueError(
                f"manifest root {self.path!r} needs a non-empty tracked list; "
                "a manifest root that tracks nothing is a payload root"
            )
        if self.storage_class is StorageClass.PAYLOAD and self.tracked:
            raise ValueError(f"tracked is only valid on class: manifest, not on payload root {self.path!r}")
        return self


class AllowEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = ".gitignore"
    pattern: str

    @model_validator(mode="before")
    @classmethod
    def _expand_shorthand(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"source": ".gitignore", "pattern": value}
        return value

    @field_validator("source")
    @classmethod
    def _check_source(cls, value: str) -> str:
        _validate_relative(value, "allow source")
        if value != ".gitignore" and not value.endswith("/.gitignore"):
            raise ValueError(f"allow source must be a .gitignore file: {value!r}")
        return value

    @field_validator("pattern")
    @classmethod
    def _check_pattern(cls, value: str) -> str:
        # GRAMMAR NOTE: an allow pattern is matched against `.gitignore` RULE
        # TEXT by equality, so it is NOT a `tracked:` glob and does NOT share its
        # grammar. A leading `/` (anchored) and a trailing `/` (directory) are
        # both legal and common -- `/data/raw/` and `.venv/` are the shapes
        # actually written, and so is LEADING whitespace, which git treats as
        # significant. What is rejected is text that cannot be a rule: empty,
        # control characters, a comment, a negation (allowing a negation is
        # meaningless -- it does not ignore anything, and the two checks that
        # consume the allowlist skip negations outright), or an UNESCAPED
        # trailing ASCII space (git strips it). Leading whitespace, Unicode
        # whitespace and escaped trailing ASCII spaces are significant.
        if not value:
            raise ValueError("allow pattern must not be empty")
        _reject_control(value, "allow pattern")
        if value.startswith("#"):
            raise ValueError(f"allow pattern must not be a comment: {value!r}")
        if value.startswith("!"):
            raise ValueError(f"allow pattern must not be a negation; negations ignore nothing: {value!r}")
        if strip_git_trailing_spaces(value) != value:
            raise ValueError(
                f"allow pattern must not have an unescaped trailing ASCII space: {value!r}. "
                f"git strips it from rule text, so this entry could never match the canonical "
                f"rule. Escaped ASCII spaces and Unicode whitespace are preserved."
            )
        return value


# Must match the scaffolded .gitignore in commands/create-project.md EXACTLY, or
# a freshly created project warns on day one. There is no shape heuristic behind
# this list: an entry is silenced because it was declared, never because it
# "looks like" tooling.
DEFAULT_UNMANAGED_ALLOW: tuple[str, ...] = (
    ".env",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "*.egg-info/",
    ".mypy_cache/",
    ".ipynb_checkpoints/",
    ".worktrees/",
    "*.pre-update*.bak",
    "doc/meta/next-steps-*.md",
    "docs/meta/next-steps-*.md",
    "doc/plans/*-plan-review.md",
    "docs/plans/*-plan-review.md",
    ".DS_Store",
)


class BoundaryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: tuple[BoundaryRoot, ...] = ()
    unmanaged_allow: tuple[AllowEntry, ...] = Field(
        default_factory=lambda: tuple(AllowEntry(pattern=p) for p in DEFAULT_UNMANAGED_ALLOW)
    )

    @model_validator(mode="after")
    def _check_roots(self) -> "BoundaryConfig":
        paths = [r.path for r in self.roots]
        seen_folded: dict[str, str] = {}
        for path in paths:
            folded = path.casefold()
            if folded in seen_folded:
                raise ValueError(
                    f"duplicate root path under conservative Git case-folding: "
                    f"{seen_folded[folded]!r} and {path!r} are case-fold-equivalent"
                )
            seen_folded[folded] = path
        for outer_index, outer in enumerate(paths):
            outer_folded = outer.casefold()
            for inner_index, inner in enumerate(paths):
                if outer_index != inner_index and (inner.casefold() + "/").startswith(outer_folded + "/"):
                    raise ValueError(
                        f"nested roots are not supported under conservative Git case-folding: "
                        f"{outer!r} contains {inner!r}. "
                        f"An anchored exclude for {outer!r} stops git descending, silently "
                        f"disabling every negation {inner!r} would generate."
                    )
        pairs = [(a.source, a.pattern) for a in self.unmanaged_allow]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate unmanaged_allow entry")
        return self
