from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import pytest
from twisted.internet import defer, reactor
from twisted.web.test.requesthelper import DummyRequest

from app.api import Api
from datetime import datetime, UTC


def _status(request: DummyRequest) -> Optional[int]:
	return getattr(request, "code", getattr(request, "responseCode", None))


class InMemoryRepo:
	"""In-memory repository to simulate DB behavior with async Deferreds."""

	def __init__(self) -> None:
		self._store: Dict[str, Dict[int, Dict[str, Any]]] = {}

	def get_latest_version(self, service: str):
		versions = sorted(self._store.get(service, {}).keys())
		return defer.succeed(versions[-1] if versions else None)

	def insert_config(self, service: str, version: int, payload: Dict[str, Any]):
		service_map = self._store.setdefault(service, {})
		if version in service_map:
			return defer.fail(Exception("duplicate key value violates unique constraint"))
		service_map[version] = payload
		return defer.succeed(None)

	def get_config(self, service: str, version: Optional[int]):
		service_map = self._store.get(service, {})
		if not service_map:
			return defer.succeed(None)
		if version is None:
			v = sorted(service_map.keys())[-1]
			return defer.succeed((service_map[v], v))
		if version in service_map:
			return defer.succeed((service_map[version], version))
		return defer.succeed(None)

	def get_history(self, service: str):
		service_map = self._store.get(service, {})
		rows = [(v, datetime.now(UTC)) for v in sorted(service_map.keys())]
		return defer.succeed(rows)


@pytest.fixture()
def api() -> Api:
	repo = InMemoryRepo()
	return Api(repo)


def _make_request(path: bytes, method: bytes = b"GET", body: Optional[bytes] = None, args: Optional[Dict[bytes, List[bytes]]] = None) -> DummyRequest:
	request = DummyRequest([seg for seg in path.split(b"/") if seg])
	request.method = method
	if args:
		request.args = args
	if body is not None:
		request.content = __import__("io").BytesIO(body)
	return request


def test_health(api: Api):
	request = _make_request(b"/health")
	resp = api.health(request)
	assert _status(request) in (None, 200)  # Klein/ DummyRequest may not set explicit 200
	assert json.loads(resp) == {"status": "ok"}


@defer.inlineCallbacks
def test_post_config_auto_version_and_get_latest(api: Api):
	# POST without version
	body_yaml = (
		b"database:\n  host: db.local\n  port: 5432\nfeatures:\n  enable_auth: true\n  enable_cache: false\n"
	)
	request = _make_request(b"/config/orders", method=b"POST", body=body_yaml)
	resp = yield api.upload_config(request, "orders")
	assert _status(request) in (None, 200)
	data = json.loads(resp)
	assert data["service"] == "orders"
	assert data["version"] == 1

	# GET latest
	request2 = _make_request(b"/config/orders")
	resp2 = yield api.get_config(request2, "orders")
	assert _status(request2) in (None, 200)
	payload = json.loads(resp2)
	assert payload["version"] == 1
	assert payload["database"]["host"] == "db.local"


@defer.inlineCallbacks
def test_post_config_with_explicit_version_and_conflict(api: Api):
	# First insert version 2
	body1 = (
		b"version: 2\ndatabase:\n  host: db.local\n  port: 5432\n"
	)
	req1 = _make_request(b"/config/orders", method=b"POST", body=body1)
	_ = yield api.upload_config(req1, "orders")
	assert _status(req1) in (None, 200)

	# Duplicate version 2 should fail
	req2 = _make_request(b"/config/orders", method=b"POST", body=body1)
	resp = yield api.upload_config(req2, "orders")
	assert _status(req2) == 409
	data = json.loads(resp)
	assert data.get("error") == "duplicate version"


