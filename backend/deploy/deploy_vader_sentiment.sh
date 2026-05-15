#!/bin/bash

# Team: 68
# Name: Yueting Duan
# Student ID: 1736334
# File: deploy_vader_sentiment.sh
# Description: Deploy Scenario A VADER sentiment analyzer to Fission and create timer.

set -e

echo "Building VADER sentiment Fission package..."

rm -rf build/vader_sentiment build/vader_sentiment.zip
mkdir -p build/vader_sentiment

cp backend/analyzers/vader_sentiment.py build/vader_sentiment/

python3 -m pip install \
  "elasticsearch==8.15.1" \
  "elastic-transport>=8,<9" \
  vaderSentiment \
  urllib3 \
  -t build/vader_sentiment

cd build/vader_sentiment
zip -r ../vader_sentiment.zip .
cd ../..

echo "Deploying vader-sentiment function..."

if fission fn list | grep -q "^vader-sentiment"; then
  fission fn update \
    --name vader-sentiment \
    --src build/vader_sentiment.zip \
    --entrypoint "vader_sentiment.main"
else
  fission fn create \
    --name vader-sentiment \
    --env python39x \
    --src build/vader_sentiment.zip \
    --entrypoint "vader_sentiment.main" \
    --secret harvester-secrets \
    --executortype poolmgr \
    --fntimeout 300
fi

echo "Creating or replacing vader-sentiment timer..."

if fission timer list | grep -q "^vader-sentiment-timer"; then
  fission timer delete --name vader-sentiment-timer
fi

fission timer create \
  --name vader-sentiment-timer \
  --function vader-sentiment \
  --cron "@every 20m"

echo "Testing vader-sentiment function..."
fission fn test --name vader-sentiment --timeout=5m

echo "VADER sentiment deployment finished."
