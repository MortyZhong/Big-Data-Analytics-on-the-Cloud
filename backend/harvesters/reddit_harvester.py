# backend/harvesters/reddit_harvester.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

import requests
import random
import time
import os
from datetime import datetime, timezone, timedelta
from elasticsearch import Elasticsearch

ELASTIC_URL = os.environ.get("ES_HOST", "https://elasticsearch-es-http.elastic.svc.cluster.local:9200")
ELASTIC_USER = os.environ.get("ES_USER", "elastic")
ELASTIC_PASSWORD = os.environ.get("ES_PASS", "elastic")

TARGET_SUBREDDITS = ["australia", "AusPolitics", "AusFinance", "melbourne"]

SEARCH_TERMS = {
    "war": ["war", "iran", "ukraine", "military"],
    "tariff": ["tariff", "trade war", "sanction"],
    "oil": ["oil", "fuel", "petrol", "energy crisis"]
}

BROWSER_HEADERS = ["Mozilla/5.0", "Chrome/124.0", "Safari/537.36"]
PAGES_PER_SEARCH = 5

# 3个月前的时间
THREE_MONTHS_AGO = datetime.now(tz=timezone.utc) - timedelta(days=90)

def classify_topic(content):
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

def build_document(post_data, content):
    return {
        "id": post_data.get("id"),
        "platform": "reddit",
        "text": content,
        "author": post_data.get("author"),
        "created_at": datetime.fromtimestamp(
            post_data.get("created_utc", 0), tz=timezone.utc
        ).isoformat(),
        "topic": classify_topic(content),
        "language": "en",
        "location": "Australia",
        "url": "https://reddit.com" + post_data.get("permalink", ""),
        "subreddit": post_data.get("subreddit"),
        "score": post_data.get("score", 0),
        "favourites": post_data.get("score", 0),
        "tags": [],
        "reblogs": 0
    }

def fetch_page(subreddit, search_term, after=None):
    api_url = "https://old.reddit.com/r/" + subreddit + "/search.json"
    query_params = {
        "q": search_term,
        "restrict_sr": 1,
        "sort": "new",
        "limit": 100,
        "t": "year"   # ← 拿过去一年，再用时间过滤到3个月
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
                print("[Reddit] rate limited, sleeping " + str(wait))
                time.sleep(wait)
                attempts -= 1
                continue
            if response.status_code != 200:
                print("[Reddit] failed: " + str(response.status_code))
                return None, None
            payload = response.json()
            data = payload.get("data", {})
            return data.get("children", []), data.get("after", None)
        except Exception as e:
            print("[Reddit] error: " + str(e))
            attempts -= 1
            time.sleep(random.uniform(5, 15))
    return None, None

def harvest(environ=None, start_response=None):
    elastic = Elasticsearch(
        ELASTIC_URL,
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
        verify_certs=False
    )
    inserted_count = 0
    skipped_count = 0

    for subreddit_name in TARGET_SUBREDDITS:
        for topic_name, term_list in SEARCH_TERMS.items():
            for search_term in term_list:
                print("[Reddit] " + subreddit_name + " - " + search_term)
                after = None
                for page in range(PAGES_PER_SEARCH):
                    print("[Reddit] 第" + str(page+1) + "页...")
                    posts, after = fetch_page(subreddit_name, search_term, after)
                    if not posts:
                        break
                    for item in posts:
                        post = item.get("data", {})
                        title = post.get("title") or ""
                        body = post.get("selftext") or ""
                        combined_text = (title + " " + body).strip()
                        if not combined_text:
                            continue

                        # ← 只要3个月内的帖子
                        created_utc = post.get("created_utc", 0)
                        post_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if post_time < THREE_MONTHS_AGO:
                            skipped_count += 1
                            continue

                        document = build_document(post, combined_text)
                        elastic.index(
                            index="social_posts",
                            id="reddit_" + str(document["id"]),
                            document=document
                        )
                        inserted_count += 1

                    time.sleep(random.uniform(2, 6))
                    if not after:
                        print("[Reddit] 没有更多页了")
                        break

    print("[Reddit] 完成！存入: " + str(inserted_count) + " 条，跳过: " + str(skipped_count) + " 条")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [("reddit done: " + str(inserted_count)).encode()]

if __name__ == "__main__":
    os.environ["ES_HOST"] = "https://localhost:9200"
    harvest()
