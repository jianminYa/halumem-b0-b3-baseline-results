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

> **关于 GitHub compare：** 本文件在 B1、B2、B3 分支中都保留，是为了让每个结果
> 分支单独打开时也能读懂完整的 B0/B1/B2/B3 流程。因此它不是“当前分支相对上一分支
> 的代码 diff”，在 compare 页面中不会显示为变化文件。要看算法变化，请看
> `SA-Mem-core` 的 focused code compare；要看本文件的真实样本说明，请直接打开当前
> 分支的 `docs/CONSTRUCTION_STAGES_REAL_EXAMPLE_CN.md`。

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

## 1.1 先看“每一次 LLM 请求”的真实形态

前面的表格只给出了字段映射，确实不够直观。下面用另一个同样来自
`artifacts/10user-v2` 的真实 block 展开完整的时序例子。它同时覆盖了 B0 的
function calling、B1 的本地解析、B2 的 gate，以及 B3 的 merged request：

```text
user_id:  2f4b4206-20bc-19a5-a5ed-4d110f91f4db
session:  session_47
raw block: block coverage = session_47, start_idx = 1, end_idx = 3
session window: 2036-02-01T22:02:50 -> 2036-02-02T00:32:50
```

### 原始 block（四个版本都读到同一份）

```text
Feb 01, 2036, 22:02:50 user: Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out. The support from industry leaders was incredible.
Feb 01, 2036, 22:02:50 assistant: Congratulations on the successful launch of GreenWave Innovations, Donna! It's fantastic to hear that industry leaders responded with enthusiasm, positioning you as a prominent figure in sustainable energy. Your commitment to sustainability and innovation truly shines through in GreenWave's mission. I remember you sharing anecdotes about the challenges and triumphs leading up to this moment, emphasizing your dedication to making a global environmental impact. However, I also recall hearing that your dialogue during the launch was filled with a sense of caution and uncertainty about the future of GreenWave Innovations. How are you feeling now about the direction of your company?
Feb 01, 2036, 22:06:04 user: I'm feeling optimistic about the future. The enthusiasm from industry leaders has reinforced my confidence in GreenWave's mission. We've worked hard to ensure our solutions are both innovative and sustainable.
```

下面每个阶段都标注了证据等级：

- **实际落盘**：可以在本仓库 artifact/log 中逐字查看；
- **源码重建**：旧运行没有保存 provider payload，但可以用实际 block 加源码模板精确重建请求结构；
- **schema/结果对照**：原始 LLM response 没有保存，只能展示 prompt 定义的 JSON 结构和最终归一化结果，不能冒充原始 response。

这是当前 artifact 的真实边界：旧 run 保存了最终 MemoryBlock、token usage、split trace 和
B2 gate trace，但没有保存每次 Pass1/Pass2 的完整 prompt 与 `message.content`。

## 1.2 B0：每一阶段实际传什么、返回什么

### B0 Pass1：raw block → mentions

**输入（源码重建，真实 block 已展示）**：请求使用
`PROMPT_DIALOG_EXTRACT`，把上面的完整 raw block 填入模板最后的
`Content to analyze: {text}`。因此 Pass1 输入不是只有最后一句 user message，而是：

```text
Generate a structured analysis of the provided dialog ...

Session window: 2036-02-01T22:02:50 -> 2036-02-02T00:32:50
...原始 block 的完整内容...

Content to analyze:
<上面的 raw block>
```

