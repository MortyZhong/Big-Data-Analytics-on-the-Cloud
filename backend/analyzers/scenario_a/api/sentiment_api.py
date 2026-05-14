# Team: 68
# Name: Yueting Duan
# Student ID: 1736334
# File: sentiment_api.py
# Description: RESTful API for Scenario A daily social media sentiment results.

import os
import json
import urllib3
from elasticsearch import Elasticsearch

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_HOST = os.environ.get(
    "ES_HOST",
    "https://elasticsearch-es-http.elastic.svc.cluster.local:9200"
)
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")

INDEX_NAME = "social_posts"


def get_es_client():
    return Elasticsearch(
        ES_HOST,
        basic_auth=(ES_USER, ES_PASS),
        verify_certs=False,
        request_timeout=60
    )


def get_sentiment_data():
    es = get_es_client()

    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"exists": {"field": "sentiment"}},
                    {"terms": {"topic": ["war", "tariff", "oil"]}},
                    {"terms": {"platform": ["reddit", "bluesky", "mastodon"]}}
                ]
            }
        },
        "aggs": {
            "by_day": {
                "date_histogram": {
                    "field": "created_at",
                    "calendar_interval": "day",
                    "format": "yyyy-MM-dd",
                    "min_doc_count": 1
                },
                "aggs": {
                    "by_topic": {
                        "terms": {
                            "field": "topic",
                            "size": 10
                        },
                        "aggs": {
                            "by_platform": {
                                "terms": {
                                    "field": "platform",
                                    "size": 10
                                },
                                "aggs": {
                                    "avg_sentiment": {
                                        "avg": {
                                            "field": "sentiment"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    response = es.search(index=INDEX_NAME, body=query)

    results = []

    day_buckets = response.get("aggregations", {}).get("by_day", {}).get("buckets", [])

    for day_bucket in day_buckets:
        date = day_bucket.get("key_as_string")

        topic_buckets = day_bucket.get("by_topic", {}).get("buckets", [])

        for topic_bucket in topic_buckets:
            topic = topic_bucket.get("key")

            platform_buckets = topic_bucket.get("by_platform", {}).get("buckets", [])

            for platform_bucket in platform_buckets:
                platform = platform_bucket.get("key")
                count = platform_bucket.get("doc_count", 0)
                avg_value = platform_bucket.get("avg_sentiment", {}).get("value")

                if avg_value is None:
                    continue

                results.append({
                    "date": date,
                    "topic": topic,
                    "platform": platform,
                    "avg_sentiment": round(avg_value, 4),
                    "post_count": count
                })

    return {
        "status": "success",
        "scenario": "scenario_a",
        "metric": "daily_sentiment",
        "data": results
    }


def main():
    try:
        return get_sentiment_data()
    except Exception as e:
        return {
            "status": "error",
            "scenario": "scenario_a",
            "message": str(e)
        }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
