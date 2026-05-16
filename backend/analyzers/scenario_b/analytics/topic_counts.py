# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
#analytics/topic_counts.py
from elasticsearch import Elasticsearch
import urllib3
import json

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

INDEX_NAME = "social_posts"


def get_es_client():

    print("CREATING ES CLIENT")

    return Elasticsearch(
        "https://elasticsearch-es-http.elastic:9200",
        basic_auth=("elastic", "elastic"),
        verify_certs=False
    )


def get_topic_counts():

    print("START get_topic_counts")

    es = get_es_client()

    print("ES CLIENT CREATED")

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

    print("BEFORE SEARCH")

    response = es.search(
        index=INDEX_NAME,
        body=query
    )

    print("AFTER SEARCH")

    buckets = response["aggregations"]["topics"]["buckets"]

    results = []

    for bucket in buckets:
        results.append({
            "topic": bucket["key"],
            "count": bucket["doc_count"]
        })

    print("RETURNING RESULT")

    return {
        "status": "success",
        "scenario": "scenario_b",
        "metric": "topic_counts",
        "data": results
    }


if __name__ == "__main__":

    try:

        topic_counts = get_topic_counts()

        print(json.dumps(topic_counts, indent=2))

    except Exception as e:

        print(f"Error: {e}")