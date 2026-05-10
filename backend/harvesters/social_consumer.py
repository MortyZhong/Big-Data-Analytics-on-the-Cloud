# Team: 68 | Name: Lixin Zhong | Student ID: 1728613

from elasticsearch import Elasticsearch
import redis
import json
import os

REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""
ES_HOST = "https://elasticsearch-es-http.elastic.svc.cluster.local:9200"
ES_USER = "elastic"
ES_PASS = "elastic"

QUEUE_KEY = "social_posts:queue"

def consume(environ=None, start_response=None):
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS or None, decode_responses=True)
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)
    count = 0
    errors = 0
    while True:
        raw = r.rpop(QUEUE_KEY)
        if raw is None:
            break
        try:
            doc = json.loads(raw)
            es_id = doc["platform"] + "_" + doc["id"].split("/")[-1]
            es.index(index="social_posts", id=es_id, document=doc)
            count += 1
        except Exception as e:
            errors += 1
            print("[Consumer] 单条错误: " + str(e))
            continue
    print("[Consumer] 完成！写入: " + str(count) + " 条，错误: " + str(errors) + " 次")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return "consumer done: " + str(count)
