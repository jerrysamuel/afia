"""Create a signed x402 v2 EIP-3009 payload locally.

This prints only the signed JSON payload. The payer key is read from
X402_PAYER_PRIVATE_KEY and is never printed or persisted.
"""

import argparse
import asyncio
import json
import os

from eth_account import Account
from dotenv import load_dotenv
from x402 import x402Client
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.schemas import PaymentRequired, PaymentRequirements, ResourceInfo


load_dotenv()


async def create_payload(args: argparse.Namespace) -> dict:
    private_key = os.getenv("X402_PAYER_PRIVATE_KEY")
    if not private_key:
        raise SystemExit("X402_PAYER_PRIVATE_KEY is required")

    account = Account.from_key(private_key)
    requirements = PaymentRequirements(
        scheme="exact",
        network=args.network,
        asset=args.asset,
        amount=str(args.amount),
        payTo=args.pay_to,
        maxTimeoutSeconds=args.timeout,
        extra={"name": args.asset_name, "version": args.asset_version},
    )
    payment_required = PaymentRequired(
        accepts=[requirements],
        resource=ResourceInfo(url=args.resource),
    )
    client = x402Client()
    client.register(args.network, ExactEvmScheme(account))
    payload = await client.create_payment_payload(payment_required)
    return payload.model_dump(by_alias=True, exclude_none=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--amount", type=int, required=True)
    parser.add_argument("--pay-to", required=True)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--network", default="eip155:11142220")
    parser.add_argument("--asset-name", default="USDC")
    parser.add_argument("--asset-version", default="2")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--resource", default="https://afia.example/orders")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(create_payload(args)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
