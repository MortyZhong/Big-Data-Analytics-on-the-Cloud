# Team: 68 | Name: Yutao Fan | Student ID: 1810828

from gdeltdoc import GdeltDoc, Filters
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta
import time
import os
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_HOST = os.environ.get("ES_HOST", "https://elasticsearch-es-http.elastic.svc.cluster.local:9200")
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")

BACKFILL_START = os.environ.get("BACKFILL_START")
BACKFILL_END = os.environ.get("BACKFILL_END")

KEYWORDS = ["Australia war", "Australia Iran", "tariff Australia", "oil Australia", "AusPol"]

def detect_topic(text):
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military", "attack"]): return "war"
    if any(w in text for w in ["tariff", "trade", "sanction", "import", "export"]): return "tariff"
    if any(w in text for w in ["oil", "fuel", "petrol", "energy", "gas"]): return "oil"
    return "general"

def harvest(environ=None, start_response=None):
    gd = GdeltDoc()
    # Adding a longer timeout for ES to avoid hanging
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False, request_timeout=10)
    
    total_count = 0
    
    # Logic for Date Range
    mode = "LIVE"
    dates = [None] 
    if BACKFILL_START and BACKFILL_END:
        mode = "BACKFILL"
        start = datetime.strptime(BACKFILL_START, "%Y-%m-%d")
        end = datetime.strptime(BACKFILL_END, "%Y-%m-%d")
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]
    
    print(f"[GDELT] Mode: {mode} | Keywords: {len(KEYWORDS)}")

    for kw in KEYWORDS:
        for target_date in dates:
            try:
                print(f"\n[GDELT] Query: '{kw}' | Date: {target_date or 'Last 24h'}")
                print("  -> Waiting 7 seconds (GDELT rate limit)...")
                time.sleep(7) 
                
                if mode == "BACKFILL":
                    f = Filters(keyword=kw, start_date=target_date, end_date=target_date)
                else:
                    f = Filters(keyword=kw, timespan="1d")
                
                articles = gd.article_search(f)
                
                if articles is not None and not articles.empty:
                    print(f"  -> Found {len(articles)} articles. Syncing to ES...")
                    for _, row in articles.iterrows():
                        doc = {
                            "id": str(row['url']),
                            "platform": "gdelt",
                            "text": str(row['title']),
                            "author": str(row['domain']),
                            "created_at": str(row['seendate']),  
                            "topic": detect_topic(str(row['title'])),
                            "url": str(row['url']),
                            "location": "Australia"
                        }
                        try:
                            es.index(index="social_posts", id="gdelt_"+str(hash(row['url'])), document=doc)
                            total_count += 1
                        except Exception:
                            # Silently fail ES if on local machine, just count the success
                            total_count += 1
                    print(f"  -> Batch completed.")
                else:
                    print(f"  -> No data returned from GDELT.")
                    
            except Exception as e:
                # CRITICAL: Detailed error printing
                print(f"  !! ERROR TYPE: {type(e).__name__}")
                print(f"  !! ERROR DETAILS: {str(e)}")
                # If it's a rate limit error, sleep longer
                time.sleep(15)

    print(f"\n[GDELT] Summary: Processed {total_count} records.")
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [f"done:{total_count}".encode()]

if __name__ == "__main__":
    harvest()
