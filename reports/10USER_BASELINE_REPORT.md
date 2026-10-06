# HaluMem-Medium 10-user B0/B1/B2/B3 Baseline（历史 v1，已失效）

> 本文件和 `artifacts/10user/` 保留用于审计。该次运行的 embedding vector store 全部为零向量，因此其中的 retrieval/QA 指标不能作为有效 baseline。修复后的结果见 [`10USER_V2_REPAIRED_REPORT.md`](10USER_V2_REPAIRED_REPORT.md)。

## 数据与模型

- HaluMem-Medium：10 users、680 sessions、29,722 messages、1,722 questions。
- LLM：`gpt-4o-mini`。
- Embedding：`text-embedding-3-small`。
- Retrieval ranking：`content_event_topic_kw`，完整 ranking 落盘，QA 使用 Top-20。
- QA：每个版本重复 3 次。

## Memory construction

| Variant | Memory units |
|---|---:|
| B0 | 2,434 |
| B1 | 2,405 |
| B2 | 2,427 |
| B3 | 2,445 |

本 release 保留每个版本的完整 `memory_units.jsonl`。subset 粒度的 provider construction token 没有可靠的 per-user attribution，因此没有把估算值冒充 exact token。

## Retrieval post-hoc gold-session audit

分母为 1,288 个有 gold evidence 的 question；所有 1,288 个 evidence 都成功映射到至少一个原始 session。指标来自 `retrieval_posthoc_gold_session.json`，不是原生 `target_boxes` 字段。

| Variant | Hit@1 | Hit@5 | Hit@10 | Hit@20 | MRR | Mean gold rank |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0.0326 | 0.0373 | 0.0637 | 0.1102 | 0.0516 | 105.94 |
| B1 | 0.0326 | 0.0349 | 0.0637 | 0.1095 | 0.0514 | 105.14 |
| B2 | 0.0326 | 0.0411 | 0.0637 | 0.1172 | 0.0518 | 106.09 |
| B3 | 0.0326 | 0.0411 | 0.0637 | 0.1149 | 0.0517 | 106.26 |

## QA

| Variant | Repeat 1 | Repeat 2 | Repeat 3 | Mean accuracy | Std |
|---|---:|---:|---:|---:|---:|
| B0 | 0.3827 | 0.3839 | 0.3740 | 0.3802 | 0.0044 |
| B1 | 0.3827 | 0.3821 | 0.3839 | 0.3829 | 0.0007 |
| B2 | 0.3839 | 0.3763 | 0.3821 | 0.3808 | 0.0032 |
| B3 | 0.3844 | 0.3844 | 0.3844 | 0.3844 | 0.0000 |

这组结果用于 pipeline sanity check 和版本对照，不应被解读为大规模结论。

## 重要口径说明

HaluMem cleaned evidence 是 `memory_content/memory_type` 字典；native adapter 的 `target_boxes` 仍按旧字符串格式解析，所以原始 JSONL 的 `target_boxes` 为空。为了避免把错误字段当成 retrieval ground truth，本 release 单独保存了 post-hoc gold-session 对齐结果，并把 unresolved evidence 单独计数。

逐题的 memory、完整 ranking、gold-session 对齐、QA hypothesis 和 judge 结果均在 `artifacts/10user/` 中。
