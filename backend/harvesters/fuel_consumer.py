# backend/harvesters/fuel_consumer.py
# Team: 68 | Name: 舒奎元 | Student ID: 1345012
# 消费 Redis 队列里的油价数据，存进 ElasticSearch official_data index

import json
import os
import urllib3
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone

import redis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Redis 配置 ────────────────────────────────────────────────
REDIS_HOST = "redis.redis.svc.cluster.local"
REDIS_PORT = 6379
REDIS_PASS = ""
QUEUE_KEY  = "official_data:queue"

# ── ElasticSearch 配置 ────────────────────────────────────────
ES_HOST  = "elasticsearch-es-http.elastic.svc.cluster.local"
ES_PORT  = 9200
ES_USER  = "elastic"
ES_PASS  = os.environ.get("ES_PASS", "elastic")
ES_INDEX = "official_data"
BATCH    = 100   # 每次处理100条


def es_index(doc_id, doc):
    """存一条数据进 ES"""
    url  = f"https://{ES_HOST}:{ES_PORT}/{ES_INDEX}/_doc/{doc_id}"
    data = json.dumps(doc).encode("utf-8")
    creds = b64encode(f"{ES_USER}:{ES_PASS}".encode()).decode()

    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Basic {creds}",
        }
    )
    # 忽略 SSL 验证
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        return resp.status in (200, 201)


def consume(environ=None, start_response=None):
    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASS or None, decode_responses=True,
    )

    stored = errors = 0

    for _ in range(BATCH):
        raw = r.rpop(QUEUE_KEY)
        if not raw:
            break

        try:
            doc = json.loads(raw)

            # 生成唯一 ID
            doc_id = f"fuel_{doc['source'].replace(' ', '_')}_{doc['location'].replace(' ', '_')}_{doc['date'][:10]}_{doc['type']}"

            if es_index(doc_id, doc):
                stored += 1
            else:
                errors += 1

        except Exception as e:
            errors += 1
            print(f"[FUEL-CONSUMER] 错误: {e}")

    msg = f"fuel consumer done: stored={stored} errors={errors}"
    print(f"[FUEL-CONSUMER] {msg}")

    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
    return msg
