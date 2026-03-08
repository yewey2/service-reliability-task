# Full Brief — Service Reliability Checker

## Compiled: 3.12pm (~1 hour of brainstorming)

---

## Project Structure
```
service-reliability/
├── app/
│   ├── main.py            
│   ├── poller.py          
│   ├── database.py        
│   ├── alerts.py          
│   └── templates/
│       └── dashboard.html
├── services.json          
├── entrypoint.sh          
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## File-by-File Scope

### `services.json`
```json
{
  "services": [
    {
      "name": "Payment API",
      "url": "https://api.example.com/health",
      "expected_version": "2.1.0",
      "environment": "production",
      "interval_seconds": 60
    },
    {
      "name": "Auth Service",
      "url": "https://auth.staging.example.com/health",
      "expected_version": "1.4.2",
      "environment": "staging",
      "interval_seconds": 30
    }
  ]
}
```

---

### `database.py`
- Use raw `sqlite3` (stdlib, no SQLAlchemy needed)
- On startup, create table if not exists:
```
health_checks:
  - id INTEGER PRIMARY KEY AUTOINCREMENT
  - service_name TEXT
  - environment TEXT
  - checked_at TIMESTAMP
  - status_code INTEGER
  - latency_ms REAL
  - version_found TEXT        ← parsed from response body if available
  - is_healthy BOOLEAN        ← True if 2xx response
  - version_drift BOOLEAN     ← True if version_found != expected_version
  - error_message TEXT        ← null if healthy, e.g. "Connection timeout"
```
- Functions to expose:
  - `insert_check(result: dict)` — write one poll result
  - `get_latest_per_service()` — one row per service, most recent only
  - `get_history(service_name, limit=50)` — last N checks for a service
  - `purge_old_records(days=90)` — delete records older than 7 days, call this on startup

---

### `poller.py`
- Load `services.json` at startup
- For each service, run a polling loop with `time.sleep(interval_seconds)`
- Each poll should:
  1. Send `GET` request to the service URL with a **5 second timeout**
  2. Record `latency_ms` (time from request to response)
  3. Try to parse response body as JSON, look for a `version` field
  4. Determine `is_healthy` — True if status code is 2xx
  5. Determine `version_drift` — True if `version_found != expected_version` (skip if no version in response)
  6. On any exception (timeout, connection error), mark `is_healthy=False`, store error message
  7. Call `insert_check()` from `database.py`
  8. After insert, call `check_and_alert()` from `alerts.py`
- Run each service in its **own thread** so different intervals don't block each other
- Add basic logging with `logging` stdlib — log each poll result to console

---

### `alerts.py`
- Track consecutive failures **in memory** using a dict:
```python
failure_counts = {}  # { service_name: int }
```
- `check_and_alert(service_name, is_healthy, environment, error_message, version_drift)`
  - If `is_healthy=False`: increment counter
  - If counter hits **3 consecutive failures**: trigger alert
  - If `is_healthy=True`: reset counter to 0
  - If `version_drift=True`: trigger version drift alert immediately (don't wait for 3 failures)
- Always log to console regardless of Telegram
- Telegram alert function — **translate the JS boilerplate to Python**:
  - Use `httpx` (already needed for poller) or `urllib` (stdlib) to POST to Telegram API
  - Read `TELEGRAM_API_KEY` from environment variable
  - Read `TELEGRAM_CHAT_IDS` from environment variable as comma-separated string, parse into list
  - If `TELEGRAM_API_KEY` is not set, **skip silently** (don't crash the poller)
  - Message format using HTML parse mode:
```
🔴 <b>Service Down</b>
Service: Payment API
Environment: production
Failures: 3 consecutive
Error: Connection timeout
Time: 2024-01-15 10:30:00 UTC
```
```
⚠️ <b>Version Drift Detected</b>
Service: Auth Service
Environment: staging
Expected: 1.4.2
Found: 1.3.9
Time: 2024-01-15 10:30:00 UTC
```
```
✅ <b>Service Recovered</b>
Service: Payment API
Environment: production
Time: 2024-01-15 10:35:00 UTC
```

---

### `main.py`
- FastAPI app
- On startup event: call `purge_old_records()` from database
- Endpoints:
  - `GET /` — serve `dashboard.html` using `Jinja2Templates`
  - `GET /api/status` — return `get_latest_per_service()` as JSON
  - `GET /api/history/{service_name}` — return `get_history(service_name)` as JSON
- Install Jinja2 for templating (`pip install jinja2`)

---

### `dashboard.html`
- Pure HTML, inline CSS, no external frameworks
- On page load, fetch `/api/status` using vanilla JS `fetch()`
- Auto-refresh every **30 seconds** using `setInterval`
- Display a **card per service** showing:
  - Service name + environment badge (color coded: green=production, blue=staging)
  - Status indicator: 🟢 Healthy / 🔴 Down / 🟡 Degraded (latency > 1000ms but 2xx)
  - Last checked timestamp
  - Latency in ms
  - Version found vs expected (highlight red if drift)
  - Last error message if unhealthy
- Group cards by environment (production first, then staging)
- Keep it clean — dark or light theme, your choice

---

### `entrypoint.sh`
```bash
#!/bin/sh
python app/poller.py &
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
```

---

### `docker-compose.yml`
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data      # persist SQLite file outside container
    env_file:
      - .env
```

---

### `requirements.txt`
```
fastapi
uvicorn
httpx
jinja2
```

---

### `.env.example`
```
TELEGRAM_API_KEY=your_bot_token_here
TELEGRAM_CHAT_IDS=your_telegram_id_1,your_telegram_id_2
```

---

## Key Constraints

1. **No SQLAlchemy** — use raw `sqlite3` only
2. **No external CSS frameworks** — inline styles only
3. **SQLite file path** should be `./data/health.db` so the volume mount in docker-compose persists it
4. **Do not hardcode** Telegram IDs or API keys — always read from environment
5. **Poller must not crash** if a service is unreachable — catch all exceptions per service
6. **Poller must not crash** if Telegram is misconfigured — alerts are best-effort
7. Each service runs in its **own thread** in poller.py

---

## What To Build Last (In Order)
```
1. database.py
2. alerts.py
3. poller.py
4. main.py
5. dashboard.html
6. entrypoint.sh + Dockerfile + docker-compose
7. Test with Docker
8. README.md
```