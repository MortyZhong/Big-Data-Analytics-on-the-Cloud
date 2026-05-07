# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

from atproto import Client
from elasticsearch import Elasticsearch
import time
import os

BLUESKY_HANDLE = os.environ.get("BLUESKY_HANDLE", "kuiyuanshu.bsky.social")
BLUESKY_PASSWORD = os.environ.get("BLUESKY_PASSWORD", "")
ES_HOST = os.environ.get("ES_HOST", "https://elasticsearch-es-http.elastic.svc.cluster.local:9200")
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")

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
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)
    count = 0
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
                    doc = {
                        "id": post.uri,
                        "platform": "bluesky",
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
                    es.index(index="social_posts", id="bluesky_" + post.uri.split("/")[-1], document=doc)
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
    print("[BlueSky] 完成！成功: " + str(count) + " 条，错误: " + str(errors) + " 次")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [("bluesky done: " + str(count)).encode()]

if __name__ == "__main__":
    os.environ["BLUESKY_PASSWORD"] = "SET_YOUR_PASSWORD_HERE"
    os.environ["ES_HOST"] = "https://localhost:9200"
    harvest()
