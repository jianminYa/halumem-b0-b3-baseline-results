# HaluMem B1 相对 B0 的流程修改说明

本文说明 HaluMem-Medium 实验中 B1 相比 B0 的 construction 修改、每一步的输入输出、local temporal resolver 的实现，以及何时回退到 B0 原始路径。

> 本文只讨论 B0 与 B1，不改变已经完成的实验结果。

## 1. 一句话概括

B1 没有删除 Pass2，也没有改变最终 Memory/MemBlock schema。它只改变了 Pass1 的时间处理方式：

```text
B0:
Pass1 LLM
  → temporal function call（如果模型调用）
  → tool result
  → Pass1 follow-up LLM
  → Pass2 LLM
  → Memory

B1:
Pass1 LLM（输出 temporal_expressions，但不调用 tool）
  → 本地 Python temporal resolver
  → 把绝对日期附加到原始 mention
  → 原有 Pass2 LLM
  → Memory

如果 B1 的本地结果不可靠：
B1 Pass1
  → 回退到 B0 的原始 Pass1 + temporal tool + follow-up
  → 原有 Pass2
```

B1 的目标是：对简单、可确定的相对时间表达，去掉一次远程 follow-up；对无法安全处理的情况，不静默猜日期，而是保留 B0 路径。

## 2. B0 原始流程

### 2.1 Block 输入

每个 block 送入 Pass1 的文本包括：

```text
Session window: <session_start> -> <session_end>
Persona info: ...
<message timestamp> user: ...
<message timestamp> assistant: ...
...
```

其中 `session_end` 被作为相对时间的 observation time。原始对话文本和 Persona info 都保留。

### 2.2 B0 Pass1 输出

B0 的目标是抽取主题、关键词和原子 mentions：

```json
{
  "keywords": ["fashion", "historical motifs"],
  "topic": "Historical motifs in fashion",
  "mentions": [
    "Yesterday, I attended a local fashion exhibition."
  ]
}
```

原始 Pass1 prompt 同时启用 `resolve_temporal_expression` function schema。模型如果识别到相对时间，可能请求：

```json
{
  "observation_time": "2030-11-29T22:04:55",
  "expression": "yesterday"
}
```

代码本地执行 function 后，把结果追加到 messages，再发送一次 follow-up LLM 请求，让模型继续完成最终 Pass1 JSON。例如，mention 可能变为：

```text
Yesterday, I attended a local fashion exhibition. (yesterday (2030-11-28))
```

temporal function 执行本身是本地 Python 计算；真正产生额外 provider token 的是带有 tool 结果上下文的 follow-up LLM 请求。

### 2.3 B0 Pass2 输入和输出

Pass2 接收 Pass1 的 mentions 和 session 时间窗口：

```json
{
  "session_start_time": "2030-11-29T20:38:25",
  "session_end_time": "2030-11-29T22:04:55",
  "mentions": [
    "Yesterday, I attended a local fashion exhibition. (yesterday (2030-11-28))"
  ]
}
```

Pass2 输出事件类型和时间字段：

```json
{
  "explicit_mentions": [
    {
      "description": "Yesterday, I attended a local fashion exhibition.",
      "type": "OCCURRENCE",
      "start_time": "2030-11-28",
      "end_time": "2030-11-28"
    }
  ]
}
```

随后结果被规范化为最终 Memory/MemBlock。B1 保留这一步不变。

## 3. B1 具体改了什么

### 3.1 B1 的 Pass1 输入

B1 仍然接收完整 block，包含：

```text
session window
timestamps
Persona info
raw dialogue
```

没有删除 raw dialogue，也没有只保留包含答案的部分。B1 的主要变化是使用了一个不同的 Pass1 prompt，并明确要求模型：

1. 抽取和 B0 同样的 `keywords`、`topic`、`mentions`；
2. 不自己计算绝对日期；
3. 额外列出 mentions 中出现的显式相对时间表达；
4. 给每个表达标记它属于哪个 mention。

### 3.2 B1 Pass1 输出

B1 的中间 JSON 增加了 `temporal_expressions`：

```json
{
  "keywords": ["fashion", "historical motifs"],
  "topic": "Historical motifs in fashion",
  "mentions": [
    "Yesterday, I attended a local fashion exhibition."
  ],
  "temporal_expressions": [
    {
      "mention_index": 0,
      "expression": "Yesterday"
    }
  ]
}
```

与 B0 的关键区别是：B1 这次 Pass1 请求不启用 temporal function calling。B1 Pass1 只负责识别和定位表达，不负责调用远程 tool，也不负责在 prompt 内计算绝对日期。

### 3.3 B1 本地处理后的 mentions

本地 resolver 根据 `session_end` 和 `expression` 计算日期，然后把人类可读的解析结果追加到对应 mention：

