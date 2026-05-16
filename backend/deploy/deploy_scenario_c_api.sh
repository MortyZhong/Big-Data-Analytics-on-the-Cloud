#!/bin/bash
# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
# File: deploy_scenario_c_api.sh
# Description:Deploy Scenario C RESTful API to Fission

set -e

echo "Building Scenario C API package..."

# Clean build directory
rm -rf build/scenario_c_api
rm -f build/scenario_c_api.zip

mkdir -p build/scenario_c_api


# Copy Scenario B source code
cp backend/analyzers/scenario_c/scenario_c_fuel_sentiment_api.py \
  build/scenario_c_api/

  
# Install dependencies
echo "Installing dependencies..."

python3 -m pip install \
  "elasticsearch==9.0.5" \
  urllib3 \
  -t build/scenario_c_api

cd build/scenario_c_api

zip -r ../scenario_c_api.zip .

cd ../..

echo "Creating or updating Fission package..."

if fission package list | grep -q "^scenario-c-api-package"; then

  fission package update \
    --name scenario-c-api-package \
    --sourcearchive build/scenario_c_api.zip

else

  fission package create \
    --name scenario-c-api-package \
    --env python39x \
    --sourcearchive build/scenario_c_api.zip

fi

echo "Creating or updating API function..."

if fission function list | grep -q "^scenario-c-fuel-sentiment-api"; then

  fission function update \
    --name scenario-c-fuel-sentiment-api \
    --pkgname scenario-c-api-package

else

  fission function create \
    --name scenario-c-fuel-sentiment-api \
    --env python39x \
    --pkgname scenario-c-api-package \
    --entrypoint "scenario_c_fuel_sentiment_api.main" \
    --executortype newdeploy \
    --minscale 1 \
    --fntimeout 60

fi

echo "Creating or replacing route..."

if fission route list | grep -q "scenario-c-fuel-sentiment-route"; then

  fission route delete \
    --name scenario-c-fuel-sentiment-route

fi

fission route create \
  --name scenario-c-fuel-sentiment-route \
  --function scenario-c-fuel-sentiment-api \
  --url /api/scenario_c/fuel_sentiment_data \
  --method GET

echo "Testing API..."

fission function test \
  --name scenario-c-fuel-sentiment-api

echo "Scenario C API deployment finished."

echo "Local test:"
echo "kubectl port-forward svc/router 8888:80 -n fission"
echo 'curl "http://localhost:8888/api/scenario_c/fuel_sentiment_data"'