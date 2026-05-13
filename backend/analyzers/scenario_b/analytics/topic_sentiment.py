# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
# analytics/topic_sentiment.py

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
# Query Topic Average Sentiment
# =========================

def get_topic_sentiment():

    query = {
        "size": 0,

        # Only keep the topics we care about
        "query": {
            "terms": {
                "topic": ["war", "tariff", "oil"]
            }
        },

        "aggs": {
            "topics": {
                "terms": {
                    "field": "topic",
                    "size": 3
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

    response = es.search(
        index=INDEX_NAME,
        body=query
    )

    topic_buckets = response["aggregations"]["topics"]["buckets"]

    results = []

    for bucket in topic_buckets:

        results.append({
            "topic": bucket["key"],
            "average_sentiment": round(
                bucket["avg_sentiment"]["value"], 4
            )
        })

    return {
        "status": "success",
        "scenario": "scenario_b",
        "metric": "topic_sentiment",
        "data": results
    }


# =========================
# Main
# =========================

if __name__ == "__main__":

    try:

        result = get_topic_sentiment()

        print("\n=== Topic Average Sentiment ===\n")

        print(json.dumps(result, indent=2))

    except Exception as e:

        print(f"Error: {e}")

        