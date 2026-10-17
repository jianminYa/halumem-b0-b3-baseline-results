# B1 源码模块定位

本文件是结果仓库中的源码导航，不复制 SA-Mem-core 全部源码。这样可以通过固定
commit 和 compare 页面审计真实实现。

| 文件 | B1 中负责的内容 |
|---|---|
| `build_prompts.py` | `PROMPT_DIALOG_EXTRACT_LOCAL_TEMPORAL` |
| `build_impl_graph.py` | Pass1 B1 分支、mention 与 temporal expression 对齐、fallback |
| `temporal_resolution_tool.py` | `resolve_temporal_expression()` |
| `memblock_extractor.py` | `ENABLE_LOCAL_TEMPORAL_RESOLUTION`、Pass1/Pass2 调用与 token log |

真实代码：

- [SA-Mem-core B1 branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b1-local-temporal)
- [B1 commit `510d0f3`](https://github.com/jianminYa/SA-Mem-core/commit/510d0f3e935b72c06128987898926f4e41948db9)
- [B1 vs B0 compare](https://github.com/jianminYa/SA-Mem-core/compare/main...halumem-b1-local-temporal)
