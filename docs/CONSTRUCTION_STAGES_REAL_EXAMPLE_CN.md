# B0 / B1 / B2 / B3 构建流程与真实样本

本文用仓库中真实跑出的 HaluMem 记录说明四个版本在 construction 阶段每一步
做什么、输入输出是什么，以及它们最后如何落成 MemoryBlock。示例不是手写的
玩具数据，来源是：

```text
artifacts/10user-v2/<variant>/memory_units.jsonl
```

选取的真实样本为：

```text
user_id:   1b846c59-456e-9550-dffd-4d23f1eca81f
session:   session_1
block:     0
```

注意：`memory_units.jsonl` 保存的是最终归一化后的 MemoryBlock。当前 release
没有保存每次 Pass1/Pass2 的完整 provider prompt 和 raw response，只保存了最终
Memory、retrieval/QA 结果以及构建 token 统计。因此本文对中间阶段只展示真实
可审计的字段和最终落盘结果，不把最终 event 反向伪装成原始 LLM JSON。

## 1. 所有版本共享的输入与分段

### 真实 raw block 片段

下面内容直接来自四个版本最终 Memory 的 `features.content_text`，四个版本在
这个样本上使用了相同的原始对话：

```text
Session window: 2025-09-04T09:27:31 -> 2025-09-04T11:57:31

Sep 04, 2025, 09:27:31 user: Hello! I'd like to share my basic personal information with you so you can better understand me and provide more thoughtful help in future conversations.
Sep 04, 2025, 09:27:31 assistant: Hello! Nice to meet you. Please tell me your basic information.
Sep 04, 2025, 09:30:58 user: My name is Williams Daniel, and I am a Male. I was born on 1984-06-16, and I am now 41 years old. I currently live in Philadelphia.
Sep 04, 2025, 09:30:58 assistant: Can you tell me about your educational background?
Sep 04, 2025, 09:43:52 user: Of course. My highest education level is Bachelor, and my major is Film Studies.
```

### Continuity segmentation

每个版本先按消息顺序做 continuity split。真实 trace 中对应的一条输入输出为：

```json
{
  "type": "split_check",
  "session_id": "session_1",
  "prev_msgs": [
    "user: My name is Williams Daniel, and I am a Male. I was born on 1984-06-16, and I am now 41 years old. I currently live in Philadelphia.",
    "assistant: Can you tell me about your educational background?"
  ],
  "curr_msg": "user: Of course. My highest education level is Bachelor, and my major is Film Studies.",
  "decision": "No"
}
```

`decision: No` 表示当前消息继续当前 block。这个样本最终的 coverage 在四个
版本中都是：

```json
{
  "session_id": "session_1",
  "start_idx": 1,
  "end_idx": 5
}
```

这一阶段的 LLM token 计入 `split_check`，不属于 Pass1/Pass2。

## 2. B0：原始 two-pass

### 配置

```text
MEMBLOCK_MERGED_EXTRACTION=0
MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
MEMBLOCK_TEMPORAL_GATE_B2=0
```

### 执行流程

```text
raw block
  → split_check
  → Pass1 extraction
  → （如果模型调用 temporal function）tool result
  → Pass1 follow-up LLM
  → Pass2 classification / temporal metadata
  → MemoryBlock
```

### 各阶段输入输出

| 阶段 | 输入 | 输出 |
|---|---|---|
| Pass1 | raw block、session window | `topic`、`keywords`、`mentions` |
| temporal tool | Pass1 中识别出的 relative expression、session end | 绝对日期或日期范围 |
| follow-up | 原 Pass1 上下文 + tool result | 补全后的 mentions |
| Pass2 | session window + mentions | `description`、`event_temporal_type`、`startTime`、`endTime` |
| assembly | topic、keywords、events、raw block | 最终 MemoryBlock |

### 真实最终输出

这个 B0 Memory 的 `topic_kw_text` 为：

```text
Personal background and educational information Williams Daniel, Philadelphia, Bachelor, Film Studies, INTJ, historically accurate films, international awards, Cannes
```

对应教育事实的真实 event 为：

