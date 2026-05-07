# backend/harvesters/reddit_harvester.py

import requests
import random
import time

from datetime import datetime, timezone
from elasticsearch import Elasticsearch


ELASTIC_URL = "https://elasticsearch-es-http.elastic.svc.cluster.local:9200"
ELASTIC_USER = "elastic"
ELASTIC_PASSWORD = "elastic"


TARGET_SUBREDDITS = [
    "australia",
    "AusPolitics",
    "AusFinance",
    "melbourne"
]


SEARCH_TERMS = {
    "war": [
        "war",
        "iran",
        "ukraine",
        "military"
    ],

    "tariff": [
        "tariff",
        "trade war",
        "sanction"
    ],

    "oil": [
        "oil",
        "fuel",
        "petrol",
        "energy crisis"
    ]
}


BROWSER_HEADERS = [
    "Mozilla/5.0",
    "Chrome/124.0",
    "Safari/537.36"
]


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
            post_data.get("created_utc", 0),
            tz=timezone.utc
        ).isoformat(),

        "topic": classify_topic(content),

        "language": "en",

        "location": "Australia",

        "url": "https://reddit.com" + post_data.get("permalink", ""),

        "source": "reddit",

        "subreddit": post_data.get("subreddit"),

        "score": post_data.get("score", 0),

        "raw_data": post_data
    }


def harvest(environ, start_response):

    elastic = Elasticsearch(
        ELASTIC_URL,
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
        verify_certs=False
    )

    inserted_count = 0

    for subreddit_name in TARGET_SUBREDDITS:

        for topic_name, term_list in SEARCH_TERMS.items():

            for search_term in term_list:

                api_url = (
                    f"https://old.reddit.com/r/"
                    f"{subreddit_name}/search.json"
                )

                query_params = {
                    "q": search_term,
                    "restrict_sr": 1,
                    "sort": "new",
                    "limit": 50
                }

                request_headers = {
                    "User-Agent": random.choice(BROWSER_HEADERS)
                }

                print(
                    f"[Crawler] subreddit={subreddit_name} "
                    f"topic={topic_name} "
                    f"keyword={search_term}"
                )

                attempts = 3

                while attempts > 0:

                    try:

                        response = requests.get(
                            api_url,
                            params=query_params,
                            headers=request_headers,
                            timeout=15
                        )

                        print(
                            f"[Crawler] status={response.status_code}"
                        )

                        if response.status_code == 429:

                            wait_seconds = random.uniform(60, 120)

                            print(
                                f"[Crawler] rate limited "
                                f"sleeping {wait_seconds:.1f}s"
                            )

                            time.sleep(wait_seconds)

                            attempts -= 1

                            continue

                        if response.status_code != 200:

                            print(
                                f"[Crawler] failed request"
                            )

                            break

                        try:

                            payload = response.json()

                        except Exception:

                            print(
                                "[Crawler] invalid json response"
                            )

                            break

                        post_list = (
                            payload.get("data", {})
                            .get("children", [])
                        )

                        print(
                            f"[Crawler] fetched "
                            f"{len(post_list)} posts"
                        )

                        for item in post_list:

                            post = item.get("data", {})

                            title = post.get("title") or ""
                            body = post.get("selftext") or ""

                            combined_text = (
                                f"{title} {body}"
                            ).strip()

                            document = build_document(
                                post,
                                combined_text
                            )

                            elastic.index(
                                index="social_posts",
                                id=f"reddit_{document['id']}",
                                document=document
                            )

                            inserted_count += 1

                        delay = random.uniform(2, 6)

                        print(
                            f"[Crawler] sleeping "
                            f"{delay:.1f}s"
                        )

                        time.sleep(delay)

                        break

                    except Exception as error:

                        print(
                            f"[Crawler] error={error}"
                        )

                        attempts -= 1

                        retry_delay = random.uniform(5, 15)

                        time.sleep(retry_delay)

    start_response(
        "200 OK",
        [("Content-Type", "text/plain")]
    )

    return [
        f"reddit crawler inserted "
        f"{inserted_count} posts".encode()
    ]
