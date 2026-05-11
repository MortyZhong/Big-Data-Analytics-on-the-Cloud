# backend/harvesters/bluesky_harvester.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import redis
from atproto import Client


def read_secret(name):
    secret_path = f"/secrets/default/harvester-secrets/{name}"
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get(name, "")


BLUESKY_HANDLE = "kuiyuanshu.bsky.social"
BLUESKY_PASSWORD = read_secret("BLUESKY_PASSWORD")
REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""

PLATFORM = "bluesky"
QUEUE_KEY = "social_posts:queue"
DEDUP_KEY = f"social_posts:{PLATFORM}:seen_uris"
CURSOR_KEY = f"social_posts:{PLATFORM}:cursor"  # Redis hash: keyword -> cursor

DEFAULT_KEYWORDS = ["Australia war", "Australia Iran", "tariff Australia", "oil Australia", "AusPol"]
DEFAULT_PAGES_PER_RUN = 1
PAGE_LIMIT = 100
MAX_AGE_DAYS = 90  # only fetch posts within the last N days


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
    """Read keywords / pages_per_run from query string or JSON body. Fall back to defaults."""
    keywords, pages_per_run, reset = None, None, False

    qs = parse_qs(environ.get("QUERY_STRING", "")) if environ else {}
    if "keywords" in qs:
        keywords = [k.strip() for k in qs["keywords"][0].split(",") if k.strip()]
    if "pages" in qs:
        try:
            pages_per_run = int(qs["pages"][0])
        except ValueError:
            pass
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
                if isinstance(payload.get("pages"), int):
                    pages_per_run = payload["pages"]
                if payload.get("reset"):
                    reset = True
        except Exception as e:
            print(f"[BlueSky] body parse error: {e}")

    return (
        keywords or DEFAULT_KEYWORDS,
        pages_per_run or DEFAULT_PAGES_PER_RUN,
        reset,
    )


def harvest(environ=None, start_response=None):
    keywords, pages_per_run, reset = parse_params(environ)

    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )
    if reset:
        r.delete(CURSOR_KEY)
        print("[BlueSky] cursor reset")

    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)

    since_iso = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    count = skipped = errors = 0

    for keyword in keywords:
        cursor = r.hget(CURSOR_KEY, keyword) or None
        finished = False

        for page in range(pages_per_run):
            print(f"[BlueSky] {keyword} page {page + 1} since={since_iso} (cursor={cursor})")
            try:
                params = {"q": keyword, "limit": PAGE_LIMIT, "since": since_iso}
                if cursor:
                    params["cursor"] = cursor
                result = client.app.bsky.feed.search_posts(params)

                if not result.posts:
                    finished = True
                    break

                for post in result.posts:
                    try:
                        text = post.record.text
                        if not text.strip():
                            continue
                        if r.sadd(DEDUP_KEY, post.uri) == 0:
                            skipped += 1
                            continue
                        doc = {
                            "id": post.uri,
                            "platform": PLATFORM,
                            "text": text,
                            "author": post.author.handle,
                            "created_at": post.indexed_at,
                            "topic": detect_topic(text),
                            "language": "en",
                            "tags": [],
                            "reblogs": getattr(post, "repost_count", 0),
                            "favourites": getattr(post, "like_count", 0),
                            "url": f"https://bsky.app/profile/{post.author.handle}",
                            "location": "Australia",
                        }
                        r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
                        count += 1
                    except Exception as e:
                        errors += 1
                        print(f"[BlueSky] post error: {e}")
                        continue

                next_cursor = getattr(result, "cursor", None)
                if not next_cursor:
                    finished = True
                    break
                cursor = next_cursor
                time.sleep(3)

            except Exception as e:
                errors += 1
                print(f"[BlueSky] page error: {e}")
                time.sleep(5)
                break

        if finished:
            r.hdel(CURSOR_KEY, keyword)
        elif cursor:
            r.hset(CURSOR_KEY, keyword, cursor)

    msg = f"bluesky done: pushed={count} skipped={skipped} errors={errors} keywords={len(keywords)} pages={pages_per_run}"
    print(f"[BlueSky] {msg}")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg
