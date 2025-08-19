## Configuration Management Service (Twisted)

### Features
- Async REST API on Twisted + Klein
- Postgres storage (jsonb) with versioning
- YAML input, JSON output
- Optional Jinja2 templating on GET
- Dockerized with docker-compose
- Type-annotated, modular codebase + basic tests

### API

#### POST `/config/<service>`
- **Purpose**: upload a new configuration in YAML
- **Request body (YAML)**: required fields `database.host: str`, `database.port: int`; optional field `version: int` (auto-assigned to `max(version)+1` if missing)
- **Status codes**:
  - `200` — `{"service": "<service>", "version": <int>, "status": "saved"}`
  - `400` — invalid YAML or top-level is not a mapping
  - `409` — duplicate version for the service
  - `422` — validation error (e.g., missing required field or wrong type)

Example:
```bash
curl -X POST \
  -H "Content-Type: text/plain" \
  --data-binary @- http://localhost:8080/config/orders <<'YAML'
version: 2
database:
  host: db.local
  port: 5432
features:
  enable_auth: true
  enable_cache: false
YAML
```

#### GET `/config/<service>`
- **Query params**:
  - `version` — optional, requested version (int). If absent, returns the latest version
  - `template=1` — optional; if present, string values are processed via Jinja2
- **Request body**: when `template=1`, you may pass a JSON context in the request body (e.g., `{"user":"Alice"}`)
- **Response**: JSON configuration
- **Status codes**:
  - `200` — configuration JSON
  - `400` — non-integer `version` or invalid JSON context / template rendering error
  - `404` — service or version not found

Examples:
```bash
curl http://localhost:8080/config/orders               # latest version
curl "http://localhost:8080/config/orders?version=3"  # specific version
curl -X GET "http://localhost:8080/config/orders?template=1" \
  -H "Content-Type: application/json" \
  --data '{"user": "Alice"}'
```

#### GET `/config/<service>/history`
- **Purpose**: return the list of versions in ascending order
- **Response**: array of `{ "version": int, "created_at": ISO8601 }`
- **Status codes**:
  - `200` — history returned
  - `404` — service not found (no versions)

### Quick start (Docker)
```bash
docker compose up --build
```
App: http://localhost:8080

### Local development
```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Start Postgres separately or via docker-compose
# Linux/macOS
export DB_HOST=localhost DB_PORT=5432 DB_NAME=configs DB_USER=configs DB_PASSWORD=configs
python -m app.main

# Windows PowerShell
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_NAME = "configs"
$env:DB_USER = "configs"
$env:DB_PASSWORD = "configs"
python -m app.main
```

### Testing
```bash
pytest -q
```

### Env vars
- `APP_PORT` (default: 8080)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

### Errors and status codes
- `400 Bad Request`:
  - invalid YAML (POST)
  - non-integer `version` (GET with `version`) or invalid JSON context / template rendering error
  - top-level YAML is not a mapping
- `409 Conflict`:
  - duplicate version on insert
- `422 Unprocessable Entity`:
  - domain validation failed: missing `database.host`/`database.port`, or wrong types; or `version` provided and not int
- `404 Not Found`:
  - service or version not found; or no history exists for the service
