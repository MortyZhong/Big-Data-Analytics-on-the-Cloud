# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
from elasticsearch import Elasticsearch
import urllib3
import json
from flask import request


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

INDEX_NAME = "scenario_c_daily"


# =========================
# ElasticSearch Connection
# =========================

def get_es_client():

    return Elasticsearch(
        "https://elasticsearch-es-http.elastic.svc.cluster.local:9200",
        #"https://elasticsearch-es-http.elastic:9200",
        #"https://localhost:9200",#local test
        basic_auth=("elastic", "elastic"),
        verify_certs=False
    )


# =========================
# REST API
# =========================

def main():

    try:

        es = get_es_client()

        fuel_type = request.args.get("fuel_type")

        filters = []

        if fuel_type:
            filters.append({
                "term": {
                    "fuel_type": fuel_type
                }
            })

        query = {
            "size": 1000,
            "sort": [
                {
                    "date": {
                        "order": "asc"
                    }
                }
            ]
        }

        if filters:
            query["query"] = {
                "bool": {
                    "filter": filters
                }
            }

        response = es.search(
            index=INDEX_NAME,
            body=query
        )

        results = []

        for hit in response["hits"]["hits"]:

            source = hit["_source"]

            results.append({
                "date": source.get("date"),
                "fuel_type": source.get("fuel_type"),
                "avg_fuel_price": source.get("avg_fuel_price"),
                "avg_sentiment_score": source.get("avg_sentiment_score"),
                "negative_ratio": source.get("negative_ratio"),
                "oil_post_count": source.get("oil_post_count"),
                "negative_post_count": source.get("negative_post_count")
            })

        return {
            "status": "success",
            "scenario": "scenario_c",
            "count": len(results),
            "data": results
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# =========================
# Local Test
# =========================

if __name__ == "__main__":

    class MockRequest:
        args = {}

    result = main(MockRequest())

    print(json.dumps(result, indent=2))