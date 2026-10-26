import asyncio

import pytest

from app.infrastructure.x402 import X402PaymentProvider, X402SettlementResult, X402VerificationResult
from app.models.payments import Payment, PaymentAttempt, PaymentAttemptStatus


class FakeFacilitator:
    def __init__(self, verification, settlement):
        self.verification = verification
        self.settlement = settlement
        self.verify_calls = []
        self.settle_calls = []

    async def verify(self, payload, requirements):
        self.verify_calls.append((payload, requirements))
        return self.verification

    async def settle(self, payload, requirements):
        self.settle_calls.append((payload, requirements))
        return self.settlement


class Response:
    def __init__(self, **values):
        self.__dict__.update(values)


def make_payment():
    return Payment(id=1, order_id=10, amount_minor=1250, currency="USD", provider="x402")


def make_payload(provider: X402PaymentProvider, payment: Payment):
    requirements = provider.build_requirements(payment).model_dump(by_alias=True)
    return {
        "x402Version": 2,
        "resource": {"url": "https://afia.example/orders/10"},
        "accepted": requirements,
        "payload": {"signature": "0xabc", "authorization": {"value": requirements["amount"]}},
    }


def test_x402_verifies_against_server_authoritative_requirements():
    facilitator = FakeFacilitator(Response(is_valid=True, payer="0xabc", invalid_reason=None), Response(success=True, transaction="0xtx", payer="0xabc", error_reason=None, network="eip155:42220"))
    provider = X402PaymentProvider(facilitator, asset="0xasset", pay_to="0xmerchant")
    payment = make_payment()

    result = asyncio.run(provider.verify(payment, make_payload(provider, payment)))

    assert result.is_valid is True
    assert facilitator.verify_calls[0][1].amount == "12500000"


def test_x402_does_not_settle_when_verification_is_invalid():
    facilitator = FakeFacilitator(Response(is_valid=False, payer=None, invalid_reason="invalid_signature"), Response(success=True, transaction="0xtx", payer="0xabc", error_reason=None, network="eip155:42220"))
    provider = X402PaymentProvider(facilitator, asset="0xasset", pay_to="0xmerchant")
    result = asyncio.run(provider.verify(make_payment(), make_payload(provider, make_payment())))

    assert result.is_valid is False
    assert facilitator.settle_calls == []


def test_x402_settlement_returns_provider_transaction_reference():
    facilitator = FakeFacilitator(Response(is_valid=True, payer="0xabc", invalid_reason=None), Response(success=True, transaction="0xtx", payer="0xabc", error_reason=None, network="eip155:42220"))
    provider = X402PaymentProvider(facilitator, asset="0xasset", pay_to="0xmerchant")
    result = asyncio.run(provider.settle(make_payment(), make_payload(provider, make_payment())))

    assert result.success is True
    assert result.transaction == "0xtx"
    assert len(facilitator.settle_calls) == 1


def test_x402_testnet_usdc_requirements_use_documented_asset_and_metadata():
    provider = X402PaymentProvider(
        FakeFacilitator(Response(is_valid=True), Response(success=True)),
        network="eip155:11142220",
        asset="0x01C5C0122039549AD1493B8220cABEdD739BC44E",
        pay_to="0xmerchant",
        asset_name="USDC",
        asset_version="2",
    )

    requirements = provider.build_requirements(make_payment())

    assert requirements.network == "eip155:11142220"
    assert requirements.asset == "0x01C5C0122039549AD1493B8220cABEdD739BC44E"
    assert requirements.extra == {"name": "USDC", "version": "2"}
