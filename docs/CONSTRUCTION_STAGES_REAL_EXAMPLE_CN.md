# HaluMem B0 / B1 / B2 / B3：构建流程与真实 request / response

本文只保留一条清晰主线：同一个真实 raw block 在四个 variant 中如何被处理。
每个 variant 的关键 API request 和 response 都放在独立的 `<details>` 折叠框中，点击标题即可展开；
超长 raw block 只保留必要片段，完整运行产物仍在 artifacts 中。

> 本文件在 B1、B2、B3 结果分支中保持一致，方便单独打开任一分支阅读。它是说明文档，
> 不是当前分支相对上一分支的完整 code diff。

## 1. 先看结论

| Variant | 核心变化 | 是否保留 Pass2 | 是否使用 B1 local resolver |
|---|---|---:|---:|
| B0 | 原始 two-pass：Pass1 → temporal tool/follow-up → Pass2 | 是 | 否 |
| B1 | Pass1 输出 `temporal_expressions`，本地按 `mention_index` 解析；失败时回退 B0 | 是 | 是 |
| B2 | 不改 B0 prompt/schema，只在 Pass1 前 gate 是否允许 tool | 是 | 否 |
| B3 | 一个 merged extraction request 直接输出 events | 否（正常路径） | 否 |

四个版本都处理完整 raw block，都保留最终 Memory/MemBlock schema。主要差别是：

```text
B0: Pass1 → tool → follow-up → Pass2
B1: Pass1(+temporal_expressions) → local resolver → Pass2
B2: local gate → [B0 原始路径 / B0 direct path] → Pass2
B3: merged extraction request → events
```

## 2. 最新 10-user-v2 实验结果

以下来自 `reports/HALUMEM_10USER_V2_RESULTS.json`：10 users、1722 questions；QA 为一次
评测。构建 token 是按 source full run 和 10-user memory-unit 比例得到的 subset estimate，
不是 provider 对每个 user 的精确 usage attribution。

| Variant | Memory units | Construction tokens | 相比 B0 | Hit@1 | Hit@5 | Hit@10 | Hit@20 | MRR | Mean gold rank | QA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | 2,434 | 19,578,022 | — | 35.25% | 54.74% | 61.41% | 68.56% | 0.4479 | 32.85 | 928/1722 = 53.89% |
| B1 | 2,405 | 15,304,975 | -21.83% | 34.32% | 53.49% | 59.86% | 67.08% | 0.4374 | 33.97 | 947/1722 = 54.99% |
| B2 | 2,427 | 15,901,285 | -18.78% | 35.17% | 54.81% | 61.80% | 69.02% | 0.4466 | 33.00 | 923/1722 = 53.60% |
| B3 | 2,445 | 14,613,505 | -25.36% | 34.47% | 53.73% | 59.78% | 66.77% | 0.4373 | 35.17 | 930/1722 = 54.01% |

B1 的 QA 比 B0 高 1.10 个百分点，但 Hit@10 和 MRR 略低。因此可以提出一个合理但尚未
证实的解释：B1 通过 `mention_index` 显式绑定相对时间，并在进入 Pass2 前确定性地补回日期，
可能让时间证据更稳定；这不等于证明 B1 的 QA 提升由该机制单独造成。QA 只运行一次，且
B0/B1 的 memory 内容存在差异，仍需重复 QA 和 relative-time 子集分析。

原始结果：

- [`HALUMEM_10USER_V2_RESULTS.json`](../reports/HALUMEM_10USER_V2_RESULTS.json)
- [`10USER_V2_REPAIRED_REPORT.md`](../reports/10USER_V2_REPAIRED_REPORT.md)

## 3. 共同真实样本

下面的 request/response replay 使用同一个 GreenWave block：

```text
Session window: 2036-02-01T22:02:50 -> 2036-02-02T00:32:50

user: Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out. The support from industry leaders was incredible.
assistant: Congratulations on the successful launch of GreenWave Innovations, Donna! ... How are you feeling now about the direction of your company?
user: I'm feeling optimistic about the future. The enthusiasm from industry leaders has reinforced my confidence in GreenWave's mission. We've worked hard to ensure our solutions are both innovative and sustainable.
```

实际 block 还包含该 session 的 persona info；这里仅展示与时间和构建流程相关的对话片段。

## 4. 真实 request / response（点击标题展开）

### B0：原始 tool path

<details>
<summary>展开：B0 Pass1 request → tool-call response → tool response → follow-up response</summary>

