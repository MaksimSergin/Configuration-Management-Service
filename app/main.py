from __future__ import annotations

from typing import Any

from twisted.internet import reactor, defer
from twisted.web.server import Site

from .api import Api
from .config import load_config
from .db import Database
from .repository import ConfigRepository


def main() -> None:
	cfg = load_config()
	db = Database(cfg)
	repo = ConfigRepository(db)
	api = Api(repo)

	@defer.inlineCallbacks
	def _start():
		yield db.init_schema()
		site = Site(api.app.resource())
		reactor.listenTCP(cfg.port, site)

	reactor.callWhenRunning(_start)
	reactor.run()


if __name__ == "__main__":
	main()
