"""Explicit ERC-8004 registration command for Celo mainnet.

Required environment variables:
  ERC8004_RPC_URL
  ERC8004_PRIVATE_KEY
  ERC8004_AGENT_URI

Optional:
  ERC8004_CHAIN_ID (defaults to Celo mainnet 42220)
  ERC8004_IDENTITY_REGISTRY (defaults to the ERC-8004 mainnet singleton)
"""

import os

from dotenv import load_dotenv

from app.infrastructure.erc8004 import register_agent


load_dotenv()


def main() -> int:
    chain_id = int(os.getenv("ERC8004_CHAIN_ID", "42220"))
    registry = os.getenv(
        "ERC8004_IDENTITY_REGISTRY",
        "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432",
    )
    required = {
        "ERC8004_RPC_URL": os.getenv("ERC8004_RPC_URL"),
        "ERC8004_PRIVATE_KEY": os.getenv("ERC8004_PRIVATE_KEY"),
        "ERC8004_AGENT_URI": os.getenv("ERC8004_AGENT_URI"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"missing required variables: {', '.join(missing)}")

    result = register_agent(
        rpc_url=required["ERC8004_RPC_URL"],
        chain_id=chain_id,
        private_key=required["ERC8004_PRIVATE_KEY"],
        agent_uri=required["ERC8004_AGENT_URI"],
        identity_registry=registry,
    )
    print(f"agent_id={result.agent_id}")
    print(f"transaction_hash={result.transaction_hash}")
    print(f"owner={result.owner}")
    print(f"registry={result.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
