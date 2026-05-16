# COMP90024 - Cluster and Cloud Computing
## Assignment 2: Big Data Analytics on the Cloud
### Team 68

| Name | Student ID |
|---|---|
| Lixin Zhong |1728613 |
| Yutao Fan  |1810828 |
| Kuiyuan Shu |1345012 |
| Yueting Duan |1736334 |
| Yunxiao Gao |1718413 |

**GitLab:** https://gitlab.unimelb.edu.au/lixinzhong/comp90024_team_68 \
**Demonstration video:**

---

## Project Overview

This project analyses Australian public opinion on three global crisis topics — **War**, **Tariff**, and **Oil** — by harvesting and analysing data from multiple social media platforms and official data sources deployed on the NeCTAR Research Cloud.

**Data Sources:**
- Mastodon (`mastodon.au` — Australian server)
- BlueSky (keywords: "Australia war", "tariff Australia", "oil Australia")
- Reddit (`r/australia`, `r/AusPolitics`, `r/AusFinance`, `r/melbourne`)
- GDELT (Global news CSV files, filtered for Australia-related events)
- FuelWatch WA (Western Australian Government official fuel price data)
- NSW Fuel Check (New South Wales Government official fuel price data)

**Three Scenarios:** 
- **Scenario A:** Sentiment trends comparison across Mastodon, BlueSky, and Reddit on War/Tariff/Oil topics
- **Scenario B:** Discussion intensity, trend dynamics, and platform-specific dissemination patterns of different topics (war, tariffs, and oil prices) on social media
- **Scenario C:** Australian fuel prices across WA and NSW vs social media sentiment on oil topics

---

## System Architecture

```
Social Media APIs              K8s Cluster (NeCTAR Research Cloud)
─────────────────             ──────────────────────────────────────────
Mastodon       ──→              Fission Harvesters
BlueSky        ──→                    ↓
Reddit         ──→              Redis Queue
GDELT CSV      ──→                    ↓
FuelWatch WA   ──→              social-consumer / fuel-consumer
NSW Fuel Check ──→                    ↓
                                ElasticSearch
                                      ↓
                                RESTful API (Fission)
                                      ↓
                                Jupyter Notebook (Frontend)
```

---

## Installation

> Note: The following assumes a Kubernetes cluster, Fission, ElasticSearch and Redis are already set up as per the workshop instructions.

### Step 1: Connect to the cluster

```bash
source unimelb-comp90024-2026-68-openrc.sh
```

### Step 2: Create K8s Secrets

```bash
# Harvester secrets (Mastodon token, BlueSky password, ES password)
kubectl create secret generic harvester-secrets \
  --from-literal=MASTODON_TOKEN=<your_mastodon_token> \
  --from-literal=BLUESKY_PASSWORD=<your_bluesky_password> \
  --from-literal=ES_PASS=<your_es_password> \
  -n default

# Fuel secrets (FuelWatch WA / NSW API credentials)
kubectl create secret generic fuel-secrets \
  --from-literal=NSW_API_KEY=<your_nsw_api_key> \
  --from-literal=NSW_API_SECRET=<your_nsw_api_secret> \
  -n default
```

### Step 3: Deploy Fission Functions

