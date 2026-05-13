# Scenario B RESTful API Usage

## Overview

Scenario B analytics APIs expose ElasticSearch analytics results through RESTful endpoints deployed with Fission.

These APIs are intended for:

* Jupyter Notebook visualization
* frontend chart rendering
* trend analysis
* dashboard development

All APIs return structured JSON data.

---

# Architecture

```text
ElasticSearch
↓
scenario_b/analytics/
↓
scenario_b/api/
↓
Fission Functions
↓
Fission Router
↓
Jupyter Notebook / Frontend
```

---

# Important Notes

These APIs are NOT direct ElasticSearch queries.

Frontend/Jupyter should call the Fission REST APIs instead of accessing ElasticSearch (`:9200`) directly.

Correct workflow:

```text
Jupyter / Frontend
↓
Fission REST API
↓
ElasticSearch
```

NOT:

```text
Jupyter
↓
ElasticSearch directly
```

---

# Start API Access (Required)

Before using the APIs, start Fission router forwarding:

```bash
kubectl port-forward -n fission svc/router 8888:80
```

After this, all APIs become available at:

```text
http://localhost:8888
```

---

# Available APIs

| API                                | Purpose                             |
| ---------------------------------- | ----------------------------------- |
| topic_counts_api.py                | Total counts for war/tariff/oil     |
| topic_trends_api.py                | Weekly topic trends                 |
| topic_sentiment_api.py             | Average sentiment by topic          |
| platform_topic_distribution_api.py | Topic distribution across platforms |

---

# REST API Endpoints

## Topic Counts

```text
GET http://localhost:8888/api/scenario_b/topic_counts
```

Returns:

* total number of posts for:
  * war
  * tariff
  * oil

Recommended charts:

* bar chart
* pie chart

---

## Topic Trends

```text
GET http://localhost:8888/api/scenario_b/topic_trends
```

Returns:

* weekly topic counts over time

Recommended charts:

* line chart
* stacked area chart

---

## Topic Sentiment

```text
GET http://localhost:8888/api/scenario_b/topic_sentiment
```

Returns:

* average sentiment score per topic

Recommended charts:

* sentiment comparison chart
* diverging bar chart

---

## Platform Topic Distribution

```text
GET http://localhost:8888/api/scenario_b/platform_topic_distribution
```

Returns:

* topic distribution for each platform

Recommended charts:

* grouped bar chart
* stacked bar chart

---

# Example Usage in Jupyter Notebook

## 1. Import libraries

```python
import requests
import pandas as pd
```

---

## 2. Call API

```python
url = "http://localhost:8888/api/scenario_b/topic_counts"

response = requests.get(url)

data = response.json()
```

---

## 3. Convert to DataFrame

```python
df = pd.DataFrame(data["data"])

df.head()
```

---

## 4. Example Visualization

```python
import matplotlib.pyplot as plt

df.plot(
    x="topic",
    y="count",
    kind="bar"
)

plt.title("Topic Counts")
plt.show()
```

---

# Example curl Usage

## Topic Counts

```bash
curl http://localhost:8888/api/scenario_b/topic_counts
```

---

## Topic Trends

```bash
curl http://localhost:8888/api/scenario_b/topic_trends
```

---

## Topic Sentiment

```bash
curl http://localhost:8888/api/scenario_b/topic_sentiment
```

---

## Platform Topic Distribution

```bash
curl http://localhost:8888/api/scenario_b/platform_topic_distribution
```

---

# Expected JSON Structure

## topic_counts Example

```json
{
  "status": "success",
  "scenario": "scenario_b",
  "metric": "topic_counts",
  "data": [
    {
      "topic": "war",
      "count": 1200
    }
  ]
}
```

---

## topic_trends Example

```json
{
  "status": "success",
  "scenario": "scenario_b",
  "metric": "topic_trends",
  "interval": "week",
  "data": [
    {
      "date": "2025-05-01T00:00:00.000Z",
      "topics": {
        "war": 120,
        "oil": 95,
        "tariff": 40
      }
    }
  ]
}
```

---

# Visualization Suggestions

| API                         | Suggested Visualization    |
| --------------------------- | -------------------------- |
| topic_counts                | bar chart                  |
| topic_trends                | line chart                 |
| topic_sentiment             | sentiment comparison chart |
| platform_topic_distribution | grouped/stacked bar chart  |

---

# Data Notes

* APIs automatically filter topics to:

  * war
  * tariff
  * oil

* Topic `general` is excluded.

* Aggregations are computed dynamically from ElasticSearch.

* Topic trends use weekly aggregation (`calendar_interval = week`).

---

# Deployment Notes

Scenario B APIs are deployed as Fission Functions using:

* Python39x environment
* newdeploy executor
* RESTful routes

Dependencies are bundled directly into the deployment package using:

```bash
pip install -r requirements.txt -t .
```

This avoids dependency installation issues during Fission package builds.