请求同时挂载 `resolve_temporal_expression` function schema，`temperature=0`，并要求
JSON object。完整模板见 [SA-Mem-core 的 build_prompts.py](https://github.com/jianminYa/SA-Mem-core/blob/halumem-b1-core-view/build_prompts.py#L7-L74)
对应的 `PROMPT_DIALOG_EXTRACT` 定义，构建调用位置见
[build_impl_graph.py](https://github.com/jianminYa/SA-Mem-core/blob/halumem-b1-core-view/build_impl_graph.py#L429-L470)，以及
[SA-Mem-core temporal function schema](https://github.com/jianminYa/SA-Mem-core/blob/halumem-b1-core-view/temporal_resolution_tool.py)。

**输出格式（源码中明确）**：

```json
{
  "keywords": ["keyword1", "keyword2"],
  "topic": "topic phrase",
  "mentions": [
    "One atomic mention sentence",
    "Another atomic mention sentence"
  ]
}
```

旧 run 没有保存这一条 `ps1_raw`，所以这里不把最终 event 反写成“原始 Pass1
response”。最终 artifact 能直接验证的是：B0 确实生成了包含 GreenWave launch、乐观状态、
industry leaders support 等事实的 events；具体见下方 Pass2/assembly 的落盘结果。

### B0 temporal tool：模型提出参数，Python 函数返回日期

当 Pass1 选择调用 tool 时，源码执行的 function 参数形态是：

```json
{
  "observation_time": "2036-02-02T00:32:50",
  "expression": "yesterday"
}
```

这是由 raw block 中的 `Yesterday` 和 session end 得到的真实 temporal case。
现有 `resolve_temporal_expression()` 的确定性返回为：

```json
{
  "start_date": "2036-02-01",
  "end_date": "2036-02-01",
  "day_of_week": "Saturday",
  "resolved_expression": "yesterday (2036-02-01)"
}
```

这一步本身是本地 Python 日期计算，不是一次新的 LLM 请求；旧 run 没有保存原始
OpenAI tool-call message 的 call id，但函数参数和日期结果可以由真实 block、session end
以及当前源码确定性复现。

### B0 follow-up：tool result 被放回上下文，再请求一次 LLM

源码中的消息序列是：

```json
[
  {"role": "user", "content": "<完整 Pass1 prompt + raw block>"},
  {"role": "assistant", "tool_calls": [
    {"function": {"name": "resolve_temporal_expression", "arguments": "<上面的参数>"}}
  ]},
  {"role": "tool", "content": "<上面的日期 JSON>"}
]
```

然后把这组 messages 重新发送给同一个 `gpt-4o-mini`，但移除 `tools` 和
`tool_choice`，要求它给出最终 Pass1 JSON。也就是说 follow-up 不是只发送
`yesterday -> 2036-02-01` 两个短字符串，而是重新携带原始 Pass1 上下文、assistant
tool-call 消息和 tool result；这正是 B0 follow-up token 很高的原因。

**旧 run 的限制**：follow-up 的原始 `message.content` 没有单独落盘；可以审计它发生了
多少次、消耗多少 provider tokens，但不能从当前 artifact 逐字复制那次模型返回。

### B0 Pass2：mentions → typed events

Pass2 使用 `PROMPT_DIALOG_CLASSIFICATION`。源码重建后的输入结构是：

```text
Generate a structured classification of the provided extracted mentions ...
Session window: 2036-02-01T22:02:50 -> 2036-02-02T00:32:50
Mentions JSON:
[
  "<Pass1 输出的 atomic mention 1>",
  "<Pass1 输出的 atomic mention 2>",
  "..."
]
```

要求的返回结构是：

```json
{
  "explicit_mentions": [
    {
      "description": "One sentence description derived from the mention",
      "start_time": "YYYY-MM-DD",
      "end_time": "YYYY-MM-DD",
      "type": "OCCURRENCE|STATE|ATTRIBUTE|INTENTION"
    }
  ]
}
```

旧 run 没有保存 exact `mentions_json` 和 exact `ps2_raw`，但最终归一化的 B0 输出是真实
落盘的。该 block 中与时间表达最直接对应的 event 是：

```json
{
  "event_id": "0_182_e0",
  "description": "Williams Donna launched GreenWave Innovations on February 1, 2036.",
  "event_temporal_type": "OCCURRENCE",
  "time_metadata": {
    "observedTime": "2036-02-02T00:32:50",
    "startTime": "2036-02-01",
    "endTime": "2036-02-01",
    "granularity": "day"
  }
}
```

### B0 assembly：events + raw block → MemoryBlock

最后不是再次调用 LLM，而是 Python assembly/normalization。真实落盘记录的关键结构为：

```json
{
  "user_id": "2f4b4206",
  "block_id": 182,
  "coverage": {"session_id": "session_47", "start_idx": 1, "end_idx": 3},
  "temporal_index": {
    "sessionstart_time": "2036-02-01T22:02:50",
    "sessionend_time": "2036-02-02T00:32:50",
    "block_event_start_time": "2036-02-01",
    "block_event_end_time": "2036-02-02"
  },
  "features": {
    "content_text": "<完整 raw block>",
    "topic_kw_text": "<Pass1 的 topic + keywords>"
  },
  "events": ["<Pass2 explicit_mentions 归一化后的 event objects>"]
}
```

完整真实记录见 [B0 memory_units.jsonl](../artifacts/10user-v2/b0/memory_units.jsonl)，
按 `user_id=2f4b4206`、`coverage.session_id=session_47`、`block_id=182` 定位。

## 1.3 B1：同一个真实 block 如何变成“本地解析”

B1 的关键变化不是删除 Pass2，而是把 B0 Pass1 中的“模型调用 tool + follow-up”改成：

```text
Pass1 LLM（不挂 temporal tools）
  → 输出 mentions + temporal_expressions
  → Python resolve_temporal_expression()
  → 把 resolved_expression 追加到对应 mention
  → 原 Pass2 LLM
```

### B1 Pass1 输入/输出

**输入**仍是同一个完整 raw block，但使用 `PROMPT_DIALOG_EXTRACT_LOCAL_TEMPORAL`。
它明确要求模型只识别并定位相对时间，不自行计算绝对日期，也不调用 tool。

**输出格式**：

```json
{
  "keywords": ["GreenWave Innovations", "sustainability"],
  "topic": "Launch of GreenWave Innovations",
  "mentions": [
    "Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out."
  ],
  "temporal_expressions": [
    {"mention_index": 0, "expression": "Yesterday"}
  ]
}
```

上面使用的是本次真实 raw block 中的真实句子和真实 expression；但由于旧 run 没保存
`ps1_raw`，这段 JSON 是“真实数据对应的输出 schema 示例”，不是声称从 provider log
逐字复制的 response。B1 prompt 的 exact schema 可在
[SA-Mem-core 的 build_prompts.py](https://github.com/jianminYa/SA-Mem-core/blob/halumem-b1-core-view/build_prompts.py#L77-L114)
和 [B1 pipeline 说明](B1_PIPELINE_CN.md) 中核对。

### B1 local resolver 输入/输出

本地函数拿到的值是：

```json
{
  "observation_time": "2036-02-02T00:32:50",
  "expression": "Yesterday",
  "mention_index": 0
}
```

返回：

```json
{
  "start_date": "2036-02-01",
  "end_date": "2036-02-01",
  "resolved_expression": "Yesterday (2036-02-01)"
}
```

然后 mention 变成（供 Pass2 使用）：

```text
Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out. (Yesterday (2036-02-01))
```

这一步没有 provider LLM token。`mention_index` 的存在就是为了回答“多个 mention
分别对应哪个时间表达”：每个表达显式指向一个 zero-based mention。

### B1 Pass2 输入/输出与 assembly

B1 Pass2 的 prompt、输入字段和输出 schema 与 B0 相同；差别仅在于 mentions 中的相对
表达已经被本地函数补上绝对日期。最终真实 event 为：

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

因此 B1 最终 MemoryBlock schema 没变；变化在 Pass1 的输出契约和中间 local resolve。

## 1.4 B2：只改变“能不能调用 tool”，不改变 LLM 的 Pass1 输出格式

B2 先对同一个 raw block 做零 token 的本地 gate：

```python
needs_temporal_tool(block_text) -> bool
```

### B2 Gate 的真实输入/输出

对无相对时间的真实 `session_1/block_0`，落盘日志是：

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

对同一真实 session 的后续 `block_1`，检测到 `now`，落盘为：

```json
{
  "stage": "temporal_gate",
  "session_id": "session_1",
  "block_id": 1,
  "temporal_gate_on": true,
  "temporal_gate_reason": "relative_temporal_expression:now"
}
```

### B2 Gate OFF / ON 的 LLM 输入输出

- **Gate OFF**：Pass1 的 prompt、raw block、JSON schema 与 B0 完全相同；唯一改变是
  `tool_choice="none"`，所以模型直接返回原始 B0 格式的
  `keywords/topic/mentions`，不走 tool/follow-up。
- **Gate ON**：Pass1、tool、follow-up、Pass2 全部沿用 B0；不使用 B1 的
  `temporal_expressions`，也不使用 local resolver。

以真实教育 block 为例，Gate OFF 的 B2 最终 event 是：

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

这说明 B2 的目标是省掉明确不需要日期解析的 tool/follow-up，而不是重新设计
Pass1/Pass2 的 JSON 结构。

## 1.5 B3：一个 merged LLM request 直接输出事件字段

B3 的输入仍然是同一个 raw block 和 session window，但使用
`PROMPT_DIALOG_EXTRACT_MERGED`，一次请求同时要求：

```text
Input:
  session window + timestamps + Persona info + complete raw dialogue

Output:
  keywords
  topic
  events[]:
    description
    type
    start_time
    end_time
```

**B3 的 JSON 输出格式（源码中明确）**：

```json
{
  "keywords": ["keyword1", "keyword2"],
  "topic": "topic phrase",
  "events": [
    {
      "description": "One atomic sentence",
      "type": "OCCURRENCE|STATE|ATTRIBUTE|INTENTION",
      "start_time": "YYYY-MM-DD",
      "end_time": "YYYY-MM-DD"
    }
  ]
}
```

在真实 `session_47` block 上，B3 最终落盘的对应 event 为：

```json
{
  "event_id": "0_183_e0",
  "description": "Williams Donna launched GreenWave Innovations.",
  "event_temporal_type": "OCCURRENCE",
  "time_metadata": {
    "observedTime": "2036-02-02T00:32:50",
    "startTime": "2036-02-01",
    "endTime": "2036-02-02",
    "granularity": "day"
  }
}
```

B3 正常路径没有独立的 Pass2 LLM 请求，但当前 merged prompt 仍可能挂载原有
function schema；是否真的发生 tool call 必须看 provider log，不能仅凭“merged”名称
推断为零。

## 1.6 四个版本的“输入输出”一眼对照

| 版本 | 第一个 LLM 输入 | 第一个 LLM 输出 | temporal 处理 | 第二个 LLM | 最终 assembly 输入 |
|---|---|---|---|---|---|
| B0 | 完整 raw block + two-pass Pass1 prompt + tools | `topic/keywords/mentions`（可能先 tool call） | tool result + follow-up 让 Pass1 完成 mentions | Pass2：mentions → typed events | raw block + topic/keywords + events |
| B1 | 完整 raw block + local-temporal Pass1 prompt，无 tools | `topic/keywords/mentions/temporal_expressions` | Python 按 `mention_index` 解析并回填日期 | 原 B0 Pass2 | raw block + topic/keywords + events |
| B2 | 完整 raw block + 原 B0 Pass1 prompt | 原 B0 `topic/keywords/mentions` | Gate OFF 禁止 tools；Gate ON 完整走 B0 | 原 B0 Pass2 | raw block + topic/keywords + events |
| B3 | 完整 raw block + merged prompt | `topic/keywords/events[type/time]` | merged request 内处理；可能仍挂 tools | 正常路径无独立 Pass2 | raw block + topic/keywords + events |

所以 B1/B2/B3 并不是都“合并成一阶段”：只有 B3 把 Pass1 和 Pass2 的 LLM 请求合并；
B1 仍是两阶段，只把 temporal follow-up 换成本地计算；B2 仍是 B0 两阶段，只减少
不需要 temporal tool 的 block 上的 follow-up。

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
