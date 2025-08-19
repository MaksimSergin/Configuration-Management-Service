from __future__ import annotations

import json
from typing import Any, Dict, Optional

import yaml
from klein import Klein
from twisted.internet import defer
from twisted.web.http import BAD_REQUEST, NOT_FOUND
from psycopg2.errors import UniqueViolation

from .models import validate_payload, ValidationError
from .repository import ConfigRepository
from .template import render_jinja_on_dict


class Api:
	app = Klein()

	def __init__(self, repo: ConfigRepository):
		self._repo = repo

	@app.route("/health", methods=["GET"])
	def health(self, request):
		request.setHeader(b"content-type", b"application/json")
		return json.dumps({"status": "ok"}).encode()

	@app.route("/config/<service>", methods=["POST"])
	@defer.inlineCallbacks
	def upload_config(self, request, service: str):
		request.setHeader(b"content-type", b"application/json")
		body = request.content.read()
		try:
			data = yaml.safe_load(body) or {}
		except Exception as exc:
			request.setResponseCode(BAD_REQUEST)
			defer.returnValue(json.dumps({"error": f"Invalid YAML: {exc}"}).encode())

		if not isinstance(data, dict):
			request.setResponseCode(BAD_REQUEST)
			defer.returnValue(json.dumps({"error": "Top-level YAML must be a mapping"}).encode())

		# If version is missing, we will auto-assign below from repository
		try:
			validate_payload(data)
		except ValidationError as ve:
			request.setResponseCode(422)
			defer.returnValue(json.dumps({"errors": ve.errors}).encode())

		requested_version: Optional[int] = data.get("version") if isinstance(data.get("version"), int) else None
		latest = yield self._repo.get_latest_version(service)
		version = requested_version if requested_version is not None else ((latest or 0) + 1)

		# Ensure stored payload contains version for better UX
		data_with_version = dict(data)
		data_with_version["version"] = version

		try:
			yield self._repo.insert_config(service, version, data_with_version)
		except UniqueViolation as exc:
			request.setResponseCode(409)
			defer.returnValue(json.dumps({"error": "duplicate version"}).encode())
		except Exception as exc:
			# Fallback: some in-memory or alternative repos may raise generic exceptions
			msg = str(exc).lower()
			if ("duplicate" in msg and "unique" in msg) or "unique constraint" in msg:
				request.setResponseCode(409)
				defer.returnValue(json.dumps({"error": "duplicate version"}).encode())
			request.setResponseCode(BAD_REQUEST)
			defer.returnValue(json.dumps({"error": str(exc)}).encode())

		defer.returnValue(json.dumps({"service": service, "version": version, "status": "saved"}).encode())

	@app.route("/config/<service>", methods=["GET"])
	@defer.inlineCallbacks
	def get_config(self, request, service: str):
		request.setHeader(b"content-type", b"application/json")
		args = request.args or {}
		version: Optional[int] = None
		if b"version" in args:
			try:
				version = int(args[b"version"][0])
			except Exception:
				request.setResponseCode(BAD_REQUEST)
				defer.returnValue(json.dumps({"error": "version must be integer"}).encode())

		row = yield self._repo.get_config(service, version)
		if not row:
			request.setResponseCode(NOT_FOUND)
			defer.returnValue(json.dumps({"error": "service or version not found"}).encode())

		payload, actual_version = row

		use_template = b"template" in args and args[b"template"][0] in (b"1", b"true", b"True")
		if use_template:
			# Optional JSON body with context
			try:
				body = request.content.read() or b""
				context: Dict[str, Any] = json.loads(body.decode() or "{}") if body else {}
			except Exception as exc:
				request.setResponseCode(BAD_REQUEST)
				defer.returnValue(json.dumps({"error": f"Invalid JSON context: {exc}"}).encode())
			try:
				payload = render_jinja_on_dict(payload, context)
			except Exception as exc:
				request.setResponseCode(BAD_REQUEST)
				defer.returnValue(json.dumps({"error": f"Template rendering error: {exc}"}).encode())

		defer.returnValue(json.dumps(payload).encode())

	@app.route("/config/<service>/history", methods=["GET"])
	@defer.inlineCallbacks
	def get_history(self, request, service: str):
		request.setHeader(b"content-type", b"application/json")
		rows = yield self._repo.get_history(service)
		if not rows:
			request.setResponseCode(NOT_FOUND)
			defer.returnValue(json.dumps({"error": "service not found"}).encode())
		items = [
			{"version": r[0], "created_at": r[1].isoformat()}
			for r in rows
		]
		defer.returnValue(json.dumps(items).encode())
