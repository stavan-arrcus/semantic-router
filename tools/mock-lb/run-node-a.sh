#!/bin/bash
# Run Node A on the Mac. Peer = Node B (VM).
# Prereqs: docker, mock-lb image, vllm-sr image.
# Build vLLM-SR (once): docker build -t vllm-sr -f ../../src/vllm-sr/Dockerfile ../..
#
# Usage: export PEER_IP=<VM_IP> && ./run-node-a.sh
# Get VM_IP: multipass list

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "${PEER_IP}" ]; then
  echo "Error: PEER_IP not set. Set the VM's IP (e.g. from 'multipass list')."
  echo "  export PEER_IP=192.168.64.3"
  echo "  ./run-node-a.sh"
  exit 1
fi

cleanup() {
  echo "Stopping Node A containers..."
  docker stop envoy-a extproc-a vllm-sr-a mock-target qwen-a tinyllama-a 2>/dev/null || true
  docker network rm envoy-net 2>/dev/null || true
}
trap cleanup EXIT

echo "Creating network..."
docker network create envoy-net 2>/dev/null || true

echo "Building mock-lb..."
docker build -t mock-lb -q .

echo "Starting Node A default target..."
docker run --rm --name mock-target  -d --network envoy-net mock-lb -target -target-port 8888 -target-name default-a

echo "Starting Qwen Mock Target..."
docker run --rm --name qwen-a -d --network envoy-net mock-lb -target -target-port 8000 -target-name qwen-a

echo "Starting TinyLlama Mock Target..."
docker run --rm --name tinyllama-a -d --network envoy-net mock-lb -target -target-port 8001 -target-name tinyllama-a

echo "Starting vLLM-SR (ExtProc 1)..."
docker run --rm --name vllm-sr-a -d \
  --network envoy-net \
  --add-host=host.docker.internal:host-gateway \
  -v envoy-models-a:/app/models \
  -v "$(pwd)/config-a.yaml:/app/config.yaml" \
  vllm-sr

echo "Starting Mock-LB ExtProc (ExtProc 2)..."
docker run --rm --name extproc-a -d --network envoy-net mock-lb -port 9000

echo "Generating Envoy config (PEER_IP=$PEER_IP)..."
sed "s/__PEER_IP__/$PEER_IP/g" envoy-a-twohost.yaml > envoy-a.yaml

echo "Starting Envoy A..."
docker run --rm --name envoy-a -d \
  --network envoy-net \
  --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)/envoy-a.yaml:/etc/envoy/envoy.yaml" \
  -p 10000:10000 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml

echo "=================================================="
echo "Node A (Mac) is up. Envoy: http://localhost:10000"
echo "Peer (Node B) at $PEER_IP:10001"
echo "Press Ctrl+C to stop."
echo "=================================================="
tail -f /dev/null
