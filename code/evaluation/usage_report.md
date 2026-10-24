# Token usage and cost report

Summary of the model calls made by the final full-dataset run that produced `output.csv` (518 requests). Everything except request classification and the optional vision fallback is deterministic code, so the agent makes at most one model call per distinct request text.

| provider | model | purpose | calls | input tokens | output tokens | est. cost (USD) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| OpenAI | gpt-4o-mini | classify_request | 375 | 134378 | 12038 | 0.0274 |

## Per-model totals

| model | calls | input tokens | output tokens | est. cost (USD) |
| --- | ---: | ---: | ---: | ---: |
| gpt-4o-mini | 375 | 134378 | 12038 | 0.0274 |

## Overall

* model calls: 375
* input tokens: 134378
* output tokens: 12038
* total tokens: 146416
* average tokens per request: 282.7
* estimated total cost: USD 0.0274
* estimated cost per request: USD 0.000053

Prices are list prices per million tokens (input/output): gpt-4o-mini 0.15/0.6.
