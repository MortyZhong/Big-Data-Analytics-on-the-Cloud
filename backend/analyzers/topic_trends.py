# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413

# analytics/topic_trends.py
from elasticsearch import Elasticsearch
import urllib3
import json

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================
# ElasticSearch Connection
# =========================

es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", "elastic"),
    verify_certs=False
)

INDEX_NAME = "social_posts"


# =========================
# Query Topic Trends
# =========================

def get_topic_trends():
    query = {
        "size": 0,

        "query": {
            "terms": {
                "topic": ["war", "tariff", "oil"]
            }
        },

        "aggs": {
            "posts_over_time": {
                "date_histogram": {
                    "field": "created_at",
                    "calendar_interval": "week"  ## per week
                },
                "aggs": {
                    "topics": {
                        "terms": {
                            "field": "topic",
                            "size": 10
                        }
                    }
                }
            }
        }
    }

    response = es.search(
        index=INDEX_NAME,
        body=query
    )

    buckets = response["aggregations"]["posts_over_time"]["buckets"]

    results = []

    for day_bucket in buckets:

        date = day_bucket["key_as_string"]

        topic_counts = {}

        for topic_bucket in day_bucket["topics"]["buckets"]:
            topic_counts[topic_bucket["key"]] = topic_bucket["doc_count"]

        results.append({
            "date": date,
            "topics": topic_counts
        })

    return results


# =========================
# Main
# =========================

if __name__ == "__main__":

    try:

        trends = get_topic_trends()

        print("\n=== Topic Trends ===\n")

        print(json.dumps(trends, indent=2))

    except Exception as e:

        print(f"Error: {e}")