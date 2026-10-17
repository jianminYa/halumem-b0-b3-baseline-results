# B2 相对 B0：Temporal Gate

本分支只描述 B2；B0 的原始结果在 `artifacts/10user-v2/b0/`，B2 的结果在
`artifacts/10user-v2/b2/`。

## 一句话区别

```text
B0: 每个 block 保留原始 Pass1 → temporal tool → follow-up 路径
B2: Pass1 前本地检查 block 是否可能含 relative temporal expression
    ├─ 明确不含：tool_choice=none，禁止 temporal tool
    └─ 含有或不确定：完整保留 B0 tool + follow-up 路径
```

## 行为约束

B2 不改动：

- B0 Pass1 prompt；
- mentions schema；
- temporal resolver；
- Pass2 prompt 和 MemBlock schema；
- retrieval、embedding 和 QA prompt。

唯一主要变量是是否允许当前 block 调用 temporal tool。gate 是本地 high-recall
规则，false positive 只会少节省 token，unknown 默认 Gate ON，避免漏掉真正的
relative time。

## B0/B2 开关

```text
B0: MEMBLOCK_MERGED_EXTRACTION=0
    MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
    MEMBLOCK_TEMPORAL_GATE_B2=0

B2: MEMBLOCK_MERGED_EXTRACTION=0
    MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
    MEMBLOCK_TEMPORAL_GATE_B2=1
```

每个 block 还记录 `temporal_gate_on/off`、reason、是否实际调用 tool、是否产生
follow-up，方便对账 construction token。

## 代码模块

| 模块 | B2 中负责的内容 |
|---|---|
| `build_impl_graph.py` | relative-time detector 和 gate decision |
| `memblock_extractor.py` | `tool_choice=none`、原始 tool/follow-up、gate log 和 token log |
| `temporal_resolution_tool.py` | 保持 B0 原有 resolver/schema，不替换 |
| `build_prompts.py` | 保持 B0 Pass1/Pass2 prompt；不使用 B1 新 schema |
| `scripts/run_halumem_variant.sh` | `b2` variant 映射为 gate=1、merged=0 |

实现所在的 SA-Mem-core branch：

- [B2 core view branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b2-core-view)
- [B1 → B2 incremental core compare](https://github.com/jianminYa/SA-Mem-core/compare/halumem-b1-core-view...halumem-b2-core-view)
- [B2 gate implementation commit `5a10d72`](https://github.com/jianminYa/SA-Mem-core/commit/5a10d722a3995e4b6d1548b5fcd5317a06da1807)
- [B2 detector recall patch `1d4f097`](https://github.com/jianminYa/SA-Mem-core/commit/1d4f097a95607353d33208b4d3b36eaba7f28246)

这个 incremental compare 只包含 `build_impl_graph.py` 和 `memblock_extractor.py`
的 gate 变化。原来的 `halumem-b0-b3-auto-urlfix` 仍保留作实验集成分支，但不再
作为核心代码审阅入口。

## 结果文件如何查看

- 构建 Memory：[`artifacts/10user-v2/b2/memory_units.jsonl`](../artifacts/10user-v2/b2/memory_units.jsonl)
- 完整 retrieval：[`retrieval_full.jsonl`](../artifacts/10user-v2/b2/retrieval_full.jsonl)
- gold-session 审计：[`retrieval_posthoc_gold_session.json`](../artifacts/10user-v2/b2/retrieval_posthoc_gold_session.json)
- QA：[`qa_results_1repeat.jsonl`](../artifacts/10user-v2/b2/qa_results_1repeat.jsonl)
