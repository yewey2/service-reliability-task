import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

import httpx

from app.alerts import check_and_alert
from app.database import insert_check


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
)
logger = logging.getLogger(__name__)

SERVICES_PATH = Path(__file__).resolve().parent.parent / 'services.json'


def load_services() -> list[dict]:
    with SERVICES_PATH.open('r', encoding='utf-8') as file:
        payload = json.load(file)
    return payload.get('services', [])


def poll_service(service: dict) -> None:
    service_name = service.get('name', 'Unknown Service')
    environment = service.get('environment', 'unknown')
    url = service.get('url')
    expected_version = service.get('expected_version')
    interval_seconds = int(service.get('interval_seconds', 60))

    while True:
        checked_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        status_code = None
        latency_ms = None
        version_found = None
        is_healthy = False
        version_drift = False
        error_message = None

        start = time.perf_counter()
        try:
            response = httpx.get(url, timeout=5.0)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = response.status_code
            is_healthy = 200 <= status_code < 300

            try:
                response_json = response.json()
                if isinstance(response_json, dict):
                    version_found = response_json.get('version')
            except ValueError:
                version_found = None

            if version_found is not None and expected_version is not None:
                version_drift = str(version_found) != str(expected_version)
        except Exception as error:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            is_healthy = False
            error_message = str(error)

        result = {
            'service_name': service_name,
            'environment': environment,
            'checked_at': checked_at,
            'status_code': status_code,
            'latency_ms': latency_ms,
            'version_found': version_found,
            'is_healthy': is_healthy,
            'version_drift': version_drift,
            'error_message': error_message,
        }

        try:
            insert_check(result)
            check_and_alert(
                service_name=service_name,
                is_healthy=is_healthy,
                environment=environment,
                error_message=error_message,
                version_drift=version_drift,
                expected_version=expected_version,
                version_found=str(version_found) if version_found is not None else None,
            )
            logger.info(
                'Polled service=%s environment=%s status=%s healthy=%s latency_ms=%s version_found=%s drift=%s error=%s',
                service_name,
                environment,
                status_code,
                is_healthy,
                latency_ms,
                version_found,
                version_drift,
                error_message,
            )
        except Exception as error:
            logger.exception('Polling pipeline failed for service=%s: %s', service_name, error)

        time.sleep(interval_seconds)


def start_poller() -> list[Thread]:
    services = load_services()
    threads: list[Thread] = []
    for service in services:
        thread = Thread(
            target=poll_service,
            args=(service,),
            daemon=True,
            name=f"poller-{service.get('name', 'service')}",
        )
        thread.start()
        threads.append(thread)
        logger.info(
            'Started poller thread for service=%s interval=%ss',
            service.get('name'),
            service.get('interval_seconds', 60),
        )
    return threads


if __name__ == '__main__':
    running_threads = start_poller()
    for thread in running_threads:
        thread.join()