```json
{
  "event_id": "0_0_e4",
  "description": "Williams Daniel's highest education level is Bachelor.",
  "event_temporal_type": "ATTRIBUTE",
  "time_metadata": {
    "observedTime": "2025-09-04T11:57:31",
    "startTime": "2025-09-04",
    "endTime": "2025-09-04",
    "granularity": "day"
  }
}
```

## 3. B1：local temporal resolution

### 配置

```text
MEMBLOCK_MERGED_EXTRACTION=0
MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=1
MEMBLOCK_TEMPORAL_GATE_B2=0
```

### 执行流程

```text
raw block
  → split_check
  → B1 Pass1：topic / keywords / mentions / temporal_expressions
  → 本地 resolve_temporal_expression()
  → 将绝对日期补到对应 mention 的处理结果
  → Pass2（不变）
  → MemoryBlock（schema 不变）
```

### Pass1 中间输出结构

B1 的新增字段是 mention 与时间表达的显式映射：

```json
{
  "keywords": ["GreenWave Innovations", "sustainability"],
  "topic": "Launch of GreenWave Innovations",
  "mentions": [
    "Yesterday marked the official launch of GreenWave Innovations."
  ],
  "temporal_expressions": [
    {"mention_index": 0, "expression": "Yesterday"}
  ]
}
```

上面结构对应真实 B1 样本中的字段定义；日期计算本身不由这个 JSON 猜测，
而是调用现有 `resolve_temporal_expression()`，观察时间取 session end。

### 真实相对时间样本

B1 的真实输入片段来自 `session_47`：

```text
Feb 01, 2036, 22:02:50 user: Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out. The support from industry leaders was incredible.
```

该 block 的 session end 是 `2036-02-02T00:32:50`。B1 最终落盘的 event 为：

```json
{
  "event_id": "0_180_e0",
  "description": "Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out.",
  "event_temporal_type": "OCCURRENCE",
  "time_metadata": {
    "observedTime": "2036-02-02T00:32:50",
    "startTime": "2036-02-01",
    "endTime": "2036-02-01",
    "granularity": "day"
  }
}
```

也就是说，原始相对表达保留在 description 中，但实际日期进入
`time_metadata.startTime/endTime`。

### fallback

若 `temporal_expressions` 不是合法列表、mention index 越界、表达式没有对应
mention、session 日期无法解析，B1 不静默采用错误日期，而是重新走 B0 的
tool + follow-up 路径。Pass2 和最终 MemoryBlock schema 不变。

## 4. B2：temporal gate

### 配置

```text
MEMBLOCK_MERGED_EXTRACTION=0
MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
MEMBLOCK_TEMPORAL_GATE_B2=1
```

### 执行流程

```text
raw block
  → split_check
  → 本地 needs_temporal_tool(block_text)
       ├─ Gate OFF：明确没有 relative time
       │    → 原始 Pass1，禁止 tool call
       │    → Pass2
       └─ Gate ON：发现时间表达或无法确定
            → 完整 B0 Pass1
            → temporal tool
            → follow-up LLM
            → Pass2
  → MemoryBlock
```

B2 不使用 B1 的 `temporal_expressions` schema，也不使用 B1 local resolver。
B2 只改变“当前 block 是否允许 temporal tool”，其余 prompt、mentions、Pass2
和 MemoryBlock 逻辑保持 B0。

### 真实 gate 日志

真实 B2 gate 日志中，`session_1 / block_0` 的结果为：

```json
{
  "stage": "temporal_gate",
  "session_id": "session_1",
  "block_id": 0,
  "temporal_gate_on": false,
  "temporal_gate_reason": "no_relative_temporal_expression_detected",
  "temporal_tool_called": false,
  "pass1_tool_followup": false,
  "usage_source": "local_gate_no_llm"
}
```

同一个真实 session 的后续 `block_1` 因检测到 `now`，日志为 Gate ON：

```json
{
  "stage": "temporal_gate",
  "session_id": "session_1",
  "block_id": 1,
  "temporal_gate_on": true,
  "temporal_gate_reason": "relative_temporal_expression:now"
}
```

### 真实 Gate OFF 最终输出

`session_1 / block_0` 的 B2 最终教育 event 为：

