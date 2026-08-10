# -*- coding: utf-8 -*-
"""抓美股新聞與重點追蹤股近期財報日曆。"""

import csv
import io
from datetime import date, datetime, timedelta, timezone

import requests


def fetch_news(api_key, limit=20, weekend_mode=False):
    params = {
        "function": "NEWS_SENTIMENT",
        "topics": "financial_markets,economy_macro,technology",
        "sort": "LATEST",
        "limit": str(30 if weekend_mode else limit),
        "apikey": api_key,
    }
    if weekend_mode:
        start = datetime.now(timezone.utc) - timedelta(hours=72)
        params["time_from"] = start.strftime("%Y%m%dT%H%M")
    try:
        response = requests.get(
            "https://www.alphavantage.co/query", params=params, timeout=30
        )
        response.raise_for_status()
        items = []
        for article in response.json().get("feed", [])[: int(params["limit"])]:
            tickers = [
                x.get("ticker") for x in article.get("ticker_sentiment", [])[:5]
                if x.get("ticker")
            ]
            items.append({
                "title": article.get("title", ""),
                "summary": article.get("summary", "")[:280],
                "source": article.get("source", ""),
                "sentiment": article.get("overall_sentiment_label", ""),
                "tickers": tickers,
                "published": article.get("time_published", ""),
            })
        return items
    except Exception as exc:
        print(f"[warn] 新聞抓取失敗: {exc}")
        return []


def fetch_upcoming_earnings(api_key, symbols, days=3):
    params = {
        "function": "EARNINGS_CALENDAR",
        "horizon": "3month",
        "apikey": api_key,
    }
    wanted = {symbol.upper() for symbol in symbols}
    start, end = date.today(), date.today() + timedelta(days=days)
    try:
        response = requests.get(
            "https://www.alphavantage.co/query", params=params, timeout=45
        )
        response.raise_for_status()
        events = []
        for row in csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))):
            symbol = (row.get("symbol") or "").upper()
            report_date = row.get("reportDate") or ""
            if symbol not in wanted or not report_date:
                continue
            try:
                event_date = date.fromisoformat(report_date)
            except ValueError:
                continue
            if start <= event_date <= end:
                events.append({
                    "symbol": symbol,
                    "name": row.get("name") or "",
                    "date": report_date,
                    "estimate": row.get("estimate") or "",
                    "currency": row.get("currency") or "",
                })
        return sorted(events, key=lambda x: (x["date"], x["symbol"]))
    except Exception as exc:
        print(f"[warn] 財報日曆抓取失敗: {exc}")
        return []


def fmt_earnings(events):
    if not events:
        return "(未取得近期重點股財報；不得自行猜測日期)"
    lines = []
    for event in events:
        estimate = event.get("estimate")
        estimate_text = (
            f"；預估 EPS {estimate} {event.get('currency', '')}" if estimate else ""
        )
        lines.append(
            f"- {event['date']} {event['symbol']} {event.get('name', '')}{estimate_text}"
        )
    return "\n".join(lines)
