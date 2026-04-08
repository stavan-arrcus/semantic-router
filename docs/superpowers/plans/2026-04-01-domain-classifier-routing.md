# Domain Classifier Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that the semantic router correctly classifies incoming prompts by domain and routes them to the appropriate backend, with classification accuracy > 0%.

**Architecture:** The router binary (`bin/router`) loads `config/config.yaml` on startup. That config has `category_mapping_path` set, so `IsCategoryEnabled()` returns true and the domain inference goroutine launches. Envoy (via `func-e`) fronts the router on port 8801 and forwards ext_proc calls to it on port 8080.

**Tech Stack:** Go router binary, Envoy (func-e), LoRA Candle Rust C bindings, Python benchmark scripts

> **Note on deployment method:** The spec references `deploy/docker-compose/docker-compose.yml`. This plan uses `scripts/local-up-router.sh` (dockerless) instead — same config and models, faster iteration. If you prefer Docker, replace Task 2 Steps 1–3 with `docker compose -f deploy/docker-compose/docker-compose.yml up` and tail container logs instead of `/tmp/router.log`.

---

## File Map

| File | Role |
|---|---|
| `config/config.yaml` | Main config — already correct, no changes needed |
| `scripts/local-up-router.sh` | Builds router, downloads models, starts router + Envoy |
| `bin/router` | Built artifact — must exist before starting |
| `models/mom-domain-classifier/` | LoRA model files (lora_config.json, model.safetensors, category_mapping.json, tokenizer files) |
| `models/mom-pii-classifier/` | Required for LoRA model discovery (all 3 must be present) |
| `models/mom-jailbreak-classifier/` | Required for LoRA model discovery (all 3 must be present) |
| `/tmp/router.log` | Router log output (written by local-up-router.sh) |
| `bench/benchmark_comparison.sh` | Benchmark script — hits Envoy at port 8801 |

---

### Task 1: Verify Model Files Are Present

**Files:**
- Read: `models/mom-domain-classifier/`
- Read: `models/mom-pii-classifier/`
- Read: `models/mom-jailbreak-classifier/`

- [ ] **Step 1: Check all three LoRA model directories exist and have required files**

```bash
ls models/mom-domain-classifier/
ls models/mom-pii-classifier/
ls models/mom-jailbreak-classifier/
```

Expected output for `mom-domain-classifier`:
```
category_mapping.json  lora_config.json  model.safetensors  tokenizer.json  tokenizer_config.json  ...
```

If any directory is missing, the LoRA model discovery loop will find zero valid model sets and `IsCategoryEnabled()` will return false. The router downloads models via `--download-only` flag, so missing models will be fetched during Task 2 Step 1.

- [ ] **Step 2: Verify `category_mapping.json` is valid JSON with a non-empty mapping**

```bash
python3 -c "
import json
with open('models/mom-domain-classifier/category_mapping.json') as f:
    m = json.load(f)
print(f'Labels: {list(m.values())[:5]}...')
print(f'Total entries: {len(m)}')
"
```

Expected: prints a list of domain labels (math, biology, etc.) with at least 14 entries.

- [ ] **Step 3: Verify `lora_config.json` has a `base_model_name_or_path` field**

```bash
python3 -c "
import json
with open('models/mom-domain-classifier/lora_config.json') as f:
    c = json.load(f)
print('base_model:', c.get('base_model_name_or_path', 'MISSING'))
print('peft_type:', c.get('peft_type', 'MISSING'))
"
```

Expected: `base_model: bert-base-uncased` (or similar BERT variant), `peft_type: LORA`.

---

### Task 2: Build and Start the Router

**Files:**
- Modify: nothing (build-only)
- Run: `scripts/local-up-router.sh`

- [ ] **Step 1: Build the router binary and download models**

```bash
make build
```

Expected: `bin/router` is produced with no errors. If build fails, check Go toolchain: `go version` must be ≥ 1.21.

- [ ] **Step 2: Start the router in a terminal (keep it running)**

Run in a separate terminal window (this blocks; keep it open):
```bash
scripts/local-up-router.sh
```

The script will:
1. Run `make build` (again — safe to skip with `-o bin` flag if already built)
2. Download models via `bin/router --config config/config.yaml --download-only`
3. Start router on port 8080 (logs → `/tmp/router.log`)
4. Install `func-e` if missing, then start Envoy on port 8801 (logs → `/tmp/envoy.log`)
5. Print: `The local semantic router is running. Press Ctrl-C to shut it down.`

- [ ] **Step 3: Wait for the health endpoint to respond**

```bash
curl -sf http://127.0.0.1:8080/health
```

Expected: `{"status":"ok"}` or similar 200 response. If curl fails after 30s, check `/tmp/router.log` for crash output.

---

### Task 3: Verify Domain Classifier Initialized

**Files:**
- Read: `/tmp/router.log`

- [ ] **Step 1: Check LoRA bindings initialized**

```bash
grep -i "LoRA C bindings\|lora.*init\|candle.*init" /tmp/router.log
```

Expected line (exact wording may vary):
```
LoRA C bindings initialized successfully
```

