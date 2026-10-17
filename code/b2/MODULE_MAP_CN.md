# B2 源码模块定位

本文件是结果仓库中的源码导航；B2 的真实源代码保存在 SA-Mem-core 的集成实验
branch，结果仓库不复制另一份容易漂移的源码。

| 文件 | B2 中负责的内容 |
|---|---|
| `build_impl_graph.py` | `_RELATIVE_TEMPORAL_RE`、gate reason 和 high-recall decision |
| `memblock_extractor.py` | Pass1 前 gate、`tool_choice=none`、原始 follow-up、gate instrumentation |
| `build_prompts.py` | B2 不改变 B0 prompt/schema |
| `temporal_resolution_tool.py` | B2 不改变 B0 resolver |
| `scripts/run_halumem_variant.sh` | `b2)` 分支设置 `local_temporal=0`、`temporal_gate=1`、`merged=0` |

源码入口：

- [B2 core view branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b2-core-view)
- [B1 → B2 incremental compare](https://github.com/jianminYa/SA-Mem-core/compare/halumem-b1-core-view...halumem-b2-core-view)
- [B2 gate commit `5a10d72`](https://github.com/jianminYa/SA-Mem-core/commit/5a10d722a3995e4b6d1548b5fcd5317a06da1807)
