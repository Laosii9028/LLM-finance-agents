# -*- coding: utf-8 -*-
"""專業版每日美股／台股分析；星期一自動切換成本週展望。"""

import os
from datetime import datetime, timedelta, timezone

import analyze
import briefs
import discord_notify
import learned
import market
import market_context
import news
import professional_analysis
from taiwan_map import as_prompt_text as verified_map_text


DEFAULT_DASHBOARD_URL = (
    "https://laosii9028.github.io/LLM-finance-agents/dashboard.html"
    "#repo=Laosii9028%2FLLM-finance-agents"
)


def get_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"缺少環境變數: {name}(請參考 .env.example 設定)")
    return value


def dashboard_url(now):
    url = os.environ.get("DASHBOARD_URL", DEFAULT_DASHBOARD_URL).strip()
    if not url:
        return ""
    cache_buster = f"v={now.strftime('%Y%m%d%H%M')}"
    if "#" in url:
        before_hash, hash_part = url.split("#", 1)
        separator = "&" if "?" in before_hash else "?"
        return f"{before_hash}{separator}{cache_buster}#{hash_part}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{cache_buster}"


def main():
    av_key = get_env("ALPHA_VANTAGE_API_KEY")
    gemini_key = get_env("GEMINI_API_KEY")
    webhook = get_env("DISCORD_WEBHOOK_URL")
    tw_now = datetime.now(timezone.utc) + timedelta(hours=8)
    monday = tw_now.weekday() == 0

    print("抓取指數、重點股、漲跌榜...")
    indices = market.fetch_indices()
    watchlist = market.fetch_watchlist()
    movers = market.fetch_gainers_losers(av_key)

    print("抓取跨資產與 11 大類股輪動...")
    cross_assets = market_context.fetch_cross_assets()
    sectors = market_context.fetch_sectors()

    print("抓取新聞與近期財報...")
    articles = news.fetch_news(
        av_key, limit=20, weekend_mode=monday
    )
    earnings = news.fetch_upcoming_earnings(
        av_key, market.WATCHLIST.keys(), days=7 if monday else 3
    )

    indices_text = analyze.fmt_indices(indices)
    watchlist_text = analyze.fmt_watchlist(watchlist)
    gainers_text = analyze.fmt_movers(movers["gainers"])
    losers_text = analyze.fmt_movers(movers["losers"])
    news_text = analyze.fmt_news(articles)
    earnings_text = news.fmt_earnings(earnings)
    cross_assets_text = market_context.fmt_rows(cross_assets)
    sectors_text = market_context.fmt_rows(sectors)
    breadth_text = market_context.fmt_breadth(sectors, watchlist)

    print("更新候選台股連動關係...")
    movers_text = (
        f"重點追蹤美股:\n{watchlist_text}\n\n"
        f"漲幅榜:\n{gainers_text}\n\n跌幅榜:\n{losers_text}"
    )
    learned_map = learned.propose_and_merge(gemini_key, news_text, movers_text)
    verified_text = verified_map_text()
    learned_text = learned.as_prompt_text(learned_map)

    data_values = {
        "indices": indices_text,
        "cross_assets": cross_assets_text,
        "sectors": sectors_text,
        "breadth": breadth_text,
        "watchlist": watchlist_text,
        "gainers": gainers_text,
        "losers": losers_text,
        "news": news_text,
        "earnings": earnings_text,
    }

    print("產生專業綜合、美股與台股分析...")
    body, us_body, tw_body = professional_analysis.build_all(
        gemini_key, monday, data_values, verified_text, learned_text
    )

    date_label = tw_now.strftime("%Y/%m/%d")
    if monday:
        title = f"🗓️ 星期一市場週展望 {date_label}"
        us_title = f"🔭 美股本週展望 {date_label}"
        tw_title = f"🇹🇼 台股本週展望 {date_label}"
    else:
        title = f"📈 專業美股早報 {date_label}"
        us_title = f"🔎 美股專業分析 {date_label}"
        tw_title = f"🇹🇼 台股專業盤前 {date_label}"

    disclaimer = "\n\n_自動彙整，資料可能延遲；僅供研究參考，非投資建議。_"
    body += disclaimer
    us_body += disclaimer
    tw_body += disclaimer

    print("儲存分析紀錄...")
    date_key = tw_now.strftime("%Y-%m-%d")
    briefs.save_brief(date_key, title, body)
    briefs.save_market_analysis(date_key, us_title, us_body)
    briefs.save_taiwan_analysis(date_key, tw_title, tw_body)

    print("推送到 Discord...")
    discord_notify.push(
        webhook, title, body, dashboard_url=dashboard_url(tw_now)
    )
    print("完成 ✅")


if __name__ == "__main__":
    main()
