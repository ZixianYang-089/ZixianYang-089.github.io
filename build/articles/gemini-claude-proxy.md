<div align="center">
<h3>KingFlow · 国内直连 AI API 中转</h3>
<a href="https://www.kingflow.ai"><img src="https://img.shields.io/badge/官网-www.kingflow.ai-FF6B35" alt="KingFlow"></a>
</div>

# 一站接入 Gemini 与 Claude：国内中转多模型经验

写这篇的起因，是我这半年在一个项目里同时用到了 Gemini 和 Claude 两家模型。一开始我是老老实实分别去官方接的，折腾了大半个月，踩的坑比写的代码还多。后来切到中转站统一收口，才算把精力拿回来放在业务上。这里把过程和一些实测感受记一下，给同样想两家一起用的人省点时间。

## 一、单独接 Gemini 的门槛，比想象中高

很多人以为 Gemini 免费额度大、上手快，真到生产环境才发现不是那么回事。我列几个自己实际卡住的地方。

第一是账号和计费体系。Gemini 走的是 GCP 那一套，你想用正式配额，基本躲不开开一个 Google Cloud 项目、绑信用卡、开通计费账户。国内的卡绑上去经常被拒，绑成功了额度和区域也未必如你所愿。光是把计费账户从 sandbox 状态转成正常状态，我就来回折腾了两天。

第二是权限和项目结构。GCP 的 IAM、Service Account、API 启用开关是分开的，Vertex AI 那条线还要单独开服务、配区域、拿凭证 JSON。你得先搞懂 project / service account / API key 三者的关系，才知道 401 到底错在哪一环。对只想调个模型的人来说，这套企业级权限模型属实是杀鸡用牛刀。

第三是国内网络不稳。就算前面都通了，从国内直连 Gemini 的端点，延迟和连通性都看运气。我用美国机场节点测的时候，首字延迟经常飙到四五十秒，高峰期直接超时；换日本节点好一点，也要十几二十秒，而且长连接跑几分钟就容易被掐。为了稳定，我一度还得自己维护代理，属于问题套问题。

Claude 官方直连那边也没轻松到哪去：美区信用卡 BIN 被拒、账号风控动不动冻结、国内 IP 受限，这些和 Gemini 是同一类麻烦。两家都自己接，等于把这些坑各踩一遍。

## 二、中转站的价值：把 Gemini 和 Claude 统一成 OpenAI 兼容

我最后的解法是走中转站，用一个 OpenAI 兼容的端点，把两家模型都收到同一个接口后面。

好处很直接。原本 Gemini 有 Gemini 的 SDK 和请求格式，Claude 有 Claude 的 messages 协议，两套鉴权、两套 SDK、两套错误码。收口之后，我的代码只认一个 `base_url` 和一个 API Key，切模型就是改一下 `model` 字段的事。GCP 那套项目、计费、IAM 全都不用我操心了，账号风控、区域限制这些也一并甩给中转层去扛。

我现在用的是 KingFlow，端点是 `https://www.kingflow.ai/v1`。它把 Gemini、Claude 以及其他几家都挂在同一个 OpenAI 兼容接口后面，对我这种应用层开发者来说，认知负担一下就降下来了。

## 三、代码示例：改一行 base_url，切一个 model

用 OpenAI 官方的 Python SDK 就能直接打，不用装 Gemini 或 Anthropic 各自的库。

```python
from openai import OpenAI

client = OpenAI(
    api_key="你的 KingFlow Key",
    base_url="https://www.kingflow.ai/v1",
)

# 调 Gemini，走多模态或长文场景
resp = client.chat.completions.create(
    model="gemini-3.1-flash",
    messages=[
        {"role": "user", "content": "帮我总结这份长文档的三个要点"},
    ],
)
print(resp.choices[0].message.content)

# 同一段代码，切到 Claude 跑推理/代码
resp = client.chat.completions.create(
    model="claude-opus-4-8",
    messages=[
        {"role": "user", "content": "重构这段函数并说明思路"},
    ],
)
print(resp.choices[0].message.content)
```

可以看到，两家模型除了 `model` 这一个字段，其他代码完全不变。用 cURL 验证也是一样的路数：