Pass1 request 的关键外层结构：

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0,
  "response_format": {"type": "json_object"},
  "tools": ["resolve_temporal_expression function schema"],
  "tool_choice": "auto",
  "messages": [
    {
      "role": "user",
      "content": "<原始 B0 Pass1 prompt + session window + 完整 raw block>"
    }
  ]
}
```

本次真实 Pass1 response 不是普通 JSON，而是：

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_axVgoGrEQ2rYcq0kTe139DJ2",
      "type": "function",
      "function": {
        "name": "resolve_temporal_expression",
        "arguments": "{\"expression\":\"yesterday\",\"observation_time\":\"2036-02-02T00:32:50\"}"
      }
    },
    {
      "id": "call_dVieHdN7sbBOmzJix79xFD7k",
      "type": "function",
      "function": {
        "name": "resolve_temporal_expression",
        "arguments": "{\"expression\":\"the future\",\"observation_time\":\"2036-02-02T00:32:50\"}"
      }
    }
  ]
}
```

Python 执行工具后追加两个 tool messages：

```json
[
  {
    "role": "tool",
    "tool_call_id": "call_axVgoGrEQ2rYcq0kTe139DJ2",
    "content": "{\"start_date\":\"2036-02-01\",\"end_date\":\"2036-02-01\",\"day_of_week\":\"Saturday\",\"resolved_expression\":\"yesterday (2036-02-01)\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_dVieHdN7sbBOmzJix79xFD7k",
    "content": "{\"start_date\":\"2036-02-02\",\"end_date\":\"2036-02-02\",\"day_of_week\":\"Saturday\",\"resolved_expression\":\"the future (2036-02-02)\",\"warning\":\"Could not parse expression 'the future', using observation time as fallback\"}"
  }
]
```

注意：`yesterday (2036-02-01)` 出现在 **tool response 的 content** 中，不是第一次
assistant response 的 `content` 中。随后移除 `tools/tool_choice`，重新发送完整 messages，
得到 follow-up response。下面保留本次真实 response 中与时间和构建流程直接相关的字段：

```json
{
  "keywords": ["GreenWave Innovations", "sustainability", "e-waste", "entrepreneurial", "technology"],
  "topic": "Launch of GreenWave Innovations and its sustainability mission",
  "mentions": [
    "Williams Donna launched GreenWave Innovations on February 1, 2036.",
    "Williams Donna felt incredible support from industry leaders during the launch of GreenWave Innovations.",
    "Williams Donna is optimistic about the future (2036-02-02).",
    "Williams Donna's commitment to sustainability and innovation is reflected in GreenWave's mission.",
    "Williams Donna aims to develop a global network for refurbishing and reselling electronic devices, reducing e-waste by 50% worldwide."
  ]
}
```

这里 follow-up LLM 根据原始 messages、tool_call_id 和多个 tool messages 重新生成 mentions；
源码中没有 `mention_index` 字段，B0 依赖模型把日期结果重新写入正确的 mention。

</details>

### B1：Pass1 识别表达，本地解析，再进入原 Pass2

<details>
<summary>展开：B1 Pass1 request → response → local resolver → Pass2 request/response</summary>

B1 Pass1 request：

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0,
  "response_format": {"type": "json_object"},
  "tool_choice": "none",
  "messages": [
    {
      "role": "user",
      "content": "<B1 local-temporal Pass1 prompt + session window + 完整 raw block>"
    }
  ]
}
```

B1 Pass1 response：

```json
{
  "keywords": ["GreenWave Innovations", "sustainability", "launch", "optimistic", "industry leaders"],
  "topic": "Launch of GreenWave Innovations",
  "mentions": [
    "Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out.",
    "The support from industry leaders was incredible.",
    "I'm feeling optimistic about the future.",
    "The enthusiasm from industry leaders has reinforced my confidence in GreenWave's mission.",
    "We've worked hard to ensure our solutions are both innovative and sustainable."
  ],
  "temporal_expressions": [
    {"mention_index": 0, "expression": "Yesterday"}
  ]
}
```

local resolver 是本地 Python 调用，不产生 LLM token：

```json
{
  "input": {
    "mention_index": 0,
    "expression": "Yesterday",
    "observation_time": "2036-02-02T00:32:50"
  },
  "output": {
    "start_date": "2036-02-01",
    "end_date": "2036-02-01",
    "resolved_expression": "Yesterday (2036-02-01)"
  }
}
```

因此送给 Pass2 的第一个 mention 会带上：

```text
Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out. (Yesterday (2036-02-01))
```

B1 Pass2 request 仍使用 B0 的 classification prompt、模型和 response format，只是输入的
mentions 已经被本地 resolver 按 `mention_index` 补充日期：

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0,
  "response_format": {"type": "json_object"},
  "messages": [
    {
      "role": "user",
      "content": "<原 B0 Pass2 prompt + session window + local-resolved mentions>"
    }
  ]
}
```

B1 Pass2 response 的真实结构仍是原 schema；下面保留与本例时间字段直接相关的 response 片段：

