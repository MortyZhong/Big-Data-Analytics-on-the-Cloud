# backend/harvesters/fuel_backfill_wa.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012
# WA 油价历史回填：FuelWatch 月度 CSV → Redis → official_data (ES)
# 一次性脚本，回填 2026-02 ~ 2026-05；重复运行安全（Redis SET + ES doc_id 双重去重）。
# 用法： python fuel_backfill_wa.py

import csv
import io
import json
import urllib.request
from collections import defaultdict
from datetime import datetime

import redis

# ── Redis 配置（与 fuel_harvester.py 保持一致）────────────────
REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""
QUEUE_KEY  = "official_data:queue"
DEDUP_KEY  = "official_data:fuel:seen"

# ── CSV URL 模板 ─────────────────────────────────────────────
CSV_URL = ("https://warsydprdstafuelwatch.blob.core.windows.net"
           "/historical-reports/FuelWatchRetail-{month:02d}-{year}.csv")

# ── 油种映射（与 fuel_harvester 的 ALLOWED_TYPES 对齐）───────
PRODUCT_MAP = {
    "ULP":    "u91",
    "PULP":   "u95",
    "98 RON": "u98",
    "Diesel": "diesel",
}
ALLOWED_TYPES = set(PRODUCT_MAP.values())


def fetch_csv(year, month):
    """下载某月的 CSV，返回文本"""
    url = CSV_URL.format(year=year, month=month)
    print(f"[BACKFILL] 下载 {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[BACKFILL] 下载失败 {year}-{month:02d}: {e}")
        return None


def parse_and_aggregate(csv_text):
    """解析 CSV，按 (date, type) 求州内均价。返回 [{date, price, type, location, source}, ...]"""
    buckets = defaultdict(list)   # (iso_date, type) -> [prices]

    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        try:
            product = (row.get("PRODUCT_DESCRIPTION") or "").strip()
            fuel_type = PRODUCT_MAP.get(product)
            if fuel_type not in ALLOWED_TYPES:
                continue

            price_raw = row.get("PRODUCT_PRICE")
            if not price_raw:
                continue
            price = float(price_raw) / 100   # 分/升 → 澳元/升

            date_raw = (row.get("PUBLISH_DATE") or "").strip()
            date_obj = datetime.strptime(date_raw, "%d/%m/%Y")
            iso_date = date_obj.strftime("%Y-%m-%dT00:00:00Z")

            buckets[(iso_date, fuel_type)].append(price)
        except Exception as e:
            print(f"[BACKFILL] 行解析错误: {e}")
            continue

    docs = []
    for (date, fuel_type), prices in buckets.items():
        docs.append({
            "date":     date,
            "price":    round(sum(prices) / len(prices), 4),
            "type":     fuel_type,
            "location": "WA",
            "source":   "FuelWatch WA",
        })
    return docs


def push_to_redis(r, docs):
    """与 fuel_harvester.push_to_redis 同样的去重逻辑"""
    pushed = skipped = 0
    for doc in docs:
        try:
            dedup_id = f"fuelwatch:{doc['location']}:{doc['date'][:10]}:{doc['type']}"
            if r.sadd(DEDUP_KEY, dedup_id) == 0:
                skipped += 1
                continue
            r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
            pushed += 1
        except Exception as e:
            print(f"[BACKFILL] Redis push 错误: {e}")
    return pushed, skipped


# 回填范围：2026-02 ~ 2026-05（5 月文件含月初到当前已发布的部分）
MONTHS = [(2026, 2), (2026, 3), (2026, 4), (2026, 5)]


def main():
    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )

    total_pushed = total_skipped = total_docs = 0
    for year, month in MONTHS:
        csv_text = fetch_csv(year, month)
        if not csv_text:
            continue
        docs = parse_and_aggregate(csv_text)
        pushed, skipped = push_to_redis(r, docs)
        total_docs    += len(docs)
        total_pushed  += pushed
        total_skipped += skipped
        print(f"[BACKFILL] {year}-{month:02d} -> docs={len(docs)} pushed={pushed} skipped={skipped}")

    print(f"[BACKFILL] 完成 docs={total_docs} pushed={total_pushed} skipped={total_skipped}")


if __name__ == "__main__":
    main()
