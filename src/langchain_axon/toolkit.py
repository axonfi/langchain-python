"""AxonToolkit — single entry point for all Axon LangChain tools."""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool

from .tools import AxonBalance, AxonExecute, AxonPay, AxonPoll, AxonSwap, AxonVaultInfo, AxonX402


class AxonToolkit:
    """LangChain toolkit for Axon vault operations.

    Creates a shared ``AxonClientSync`` and exposes all Axon tools.

    Accepts either a raw private key or a keystore file + passphrase::

        # Raw key
        toolkit = AxonToolkit(
            vault_address="0x...",
            chain_id=84532,
            bot_private_key="0x...",
        )

        # Keystore
        toolkit = AxonToolkit(
            vault_address="0x...",
            chain_id=84532,
            bot_keystore="bot-keystore.json",
            bot_passphrase="secret",
        )
    """

    def __init__(
        self,
        vault_address: str,
        chain_id: int,
        *,
        bot_private_key: str | None = None,
        bot_keystore: str | None = None,
        bot_passphrase: str | None = None,
        relayer_url: str | None = None,
    ) -> None:
        from axonfi import AxonClientSync

        private_key = bot_private_key
        if private_key is None:
            if bot_keystore is None or bot_passphrase is None:
                raise ValueError(
                    "Provide either bot_private_key or both bot_keystore + bot_passphrase"
                )
            private_key = self._decrypt_keystore(bot_keystore, bot_passphrase)

        kwargs: dict = {
            "vault_address": vault_address,
            "chain_id": chain_id,
            "bot_private_key": private_key,
        }
        if relayer_url is not None:
            kwargs["relayer_url"] = relayer_url

        self._client = AxonClientSync(**kwargs)
        self._chain_id = chain_id

    @staticmethod
    def _decrypt_keystore(keystore_path: str, passphrase: str) -> str:
        """Decrypt an Ethereum keystore file and return the private key."""
        from eth_account import Account

        with open(keystore_path) as f:
            keystore = json.load(f)
        return "0x" + Account.decrypt(keystore, passphrase).hex()

    @property
    def client(self):
        """The underlying ``AxonClientSync`` instance."""
        return self._client

    def get_tools(self) -> list[BaseTool]:
        """Return all 7 Axon tools sharing a single client."""
        return [
            AxonPay(client=self._client),
            AxonBalance(client=self._client, chain_id=self._chain_id),
            AxonSwap(client=self._client),
            AxonExecute(client=self._client),
            AxonPoll(client=self._client),
            AxonVaultInfo(client=self._client),
            AxonX402(client=self._client),
        ]