```json
{
  "event_id": "0_0_e3",
  "description": "Williams Daniel's highest education level is Bachelor.",
  "event_temporal_type": "ATTRIBUTE",
  "time_metadata": {
    "observedTime": "2025-09-04T11:57:31",
    "startTime": "2025-09-04",
    "endTime": "2025-09-04",
    "granularity": "day"
  }
}
```

## 5. B3：merged extraction

### 配置

```text
MEMBLOCK_MERGED_EXTRACTION=1
MEMBLOCK_LOCAL_TEMPORAL_RESOLUTION=0
MEMBLOCK_TEMPORAL_GATE_B2=0
```

### 执行流程

```text
raw block
  → split_check
  → 一个 merged extraction LLM request
       ├─ topic
       ├─ keywords
       └─ events: description / type / start_time / end_time
  → 输出归一化
  → MemoryBlock
```

B3 不再执行正常的 Pass2 classification call。它直接让一个 merged request
同时生成 Pass1 的主题/关键词和 Pass2 的事件/时间字段，然后复用已有 assembly
代码落盘。当前实现的 merged request 仍可能保留 function schema，因此不能仅
凭“merged”名称断言 tool call 一定为零，实际数量以 provider log 为准。

### 真实最终输出

同一 `session_1 / block_0` 的 B3 `topic_kw_text` 为：

```text
Personal information sharing Williams Daniel, Philadelphia, Film Studies, Bachelor, INTJ, historically accurate films, international awards
```

教育事实对应的真实 event 为：

```json
{
  "event_id": "0_0_e4",
  "description": "Williams Daniel's highest education level is Bachelor.",
  "event_temporal_type": "ATTRIBUTE",
  "time_metadata": {
    "observedTime": "2025-09-04T11:57:31",
    "startTime": "2025-09-04",
    "endTime": "2025-09-04",
    "granularity": "day"
  }
}
```

## 6. 同一个真实样本的最终结果对比

| Variant | coverage | events 数量 | 教育事实最终描述 |
|---|---|---:|---|
| B0 | `session_1, 1–5` | 10 | `highest education level is Bachelor` |
| B1 | `session_1, 1–5` | 9 | `highest education level is Bachelor` |
| B2 | `session_1, 1–5` | 9 | `highest education level is Bachelor` |
| B3 | `session_1, 1–5` | 8 | `highest education level is Bachelor` |

这里的 events 数量差异是模型抽取/归并结果差异，不代表四个版本的 schema
不同；四个版本都最终写入相同的 `features`、`events`、`time_metadata` 结构。
这个单样本只用于解释流程，不能作为总体质量结论。

## 7. 构建 token 如何对应到阶段

```text
B0: split_check + pass1_extract + pass1_tool_followup + pass2_classify
B1: split_check + pass1_extract + temporal_local_resolve(本地零 provider token)
    + fallback follow-up（仅异常时）+ pass2_classify
B2: split_check + local gate(零 provider token) + pass1
    + tool/follow-up（仅 Gate ON）+ pass2_classify
B3: split_check + merged_extract（正常 Pass2 不再单独调用）
```

QA、judge、retrieval parser 和 embedding 不计入上述 construction cost。

## 8. 结果与源码位置

- B0：[`artifacts/10user-v2/b0/memory_units.jsonl`](../artifacts/10user-v2/b0/memory_units.jsonl)
- B1：[`artifacts/10user-v2/b1/memory_units.jsonl`](../artifacts/10user-v2/b1/memory_units.jsonl)
- B2：[`artifacts/10user-v2/b2/memory_units.jsonl`](../artifacts/10user-v2/b2/memory_units.jsonl)
- B3：[`artifacts/10user-v2/b3/memory_units.jsonl`](../artifacts/10user-v2/b3/memory_units.jsonl)

核心源码审阅入口：

- [B1 core view](https://github.com/jianminYa/SA-Mem-core/compare/main...halumem-b1-core-view)
- [B2 incremental core view](https://github.com/jianminYa/SA-Mem-core/compare/halumem-b1-core-view...halumem-b2-core-view)
- [B3 configuration view](https://github.com/jianminYa/SA-Mem-core/compare/halumem-b2-core-view...halumem-b3-core-view)
