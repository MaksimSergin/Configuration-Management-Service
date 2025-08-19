from __future__ import annotations

import json

from app.models import validate_payload, ValidationError
from app.template import render_jinja_on_dict


def test_validate_payload_ok():
	payload = {
		"version": 1,
		"database": {"host": "db", "port": 5432},
	}
	validate_payload(payload)


def test_validate_payload_errors():
	payload = {"database": {"host": 1, "port": "x"}}
	try:
		validate_payload(payload)
	except ValidationError as e:
		assert e.errors.get("database.host") == "must be str"
		assert e.errors.get("database.port") == "must be int"
	else:
		assert False, "ValidationError expected"


def test_jinja_rendering():
	payload = {"greeting": "Hello {{ user }}!", "nested": {"m": "{{ val }}"}}
	context = {"user": "Alice", "val": 10}
	result = render_jinja_on_dict(payload, context)
	assert result["greeting"] == "Hello Alice!"
	assert result["nested"]["m"] == "10"
