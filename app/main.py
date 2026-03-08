import json
import logging
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates

from app.ai import ask_ai
from app.chat_history_db import add_chat_turn, get_chat_turns
from app.database import (
    get_ai_context_history,
    get_ai_context_snapshot,
    get_history,
    get_latest_per_service,
    purge_old_records,
)

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title='Service Reliability Checker')
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / 'templates'))
services_path = Path(__file__).resolve().parent.parent / 'services.json'
logger = logging.getLogger(__name__)

PURGE_RETENTION_DAYS = int(os.getenv('PURGE_RETENTION_DAYS', '90'))
PURGE_INTERVAL_SECONDS = int(os.getenv('PURGE_INTERVAL_SECONDS', '3600'))
MAX_CHAT_MESSAGES = int(os.getenv('MAX_CHAT_MESSAGES', '3'))

_purge_stop_event = threading.Event()
_purge_thread: threading.Thread | None = None


class ChatQuestion(BaseModel):
    question: str


def _load_service_metadata() -> dict[str, dict]:
    with services_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)
    return {
        item['name']: {
            'expected_version': item.get('expected_version'),
            'environment': item.get('environment'),
            'url': item.get('url'),
            'interval_seconds': item.get('interval_seconds'),
        }
        for item in payload.get('services', [])
    }


@app.on_event('startup')
def startup_event() -> None:
    purge_old_records(days=PURGE_RETENTION_DAYS)

    def _purge_loop() -> None:
        while not _purge_stop_event.wait(PURGE_INTERVAL_SECONDS):
            try:
                purge_old_records(days=PURGE_RETENTION_DAYS)
            except Exception:
                logger.exception('Periodic purge failed')

    global _purge_thread
    if _purge_thread is None or not _purge_thread.is_alive():
        _purge_stop_event.clear()
        _purge_thread = threading.Thread(target=_purge_loop, daemon=True, name='purge-scheduler')
        _purge_thread.start()


@app.on_event('shutdown')
def shutdown_event() -> None:
    _purge_stop_event.set()


@app.get('/')
def dashboard(request: Request):
    return templates.TemplateResponse('dashboard.html', {'request': request})


@app.get('/api/status')
def api_status():
    latest = get_latest_per_service()
    metadata = _load_service_metadata()

    for item in latest:
        service_metadata = metadata.get(item.get('service_name', ''), {})
        item['expected_version'] = service_metadata.get('expected_version')

    return latest


@app.get('/api/history/{service_name}')
def api_history(service_name: str, limit: int = Query(default=50, ge=1, le=500)):
    return get_history(service_name, limit=limit)


@app.get('/history/{service_name}')
def history_page(request: Request, service_name: str):
    return templates.TemplateResponse(
        'history.html',
        {
            'request': request,
            'service_name': service_name,
        },
    )


@app.post('/api/chat/snapshot')
async def chat_snapshot(payload: ChatQuestion):
    context = get_ai_context_snapshot()
    answer = await ask_ai(context=context, question=payload.question)
    add_chat_turn(
        scope='snapshot',
        service_name='',
        user_message=payload.question,
        ai_message=answer,
        max_messages=MAX_CHAT_MESSAGES,
    )
    return {
        'answer': answer,
        'history': get_chat_turns(scope='snapshot', service_name='', limit=MAX_CHAT_MESSAGES),
    }


@app.post('/api/chat/history/{service_name}')
async def chat_history(service_name: str, payload: ChatQuestion):
    context = get_ai_context_history(service_name)
    answer = await ask_ai(context=context, question=payload.question)
    add_chat_turn(
        scope='service-history',
        service_name=service_name,
        user_message=payload.question,
        ai_message=answer,
        max_messages=MAX_CHAT_MESSAGES,
    )
    return {
        'answer': answer,
        'history': get_chat_turns(
            scope='service-history',
            service_name=service_name,
            limit=MAX_CHAT_MESSAGES,
        ),
    }


@app.get('/api/chat/snapshot/history')
def chat_snapshot_history():
    return {
        'history': get_chat_turns(scope='snapshot', service_name='', limit=MAX_CHAT_MESSAGES),
    }


@app.get('/api/chat/history/{service_name}/messages')
def chat_service_history_messages(service_name: str):
    return {
        'history': get_chat_turns(
            scope='service-history',
            service_name=service_name,
            limit=MAX_CHAT_MESSAGES,
        ),
    }