```json
{
  "explicit_mentions": [
    {
      "description": "Yesterday marked the official launch of GreenWave Innovations, and I couldn't be happier with how everything turned out.",
      "start_time": "2036-02-01",
      "end_time": "2036-02-01",
      "type": "OCCURRENCE"
    },
    {
      "description": "The support from industry leaders was incredible.",
      "start_time": "2036-02-01T22:02:50",
      "end_time": "2036-02-02T00:32:50",
      "type": "STATE"
    }
  ]
}
```

</details>

### B2：本地 gate，B0 路径不变

<details>
<summary>展开：B2 gate → Gate OFF request/response；Gate ON 复用 B0 request/response</summary>

Gate 输入是 raw block 的本地文本检查，输出只有是否允许 temporal tool：

```json
{
  "temporal_gate_on": false,
  "temporal_gate_reason": "no_relative_temporal_expression_detected",
  "temporal_tool_called": false
}
```

Gate OFF 时，request 仍是完整 B0 Pass1 prompt + raw block，只增加：

```json
{"tool_choice": "none"}
```

response 是普通 B0 `topic/keywords/mentions` JSON，不改变 B0 schema。Gate ON 时完全复用
B0 的 `Pass1 → tool → follow-up → Pass2`，不使用 B1 的 `temporal_expressions` 或 local resolver。

Gate OFF 的真实 direct response 结构示例：

```json
{
  "keywords": ["Williams Daniel", "Philadelphia", "Film Studies", "INTJ"],
  "topic": "Personal information sharing and educational background",
  "mentions": [
    "Williams Daniel is a Male.",
    "Williams Daniel currently lives in Philadelphia.",
    "Williams Daniel's highest education level is Bachelor.",
    "Williams Daniel's major is Film Studies."
  ]
}
```

</details>

### B3：一个 merged extraction request

<details>
<summary>展开：B3 merged request → merged response</summary>

B3 request：

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0,
  "response_format": {"type": "json_object"},
  "tools": ["resolve_temporal_expression function schema"],
  "tool_choice": "auto",
  "messages": [
    {
      "role": "user",
      "content": "<merged extraction prompt + session window + 完整 raw block>"
    }
  ]
}
```

本次真实 replay 没有返回 tool call，直接返回 merged events；下面保留真实 response 中的代表性事件：

```json
{
  "keywords": ["GreenWave Innovations", "sustainability", "e-waste", "industry leaders"],
  "topic": "Launch of GreenWave Innovations and its impact on sustainability",
  "events": [
    {
      "description": "Williams Donna launched GreenWave Innovations.",
      "type": "OCCURRENCE",
      "start_time": "2036-02-01T22:02:50",
      "end_time": "2036-02-02T00:32:50"
    },
    {
      "description": "Williams Donna has a Bachelor's degree in Business Administration.",
      "type": "ATTRIBUTE",
      "start_time": "2036-02-01T22:02:50",
      "end_time": "2036-02-02T00:32:50"
    }
  ]
}
```

B3 正常路径没有独立 Pass2；若 provider 实际返回 tool call，当前通用 `chat_completion()`
仍可能执行 tool 并 follow-up。因此 B3 的 call 数和 token 仍应以 provider instrumentation
为准，不能只根据 prompt 名称判断。

</details>

## 5. 为什么 B1 可能比 B0 QA 高

B0 的 temporal tool 返回的是“表达式 → 日期”结果，例如：

```text
yesterday → 2036-02-01
```

但 B0 的 tool 参数没有 `mention_index`。当一个 block 有多个时间表达时，follow-up LLM
需要结合原始 block、assistant tool calls、多个 tool messages，自行决定哪个日期应写入
哪个 mention。B1 则让 Pass1 直接返回：

```text
mention_index=0, expression="Yesterday"
```

本地 resolver 得到日期后，直接回填对应 mention，再交给相同的 Pass2。这样可能减少日期
与 mention 错配，即使整体 retrieval recall 没有提升，也可能改善最终 QA context 的时间
语义。这个机制解释是合理假设，不是由当前一次 QA 运行单独证明的结论。

## 6. 代码、结果与进一步阅读

- B1 详细流程与 fallback：[`docs/B1_VS_B0_PIPELINE_CN.md`](B1_VS_B0_PIPELINE_CN.md)
- B3 详细流程：[`docs/B3_PIPELINE_CN.md`](B3_PIPELINE_CN.md)
- B1/B2/B3 结果 artifacts：[`artifacts/10user-v2/`](../artifacts/10user-v2/)
- B1/B2/B3 运行报告：[`reports/`](../reports/)
- SA-Mem 核心代码 compare：见各分支 README 中的链接

如果需要查看完整原始 prompt 和完整 raw block，优先看各 variant 的运行 artifacts；本文只
保留能说明“request → response → 下一阶段输入”的最小真实片段，避免把同一份长 prompt 在
多个章节重复粘贴。
