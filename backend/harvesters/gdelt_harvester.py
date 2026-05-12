# backend/harvesters/gdelt_harvester.py
# Team: 68 | Name: Yutao Fan | Student ID: 1810828
import json
import time
import urllib3
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import redis
from gdeltdoc import GdeltDoc, Filters

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""

PLATFORM = "gdelt"
QUEUE_KEY = "social_posts:queue"
DEDUP_KEY = f"social_posts:{PLATFORM}:seen_urls"
CURSOR_KEY = f"social_posts:{PLATFORM}:cursor"

DEFAULT_KEYWORDS = ["Australia war", "Australia Iran", "tariff Australia", "oil Australia", "AusPol"]
MAX_AGE_DAYS = 90
RATE_LIMIT_SLEEP = 10
START_OFFSET_DAYS = 2   # GDELT 数据有延迟,从 2 天前开始回填


def detect_topic(text):
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military", "attack"]):
        return "war"
    if any(w in text for w in ["tariff", "trade", "sanction", "import", "export"]):
        return "tariff"
    if any(w in text for w in ["oil", "fuel", "petrol", "energy", "gas"]):
        return "oil"
    return "general"


def parse_params(environ):
    keywords, reset = None, False

    qs = parse_qs(environ.get("QUERY_STRING", "")) if environ else {}
    if "keywords" in qs:
        keywords = [k.strip() for k in qs["keywords"][0].split(",") if k.strip()]
    if qs.get("reset", ["0"])[0] in ("1", "true", "yes"):
        reset = True

    if environ and environ.get("REQUEST_METHOD") == "POST":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > 0:
                body = environ["wsgi.input"].read(length)
                payload = json.loads(body)
                if isinstance(payload.get("keywords"), list):
                    keywords = [str(k).strip() for k in payload["keywords"] if str(k).strip()]
                if payload.get("reset"):
                    reset = True
        except Exception as e:
            print(f"[GDELT] body parse error: {e}")

    return keywords or DEFAULT_KEYWORDS, reset


def harvest(environ=None, start_response=None):
    keywords, reset = parse_params(environ)

    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )

    if reset:
        r.delete(CURSOR_KEY)
        print("[GDELT] cursor reset")

    today = datetime.now(timezone.utc).date()
    cutoff_date = today - timedelta(days=MAX_AGE_DAYS)
    start_date = (today - timedelta(days=START_OFFSET_DAYS)).strftime("%Y-%m-%d")

    for kw in keywords:
        if not r.hexists(CURSOR_KEY, kw):
            r.hset(CURSOR_KEY, kw, start_date)
            print(f"[GDELT] init backfill for '{kw}' from {start_date}")

    gd = GdeltDoc()
    pushed = skipped = errors = 0

    for kw in keywords:
        cursor_date = r.hget(CURSOR_KEY, kw)
        kw_pushed = kw_skipped = 0

        print(f"[GDELT] '{kw}' BACKFILL target={cursor_date} (sleep {RATE_LIMIT_SLEEP}s)")
        time.sleep(RATE_LIMIT_SLEEP)

        rate_limited = False
        try:
            f = Filters(keyword=kw, start_date=cursor_date, end_date=cursor_date)
            articles = gd.article_search(f)

            if articles is not None and not articles.empty:
                for _, row in articles.iterrows():
                    try:
                        url = str(row["url"])
                        if r.sadd(DEDUP_KEY, url) == 0:
                            skipped += 1
                            kw_skipped += 1
                            continue

                        title = str(row["title"])
                        doc = {
                            "id": url,
                            "platform": PLATFORM,
                            "text": title,
                            "author": str(row["domain"]),
                            "created_at": str(row["seendate"]),
                            "topic": detect_topic(title),
                            "language": "en",
                            "tags": [],
                            "reblogs": 0,
                            "favourites": 0,
                            "url": url,
                            "location": "Australia",
                        }
                        r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
                        pushed += 1
                        kw_pushed += 1
                    except Exception as e:
                        errors += 1
                        print(f"[GDELT] row error: {e}")
                        continue
            else:
                print(f"[GDELT] '{kw}' no data for {cursor_date}")

        except Exception as e:
            errors += 1
            err_str = str(e).lower()
            if "limit" in err_str or "rate" in err_str or "one every" in err_str:
                rate_limited = True
                print(f"[GDELT] '{kw}' RATE LIMITED, cursor not advanced")
                time.sleep(15)
            elif "invalid query end date" in err_str or "invalid query" in err_str:
                # 日期超出 GDELT 范围(太新或太旧)→ 强制推进 cursor,避免卡死
                print(f"[GDELT] '{kw}' INVALID DATE {cursor_date}, will advance cursor")
            else:
                print(f"[GDELT] '{kw}' ERROR {type(e).__name__}: {e}")
                time.sleep(5)

        if not rate_limited:
            next_date = datetime.strptime(cursor_date, "%Y-%m-%d").date() - timedelta(days=1)
            if next_date < cutoff_date:
                r.hdel(CURSOR_KEY, kw)
                print(f"[GDELT] '{kw}' reached cutoff {cutoff_date}, will restart next run")
            else:
                r.hset(CURSOR_KEY, kw, next_date.strftime("%Y-%m-%d"))

        print(f"[GDELT] '{kw}' -> pushed={kw_pushed} skipped={kw_skipped}")

    msg = f"gdelt done: pushed={pushed} skipped={skipped} errors={errors}"
    print(f"[GDELT] {msg}")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg