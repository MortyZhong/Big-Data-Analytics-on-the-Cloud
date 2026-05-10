# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

from atproto import Client
import redis
import json
import time
import os

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
DEDUP_KEY = "social_posts:" + PLATFORM + ":seen_uris"

KEYWORDS = ["Australia war", "Australia Iran", "tariff Australia", "oil Australia", "AusPol"]

def detect_topic(text):
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military", "attack"]):
        return "war"
    elif any(w in text for w in ["tariff", "trade", "sanction", "import", "export"]):
        return "tariff"
    elif any(w in text for w in ["oil", "fuel", "petrol", "energy", "gas"]):
        return "oil"
    return "general"

def harvest(environ=None, start_response=None):
    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS or None, decode_responses=True)
    count = 0
    skipped = 0
    errors = 0
    for kw in KEYWORDS:
        try:
            print("[BlueSky] 搜索: " + kw)
            time.sleep(3)
            result = client.app.bsky.feed.search_posts({"q": kw, "limit": 50})
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
                        "url": "https://bsky.app/profile/" + post.author.handle,
                        "location": "Australia"
                    }
                    r.lpush(QUEUE_KEY, json.dumps(doc, ensure_ascii=False))
                    count += 1
                except Exception as e:
                    errors += 1
                    print("[BlueSky] 单条错误: " + str(e))
                    continue
        except Exception as e:
            errors += 1
            print("[BlueSky] 错误: " + str(e))
            time.sleep(15)
            continue
    print("[BlueSky] 完成！入队: " + str(count) + " 条，去重跳过: " + str(skipped) + " 条，错误: " + str(errors) + " 次")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        
    return "bluesky done: pushed=" + str(count) + " skipped=" + str(skipped) + " errors=" + str(errors)

