from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommitRecord:
    hash: str
    author_name: str
    author_email: str
    authored_date: str
    committer_name: str
    committer_email: str
    parents: list[str]
    subject: str
    body: str
    trailers: dict[str, list[str]] = field(default_factory=dict)
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    is_merge: bool = False
    is_revert: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "authored_date": self.authored_date,
            "committer_name": self.committer_name,
            "committer_email": self.committer_email,
            "parents": self.parents,
            "subject": self.subject,
            "body": self.body,
            "trailers": self.trailers,
            "files_changed": self.files_changed,
            "additions": self.additions,
            "deletions": self.deletions,
            "is_merge": self.is_merge,
            "is_revert": self.is_revert,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CommitRecord":
        return cls(
            hash=str(payload.get("hash", "")),
            author_name=str(payload.get("author_name", "")),
            author_email=str(payload.get("author_email", "")),
            authored_date=str(payload.get("authored_date", "")),
            committer_name=str(payload.get("committer_name", "")),
            committer_email=str(payload.get("committer_email", "")),
            parents=list(payload.get("parents", [])),
            subject=str(payload.get("subject", "")),
            body=str(payload.get("body", "")),
            trailers=dict(payload.get("trailers", {})),
            files_changed=int(payload.get("files_changed", 0)),
            additions=int(payload.get("additions", 0)),
            deletions=int(payload.get("deletions", 0)),
            is_merge=bool(payload.get("is_merge", False)),
            is_revert=bool(payload.get("is_revert", False)),
        )


@dataclass
class StageResult:
    path: str
    record_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
