import logging
import os
import threading
from datetime import datetime, timezone

import httpx

from dotenv import load_dotenv
load_dotenv()

failure_counts: dict[str, int] = {}
_failure_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def _send_telegram_message(message: str) -> None:
    api_key = os.getenv('TELEGRAM_API_KEY', '').strip()
    if not api_key:
        return

    raw_chat_ids = os.getenv('TELEGRAM_CHAT_IDS', '').strip()
    chat_ids = [item.strip() for item in raw_chat_ids.split(',') if item.strip()]
    if not chat_ids:
        return

    endpoint = f'https://api.telegram.org/bot{api_key}/sendMessage'
    for chat_id in chat_ids:
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }
        try:
            httpx.post(endpoint, data=payload, timeout=5.0)
        except Exception as error:
            logger.warning('Failed to send Telegram alert to chat_id %s: %s', chat_id, error)


def check_and_alert(
    service_name: str,
    is_healthy: bool,
    environment: str,
    error_message: str | None,
    version_drift: bool,
    expected_version: str | None = None,
    version_found: str | None = None,
) -> None:
    with _failure_lock:
        current_failures = failure_counts.get(service_name, 0)

        if not is_healthy:
            current_failures += 1
            failure_counts[service_name] = current_failures
            logger.warning(
                'Service unhealthy | service=%s environment=%s failures=%s error=%s',
                service_name,
                environment,
                current_failures,
                error_message,
            )

            if current_failures == 3:
                down_message = (
                    '🔴 <b>Service Down</b>\n'
                    f'Service: {service_name}\n'
                    f'Environment: {environment}\n'
                    f'Failures: {current_failures} consecutive\n'
                    f'Error: {error_message or "Unknown error"}\n'
                    f'Time: {_now_utc()}'
                )
                logger.error('ALERT: Service down triggered for %s', service_name)
                _send_telegram_message(down_message)
        else:
            if current_failures > 0:
                recovery_message = (
                    '✅ <b>Service Recovered</b>\n'
                    f'Service: {service_name}\n'
                    f'Environment: {environment}\n'
                    f'Time: {_now_utc()}'
                )
                logger.info('ALERT: Service recovered for %s', service_name)
                _send_telegram_message(recovery_message)
            failure_counts[service_name] = 0

        if version_drift:
            drift_message = (
                '⚠️ <b>Version Drift Detected</b>\n'
                f'Service: {service_name}\n'
                f'Environment: {environment}\n'
                f'Expected: {expected_version or "Unknown"}\n'
                f'Found: {version_found or "Unknown"}\n'
                f'Time: {_now_utc()}'
            )
            logger.warning(
                'ALERT: Version drift | service=%s environment=%s expected=%s found=%s',
                service_name,
                environment,
                expected_version,
                version_found,
            )
            _send_telegram_message(drift_message)
