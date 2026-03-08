import os

import httpx

import logging
import traceback


SYSTEM_PROMPT = (
    'You are a service reliability assistant. You help engineers understand the health of their '
    'services. Be concise and direct. Use bullet points where helpful. If you see version drift '
    'or repeated failures, highlight them clearly.'
)


async def ask_ai(context: str, question: str) -> str:
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return 'AI assistant is not configured. Please set OPENAI_API_KEY in your environment.'

    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini').strip() or 'gpt-4o-mini'

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': SYSTEM_PROMPT,
            },
            {
                'role': 'user',
                'content': f'Here is the current service data:\n\n{context}\n\nQuestion: {question}',
            },
        ],
        'max_tokens': 500,
        'temperature': 0.3,
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                'https://api.openai.com/v1/chat/completions',
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            response_payload = response.json()
            return (
                response_payload.get('choices', [{}])[0]
                .get('message', {})
                .get('content', '')
                .strip()
                or 'AI assistant is temporarily unavailable. Please check the dashboard directly.' + ' (No content in response)'
            )
    except Exception:
        logging.exception('Error while communicating with OpenAI API')
        traceback.print_exc()
        return 'AI assistant is temporarily unavailable. Please check the dashboard directly.'
