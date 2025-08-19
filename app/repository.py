from __future__ import annotations

from typing import Any, Dict, Optional

from twisted.internet import defer
from psycopg2.extras import Json

from .db import Database


class ConfigRepository:
	def __init__(self, db: Database):
		self._db = db

	@defer.inlineCallbacks
	def get_latest_version(self, service: str) -> defer.Deferred:
		row = yield self._db.fetchone(
			"SELECT version FROM configurations WHERE service = %s ORDER BY version DESC LIMIT 1",
			(service,),
		)
		defer.returnValue(row[0] if row else None)

	@defer.inlineCallbacks
	def insert_config(self, service: str, version: int, payload: Dict[str, Any]) -> defer.Deferred:
		yield self._db.execute(
			"INSERT INTO configurations(service, version, payload) VALUES (%s, %s, %s)",
			(service, version, Json(payload)),
		)

	@defer.inlineCallbacks
	def get_config(self, service: str, version: Optional[int]) -> defer.Deferred:
		if version is None:
			row = yield self._db.fetchone(
				"SELECT payload, version FROM configurations WHERE service = %s ORDER BY version DESC LIMIT 1",
				(service,),
			)
			defer.returnValue(row)
		row = yield self._db.fetchone(
			"SELECT payload, version FROM configurations WHERE service = %s AND version = %s",
			(service, version),
		)
		defer.returnValue(row)

	@defer.inlineCallbacks
	def get_history(self, service: str) -> defer.Deferred:
		rows = yield self._db.fetchall(
			"SELECT version, created_at FROM configurations WHERE service = %s ORDER BY version ASC",
			(service,),
		)
		defer.returnValue(rows)
