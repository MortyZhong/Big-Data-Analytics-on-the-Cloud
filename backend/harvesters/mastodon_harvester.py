# backend/harvesters/mastodon_harvester.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

from mastodon import Mastodon
from elasticsearch import Elasticsearch
import re, time, os

MASTODON_TOKEN = os.environ.get("MASTODON_TOKEN", "your_token_here")
MASTODON_API_BASE = "https://mastodon.au"
ES_HOST = os.environ.get("ES_HOST", "https://elasticsearch-es-http.elastic.svc.cluster.local:9200")
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")

TAGS = ["Australia", "AusPol", "war", "tariff", "oil", "Iran"]
PAGES_PER_TAG = 5  # 每个tag翻5页，每页40条，共200条

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text)

def detect_topic(text):
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military", "attack"]):
        return "war"
    elif any(w in text for w in ["tariff", "trade", "sanction", "import", "export"]):
        return "tariff"
    elif any(w in text for w in ["oil", "fuel", "petrol", "energy", "gas"]):
        return "oil"
    return "general"

def harvest_tag(mastodon, es, tag):
    count = 0
    max_id = None

    for page in range(PAGES_PER_TAG):
        try:
            print(f"[Mastodon] #{tag} 第{page+1}页...")

            # 翻页：传入 max_id 拿下一页
            if max_id:
                statuses = mastodon.timeline_hashtag(tag, limit=40, max_id=max_id)
            else:
                statuses = mastodon.timeline_hashtag(tag, limit=40)

            if not statuses:
                print(f"[Mastodon] #{tag} 没有更多数据了")
                break

            for s in statuses:
                try:
                    if s.get("language") != "en":
                        continue
                    text = clean_html(s["content"])
                    if not text.strip():
                        continue

                    es.index(
                        index="social_posts",
                        id="mastodon_" + str(s["id"]),
                        document={
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
                        }
                    )
                    count += 1
                except Exception as e:
                    print("[Mastodon] 单条错误: " + str(e))
                    continue

            # 拿最后一条的ID，用于下一页
            max_id = statuses[-1]["id"]

            # 反爬虫：每页之间等2秒
            time.sleep(2)

        except Exception as e:
            print("[Mastodon] #" + tag + " 第" + str(page+1) + "页错误: " + str(e))
            time.sleep(10)
            break

    return count

def harvest(environ=None, start_response=None):
    mastodon = Mastodon(
        access_token=MASTODON_TOKEN,
        api_base_url=MASTODON_API_BASE
    )
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)

    total = 0
    for tag in TAGS:
        count = harvest_tag(mastodon, es, tag)
        total += count
        print("[Mastodon] #" + tag + " 完成: " + str(count) + " 条")
        time.sleep(3)

    print("[Mastodon] 全部完成！共 " + str(total) + " 条")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [("mastodon done: " + str(total)).encode()]

if __name__ == "__main__":
    os.environ["MASTODON_TOKEN"] = "LdayWQTCWsDqcS8JBZG27v32ua-5p6xzUVoz57kd8_Q"
    os.environ["ES_HOST"] = "https://localhost:9200"
    harvest()