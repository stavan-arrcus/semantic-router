# Two-Host Setup (Mac + VM)

Run **Node A** on your Mac and **Node B** on a VM (e.g. Multipass). Each node runs:

- **Envoy** (entry)
- **vLLM-SR** (ExtProc 1 – semantic routing, sets `x-selected-model`)
- **Mock-LB** (ExtProc 2 – concurrency; sets `x-reroute-target: peer` when >3 queries for a model)
- **Mock backends**: Qwen, TinyLlama, and a default mock target

When more than three concurrent queries hit the same model on one node, Mock-LB injects `x-reroute-target: peer` and Envoy forwards the request to the other node.

---

## Prerequisites

- **Mac:** Docker Desktop, Multipass (or another VM), repo at e.g. `~/semantic-router`.
- **VM:** Docker installed (e.g. `curl -fsSL https://get.docker.com | sh` inside the VM).

---

## 1. Build images on the Mac

From the repo root:

```bash
# Mock-LB (used by both nodes)
cd tools/mock-lb && docker build -t mock-lb . && cd ../..

# vLLM-SR (used by both nodes; build once, transfer to VM)
docker build -t vllm-sr -f src/vllm-sr/Dockerfile .
```

---

## 2. Get the VM’s IP

```bash
multipass list
```

Note the **IPv4** for your VM (e.g. `192.168.64.3`). This is **VM_IP** for the next steps.

The Mac’s address as seen from the VM is usually **`192.168.64.1`** (Multipass bridge). Use that as **PEER_IP** when running Node B.

---

## 3. Transfer Node B files and images to the VM

From the repo root (replace `node-b` with your VM name):

```bash
# Transfer mock-lb directory (configs + scripts)
multipass transfer -r tools/mock-lb node-b:./mock-lb

# Transfer vLLM-SR and mock-lb images so the VM doesn’t need to build them
docker save vllm-sr mock-lb | multipass transfer - node-b:images.tar
```

On the VM, load the images:

```bash
multipass shell node-b
docker load -i images.tar
rm images.tar
exit
```

---

## 4. Start Node B on the VM first

```bash
multipass shell node-b
cd mock-lb
export PEER_IP=192.168.64.1
chmod +x run-node-b.sh
./run-node-b.sh
```

Leave this running (or run in the background). Envoy B will listen on port **10001** inside the VM.

---

## 5. Start Node A on the Mac

In a new terminal on the Mac:

```bash
cd /Users/stavandarshanjani/semantic-router/tools/mock-lb
export PEER_IP=<VM_IP>   # e.g. 192.168.64.3 from multipass list
chmod +x run-node-a.sh
./run-node-a.sh
```

Envoy A will listen on **localhost:10000**.

---

## 6. Test

**Basic request (Node A):**

```bash
curl -s http://localhost:10000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"test","messages":[{"role":"user","content":"Calculate 2+2"}]}'
```

**Trigger reroute to Node B (>3 concurrent queries for same model):**

Send 4+ concurrent requests that vLLM-SR routes to the same model (e.g. math → Qwen). The 4th should be rerouted to the VM. Example (run from Mac):

```bash
curl -s http://localhost:10000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"test","messages":[{"role":"user","content":"Calculate 1+1"}]}' &
curl -s http://localhost:10000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"test","messages":[{"role":"user","content":"Calculate 2+2"}]}' &
curl -s http://localhost:10000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"test","messages":[{"role":"user","content":"Calculate 3+3"}]}' &
curl -s http://localhost:10000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"test","messages":[{"role":"user","content":"Calculate 4+4"}]}' &
wait
```

Check Node A and Node B logs; one of the requests should be handled by the peer.

---

## 7. Stop everything

- **Mac:** In the terminal running `run-node-a.sh`, press **Ctrl+C** (containers will stop via the trap).
- **VM:** In the terminal running `run-node-b.sh`, press **Ctrl+C**, or from the Mac:

  ```bash
  multipass shell node-b
  # then Ctrl+C if run-node-b.sh is in foreground, or:
  docker stop envoy-b extproc-b vllm-sr-b mock-target qwen-b tinyllama-b
  ```

---

## Files used

| File | Purpose |
|------|--------|
| `envoy-a-twohost.yaml` | Envoy A template; `$PEER_IP` → VM IP |
| `envoy-b-twohost.yaml` | Envoy B template; `$PEER_IP` → Mac IP (e.g. 192.168.64.1) |
| `run-node-a.sh` | Start Node A on Mac (backends, vLLM-SR, Mock-LB, Envoy) |
| `run-node-b.sh` | Start Node B on VM (same stack) |
| `config-a.yaml` / `config-b.yaml` | vLLM-SR config per node |

`sed` is used to substitute `__PEER_IP__` with the peer’s IP in the Envoy config at startup (both scripts do this; no extra tools like `envsubst` required on macOS).
