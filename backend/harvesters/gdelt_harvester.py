# backend/harvesters/gdelt_harvester.py
# Team: 68 | Name: all member
# 新方案：直接下载 GDELT 每15分钟更新的 CSV 文件，不走 API，完全无限流

import csv
import io
import json
import time
import zipfile
import urllib3
import urllib.request
from datetime import datetime, timedelta, timezone

import redis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Redis 配置 ────────────────────────────────────────────────
REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""

PLATFORM      = "gdelt"
QUEUE_KEY     = "social_posts:queue"
DEDUP_KEY     = f"social_posts:{PLATFORM}:seen_urls"
PROCESSED_KEY = f"social_posts:{PLATFORM}:processed_files"

# ── GDELT CSV 列索引（共61列，tab分隔，无表头）────────────────
COL_SQLDATE      = 1   # YYYYMMDD
COL_ACTOR1_CC    = 7   # Actor1 国家代码 (AUS = 澳大利亚)
COL_ACTOR2_CC    = 17  # Actor2 国家代码
COL_EVENTCODE    = 26  # CAMEO 事件代码
COL_AVGTONE      = 34  # 情感分数
COL_ACTIONGEO_CC = 53  # 事件发生地国家代码 (AS = 澳大利亚 FIPS)
COL_SOURCEURL    = 60  # 文章 URL


# ── 话题检测 ─────────────────────────────────────────────────
def detect_topic(url, event_code):
    """根据 URL 和 CAMEO 事件代码判断话题（War / Tariff / Oil）"""
    url_lower = url.lower()

    # War 关键词
    if any(w in url_lower for w in [
        "war", "iran", "conflict", "military", "attack", "bomb",
        "missile", "troops", "weapon", "combat", "invasion",
        "russia", "nato", "ceasefire", "strike"
    ]):
        return "war"

    # Tariff 关键词
    if any(w in url_lower for w in [
        "tariff", "trade", "sanction", "import", "export",
        "duty", "quota", "wto", "customs", "levy", "protectionism"
    ]):
        return "tariff"

    # Oil 关键词
    if any(w in url_lower for w in [
        "oil", "fuel", "petrol", "energy", "gas", "opec",
        "crude", "petroleum", "lng", "pipeline", "barrel",
        "diesel", "refinery", "fossil"
    ]):
        return "oil"

    # CAMEO 事件代码兜底
    try:
        code = int(str(event_code)[:2])
        if code in [18, 19, 20]:   # Assault / Fight / Mass violence → war
            return "war"
        if code in [16, 17]:       # Reduce relations / Coerce → tariff
            return "tariff"
    except Exception:
        pass

    return "general"


# ── 澳大利亚过滤 ──────────────────────────────────────────────
def is_australia_related(row):
    """判断这条新闻是否跟澳大利亚有关"""
    try:
        if "AUS" in (row[COL_ACTOR1_CC], row[COL_ACTOR2_CC]):
            return True
        if row[COL_ACTIONGEO_CC] == "AS":    # AS = 澳大利亚 FIPS 代码
            return True
        url = row[COL_SOURCEURL].lower()
        if ".com.au" in url or ".gov.au" in url or ".edu.au" in url:
            return True
    except IndexError:
        pass
    return False


# ── 下载 & 解析 CSV ───────────────────────────────────────────
def get_latest_csv_url():
    """从 GDELT lastupdate.txt 获取最新的 export CSV 下载链接"""
    with urllib.request.urlopen(
        "http://data.gdeltproject.org/gdeltv2/lastupdate.txt", timeout=30
    ) as resp:
        content = resp.read().decode("utf-8")
    for line in content.strip().splitlines():
        parts = line.strip().split(" ")
        if len(parts) == 3 and "export.CSV.zip" in parts[2]:
            return parts[2]
    raise ValueError("找不到 export CSV URL")


def download_and_parse(csv_url):
    """下载 zip，解压，解析 CSV，返回所有行"""
    print(f"[GDELT] 下载 {csv_url}")
    with urllib.request.urlopen(csv_url, timeout=60) as resp:
        zip_data = resp.read()
    rows = []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            reader = csv.reader(
                io.TextIOWrapper(f, encoding="utf-8", errors="ignore"),
                delimiter="\t"
            )
            for row in reader:
                if len(row) > COL_SOURCEURL:
                    rows.append(row)
    print(f"[GDELT] 解析完成，共 {len(rows)} 条记录")
    return rows


