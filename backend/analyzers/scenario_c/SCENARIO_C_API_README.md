# Scenario C API Usage Guide


# Scenario C — Fuel Price vs Social Media Sentiment API

## Scenario Goal

This scenario explores the relationship between Australian fuel prices and public sentiment on social media.

Main question:

> "When fuel prices rise, do social media sentiments become more negative?"

The backend provides aggregated daily analytics data through a RESTful API.



# Data Source

The API reads from the Elasticsearch index:

```text
scenario_c_daily
````

The index contains pre-aggregated daily records combining:

* Official Australian fuel price data
* Social media sentiment data related to oil/fuel topics

---

# API Endpoint

## Main Endpoint

```text
GET /api/scenario_c/fuel_sentiment_data
```

Example:

```text
http://localhost:8888/api/scenario_c/fuel_sentiment_data
```

---

# Optional Query Parameters

## Filter by Fuel Type

Example:

```text
/api/scenario_c/fuel_sentiment_data?fuel_type=u91
```

Supported values:

* diesel
* u91
* u95
* u98

If no `fuel_type` is provided, the API returns all fuel types.

---

# Response Format

Example response:

```json
{
  "status": "success",
  "scenario": "scenario_c",
  "data": [
    {
      "date": "2024-01-01",
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

# Field Descriptions

| Field               | Description                                           |
| ------------------- | ----------------------------------------------------- |
| date                | Aggregated daily date                                 |
| fuel_type           | Fuel category                                         |
| avg_fuel_price      | Average daily fuel price                              |
| avg_sentiment_score | Average sentiment score from oil-related social posts |
| negative_ratio      | Ratio of negative posts                               |
| oil_post_count      | Total number of oil-related posts                     |
| negative_post_count | Number of negative oil-related posts                  |

---

# Recommended Frontend Visualizations

The backend intentionally provides flexible aggregated data instead of hardcoded chart logic.

Frontend/Jupyter visualization is responsible for deciding:

* what metrics to compare
* which charts to use
* how to explore the data

Recommended visualizations include:

---

## 1. Fuel Price vs Sentiment Trend

Suggested chart:

* Dual-axis line chart

Possible dimensions:

* avg_fuel_price
* avg_sentiment_score
* negative_ratio

---

## 2. Fuel Type Comparison

Suggested chart:

* Multi-line chart

Compare:

* u91
* u95
* u98
* diesel

Possible metrics:

* avg_fuel_price
* avg_sentiment_score
* negative_ratio

---

## 3. Correlation Analysis

Suggested chart:

* Scatter plot

Possible analysis:

* fuel price vs sentiment score
* fuel price vs negative ratio

---

# Design Philosophy

The backend exposes standardized analytics data through RESTful APIs.

Visualization and exploratory analysis are intentionally delegated to the frontend/Jupyter layer to support:

* flexible storytelling
* exploratory analytics
* interactive dashboard design

The API therefore focuses on:

* clean aggregated data
* filtering support
* consistent JSON structure

rather than fixed visualization logic.

---

# Notes for Frontend Developers

* All data is already aggregated daily.
* No additional backend aggregation is required.
* Frontend can freely group/filter data.
* Fuel type filtering can be done either:

  * in the API (`?fuel_type=u91`)
  * or directly in frontend logic after loading all data.

---

```
```
