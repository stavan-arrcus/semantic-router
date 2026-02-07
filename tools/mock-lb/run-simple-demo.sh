#!/bin/bash
# Local 1-ExtProc demo: 2 Envoy + 2 Mock-LB. Inputs: qwen / llama (via x-selected-model). Every 4th request reroutes to the other Envoy.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

cleanup() {
  echo "Stopping containers..."
  docker stop envoy-a envoy-b extproc-a extproc-b qwen-a llama-a qwen-b llama-b 2>/dev/null || true
  docker network rm simple-envoy-net 2>/dev/null || true
}
trap cleanup EXIT

echo "Creating network..."
docker network create simple-envoy-net 2>/dev/null || true

echo "Building mock-lb..."
docker build -t mock-lb -q .

echo "Starting mock backends (qwen-a, llama-a, qwen-b, llama-b)..."
docker run --rm --name qwen-a  -d --network simple-envoy-net mock-lb -target -target-port 8000 -target-name qwen-a
docker run --rm --name llama-a -d --network simple-envoy-net mock-lb -target -target-port 8001 -target-name llama-a
docker run --rm --name qwen-b  -d --network simple-envoy-net mock-lb -target -target-port 8002 -target-name qwen-b
docker run --rm --name llama-b -d --network simple-envoy-net mock-lb -target -target-port 8003 -target-name llama-b

echo "Starting Mock-LB ExtProcs (every 4th request reroutes)..."
docker run --rm --name extproc-a -d --network simple-envoy-net mock-lb -port 9000
docker run --rm --name extproc-b -d --network simple-envoy-net mock-lb -port 9001

echo "Starting Envoy A and B..."
docker run --rm --name envoy-a -d \
  --network simple-envoy-net \
  -v "$(pwd)/envoy-simple-a.yaml:/etc/envoy/envoy.yaml" \
  -p 10000:10000 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml

docker run --rm --name envoy-b -d \
  --network simple-envoy-net \
  -v "$(pwd)/envoy-simple-b.yaml:/etc/envoy/envoy.yaml" \
  -p 10001:10001 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml

echo "=================================================="
echo "Simple demo up. No vLLM-SR; 1 ExtProc per Envoy."
echo "  Envoy A: http://localhost:10000"
echo "  Envoy B: http://localhost:10001"
echo "  Send x-selected-model: qwen or x-selected-model: llama"
echo "  Every 4th request (per model) reroutes to the other Envoy."
echo "  Example:"
echo "    curl -s -w '%%{http_code}' http://localhost:10000/ -H 'x-selected-model: qwen'"
echo "    (run 4 times; 4th goes to Envoy B)"
echo "=================================================="
tail -f /dev/null
