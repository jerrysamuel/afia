"""Small ERC-8004 Identity Registry adapter.

This module prepares and submits an agent registration only when the caller
explicitly supplies a signer, RPC URL, chain ID, and agent URI. It does not
run during API startup and never stores private keys in Afia models.
"""

from __future__ import annotations

from dataclasses import dataclass


IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "agentURI", "type": "string"}],
        "name": "register",
        "outputs": [{"internalType": "uint256", "name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "agentId", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "agentURI", "type": "string"},
            {"indexed": True, "internalType": "address", "name": "owner", "type": "address"},
        ],
        "name": "Registered",
        "type": "event",
    },
]


@dataclass(frozen=True)
class AgentRegistrationResult:
    agent_id: int
    transaction_hash: str
    owner: str
    registry: str
    chain_id: int


def register_agent(
    *,
    rpc_url: str,
    chain_id: int,
    private_key: str,
    agent_uri: str,
    identity_registry: str,
) -> AgentRegistrationResult:
    """Register an agent and return its authoritative transaction and ID.

    The private key is read by the caller and used only in memory. The caller
    must verify ``agent_uri`` and ``identity_registry`` before submitting.
    """
    from eth_account import Account
    from web3 import Web3

    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if not web3.is_connected():
        raise RuntimeError("could not connect to the configured ERC-8004 RPC")
    if web3.eth.chain_id != chain_id:
        raise RuntimeError(f"RPC chain ID {web3.eth.chain_id} does not match configured {chain_id}")

    account = Account.from_key(private_key)
    registry = Web3.to_checksum_address(identity_registry)
    contract = web3.eth.contract(address=registry, abi=IDENTITY_REGISTRY_ABI)
    if web3.eth.get_code(registry) in {b"", b"0x"}:
        raise RuntimeError("no contract code found at the configured ERC-8004 registry")

    nonce = web3.eth.get_transaction_count(account.address, "pending")
    gas = contract.functions.register(agent_uri).estimate_gas({"from": account.address})
    transaction = contract.functions.register(agent_uri).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": gas,
            "maxFeePerGas": web3.eth.gas_price * 2,
            "maxPriorityFeePerGas": web3.to_wei(1, "gwei"),
        }
    )
    signed = account.sign_transaction(transaction)
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"ERC-8004 registration reverted: {tx_hash.hex()}")

    events = contract.events.Registered().process_receipt(receipt)
    if not events:
        raise RuntimeError("registration succeeded but no Registered event was found")
    agent_id = int(events[0]["args"]["agentId"])
    return AgentRegistrationResult(
        agent_id=agent_id,
        transaction_hash=tx_hash.hex(),
        owner=account.address,
        registry=registry,
        chain_id=chain_id,
    )
