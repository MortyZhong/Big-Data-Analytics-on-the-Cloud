# backend/harvesters/reddit_harvester.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

import json
import os
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import redis
import requests


def read_secret(name):
    secret_path = f"/secrets/default/harvester-secrets/{name}"
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get(name, "")


REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""

PLATFORM = "reddit"
QUEUE_KEY = "social_posts:queue"
DEDUP_KEY = f"social_posts:{PLATFORM}:seen_ids"
CURSOR_KEY = f"social_posts:{PLATFORM}:cursor"

DEFAULT_SUBREDDITS = ["australia", "AusPolitics", "AusFinance", "melbourne"]
DEFAULT_SEARCH_TERMS = {
    "war": ["war", "iran", "ukraine", "military"],
    "tariff": ["tariff", "trade war", "sanction"],
    "oil": ["oil", "fuel", "petrol", "energy crisis"]
}
DEFAULT_PAGES_PER_RUN = 1
PAGE_LIMIT = 100
MAX_AGE_DAYS = 90

BROWSER_HEADERS = ["Mozilla/5.0", "Chrome/124.0", "Safari/537.36"]


def detect_topic(content):
    lowered = content.lower()
    topic_map = {
        "war": ["war", "iran", "ukraine", "military"],
        "tariff": ["tariff", "trade", "sanction"],
        "oil": ["oil", "fuel", "petrol", "energy"]
    }
    for topic_name, words in topic_map.items():
        if any(word in lowered for word in words):
            return topic_name
    return "general"


def parse_params(environ):
    subreddits, pages_per_run, reset = None, None, False

    qs = parse_qs(environ.get("QUERY_STRING", "")) if environ else {}
    if "subreddits" in qs:
        subreddits = [s.strip() for s in qs["subreddits"][0].split(",") if s.strip()]
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
                if isinstance(payload.get("subreddits"), list):
                    subreddits = [str(s).strip() for s in payload["subreddits"] if str(s).strip()]
                if isinstance(payload.get("pages"), int):
                    pages_per_run = payload["pages"]
                if payload.get("reset"):
                    reset = True
        except Exception as e:
            print(f"[Reddit] body parse error: {e}")

    return (
        subreddits or DEFAULT_SUBREDDITS,
        pages_per_run or DEFAULT_PAGES_PER_RUN,
        reset,
    )


def fetch_page(subreddit, search_term, after=None):
    api_url = f"https://old.reddit.com/r/{subreddit}/search.json"
    since = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).timestamp()
    query_params = {
        "q": search_term,
        "restrict_sr": 1,
        "sort": "new",
        "limit": PAGE_LIMIT,
        "t": "year"
    }
    if after:
        query_params["after"] = after

    request_headers = {"User-Agent": random.choice(BROWSER_HEADERS)}
    attempts = 3

    while attempts > 0:
        try:
            response = requests.get(
                api_url, params=query_params,
                headers=request_headers, timeout=15
            )
            if response.status_code == 429:
                wait = random.uniform(60, 120)
                print(f"[Reddit] rate limited, sleeping {wait:.1f}s")
                time.sleep(wait)
                attempts -= 1
                continue
            if response.status_code != 200:
                print(f"[Reddit] failed: {response.status_code}")
                return None, None, since
            payload = response.json()
            data = payload.get("data", {})
            return data.get("children", []), data.get("after", None), since
        except Exception as e:
            print(f"[Reddit] error: {e}")
            attempts -= 1
            time.sleep(random.uniform(5, 15))
    return None, None, since


def harvest(environ=None, start_response=None):
    subreddits, pages_per_run, reset = parse_params(environ)

    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )

    if reset:
        r.delete(CURSOR_KEY)
        print("[Reddit] cursor reset")

    count = skipped = errors = 0

    for subreddit in subreddits:
        for topic_name, term_list in DEFAULT_SEARCH_TERMS.items():
            for search_term in term_list:
                cursor_key = f"{subreddit}:{search_term}"
                after = r.hget(CURSOR_KEY, cursor_key) or None
                finished = False

                for page in range(pages_per_run):
                    print(f"[Reddit] r/{subreddit} {search_term} page {page+1} (after={after})")
                    posts, after, since = fetch_page(subreddit, search_term, after)

                    if not posts:
                        finished = True
                        break

                    for item in posts:
                        try:
                            post = item.get("data", {})
                            title = post.get("title") or ""
                            body = post.get("selftext") or ""
                            combined_text = (title + " " + body).strip()

                            if not combined_text:
                                continue

                            # 只要90天内的帖子
                            created_utc = post.get("created_utc", 0)
                            if created_utc < since:
                                finished = True
                                break

                            post_id = post.get("id")
                            if r.sadd(DEDUP_KEY, post_id) == 0:
                                skipped += 1
                                continue

                            doc = {
                                "id": post_id,
                                "platform": PLATFORM,
                                "text": combined_text,
                                "author": post.get("author"),
                                "created_at": datetime.fromtimestamp(
                                    created_utc, tz=timezone.utc
                                ).isoformat(),
                                "topic": detect_topic(combined_text),
                                "language": "en",
                                "location": "Australia",
                                "url": "https://reddit.com" + post.get("permalink", ""),
                                "subreddit": post.get("subreddit"),
                                "score": post.get("score", 0),
                                "favourites": post.get("score", 0),
                                "tags": [],
                                "reblogs": 0
                            }
                            r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
                            count += 1

                        except Exception as e:
                            errors += 1
                            print(f"[Reddit] post error: {e}")
                            continue

                    if finished:
                        break

                    delay = random.uniform(2, 6)
                    time.sleep(delay)

                    if not after:
                        finished = True
                        break

                if finished:
                    r.hdel(CURSOR_KEY, cursor_key)
                elif after:
                    r.hset(CURSOR_KEY, cursor_key, after)

    msg = f"reddit done: pushed={count} skipped={skipped} errors={errors}"
    print(f"[Reddit] {msg}")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg


if __name__ == "__main__":
    os.environ["ES_HOST"] = "https://localhost:9200"
    harvest()