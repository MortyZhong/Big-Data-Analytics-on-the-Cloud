# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
# analytics/topic_counts.py
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
# Query Topic Counts
# =========================

def get_topic_counts():
    """
    Count how many posts belong to each topic.
    """

    query = {
        "size": 0,

        "query": {
            "terms": {
                "topic": ["war", "tariff", "oil"]
            }
        },

        "aggs": {
            "topics": {
                "terms": {
                    "field": "topic",
                    "size": 20
                }
            }
        }
    }

    response = es.search(
        index=INDEX_NAME,
        body=query
    )

    buckets = response["aggregations"]["topics"]["buckets"]

    results = []

    for bucket in buckets:
        results.append({
            "topic": bucket["key"],
            "count": bucket["doc_count"]
        })

    #return results
    return {
        "status": "success",
        "scenario": "scenario_b",
        "metric": "topic_counts",
        "data": results
    }


# =========================
# Main
# =========================

if __name__ == "__main__":

    try:
        topic_counts = get_topic_counts()

        #print("\n=== Topic Counts ===\n")

        print(json.dumps(topic_counts, indent=2))

    except Exception as e:
        print(f"Error: {e}")