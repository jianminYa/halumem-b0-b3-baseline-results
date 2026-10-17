# B3 相对 B0：Merged Extraction

本分支只描述 B3；B0 的原始结果在 `artifacts/10user-v2/b0/`，B3 的结果在
`artifacts/10user-v2/b3/`。

## 一句话区别

```text
B0: Pass1 topic/keywords/mentions
    → temporal tool（必要时）
    → follow-up LLM
    → Pass2 classify / temporal metadata
    → MemBlock

B3: 一个 merged extraction request
    → topic / keywords / events / temporal metadata
    → MemBlock assembly
```

B3 将原 B0 的主要抽取结果放进 merged extraction prompt，作为“减少阶段边界
和重复上下文”的对照方案。raw dialogue 仍然保留，最终 Memory/MemBlock 的
下游 schema 和 retrieval/QA 使用方式保持兼容。

## B3 不包含什么

B3 不是 B1+B2 的叠加：

- 不使用 B1 的 `temporal_expressions` 中间 schema；
- 不使用 B1 的本地 temporal resolver；
- 不使用 B2 的 `MEMBLOCK_TEMPORAL_GATE_B2`；
- 不修改 retrieval、embedding 或 QA prompt；
- 不删除 raw dialogue，也不改变最终 Memory/MemBlock 的存储接口。

## 输入与输出

### 输入

merged extraction 仍以当前 block/session 的 raw dialogue、session 时间窗口和
原有构建配置为输入。请求由 `PROMPT_DIALOG_EXTRACT_MERGED` 生成；具体字段和
schema 以 SA-Mem-core 对应 commit 为准。

### 输出

主抽取请求直接生成后续 MemBlock 需要的主题、关键词、事件/mention 以及时间
元数据，随后由现有归一化和 MemBlock assembly 代码落盘。结果文件中可以查看：

- `artifacts/10user-v2/b3/memory_units.jsonl`：全部 memory units；
- `artifacts/10user-v2/b3/retrieval_full.jsonl`：每个 question 的完整 ranking；
- `artifacts/10user-v2/b3/retrieval_posthoc_gold_session.json`：gold-session
  Hit@K/MRR 审计；
- `artifacts/10user-v2/b3/qa_results_1repeat.jsonl`：一次 QA/judge 结果；
- `artifacts/10user-v2/b3/build_checkpoint.json`：构建来源和复用范围。

## 开关配置

```text
B0: MEMBLOCK_MERGED_EXTRACTION=0
    MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
    MEMBLOCK_TEMPORAL_GATE_B2=0

B3: MEMBLOCK_MERGED_EXTRACTION=1
    MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
    MEMBLOCK_TEMPORAL_GATE_B2=0
```

实验脚本中的 `b3)` variant 会设置上述组合。B3 不继承 B1/B2 的局部时间
处理逻辑；如果 merged request 在实际代码路径中仍触发 function/tool call，
应以 `construction_calls`/provider usage 记录为准，而不能仅凭“merged”名称
推断 tool calls 必为零。

## 与 B0 的比较边界

B3 的主要变量是 construction 阶段的抽取组织方式。为了避免把收益归因到别的
改动，比较时应固定：

```text
LLM             = gpt-4o-mini
Embedding       = text-embedding-3-small
retrieval       = 当前 baseline 参数
QA model/prompt = 当前 baseline 参数
数据集          = 同一 HaluMem 10-user snapshot
```

本仓库的 `artifacts/10user-v2/` retrieval/QA 是在修复 embedding 后生成的；
该 v2 release 复用了已有 construction artifacts，没有重新产生 construction
token。因此需要区分 source construction token 与 v2 retrieval/QA 结果，不能把
v2 的新增 construction cost 写成一次完整重建。

## 真实源码位置与审阅入口

这里需要明确区分“核心算法代码”和“实验开关”：B3 的 merged extraction 核心
代码已经存在于 sanitized `main`，不是 `halumem-b0-b3-auto-urlfix` 新增的独立
算法。B3 实验通过 runner 将 `MEMBLOCK_MERGED_EXTRACTION=1` 打开。

推荐按下面顺序阅读：

1. [B3 core view branch](https://github.com/jianminYa/SA-Mem-core/tree/halumem-b3-core-view)：只展示 B3 variant 的开关入口；
2. [B2 → B3 incremental compare](https://github.com/jianminYa/SA-Mem-core/compare/halumem-b2-core-view...halumem-b3-core-view)：只包含 `scripts/run_halumem_variant.sh`；
3. [`build_prompts.py` merged prompt（main）](https://github.com/jianminYa/SA-Mem-core/blob/main/build_prompts.py#L73-L150)；
4. [`build_impl_graph.py` merged dispatch（main）](https://github.com/jianminYa/SA-Mem-core/blob/main/build_impl_graph.py#L201-L245)；
5. [`memblock_extractor.py` merged 开关（main）](https://github.com/jianminYa/SA-Mem-core/blob/main/memblock_extractor.py#L449-L459)。

因此不应再使用 `main...halumem-b0-b3-auto-urlfix` 作为 B3 核心代码 compare；它
是包含 runner、报告和实验 artifacts 的集成分支。

本结果仓库的模块导航见 [`code/b3/MODULE_MAP_CN.md`](../code/b3/MODULE_MAP_CN.md)。