```bash
cd backend/harvesters

# Package all harvesters
zip harvester.zip mastodon_harvester.py bluesky_harvester.py \
    reddit_harvester.py gdelt_harvester.py social_consumer.py \
    fuel_harvester.py fuel_consumer.py build.sh requirements.txt

fission package create --name harvester-pkg --env python39x \
  --source harvester.zip --buildcmd "./build.sh"

# Create functions
fission fn create --name mastodon-harvester --env python39x \
  --pkg harvester-pkg --entrypoint "mastodon_harvester.harvest" \
  --secret harvester-secrets

fission fn create --name bluesky-harvester --env python39x \
  --pkg harvester-pkg --entrypoint "bluesky_harvester.harvest" \
  --secret harvester-secrets

fission fn create --name reddit-harvester --env python39x \
  --pkg harvester-pkg --entrypoint "reddit_harvester.harvest" \
  --secret harvester-secrets

fission fn create --name gdelt-harvester --env python39x \
  --pkg harvester-pkg --entrypoint "gdelt_harvester.harvest" \
  --secret harvester-secrets

fission fn create --name social-consumer --env python39x \
  --pkg harvester-pkg --entrypoint "social_consumer.consume" \
  --secret harvester-secrets

fission fn create --name fuel-harvester --env python39x \
  --pkg harvester-pkg --entrypoint "fuel_harvester.harvest" \
  --secret fuel-secrets --secret harvester-secrets

fission fn create --name fuel-consumer --env python39x \
  --pkg harvester-pkg --entrypoint "fuel_consumer.consume" \
  --secret harvester-secrets
```

### Step 4: Update an Existing Harvester

To modify and redeploy a harvester (e.g. bluesky):

```bash
cd backend/harvesters

# Repackage
zip bluesky.zip bluesky_harvester.py build.sh requirements.txt

# Delete old function and redeploy
fission fn delete --name bluesky-harvester
fission fn create \
  --name bluesky-harvester \
  --env python39x \
  --src bluesky.zip \
  --entrypoint "bluesky_harvester.harvest" \
  --buildcmd "./build.sh" \
  --secret harvester-secrets

fission fn test --name bluesky-harvester
```

### Step 5: Set Up Scheduled Timers 

```bash
fission timer create --name mastodon-5min \
  --function mastodon-harvester --cron "@every 5m"

fission timer create --name bluesky-5min \
  --function bluesky-harvester --cron "@every 5m"

fission timer create --name reddit-10min \
  --function reddit-harvester --cron "*/10 * * * *"

fission timer create --name gdelt-15min \
  --function gdelt-harvester --cron "*/15 * * * *"

fission timer create --name consumer-20min \
  --function social-consumer --cron "@every 20m"

fission timer create --name fuel-harvester-1day \
  --function fuel-harvester --cron "0 22 * * *"

fission timer create --name fuel-consumer-1h \
  --function fuel-consumer --cron "@hourly"

fission timer create --name vader-sentiment-timer \
  --function vader-sentiment --cron "@every 10m"

fission timer create --name scenario-c-daily-timer \
  --function scenario-c-daily-aggregator --cron "*/20 * * * *"
```

### Step 6: Create RESTful API Routes 丹丹/萧子 需要去看一下 RESTful API 之后涛子帮忙

```bash
fission route create --name scenario-a-sentiment-route \
  --method GET --url /api/scenario-a/sentiment \
  --function scenario-a-sentiment-api

fission route create --name topic-counts-route \
  --method GET --url /api/scenario_b/topic_counts \
  --function topic-counts-api

fission route create --name topic-trends-route \
  --method GET --url /api/scenario_b/topic_trends \
  --function topic-trends-api

fission route create --name topic-sentiment-route \
  --method GET --url /api/scenario_b/topic_sentiment \
  --function topic-sentiment-api

fission route create --name topic-platform-distribution-route \
  --method GET --url /api/scenario_b/topic_platform_distribution \
  --function topic-platform-distribution-api

fission route create --name scenario-c-fuel-sentiment-route \
  --method GET --url /api/scenario_c/fuel_sentiment_data \
  --function scenario-c-fuel-sentiment-api
```

---

## How to Run the Application

### Step 1: Connect to cluster services

```bash
# Connect to ElasticSearch
kubectl port-forward service/elasticsearch-es-http -n elastic 9200:9200 &

# Connect to Kibana (ES user interface)
kubectl port-forward service/kibana-kb-http -n elastic 5601:5601 &

# Connect to Fission Router (for API calls)
kubectl port-forward svc/router -n fission 8888:80 &
```

