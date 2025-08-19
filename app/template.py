from __future__ import annotations

from typing import Any, Dict

from jinja2 import Environment, StrictUndefined


def render_jinja_on_dict(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
	env = Environment(undefined=StrictUndefined, autoescape=False)
	def _render(value: Any) -> Any:
		if isinstance(value, str):
			return env.from_string(value).render(**context)
		if isinstance(value, dict):
			return {k: _render(v) for k, v in value.items()}
		if isinstance(value, list):
			return [_render(v) for v in value]
		return value
	return _render(data)