@defer.inlineCallbacks
def test_yaml_invalid_and_top_level_type(api: Api):
	# invalid YAML
	req1 = _make_request(b"/config/orders", method=b"POST", body=b"version: :\n")
	resp1 = yield api.upload_config(req1, "orders")
	assert _status(req1) == 400
	assert "Invalid YAML" in json.loads(resp1)["error"]

	# top-level not a mapping
	req2 = _make_request(b"/config/orders", method=b"POST", body=b"- 1\n- 2\n")
	resp2 = yield api.upload_config(req2, "orders")
	assert _status(req2) == 400
	assert json.loads(resp2)["error"] == "Top-level YAML must be a mapping"


@defer.inlineCallbacks
def test_get_specific_version_and_not_found(api: Api):
	# Insert v1
	body = b"database:\n  host: h\n  port: 1\n"
	req1 = _make_request(b"/config/orders", method=b"POST", body=body)
	_ = yield api.upload_config(req1, "orders")
	assert _status(req1) in (None, 200)

	# Get v1 explicitly
	req2 = _make_request(b"/config/orders?version=1", args={b"version": [b"1"]})
	resp2 = yield api.get_config(req2, "orders")
	assert _status(req2) in (None, 200)
	assert json.loads(resp2)["version"] == 1

	# Not found service
	req3 = _make_request(b"/config/unknown")
	resp3 = yield api.get_config(req3, "unknown")
	assert _status(req3) == 404
	assert json.loads(resp3)["error"] == "service or version not found"

	# version non-integer must error
	req4 = _make_request(b"/config/orders?version=abc", args={b"version": [b"abc"]})
	resp4 = yield api.get_config(req4, "orders")
	assert _status(req4) == 400
	assert json.loads(resp4)["error"] == "version must be integer"


@defer.inlineCallbacks
def test_template_render_and_invalid_json_context(api: Api):
	# Insert v2 with template
	body = b"version: 2\nwelcome_message: 'Hello {{ user }}!'\ndatabase:\n  host: h\n  port: 2\n"
	req1 = _make_request(b"/config/orders", method=b"POST", body=body)
	_ = yield api.upload_config(req1, "orders")
	assert _status(req1) in (None, 200)

	# GET template applied
	args = {b"template": [b"1"]}
	req2 = _make_request(b"/config/orders?template=1", args=args, body=b"{\"user\":\"Alice\"}")
	resp2 = yield api.get_config(req2, "orders")
	assert _status(req2) in (None, 200)
	assert json.loads(resp2)["welcome_message"] == "Hello Alice!"

	# invalid JSON context
	req3 = _make_request(b"/config/orders?template=1", args=args, body=b"{user: Alice}")
	resp3 = yield api.get_config(req3, "orders")
	assert _status(req3) == 400
	assert "Invalid JSON context" in json.loads(resp3)["error"]

	# template rendering error (missing variable with StrictUndefined)
	args2 = {b"template": [b"1"]}
	req4 = _make_request(b"/config/orders?template=1", args=args2, body=b"{}")
	# Replace stored config with template referencing variable not provided in context
	api._repo._store["orders"][2] = {"version": 2, "welcome_message": "Hello {{ must_exist }}!", "database": {"host": "h", "port": 2}}
	resp4 = yield api.get_config(req4, "orders")
	assert _status(req4) == 400
	assert "Template rendering error" in json.loads(resp4)["error"]


@defer.inlineCallbacks
def test_history(api: Api):
	# Insert v1, v2, v3
	for v in (1, 2, 3):
		body = f"version: {v}\ndatabase:\n  host: h\n  port: 5\n".encode()
		req = _make_request(b"/config/orders", method=b"POST", body=body)
		_ = yield api.upload_config(req, "orders")
		assert _status(req) in (None, 200)

	# history for unknown service should 404
	req_empty = _make_request(b"/config/unknown/history")
	resp_empty = yield api.get_history(req_empty, "unknown")
	assert _status(req_empty) == 404
	assert json.loads(resp_empty)["error"] == "service not found"

	req_h = _make_request(b"/config/orders/history")
	resp_h = yield api.get_history(req_h, "orders")
	assert _status(req_h) in (None, 200)
	hist = json.loads(resp_h)
	assert [item["version"] for item in hist] == [1, 2, 3]
