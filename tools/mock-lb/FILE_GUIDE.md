# File Guide: mock-lb Directory

This guide explains the purpose of each file in `tools/mock-lb/`.

---

## Core Implementation

### `main.go`
Mock Load Balancer ExtProc: gRPC ExtProc for Envoy, tracks concurrency per `x-selected-model`, injects `x-reroute-target: peer` when a model exceeds 3 concurrent queries. Can also run as mock HTTP target (`-target`).

### `Dockerfile`
Builds the Mock-LB Docker image. Exposes port 9000.

### `go.mod` / `go.sum`
Go module dependencies (Envoy go-control-plane, gRPC).

---

## Configuration

### `config-a.yaml`
vLLM-SR config for Node A: semantic routing (math → local/qwen, code → local/tinyllama), backends at qwen-a:8000, tinyllama-a:8001.

### `config-b.yaml`
vLLM-SR config for Node B: same routing logic, backends at qwen-b:8002, tinyllama-b:8003.

### `envoy-a.yaml`
Envoy config for Node A (single-host demo). Used by `run_demo.sh`. Peer = envoy-b:10001.

### `envoy-b.yaml`
Envoy config for Node B (single-host demo). Used by `run_demo.sh`. Peer = envoy-a:10000.

### `envoy-a-twohost.yaml`
Template for Node A when Mac and VM are separate. `$PEER_IP` is substituted with the VM IP. Used by `run-node-a.sh`.

### `envoy-b-twohost.yaml`
Template for Node B when running on VM. `$PEER_IP` is substituted with the Mac IP (e.g. 192.168.64.1). Used by `run-node-b.sh`.

### `envoy-simple-a.yaml` / `envoy-simple-b.yaml`
Minimal Envoy configs for the local 1-ExtProc demo: one Mock-LB ExtProc, routes by `x-selected-model` (qwen/llama) and `x-reroute-target` (peer). Used by `run-simple-demo.sh`.

---

## Scripts

### `run_demo.sh`
Single-host: starts both nodes (A and B) on one Docker network. All 10 containers (backends, vLLM-SR, ExtProc, Envoy) on the same host. Use for local demo.

### `run-node-a.sh`
Node A on the Mac. Requires `PEER_IP=<VM_IP>`. Starts backends, vLLM-SR, Mock-LB, Envoy A. Uses `envoy-a-twohost.yaml` → `envoy-a.yaml` via envsubst.

### `run-node-b.sh`
Node B on the VM. Requires `PEER_IP=192.168.64.1` (or Mac IP). Same stack as Node A; uses `envoy-b-twohost.yaml` → `envoy-b.yaml` via envsubst.

### `run-simple-demo.sh`
**Local 1-ExtProc demo (no vLLM-SR).** Two Envoy instances, each with one Mock-LB ExtProc. Backends: qwen-a, llama-a (Envoy A), qwen-b, llama-b (Envoy B). Client sends `x-selected-model: qwen` or `x-selected-model: llama`; every 4th request (per model) reroutes to the other Envoy. Use `envoy-simple-a.yaml` and `envoy-simple-b.yaml`.

---

## Documentation

### `TWO_HOST_SETUP.md`
Step-by-step for Mac + VM: build images, transfer to VM, start Node B then Node A, test reroute when >3 queries.

### `MANUAL_SETUP.md`
Manual setup for single-host (optional alternative to `run_demo.sh`).

### `FILE_GUIDE.md` (this file)
Reference for all files in this directory.
