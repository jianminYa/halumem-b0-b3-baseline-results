# HaluMem-Medium B0/B1/B2/B3 Baseline Results

> 当前推荐使用 `10user-v2` 结果。`10user-v1` 是保留的历史审计快照：其 embedding 请求虽然返回 HTTP 200，但由于旧 runner 的 base URL 缺少 `/v1`，最终 vector store 中的向量全部为零向量。因此 v1 的 retrieval/QA 指标已标记为 **invalid**，不能作为正式 baseline。

这是 HaluMem-Medium 的 10-user evaluation snapshot，使用四个 memory construction 版本进行同口径 Retrieval 与 QA 对照。修复后的 v2 结果重新生成 embedding、retrieval 和 QA，但复用了已完成的 memory construction。

## 实验配置

| 项目 | 配置 |
|---|---|
| LLM | `gpt-4o-mini` |
| Embedding | `text-embedding-3-small` |
| Retrieval ranking | `content + event + topic/keyword` |
| Retrieval Top-K | 20 |
| QA context | Top-20 |
| QA repeats（v2） | 1 |
| 用户数 | 10 |
| session 数 | 680 |
| message 数 | 29,722 |
| question 数 | 1,722 |

## 四个版本

- `B0`：原始 two-pass construction。
- `B1`：加入 local temporal resolution，并对无法本地处理的情况保留 fallback。
- `B2`：temporal gate；不含相对时间的 block 禁止 temporal tool，含时间或不确定时保留原路径。
- `B3`：merged extraction 版本，作为额外对照。

## 目录说明

### 推荐结果：`artifacts/10user-v2/`

每个版本提供：

- `memory_units.jsonl`：实际复用的全部 memory units；与 v1 中的 construction artifact SHA-256 一致。
- `retrieval_full.jsonl`：修复 embedding 后生成的完整 retrieval ranking。
- `retrieval_posthoc_gold_session.json`：修复后的 gold-session Hit@K/MRR 审计。
- `qa_results_1repeat.jsonl`：一次 QA + judge 的逐题结果及 token usage。
- `qa_summary.json`：一次 QA aggregate。
- `build_checkpoint.json`：构建来源和复用范围。

### 历史结果：`artifacts/10user/`

该目录保留 v1 的原始结果用于审计，但 v1 retrieval/QA 因全零 embedding 已失效。v1 的 memory construction artifact 仍然有效。

每个版本都在 `artifacts/10user/<variant>/` 下提供：

- `memory_units.jsonl`：实际用于评估的全部 MemoryBlock/box 构建结果；可查看 `block_id`、`coverage`、`features`、events 和 temporal metadata。
- `retrieval_full.jsonl`：每个 question 的完整 ranking，不只保存 Top-K。
- `retrieval_posthoc_gold_session.json`：基于原始 conversation 和 gold evidence 的 post-hoc gold-session Hit@K 审计结果。
- `qa_results_3repeats.jsonl`：三次 QA/judge 的逐题结果及 token usage。
- `qa_summary.json`：QA aggregate。
- `build_checkpoint.json`：构建文件范围与 memory unit 计数。

`reports/10user_dataset_stats.json` 和 `reports/10user_selection_manifest.json` 保存数据规模及非敏感配置。原始数据、embedding/vector cache、API 配置和 credentials 不在仓库中。

## 如何查看一个 question

```bash
# 查看修复后版本某个 variant 的第一条 memory
sed -n '1p' artifacts/10user-v2/b0/memory_units.jsonl | python -m json.tool

# 查看修复后某个 question 的完整 retrieval ranking
rg '"qa_idx": 1' artifacts/10user-v2/b0/retrieval_full.jsonl

# 查看修复后 gold-session post-hoc 对齐
python - <<'PY'
import json
p = json.load(open('artifacts/10user-v2/b0/retrieval_posthoc_gold_session.json'))
print(p['summary'])
print(p['details'][1])
PY

# 查看一次 QA 结果
rg '"qa_idx": 1' artifacts/10user-v2/b0/qa_results_1repeat.jsonl
```

## B1 流程说明

B1 相比 B0 的完整中文流程、输入输出字段、本地 temporal resolver、fallback 条件和实际示例，见：

[docs/B1_VS_B0_PIPELINE_CN.md](docs/B1_VS_B0_PIPELINE_CN.md)

B1 实际源码快照位于 [`code/b1/`](code/b1/)，包括构建集成文件和 temporal resolver。

该文档特别区分了：

- B1 的 Pass1 中间输出与 B0 的差异；
- local resolver 的零 token 本地计算；
- 哪些情况直接 local resolve；
- 哪些情况回退到 B0 的 tool + follow-up；
- B1 如何继续复用原有 Pass2 和最终 Memory schema。

## Retrieval 指标口径

HaluMem cleaned evidence 使用字典结构 `memory_content/memory_type`，而原生 adapter 的 `target_boxes` 解析器仍期待旧式字符串 evidence。因此原始 retrieval JSONL 中的 `target_boxes` 不能直接用于 Hit@K。

本仓库的 `retrieval_posthoc_gold_session.json` 不修改 ranking，也不调用 API；它将 gold evidence 与原始 conversation session 做确定性的 lexical alignment，再按照 MemoryBlock 的 `coverage.session_id` 计算 gold-session rank。该结果是可审计的 adapter-level diagnostic，未宣称为数据集官方 retrieval label。未解析项单独计数，不静默当作 hit 或 miss。

## Construction 口径

v2 没有重新执行 construction，因此本次新增 construction token 为 `0`。`memory_units.jsonl` 是从已完成 source run 复用的构建结果。

现有 source construction log 没有保存 `source_file_id`，无法把 provider token 精确分配到这 10 个用户；因此报告同时给出 source full-run exact token，以及按 memory-unit 比例计算的非精确 estimate，estimate 不作为 exact cost。

QA token 仅属于 QA/judge 阶段，不计入 construction cost。

## 结果摘要

修复后详细表格见 [`reports/10USER_V2_REPAIRED_REPORT.md`](reports/10USER_V2_REPAIRED_REPORT.md)；旧版审计说明见 [`reports/10USER_BASELINE_REPORT.md`](reports/10USER_BASELINE_REPORT.md)。

本仓库只发布 10-user evaluation snapshot；后续若扩大数据规模，应建立新的 release，而不是覆盖本版本 artifacts。v2 的详细结果见 [`reports/10USER_V2_REPAIRED_REPORT.md`](reports/10USER_V2_REPAIRED_REPORT.md)。
