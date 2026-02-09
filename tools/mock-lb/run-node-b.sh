#!/bin/bash
# Run Node B on the VM. Peer = Node A (Mac). Mac is usually 192.168.64.1 from Multipass.
# Prereqs: docker, mock-lb image, vllm-sr image (build on Mac and transfer, or build in VM).
#
# Usage: export PEER_IP=192.168.64.1 && ./run-node-b.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "${PEER_IP}" ]; then
  echo "Error: PEER_IP not set. Set the Mac's IP (Multipass: usually 192.168.64.1)."
  echo "  export PEER_IP=192.168.64.1"
  echo "  ./run-node-b.sh"
  exit 1
fi

cleanup() {
  echo "Stopping Node B containers..."
  docker stop envoy-b extproc-b vllm-sr-b mock-target qwen-b tinyllama-b 2>/dev/null || true
  docker network rm envoy-net 2>/dev/null || true
}
trap cleanup EXIT

echo "Creating network..."
docker network create envoy-net 2>/dev/null || true

echo "Building mock-lb..."
docker build -t mock-lb -q .

echo "Starting Node B backends (mock Qwen, TinyLlama, default target)..."
docker run --rm --name qwen-b       -d --network envoy-net mock-lb -target -target-port 8002 -target-name qwen-b
docker run --rm --name tinyllama-b  -d --network envoy-net mock-lb -target -target-port 8003 -target-name tinyllama-b
docker run --rm --name mock-target  -d --network envoy-net mock-lb -target -target-port 8888 -target-name default-b

echo "Starting vLLM-SR (ExtProc 1)..."
docker run --rm --name vllm-sr-b -d \
  --network envoy-net \
  -v envoy-models-b:/app/models \
  -v "$(pwd)/config-b.yaml:/app/config.yaml" \
  vllm-sr

echo "Starting Mock-LB ExtProc (ExtProc 2)..."
docker run --rm --name extproc-b -d --network envoy-net mock-lb -port 9001

echo "Generating Envoy config (PEER_IP=$PEER_IP)..."
sed "s/__PEER_IP__/$PEER_IP/g" envoy-b-twohost.yaml > envoy-b.yaml

echo "Starting Envoy B..."
docker run --rm --name envoy-b -d \
  --network envoy-net \
  -v "$(pwd)/envoy-b.yaml:/etc/envoy/envoy.yaml" \
  -p 10001:10001 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml

echo "=================================================="
echo "Node B (VM) is up. Envoy: http://localhost:10001"
echo "Peer (Node A) at $PEER_IP:10000"
echo "Press Ctrl+C to stop."
echo "=================================================="
tail -f /dev/null
