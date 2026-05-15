#!/bin/bash

# Team: 68
# Name: Yueting Duan
# Student ID: 1736334
# File: deploy_scenario_a_api.sh
# Description: Deploy Scenario A sentiment RESTful API to Fission and create route.

set -e

echo "Building Scenario A sentiment API Fission package..."

rm -rf build/scenario_a_sentiment_api build/scenario_a_sentiment_api.zip
mkdir -p build/scenario_a_sentiment_api

cp backend/analyzers/scenario_a/api/sentiment_api.py build/scenario_a_sentiment_api/

python3 -m pip install \
  "elasticsearch==8.15.1" \
  "elastic-transport>=8,<9" \
  urllib3 \
  -t build/scenario_a_sentiment_api

cd build/scenario_a_sentiment_api
zip -r ../scenario_a_sentiment_api.zip .
cd ../..

echo "Deploying scenario-a-sentiment-api function..."

if fission fn list | grep -q "^scenario-a-sentiment-api"; then
  fission fn update \
    --name scenario-a-sentiment-api \
    --src build/scenario_a_sentiment_api.zip \
    --entrypoint "sentiment_api.main"
else
  fission fn create \
    --name scenario-a-sentiment-api \
    --env python39x \
    --src build/scenario_a_sentiment_api.zip \
    --entrypoint "sentiment_api.main" \
    --executortype newdeploy \
    --fntimeout 60
fi

echo "Creating or replacing route..."

if fission route list | grep -q "scenario-a-sentiment-route"; then
  fission route delete --name scenario-a-sentiment-route
fi

fission route create \
  --name scenario-a-sentiment-route \
  --function scenario-a-sentiment-api \
  --url /api/scenario-a/sentiment \
  --method GET

echo "Testing scenario-a-sentiment-api function..."
fission fn test --name scenario-a-sentiment-api

echo "Scenario A API deployment finished."
echo "Local test:"
echo "kubectl port-forward svc/router 8888:80 -n fission"
echo "curl http://localhost:8888/api/scenario-a/sentiment"
