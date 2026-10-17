# B3 源码模块定位

本文件是结果仓库中的源码导航。B3 的真实实现保存在 SA-Mem-core 的集成实验
branch；结果仓库不复制完整源码，以免结果仓库和源码仓库发生漂移。

| 文件/入口 | B3 中负责的内容 |
|---|---|
| `scripts/run_halumem_variant.sh` | `b3)` 设置 `merged=1`，同时关闭 local temporal 和 B2 gate |
| `memblock_extractor.py` | 读取 `MEMBLOCK_MERGED_EXTRACTION`，选择 merged construction 路径并记录 usage |
| `build_prompts.py` | 定义 `PROMPT_DIALOG_EXTRACT_MERGED` 及其输出约束 |
| `build_impl_graph.py` | 处理 merged 输出、事件/时间字段归一化并组装 MemBlock |
| `temporal_resolution_tool.py` | B3 不是 B1 local resolver；若当前 merged 路径保留 function schema，实际 tool 使用以日志为准 |

## 代码与结果的对应关系

```text
variant b3
  → MEMBLOCK_MERGED_EXTRACTION=1
  → merged prompt / extractor
  → memory_units.jsonl
  → embedding retrieval
  → retrieval_full.jsonl
  → QA / judge
  → qa_results_1repeat.jsonl
```

结果文件：

- [`artifacts/10user-v2/b3/memory_units.jsonl`](../../artifacts/10user-v2/b3/memory_units.jsonl)
- [`artifacts/10user-v2/b3/retrieval_full.jsonl`](../../artifacts/10user-v2/b3/retrieval_full.jsonl)
- [`artifacts/10user-v2/b3/retrieval_posthoc_gold_session.json`](../../artifacts/10user-v2/b3/retrieval_posthoc_gold_session.json)
- [`artifacts/10user-v2/b3/qa_results_1repeat.jsonl`](../../artifacts/10user-v2/b3/qa_results_1repeat.jsonl)

源码入口：

- [SA-Mem-core B0–B3 branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b0-b3-auto-urlfix)
- [完整 compare](https://github.com/jianminYa/SA-Mem-core/compare/main...halumem-b0-b3-auto-urlfix)

结果仓库的 B3 分支是文档/结果视图，不是另一个源码 fork；需要查看逐行代码
差异时，应在上面的 SA-Mem-core branch 和 compare 页面中进行。
