## Getting started

fission fn create \
  --name bluesky-harvester \
  --env python39x \
  --src bluesky.zip \
  --entrypoint "bluesky_harvester.harvest" \
  --buildcmd "./build.sh"


fission fn get --name bluesky-harvester -o yaml > fn.yaml


kubectl apply -f fn.yaml