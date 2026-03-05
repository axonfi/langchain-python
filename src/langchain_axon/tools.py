"""Axon LangChain tools — 6 BaseTool subclasses for vault operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from axonfi import AxonClientSync


# ── Pydantic input schemas ──────────────────────────────────────────────────


class PayInput(BaseModel):
    """Input for sending a payment from the vault."""

    to: str = Field(description="Recipient address (0x...)")
    token: str = Field(description="Token symbol (USDC, WETH, etc.) or contract address")
    amount: float = Field(description="Human-readable amount (e.g. 5.0 for 5 USDC)")
    memo: Optional[str] = Field(default=None, description="Optional payment description")


class BalanceInput(BaseModel):
    """Input for checking vault token balance."""

    token: str = Field(default="USDC", description="Token symbol (default: USDC)")


class SwapInput(BaseModel):
    """Input for in-vault token rebalancing."""

    to_token: str = Field(description="Target token symbol (e.g. WETH)")
    min_to_amount: float = Field(description="Minimum amount of target token to receive")
    from_token: Optional[str] = Field(default=None, description="Source token (default: USDC)")
    max_from_amount: Optional[float] = Field(default=None, description="Maximum source token to spend")


class ExecuteInput(BaseModel):
    """Input for DeFi protocol interaction."""

    protocol: str = Field(description="Target protocol contract address (0x...)")
    call_data: str = Field(description="ABI-encoded function calldata (0x...)")
    token: str = Field(description="Token to approve for the protocol")
    amount: float = Field(description="Approval amount in human-readable units")
    memo: Optional[str] = Field(default=None, description="Optional description")


class PollInput(BaseModel):
    """Input for polling async request status."""

    request_id: str = Field(description="Request ID from a pending payment, swap, or execute")
    request_type: str = Field(
        default="payment",
        description="Type of request: 'payment', 'swap', or 'execute'",
    )


class VaultInfoInput(BaseModel):
    """Input for getting vault information (no parameters required)."""

    pass


# ── Helper ───────────────────────────────────────────────────────────────────


def _format_result(result) -> str:
    """Format a PaymentResult into an LLM-friendly string."""
    if result.status == "approved":
        return f"Approved! TX: {result.tx_hash}"
    elif result.status == "pending_review":
        return f"Under review (request ID: {result.request_id}). Use AxonPoll to check status."
    else:
        return f"Rejected: {result.reason}"


# ── Tools ────────────────────────────────────────────────────────────────────


class AxonPay(BaseTool):
    """Send a payment from the Axon vault to a recipient address."""

    name: str = "axon_pay"
    description: str = (
        "Send a payment from the Axon vault. Specify recipient address, token, "
        "amount, and an optional memo. Returns transaction hash if approved, "
        "or a request ID if the payment requires human review."
    )
    args_schema: Type[BaseModel] = PayInput
    client: object = Field(exclude=True)

    def _run(self, to: str, token: str, amount: float, memo: str | None = None) -> str:
        result = self.client.pay(to=to, token=token, amount=amount, memo=memo)
        return _format_result(result)


class AxonBalance(BaseTool):
    """Check the vault balance for a specific token."""

    name: str = "axon_balance"
    description: str = (
        "Check how much of a token the vault holds. "
        "Returns the balance in human-readable units (e.g. '125.50 USDC')."
    )
    args_schema: Type[BaseModel] = BalanceInput
    client: object = Field(exclude=True)
    chain_id: int = Field(exclude=True)

    def _run(self, token: str = "USDC") -> str:
        from axonfi import KNOWN_TOKENS, resolve_token

        token_address = resolve_token(token, self.chain_id)
        balance_raw = self.client.get_balance(token_address)

        info = KNOWN_TOKENS.get(token.upper())
        if info:
            human = balance_raw / (10 ** info.decimals)
            return f"Vault holds {human:.6g} {token.upper()}"
        return f"Vault holds {balance_raw} base units of {token}"


class AxonSwap(BaseTool):
    """Perform an in-vault token rebalance (e.g. swap USDC for WETH)."""

    name: str = "axon_swap"
    description: str = (
        "Swap tokens within the vault (rebalancing). The output stays in the vault. "
        "Specify target token, minimum output amount, and optionally source token and max spend."
    )
    args_schema: Type[BaseModel] = SwapInput
    client: object = Field(exclude=True)

    def _run(
        self,
        to_token: str,
        min_to_amount: float,
        from_token: str | None = None,
        max_from_amount: float | None = None,
    ) -> str:
        kwargs: dict = {"to_token": to_token, "min_to_amount": min_to_amount}
        if from_token:
            kwargs["from_token"] = from_token
        if max_from_amount is not None:
            kwargs["max_from_amount"] = max_from_amount
        result = self.client.swap(**kwargs)
        return _format_result(result)


class AxonExecute(BaseTool):
    """Execute a DeFi protocol interaction through the vault."""

    name: str = "axon_execute"
    description: str = (
        "Call a DeFi protocol contract through the vault. The vault approves the token, "
        "executes the call, then revokes approval. You must provide the protocol address "
        "and ABI-encoded calldata."
    )
    args_schema: Type[BaseModel] = ExecuteInput
    client: object = Field(exclude=True)

    def _run(
        self,
        protocol: str,
        call_data: str,
        token: str,
        amount: float,
        memo: str | None = None,
    ) -> str:
        result = self.client.execute(
            protocol=protocol,
            call_data=call_data,
            token=token,
            amount=amount,
            memo=memo,
        )
        return _format_result(result)


class AxonPoll(BaseTool):
    """Poll the status of a pending payment, swap, or execute request."""

    name: str = "axon_poll"
    description: str = (
        "Check the status of a pending request. Provide the request ID and type "
        "('payment', 'swap', or 'execute'). Returns approved (with TX hash), "
        "still pending, or rejected (with reason)."
    )
    args_schema: Type[BaseModel] = PollInput
    client: object = Field(exclude=True)

    def _run(self, request_id: str, request_type: str = "payment") -> str:
        poll_fn = {
            "payment": self.client.poll,
            "swap": self.client.poll_swap,
            "execute": self.client.poll_execute,
        }.get(request_type, self.client.poll)

        result = poll_fn(request_id)
        return _format_result(result)


class AxonVaultInfo(BaseTool):
    """Get vault status information (owner, operator, paused state, version)."""

    name: str = "axon_vault_info"
    description: str = (
        "Get information about the vault: owner address, operator address, "
        "whether the vault is paused, and the contract version."
    )
    args_schema: Type[BaseModel] = VaultInfoInput
    client: object = Field(exclude=True)

    def _run(self) -> str:
        info = self.client.get_vault_info()
        paused = "PAUSED" if info.paused else "active"
        operator = info.operator if info.operator != "0x" + "0" * 40 else "none"
        return (
            f"Vault status: {paused}\n"
            f"Owner: {info.owner}\n"
            f"Operator: {operator}\n"
            f"Version: {info.version}"
        )
