# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

from mastodon import Mastodon
from elasticsearch import Elasticsearch
import re, time

MASTODON_TOKEN = "LdayWQTCWsDqcS8JBZG27v32ua-5p6xzUVoz57kd8_Q"
MASTODON_API_BASE = "https://mastodon.au"
ES_HOST = "https://localhost:9200"
ES_USER = "elastic"
ES_PASS = "elastic"
TAGS = ["Australia", "AusPol", "war", "tariff", "oil", "Iran"]

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text)

def detect_topic(text):
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military"]):
        return "war"
    elif any(w in text for w in ["tariff", "trade", "sanction"]):
        return "tariff"
    elif any(w in text for w in ["oil", "fuel", "petrol", "energy"]):
        return "oil"
    return "general"

def harvest(environ=None, start_response=None):
    mastodon = Mastodon(access_token=MASTODON_TOKEN, api_base_url=MASTODON_API_BASE)
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)
    count = 0
    for tag in TAGS:
        try:
            print(f"爬取 #{tag}...")
            time.sleep(2)
            for s in mastodon.timeline_hashtag(tag, limit=40):
                try:
                    if s.get("language") != "en":
                        continue
                    text = clean_html(s["content"])
                    if not text.strip():
                        continue
                    es.index(index="social_posts", id=f"mastodon_{s['id']}", document={
                        "id": str(s["id"]),
                        "platform": "mastodon",
                        "text": text,
                        "author": s["account"]["acct"],
                        "created_at": s["created_at"].isoformat(),
                        "topic": detect_topic(text),
                        "language": s.get("language", "en"),
                        "tags": [t["name"] for t in s.get("tags", [])],
                        "reblogs": s.get("reblogs_count", 0),
                        "favourites": s.get("favourites_count", 0),
                        "url": s.get("url", ""),
                        "location": "Australia"
                    })
                    count += 1
                except Exception as e:
                    print(f"单条错误: {e}")
        except Exception as e:
            print(f"#{tag} 错误: {e}")
            time.sleep(10)
    print(f"完成！共 {count} 条")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [f"done:{count}".encode()]

if __name__ == "__main__":
    harvest()
