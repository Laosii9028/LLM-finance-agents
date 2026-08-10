# -*- coding: utf-8 -*-
"""把日報推送到 Discord，支援限流與暫時性錯誤重試。"""

import random
import time

import requests

MAX_DESC = 4000
MAX_ATTEMPTS = 7
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _split(text, size):
    chunks, current = [], ""
    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 > size:
            if current:
                chunks.append(current)
            # 單一段落本身過長時也必須硬切，避免 Discord 400。
            while len(paragraph) > size:
                chunks.append(paragraph[:size])
                paragraph = paragraph[size:]
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks or [text]


def _retry_delay(response, attempt):
    if response is not None and response.status_code == 429:
        try:
            delay = float(response.json().get("retry_after", 0))
            if delay > 0:
                return min(delay, 120)
        except (TypeError, ValueError, requests.exceptions.JSONDecodeError):
            pass
        try:
            header = response.headers.get("Retry-After")
            if header:
                return min(float(header), 120)
        except ValueError:
            pass
    return min(2 ** attempt, 64) + random.uniform(0, 1)


def _post_with_retry(webhook_url, payload):
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = None
        try:
            response = requests.post(
                webhook_url, json=payload, timeout=(10, 30)
            )
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return
            last_error = requests.HTTPError(
                f"Discord 暫時失敗: HTTP {response.status_code}",
                response=response,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
        except requests.HTTPError:
            raise

        if attempt == MAX_ATTEMPTS:
            break
        delay = _retry_delay(response, attempt)
        status = response.status_code if response is not None else type(last_error).__name__
        print(f"Discord 傳送失敗({status})，{delay:.1f} 秒後重試 ({attempt}/{MAX_ATTEMPTS})")
        time.sleep(delay)
    raise RuntimeError(
        f"Discord webhook 重試 {MAX_ATTEMPTS} 次後仍失敗"
    ) from last_error


def push(webhook_url, title, body, dashboard_url=None):
    for index, chunk in enumerate(_split(body, MAX_DESC)):
        embed = {
            "title": title if index == 0 else f"{title}(續 {index + 1})",
            "description": chunk,
            "color": 0x1D9E75,
        }
        _post_with_retry(webhook_url, {"embeds": [embed]})
    if dashboard_url:
        _post_with_retry(
            webhook_url, {"content": f"🔗 最新網頁版：{dashboard_url}"}
        )
