import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


CHAT_DB_PATH = os.path.join('.', 'data', 'chat_history.db')


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)
    connection = sqlite3.connect(CHAT_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def _init_db() -> None:
    with _get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS chat_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                service_name TEXT NOT NULL DEFAULT '',
                user_message TEXT NOT NULL,
                ai_message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            '''
        )
        connection.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def add_chat_turn(
    scope: str,
    service_name: str,
    user_message: str,
    ai_message: str,
    max_messages: int = 3,
) -> None:
    safe_service_name = service_name or ''
    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    with _get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO chat_turns (scope, service_name, user_message, ai_message, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (scope, safe_service_name, user_message, ai_message, created_at),
        )

        connection.execute(
            '''
            DELETE FROM chat_turns
            WHERE scope = ?
              AND service_name = ?
              AND id NOT IN (
                  SELECT id FROM chat_turns
                  WHERE scope = ? AND service_name = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
            ''',
            (scope, safe_service_name, scope, safe_service_name, max_messages),
        )
        connection.commit()


def get_chat_turns(scope: str, service_name: str, limit: int = 3) -> list[dict[str, Any]]:
    safe_service_name = service_name or ''
    with _get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT *
            FROM chat_turns
            WHERE scope = ? AND service_name = ?
            ORDER BY id DESC
            LIMIT ?
            ''',
            (scope, safe_service_name, limit),
        ).fetchall()

    ordered = list(reversed(rows))
    return [_row_to_dict(row) for row in ordered]


_init_db()
