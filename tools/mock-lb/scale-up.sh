#!/bin/bash
# Scalable Launcher for vLLM Semantic Router
# Usage: ./scale-up.sh <node_id> <peer_address>
# Example: ./scale-up.sh a 192.168.64.4,192.168.64.8

if [ "$#" -ne 2 ]; then
    echo "Usage: ./scale-up.sh <node_id> <peer_address>"
    echo "Example: ./scale-up.sh a 192.168.64.4,192.168.64.8"
    exit 1
fi

NODE_ID=$1
PEER_LIST=$2

echo "Scaling up Node $NODE_ID (Peers: $PEER_LIST)..."

# Generate Envoy lb_endpoints YAML block (Standardized to port 10000)
PEER_ENDPOINTS=""
IFS=',' read -ra PEERS <<< "$PEER_LIST"
for PEER in "${PEERS[@]}"; do
    PEER_ENDPOINTS="${PEER_ENDPOINTS}              - endpoint:\n                  address:\n                    socket_address: { address: $PEER, port_value: 10000 }\n"
done

# Ensure we have a config file for this node
if [ ! -f "config-$NODE_ID.yaml" ]; then
    echo "Creating default config for Node $NODE_ID..."
    cp config-a.yaml "config-$NODE_ID.yaml"
fi

# Pre-process Envoy config using Python (since envsubst is often missing on Mac)
export PEER_ENDPOINTS_VAL=$(printf "$PEER_ENDPOINTS")
python3 -c "
import os
import sys
content = sys.stdin.read()
# Replace \${PEER_ENDPOINTS} with the environment variable value
print(content.replace('\${PEER_ENDPOINTS}', os.environ.get('PEER_ENDPOINTS_VAL', '')))
" < envoy-template.yaml > "envoy-$NODE_ID.yaml"

# Launch using Docker Compose
# Standardized to use internal 10000/8080 mapped to host 10000/8080
NODE_ID=$NODE_ID \
ENVOY_CONFIG="envoy-$NODE_ID.yaml" \
docker compose -p "router-node-$NODE_ID" -f docker-compose.node.yaml up -d --build

echo "Node $NODE_ID is running at http://localhost:10000"
