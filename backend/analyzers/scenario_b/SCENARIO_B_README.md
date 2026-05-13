# Scenario B RESTful API Usage

## Overview

Scenario B analytics APIs expose ElasticSearch analytics results through RESTful endpoints.

These APIs are intended for:

* Jupyter Notebook visualization
* frontend chart rendering
* trend analysis

All APIs return structured JSON data.

---

# Architecture

```text
ElasticSearch
↓
analytics/scenario_b/
↓
api/scenario_b/
↓
Fission REST API
↓
Jupyter Notebook / Frontend
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

# Example API Endpoints

## Topic Counts

```text
GET /api/scenario_b/topic_counts
```

---

## Topic Trends

```text
GET /api/scenario_b/topic_trends
```

---

## Topic Sentiment

```text
GET /api/scenario_b/topic_sentiment
```

---

## Platform Topic Distribution

```text
GET /api/scenario_b/platform_topic_distribution
```

---

# Example Usage in Jupyter Notebook

## 1. Import requests

```python
import requests
```

---

## 2. Call API

```python
response = requests.get(
    "http://<API_URL>/api/scenario_b/topic_counts"
)

data = response.json()
```

---

## 3. Access Data

```python
data["data"]
```

---

# Expected JSON Structure

## Example

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

# Visualization Suggestions

| API                         | Suggested Visualization    |
| --------------------------- | -------------------------- |
| topic_counts                | bar chart                  |
| topic_trends                | line chart                 |
| topic_sentiment             | sentiment comparison chart |
| platform_topic_distribution | grouped/stacked bar chart  |

---

# Notes

* APIs already filter topics to:

  * war
  * tariff
  * oil

* Topic `general` is excluded.

* Data is read dynamically from ElasticSearch.

* APIs should be deployed through Fission using RESTful routes.
