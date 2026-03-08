# Service Reliability Checker

A lightweight service health monitoring tool that periodically polls configured endpoints, detects availability and version issues, and displays results through a live dashboard with an AI-powered chat assistant.

---

## Quickstart

### Run with Docker (Recommended)

```bash
git clone <your-repo-url>
cd service-reliability

cp .env.example .env
# Edit .env with your Telegram and OpenAI keys if desired

docker compose up --build
```

Open: `http://localhost:8000`

SQLite data persists via the mounted `./data` volume — restarts will not lose history.

### Run Locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env as needed
```

Start the poller in one terminal:
```bash
python -m app.poller
```

Start the API in a second terminal:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

---

## Configuration

### Adding Services

Edit `services.json`:

```json
{
  "services": [
    {
      "name": "JSONPlaceholder",
      "url": "https://jsonplaceholder.typicode.com/posts/1",
      "expected_version": null,
      "environment": "production",
      "interval_seconds": 15
    },
    {
      "name": "HTTPBin Health",
      "url": "https://httpbin.org/status/200",
      "expected_version": "1.0.0",
      "environment": "staging",
      "interval_seconds": 20
    },
    {
      "name": "Broken Service",
      "url": "https://httpbin.org/status/500",
      "expected_version": "1.0.0",
      "environment": "staging",
      "interval_seconds": 15
    }
  ]
}
```

Each service is polled on its own thread at its own interval. Changes to `services.json` require a restart.

### Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_API_KEY` | Optional | Bot token for Telegram alerts |
| `TELEGRAM_CHAT_IDS` | Optional | Comma-separated chat/group IDs |
| `OPENAI_API_KEY` | Optional | Enables AI chat assistant |
| `OPENAI_MODEL` | Optional | Defaults to `gpt-4o-mini` |
| `MAX_CHAT_MESSAGES` | Optional | Chat history cap per context, defaults to `3` |
| `PURGE_RETENTION_DAYS` | Optional | Number of days to keep health check records before purge |
| `PURGE_INTERVAL_SECONDS` | Optional | Interval (in seconds) between periodic purge runs |

All integrations degrade gracefully — if a key is missing, that feature is silently skipped and the rest of the app continues normally.

---

## Features

### Core
- Polls each configured service endpoint on a dedicated thread
- Records status code, latency, version, and error messages per check
- Stores all results persistently in SQLite at `./data/health.db`
- Auto-purges records older than 7 days on startup
- Dashboard auto-refreshes every 30 seconds

### Version Drift Detection
If a service returns a `version` field in its health response, it is compared against the `expected_version` in `services.json`. Drift is flagged visually on the dashboard and triggers an immediate Telegram alert.

### Environment Grouping
Services are grouped by environment on the dashboard (production first, then staging). Environment badges are colour-coded for quick scanning.

### Degraded State Detection
A service returning a 2xx status code but with latency above 1000ms is marked as **Degraded** (🟡) rather than healthy, distinguishing slow services from fully down ones.

### Telegram Alerting
Alerts are sent after **3 consecutive failures** for a service, on **version drift detection**, and on **service recovery**. If `TELEGRAM_API_KEY` is not configured, alerting is skipped silently without affecting polling.

### AI Chat Assistant
Each page includes a chat widget powered by OpenAI (`gpt-4o-mini` by default):
- **Dashboard chat** — ask questions about the current snapshot across all services
- **History page chat** — ask questions scoped to the last 10 checks of a specific service

Suggested prompt chips are provided for quick access. Chat history is persisted in `./data/chat_history.db`, capped at the last 3 exchanges per context to control token usage and keep responses relevant.

If `OPENAI_API_KEY` is not set, the chat widget renders but returns a fallback message — the rest of the dashboard is unaffected.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main dashboard |
| `GET` | `/history/{service_name}` | History page for a service |
| `GET` | `/api/status` | Latest check per service (JSON) |
| `GET` | `/api/history/{service_name}` | Last 50 checks for a service (JSON) |
| `POST` | `/api/chat/snapshot` | AI chat against current snapshot |
| `POST` | `/api/chat/history/{service_name}` | AI chat against service history |
| `GET` | `/api/chat/snapshot/history` | Persisted snapshot chat history |
| `GET` | `/api/chat/history/{service_name}/messages` | Persisted service chat history |

