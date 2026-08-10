# -*- coding: utf-8 -*-
"""依專業市場評論框架產生每日／週一版美股與台股分析。"""

from google import genai

import analyze


RULES = """
共同規則：
- 只可使用輸入資料，不得虛構即時價格、財報、經濟事件、公司消息或籌碼。
- 每個原因標示為「資料事實」、「新聞支持」、「新聞＋量價共振」或「量價／跨資產推論」。
- 相關不代表因果；若只能觀察到同向變化，必須使用「可能」「需確認」。
- 指出資料日期；不同市場資料日期不一致時不可直接當成同一時點。
- 財報日期未取得時寫資料不足，不得猜測。
- 不給買賣指令、目標價、勝率或保證式預測。
- 所有展望使用條件式情境，附確認訊號與失效條件。
"""


DAILY_CONTEXT = """今天是台灣時間星期二至星期六，主要股票資料應對應最近一次美股正常盤收盤。
請把報告寫成盤後解讀與台股盤前推演。"""

MONDAY_CONTEXT = """今天是台灣時間星期一，美股週日沒有正常盤收盤。
股票、指數和類股資料來自最近交易日（通常是上週五），不是星期一的新收盤。
週末新聞可能尚未反映於正常盤；必須區分「已反映」與「待星期一美股開盤確認」。
請把報告寫成上週收尾與本週展望。"""


DATA_BLOCK = """
# 指數
{indices}
# 跨資產（美元、油、黃金、Bitcoin、小型股、美元/台幣）
{cross_assets}
# 11 大美股類股 ETF
{sectors}
# 代理市場廣度
{breadth}
# 重點美股量價與相對強弱
{watchlist}
# 漲幅榜
{gainers}
# 跌幅榜
{losers}
# 最新新聞
{news}
# 未來財報
{earnings}
"""


BRIEF_TASK = """
你是跨市場策略分析師，請用繁體中文寫給一般投資者看的市場早報。
{mode}
{rules}
{data}
# 已驗證美股→台股對應表
{map_verified}
# 候選對應表（低信任）
{map_learned}

結構：
**一、執行摘要**：3-5 句，只寫最重要結論與信心水準。
**二、昨夜／上週市場因果鏈**：股票→殖利率/VIX→美元/油/黃金→風險偏好；不可硬湊因果。
**三、類股輪動與市場廣度**：領漲、落後、漲勢是否集中，區分 1 日與 5 日。
**四、重點美股證據表**：挑 5-8 檔，每檔列事實、可能原因、確認訊號、失效條件。
**五、事件與財報雷達**：已反映／正在反映／尚未反映；只列已提供事件。
**六、台股傳導路徑**：美股或跨資產→台股族群→已驗證個股；候選關係標低信心。
**七、三情境推演**：偏多／震盪／偏空，各列觸發條件，不指定必然方向。
**八、開盤前檢查清單**：3-6 個需要確認、但輸入未必含即時值的訊號。
**九、一句話總結**。
"""


US_TASK = """
你是美股市場策略分析師，請用繁體中文產生專業美股分析。
{mode}
{rules}
{data}

結構：
**一、市場狀態**：risk-on、risk-off 或分化，附資料證據與信心水準。
**二、驅動因素排序**：依證據強度列 3-5 項，不以新聞標題硬解釋價格。
**三、跨資產確認**：美元、原油、黃金、Bitcoin、小型股與殖利率/VIX 是否支持股票走勢。
**四、類股輪動與廣度**：領漲／落後、集中度、1 日與 5 日是否一致。
**五、重點股觀察矩陣**：5-8 檔，列催化因素、量價確認、失效條件、主要風險。
**六、財報與事件風險**：只用已提供資料，分已反映／尚未反映。
**七、未來 1-3 個交易日三情境**：偏多／震盪／偏空的條件與確認訊號。
**八、資料限制與一句話結論**。
"""


TAIWAN_TASK = """
你是台股盤前策略分析師，請用繁體中文產生台股盤前分析。
{mode}
{rules}
{data}
# 已驗證美股→台股對應表
{map_verified}
# 候選對應表（低信任）
{map_learned}

結構：
**一、台股盤前背景**：美股、SOX、TSM ADR、美元/台幣與風險偏好；未提供即時值就列待確認。
**二、傳導鏈**：美股/類股/商品→台股族群→個股，標示資料事實或推論。
**三、可能受惠族群**：每項列來源、確認訊號、失效條件。
**四、可能承壓族群**：每項列來源、確認訊號、失效條件。
**五、台股觀察矩陣**：6-10 檔，優先已驗證表；候選標低信心，不給買賣建議。
**六、開盤三情境**：偏多／震盪／偏空，不預測唯一結果。
**七、開盤後 30 分鐘檢查清單**：量價、台指期、匯率與族群擴散等；未提供值只列待確認。
**八、資料限制與一句話結論**。
"""


def _generate(api_key, prompt, label):
    client = genai.Client(api_key=api_key)
    last_error = None
    for model in analyze._model_candidates():
        try:
            print(f"使用 Gemini {label}模型: {model}")
            return client.models.generate_content(model=model, contents=prompt).text
        except Exception as exc:
            last_error = exc
            print(f"[warn] {label}模型 {model} 失敗，嘗試下一個: {exc}")
    raise last_error


def _data(**values):
    return DATA_BLOCK.format(**values)


def build_all(api_key, monday, data_values, map_verified, map_learned):
    mode = MONDAY_CONTEXT if monday else DAILY_CONTEXT
    data = _data(**data_values)
    common = {"mode": mode, "rules": RULES, "data": data}
    brief = _generate(api_key, BRIEF_TASK.format(
        **common, map_verified=map_verified, map_learned=map_learned
    ), "綜合早報")
    us = _generate(api_key, US_TASK.format(**common), "美股分析")
    taiwan = _generate(api_key, TAIWAN_TASK.format(
        **common, map_verified=map_verified, map_learned=map_learned
    ), "台股分析")
    return brief, us, taiwan
