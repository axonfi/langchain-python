"""Unit tests for langchain-axon tools (mocked AxonClientSync)."""

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from langchain_axon import AxonBalance, AxonExecute, AxonPay, AxonPoll, AxonSwap, AxonVaultInfo


@dataclass
class FakePaymentResult:
    request_id: str = "req-123"
    status: str = "approved"
    tx_hash: str | None = "0xabc123"
    poll_url: str | None = None
    estimated_resolution_ms: int | None = None
    reason: str | None = None


@dataclass
class FakeVaultInfo:
    owner: str = "0x1111111111111111111111111111111111111111"
    operator: str = "0x0000000000000000000000000000000000000000"
    paused: bool = False
    version: int = 3


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.pay.return_value = FakePaymentResult()
    client.swap.return_value = FakePaymentResult(status="approved", tx_hash="0xswap456")
    client.execute.return_value = FakePaymentResult(status="approved", tx_hash="0xexec789")
    client.poll.return_value = FakePaymentResult()
    client.poll_swap.return_value = FakePaymentResult()
    client.poll_execute.return_value = FakePaymentResult()
    client.get_balance.return_value = 5_000_000  # 5 USDC in base units
    client.get_vault_info.return_value = FakeVaultInfo()
    return client


# ── AxonPay ──────────────────────────────────────────────────────────────────


class TestAxonPay:
    def test_approved(self, mock_client):
        tool = AxonPay(client=mock_client)
        result = tool._run(to="0xrecipient", token="USDC", amount=5.0)
        assert "Approved" in result
        assert "0xabc123" in result
        mock_client.pay.assert_called_once_with(to="0xrecipient", token="USDC", amount=5.0, memo=None)

    def test_pending_review(self, mock_client):
        mock_client.pay.return_value = FakePaymentResult(status="pending_review", tx_hash=None)
        tool = AxonPay(client=mock_client)
        result = tool._run(to="0xrecipient", token="USDC", amount=100.0)
        assert "review" in result.lower()
        assert "req-123" in result

    def test_rejected(self, mock_client):
        mock_client.pay.return_value = FakePaymentResult(status="rejected", tx_hash=None, reason="Exceeds limit")
        tool = AxonPay(client=mock_client)
        result = tool._run(to="0xrecipient", token="USDC", amount=999.0)
        assert "Rejected" in result
        assert "Exceeds limit" in result

    def test_with_memo(self, mock_client):
        tool = AxonPay(client=mock_client)
        tool._run(to="0xrecipient", token="WETH", amount=0.1, memo="API payment")
        mock_client.pay.assert_called_once_with(to="0xrecipient", token="WETH", amount=0.1, memo="API payment")


# ── AxonBalance ──────────────────────────────────────────────────────────────


class TestAxonBalance:
    def test_known_token(self, mock_client):
        tool = AxonBalance(client=mock_client, chain_id=84532)
        result = tool._run(token="USDC")
        assert "5" in result
        assert "USDC" in result

    def test_unknown_token(self, mock_client):
        tool = AxonBalance(client=mock_client, chain_id=84532)
        result = tool._run(token="0xunknowntoken")
        assert "base units" in result


# ── AxonSwap ─────────────────────────────────────────────────────────────────


class TestAxonSwap:
    def test_basic_swap(self, mock_client):
        tool = AxonSwap(client=mock_client)
        result = tool._run(to_token="WETH", min_to_amount=0.001)
        assert "Approved" in result
        mock_client.swap.assert_called_once_with(to_token="WETH", min_to_amount=0.001)

    def test_swap_with_source(self, mock_client):
        tool = AxonSwap(client=mock_client)
        tool._run(to_token="WETH", min_to_amount=0.001, from_token="USDC", max_from_amount=5.0)
        mock_client.swap.assert_called_once_with(
            to_token="WETH", min_to_amount=0.001, from_token="USDC", max_from_amount=5.0
        )


# ── AxonExecute ──────────────────────────────────────────────────────────────


class TestAxonExecute:
    def test_execute(self, mock_client):
        tool = AxonExecute(client=mock_client)
        result = tool._run(
            protocol="0xrouter",
            call_data="0xabcdef",
            token="USDC",
            amount=10.0,
        )
        assert "Approved" in result
        mock_client.execute.assert_called_once_with(
            protocol="0xrouter", call_data="0xabcdef", token="USDC", amount=10.0, memo=None
        )


# ── AxonPoll ─────────────────────────────────────────────────────────────────


class TestAxonPoll:
    def test_poll_payment(self, mock_client):
        tool = AxonPoll(client=mock_client)
        result = tool._run(request_id="req-123", request_type="payment")
        assert "Approved" in result
        mock_client.poll.assert_called_once_with("req-123")

    def test_poll_swap(self, mock_client):
        tool = AxonPoll(client=mock_client)
        tool._run(request_id="req-456", request_type="swap")
        mock_client.poll_swap.assert_called_once_with("req-456")

    def test_poll_execute(self, mock_client):
        tool = AxonPoll(client=mock_client)
        tool._run(request_id="req-789", request_type="execute")
        mock_client.poll_execute.assert_called_once_with("req-789")


# ── AxonVaultInfo ────────────────────────────────────────────────────────────


class TestAxonVaultInfo:
    def test_active_vault(self, mock_client):
        tool = AxonVaultInfo(client=mock_client)
        result = tool._run()
        assert "active" in result
        assert "0x1111" in result
        assert "none" in result.lower()  # zero-address operator
        assert "3" in result

    def test_paused_vault(self, mock_client):
        mock_client.get_vault_info.return_value = FakeVaultInfo(paused=True)
        tool = AxonVaultInfo(client=mock_client)
        result = tool._run()
        assert "PAUSED" in result
