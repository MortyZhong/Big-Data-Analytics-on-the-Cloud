# backend/harvesters/fuel_harvester.py
# Team: 68 | Name: 舒奎元 | Student ID: 1345012
# 官方油价数据采集：FuelWatch WA + NSW FuelCheck → Redis → official_data (ES)

import json
import os
import time
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import urllib3
from datetime import datetime, timezone
from base64 import b64encode

import redis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Redis 配置 ────────────────────────────────────────────────
REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""

QUEUE_KEY = "official_data:queue"           # 存进 official_data 的队列
DEDUP_KEY = "official_data:fuel:seen"       # 去重

# ── NSW API 配置（Fission 把 secret 挂成 /secrets/<ns>/<name>/<key> 文件）──
def read_secret(name):
    secret_path = f"/secrets/default/fuel-secrets/{name}"
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get(name, "")

NSW_API_KEY    = read_secret("NSW_API_KEY")
NSW_API_SECRET = read_secret("NSW_API_SECRET")

# ── FuelWatch WA 配置 ─────────────────────────────────────────
# Product codes: 1=ULP91, 2=PULP95, 4=Diesel, 6=98RON
# Region codes: 25=Metro North, 26=Metro South, 27=Metro East
FUELWATCH_REGIONS = [25, 26, 27]   # 珀斯大都会区
FUELWATCH_PRODUCTS = [1, 2, 4, 6]  # 91 + 95 + 柴油 + 98

# 统一油种命名（与 ES mapping 的 type keyword 对齐）
ALLOWED_TYPES = {"u91", "u95", "u98", "diesel"}


# ══════════════════════════════════════════════════════════════
# FuelWatch WA
# ══════════════════════════════════════════════════════════════

def fetch_fuelwatch(product=1, region=25):
    """从 FuelWatch WA 获取油价数据"""
    url = f"https://www.fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS?Product={product}&Region={region}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"[FUEL] FuelWatch 请求失败 product={product} region={region}: {e}")
        return None


def parse_fuelwatch(xml_data, product_code):
    """解析 FuelWatch XML，返回油价列表"""
    product_map = {1: "u91", 2: "u95", 4: "diesel", 6: "u98"}
    fuel_type = product_map.get(product_code)
    if fuel_type not in ALLOWED_TYPES:
        return []

    items = []
    try:
        root = ET.fromstring(xml_data)
        channel = root.find("channel")
        if channel is None:
            return items

        for item in channel.findall("item"):
            try:
                price    = item.findtext("price")
                date_str = item.findtext("date")

                if not price or not date_str:
                    continue

                try:
                    date_obj   = datetime.strptime(date_str, "%Y-%m-%d")
                    created_at = date_obj.strftime("%Y-%m-%dT00:00:00Z")
                except Exception:
                    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                items.append({
                    "date":  created_at,
                    "price": float(price) / 100,   # 分/升 → 澳元/升
                    "type":  fuel_type,
                })
            except Exception as e:
                print(f"[FUEL] FuelWatch item 解析错误: {e}")
                continue

    except ET.ParseError as e:
        print(f"[FUEL] FuelWatch XML 解析失败: {e}")

    return items


# ══════════════════════════════════════════════════════════════
# NSW FuelCheck
# ══════════════════════════════════════════════════════════════

