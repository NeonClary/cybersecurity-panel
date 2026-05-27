"""Persistent storage facade backed by SQLite + filesystem on a Hugging Face
Storage Bucket mount.

Background
----------
This Space used to require MongoDB (via Motor / GridFS). On Hugging Face
Spaces the container has no Mongo, the legacy ``/data`` Persistent Storage
was retired, and the user does not want to use Atlas (or any paid third
party). The replacement is a single Hugging Face Storage Bucket mounted into
the Space at ``$DATA_DIR`` (default ``/data``). Everything durable lives
there:

  ${DATA_DIR}/cybersecurity_panel.db   — SQLite database (users, chat
                                          sessions, profiles, onboarding,
                                          PhD canvases)

A single ``hf buckets sync hf://buckets/<org>/<bucket> ./backup`` therefore
captures the full state and can be restored before the next redeploy.

Design
------
This module exposes the **subset** of the Motor / pymongo API that the
existing routers and services already call (``find_one``, ``find``,
``insert_one``, ``update_one``, ``update_many``, ``delete_one``,
``delete_many``, ``replace_one``, ``count_documents``,
``find_one_and_delete``, ``aggregate`` with ``$match``/``$group``/``$in``).
The on-disk format is plain JSON-encoded documents in SQLite tables (one row
per document, with an indexed ``_id`` primary key, optional ``email`` UNIQUE
column on ``users``, and an indexed/UNIQUE ``user_id`` column on the user
scoped collections).

Why not full SQL? The router code uses Mongo idioms (``$in``, ``$set``,
``find_one_and_delete``, an aggregation pipeline) and ``bson.ObjectId`` IDs.
A small in-process query engine over JSON dicts keeps the routers untouched
while still benefiting from SQLite's durability and crash safety on the
bucket mount.

Why SQLite and not pure JSON files? Atomic commit, crash-consistent writes,
unique constraints (email, user-scoped profile/onboarding), and one
mongodump-style salvage file. WAL mode is *attempted* but if the bucket
FUSE doesn't support the required fcntl/mmap semantics SQLite falls back to
the default rollback journal automatically and this module logs a warning.

Errors from the underlying storage are re-raised as
``pymongo.errors.PyMongoError`` (or ``DuplicateKeyError`` for unique-index
violations) so the existing 5xx / DuplicateKey handlers keep working
unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Mapping, Sequence

import aiosqlite
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Each entry: (table name, has_unique_email_column, user_id_unique).
# users have a UNIQUE email column. user_profiles and onboarding_conversations
# have a UNIQUE user_id column (one record per user). chat_sessions and
# phd_canvases keep user_id only as an index (many records per user).
_TABLES: tuple[tuple[str, bool, bool], ...] = (
    ("users",                       True,  False),
    ("chat_sessions",               False, False),
    ("user_profiles",               False, True),
    ("onboarding_conversations",    False, True),
    ("phd_canvases",                False, False),
)

_TABLE_NAMES = {t[0] for t in _TABLES}


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _data_dir() -> Path:
    raw = os.environ.get("DATA_DIR") or "/data"
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _db_path() -> Path:
    return _data_dir() / "cybersecurity_panel.db"


# ---------------------------------------------------------------------------
# JSON (de)serialization that round-trips ObjectId / datetime
# ---------------------------------------------------------------------------

def _enc(o: Any) -> Any:
    if isinstance(o, ObjectId):
        return {"$oid": str(o)}
    if isinstance(o, datetime):
        if o.tzinfo is None:
            o = o.replace(tzinfo=timezone.utc)
        return {"$date": o.isoformat()}
    raise TypeError(f"Type {type(o)!r} is not JSON serialisable")


def _hook(d: dict) -> Any:
    if len(d) == 1:
        if "$oid" in d:
            return ObjectId(d["$oid"])
        if "$date" in d:
            return datetime.fromisoformat(d["$date"])
    return d


def _dumps(doc: Mapping) -> str:
    return json.dumps(dict(doc), default=_enc)


def _loads(text: str) -> dict:
    return json.loads(text, object_hook=_hook)


def _id_str(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        return v
    return str(v)


# ---------------------------------------------------------------------------
# Connection management (single shared aiosqlite connection)
# ---------------------------------------------------------------------------

_conn: aiosqlite.Connection | None = None
_open_lock = asyncio.Lock()


async def _open() -> aiosqlite.Connection:
    global _conn
    if _conn is not None:
        return _conn
    async with _open_lock:
        if _conn is not None:
            return _conn
        path = _db_path()
        try:
            conn = await aiosqlite.connect(str(path))
        except (aiosqlite.OperationalError, OSError) as exc:
            raise PyMongoError(f"Cannot open database at {path}: {exc}") from exc

        # WAL gives concurrent readers; if the bucket FUSE doesn't support the
        # mmap/lock semantics WAL needs, SQLite stays in the default rollback
        # journal which still works on every filesystem we care about.
        try:
            cur = await conn.execute("PRAGMA journal_mode=WAL")
            row = await cur.fetchone()
            mode = (row[0] if row else "?")
            if str(mode).lower() != "wal":
                LOG.warning(
                    "Could not enable WAL mode on %s (got %r); using rollback journal",
                    path, mode,
                )
        except aiosqlite.OperationalError as exc:
            LOG.warning("PRAGMA journal_mode=WAL failed (%s); using rollback journal", exc)

        try:
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA foreign_keys=ON")
        except aiosqlite.OperationalError:
            pass

        await _init_schema(conn)
        await conn.commit()
        LOG.info("SQLite ready at %s", path)
        _conn = conn
        return _conn


async def _init_schema(conn: aiosqlite.Connection) -> None:
    parts: list[str] = []
    for name, has_email, user_id_unique in _TABLES:
        if has_email:
            parts.append(
                f"""
                CREATE TABLE IF NOT EXISTS {name} (
                    _id TEXT PRIMARY KEY,
                    email TEXT UNIQUE,
                    doc TEXT NOT NULL
                );
                """
            )
        else:
            uniq = "UNIQUE" if user_id_unique else ""
            parts.append(
                f"""
                CREATE TABLE IF NOT EXISTS {name} (
                    _id TEXT PRIMARY KEY,
                    user_id TEXT {uniq},
                    doc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_{name}_user_id ON {name}(user_id);
                """
            )
    await conn.executescript("\n".join(parts))


async def _close() -> None:
    """Best-effort connection close (called from FastAPI lifespan teardown)."""
    global _conn
    if _conn is not None:
        try:
            await _conn.close()
        except Exception:  # pragma: no cover - shutdown path
            pass
        _conn = None


# ---------------------------------------------------------------------------
# Filter matching (only the Mongo operators the routers actually use)
# ---------------------------------------------------------------------------

def _match_value(actual: Any, want: Any) -> bool:
    if isinstance(want, dict) and len(want) == 1:
        op, arg = next(iter(want.items()))
        if op == "$in":
            return actual in arg
    return actual == want


def _matches(doc: Mapping, query: Mapping) -> bool:
    for k, v in query.items():
        if not _match_value(doc.get(k), v):
            return False
    return True


# ---------------------------------------------------------------------------
# Result types (shaped like pymongo's so existing ``res.inserted_id`` etc. works)
# ---------------------------------------------------------------------------

class _InsertOneResult:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, matched: int, modified: int, upserted_id: ObjectId | None = None) -> None:
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id


class _DeleteResult:
    def __init__(self, deleted: int) -> None:
        self.deleted_count = deleted


# ---------------------------------------------------------------------------
# Cursor / aggregation
# ---------------------------------------------------------------------------

def _sort_key_factory(field: str):
    def keyfn(d: Mapping):
        v = d.get(field)
        return (v is None, v)
    return keyfn


class _Cursor:
    """Lazy cursor: docs are fetched the first time you await iteration / to_list."""

    def __init__(self, fetch):
        self._fetch = fetch
        self._sort_field: str | None = None
        self._sort_dir: int = 1
        self._limit: int | None = None
        self._skip: int = 0

    def sort(self, field: str | list[tuple[str, int]], direction: int = 1) -> "_Cursor":
        # Routers also call .sort([("created_at", -1)]) — accept that form too,
        # honoring only the first key (Mongo allows compound sort; for the
        # routers we have, single-key sort is sufficient).
        if isinstance(field, list) and field:
            f, d = field[0]
            self._sort_field = f
            self._sort_dir = d
        else:
            self._sort_field = field  # type: ignore[assignment]
            self._sort_dir = direction
        return self

    def limit(self, n: int) -> "_Cursor":
        self._limit = int(n)
        return self

    def skip(self, n: int) -> "_Cursor":
        self._skip = int(n)
        return self

    async def _materialize(self) -> list[dict]:
        items = await self._fetch()
        if self._sort_field is not None:
            items.sort(key=_sort_key_factory(self._sort_field), reverse=self._sort_dir < 0)
        if self._skip:
            items = items[self._skip:]
        if self._limit is not None:
            items = items[: self._limit]
        return items

    async def to_list(self, length: int | None = None) -> list[dict]:
        items = await self._materialize()
        return items if length is None else items[:length]

    def __aiter__(self) -> AsyncIterator[dict]:
        async def _gen():
            for d in await self._materialize():
                yield d
        return _gen()


class _Aggregate:
    """Tiny aggregation runner — supports the pipeline shapes the routers use:
    ``$match`` and ``$group`` with ``_id: None`` plus ``$sum``.

    More exotic shapes (``$lookup``) raise NotImplementedError; the only
    caller is a maintenance ``cleanup_old_canvas_data`` function that isn't
    on the request path, so this is safe.
    """

    def __init__(self, fetch, pipeline: Sequence[Mapping]):
        self._fetch = fetch
        self._pipeline = list(pipeline)

    async def to_list(self, length: int | None = None) -> list[dict]:
        items = await self._fetch()
        for stage in self._pipeline:
            if "$match" in stage:
                items = [d for d in items if _matches(d, stage["$match"])]
            elif "$group" in stage:
                spec = stage["$group"]
                gid = spec.get("_id")
                if gid is not None:
                    raise NotImplementedError("Only $group with _id: None is supported")
                bucket: dict[str, Any] = {"_id": None}
                for k, v in spec.items():
                    if k == "_id":
                        continue
                    if not (isinstance(v, dict) and len(v) == 1):
                        raise NotImplementedError(f"Unsupported $group field: {k}={v!r}")
                    op, arg = next(iter(v.items()))
                    if op == "$sum" and isinstance(arg, str) and arg.startswith("$"):
                        field = arg[1:]
                        bucket[k] = sum(int(d.get(field) or 0) for d in items)
                    else:
                        raise NotImplementedError(f"Unsupported $group op: {op}")
                items = [bucket]
            else:
                raise NotImplementedError(f"Unsupported aggregation stage: {stage}")
        return items if length is None else items[:length]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

class Collection:
    def __init__(self, name: str) -> None:
        self._name = name
        self._has_email = name == "users"

    # ----- low-level helpers ------------------------------------------------

    async def _all(self, conn: aiosqlite.Connection) -> list[dict]:
        cur = await conn.execute(f"SELECT doc FROM {self._name}")
        rows = await cur.fetchall()
        return [_loads(r[0]) for r in rows]

    def _insert_params(self, _id: str, email: str | None, user_id: str | None, doc_json: str):
        if self._has_email:
            return (
                "INSERT INTO users (_id, email, doc) VALUES (?, ?, ?)",
                (_id, email, doc_json),
            )
        return (
            f"INSERT INTO {self._name} (_id, user_id, doc) VALUES (?, ?, ?)",
            (_id, user_id, doc_json),
        )

    async def _update_row(
        self,
        conn: aiosqlite.Connection,
        _id: str,
        email: str | None,
        user_id: str | None,
        doc_json: str,
    ) -> None:
        if self._has_email:
            await conn.execute(
                "UPDATE users SET email=?, doc=? WHERE _id=?",
                (email, doc_json, _id),
            )
        else:
            await conn.execute(
                f"UPDATE {self._name} SET user_id=?, doc=? WHERE _id=?",
                (user_id, doc_json, _id),
            )

    def _apply_update(self, doc: dict, update: Mapping, is_insert: bool = False) -> None:
        for op, fields in update.items():
            if op == "$set":
                for k, v in fields.items():
                    doc[k] = v
            elif op == "$unset":
                for k in fields:
                    doc.pop(k, None)
            elif op == "$inc":
                for k, v in fields.items():
                    doc[k] = (doc.get(k) or 0) + v
            elif op == "$push":
                # Supports {"$push": {"field": value}} and
                # {"$push": {"field": {"$each": [v1, v2, ...]}}}.
                for k, spec in fields.items():
                    existing = doc.get(k)
                    if not isinstance(existing, list):
                        existing = []
                        doc[k] = existing
                    if isinstance(spec, Mapping) and "$each" in spec:
                        items = list(spec["$each"])
                    else:
                        items = [spec]
                    existing.extend(items)
            elif op == "$setOnInsert":
                # Only applies on the insert side of an upsert.
                if is_insert:
                    for k, v in fields.items():
                        doc.setdefault(k, v)
            else:
                raise NotImplementedError(f"Unsupported update operator: {op}")

    # ----- public API -------------------------------------------------------

    async def find_one(self, query: Mapping | None = None, projection: Mapping | None = None) -> dict | None:
        query = dict(query or {})
        try:
            conn = await _open()
            # Fast paths for primary-key / unique-index lookups.
            if list(query.keys()) == ["_id"] and isinstance(query["_id"], (ObjectId, str)):
                cur = await conn.execute(
                    f"SELECT doc FROM {self._name} WHERE _id = ?",
                    (_id_str(query["_id"]),),
                )
                row = await cur.fetchone()
                return _loads(row[0]) if row else None
            if self._has_email and list(query.keys()) == ["email"]:
                cur = await conn.execute(
                    "SELECT doc FROM users WHERE email = ?",
                    (query["email"],),
                )
                row = await cur.fetchone()
                return _loads(row[0]) if row else None
            for d in await self._all(conn):
                if _matches(d, query):
                    return d
            return None
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"find_one({self._name}) failed: {exc}") from exc

    def find(self, query: Mapping | None = None, projection: Mapping | None = None) -> _Cursor:
        q = dict(query or {})

        async def _go() -> list[dict]:
            try:
                conn = await _open()
                docs = await self._all(conn)
                return [d for d in docs if _matches(d, q)]
            except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
                raise PyMongoError(f"find({self._name}) failed: {exc}") from exc

        return _Cursor(_go)

    def aggregate(self, pipeline: Sequence[Mapping]) -> _Aggregate:
        async def _go() -> list[dict]:
            try:
                conn = await _open()
                return await self._all(conn)
            except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
                raise PyMongoError(f"aggregate({self._name}) failed: {exc}") from exc

        return _Aggregate(_go, pipeline)

    async def count_documents(self, filter: Mapping | None = None) -> int:
        f = dict(filter or {})
        try:
            conn = await _open()
            if not f:
                cur = await conn.execute(f"SELECT COUNT(*) FROM {self._name}")
                row = await cur.fetchone()
                return int(row[0]) if row else 0
            return sum(1 for d in await self._all(conn) if _matches(d, f))
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"count_documents({self._name}) failed: {exc}") from exc

    async def insert_one(self, doc: Mapping) -> _InsertOneResult:
        d = dict(doc)
        if "_id" not in d or d["_id"] is None:
            d["_id"] = ObjectId()
        oid = d["_id"]
        try:
            conn = await _open()
            email = d.get("email") if self._has_email else None
            user_id = _id_str(d["user_id"]) if "user_id" in d else None
            sql, params = self._insert_params(_id_str(oid), email, user_id, _dumps(d))
            await conn.execute(sql, params)
            await conn.commit()
            return _InsertOneResult(oid)
        except aiosqlite.IntegrityError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"insert_one({self._name}) failed: {exc}") from exc

    async def update_one(
        self,
        filter: Mapping,
        update: Mapping,
        upsert: bool = False,
    ) -> _UpdateResult:
        try:
            conn = await _open()
            doc = await self.find_one(filter)
            if doc is None and not upsert:
                return _UpdateResult(0, 0)
            if doc is None and upsert:
                base: dict[str, Any] = {}
                for k, v in filter.items():
                    if not (isinstance(v, dict) and any(str(kk).startswith("$") for kk in v)):
                        base[k] = v
                if "_id" not in base:
                    base["_id"] = ObjectId()
                self._apply_update(base, update, is_insert=True)
                res = await self.insert_one(base)
                return _UpdateResult(0, 0, upserted_id=res.inserted_id)
            self._apply_update(doc, update)
            email = doc.get("email") if self._has_email else None
            user_id = _id_str(doc["user_id"]) if "user_id" in doc else None
            await self._update_row(conn, _id_str(doc["_id"]), email, user_id, _dumps(doc))
            await conn.commit()
            return _UpdateResult(1, 1)
        except aiosqlite.IntegrityError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"update_one({self._name}) failed: {exc}") from exc

    async def update_many(
        self,
        filter: Mapping,
        update: Mapping,
    ) -> _UpdateResult:
        try:
            conn = await _open()
            docs = [d for d in await self._all(conn) if _matches(d, filter)]
            if not docs:
                return _UpdateResult(0, 0)
            for doc in docs:
                self._apply_update(doc, update)
                email = doc.get("email") if self._has_email else None
                user_id = _id_str(doc["user_id"]) if "user_id" in doc else None
                await self._update_row(conn, _id_str(doc["_id"]), email, user_id, _dumps(doc))
            await conn.commit()
            return _UpdateResult(len(docs), len(docs))
        except aiosqlite.IntegrityError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"update_many({self._name}) failed: {exc}") from exc

    async def replace_one(
        self,
        filter: Mapping,
        replacement: Mapping,
        upsert: bool = False,
    ) -> _UpdateResult:
        try:
            conn = await _open()
            existing = await self.find_one(filter)
            new_doc = dict(replacement)
            if existing is None and not upsert:
                return _UpdateResult(0, 0)
            if existing is None and upsert:
                if "_id" not in new_doc or new_doc["_id"] is None:
                    new_doc["_id"] = ObjectId()
                res = await self.insert_one(new_doc)
                return _UpdateResult(0, 0, upserted_id=res.inserted_id)
            # Preserve the existing _id so the replacement updates the same row.
            new_doc["_id"] = existing["_id"]
            email = new_doc.get("email") if self._has_email else None
            user_id = _id_str(new_doc["user_id"]) if "user_id" in new_doc else None
            await self._update_row(conn, _id_str(existing["_id"]), email, user_id, _dumps(new_doc))
            await conn.commit()
            return _UpdateResult(1, 1)
        except aiosqlite.IntegrityError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"replace_one({self._name}) failed: {exc}") from exc

    async def delete_one(self, filter: Mapping) -> _DeleteResult:
        try:
            conn = await _open()
            doc = await self.find_one(filter)
            if doc is None:
                return _DeleteResult(0)
            await conn.execute(
                f"DELETE FROM {self._name} WHERE _id=?",
                (_id_str(doc["_id"]),),
            )
            await conn.commit()
            return _DeleteResult(1)
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"delete_one({self._name}) failed: {exc}") from exc

    async def delete_many(self, filter: Mapping) -> _DeleteResult:
        try:
            conn = await _open()
            docs = [d for d in await self._all(conn) if _matches(d, filter)]
            for d in docs:
                await conn.execute(
                    f"DELETE FROM {self._name} WHERE _id=?",
                    (_id_str(d["_id"]),),
                )
            if docs:
                await conn.commit()
            return _DeleteResult(len(docs))
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"delete_many({self._name}) failed: {exc}") from exc

    async def find_one_and_delete(self, filter: Mapping) -> dict | None:
        try:
            conn = await _open()
            doc = await self.find_one(filter)
            if doc is None:
                return None
            await conn.execute(
                f"DELETE FROM {self._name} WHERE _id=?",
                (_id_str(doc["_id"]),),
            )
            await conn.commit()
            return doc
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError, OSError) as exc:
            raise PyMongoError(f"find_one_and_delete({self._name}) failed: {exc}") from exc

    async def create_index(self, keys: Any, unique: bool = False, **_: Any) -> str:
        # The schema already declares the indexes the routers rely on
        # (PK on _id, UNIQUE on users.email and on user_profiles.user_id /
        # onboarding_conversations.user_id, plain index on user_id elsewhere).
        # Stays a no-op so legacy main.py / canvas_database.py calls keep
        # working without changes.
        return "ok"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class Database:
    def __init__(self) -> None:
        self._collections: dict[str, Collection] = {}

    def _coll(self, name: str) -> Collection:
        c = self._collections.get(name)
        if c is None:
            c = Collection(name)
            self._collections[name] = c
        return c

    def __getattr__(self, name: str) -> Collection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._coll(name)

    def __getitem__(self, name: str) -> Collection:
        return self._coll(name)


_database: Database | None = None


def get_database() -> Database:
    global _database
    if _database is None:
        _database = Database()
    return _database


__all__ = [
    "Collection",
    "Database",
    "get_database",
]
