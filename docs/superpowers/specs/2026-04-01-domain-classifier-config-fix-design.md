# Domain Classifier Config Fix — Design Spec

**Date:** 2026-04-01
**Branch:** fresh-vllm
**Status:** Approved

## Problem

Domain classification is silently disabled on every request. The router's `IsCategoryEnabled()` check requires three conditions:

```go
func (c *Classifier) IsCategoryEnabled() bool {
    return c.Config.CategoryModel.ModelID != "" &&
           c.Config.CategoryMappingPath != "" &&
           c.CategoryMapping != nil
}
```

`ModelID` is set in `config-a.yaml`, but `CategoryMappingPath` is never set. This causes the domain inference goroutine to never launch, resulting in `domain=[]` on every request and 0% classification accuracy.

## Root Cause

`category_mapping_path` is a required top-level config field (`config.go:426`) that tells the router where to load the label→index mapping JSON at startup (`extproc/router.go:69`). It was omitted from `config-a.yaml`.

## Fix

Add `category_mapping_path` to `tools/mock-lb/config-a.yaml` under the `classifier` block:

```yaml
classifier:
  category_model:
    model_id: "models/lora_intent_classifier_bert-base-uncased_model"
  category_mapping_path: "models/lora_intent_classifier_bert-base-uncased_model/category_mapping.json"
```

The path resolves to the bind-mounted local model at `/app/models/lora_intent_classifier_bert-base-uncased_model/category_mapping.json` inside the container.

## Scope

- **File changed:** `tools/mock-lb/config-a.yaml`
- **No code changes required**
- **No rebuild required**

## Verification

After restarting the stack, the router logs should show:
- `[Signal Computation] Domain signal evaluation completed in Xms`
- `Signal evaluation results: domain=[math]` (or similar non-empty value)

Running `python tools/benchmark_sr.py` should produce non-zero classification accuracy.
