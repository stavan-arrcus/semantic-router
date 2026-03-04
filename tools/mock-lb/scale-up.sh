#!/bin/bash
# Scalable Launcher for vLLM Semantic Router
# Usage: ./scale-up.sh <node_id> <host_port> <health_port> <peer_address>
# Example: ./scale-up.sh a 10000 8080 192.168.64.3

if [ "$#" -ne 4 ]; then
    echo "Usage: ./scale-up.sh <node_id> <host_port> <health_port> <peer_address>"
    echo "Example: ./scale-up.sh a 10000 8080 192.168.64.3"
    exit 1
fi

NODE_ID=$1
HOST_PORT=$2
HEALTH_PORT=$3
PEER_LIST=$4

echo "Scaling up Node $NODE_ID on port $HOST_PORT (Health: $HEALTH_PORT, Peers: $PEER_LIST)..."

# Generate Envoy lb_endpoints YAML block
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
NODE_ID=$NODE_ID \
HOST_PORT=$HOST_PORT \
HEALTH_PORT=$HEALTH_PORT \
ENVOY_CONFIG="envoy-$NODE_ID.yaml" \
docker compose -p "router-node-$NODE_ID" -f docker-compose.node.yaml up -d --build

echo "Node $NODE_ID is running at http://localhost:$HOST_PORT"
