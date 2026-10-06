# HaluMem-Medium B0/B1/B2/B3 Baseline Results

这是 HaluMem-Medium 的 10-user evaluation snapshot，使用四个 memory construction 版本进行同口径 Retrieval 与 QA 对照。

## 实验配置

| 项目 | 配置 |
|---|---|
| LLM | `gpt-4o-mini` |
| Embedding | `text-embedding-3-small` |
| Retrieval ranking | `content + event + topic/keyword` |
| Retrieval Top-K | 20 |
| QA context | Top-20 |
| QA repeats | 3 |
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
# 查看某个版本的第一条 memory
sed -n '1p' artifacts/10user/b0/memory_units.jsonl | python -m json.tool

# 查看某个 question 的完整 retrieval ranking
rg '"qa_idx": 1' artifacts/10user/b0/retrieval_full.jsonl

# 查看该 question 的 gold-session post-hoc 对齐
python - <<'PY'
import json
p = json.load(open('artifacts/10user/b0/retrieval_posthoc_gold_session.json'))
print(p['summary'])
print(p['details'][1])
PY

# 查看三次 QA 结果
rg '"qa_idx": 1' artifacts/10user/b0/qa_results_3repeats.jsonl
```

## Retrieval 指标口径

HaluMem cleaned evidence 使用字典结构 `memory_content/memory_type`，而原生 adapter 的 `target_boxes` 解析器仍期待旧式字符串 evidence。因此原始 retrieval JSONL 中的 `target_boxes` 不能直接用于 Hit@K。

本仓库的 `retrieval_posthoc_gold_session.json` 不修改 ranking，也不调用 API；它将 gold evidence 与原始 conversation session 做确定性的 lexical alignment，再按照 MemoryBlock 的 `coverage.session_id` 计算 gold-session rank。该结果是可审计的 adapter-level diagnostic，未宣称为数据集官方 retrieval label。未解析项单独计数，不静默当作 hit 或 miss。

## Construction 口径

`memory_units.jsonl` 是本 evaluation snapshot 实际使用的构建结果。subset 粒度的 provider construction token attribution 不可从现有 per-call log 精确恢复，因此本仓库不伪造 subset exact token；构建结果本身和 memory unit 数量完整保留。

QA token 仅属于 QA/judge 阶段，不计入 construction cost。

## 结果摘要

详细表格见 [`reports/10USER_BASELINE_REPORT.md`](reports/10USER_BASELINE_REPORT.md)。

本仓库只发布 10-user evaluation snapshot；后续若扩大数据规模，应建立新的 release，而不是覆盖本版本 artifacts。
