## Get access to elastic search

## (1) connect to cluster
source unimelb-comp90024-2026-68-openrc.sh

## (2) To access elastic search database locally
kubectl port-forward service/elasticsearch-es-http -n elastic 9200:9200 \
# Then

## (3) To access Kibana (ES user interface) locally
kubectl port-forward service/kibana-kb-http  -n elastic 5601:5601

