"""
test_rwa_token.py — pytest test suite for RWAToken.vy

Run with:  pytest tests/ -v

No external node needed — tests use eth-tester which runs an in-memory
EVM (Ethereum Virtual Machine) entirely inside Python. This is the
fastest way to test contracts.

How it works:
  1. EthereumTester creates a fake blockchain in memory
  2. We deploy a fresh contract before each test
  3. We call contract functions and assert the expected results
  4. Everything is thrown away after the test session ends

Fixtures (the @pytest.fixture functions) are helpers that create
shared objects (like the web3 connection or deployed contract)
so each test doesn't have to set these up itself.
"""

import pytest
from web3 import Web3
from eth_tester import EthereumTester, PyEVMBackend
from vyper import compile_code
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

CONTRACT_FILE = Path(__file__).parent.parent / "contracts" / "RWAToken.vy"
DECIMALS      = 10**18               # 1 token = 10^18 base units (like cents to dollars)
TOTAL_SUPPLY  = 1_000_000 * DECIMALS
MINT_AMOUNT   =   100_000 * DECIMALS
ASSET_VALUE   = 3_500_000_00         # $3.5M in cents


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def compiled():
    """Compile the Vyper contract once for the whole test session."""
    source = CONTRACT_FILE.read_text()
    return compile_code(source, output_formats=["abi", "bytecode"])


@pytest.fixture
def w3():
    """
    A fresh in-memory Ethereum blockchain for each test.
    scope not set → created fresh for every test function → tests can't affect each other.
    PyEVMBackend is a pure-Python EVM implementation.
    """
    tester = EthereumTester(PyEVMBackend())
    return Web3(Web3.EthereumTesterProvider(tester))


@pytest.fixture
def accounts(w3):
    """10 pre-funded test accounts. accounts[0] = deployer/owner."""
    return w3.eth.accounts


@pytest.fixture
def token(w3, compiled, accounts):
    """
    Deploy a fresh RWAToken contract before each test.
    Returns a web3.py Contract object you can call functions on.
    """
    owner = accounts[0]
    factory = w3.eth.contract(abi=compiled["abi"], bytecode=compiled["bytecode"])

    tx_hash = factory.constructor(
        "Marina Bay Residences Token",
        "MBRT",
        "Marina Bay Residences — Unit 2401",
        "Luxury 3-bedroom apartment",
        "Marina Bay, Singapore",
        ASSET_VALUE,
        TOTAL_SUPPLY,
    ).transact({"from": owner})

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return w3.eth.contract(address=receipt.contractAddress, abi=compiled["abi"])


# Helper: whitelist an account and mint tokens to it
def setup_investor(token, investor, amount, owner):
    token.functions.setWhitelist(investor, True).transact({"from": owner})
    token.functions.mint(investor, amount).transact({"from": owner})


# ── Deployment tests ──────────────────────────────────────────────────────────

class TestDeployment:
    def test_token_name_and_symbol(self, token):
        assert token.functions.name().call()   == "Marina Bay Residences Token"
        assert token.functions.symbol().call() == "MBRT"
        assert token.functions.decimals().call() == 18

    def test_asset_metadata(self, token):
        assert token.functions.assetName().call()     == "Marina Bay Residences — Unit 2401"
        assert token.functions.assetValueUSD().call() == ASSET_VALUE
        assert token.functions.totalTokenSupply().call() == TOTAL_SUPPLY

    def test_owner_is_whitelisted(self, token, accounts):
        assert token.functions.whitelist(accounts[0]).call() is True

    def test_starts_with_zero_supply(self, token):
        assert token.functions.totalSupply().call() == 0


# ── Whitelist tests ───────────────────────────────────────────────────────────

class TestWhitelist:
    def test_owner_can_whitelist(self, token, accounts):
        token.functions.setWhitelist(accounts[1], True).transact({"from": accounts[0]})
        assert token.functions.whitelist(accounts[1]).call() is True

    def test_owner_can_revoke(self, token, accounts):
        token.functions.setWhitelist(accounts[1], True).transact({"from": accounts[0]})
        token.functions.setWhitelist(accounts[1], False).transact({"from": accounts[0]})
        assert token.functions.whitelist(accounts[1]).call() is False

    def test_non_owner_cannot_whitelist(self, token, accounts):
        with pytest.raises(Exception, match="RWAToken: not owner"):
            token.functions.setWhitelist(accounts[2], True).transact({"from": accounts[1]})


# ── Minting tests ─────────────────────────────────────────────────────────────

class TestMinting:
    def test_owner_can_mint_to_whitelisted(self, token, accounts):
        token.functions.setWhitelist(accounts[1], True).transact({"from": accounts[0]})
        token.functions.mint(accounts[1], MINT_AMOUNT).transact({"from": accounts[0]})
        assert token.functions.balanceOf(accounts[1]).call() == MINT_AMOUNT

    def test_cannot_mint_to_non_whitelisted(self, token, accounts):
        with pytest.raises(Exception, match="RWAToken: recipient not whitelisted"):
            token.functions.mint(accounts[2], MINT_AMOUNT).transact({"from": accounts[0]})

    def test_cannot_exceed_cap(self, token, accounts):
        token.functions.setWhitelist(accounts[1], True).transact({"from": accounts[0]})
        over_cap = TOTAL_SUPPLY + 1
        with pytest.raises(Exception, match="RWAToken: cap exceeded"):
            token.functions.mint(accounts[1], over_cap).transact({"from": accounts[0]})

    def test_non_owner_cannot_mint(self, token, accounts):
        with pytest.raises(Exception, match="RWAToken: not owner"):
            token.functions.mint(accounts[1], MINT_AMOUNT).transact({"from": accounts[1]})

    def test_total_supply_increases(self, token, accounts):
        token.functions.setWhitelist(accounts[1], True).transact({"from": accounts[0]})
        token.functions.mint(accounts[1], MINT_AMOUNT).transact({"from": accounts[0]})
        assert token.functions.totalSupply().call() == MINT_AMOUNT