# ── 推入 Redis 公共函数 ───────────────────────────────────────
def push_rows(r, rows):
    """过滤行并推入 Redis，返回 (pushed, skipped, errors)"""
    pushed = skipped = errors = 0
    for row in rows:
        try:
            if not is_australia_related(row):
                continue
            url = row[COL_SOURCEURL].strip()
            if not url.startswith("http"):
                continue
            topic = detect_topic(url, row[COL_EVENTCODE])
            if topic == "general":          # ✅ 只要 war / tariff / oil
                continue
            if r.sadd(DEDUP_KEY, url) == 0:
                skipped += 1
                continue
            try:
                created_at = datetime.strptime(
                    row[COL_SQLDATE], "%Y%m%d"
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            doc = {
                "id":              url,
                "platform":        PLATFORM,
                "text":            url,
                "author":          url.split("/")[2] if "/" in url else "unknown",
                "created_at":      created_at,
                "topic":           topic,
                "language":        "en",
                "tags":            [],
                "reblogs":         0,
                "favourites":      0,
                "url":             url,
                "location":        "Australia",
                "sentiment_score": float(row[COL_AVGTONE]) if row[COL_AVGTONE] else 0.0,
            }
            r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
            pushed += 1
        except Exception as e:
            errors += 1
            print(f"[GDELT] row error: {e}")
    return pushed, skipped, errors


# ── 实时 harvest（每15分钟跑一次）────────────────────────────
def harvest(environ=None, start_response=None):
    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )
    pushed = skipped = errors = 0

    try:
        csv_url   = get_latest_csv_url()
        file_name = csv_url.split("/")[-1]

        # 已处理过就跳过
        if r.sismember(PROCESSED_KEY, file_name):
            msg = f"gdelt: {file_name} 已处理过，跳过"
            print(f"[GDELT] {msg}")
            if start_response:
                start_response("200 OK", [("Content-Type", "text/plain")])
            return msg

        rows = download_and_parse(csv_url)
        pushed, skipped, errors = push_rows(r, rows)

        # 标记已处理（保留最近200个）
        r.sadd(PROCESSED_KEY, file_name)
        if r.scard(PROCESSED_KEY) > 200:
            r.srem(PROCESSED_KEY, list(r.smembers(PROCESSED_KEY))[0])

        print(f"[GDELT] {file_name} -> pushed={pushed} skipped={skipped}")

    except Exception as e:
        errors += 1
        print(f"[GDELT] harvest 错误: {type(e).__name__}: {e}")

    msg = f"gdelt done: pushed={pushed} skipped={skipped} errors={errors}"
    print(f"[GDELT] {msg}")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg


# ── 历史回填（单独手动触发一次）─────────────────────────────
def backfill(environ=None, start_response=None):
    """
    回填历史90天数据：每天只取中午12点那个文件
    90天 = 90个文件，每个文件间隔2秒，总计约3-5分钟
    """
    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )
    today          = datetime.now(timezone.utc).date()
    total_pushed   = total_skipped = total_errors = 0

    print(f"[GDELT] 开始 backfill 最近90天")

    for i in range(2, 92):           # 从2天前到91天前（GDELT有2天延迟）
        target_date = today - timedelta(days=i)
        file_name   = target_date.strftime("%Y%m%d") + "120000.export.CSV.zip"
        csv_url     = f"http://data.gdeltproject.org/gdeltv2/{file_name}"

        if r.sismember(PROCESSED_KEY, file_name):
            print(f"[GDELT] backfill skip {file_name}")
            continue

        try:
            rows = download_and_parse(csv_url)
            pushed, skipped, errors = push_rows(r, rows)
            total_pushed  += pushed
            total_skipped += skipped
            total_errors  += errors

            r.sadd(PROCESSED_KEY, file_name)
            print(f"[GDELT] backfill {file_name} -> pushed={pushed}")

        except Exception as e:
            print(f"[GDELT] backfill {file_name} 失败: {e}")

        time.sleep(2)    # 每个文件间隔2秒

    msg = f"gdelt backfill done: pushed={total_pushed} skipped={total_skipped} errors={total_errors}"
    print(f"[GDELT] {msg}")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg
