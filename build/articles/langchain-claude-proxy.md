<div align="center">
<h3>KingFlow · 国内直连 AI API 中转</h3>
<a href="https://www.kingflow.ai"><img src="https://img.shields.io/badge/官网-www.kingflow.ai-FF6B35" alt="KingFlow"></a>
</div>

# LangChain 接入 Claude 中转 API：开发实战

写这篇是因为我自己在 LangChain 项目里折腾中转接 Claude 踩了不少坑。网上多数教程还停留在直连官方，或者用早就下线的模型名跑示例，照抄根本跑不起来。这篇按我实际项目里能跑通的写法整理，从两种接入方式讲到链/Agent 里的多模型混用，再到流式和工具调用的细节，最后回答几个常被问到的问题。

## 一、LangChain 里接中转的两种方式

LangChain 生态里接 Claude 中转，本质上就是把请求指向一个自己可控的 `base_url`。有两条路，选哪条取决于你想走哪套协议。

**方式一：走 OpenAI 兼容协议，用 `ChatOpenAI`。**

这是我更推荐的默认做法。KingFlow 提供 OpenAI 兼容端点 `https://www.kingflow.ai/v1`，你用 `langchain-openai` 里的 `ChatOpenAI`，把 `base_url` 指过去，`model` 填 Claude 的在售名（比如 `claude-opus-4-8`），一个客户端就能同时调 Claude 和 GPT 系模型，切换只改 `model` 参数。团队里如果本来就用 `ChatOpenAI` 封装了一堆链，这条路几乎零改动。

**方式二：走 Anthropic 原生协议，用 `ChatAnthropic`。**

如果你的代码依赖 Anthropic 特有的字段（比如某些细粒度的 `system` 结构、`cache_control` prompt 缓存标记），那就用 `langchain-anthropic` 的 `ChatAnthropic`，把 `base_url` 指向中转的 Anthropic 端点，同时提供 `ANTHROPIC_AUTH_TOKEN` 作为鉴权。这条路能拿到官方 `/v1/messages` 协议的完整能力，KingFlow 这边是完整透传官方协议的，不是逆向反代，所以 prompt cache 这类特性能原样用上。

我的经验：混合调度多家模型、想用一个 Key 管全部，用方式一；纯 Claude、且要压榨缓存和原生字段，用方式二。两者可以在同一个项目里并存，互不冲突。

## 二、代码示例：改一行 Base URL 接进来

先看方式一，最常用。安装 `langchain-openai` 后：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://www.kingflow.ai/v1",
    api_key="你的-KingFlow-Key",
    model="claude-opus-4-8",
    temperature=0.3,
)

resp = llm.invoke("用三句话解释向量数据库的作用")
print(resp.content)
```

关键就是 `base_url` 和 `api_key` 两行，其余用法跟你平时写 `ChatOpenAI` 一模一样。想换成便宜些的高频模型，把 `model` 改成 `claude-haiku-4-5` 即可，Key 不用动。

如果偏好用环境变量（生产里建议这样，别把 Key 写进代码）：

```python
import os
from langchain_openai import ChatOpenAI

os.environ["OPENAI_API_KEY"] = "你的-KingFlow-Key"
os.environ["OPENAI_BASE_URL"] = "https://www.kingflow.ai/v1"

llm = ChatOpenAI(model="claude-sonnet-4-6")
```

方式二，走 `ChatAnthropic` 原生协议：

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    base_url="https://www.kingflow.ai",
    api_key="你的-KingFlow-Key",   # 对应 ANTHROPIC_AUTH_TOKEN
    model="claude-opus-4-8",
    max_tokens=2048,
)

print(llm.invoke("写一个快速排序的 Python 实现").content)
```

注意 `ChatAnthropic` 的 `base_url` 指向的是根地址（不带 `/v1`），而 `ChatOpenAI` 那条要带 `/v1`。这个差别踩过一次坑，两边协议的路径约定不一样，别搞混。

## 三、链/Agent 里的多模型混用

这是中转最香的地方：一个 Key 背后挂着多款模型，你可以在一条链里按环节分配不同模型，让强模型干重活、便宜模型干杂活，成本能压下来一大截。

我常用的模式是——**推理规划用旗舰，工具调用/格式整理用低成本模型**。比如一个 Agent，用 `claude-opus-4-8` 做任务拆解和最终推理，用 `claude-haiku-4-5` 去跑那些只是"填个模板、抽个字段、判断个是否"的高频小步骤：

```python
from langchain_openai import ChatOpenAI

BASE = "https://www.kingflow.ai/v1"
KEY = "你的-KingFlow-Key"

# 强模型：负责推理、规划、最终输出
brain = ChatOpenAI(base_url=BASE, api_key=KEY, model="claude-opus-4-8")

# 便宜模型：负责工具调用、字段抽取、格式整理等高频轻活
worker = ChatOpenAI(base_url=BASE, api_key=KEY, model="claude-haiku-4-5")

def pipeline(question: str):
    plan = brain.invoke(f"把这个任务拆成可执行步骤：{question}")
    draft = worker.invoke(f"按下面步骤整理成结构化清单：\n{plan.content}")
    return brain.invoke(f"基于清单给出最终答复：\n{draft.content}").content
```