```text
输入 mention:
Yesterday, I attended a local fashion exhibition.

本地结果:
yesterday (2030-11-28)

送入 Pass2 的 mention:
Yesterday, I attended a local fashion exhibition. (yesterday (2030-11-28))
```

之后 B1 继续使用 B0 原有 Pass2 prompt 和最终 Memory/MemBlock 规范化逻辑。

## 4. Local temporal resolver 如何实现

### 4.1 输入和输出

本地 resolver 的接口可以抽象为：

```python
resolve_temporal_expression(
    observation_time="2030-11-29",
    expression="yesterday",
)
```

输出：

```json
{
  "start_date": "2030-11-28",
  "end_date": "2030-11-28",
  "day_of_week": "Friday",
  "resolved_expression": "yesterday (2030-11-28)"
}
```

它使用 Python `datetime` / `timedelta` 和日历规则，不访问 LLM API，也不产生 provider token。

### 4.2 observation time 的处理

HaluMem session 时间可能带有完整时间戳，例如：

```text
2030-11-29T22:04:55
```

B1 先提取日期部分：

```text
2030-11-29
```

再把它作为相对表达的计算锚点：

```text
session_end = 2030-11-29T22:04:55
expression = yesterday
result = 2030-11-28
```

### 4.3 当前 resolver 的规则类型

当前实现覆盖的主要规则包括：

```text
yesterday
today
this morning / this afternoon / this evening / tonight
last Monday ... last Sunday
last week
last month
last year
```

星期表达会根据 observation date 计算上一个对应星期几；`last month` 和 `last year` 使用日历边界计算，而不是简单地把月份减一。

例如：

```text
observation_time = 2028-02-01
expression = last month

start_date = 2028-01-01
end_date = 2028-01-31
```

对于 resolver 没有明确实现的表达，函数可能返回 observation date 并附带 warning。B1 不接受这种 warning 结果作为成功解析，而是进入 fallback，避免把未解析的表达伪装成已解析日期。

## 5. B1 什么时候直接 local resolve

B1 只有在以下条件都满足时才直接使用 local result：

1. Pass1 返回了可解析的 JSON；
2. `mentions` 是有效的字符串列表；
3. `temporal_expressions` 是有效列表；
4. 每个相对时间表达都映射到了合法的 `mention_index`；
5. `mention_index` 没有越界或重复；
6. expression 非空；
7. session_end 可以转换为有效的日期；
8. resolver 返回了没有 warning 的解析结果；
9. 解析结果包含非空的 `resolved_expression`。

例如：

```json
{
  "mentions": [
    "Yesterday, I attended an exhibition."
  ],
  "temporal_expressions": [
    {"mention_index": 0, "expression": "Yesterday"}
  ]
}
```

当 session_end 有效且 resolver 能处理 `Yesterday` 时，直接本地解析，不启用 function calling，也不会产生 Pass1 follow-up。

## 6. B1 什么时候 fallback 到 B0

fallback 的原则是：**只要本地结果有可能改变原始时间语义，就不继续使用本地结果。**

### 6.1 Pass1 JSON 或字段结构异常

例如：

```text
Pass1 返回空字符串
Pass1 返回非法 JSON
mentions 不是 list
temporal_expressions 不是 list
```

这时 B1 无法安全验证中间结果，会重新使用 B0 的原始 Pass1 prompt 和 tool-calling 路径。

### 6.2 相对表达没有完整映射

例如 mention 中出现：

```text
I visited the museum yesterday and returned last Sunday.
```

但 Pass1 只返回：

```json
{
  "temporal_expressions": [
    {"mention_index": 0, "expression": "yesterday"}
  ]
}
```

第二个相对表达没有被列出，B1 会判定 coverage 不完整，进入 fallback，而不是只解析一半。

### 6.3 mention_index 不合法

以下情况都会 fallback：

```text
mention_index 越界
mention_index 不是整数
同一个 mention_index 重复映射
expression 为空
```

### 6.4 observation time 不合法

例如 session window 缺失或无法提取出合法日期：

```text
session_end = Unknown
```

此时不能可靠计算 `yesterday` 或 `last Sunday`，因此回到 B0。

### 6.5 resolver 不支持或拒绝表达

例如：

```text
two weeks before the conference
a while ago
around the holidays
```

这些表达可能需要另一个事件作为锚点，或者缺少足够信息。如果 resolver 返回 warning 或无法给出明确结果，B1 不使用 observation date 冒充答案，而是 fallback。

### 6.6 fallback 的实际路径

fallback 会重新发送 B0 原始 Pass1 prompt，并重新启用 temporal function schema：

```text
B1 local Pass1
  → 发现本地结果不可靠
  → B0 original Pass1
  → temporal tool（如果模型调用）
  → B0 Pass1 follow-up（如果发生 tool call）
  → 原有 Pass2
```

fallback 产生的 follow-up 在 token log 中单独标记为：

```text
pass1_tool_followup_fallback
```