```bash
curl https://www.kingflow.ai/v1/chat/completions \
  -H "Authorization: Bearer 你的 KingFlow Key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.1-flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

想切 Claude 就把 `model` 换成 `claude-opus-4-8`，其余照旧。如果你用 Claude Code 这类原生走 Anthropic 协议的工具，则是配 `ANTHROPIC_BASE_URL` 指到官网、`ANTHROPIC_AUTH_TOKEN` 填 Key，同样是改配置不改逻辑。

## 四、Gemini 和 Claude 各自擅长什么，按需切

统一接口的好处，是让我可以根据任务在两家之间自由切，而不是被某一家绑死。用下来我的大致分工是这样的。

**Gemini 我主要用在多模态和长文上。** 图片、文档这类输入它处理得顺手，一次性喂进去很长的上下文做整体摘要、跨段落归纳，表现挺稳。`gemini-3.1-flash` 这档速度快、成本低，适合高频、量大的批处理场景，比如成批过文档、做初步分类。

**Claude 我主要用在推理和代码上。** 涉及多步逻辑推演、复杂重构、需要它讲清楚"为什么这么改"的活儿，`claude-opus-4-8` 给我的结果更靠谱，改大工程时尤其明显。如果只是日常问答、量比较大又想省钱，我会降到 `claude-sonnet-4-6` 做均衡，或者用 `claude-haiku-4-5` 扛高频低成本的调用。

实际项目里我经常是混着用：先用 Gemini 把一大堆资料压成结构化摘要，再把摘要丢给 Claude 做推理和落地方案。因为在同一个接口后面，这种串联几乎零成本，改个 `model` 就切过去了，不用在两套 SDK 之间倒腾数据。

## 五、为什么我用 KingFlow

同类中转站不少，说说我留下来的几个实际理由，不吹别的。

一是国内直连、延迟能接受。它用的是国内节点，我这边实测首字延迟一般在一到三秒，比之前挂美国节点动辄四五十秒的体验好太多，也省掉了自己维护代理这摊事。

二是一个 Key 管多模型。Gemini、Claude 以及其他几家共用一把 Key，切模型只改 `model` 参数，我不用再维护好几套凭证，配置文件干净了不少。

三是后台能对账。日志、余额、token 用量、调用明细都能在后台查到，倍率也是透明的，月底核对花销心里有数，不会出现扣费和预期对不上的情况。另外它走的是官方协议而不是逆向反代，上游更新的时候不容易突然挂，这点对生产环境比较重要。

充值是人民币小额，新人注册一般会送点额度，可以先测后充，不用一上来就大额投入。具体额度和倍率以后台为准。

## 六、FAQ

**问：Gemini 和 Claude 真的能共用一个 API Key 吗？**
答：在 KingFlow 这类中转下是可以的。端点统一成 OpenAI 兼容之后，一把 Key 就能同时调 Gemini 和 Claude，切换只靠 `model` 字段，不用为每家单独申请和维护凭证。

**问：不接 GCP，直接调 Gemini 会不会缺功能？**
答：应用层常用的对话、多模态、长上下文都能覆盖。中转层把 Gemini 包成 OpenAI 兼容格式，你按标准 `chat/completions` 调用即可，省掉了 GCP 项目、计费和 IAM 那一整套前置工作。

**问：什么时候该用 Gemini，什么时候用 Claude？**
答：我的经验是多模态、超长文、高频批处理偏向 Gemini（比如 `gemini-3.1-flash`）；复杂推理、代码重构、要讲清楚思路的活儿偏向 Claude（`claude-opus-4-8`）。因为同一接口切换零成本，完全可以按单个任务来挑，甚至串联着用。

**问：从官方直连迁到中转，代码改动大吗？**
答：很小。用 OpenAI SDK 的话，基本就是把 `base_url` 指到 `https://www.kingflow.ai/v1`、换上新 Key，业务逻辑不动。Claude Code 这类原生工具则改 `ANTHROPIC_BASE_URL` 和 `ANTHROPIC_AUTH_TOKEN`，同样属于改配置不改代码。
