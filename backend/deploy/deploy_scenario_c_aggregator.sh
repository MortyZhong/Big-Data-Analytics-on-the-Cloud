#!/bin/bash
# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
# Description:Deploy Scenario C aggregation pipeline to Fission

set -e

echo "Building Scenario C aggregator package..."

rm -rf build/scenario_c_aggregator
rm -f build/scenario_c_aggregator.zip

mkdir -p build/scenario_c_aggregator

cp backend/analyzers/scenario_c/scenario_c_daily_aggregator.py \
  build/scenario_c_aggregator/

python3 -m pip install \
  "elasticsearch==9.0.5" \
  urllib3 \
  -t build/scenario_c_aggregator

cd build/scenario_c_aggregator

zip -r ../scenario_c_aggregator.zip .

cd ../..

echo "Creating or updating Fission package..."

if fission package list | grep -q "^scenario-c-aggregator-package"; then

  fission package update \
    --name scenario-c-aggregator-package \
    --sourcearchive build/scenario_c_aggregator.zip

else

  fission package create \
    --name scenario-c-aggregator-package \
    --env python39x \
    --sourcearchive build/scenario_c_aggregator.zip

fi

echo "Creating or updating aggregator function..."

if fission function list | grep -q "^scenario-c-daily-aggregator"; then

  fission function update \
    --name scenario-c-daily-aggregator \
    --pkgname scenario-c-aggregator-package

else

  fission function create \
    --name scenario-c-daily-aggregator \
    --env python39x \
    --pkgname scenario-c-aggregator-package \
    --entrypoint "scenario_c_daily_aggregator.main" \
    --executortype newdeploy \
    --minscale 1 \
    --fntimeout 300

fi

echo "Creating or replacing timer..."

if fission timer list | grep -q "^scenario-c-daily-timer"; then

  fission timer delete \
    --name scenario-c-daily-timer

fi

fission timer create \
  --name scenario-c-daily-timer \
  --function scenario-c-daily-aggregator \
  --cron "*/20 * * * *"

echo "Testing aggregator..."

fission function test \
  --name scenario-c-daily-aggregator

echo "Scenario C aggregator deployment finished."