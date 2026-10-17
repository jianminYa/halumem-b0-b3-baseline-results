# B1 相对 B0：Local Temporal Resolution

本分支只描述 B1；B0 的原始结果仍在 `artifacts/10user-v2/b0/`，B1 的结果在
`artifacts/10user-v2/b1/`。

## 一句话区别

```text
B0: Pass1 → temporal tool → follow-up LLM → Pass2
B1: Pass1 输出 temporal_expressions → 本地 resolver → Pass2
                                  ↘ 不可靠时 fallback 到 B0
```

## 流程与输入输出

1. 原始 block 和 B0 相同，保留 raw dialogue、session 日期、topic continuity
   segmentation 和 MemBlock 最终 schema。
2. Pass1 使用 B1 prompt，除 `topic / keywords / mentions` 外，额外输出
   `temporal_expressions`，每个表达带有对应 mention 的关联信息。
3. 对每个 temporal expression 调用已有的
   `resolve_temporal_expression()`。这是本地 Python 计算，不产生 provider
   LLM token。
4. 本地解析成功后，把绝对日期补回对应 mention，再交给原有 Pass2；Pass2 的
   输入字段、分类逻辑和输出 schema 不改变。
5. 如果 JSON 解析、mention 映射、session 日期、表达式解析任一环节不可靠，
   不静默丢弃结果，而是回到 B0 的 temporal tool + follow-up 路径。

## B0/B1 开关

```text
B0: MEMBLOCK_MERGED_EXTRACTION=0
    MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
    MEMBLOCK_TEMPORAL_GATE_B2=0

B1: MEMBLOCK_MERGED_EXTRACTION=0
    MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=1
    MEMBLOCK_TEMPORAL_GATE_B2=0
```

B1 不启用 B2 gate，也不启用 B3 merged extraction。

## 代码模块

| 模块 | 作用 |
|---|---|
| `build_prompts.py` | B1 Pass1 输出格式和 temporal expression 字段 |
| `build_impl_graph.py` | B1 分支、表达式覆盖检查、本地解析和 fallback 编排 |
| `temporal_resolution_tool.py` | 现有日期解析函数及原始 function schema |
| `memblock_extractor.py` | 配置开关、LLM/tool 调用、Pass2 和 token instrumentation |
| `scripts/run_halumem_variant.sh` | 实验 runner 中的 variant 开关映射 |

精确源码以 SA-Mem-core commit `510d0f3` 为准。为了避免把实验 runner、报告和
artifacts 混进代码审阅，推荐使用只包含核心源码的 view branch：

- [B1 core view branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b1-core-view)
- [B1 core vs main compare](https://github.com/jianminYa/SA-Mem-core/compare/main...halumem-b1-core-view)
- [原始 B1 实验 branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b1-local-temporal)

core view compare 只包含 `build_impl_graph.py`、`build_prompts.py` 和
`memblock_extractor.py` 三个核心文件；B1 实验结果和 runner 仍在本结果仓库中。

## 结果文件如何查看

- 构建 Memory：[`artifacts/10user-v2/b1/memory_units.jsonl`](../artifacts/10user-v2/b1/memory_units.jsonl)
- 完整 retrieval：[`retrieval_full.jsonl`](../artifacts/10user-v2/b1/retrieval_full.jsonl)
- gold-session 审计：[`retrieval_posthoc_gold_session.json`](../artifacts/10user-v2/b1/retrieval_posthoc_gold_session.json)
- QA：[`qa_results_1repeat.jsonl`](../artifacts/10user-v2/b1/qa_results_1repeat.jsonl)

注意：`10user-v2` 的 retrieval/QA 使用修复后的 embedding 重新生成；construction
memory 是复用的既有构建结果，不能把 v2 的新增 token 记为重新 construction。
