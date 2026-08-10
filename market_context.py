# -*- coding: utf-8 -*-
"""補充專業市場報告需要的跨資產、類股輪動與市場廣度資料。"""

import yfinance as yf


CROSS_ASSETS = {
    "DX-Y.NYB": "美元指數 DXY",
    "CL=F": "WTI 原油",
    "GC=F": "黃金",
    "BTC-USD": "Bitcoin",
    "^RUT": "Russell 2000 小型股",
    "TWD=X": "美元/台幣",
}

SECTOR_ETFS = {
    "XLK": "科技",
    "XLC": "通訊服務",
    "XLY": "非必需消費",
    "XLP": "必需消費",
    "XLF": "金融",
    "XLV": "醫療保健",
    "XLI": "工業",
    "XLE": "能源",
    "XLB": "原物料",
    "XLRE": "房地產",
    "XLU": "公用事業",
}


def _pct(hist, days):
    if len(hist) <= days:
        return None
    last = float(hist["Close"].iloc[-1])
    previous = float(hist["Close"].iloc[-1 - days])
    return round((last / previous - 1) * 100, 2) if previous else None


def _fetch(symbols):
    results = []
    for symbol, name in symbols.items():
        try:
            hist = yf.Ticker(symbol).history(period="3mo")
            if len(hist) < 2:
                continue
            results.append({
                "symbol": symbol,
                "name": name,
                "close": round(float(hist["Close"].iloc[-1]), 3),
                "pct_1d": _pct(hist, 1),
                "pct_5d": _pct(hist, 5),
                "pct_20d": _pct(hist, 20),
                "as_of": hist.index[-1].strftime("%Y-%m-%d"),
            })
        except Exception as exc:
            print(f"[warn] {name} ({symbol}) 抓取失敗: {exc}")
    return results


def fetch_cross_assets():
    return _fetch(CROSS_ASSETS)


def fetch_sectors():
    return _fetch(SECTOR_ETFS)


def fmt_rows(rows):
    if not rows:
        return "(無資料)"

    def signed(value):
        if value is None:
            return "無資料"
        return f"{'+' if value >= 0 else ''}{value}%"

    return "\n".join(
        f"- {row['name']} ({row['symbol']}): {row['close']}；"
        f"1日 {signed(row['pct_1d'])}；5日 {signed(row['pct_5d'])}；"
        f"20日 {signed(row['pct_20d'])}；資料日 {row['as_of']}"
        for row in rows
    )


def fmt_breadth(sectors, watchlist):
    sector_valid = [x for x in sectors if x.get("pct_1d") is not None]
    stock_valid = [x for x in watchlist if x.get("pct") is not None]
    sector_up = sum(x["pct_1d"] > 0 for x in sector_valid)
    stock_up = sum(x["pct"] > 0 for x in stock_valid)

    if not sector_valid and not stock_valid:
        return "(無資料)"
    return (
        f"- 11 大類股 ETF：{sector_up}/{len(sector_valid)} 上漲\n"
        f"- 重點追蹤股：{stock_up}/{len(stock_valid)} 上漲\n"
        "- 注意：這是代理廣度，不等同完整 NYSE/Nasdaq 漲跌家數。"
    )
