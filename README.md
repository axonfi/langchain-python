# langchain-axon

LangChain toolkit for [Axon](https://axonfi.xyz) — treasury and payment infrastructure for autonomous AI agents.

Gives your LangChain agent 7 tools: pay, check balance, swap tokens, execute DeFi protocols, poll async requests, get vault info, and handle x402 paywalls.

## Install

```bash
pip install langchain-axon
```

## Prerequisites

Before using this toolkit, you need an Axon vault and a registered bot:

1. **Deploy a vault** — Go to [app.axonfi.xyz](https://app.axonfi.xyz), connect your wallet, and deploy a vault. The vault is a non-custodial smart contract that holds your funds. You'll get a vault address (e.g. `0xb8e3...`).

2. **Fund the vault** — Send USDC (or any ERC-20) to your vault address. Anyone can deposit.

3. **Register a bot** — In the dashboard, go to your vault → Bots → Add Bot. You can generate a new keypair (downloads a keystore file) or bring your own public key. Set spending limits and policies.

4. **Get the bot key** — Your agent needs the bot's private key to sign payment intents. Either use the keystore file + passphrase, or export the raw private key.

Your wallet (vault owner) stays secure — the bot key can only sign intents within the policies you set. The bot never touches gas or holds funds.

**Supported chains:** Base, Arbitrum, Optimism, Polygon (mainnet + testnets).

## Quick Start

```python
from langchain_axon import AxonToolkit
from langchain_anthropic import ChatAnthropic
from axonfi import Chain

toolkit = AxonToolkit(
    vault_address="0x...",
    chain_id=Chain.BaseSepolia,
    bot_private_key="0x...",
)

llm = ChatAnthropic(model="claude-sonnet-4-20250514")
agent = llm.bind_tools(toolkit.get_tools())
```

### Keystore Authentication

```python
toolkit = AxonToolkit(
    vault_address="0x...",
    chain_id=Chain.Base,
    bot_keystore="bot-keystore.json",
    bot_passphrase="my-secret-passphrase",
)
```

### Environment Variables

```bash
AXON_VAULT_ADDRESS=0x...
AXON_CHAIN_ID=84532
AXON_BOT_PRIVATE_KEY=0x...
# or
AXON_BOT_KEYSTORE_PATH=bot-keystore.json
AXON_BOT_PASSPHRASE=my-secret-passphrase
```

## Tools

| Tool | Description |
|------|-------------|
| `axon_pay` | Send a payment from the vault |
| `axon_balance` | Check vault token balance |
| `axon_swap` | In-vault token rebalance |
| `axon_execute` | DeFi protocol interaction (approve → call → revoke) |
| `axon_poll` | Poll async payment/swap/execute status |
| `axon_vault_info` | Get vault status, owner, paused state |
| `axon_x402` | Handle HTTP 402 Payment Required paywalls |

## Individual Tools

```python
from langchain_axon import AxonPay, AxonBalance
from axonfi import AxonClientSync, Chain

client = AxonClientSync(
    vault_address="0x...",
    chain_id=Chain.BaseSepolia,
    bot_private_key="0x...",
)

pay_tool = AxonPay(client=client)
balance_tool = AxonBalance(client=client, chain_id=Chain.BaseSepolia)
```

## Full Agent Example

```python
import os
from langchain_axon import AxonToolkit
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from axonfi import Chain

toolkit = AxonToolkit(
    vault_address=os.environ["AXON_VAULT_ADDRESS"],
    chain_id=Chain.BaseSepolia,
    bot_private_key=os.environ["AXON_BOT_PRIVATE_KEY"],
)

tools = toolkit.get_tools()
llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
llm_with_tools = llm.bind_tools(tools)

messages = [
    SystemMessage(content="You are an AI agent with an Axon payment vault."),
    HumanMessage(content="Check my USDC balance then send 1 USDC to 0xRecipient"),
]

# Agent loop
while True:
    response = llm_with_tools.invoke(messages)
    messages.append(response)

    if not response.tool_calls:
        print(response.content)
        break

    for call in response.tool_calls:
        tool = next(t for t in tools if t.name == call["name"])
        result = tool.invoke(call["args"])
        messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
```

## Links

- [Axon Documentation](https://axonfi.xyz/docs)
- [Python SDK (`axonfi`)](https://pypi.org/project/axonfi/)
- [TypeScript SDK (`@axonfi/sdk`)](https://www.npmjs.com/package/@axonfi/sdk)
- [GitHub](https://github.com/axonfi/langchain-python)