---

## Project Structure

```
service-reliability/
├── app/
│   ├── main.py              # FastAPI app, routes, startup
│   ├── poller.py            # Per-service polling threads
│   ├── database.py          # SQLite health check read/write
│   ├── chat_history_db.py   # SQLite chat history, capped per context
│   ├── alerts.py            # Console + Telegram alerting
│   ├── ai.py                # OpenAI chat completions via httpx
│   └── templates/
│       ├── dashboard.html   # Main dashboard with chat widget
│       └── history.html     # Per-service history with chat widget
├── services.json            # Service configuration
├── entrypoint.sh            # Starts poller + uvicorn
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Design Overview and Trade-offs

### What Was Prioritised
- **Single deployable unit** — poller and API run in one container via `entrypoint.sh`, keeping the setup simple without requiring orchestration
- **Zero heavy dependencies** — raw `sqlite3` instead of SQLAlchemy, `httpx` instead of the OpenAI SDK, stdlib `threading` and `logging` throughout
- **Graceful degradation** — Telegram and OpenAI are fully optional; missing keys never crash the app
- **Config as code** — `services.json` is version-controlled, making changes auditable and intentional

### Known Trade-offs

| Decision | Trade-off |
|---|---|
| Single container for poller + API | Simpler to run, but if the API crashes it takes the poller with it. In production these would be separate services. |
| SQLite | Zero infrastructure cost, but not suitable for multiple concurrent writers or horizontal scaling. |
| In-memory failure counters in `alerts.py` | Simple and fast, but counter resets on restart. A restarted container won't remember it had 2 consecutive failures. |
| `services.json` requires restart to update | Intentional — changes are auditable via git. A future improvement would be a hot-reload watcher. |
| Chat history capped at 3 exchanges | Keeps OpenAI token usage low and responses focused on recent context. |

---

## Infrastructure / Deployment Notes

In production, I would split the poller and API into two separate ECS Fargate tasks sharing a common EFS volume for the SQLite file. This isolates failure domains — a crashing API does not interrupt polling, and each can be scaled or redeployed independently.

For the SQLite persistence layer, EFS works at low scale, but the natural migration path as load grows is to swap `database.py` for a PostgreSQL backend (RDS or Aurora Serverless), which requires minimal changes given the current abstraction.

The `services.json` config would be stored in S3 or AWS AppConfig, allowing updates without a container rebuild. The poller would poll for config changes on a slow interval (e.g. every 5 minutes) and reload its thread pool accordingly.

For observability, the existing console logging would be routed to CloudWatch Logs via the ECS log driver. A CloudWatch alarm on the API's 5xx rate and a dead-man's switch alarm (alert if no health check rows written in the last N minutes) would cover the two most important failure modes: the API is broken, or the poller has silently stopped.

Telegram alerting would remain for developer-facing notifications. For broader incident management, the webhook pattern in `alerts.py` could be extended to post to PagerDuty or an SNS topic.

Deployments would be handled via a CI/CD pipeline (GitHub Actions) that builds and pushes the Docker image to ECR, then triggers an ECS rolling update. The `expected_version` field in `services.json` would be updated as part of the same pipeline, so version drift detection catches any environment where the rollout did not complete cleanly.

---

## AI Usage

This project was built with AI assistance in the following stages:

- **Architecture and scoping** — Claude was used to brainstorm the project structure, evaluate trade-offs (e.g. config file vs database for service list, single container vs docker-compose split), and define the data model before any code was written
- **Copilot code generation** — GitHub Copilot generated the majority of the implementation files based on detailed briefs, including `database.py`, `poller.py`, `alerts.py`, `ai.py`, and both HTML templates
- **Telegram alert translation** — existing JS boilerplate was provided to Copilot and translated to Python `httpx` calls
- **Chat history feature** — Copilot designed and implemented `chat_history_db.py` and wired the persistent chat history into both frontend templates and API endpoints
- **README drafting** — Claude drafted this README based on the implemented feature set and assignment requirements