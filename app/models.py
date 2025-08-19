from __future__ import annotations

from typing import Any, Dict, Optional


class ValidationError(Exception):
	def __init__(self, errors: Dict[str, str]):
		super().__init__("Validation error")
		self.errors = errors


REQUIRED_FIELDS = [
	# version is optional (auto-assigned if missing)
	("database", dict),
	("database.host", str),
	("database.port", int),
]


def _lookup_path(payload: Dict[str, Any], path: str) -> Optional[Any]:
	node: Any = payload
	for part in path.split("."):
		if not isinstance(node, dict) or part not in node:
			return None
		node = node[part]
	return node


def validate_payload(payload: Dict[str, Any]) -> None:
	errors: Dict[str, str] = {}
	# If version is provided, ensure it is integer
	if "version" in payload and not isinstance(payload["version"], int):
		errors["version"] = "must be int"
	for field_path, expected_type in REQUIRED_FIELDS:
		value = _lookup_path(payload, field_path)
		if value is None:
			errors[field_path] = "is required"
			continue
		if not isinstance(value, expected_type):
			errors[field_path] = f"must be {expected_type.__name__}"
	if errors:
		raise ValidationError(errors)
