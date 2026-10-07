# B1 源码快照

本目录提供 HaluMem B1 temporal optimization 的源码快照，方便审阅和对照文档。

## 文件

- [`build_impl_graph.py`](build_impl_graph.py)：实验 runner 使用的完整构建实现，其中包含 B1 的 local temporal 分支和 fallback 分支。重点搜索：
  - `_temporal_observation_date`
  - `_resolve_local_temporal_mentions`
  - `_temporal_annotations_cover_mentions`
  - `ENABLE_LOCAL_TEMPORAL_RESOLUTION`
  - `pass1_tool_followup_fallback`
- [`temporal_resolution_tool.py`](temporal_resolution_tool.py)：本地日期解析函数和原始 function schema。

## B1 关键位置

`build_impl_graph.py` 中 B1 的处理顺序是：

```text
local-temporal Pass1 JSON
→ 校验 temporal_expressions 是否覆盖 mentions
→ resolve_temporal_expression(observation_date, expression)
→ 将 resolved_expression 附加到对应 mention
→ 原有 Pass2
```

如果校验失败、session 日期无效、expression 无法解析或 resolver 返回 warning，则重新调用原始 B0 Pass1，并启用 temporal function calling。该路径在 instrumentation 中标记为：

```text
pass1_tool_followup_fallback
```

## 说明

`build_impl_graph.py` 是完整实验构建文件，不是脱离 SA-Mem 依赖即可单独运行的最小脚本；其中还包含构建流程的其它实现。B1 的流程解释和输入输出示例见：

[`docs/B1_VS_B0_PIPELINE_CN.md`](../../docs/B1_VS_B0_PIPELINE_CN.md)

本目录不包含 API key、配置文件或运行缓存。