# ── Transfer restriction tests ────────────────────────────────────────────────

class TestTransfers:
    def test_whitelisted_can_transfer_to_whitelisted(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        token.functions.setWhitelist(accounts[2], True).transact({"from": accounts[0]})
        token.functions.transfer(accounts[2], 1000 * DECIMALS).transact({"from": accounts[1]})
        assert token.functions.balanceOf(accounts[2]).call() == 1000 * DECIMALS

    def test_cannot_transfer_to_non_whitelisted(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        with pytest.raises(Exception, match="RWAToken: recipient not whitelisted"):
            token.functions.transfer(accounts[3], 100 * DECIMALS).transact({"from": accounts[1]})

    def test_revoked_sender_cannot_transfer(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        token.functions.setWhitelist(accounts[2], True).transact({"from": accounts[0]})
        # Revoke investor1 after they got tokens
        token.functions.setWhitelist(accounts[1], False).transact({"from": accounts[0]})
        with pytest.raises(Exception, match="RWAToken: sender not whitelisted"):
            token.functions.transfer(accounts[2], 100 * DECIMALS).transact({"from": accounts[1]})

    def test_insufficient_balance_reverts(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        token.functions.setWhitelist(accounts[2], True).transact({"from": accounts[0]})
        too_much = MINT_AMOUNT + 1
        with pytest.raises(Exception):
            token.functions.transfer(accounts[2], too_much).transact({"from": accounts[1]})


# ── Burn tests ────────────────────────────────────────────────────────────────

class TestBurning:
    def test_owner_can_burn(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        token.functions.burn(accounts[1], MINT_AMOUNT).transact({"from": accounts[0]})
        assert token.functions.balanceOf(accounts[1]).call() == 0
        assert token.functions.totalSupply().call() == 0

    def test_non_owner_cannot_burn(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        with pytest.raises(Exception, match="RWAToken: not owner"):
            token.functions.burn(accounts[1], MINT_AMOUNT).transact({"from": accounts[1]})


# ── Pause tests ───────────────────────────────────────────────────────────────

class TestPause:
    def test_owner_can_pause_and_unpause(self, token, accounts):
        token.functions.pause().transact({"from": accounts[0]})
        assert token.functions.paused().call() is True
        token.functions.unpause().transact({"from": accounts[0]})
        assert token.functions.paused().call() is False

    def test_transfer_blocked_when_paused(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        token.functions.setWhitelist(accounts[2], True).transact({"from": accounts[0]})
        token.functions.pause().transact({"from": accounts[0]})
        with pytest.raises(Exception, match="RWAToken: paused"):
            token.functions.transfer(accounts[2], 100 * DECIMALS).transact({"from": accounts[1]})

    def test_transfer_resumes_after_unpause(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        token.functions.setWhitelist(accounts[2], True).transact({"from": accounts[0]})
        token.functions.pause().transact({"from": accounts[0]})
        token.functions.unpause().transact({"from": accounts[0]})
        token.functions.transfer(accounts[2], 100 * DECIMALS).transact({"from": accounts[1]})
        assert token.functions.balanceOf(accounts[2]).call() == 100 * DECIMALS


# ── View helper tests ─────────────────────────────────────────────────────────

class TestViewHelpers:
    def test_token_value_usd(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        # $3,500,000 / 100,000 tokens = $35 per token = 3500 cents
        expected = ASSET_VALUE // (MINT_AMOUNT // DECIMALS)
        assert token.functions.tokenValueUSD().call() == expected

    def test_ownership_bps(self, token, accounts):
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        # 100,000 of 100,000 tokens = 100% = 10,000 bps
        assert token.functions.ownershipBps(accounts[1]).call() == 10_000

    def test_ownership_bps_partial(self, token, accounts):
        # Mint to two investors, check their bps add up to 10,000
        setup_investor(token, accounts[1], MINT_AMOUNT, accounts[0])
        setup_investor(token, accounts[2], MINT_AMOUNT, accounts[0])
        bps1 = token.functions.ownershipBps(accounts[1]).call()
        bps2 = token.functions.ownershipBps(accounts[2]).call()
        assert bps1 == 5_000
        assert bps2 == 5_000


# ── Asset metadata update tests ───────────────────────────────────────────────

class TestAssetMetadata:
    def test_owner_can_update(self, token, accounts):
        token.functions.updateAssetDetails(
            "New Building", "New Description", 4_000_000_00
        ).transact({"from": accounts[0]})
        assert token.functions.assetName().call()     == "New Building"
        assert token.functions.assetValueUSD().call() == 4_000_000_00

    def test_non_owner_cannot_update(self, token, accounts):
        with pytest.raises(Exception, match="RWAToken: not owner"):
            token.functions.updateAssetDetails(
                "Hack", "Hack", 1
            ).transact({"from": accounts[1]})
