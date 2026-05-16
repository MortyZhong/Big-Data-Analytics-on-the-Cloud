# test/test_harvesters.py
# Team: 68 | Name: Kuiyuan Shu | Student ID: 1345012

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_detect_topic_war():
    from backend.harvesters.reddit_harvester import detect_topic
    assert detect_topic("Iran war Australia") == "war"

def test_detect_topic_tariff():
    from backend.harvesters.reddit_harvester import detect_topic
    assert detect_topic("tariff trade Australia") == "tariff"

def test_detect_topic_oil():
    from backend.harvesters.reddit_harvester import detect_topic
    assert detect_topic("oil petrol price Australia") == "oil"

def test_detect_topic_general():
    from backend.harvesters.reddit_harvester import detect_topic
    assert detect_topic("hello world") == "general"

def test_read_secret_fallback():
    from backend.harvesters.reddit_harvester import read_secret
    os.environ["TEST_SECRET"] = "test_value"
    assert read_secret("TEST_SECRET") == "test_value"

def test_vader_sentiment():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    score = analyzer.polarity_scores("I love Australia!")["compound"]
    assert score > 0

def test_api_scenario_b_topic_counts():
    """测试场景B topic_counts API"""
    import requests
    try:
        response = requests.get(
            "http://localhost:8888/api/scenario_b/topic_counts",
            timeout=5
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or len(data) > 0
    except requests.exceptions.ConnectionError:
        pass

def test_api_scenario_a_sentiment():
    """测试场景A sentiment API"""
    import requests
    try:
        response = requests.get(
            "http://localhost:8888/api/scenario-a/sentiment",
            timeout=5
        )
        assert response.status_code == 200
    except requests.exceptions.ConnectionError:
        pass

def test_gdelt_topic_detection():
    """测试GDELT话题检测"""
    from backend.harvesters.gdelt_harvester import detect_topic
    assert detect_topic("https://www.abc.net.au/news/oil-prices-rise", "190") == "oil"
    assert detect_topic("https://www.abc.net.au/news/tariff-war-trade", "160") == "tariff"
    assert detect_topic("https://www.abc.net.au/news/military-attack", "180") == "war"
