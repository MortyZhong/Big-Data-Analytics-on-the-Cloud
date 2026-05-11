# backend/harvesters/mastodon_harvester.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import redis
from mastodon import Mastodon


def read_secret(name):
    secret_path = f"/secrets/default/harvester-secrets/{name}"
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get(name, "")


MASTODON_TOKEN = read_secret("MASTODON_TOKEN")
MASTODON_API_BASE = "https://mastodon.au"

REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""

PLATFORM = "mastodon"
QUEUE_KEY = "social_posts:queue"
DEDUP_KEY = f"social_posts:{PLATFORM}:seen_ids"
CURSOR_KEY = f"social_posts:{PLATFORM}:cursor"  # Redis hash: tag -> max_id

DEFAULT_TAGS = ["Australia", "AusPol", "war", "tariff", "oil", "Iran"]
DEFAULT_PAGES_PER_RUN = 1
PAGE_LIMIT = 40  # Mastodon hashtag timeline cap
MAX_AGE_DAYS = 90


def clean_html(text):
    return re.sub(r"<[^>]+>", "", text)


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
    tags, pages_per_run, reset = None, None, False

    qs = parse_qs(environ.get("QUERY_STRING", "")) if environ else {}
    if "tags" in qs:
        tags = [t.strip() for t in qs["tags"][0].split(",") if t.strip()]
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
                if isinstance(payload.get("tags"), list):
                    tags = [str(t).strip() for t in payload["tags"] if str(t).strip()]
                if isinstance(payload.get("pages"), int):
                    pages_per_run = payload["pages"]
                if payload.get("reset"):
                    reset = True
        except Exception as e:
            print(f"[Mastodon] body parse error: {e}")

    return (
        tags or DEFAULT_TAGS,
        pages_per_run or DEFAULT_PAGES_PER_RUN,
        reset,
    )


def harvest(environ=None, start_response=None):
    tags, pages_per_run, reset = parse_params(environ)

    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )
    if reset:
        r.delete(CURSOR_KEY)
        print("[Mastodon] cursor reset")

    mastodon = Mastodon(access_token=MASTODON_TOKEN, api_base_url=MASTODON_API_BASE)

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    pushed = skipped = errors = 0

    for tag in tags:
        max_id = r.hget(CURSOR_KEY, tag) or None
        finished = False
        tag_pushed = tag_skipped = 0

        for page in range(pages_per_run):
            print(f"[Mastodon] #{tag} page {page + 1} cutoff={cutoff.isoformat()} (max_id={max_id})")
            try:
                kwargs = {"limit": PAGE_LIMIT}
                if max_id:
                    kwargs["max_id"] = max_id
                statuses = mastodon.timeline_hashtag(tag, **kwargs)

                if not statuses:
                    finished = True
                    break

                hit_cutoff = False
                for s in statuses:
                    try:
                        created = s["created_at"]
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        if created < cutoff:
                            hit_cutoff = True
                            break

                        lang = s.get("language")
                        if lang and lang != "en":
                            continue
                        text = clean_html(s["content"])
                        if not text.strip():
                            continue

                        post_id = str(s["id"])
                        if r.sadd(DEDUP_KEY, post_id) == 0:
                            skipped += 1
                            tag_skipped += 1
                            continue

                        doc = {
                            "id": post_id,
                            "platform": PLATFORM,
                            "text": text,
                            "author": s["account"]["acct"],
                            "created_at": created.isoformat(),
                            "topic": detect_topic(text),
                            "language": lang or "und",
                            "tags": [t["name"] for t in s.get("tags", [])],
                            "reblogs": s.get("reblogs_count", 0),
                            "favourites": s.get("favourites_count", 0),
                            "url": s.get("url", ""),
                            "location": "Australia",
                        }
                        r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
                        pushed += 1
                        tag_pushed += 1
                    except Exception as e:
                        errors += 1
                        print(f"[Mastodon] post error: {e}")
                        continue

                max_id = str(statuses[-1]["id"])

                if hit_cutoff:
                    finished = True
                    break
                time.sleep(2)

            except Exception as e:
                errors += 1
                print(f"[Mastodon] #{tag} page error: {e}")
                time.sleep(5)
                break

        if finished:
            r.hdel(CURSOR_KEY, tag)
        elif max_id:
            r.hset(CURSOR_KEY, tag, max_id)

        print(f"[Mastodon] #{tag} -> pushed={tag_pushed} skipped={tag_skipped} finished={finished} next_max_id={max_id}")

    msg = f"mastodon done: pushed={pushed} skipped={skipped} errors={errors} tags={len(tags)} pages={pages_per_run}"
    print(f"[Mastodon] {msg}")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg
