from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from twisted.internet import defer
from txpostgres import txpostgres

from .config import AppConfig


class Database:
	def __init__(self, cfg: AppConfig):
		self._cfg = cfg
		self._conn: Optional[txpostgres.Connection] = None

	@defer.inlineCallbacks
	def connect(self) -> defer.Deferred:
		if self._conn is not None:
			defer.returnValue(self._conn)

		dsn = (
			f"host={self._cfg.db_host} port={self._cfg.db_port} "
			f"dbname={self._cfg.db_name} user={self._cfg.db_user} password={self._cfg.db_password}"
		)
		self._conn = txpostgres.Connection()
		yield self._conn.connect(dsn=dsn)
		defer.returnValue(self._conn)

	@defer.inlineCallbacks
	def init_schema(self) -> defer.Deferred:
		conn = yield self.connect()
		yield conn.runOperation(
			"""
			CREATE TABLE IF NOT EXISTS configurations (
				id SERIAL PRIMARY KEY,
				service TEXT NOT NULL,
				version INTEGER NOT NULL,
				payload JSONB NOT NULL,
				created_at TIMESTAMP DEFAULT NOW(),
				UNIQUE(service, version)
			);
			"""
		)

	@defer.inlineCallbacks
	def fetchone(self, query: str, params: Tuple[Any, ...]) -> defer.Deferred:
		conn = yield self.connect()
		row = yield conn.runQuery(query, params)
		defer.returnValue(row[0] if row else None)

	@defer.inlineCallbacks
	def fetchall(self, query: str, params: Tuple[Any, ...] = ()) -> defer.Deferred:
		conn = yield self.connect()
		rows = yield conn.runQuery(query, params)
		defer.returnValue(rows)

	@defer.inlineCallbacks
	def execute(self, query: str, params: Tuple[Any, ...]) -> defer.Deferred:
		conn = yield self.connect()
		yield conn.runOperation(query, params)
