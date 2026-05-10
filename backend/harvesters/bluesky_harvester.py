# backend/harvesters/bluesky_harvester.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

from atproto import Client
from elasticsearch import Elasticsearch
import time, os

BLUESKY_HANDLE = os.environ.get("BLUESKY_HANDLE", "kuiyuanshu.bsky.social")
BLUESKY_PASSWORD = os.environ.get("BLUESKY_PASSWORD", "your_password_here")
ES_HOST = os.environ.get("ES_HOST", "https://elasticsearch-es-http.elastic.svc.cluster.local:9200")
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")

KEYWORDS = ["Australia war", "Australia Iran", "tariff Australia", "oil Australia", "AusPol"]
PAGES_PER_KEYWORD = 10

def detect_topic(text):
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military", "attack"]):
        return "war"
    elif any(w in text for w in ["tariff", "trade", "sanction", "import", "export"]):
        return "tariff"
    elif any(w in text for w in ["oil", "fuel", "petrol", "energy", "gas"]):
        return "oil"
    return "general"

def harvest_keyword(client, es, keyword):
    count = 0
    cursor = None
    for page in range(PAGES_PER_KEYWORD):
        try:
            print("[BlueSky] " + keyword + " 第" + str(page+1) + "页...")
            params = {"q": keyword, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = client.app.bsky.feed.search_posts(params)
            if not result.posts:
                break
            for post in result.posts:
                try:
                    text = post.record.text
                    if not text.strip():
                        continue
                    es.index(
                        index="social_posts",
                        id="bluesky_" + post.uri.split("/")[-1],
                        document={
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
                    )
                    count += 1
                except Exception as e:
                    print("[BlueSky] 单条错误: " + str(e))
                    continue
            if hasattr(result, "cursor") and result.cursor:
                cursor = result.cursor
            else:
                break
            time.sleep(3)
        except Exception as e:
            print("[BlueSky] 错误: " + str(e))
            time.sleep(15)
            break
    return count

def harvest(environ=None, start_response=None):
    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)
    total = 0
    for kw in KEYWORDS:
        count = harvest_keyword(client, es, kw)
        total += count
        print("[BlueSky] " + kw + " 完成: " + str(count) + " 条")
        time.sleep(5)
    print("[BlueSky] 全部完成！共 " + str(total) + " 条")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [("bluesky done: " + str(total)).encode()]

if __name__ == "__main__":
    os.environ["BLUESKY_PASSWORD"] = "7rsg-hzpy-eesq-oy5d"
    os.environ["ES_HOST"] = "https://localhost:9200"
    harvest()