If absent, check for `IsCategoryEnabled = false` instead.

- [ ] **Step 2: Confirm `IsCategoryEnabled` is not false**

```bash
grep -i "IsCategoryEnabled\|category.*enabled\|category.*disabled" /tmp/router.log
```

Expected: no lines containing `IsCategoryEnabled = false`. If found, verify `config/config.yaml` lines 101–105:
```yaml
classifier:
  category_model:
    model_id: "models/mom-domain-classifier"
    threshold: 0.6
    use_cpu: true
    category_mapping_path: "models/mom-domain-classifier/category_mapping.json"
```

- [ ] **Step 3: Check domain signal evaluation appears in logs during startup or first request**

```bash
grep -i "domain\|category\|signal" /tmp/router.log | head -20
```

Expected after first request: lines containing `Signal Computation` or `domain inference goroutine`.

---

### Task 4: Send a Test Prompt and Confirm Domain Classification

**Files:**
- Read: `config/config.yaml` (decisions section, lines 202–480)

- [ ] **Step 1: Send a math prompt through Envoy**

```bash
curl -s -X POST http://127.0.0.1:8801/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 1234" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "What is the derivative of x squared?"}],
    "max_tokens": 5
  }'
```

Expected: JSON response (may be an error if no backend is running — that is fine). The important check is in the router logs.

- [ ] **Step 2: Check router logs for non-empty domain signal**

```bash
grep -i "domain=\[" /tmp/router.log | tail -5
```

Expected:
```
Signal evaluation results: domain=[math]
```

Any non-empty `domain=[<label>]` confirms classification is working. `domain=[]` means the classifier is still not running — go back to Task 3.

- [ ] **Step 3: Send a biology prompt and verify routing decision**

```bash
curl -s -X POST http://127.0.0.1:8801/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 1234" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Explain the role of mitochondria in ATP synthesis."}],
    "max_tokens": 5
  }'
```

- [ ] **Step 4: Confirm routing decision appears in logs**

```bash
grep -i "decision\|matched\|routing" /tmp/router.log | tail -10
```

Expected: a line referencing the decision name that matched (e.g., `biology_decision` selected, or `matched decision: biology_decision`).

---

### Task 5: Run Benchmark and Confirm Accuracy > 0%

**Files:**
- Run: `bench/benchmark_comparison.sh`

- [ ] **Step 1: Activate the Python virtual environment**

```bash
source vsr/bin/activate
```

Expected: shell prompt changes to show `(vsr)`.

- [ ] **Step 2: Run the router-only benchmark with a small sample**

```bash
cd bench && bash benchmark_comparison.sh arc 3 1
```

This runs:
- 3 samples per category from the ARC dataset
- 1 concurrent request
- Router endpoint: `http://127.0.0.1:8801/v1`

Note: The vLLM direct endpoint (`http://127.0.0.1:8000/v1`) will likely fail if no direct vLLM backend is running — that is expected and OK. Focus on the router phase output.

- [ ] **Step 3: Check the benchmark output for classification accuracy**

Look for lines like:
```
Router (via Envoy):
  Accuracy: 0.XXX
  ...
  Questions: N/N
```

Success criterion: accuracy > 0.0 (any non-zero value confirms domain classification is firing).

- [ ] **Step 4: Check router logs for domain signal during benchmark**

In a second terminal:
```bash
grep "domain=\[" /tmp/router.log | grep -v "domain=\[\]" | wc -l
```

Expected: count > 0. Every request that got a non-empty domain classification counted.

---

### Task 6: Commit Verification Evidence

- [ ] **Step 1: Capture a snapshot of key log lines as evidence**

```bash
grep -E "LoRA C bindings|IsCategoryEnabled|domain=\[|Signal evaluation" /tmp/router.log \
  | head -30 > /tmp/domain_classifier_evidence.txt
cat /tmp/domain_classifier_evidence.txt
```

- [ ] **Step 2: Commit the design spec (already written) to confirm the branch state**

```bash
git add docs/superpowers/specs/2026-04-01-domain-classifier-config-fix-design.md
git add docs/superpowers/plans/2026-04-01-domain-classifier-routing.md
git commit -m "docs: add domain classifier routing spec and implementation plan

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Troubleshooting Reference

| Symptom | Cause | Fix |
|---|---|---|
| `domain=[]` in every request | `IsCategoryEnabled()` returns false | Check `config.yaml` line 105 for `category_mapping_path` |
| `no valid models found` | LoRA model discovery failed | Ensure all 3 dirs exist: `mom-domain-classifier`, `mom-pii-classifier`, `mom-jailbreak-classifier` |
| `IsCategoryEnabled = false` in logs | `CategoryMappingPath == ""` | Verify `category_mapping_path` field in yaml |
| Router crashes on startup | Build artifact missing or candle binding error | Re-run `make build`; check Go + Rust toolchain |
| Envoy not starting | `func-e` download failed | Check network; re-run `scripts/local-up-router.sh` |
| 0% benchmark accuracy | Requests not reaching router, or domain=[] | Check Envoy is running on 8801 and domain log lines |