### Step 2: Verify data collection

```bash
# Check total data count
curl -k 'https://127.0.0.1:9200/social_posts/_count' \
  --user 'elastic:elastic'

# Check data by platform
curl -k 'https://127.0.0.1:9200/social_posts/_search?pretty' \
  --user 'elastic:elastic' \
  -H 'Content-Type: application/json' \
  -d '{"size":0,"aggs":{"by_platform":{"terms":{"field":"platform"}}}}'
```

### Step 3: Access the RESTful APIs   丹丹/萧子

```bash
# Scenario A - Daily sentiment by platform and topic
curl http://localhost:8888/api/scenario-a/sentiment

# Scenario B - Topic post counts
curl http://localhost:8888/api/scenario_b/topic_counts

# Scenario B - Topic trends over time
curl http://localhost:8888/api/scenario_b/topic_trends

# Scenario B - Topic sentiment scores
curl http://localhost:8888/api/scenario_b/topic_sentiment

# Scenario B - Platform distribution per topic
curl http://localhost:8888/api/scenario_b/topic_platform_distribution

# Scenario C - Fuel price vs sentiment
curl http://localhost:8888/api/scenario_c/fuel_sentiment_data

# Scenario C - Filter by fuel type
curl "http://localhost:8888/api/scenario_c/fuel_sentiment_data?fuel_type=u91"
```

### Step 4: Open Jupyter Notebook 涛子

```bash
# Ensure port-forward is running (Step 1)
cd frontend/
jupyter notebook
```

---

## How to Test the System 

### Run Unit Tests

```bash
pip install pytest vaderSentiment requests redis
pytest test/ -v
```

### Test Coverage (9 tests)

| Test | What it tests |
|---|---|
| `test_detect_topic_war` | Reddit harvester correctly identifies war topic |
| `test_detect_topic_tariff` | Reddit harvester correctly identifies tariff topic |
| `test_detect_topic_oil` | Reddit harvester correctly identifies oil topic |
| `test_detect_topic_general` | Unrelated content returns "general" |
| `test_read_secret_fallback` | Secret reading falls back to env variables |
| `test_vader_sentiment` | VADER correctly identifies positive sentiment |
| `test_api_scenario_b_topic_counts` | Scenario B API returns HTTP 200 |
| `test_api_scenario_a_sentiment` | Scenario A API returns HTTP 200 |
| `test_gdelt_topic_detection` | GDELT harvester identifies topics from URLs |

### CI/CD Pipeline

All tests run automatically via GitLab CI/CD on every commit with stages: lint → test → build → deploy.

---

## Codebase Layout

