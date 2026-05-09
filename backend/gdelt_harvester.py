# Team: 68 | Name: Yutao Fan | Student ID: 1810828

from gdeltdoc import GdeltDoc, Filters
from elasticsearch import Elasticsearch
import time
import os

# Environment variables configuration (compatible with local testing and K8s cluster deployment)
ES_HOST = os.environ.get("ES_HOST", "https://elasticsearch-es-http.elastic.svc.cluster.local:9200")
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")

# List of keywords to search
KEYWORDS = ["Australia war", "Australia Iran", "tariff Australia", "oil Australia", "AusPol"]

def detect_topic(text):
    """Dynamic topic classifier, kept consistent with teammates"""
    text = text.lower()
    if any(w in text for w in ["war", "iran", "conflict", "military", "attack"]):
        return "war"
    elif any(w in text for w in ["tariff", "trade", "sanction", "import", "export"]):
        return "tariff"
    elif any(w in text for w in ["oil", "fuel", "petrol", "energy", "gas"]):
        return "oil"
    return "general"

def harvest(environ=None, start_response=None):
    """Main harvesting function, compatible with Fission WSGI invocation"""
    gd = GdeltDoc()
    es = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)
    
    count = 0
    errors = 0
    
    for kw in KEYWORDS:
        try:
            print(f"[GDELT] Searching for keyword: {kw}")
            time.sleep(2) # Polite delay to avoid being blocked by GDELT API
            
            # Use 1d (last 24 hours) to avoid API timeout/hang
            f = Filters(keyword=kw, timespan="1d")
            articles = gd.article_search(f)
            
            # GDELT might return an empty DataFrame
            if articles.empty:
                print(f"[GDELT] No news found for keyword '{kw}'.")
                continue
                
            for index, row in articles.iterrows():
                try:
                    title_text = str(row['title'])
                    if not title_text.strip():
                        continue
                        
                    # Uniform mapping to the team's standard Schema
                    doc = {
                        "id": str(row['url']),               # Uniform ID format
                        "platform": "gdelt",                 # Platform identifier
                        "text": title_text,                  # GDELT's title corresponds to social media's text
                        "author": str(row['domain']),        # News source domain treated as author
                        # Store created_at directly if string; convert if datetime
                        "created_at": str(row['seendate']),  
                        "topic": detect_topic(title_text),   # Dynamic classification
                        "language": str(row.get('language', 'en')), 
                        "tags": [],                          # News has no tags currently, left empty for structure consistency
                        "reblogs": 0,                        # Uniform field
                        "favourites": 0,                     # Uniform field
                        "url": str(row['url']),
                        "location": "Australia",
                        "sentiment": 0.0                     # Reserved sentiment placeholder for GDELT
                    }
                    
                    # Write to Elasticsearch, ensure it goes to the same index as teammates
                    # Handle ES _id using URL hash to prevent special character errors
                    safe_id = "gdelt_" + str(hash(row['url']))
                    es.index(index="social_posts", id=safe_id, document=doc)
                    
                    count += 1
                except Exception as e:
                    errors += 1
                    print(f"[GDELT] Error processing single record: {e}")
                    continue
                    
        except Exception as e:
            errors += 1
            print(f"[GDELT] Search error for keyword '{kw}': {e}")
            time.sleep(5)
            continue
            
    print(f"[GDELT] Harvest complete! Successfully written to ES: {count}, Errors: {errors}")
    
    # Return HTTP 200 status code for Fission K8s environment
    if start_response:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [f"gdelt done: {count}".encode()]

if __name__ == "__main__":
    # Override configuration for local testing environment
    os.environ["ES_HOST"] = "https://localhost:9200" # ES address for local testing
    harvest()
