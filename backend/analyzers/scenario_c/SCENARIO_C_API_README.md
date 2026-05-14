````markdown
# Scenario C Backend API Documentation

## Scenario Overview

Scenario C explores the relationship between fuel prices and public sentiment on social media.

Main research question:

> "When fuel prices rise, do Australians become more negative on social media?"

The backend has already completed data aggregation and created a processed Elasticsearch index:

```text
scenario_c_daily
````

This index contains daily aggregated analytics data combining:

* Official Australian fuel price data
* Social media sentiment data related to oil/fuel discussions

---

# Current Dataset

The index currently contains:

* 360 records total
* 4 fuel types:

  * diesel
  * u91
  * u95
  * u98

Each fuel type contains approximately 90 daily records.

---

# Available Fields

Each document in `scenario_c_daily` contains:

| Field               | Description                          |
| ------------------- | ------------------------------------ |
| date                | Date of aggregation                  |
| fuel_type           | Fuel category                        |
| avg_fuel_price      | Average fuel price                   |
| avg_sentiment_score | Average social media sentiment score |
| negative_ratio      | Ratio of negative posts              |
| oil_post_count      | Number of oil-related posts          |
| negative_post_count | Number of negative oil-related posts |

---

# Backend API Design

Unlike Scenario B, Scenario C does NOT hardcode visualization logic inside the backend.

The backend only provides:

* Clean aggregated analytics data
* Optional filtering
* Standardized JSON output

The frontend / Jupyter notebook is responsible for:

* Choosing chart types
* Comparing fuel types
* Correlation analysis
* Storytelling and visualization

This design keeps the API flexible and RESTful.

---

# Main API Endpoint

```text
GET /api/scenario_c/fuel_sentiment_data
```

---

# Optional Query Parameters

## Filter by Fuel Type

Example:

```text
/api/scenario_c/fuel_sentiment_data?fuel_type=u91
```

Supported fuel types:

* diesel
* u91
* u95
* u98

If no fuel_type is provided, the API returns data for ALL fuel types.

---

# Example JSON Response

```json
{
  "status": "success",
  "scenario": "scenario_c",
  "data": [
    {
      "date": "2025-01-01",
      "fuel_type": "u91",
      "avg_fuel_price": 1.82,
      "avg_sentiment_score": -0.14,
      "negative_ratio": 0.37,
      "oil_post_count": 120,
      "negative_post_count": 44
    }
  ]
}
```

---

# Suggested Frontend Visualizations

The frontend/Jupyter notebook may choose to build:

## Overall Trend Analysis

* Fuel price vs sentiment over time
* Fuel price vs negative ratio
* Dual-axis line charts

---

## Fuel Type Comparison

Compare:

* diesel
* u91
* u95
* u98

Possible charts:

* Multi-line charts
* Grouped trend charts
* Correlation plots

---

## Exploratory Analytics

Possible analyses:

* Does higher fuel price correlate with negative sentiment?
* Which fuel type has the strongest sentiment response?
* Which periods contain unusually negative discussions?

---

# Backend Structure

Recommended project structure:

```text
backend/analyzers/scenario_c/

    analytics/
        fuel_sentiment_data.py

    api/
        fuel_sentiment_data_api.py
```

---

# Important Design Notes

## Backend Responsibilities

The backend is responsible for:

* Elasticsearch querying
* Data filtering
* Returning standardized JSON

The backend should NOT:

* Decide chart types
* Hardcode comparison modes
* Hardcode visualization logic

---

## Frontend Responsibilities

The frontend/Jupyter notebook is responsible for:

* Data visualization
* Comparative analysis
* Interactive filtering
* Dashboard storytelling

---

# Deployment Notes

Scenario C will be deployed through:

* Fission Functions
* RESTful API endpoints
* Kubernetes runtime

The deployment workflow follows the same structure as Scenario B.

---

# GitLab Files

Current aggregation script:

```text
backend/analyzers/scenario_c_daily_aggregator.py
```

Upcoming API files:

```text
backend/analyzers/scenario_c/analytics/fuel_sentiment_data.py

backend/analyzers/scenario_c/api/fuel_sentiment_data_api.py
```

```
```
