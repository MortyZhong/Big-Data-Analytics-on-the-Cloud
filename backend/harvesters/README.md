## Getting started

 zip bluesky_harvester.zip bluesky_harvester.py build.sh requirements.txt

fission fn create \\\
  --name bluesky-harvester \\\
  --env python39x \\\
  --src bluesky_harvester.zip \\\
  --entrypoint "bluesky_harvester.harvest" \\\
  --buildcmd "./build.sh" \\\
  --secret harvester-secrets

