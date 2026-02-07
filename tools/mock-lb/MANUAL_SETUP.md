# Manual Setup Guide: Dual Envoy + vLLM-SR Integration

This guide walks you through manually starting the complete dual-node Envoy setup with semantic routing and load balancing.

## Prerequisites

- Docker installed with network support
- `vllm-sr` Docker image built: `docker build -t vllm-sr -f ../../src/vllm-sr/Dockerfile ../../`
- For real models: NVIDIA Docker runtime (optional, can use CPU mode)

## Quick Start

### Step 1: Create Network
```bash
docker network create envoy-net
```

### Step 2: Build Mock LB
```bash
cd /Users/stavandarshanjani/semantic-router/tools/mock-lb
docker build -t mock-lb .
```

---

## Option A: Mock Model Setup (Fast, No GPU Required)

### Step 3A: Start vLLM-SR Instances (Parallel)

**Terminal 1 - Node A Router:**
```bash
docker run --rm --name vllm-sr-a \
  --network envoy-net \
  -v envoy-models-a:/app/models \
  -v $(pwd)/config-a.yaml:/app/config.yaml \
  vllm-sr
```

**Terminal 2 - Node B Router:**
```bash
docker run --rm --name vllm-sr-b \
  --network envoy-net \
  -v envoy-models-b:/app/models \
  -v $(pwd)/config-b.yaml:/app/config.yaml \
  vllm-sr
```

**Wait for:** `"Starting insecure LLM Router ExtProc on :50051"` in both terminals (~5-7 minutes on first run).

### Step 4A: Start Mock Backends

**Terminal 3:**
```bash
# Node A backends
docker run --rm --name qwen-a -d --network envoy-net mock-lb -target -target-port 8000
docker run --rm --name tinyllama-a -d --network envoy-net mock-lb -target -target-port 8001

# Node B backends
docker run --rm --name qwen-b -d --network envoy-net mock-lb -target -target-port 8002
docker run --rm --name tinyllama-b -d --network envoy-net mock-lb -target -target-port 8003
```

---

## Option B: Real vLLM Models (GPU Recommended)

### Step 3B: Start vLLM-SR Instances (Same as Option A)

Use the same commands from Step 3A above.

### Step 4B: Start Real Model Servers

**Terminal 4 - Node A Qwen:**
```bash
docker run --rm --name qwen-a \
  --network envoy-net \
  --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --port 8000 \
  --host 0.0.0.0
```

**Terminal 5 - Node A TinyLlama:**
```bash
docker run --rm --name tinyllama-a \
  --network envoy-net \
  --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8001:8001 \
  vllm/vllm-openai:latest \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --port 8001 \
  --host 0.0.0.0
```

**Terminal 6 - Node B Qwen:**
```bash
docker run --rm --name qwen-b \
  --network envoy-net \
  --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8002:8002 \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --port 8002 \
  --host 0.0.0.0
```

**Terminal 7 - Node B TinyLlama:**
```bash
docker run --rm --name tinyllama-b \
  --network envoy-net \
  --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8003:8003 \
  vllm/vllm-openai:latest \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --port 8003 \
  --host 0.0.0.0
```

**Wait for:** `"Uvicorn running on http://0.0.0.0:XXXX"` in all four terminals.

#### CPU-Only Mode (No GPU)
If you don't have GPUs, add these flags to each vLLM command:
```bash
--enforce-eager \
--max-model-len 2048
```

---

## Common Steps (Both Options)

### Step 5: Start Load Balancer ExtProc Services

**Terminal 3 (or 8 if using real models):**
```bash
docker run --rm --name extproc-a -d --network envoy-net mock-lb -port 9000
docker run --rm --name extproc-b -d --network envoy-net mock-lb -port 9001
```

### Step 6: Start Envoy Proxies

**Same terminal:**
```bash
# Envoy A (Primary - Port 10000)
docker run --rm --name envoy-a -d \
  --network envoy-net \
  -v $(pwd)/envoy-a.yaml:/etc/envoy/envoy.yaml \
  -p 10000:10000 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml

# Envoy B (Peer - Port 10001)
docker run --rm --name envoy-b -d \
  --network envoy-net \
  -v $(pwd)/envoy-b.yaml:/etc/envoy/envoy.yaml \
  -p 10001:10001 \
  envoyproxy/envoy:v1.30-latest \
  -c /etc/envoy/envoy.yaml
```

---

## Verification

### Check All Containers
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected output: 10 containers running (2 Envoy, 2 ExtProc, 2 vLLM-SR, 4 backends).

### Test Semantic Routing

**Math Query (should route to Qwen):**
```bash
curl -v -X POST http://localhost:10000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Calculate the integral of x^2"}]}'
```

**Code Query (should route to TinyLlama):**
```bash
curl -v -X POST http://localhost:10000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Write a Python function to sort a list"}]}'
```

**Look for:** `x-selected-model: local/qwen` or `x-selected-model: local/tinyllama` in response headers.

### Test Load Balancing (Overload Simulation)

Send 4+ concurrent requests to trigger rerouting:
```bash
for i in {1..6}; do
  curl -X POST http://localhost:10000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Calculate 2+2"}]}' &
done
wait
```

**Look for:** `x-reroute-target: peer` in some responses, indicating load balancing to Node B.

---

## Cleanup

```bash
# Stop all containers
docker stop envoy-a envoy-b extproc-a extproc-b vllm-sr-a vllm-sr-b \
  qwen-a tinyllama-a qwen-b tinyllama-b

# Remove network
docker network rm envoy-net
```

---

## Troubleshooting

### vLLM-SR Not Starting
- **Check logs:** `docker logs vllm-sr-a --tail 100`
- **Common issue:** Model downloads taking 5-7 minutes on first run
- **Solution:** Wait for "Starting insecure LLM Router ExtProc" message

### Envoy 500 Errors
- **Check:** vLLM-SR gRPC port is active: `docker exec vllm-sr-a netstat -lntp | grep 50051`
- **Solution:** Ensure vLLM-SR fully initialized before starting Envoy

### Real Models Out of Memory
- **Reduce batch size:** Add `--max-num-seqs 4` to vLLM commands
- **Use smaller models:** Try `Qwen/Qwen2.5-0.5B-Instruct` instead
- **CPU mode:** Remove `--gpus all` and add `--enforce-eager`

### Port Conflicts
- **Check:** `lsof -i :10000` or `lsof -i :10001`
- **Solution:** Stop conflicting processes or change ports in `envoy-a.yaml` / `envoy-b.yaml`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Client                              │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──► Envoy A (10000) ──► vLLM-SR-A ──► Mock-LB-A
             │         │                                │
             │         └──► Qwen-A / TinyLlama-A ◄─────┘
             │
             └──► Envoy B (10001) ──► vLLM-SR-B ──► Mock-LB-B
                       │                                │
                       └──► Qwen-B / TinyLlama-B ◄─────┘
```

- **vLLM-SR:** Semantic routing (keyword + embedding)
- **Mock-LB:** Concurrency tracking + rerouting logic
- **Shared-Nothing:** Each node has independent model instances
