## Only edit harvester, take bluesky for example

## After modifing each harvester
zip bluesky_harvester.zip bluesky_harvester.py build.sh requirements.txt

## Upload to fission, remember to delete the old function

fission fn delete --name bluesky-harvester

fission fn create \\\
  --name bluesky-harvester \\\
  --env python39x \\\
  --src bluesky_harvester.zip \\\
  --entrypoint "bluesky_harvester.harvest" \\\
  --buildcmd "./build.sh" \\\
  --secret harvester-secrets

fission timetrigger create \\\
  --name bluesky-5min \\\
  --function bluesky-harvester \\\
  --cron "@every 5m"

## If free also to delete pkg unused