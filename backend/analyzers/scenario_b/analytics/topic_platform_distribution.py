# analytics/platform_topic_distribution.py

from elasticsearch import Elasticsearch
import urllib3
import json

# Disable SSL warnings
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

INDEX_NAME = "social_posts"


# ElasticSearch Connection
def get_es_client():

    return Elasticsearch(
        # "https://localhost:9200",  # local test
        "https://elasticsearch-es-http.elastic:9200",
        basic_auth=("elastic", "elastic"),
        verify_certs=False
    )


# Query Platform Topic Distribution

def get_topic_platform_distribution():

    es = get_es_client()

    query = {
        "size": 0,

        # Only keep the topics we care about
        "query": {
            "terms": {
                "topic": ["war", "tariff", "oil"]
            }
        },

        "aggs": {
            "platforms": {
                "terms": {
                    "field": "platform",
                    "size": 10
                },
                "aggs": {
                    "topics": {
                        "terms": {
                            "field": "topic",
                            "size": 3
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

    platform_buckets = response["aggregations"]["platforms"]["buckets"]

    results = []

    for platform_bucket in platform_buckets:

        platform_name = platform_bucket["key"]

        topic_counts = {}

        for topic_bucket in platform_bucket["topics"]["buckets"]:

            topic_counts[topic_bucket["key"]] = topic_bucket["doc_count"]

        results.append({
            "platform": platform_name,
            "topics": topic_counts
        })

    return {
        "status": "success",
        "scenario": "scenario_b",
        "metric": "platform_topic_distribution",
        "data": results
    }

# Main
if __name__ == "__main__":

    try:

        result = get_topic_platform_distribution()

        print("\n=== Platform Topic Distribution ===\n")

        print(json.dumps(result, indent=2))

    except Exception as e:

        print(f"Error: {e}")