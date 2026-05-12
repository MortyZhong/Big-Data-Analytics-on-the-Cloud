import os
import urllib3
from elasticsearch import Elasticsearch, helpers
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ELASTIC_URL = os.environ.get("ES_HOST", "https://localhost:9200")
ELASTIC_USER = os.environ.get("ES_USER", "elastic")
ELASTIC_PASSWORD = os.environ.get("ES_PASS", "elastic")

INDEX_NAME = "social_posts"


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
                    {
                        "exists": {
                            "field": "text"
                        }
                    }
                ],
                "must_not": [
                    {
                        "exists": {
                            "field": "sentiment"
                        }
                    }
                ]
            }
        }
    }

def run_vader_sentiment():
    es = get_es_client()
    analyzer = SentimentIntensityAnalyzer()

    query = build_query()

    processed = 0
    skipped = 0
    actions = []
    max_docs = None

    for doc in helpers.scan(
        client=es,
        index=INDEX_NAME,
        query=query,
        scroll="5m",
        size=500
    ):
        doc_id = doc["_id"]
        source = doc["_source"]

        text = source.get("text", "")

        if not isinstance(text, str) or not text.strip():
            skipped += 1
            continue

        scores = analyzer.polarity_scores(text)
        compound = scores["compound"]
        label = classify_sentiment(compound)

        action = {
            "_op_type": "update",
            "_index": INDEX_NAME,
            "_id": doc_id,
            "doc": {
                "sentiment": compound,
                "sentiment_score": compound,
                "sentiment_label": label
            }
        }

        actions.append(action)

        if max_docs is not None and len(actions) >= max_docs:
            break

        if len(actions) >= 500:
            helpers.bulk(es, actions)
            processed += len(actions)
            print(f"Processed {processed} documents...")
            actions = []

    if actions:
        helpers.bulk(es, actions)
        processed += len(actions)

    print("VADER sentiment analysis finished.")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")

    return {
        "status": "success",
        "processed": processed,
        "skipped": skipped
    }


def main():
    return run_vader_sentiment()


if __name__ == "__main__":
    run_vader_sentiment()
