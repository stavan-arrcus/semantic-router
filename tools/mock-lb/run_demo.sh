#!/bin/bash

# Kill background jobs on exit
cleanup() {
  echo "Stopping containers and processes..."
  docker stop envoy-a envoy-b extproc-a extproc-b vllm-sr-a vllm-sr-b qwen-a tinyllama-a qwen-b tinyllama-b 2>/dev/null
  docker network rm envoy-net 2>/dev/null
}
trap cleanup EXIT

# 1. Create Network
echo "Creating Network..."
docker network create envoy-net 2>/dev/null || true

# 2. Build Tools
echo "Building Mock LB..."
docker build -t mock-lb .

# Note: vLLM-SR should be built separately: 
# docker build -t vllm-sr -f ../../src/vllm-sr/Dockerfile ../../

# 3. Start Infrastructure

# --- NODE A (Primary) ---
echo "Starting Node A Backends..."
# Qwen A (Port 8000)
docker run --rm --name qwen-a -d --network envoy-net mock-lb -target -target-port 8000
# TinyLlama A (Port 8001)
docker run --rm --name tinyllama-a -d --network envoy-net mock-lb -target -target-port 8001

echo "Starting Node A Infrastructure..."
# vLLM-SR (Router)
docker run --rm --name vllm-sr-a -d \
  --network envoy-net \
  -v envoy-models-a:/app/models \
  -v $(pwd)/config-a.yaml:/app/config.yaml \
  vllm-sr
# Mock-LB (Load Balancer)
docker run --rm --name extproc-a -d --network envoy-net mock-lb -port 9000
# Envoy
docker run --rm --name envoy-a -d \
  --network envoy-net \
  -v $(pwd)/envoy-a.yaml:/etc/envoy/envoy.yaml \
  -p 10000:10000 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml


# --- NODE B (Peer/Failover) ---
echo "Starting Node B Backends..."
# Qwen B (Port 8002)
docker run --rm --name qwen-b -d --network envoy-net mock-lb -target -target-port 8002
# TinyLlama B (Port 8003)
docker run --rm --name tinyllama-b -d --network envoy-net mock-lb -target -target-port 8003

echo "Starting Node B Infrastructure..."
# vLLM-SR (Router)
docker run --rm --name vllm-sr-b -d \
  --network envoy-net \
  -v envoy-models-b:/app/models \
  -v $(pwd)/config-b.yaml:/app/config.yaml \
  vllm-sr
# Mock-LB (Load Balancer)
docker run --rm --name extproc-b -d --network envoy-net mock-lb -port 9001
# Envoy
docker run --rm --name envoy-b -d \
  --network envoy-net \
  -v $(pwd)/envoy-b.yaml:/etc/envoy/envoy.yaml \
  -p 10001:10001 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml

echo "=================================================="
echo "DEMO STARTED."
echo "Envoy A Loop: localhost:10000 (Primary)"
echo "Envoy B Loop: localhost:10001 (Peer)"

# Keep script alive so containers stay up
tail -f /dev/null
