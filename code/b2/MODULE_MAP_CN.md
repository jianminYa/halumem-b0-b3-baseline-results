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

- [SA-Mem-core B0–B3 branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b0-b3-auto-urlfix)
- [B2 branch tip `b18bf77`](https://github.com/jianminYa/SA-Mem-core/commit/b18bf7727e0178e3a316fa01903541d2061716e9)
- [完整 compare](https://github.com/jianminYa/SA-Mem-core/compare/main...halumem-b0-b3-auto-urlfix)
