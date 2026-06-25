# Architecture Overview

This document explains how the four layers of the platform fit together.

---

## System diagram

```
Browser (localhost:8501)
        │
        ▼
┌───────────────────┐
│  Streamlit UI     │  frontend/app.py — Python web app
│  (app.py)         │
└────────┬──────────┘
         │ web3.py (HTTP JSON-RPC)
         ▼
┌───────────────────┐
│  Hardhat Node     │  local in-memory Ethereum blockchain
│  :8545            │
└────────┬──────────┘
         │ EVM execution
         ▼
┌───────────────────┐
│  RWAToken.vy      │  Vyper smart contract (deployed on-chain)
│  (smart contract) │
└───────────────────┘
```

---

## Layer 1 — Smart contract (`contracts/RWAToken.vy`)

An ERC-20 security token written in Vyper. On top of standard token logic it adds three features:

**KYC whitelist**
Every `transfer()` and `transferFrom()` call goes through `_transfer()`, which asserts both sender and receiver are in `whitelist`. Unwhitelisted addresses cannot send or receive tokens.

**Supply cap**
`totalTokenSupply` is set at deploy time and never changes. `mint()` reverts if `totalSupply + amount` would exceed it.

**Emergency pause**
The owner can call `pause()` to freeze all transfers. `_transfer()` asserts `not self.paused` before moving any tokens.

Key on-chain state:

| Variable | Type | Purpose |
|---|---|---|
| `balanceOf` | `HashMap[address, uint256]` | Token balances |
| `whitelist` | `HashMap[address, bool]` | KYC-approved addresses |
| `totalTokenSupply` | `uint256` | Hard mint cap |
| `assetValueUSD` | `uint256` | Asset value in USD cents |
| `paused` | `bool` | Transfer freeze flag |

---

## Layer 2 — Local Ethereum node (Hardhat)

Runs at `http://127.0.0.1:8545`. It is a fake blockchain in memory — no real ETH, no real network. It provides pre-funded test accounts and mines transactions instantly.

Started separately from the JS project:
```bash
cd ../rwa_platform/contracts && npx hardhat node
```

---

## Layer 3 — Compile + deploy scripts (`scripts/`)

**`compile.py`** — calls the Vyper compiler, writes ABI and bytecode to `compiled/RWAToken.json`.

**`deploy.py`** — reads the compiled artifact, sends a deploy transaction signed with the deployer private key, saves the contract address to `config.json`, and mints the initial token supply.

Transaction signing flow (used in both deploy and the frontend):
```
build_transaction()        # unsigned tx dict
  → sign_transaction()     # signed locally — private key never sent to node
    → send_raw_transaction() # broadcast signed bytes
      → wait_for_transaction_receipt() # block until mined
```

---

## Layer 4 — Streamlit frontend (`frontend/app.py`)

A Python script that Streamlit turns into a web app. The entire script re-runs from top to bottom on every user interaction.

**Reading data** — free `view` calls, no gas, no signing:
```python
contract.functions.balanceOf(address).call()
```

**Writing data** — requires a private key, costs gas, goes through the sign-and-send flow above:
```python
send_tx(w3, contract.functions.transfer(to, amount), private_key)
```

### Tabs

| Tab | Access | What it does |
|---|---|---|
| Asset Overview | Public | Reads asset metadata and issuance progress from chain |
| My Portfolio | Requires private key | Shows balance, USD value, ownership %, KYC status |
| Transfer | Requires whitelisted key | Sends a signed `transfer()` transaction |
| Admin | Owner key only | Mint, burn, whitelist addresses, pause, update asset details |

---

## Data flow — reading vs writing

```
READ  →  .call()             →  free, instant, no signature
WRITE →  build → sign → send →  costs gas, mined into a block, permanent
```

All write operations check access control in the contract (`assert msg.sender == self.owner`, `assert self.whitelist[...]`). The frontend validates inputs before submitting but the contract is the authoritative enforcement layer.