```
comp90024_team_68/
│
├── README.md                                        # This file
├── .gitlab-ci.yml                                   # CI/CD pipeline
├── .gitignore
│
├── backend/
│   ├── harvesters/                                  # Data collection
│   │   ├── README.md                                # Harvester deployment guide
│   │   ├── mastodon_harvester.py                    # Mastodon harvester
│   │   ├── bluesky_harvester.py                     # BlueSky harvester
│   │   ├── reddit_harvester.py                      # Reddit harvester
│   │   ├── gdelt_harvester.py                       # GDELT CSV harvester
│   │   ├── fuel_harvester.py                        # FuelWatch WA harvester
│   │   ├── fuel_consumer.py                         # Fuel data consumer
│   │   ├── fuel_backfill_wa.py                      # WA fuel historical data
│   │   ├── fuel_backfill_nsw.py                     # NSW fuel historical data
│   │   ├── social_consumer.py                       # Social posts consumer
│   │   ├── backfill-wa-job.yaml                     # WA backfill K8s job
│   │   ├── backfill-nsw-job.yaml                    # NSW backfill K8s job
│   │   ├── build.sh                                 # Fission build script
│   │   └── requirements.txt
│   │
│   ├── analyzers/
│   │   ├── scenario_a/                              # Scenario A: Sentiment Analysis
│   │   │   ├── api/
│   │   │   │   └── sentiment_api.py                 # Scenario A REST API endpoint
│   │   │   └── vader_sentiment.py                   # VADER sentiment processing
│   │   │
│   │   ├── scenario_b/                              # Scenario B: Topic Analysis
│   │   │   ├── analytics/
│   │   │   │   ├── topic_counts.py                  # Topic post count analytics
│   │   │   │   ├── topic_platform_distribution.py   # Platform distribution analytics
│   │   │   │   ├── topic_sentiment.py               # Topic sentiment analytics
│   │   │   │   └── topic_trends.py                  # Topic trend analytics
│   │   │   ├── api/
│   │   │   │   ├── topic_counts_api.py              # Topic counts REST API
│   │   │   │   ├── topic_platform_distribution_api.py # Platform distribution REST API
│   │   │   │   ├── topic_sentiment_api.py           # Topic sentiment REST API
│   │   │   │   └── topic_trends_api.py              # Topic trends REST API
│   │   │   ├── SCENARIO_B_API_README.md             # Scenario B API documentation
│   │   │   ├── SCENARIO_B_README.md                 # Scenario B documentation
│   │   │   └── requirements.txt
│   │   │
│   │   └── scenario_c/                              # Scenario C: Fuel Price vs Sentiment
│   │       ├── SCENARIO_C_API_README.md             # Scenario C API documentation
│   │       ├── scenario_c_daily_aggregator.py       # Daily data aggregator
│   │       └── scenario_c_fuel_sentiment_api.py     # Scenario C REST API endpoint
│   │
│   └── deploy/                                      # Deployment scripts
│       ├── deploy_scenario_a_api.sh                 # Scenario A deployment script
│       └── deploy_vader_sentiment.sh                # VADER deployment script
│
├── frontend/                                        # Jupyter Notebook visualisations
│
├── database/
│   ├── README.md                                    # ES connection guide
│   └── mappings/
│       ├── social_posts_mapping.json
│       ├── official_data_mapping.json
│       └── gdelt_news_mapping.json
│
├── test/
│   └── test_harvesters.py                           # Unit and API tests
│
├── data/                                            # Static data files
├── docs/                                            # Report PDF
└── llm/                                             # LLM usage documentation
```

---

## ElasticSearch Indices 

| Index | Description |
|---|---|
| `social_posts` | Social media posts from all platforms (growing) |
| `official_data` | FuelWatch WA fuel price data |
| `scenario_c_daily` | Pre-aggregated daily fuel + sentiment data |

## Fission Functions Summary 对了

| Function | Executor | Schedule | Purpose |
|---|---|---|---|
| mastodon-harvester | poolmgr | every 5min | Harvest Mastodon posts |
| bluesky-harvester | poolmgr | every 5min | Harvest BlueSky posts |
| reddit-harvester | poolmgr | every 10min | Harvest Reddit posts |
| gdelt-harvester | poolmgr | every 15min | Harvest GDELT CSV |
| social-consumer | poolmgr | every 20min | Redis → ES |
| vader-sentiment | poolmgr | every 10min | VADER analysis |
| fuel-harvester | poolmgr | daily 22:00 | FuelWatch WA prices |
| fuel-consumer | poolmgr | hourly | Fuel Redis → ES |
| scenario-c-daily-aggregator | newdeploy | every 20min | Aggregate Scenario C |
| scenario-a-sentiment-api | newdeploy | on demand | Scenario A API |
| topic-counts-api | newdeploy | on demand | Scenario B API |
| topic-trends-api | newdeploy | on demand | Scenario B API |
| topic-sentiment-api | newdeploy | on demand | Scenario B API |
| topic-platform-distribution-api | newdeploy | on demand | Scenario B API |
| scenario-c-fuel-sentiment-api | newdeploy | on demand | Scenario C API |
