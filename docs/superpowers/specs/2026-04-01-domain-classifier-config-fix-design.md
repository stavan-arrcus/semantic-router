# Domain Classifier Routing Fix — Design Spec

**Date:** 2026-04-01
**Branch:** fresh-vllm (from main)
**Status:** Approved

## Problem

Domain classification returns `domain=[]` on every request, so no decisions match and all traffic falls through to the default model. The router's `IsCategoryEnabled()` check requires three conditions:

```go
func (c *Classifier) IsCategoryEnabled() bool {
    return c.Config.CategoryModel.ModelID != "" &&
           c.Config.CategoryMappingPath != "" &&
           c.CategoryMapping != nil
}
```

During debugging with a stripped-down custom config (`tools/mock-lb/config-a.yaml`), `category_mapping_path` was absent, causing `IsCategoryEnabled()` to return false and the domain inference goroutine to never launch.

## Root Cause (Confirmed)

The custom `tools/mock-lb/config-a.yaml` used during experimentation was missing `category_mapping_path`. The main `config/config.yaml` already has it set correctly:

```yaml
classifier:
  category_model:
    model_id: "models/mom-domain-classifier"
    threshold: 0.6
    use_cpu: true
    category_mapping_path: "models/mom-domain-classifier/category_mapping.json"
```

## Deployment Setup

This branch uses the standard deployment:
- **Config:** `config/config.yaml` mounted at `/app/config/config.yaml`
- **Models:** `models/` mounted at `/app/models/`
- **Docker:** `deploy/docker-compose/docker-compose.yml`
- **Image:** `ghcr.io/vllm-project/semantic-router/extproc:latest`

## What Already Works

- `category_mapping_path` — present in `config/config.yaml`
- Domain-only decisions — all decisions use `type: "domain"` conditions (no keyword rules)
- Model files — `models/mom-domain-classifier/` has `lora_config.json`, `model.safetensors`, `category_mapping.json`, tokenizer files

## Implementation Plan

1. Deploy with `deploy/docker-compose/docker-compose.yml`
2. Verify classifier loads: check logs for `LoRA C bindings initialized successfully` and absence of `IsCategoryEnabled = false`
3. Run benchmark (`tools/benchmark_sr.py`) configured for the standard stack port
4. Confirm `domain=[<category>]` appears in router logs and accuracy > 0%

## Success Criteria

- Router logs show `[Signal Computation] Domain signal evaluation completed`
- `Signal evaluation results: domain=[math]` (or similar non-empty)
- `benchmark_sr.py` reports classification accuracy > 0%
