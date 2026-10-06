# HaluMem-Medium 10-user B0/B1/B2/B3 修复后结果

## 结论

本次只重新执行了 embedding、retrieval 和一次 QA/judge。四个版本的 memory construction 直接复用已有结果，没有重新执行 construction。

旧版 `10user-v1` 的 vector store 全部为零向量，retrieval/QA 指标无效；本报告使用 `10user-v2` 的修复后结果。

## 配置与运行

- LLM：`gpt-4o-mini`
- Embedding：`text-embedding-3-small`
- Embedding endpoint：使用规范化的 `/v1` path
- Retrieval ranking：`content_event_topic_kw`
- Retrieval Top-K：20
- QA context：20
- QA repeats：1
- 用户数：10
- sessions：680
- messages：29,722
- questions：1,722
- 新运行目录：`/workspace/SA-mem/halumem-b0-b3-runs-10user-v2`

## Embedding 健康检查

| Variant | Embedding requests | Vector files | Numeric vectors | Zero vectors | Dimension |
|---|---:|---:|---:|---:|---:|
| B0 | 4,019 | 10 | 4,019 | 0 | 1,536 |
| B1 | 3,990 | 10 | 3,990 | 0 | 1,536 |
| B2 | 4,012 | 10 | 4,012 | 0 | 1,536 |
| B3 | 4,030 | 10 | 4,030 | 0 | 1,536 |

向量范数范围约为 `0.9993–1.0007`，不再是零向量。

## Construction token 成本

### 本次新增成本

本次没有重新进行 memory construction，因此新增 construction token 为：

```text
0 provider construction tokens
```

### Source full-run exact provider usage

以下是生成这批 memory 的 source run 全量 construction 成本：

| Variant | Split / continuity | Pass1 / merged | Tool follow-up | Pass2 | Source total |
|---|---:|---:|---:|---:|---:|
| B0 | 11,238,687 | 10,023,491 | 11,441,616 | 7,192,257 | 39,896,051 |
| B1 | 11,239,700 | 10,550,762 | 3,179,076 fallback | 6,524,982 | 31,494,520 |
| B2 | 11,233,933 | 10,382,190 | 3,875,355 | 7,143,175 | 32,634,653 |
| B3 | 11,231,562 | 13,046,497 merged | 5,564,571 merged follow-up | — | 29,842,630 |

B1 还有 2,401 次 `temporal_local_resolve`，属于本地处理，不产生 provider LLM token。

### 10-user subset estimate

原始 per-call log 没有记录 `source_file_id`，所以无法精确恢复这 10 个 source file 的 provider token。下面只是按 memory-unit 比例的粗略估算：

| Variant | 10-user memory units | Source memory units | Unit ratio | Estimated construction tokens |
|---|---:|---:|---:|---:|
| B0 | 2,434 | 4,960 | 0.4907 | ≈19,578,022 |
| B1 | 2,405 | 4,949 | 0.4860 | ≈15,304,975 |
| B2 | 2,427 | 4,981 | 0.4873 | ≈15,901,285 |
| B3 | 2,445 | 4,993 | 0.4897 | ≈14,613,505 |

这些数值是 estimate，不是 exact provider attribution；GitHub 中不将其冒充为精确 construction cost。

## Retrieval post-hoc gold-session audit

分母为 1,288 个有 evidence 的问题，所有 evidence 均成功映射到至少一个原始 session。该指标是基于原始 conversation 和 memory coverage 的 post-hoc audit，不是 HaluMem native `target_boxes` 官方标签。

| Variant | Hit@1 | Hit@5 | Hit@10 | Hit@20 | MRR | Mean gold rank |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0.3525 | 0.5474 | 0.6141 | 0.6856 | 0.4479 | 32.85 |
| B1 | 0.3432 | 0.5349 | 0.5986 | 0.6708 | 0.4374 | 33.97 |
| B2 | 0.3517 | 0.5481 | 0.6180 | 0.6902 | 0.4466 | 33.00 |
| B3 | 0.3447 | 0.5373 | 0.5978 | 0.6677 | 0.4373 | 35.17 |

## QA

| Variant | Correct | Accuracy | Hallucination | Omission | QA+judge tokens |
|---|---:|---:|---:|---:|---:|
| B0 | 928/1,722 | 0.5389 | 364 | 430 | 16,773,823 |
| B1 | 947/1,722 | 0.5499 | 370 | 405 | 16,634,795 |
| B2 | 923/1,722 | 0.5360 | 363 | 436 | 16,634,938 |
| B3 | 930/1,722 | 0.5401 | 360 | 432 | 16,509,960 |

QA token 不计入 construction cost。由于本次只运行一次 QA，这些 accuracy 不是重复实验均值。

## v1 与 v2 的含义

v1 的 Hit@10 约为 0.064，QA 约为 0.38；v2 修复后 Hit@10 约为 0.60–0.62，QA 约为 0.536–0.550。这个变化符合“零向量排序被修复”的预期，因此 v1 不应被解释为随机 memory 的正式对照。

## 可审计文件

- `artifacts/10user-v2/<variant>/memory_units.jsonl`
- `artifacts/10user-v2/<variant>/retrieval_full.jsonl`
- `artifacts/10user-v2/<variant>/retrieval_posthoc_gold_session.json`
- `artifacts/10user-v2/<variant>/qa_results_1repeat.jsonl`
- `artifacts/10user-v2/<variant>/qa_summary.json`
- `reports/HALUMEM_10USER_V2_RESULTS.json`
