# Team: 68
# Name: Yueting Duan
# Student ID: 1736334
# File: vader_sentiment.py
# Description: Batch VADER sentiment analysis for social_posts.

import os
import urllib3
from elasticsearch import Elasticsearch, helpers
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ELASTIC_URL = os.environ.get(
    "ES_HOST",
    "https://elasticsearch-es-http.elastic.svc.cluster.local:9200"
)
ELASTIC_USER = os.environ.get("ES_USER", "elastic")
ELASTIC_PASSWORD = os.environ.get("ES_PASS", "elastic")

INDEX_NAME = "social_posts"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5000"))


def get_es_client():
    return Elasticsearch(
        ELASTIC_URL,
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
        verify_certs=False,
        request_timeout=60
    )


def classify_sentiment(compound):
    if compound >= 0.05:
        return "positive"
    elif compound <= -0.05:
        return "negative"
    else:
        return "neutral"


def build_query():
    return {
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "text"}}
                ],
                "filter": [
                    {"terms": {"platform": ["reddit", "bluesky", "mastodon"]}},
                    {"terms": {"topic": ["war", "tariff", "oil"]}}
                ],
                "must_not": [
                    {"exists": {"field": "sentiment_score"}}
                ]
            }
        },
        "size": BATCH_SIZE,
        "_source": ["text", "platform", "topic", "created_at"]
    }


def run_vader_sentiment():
    es = get_es_client()
    analyzer = SentimentIntensityAnalyzer()

    response = es.search(
        index=INDEX_NAME,
        body=build_query()
    )

    hits = response.get("hits", {}).get("hits", [])

    if not hits:
        result = {
            "status": "success",
            "processed": 0,
            "skipped": 0,
            "message": "No new documents need VADER sentiment analysis."
        }
        print(result)
        return result

    actions = []
    skipped = 0

    for hit in hits:
        doc_id = hit["_id"]
        source = hit.get("_source", {})
        text = source.get("text", "")

        if not isinstance(text, str) or not text.strip():
            skipped += 1
            continue

        scores = analyzer.polarity_scores(text)
        compound = scores["compound"]
        label = classify_sentiment(compound)

        actions.append(
            {
                "_op_type": "update",
                "_index": INDEX_NAME,
                "_id": doc_id,
                "doc": {
                    "sentiment": compound,
                    "sentiment_score": compound,
                    "sentiment_label": label
                }
            }
        )

    if actions:
        helpers.bulk(es, actions)

    result = {
        "status": "success",
        "processed": len(actions),
        "skipped": skipped,
        "batch_size": BATCH_SIZE
    }

    print(result)
    return result


def main():
    return run_vader_sentiment()


if __name__ == "__main__":
    run_vader_sentiment()