def get_nsw_token():
    """获取 NSW API OAuth token"""
    if not NSW_API_KEY or not NSW_API_SECRET:
        print("[FUEL] NSW API key/secret 未设置")
        return None

    try:
        credentials = b64encode(f"{NSW_API_KEY}:{NSW_API_SECRET}".encode()).decode()
        req = urllib.request.Request(
            "https://api.onegov.nsw.gov.au/oauth/client_credential/accesstoken?grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("access_token")
    except Exception as e:
        print(f"[FUEL] NSW token 获取失败: {e}")
        return None


def fetch_nsw_prices(token):
    """从 NSW FuelCheck 获取所有油价"""
    try:
        req = urllib.request.Request(
            "https://api.onegov.nsw.gov.au/FuelPriceCheck/v2/fuel/prices",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
                "apikey":        NSW_API_KEY,
                "User-Agent":    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                 "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[FUEL] NSW prices 获取失败: {e}")
        return None


def parse_nsw_prices(data):
    """解析 NSW FuelCheck 数据，返回 [{date, price, type}, ...]"""
    items = []
    if not data or "prices" not in data:
        return items

    fuel_map = {"U91": "u91", "P95": "u95", "P98": "u98", "DL": "diesel"}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    for p in data["prices"]:
        try:
            price = p.get("price")
            if not price:
                continue
            fuel_type = fuel_map.get(p.get("fueltype", ""))
            if fuel_type not in ALLOWED_TYPES:
                continue
            items.append({
                "date":  today,
                "price": float(price) / 100,
                "type":  fuel_type,
            })
        except Exception as e:
            print(f"[FUEL] NSW item 解析错误: {e}")
            continue

    return items


# ══════════════════════════════════════════════════════════════
# 聚合：按 (date, type) 求州内平均价 → 每州每油种 1 条
# ══════════════════════════════════════════════════════════════

def aggregate_by_state(items, location, source):
    """把单州内的 [{date,price,type}, ...] 聚合成每 type 一条 5 字段 doc"""
    buckets = {}   # (date, type) -> [prices]
    for it in items:
        buckets.setdefault((it["date"], it["type"]), []).append(it["price"])

    docs = []
    for (date, fuel_type), prices in buckets.items():
        docs.append({
            "date":     date,
            "price":    round(sum(prices) / len(prices), 4),
            "type":     fuel_type,
            "location": location,
            "source":   source,
        })
    return docs


# ══════════════════════════════════════════════════════════════
# 推入 Redis
# ══════════════════════════════════════════════════════════════

def push_to_redis(r, items, source):
    """推入 Redis 队列，去重"""
    pushed = skipped = 0
    for doc in items:
        try:
            # 去重 key：来源 + 地点 + 日期 + 类型
            dedup_id = f"{source}:{doc['location']}:{doc['date'][:10]}:{doc['type']}"
            if r.sadd(DEDUP_KEY, dedup_id) == 0:
                skipped += 1
                continue
            r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
            pushed += 1
        except Exception as e:
            print(f"[FUEL] Redis push 错误: {e}")
    return pushed, skipped


# ══════════════════════════════════════════════════════════════
# 主函数（Fission 入口）
# ══════════════════════════════════════════════════════════════

def harvest(environ=None, start_response=None):
    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )

    total_pushed = total_skipped = 0

    # ── 1. FuelWatch WA：收齐所有 region/product → 聚合成 4 条 ──
    print("[FUEL] 开始抓取 FuelWatch WA")
    wa_items = []
    for product in FUELWATCH_PRODUCTS:
        for region in FUELWATCH_REGIONS:
            xml_data = fetch_fuelwatch(product=product, region=region)
            if xml_data:
                wa_items.extend(parse_fuelwatch(xml_data, product))
            time.sleep(1)   # 友好访问
    wa_docs = aggregate_by_state(wa_items, location="WA", source="FuelWatch WA")
    pushed, skipped = push_to_redis(r, wa_docs, "fuelwatch")
    total_pushed  += pushed
    total_skipped += skipped
    print(f"[FUEL] FuelWatch WA -> raw={len(wa_items)} docs={len(wa_docs)} pushed={pushed} skipped={skipped}")

    # ── 2. NSW FuelCheck：聚合成 4 条 ──
    print("[FUEL] 开始抓取 NSW FuelCheck")
    token = get_nsw_token()
    if token:
        data = fetch_nsw_prices(token)
        if data:
            nsw_items = parse_nsw_prices(data)
            nsw_docs  = aggregate_by_state(nsw_items, location="NSW", source="NSW FuelCheck")
            pushed, skipped = push_to_redis(r, nsw_docs, "nsw")
            total_pushed  += pushed
            total_skipped += skipped
            print(f"[FUEL] NSW FuelCheck -> raw={len(nsw_items)} docs={len(nsw_docs)} pushed={pushed} skipped={skipped}")
    else:
        print("[FUEL] NSW token 获取失败，跳过")

    msg = f"fuel done: pushed={total_pushed} skipped={total_skipped}"
    print(f"[FUEL] {msg}")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg
