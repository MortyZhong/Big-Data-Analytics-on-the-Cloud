# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
# File: deploy_scenario_b_api.sh
# Description:Deploy Scenario B APIs to Fission

set -e

echo "Deploying Scenario B APIs to Fission..."

# Clean build directory

rm -rf build/scenario_b_api
rm -f build/scenario_b_api.zip

mkdir -p build/scenario_b_api

# Copy Scenario B source code

cp -r backend/analyzers/scenario_b/* build/scenario_b_api/

# Install dependencies

echo "Installing dependencies..."

python3 -m pip install \
  elasticsearch==9.0.5 \
  urllib3==2.2.3 \
  -t build/scenario_b_api

# Build zip package

echo "Creating zip package..."

cd build/scenario_b_api

zip -r ../scenario_b_api.zip .

cd ../..

# Create or update package

echo "Deploying Fission package..."

if fission package list | grep -q "^scenario-b-package"; then

  echo "Updating existing package..."

  fission package update \
    --name scenario-b-package \
    --sourcearchive build/scenario_b_api.zip

else

  echo "Creating new package..."

  fission package create \
    --name scenario-b-package \
    --env python39x \
    --sourcearchive build/scenario_b_api.zip

fi

# Function deployment helper

deploy_function () {

  FUNCTION_NAME=$1
  ENTRYPOINT=$2
  ROUTE_NAME=$3
  ROUTE_URL=$4

  echo "---------------------------------------"
  echo "Deploying function: $FUNCTION_NAME"
  echo "---------------------------------------"

  if fission function list | grep -q "^$FUNCTION_NAME"; then

    echo "Updating existing function..."

    fission function update \
      --name $FUNCTION_NAME \
      --pkgname scenario-b-package \
      --entrypoint $ENTRYPOINT

  else

    echo "Creating new function..."

    fission function create \
      --name $FUNCTION_NAME \
      --env python39x \
      --pkgname scenario-b-package \
      --entrypoint $ENTRYPOINT \
      --executortype newdeploy \
      --minscale 1

  fi

  echo "Creating route..."

  if fission route list | grep -q "$ROUTE_NAME"; then
    fission route delete --name $ROUTE_NAME
  fi

  fission route create \
    --name $ROUTE_NAME \
    --function $FUNCTION_NAME \
    --url $ROUTE_URL \
    --method GET

}

# Deploy all Scenario B APIs
deploy_function \
  "topic-counts-api" \
  "scenario_b.api.topic_counts_api.main" \
  "topic-counts-route" \
  "/api/scenario_b/topic_counts"

deploy_function \
  "topic-trends-api" \
  "scenario_b.api.topic_trends_api.main" \
  "topic-trends-route" \
  "/api/scenario_b/topic_trends"

deploy_function \
  "topic-sentiment-api" \
  "scenario_b.api.topic_sentiment_api.main" \
  "topic-sentiment-route" \
  "/api/scenario_b/topic_sentiment"

deploy_function \
  "topic-platform-distribution-api" \
  "scenario_b.api.topic_platform_distribution_api.main" \
  "topic-platform-distribution-route" \
  "/api/scenario_b/topic_platform_distribution"

deploy_function \
  "posts-query-api" \
  "scenario_b.api.posts_query_api.main" \
  "posts-query-route" \
  "/api/scenario_b/posts"

# Test APIs
echo "Testing APIs..."

fission fn test --name topic-counts-api
fission fn test --name topic-trends-api
fission fn test --name topic-sentiment-api
fission fn test --name topic-platform-distribution-api
#fission fn test --name posts-query-api

# Done
echo "Scenario B deployment complete!"

echo ""
echo "To access APIs locally:"
echo "kubectl port-forward -n fission svc/router 8888:80"
echo ""
echo "Example:"
echo "curl http://localhost:8888/api/scenario_b/topic_counts"