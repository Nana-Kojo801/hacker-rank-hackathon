# Token usage and cost report

Summary of the model calls made by the final full-dataset run that produced `output.csv` (518 requests). Everything except request classification and the optional vision fallback is deterministic code, so the agent makes at most one model call per distinct request text.

| provider | model | purpose | calls | input tokens | output tokens | est. cost (USD) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| OpenAI | gpt-4o-mini | classify_request | 375 | 59753 | 7931 | 0.0137 |

## Per-model totals

| model | calls | input tokens | output tokens | est. cost (USD) |
| --- | ---: | ---: | ---: | ---: |
| gpt-4o-mini | 375 | 59753 | 7931 | 0.0137 |

## Overall

* model calls: 375
* input tokens: 59753
* output tokens: 7931
* total tokens: 67684
* average tokens per request: 130.7
* estimated total cost: USD 0.0137
* estimated cost per request: USD 0.000026

Prices are list prices per million tokens (input/output): gpt-4o-mini 0.15/0.6.
