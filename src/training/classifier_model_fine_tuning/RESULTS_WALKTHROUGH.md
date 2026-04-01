# MiniLM Domain Classifier — Training & Evaluation Walkthrough

## Model

- **Architecture**: `sentence-transformers/all-MiniLM-L12-v2` fine-tuned via `AutoModelForSequenceClassification`
- **Task**: 14-class domain classification
- **Framework**: Hugging Face Transformers + Trainer API

## Dataset

- **Base**: [TIGER-Lab/MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro) — 12,032 samples
- **Supplement**: [LLM-Semantic-Router/category-classifier-supplement](https://huggingface.co/datasets/LLM-Semantic-Router/category-classifier-supplement) — 653 samples
- **Total**: 12,685 samples
- **Split**: 70% train / 15% validation / 15% test (stratified)

## Training Configuration

| Parameter | Value |
|-----------|-------|
| Epochs | 3 |
| Batch size | 8 |
| Learning rate | 2e-5 |
| Weight decay | 0.1 |
| Gradient accumulation steps | 2 |
| Mixed precision (fp16) | No (CPU/MPS) |
| Best model metric | F1 (weighted) |

## Training Progress

| Epoch | Eval Loss | F1 (weighted) | Accuracy |
|-------|-----------|---------------|----------|
| 1 | 1.389 | 0.673 | 69.4% |
| 2 | 1.026 | 0.793 | 79.4% |
| 3 | **0.927** | **0.813** | **81.4%** |

## Final Evaluation

| Split | Accuracy | Precision | Recall | F1 |
|-------|----------|-----------|--------|----|
| Validation | 81.4% | 0.816 | 0.814 | 0.813 |
| Test | 78.4% | 0.787 | 0.783 | 0.782 |

## Per-Class Test Results

| Category | Precision | Recall | F1 | Support |
|----------|-----------|--------|----|---------|
| law | 0.911 | 0.959 | 0.934 | 170 |
| math | 0.821 | 0.928 | 0.871 | 207 |
| history | 1.000 | 0.742 | 0.852 | 62 |
| economics | 0.799 | 0.817 | 0.808 | 131 |
| philosophy | 0.813 | 0.762 | 0.787 | 80 |
| engineering | 0.854 | 0.700 | 0.769 | 150 |
| chemistry | 0.721 | 0.833 | 0.773 | 174 |
| business | 0.756 | 0.780 | 0.768 | 123 |
| computer science | 0.783 | 0.712 | 0.746 | 66 |
| health | 0.738 | 0.756 | 0.747 | 127 |
| physics | 0.754 | 0.769 | 0.761 | 199 |
| biology | 0.822 | 0.661 | 0.733 | 112 |
| other | 0.713 | 0.640 | 0.675 | 178 |
| psychology | 0.652 | 0.742 | 0.694 | 124 |
| **weighted avg** | **0.787** | **0.783** | **0.782** | 1903 |

## Key Observations

**Strongest categories** (F1 > 0.85):
- `law` (0.934) — high precision and recall, well-defined vocabulary
- `math` (0.871) — strong recall, model reliably catches math questions
- `history` (0.852) — perfect precision, though recall drops to 0.742

**Weakest categories** (F1 < 0.72):
- `other` (0.675) — catch-all class with high intra-class variance; hardest to classify
- `psychology` (0.694) — overlaps with `health` and `biology`

**Notable patterns**:
- `biology` has good precision (0.822) but weak recall (0.661), meaning the model is conservative — it misses biology questions and likely assigns them to `chemistry` or `health`
- `engineering` has the inverse problem: strong precision (0.854), weak recall (0.700)
- `computer science` has the smallest support (66) which limits generalization

## Saved Artifacts

| File | Description |
|------|-------------|
| `category_classifier_minilm_model/model.safetensors` | Fine-tuned model weights |
| `category_classifier_minilm_model/tokenizer.json` | Tokenizer |
| `category_classifier_minilm_model/category_mapping.json` | Label ↔ ID mappings |
| `category_classifier_minilm_model/evaluation_results.json` | Full per-class metrics (JSON) |

## How to Run

**Train from scratch:**
```bash
python ft_linear.py --mode train --model minilm
```

**Run inference on saved model:**
```bash
python ft_linear.py --mode test --model minilm
```

**Try a stronger model:**
```bash
python ft_linear.py --mode train --model modernbert-base
```