因为两个客户端指的是同一个 `base_url`、同一个 Key，后台能把这些调用汇总在一起，日志、token 用量、余额都在一个面板看，对账不用在多家平台之间来回切。真正做量之后，这种"分模型对账"能力比省那点接入代码值钱得多。

在 LangGraph 里也是一样的思路：不同节点绑不同 `ChatOpenAI` 实例，路由节点决定走强还是走弱。甚至可以在同一套代码里混进 GPT 系模型做交叉验证，只要改 `model` 就行，不必再维护第二套 Key 和第二个 SDK。

## 四、流式与工具调用注意点

**流式输出。** LangChain 里用 `.stream()` 或异步 `.astream()` 拿增量。KingFlow 这边流式是支持的，用法跟直连官方没区别：

```python
for chunk in llm.stream("讲讲 RAG 的检索召回优化"):
    print(chunk.content, end="", flush=True)
```

有两个点提一下：一是首字延迟（TTFT），走国内直连节点通常一两秒就出字，比自己挂代理连美国节点动辄几十秒稳定得多，交互式场景体感差别很大；二是流式下别忘了处理空 chunk，某些模型在开头会先吐一个不带内容的分片，`chunk.content` 可能是空串，做前端拼接时判一下。

**工具调用（Function Calling）。** 用 `bind_tools` 绑定工具，两种方式都支持：

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气"""
    return f"{city}：晴，26 度"

llm_with_tools = llm.bind_tools([get_weather])
ai_msg = llm_with_tools.invoke("北京今天天气怎么样")
print(ai_msg.tool_calls)
```

实践中要注意：走 `ChatOpenAI` 兼容协议时，工具调用被转成 OpenAI 的 `tool_calls` 格式，绝大多数场景没问题；但如果你的工具 schema 特别复杂、或用到 Anthropic 独有的工具行为，建议直接用 `ChatAnthropic` 走原生协议，保真度更高。另外流式 + 工具调用同时开时，`tool_calls` 是分片累积出来的，要等流结束再解析，别在中途读。

## 五、为什么用 KingFlow

抛开接入方便不谈，我最后固定用它，是几个实在的理由：

- **国内直连**：国内节点，TTFT 一般一到三秒，不用自己再挂代理。之前用机场代理连官方，高频长连接三五分钟就被识别，403/429 连着来，Agent 跑一半断掉的事没少遇到，换成直连之后这类问题基本消失。
- **一个 Key 多模型**：Claude 全系加 GPT 系等都在一个 Key 后面，链里换模型只改 `model` 参数，不用维护多套凭证和多个 SDK。
- **走官方协议、不掉包**：是官方 `/v1/messages` 协议透传，不是逆向反代，官方更新时不容易突然挂；也不会拿小模型冒充旗舰，你填 `claude-opus-4-8` 拿到的就是它。
- **后台对账透明**：日志、余额、token 用量、调用明细都能查，做多模型混用时按 Key 拆成本很方便。人民币小额充值、新人有额度，可以先测通再决定要不要上量。

对做 LangChain 项目的人来说，"改一行 base_url 就能接、一个 Key 调全部、用量能对上账"这三点，基本覆盖了日常开发的核心诉求。

## 六、FAQ

**Q1：`ChatOpenAI` 和 `ChatAnthropic` 到底选哪个？**
默认用 `ChatOpenAI` 指 `https://www.kingflow.ai/v1`，因为它天然支持多家模型混调、一个 Key 走天下。只有当你要用 Anthropic 原生字段或 prompt 缓存特性时，才用 `ChatAnthropic` 走根地址端点。同一项目两者可以并存。

**Q2：`base_url` 要不要带 `/v1`？**
走 `ChatOpenAI`（OpenAI 兼容）要带，`https://www.kingflow.ai/v1`；走 `ChatAnthropic`（Anthropic 原生）填根地址 `https://www.kingflow.ai`，不带 `/v1`。这个最容易搞混，接不通先检查这里。

**Q3：模型名填什么？**
用当前在售的名字：`claude-opus-4-8`（旗舰、重活）、`claude-sonnet-4-6`（均衡）、`claude-haiku-4-5`（高频低成本）。别再抄老教程里那种带长日期后缀的旧模型名，那些已经调不通了。

**Q4：多模型混用会不会难对账？**
不会，反而更好对。因为所有调用都走同一个 `base_url` 和同一个 Key，后台把 token 用量、调用明细汇总在一处，按模型看消耗一目了然。要给团队分账，就给不同成员发不同 Key，后台按 Key 分别统计即可。