因此 fallback 不是把错误日期继续传下去，而是放弃本地结果，重新走原始路径。

## 7. B0 与 B1 的输入输出对照

| 阶段 | B0 | B1 |
|---|---|---|
| Block 输入 | 完整 session window、Persona、原始 dialogue | 相同 |
| Pass1 prompt | 原始抽取 prompt | 增加 temporal expression 识别和 mention 映射要求 |
| Pass1 输出 | `keywords/topic/mentions` | `keywords/topic/mentions/temporal_expressions` |
| Pass1 tool | 允许模型调用 | 正常 local path 禁止调用；fallback 时恢复 |
| 时间计算 | 本地 tool 执行后由 follow-up 整合 | local Python resolver 直接计算 |
| Pass1 follow-up | tool call 后可能发生 | local 成功时没有；fallback 时保留 |
| Pass2 | 原始 Pass2 | 完全保留 |
| 最终 Memory schema | 原始 schema | 相同 |
| Raw dialogue | 保留 | 保留 |

## 8. 实验中的实际例子

下面的例子来自 B1 source run 的实际 instrumentation / Memory artifact。

### 例子 A：local resolve 成功

```text
session_id: session_37
block_id: 144
session_end: 2030-11-29T22:04:55
expression: Yesterday
```

B1 local resolver 记录：

```json
{
  "expression": "Yesterday",
  "mention_index": 0,
  "resolved_expression": "yesterday (2030-11-28)",
  "fallback_used": false,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0
}
```

对应最终 event 的时间是：

```json
{
  "description": "Yesterday, I attended a local fashion exhibition and stumbled upon graphic tees featuring historical motifs.",
  "event_temporal_type": "OCCURRENCE",
  "time_metadata": {
    "observedTime": "2030-11-29T22:04:55",
    "startTime": "2030-11-28",
    "endTime": "2030-11-28",
    "granularity": "day"
  }
}
```

这个最终结果可以在 [B1 memory_units.jsonl](../artifacts/10user-v2/b1/memory_units.jsonl) 中查看。

### 例子 B：local 结果不能安全使用，进入 fallback

当 mention 中包含相对时间，但 Pass1 的 `temporal_expressions` 没有覆盖所有表达时，instrumentation 会记录：

```json
{
  "stage": "temporal_local_resolve",
  "success": false,
  "fallback_used": true,
  "reason": "unmapped_relative_expression"
}
```

随后重新执行原始 B0 Pass1，并将额外请求记录为：

```json
{
  "stage": "pass1_tool_followup_fallback"
}
```

这类 block 不会因为 B1 的本地分支失败而直接丢弃时间处理。

## 9. Token 统计含义

本地 resolver 的统计记录明确标记为：

```text
model: local-temporal-resolver
prompt_tokens: 0
completion_tokens: 0
total_tokens: 0
provider_usage_available: false
usage_source: local_no_llm
```

HaluMem source run 的 B1 统计为：

| Stage | Provider calls | Provider total tokens |
|---|---:|---:|
| split / continuity | 53,857 | 11,239,700 |
| Pass1 extract | 6,135 | 10,550,762 |
| local temporal instrumentation | 2,401 records | 0 |
| fallback follow-up | 1,184 | 3,179,076 |
| Pass2 classify | 4,948 | 6,524,982 |
| total | — | 31,494,520 |

这里的 `temporal_local_resolve` 是本地尝试/审计记录，其中既可能有成功记录，也可能有触发 fallback 的失败记录；它不是 provider LLM call 数量。

相比 B0，B1 的主要节省来自：

```text
部分 block 不再执行 Pass1 temporal follow-up
```

而不是删除 Pass2，也不是删除 split/continuity 阶段。

## 10. B1 的边界和风险

B1 的 fallback 能保护“本地解析失败”的情况，但不能证明所有时间都一定正确。尤其要区分：

```text
Pass1 识别了表达，但 local resolver 解析失败
→ 可以 fallback

Pass1 根本没有识别出原始 dialogue 中的相对表达
→ 后续没有输入给 local resolver，这是 B1 的残余风险
```

因此 B1 的实验审计需要同时关注：

```text
local resolve success
fallback count
unmapped relative expression
时间 metadata 是否与 B0 一致
retrieval Hit@K
QA correctness
```

B1 不是把 B0 的时间逻辑完全替换为规则系统，而是把可安全处理的部分搬到本地，把不确定部分交还给 B0。

## 11. 与 B2、B3 的区别

```text
B1：改变 Pass1 输出格式，并加入 local resolver；Pass2 保留。
B2：不改 Pass1 prompt/schema，只在调用前决定是否允许 temporal tool；Pass2 保留。
B3：把 Pass1 和 Pass2 合并为 merged extraction；最终 schema 保留，但独立 Pass2 消失。
```

所以 B1 的行为变化小于 B3，但比 B2 更改了 Pass1 的中间输出协议。
