"""
deploy.py — Deploy RWAToken to a running Ethereum node.

Prerequisites:
  1. Compiled: python scripts/compile.py
  2. Node running: npx hardhat node   (in contracts/ of the JS project)
     OR any other Ethereum node (Anvil, Geth, Sepolia, etc.)

Run:
    python scripts/deploy.py

What it does:
  1. Connects to the Ethereum node via JSON-RPC (HTTP)
  2. Loads the compiled ABI + bytecode
  3. Signs and sends the constructor transaction
  4. Waits for the transaction to be mined (included in a block)
  5. Saves the deployed address to config.json
  6. Mints an initial allocation to the deployer
"""

import json, os
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
RPC_URL     = os.getenv("RPC_URL", "http://127.0.0.1:8545")
PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")

if not PRIVATE_KEY:
    raise SystemExit("❌ Set DEPLOYER_PRIVATE_KEY in .env (copy .env.example)")

# ── Asset parameters ──────────────────────────────────────────────────────────
TOKEN_NAME   = "Marina Bay Residences Token"
TOKEN_SYMBOL = "MBRT"
ASSET_NAME   = "Marina Bay Residences — Unit 2401"
ASSET_DESC   = "Luxury 3-bed apartment in the Marina Bay financial district. 1,850 sq ft. Est. rental yield 4.8% p.a."
ASSET_LOC    = "Marina Bay, Singapore"
ASSET_VALUE  = 3_500_000_00       # $3,500,000.00 in cents
TOTAL_TOKENS = 1_000_000 * 10**18 # 1,000,000 tokens (each divisible to 18 decimal places)
INITIAL_MINT = 100_000  * 10**18  # 100,000 tokens = 10% initial issuance


def main():
    # ── Connect ───────────────────────────────────────────────────────────────
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise SystemExit(f"❌ Cannot connect to {RPC_URL}. Is the node running?")

    account = w3.eth.account.from_key(PRIVATE_KEY)
    balance = w3.from_wei(w3.eth.get_balance(account.address), "ether")
    print(f"Deploying from: {account.address}")
    print(f"Balance:        {balance:.4f} ETH\n")

    # ── Load compiled contract ────────────────────────────────────────────────
    compiled_path = Path(__file__).parent.parent / "compiled" / "RWAToken.json"
    if not compiled_path.exists():
        raise SystemExit("❌ Run `python scripts/compile.py` first.")

    compiled = json.loads(compiled_path.read_text())
    factory  = w3.eth.contract(abi=compiled["abi"], bytecode=compiled["bytecode"])

    # ── Deploy ────────────────────────────────────────────────────────────────
    # build_transaction() returns an unsigned tx dict.
    # We sign it locally with our private key, then send the signed bytes.
    # This is safer than sending the raw key to the node.
    print("Deploying contract...")
    deploy_tx = factory.constructor(
        TOKEN_NAME,
        TOKEN_SYMBOL,
        ASSET_NAME,
        ASSET_DESC,
        ASSET_LOC,
        ASSET_VALUE,
        TOTAL_TOKENS,
    ).build_transaction({
        "from":     account.address,
        "nonce":    w3.eth.get_transaction_count(account.address),
        "gas":      3_000_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed  = w3.eth.account.sign_transaction(deploy_tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    address = receipt.contractAddress

    print(f"✅ Deployed to:  {address}")
    print(f"   Gas used:     {receipt.gasUsed:,}")

    # ── Save address ──────────────────────────────────────────────────────────
    config_path = Path(__file__).parent.parent / "config.json"
    config_path.write_text(json.dumps({"address": address, "deployer": account.address}, indent=2))
    print(f"\n📦 Saved to config.json")

    # ── Mint initial allocation ───────────────────────────────────────────────
    print("\nMinting initial tokens...")
    token = w3.eth.contract(address=address, abi=compiled["abi"])

    mint_tx = token.functions.mint(
        account.address,
        INITIAL_MINT,
    ).build_transaction({
        "from":     account.address,
        "nonce":    w3.eth.get_transaction_count(account.address),
        "gas":      200_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed  = w3.eth.account.sign_transaction(mint_tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)

    balance_tokens = w3.from_wei(token.functions.balanceOf(account.address).call(), "ether")
    print(f"🪙 Minted {balance_tokens:,.0f} MBRT to {account.address}")
    print(f"\nDone! Open the Streamlit app: streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
