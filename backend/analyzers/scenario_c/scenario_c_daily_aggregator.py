# Team: 68
# Name: Yueting Duan
# Student ID: 1736334
# File: scenario_c_daily_aggregator.py
# Description: Daily aggregation of official fuel prices and oil-related social media sentiment.

import os
from collections import defaultdict
from datetime import datetime, timezone

import urllib3
from elasticsearch import Elasticsearch, helpers

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ELASTIC_URL = os.environ.get("ES_HOST", "https://localhost:9200")
ELASTIC_USER = os.environ.get("ES_USER", "elastic")
ELASTIC_PASSWORD = os.environ.get("ES_PASS", "elastic")

OFFICIAL_INDEX = "official_data"
SOCIAL_INDEX = "social_posts"
OUTPUT_INDEX = "scenario_c_daily"

FUEL_TYPES = ["u91", "u95", "u98", "diesel"]
LOCATION = "WA"


def get_es_client():
    return Elasticsearch(
        ELASTIC_URL,
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
        verify_certs=False,
        request_timeout=60,
    )


def parse_date_to_day(value):
    """
    Convert ISO datetime string to YYYY-MM-DD.
    """
    if not value:
        return None

    try:
        value = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        return dt.date().isoformat()
    except Exception:
        return None


def create_output_index(es):
    """
    Recreate scenario_c_daily index.
    This only deletes the derived aggregation index, not raw data.
    """
    if es.indices.exists(index=OUTPUT_INDEX):
        print(f"Deleting existing index: {OUTPUT_INDEX}")
        es.indices.delete(index=OUTPUT_INDEX)

    mapping = {
        "mappings": {
            "properties": {
                "date": {"type": "date"},
                "fuel_type": {"type": "keyword"},
                "location": {"type": "keyword"},
                "avg_fuel_price": {"type": "float"},
                "avg_sentiment_score": {"type": "float"},
                "negative_ratio": {"type": "float"},
                "oil_post_count": {"type": "integer"},
                "negative_post_count": {"type": "integer"},
                "source": {"type": "keyword"},
                "created_at": {"type": "date"},
            }
        }
    }

    es.indices.create(index=OUTPUT_INDEX, body=mapping)
    print(f"Created index: {OUTPUT_INDEX}")


def load_official_fuel_prices(es):
    """
    Load official WA fuel prices from official_data and aggregate by date and fuel type.
    """
    query = {
        "query": {
            "bool": {
                "filter": [
                    {"terms": {"type": FUEL_TYPES}},
                    {"term": {"location": LOCATION}},
                    {"exists": {"field": "price"}},
                    {"exists": {"field": "date"}},
                ]
            }
        }
    }

    prices_by_type_and_day = defaultdict(lambda: defaultdict(list))

    for doc in helpers.scan(
        client=es,
        index=OFFICIAL_INDEX,
        query=query,
        scroll="5m",
        size=500,
    ):
        source = doc["_source"]

        fuel_type = source.get("type")
        day = parse_date_to_day(source.get("date"))
        price = source.get("price")

        if fuel_type not in FUEL_TYPES or day is None or price is None:
            continue

        try:
            prices_by_type_and_day[fuel_type][day].append(float(price))
        except Exception:
            continue

    fuel_daily = defaultdict(dict)

    for fuel_type, day_prices in prices_by_type_and_day.items():
        for day, prices in day_prices.items():
            if prices:
                fuel_daily[fuel_type][day] = sum(prices) / len(prices)

    for fuel_type in FUEL_TYPES:
        print(f"Official fuel days loaded for {fuel_type}: {len(fuel_daily[fuel_type])}")

    return fuel_daily


def load_social_oil_sentiment(es):
    """
    Load oil-related social media posts with VADER sentiment and aggregate by date.
    Only use real social platforms.
    """
    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"topic": "oil"}},
                    {"exists": {"field": "sentiment_score"}},
                    {"exists": {"field": "created_at"}},
                    {
                        "terms": {
                            "platform": ["reddit", "bluesky", "mastodon"]
                        }
                    },
                ]
            }
        }
    }

    sentiment_by_day = defaultdict(list)
    negative_by_day = defaultdict(int)
    count_by_day = defaultdict(int)

    for doc in helpers.scan(
        client=es,
        index=SOCIAL_INDEX,
        query=query,
        scroll="5m",
        size=500,
    ):
        source = doc["_source"]

        day = parse_date_to_day(source.get("created_at"))
        score = source.get("sentiment_score")
        label = source.get("sentiment_label")

        if day is None or score is None:
            continue

        try:
            score = float(score)
        except Exception:
            continue

        sentiment_by_day[day].append(score)
        count_by_day[day] += 1

        if label == "negative":
            negative_by_day[day] += 1

    social_daily = {}

    for day, scores in sentiment_by_day.items():
        total = count_by_day[day]
        negative_count = negative_by_day[day]

        social_daily[day] = {
            "avg_sentiment_score": sum(scores) / len(scores),
            "oil_post_count": total,
            "negative_post_count": negative_count,
            "negative_ratio": negative_count / total if total > 0 else 0,
        }

    print(f"Social sentiment days loaded: {len(social_daily)}")
    return social_daily


def build_daily_records(fuel_daily, social_daily):
    """
    Merge fuel prices and social sentiment on common dates.
    One record per date and fuel type.
    """
    records = []

    for fuel_type in FUEL_TYPES:
        common_days = sorted(set(fuel_daily[fuel_type].keys()) & set(social_daily.keys()))

        print(f"Common days for {fuel_type}: {len(common_days)}")

        for day in common_days:
            social = social_daily[day]

            record = {
                "date": day,
                "fuel_type": fuel_type,
                "location": LOCATION,
                "avg_fuel_price": fuel_daily[fuel_type][day],
                "avg_sentiment_score": social["avg_sentiment_score"],
                "negative_ratio": social["negative_ratio"],
                "oil_post_count": social["oil_post_count"],
                "negative_post_count": social["negative_post_count"],
                "source": "FuelWatch WA + social_posts",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            records.append(record)

    print(f"Total records written: {len(records)}")
    return records


def write_records(es, records):
    actions = []

    for record in records:
        doc_id = f"{record['date']}_{record['fuel_type']}_{record['location']}"

        actions.append(
            {
                "_op_type": "index",
                "_index": OUTPUT_INDEX,
                "_id": doc_id,
                "_source": record,
            }
        )

    if actions:
        helpers.bulk(es, actions)

    print(f"Written records: {len(actions)}")


def main():
    es = get_es_client()

    create_output_index(es)

    fuel_daily = load_official_fuel_prices(es)
    social_daily = load_social_oil_sentiment(es)

    records = build_daily_records(fuel_daily, social_daily)
    write_records(es, records)

    print("Scenario C daily aggregation finished.")


if __name__ == "__main__":
    main()
