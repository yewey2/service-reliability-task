import os
import sqlite3
import json
from pathlib import Path
from typing import Any


DB_PATH = os.path.join('.', 'data', 'health.db')

os.makedirs("data", exist_ok=True)

def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def _init_db() -> None:
    with _get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT,
                environment TEXT,
                checked_at TIMESTAMP,
                status_code INTEGER,
                latency_ms REAL,
                version_found TEXT,
                is_healthy BOOLEAN,
                version_drift BOOLEAN,
                error_message TEXT
            )
            '''
        )
        connection.commit()


def insert_check(result: dict[str, Any]) -> None:
    with _get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO health_checks (
                service_name,
                environment,
                checked_at,
                status_code,
                latency_ms,
                version_found,
                is_healthy,
                version_drift,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                result.get('service_name'),
                result.get('environment'),
                result.get('checked_at'),
                result.get('status_code'),
                result.get('latency_ms'),
                result.get('version_found'),
                int(bool(result.get('is_healthy'))),
                int(bool(result.get('version_drift'))),
                result.get('error_message'),
            ),
        )
        connection.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload['is_healthy'] = bool(payload.get('is_healthy'))
    payload['version_drift'] = bool(payload.get('version_drift'))
    return payload


def get_latest_per_service() -> list[dict[str, Any]]:
    with _get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT hc.*
            FROM health_checks hc
            INNER JOIN (
                SELECT service_name, environment, MAX(id) AS max_id
                FROM health_checks
                GROUP BY service_name, environment
            ) latest
              ON hc.id = latest.max_id
            ORDER BY
              CASE hc.environment
                WHEN 'production' THEN 0
                WHEN 'staging' THEN 1
                ELSE 2
              END,
              hc.service_name
            '''
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_history(service_name: str, limit: int = 50) -> list[dict[str, Any]]:
    with _get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT *
            FROM health_checks
            WHERE service_name = ?
            ORDER BY id DESC
            LIMIT ?
            ''',
            (service_name, limit),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def purge_old_records(days: int = 90) -> None:
    with _get_connection() as connection:
        connection.execute(
            '''
            DELETE FROM health_checks
            WHERE datetime(checked_at) < datetime('now', ?)
            ''',
            (f'-{days} days',),
        )
        connection.commit()


_init_db()


def _load_expected_versions() -> dict[str, str]:
    services_path = Path(__file__).resolve().parent.parent / 'services.json'
    if not services_path.exists():
        return {}

    try:
        with services_path.open('r', encoding='utf-8') as file:
            payload = json.load(file)
        return {
            item.get('name', ''): str(item.get('expected_version', 'N/A'))
            for item in payload.get('services', [])
            if item.get('name')
        }
    except Exception:
        return {}


def get_ai_context_snapshot() -> str:
    latest = get_latest_per_service()
    expected_versions = _load_expected_versions()

    if not latest:
        return 'No service checks available yet.'

    lines: list[str] = []
    for item in latest:
        service_name = item.get('service_name', 'Unknown')
        expected_version = expected_versions.get(service_name, 'N/A')
        latency = item.get('latency_ms')
        latency_value = f'{latency}ms' if latency is not None else 'N/A'
        healthy_value = 'Yes' if item.get('is_healthy') else 'No'
        drift_value = 'Yes' if item.get('version_drift') else 'No'
        status_code = item.get('status_code') if item.get('status_code') is not None else 'N/A'
        version_found = item.get('version_found') if item.get('version_found') is not None else 'N/A'
        checked_at = item.get('checked_at', 'N/A')
        error_message = item.get('error_message') or 'None'

        lines.append(
            f'Service: {service_name} | '
            f'Environment: {item.get("environment", "unknown")} | '
            f'Healthy: {healthy_value} | '
            f'Status: {status_code} | '
            f'Latency: {latency_value} | '
            f'Version Expected: {expected_version} | '
            f'Version Found: {version_found} | '
            f'Version Drift: {drift_value} | '
            f'Last Checked: {checked_at} | '
            f'Error: {error_message}'
        )

    return '\n'.join(lines)


def get_ai_context_history(service_name: str) -> str:
    records = get_history(service_name, limit=10)

    if not records:
        return f'No checks available for service: {service_name}'

    lines: list[str] = [f'Service: {service_name}']
    for index, item in enumerate(records, start=1):
        latency = item.get('latency_ms')
        latency_value = f'{latency}ms' if latency is not None else 'N/A'
        healthy_value = 'Yes' if item.get('is_healthy') else 'No'
        status_code = item.get('status_code') if item.get('status_code') is not None else 'N/A'
        version_found = item.get('version_found') if item.get('version_found') is not None else 'N/A'
        drift_value = 'Yes' if item.get('version_drift') else 'No'
        error_message = item.get('error_message') or 'None'

        lines.append(
            f'Check {index}: {item.get("checked_at", "N/A")} | '
            f'Healthy: {healthy_value} | '
            f'Status: {status_code} | '
            f'Latency: {latency_value} | '
            f'Version Found: {version_found} | '
            f'Version Drift: {drift_value} | '
            f'Error: {error_message}'
        )

    return '\n'.join(lines)
