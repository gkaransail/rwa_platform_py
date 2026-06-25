# Standard Operating Procedure — RWA Tokenization Platform

## Overview

Full-stack platform for issuing and managing ERC-20 security tokens that represent fractional ownership of real-world assets.

| Layer | Technology |
|---|---|
| Smart contract | Vyper 0.4 — compiled to Ethereum bytecode |
| Blockchain interaction | web3.py |
| Tests | pytest + eth-tester (in-memory EVM, no node required) |
| Frontend | Streamlit |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.14 | With the project `.venv` activated |
| Node.js 18+ | For the Hardhat local node |
| Hardhat | Installed in `../rwa_platform/contracts/` |

---

## First-Time Setup

```bash
# 1. Create virtual environment
python3.14 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (Vyper, web3.py, Streamlit)
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Default values work for local Hardhat — no edits needed
```

---

## Standard Workflow

### Step 1 — Compile the contract

```bash
python scripts/compile.py
```

Output: `compiled/RWAToken.json` (ABI + bytecode). Re-run any time `contracts/RWAToken.vy` changes.

### Step 2 — Start the local Ethereum node

In a separate terminal (requires the sibling `rwa_platform` JS project):

```bash
cd ../rwa_platform/contracts
npx hardhat node
```

Runs at `http://127.0.0.1:8545`. Provides 20 pre-funded test accounts.

### Step 3 — Deploy the contract

```bash
python scripts/deploy.py
```

Output: deploys `RWAToken` to the Hardhat node, mints the initial token allocation, and saves the contract address to `config.json`.

### Step 4 — Run the frontend

```bash
streamlit run frontend/app.py
```

Opens at **http://localhost:8501**.

---

## Frontend Operations

### Asset Overview tab
Read-only. Shows asset metadata, token price, issuance progress, and contract address. No private key required.

### My Portfolio tab
Shows balance, USD value, ownership percentage, and KYC status for the connected wallet. Requires a private key in the sidebar.

### Transfer tab
Sends tokens to another address. Both sender and recipient must be whitelisted. Requires a private key.

### Admin tab
Owner-only operations. Requires the deployer's private key.

| Operation | What it does |
|---|---|
| Pause / Unpause | Freezes or resumes all token transfers |
| Mint Tokens | Issues new tokens to a whitelisted address (cannot exceed the supply cap) |
| Burn Tokens | Permanently destroys tokens from any holder's balance |
| Manage Whitelist | Approves or revokes KYC status for an investor address |
| Update Asset Details | Updates on-chain name, description, and USD valuation |

---

## Running Tests

Tests use an in-memory EVM — no Hardhat node required.

```bash
# Run full test suite
pytest tests/ -v

# Run a specific test class
pytest tests/test_rwa_token.py::TestTransfers -v -s
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RPC_URL` | `http://127.0.0.1:8545` | Ethereum node URL |
| `DEPLOYER_PRIVATE_KEY` | — | **Required for deploy.** Hardhat test key is pre-filled in `.env.example` |

---

## Contract Parameters

Configured as constants in `scripts/deploy.py`:

| Constant | Description |
|---|---|
| `TOKEN_NAME` | Full token name (e.g. `Marina Bay Residences Token`) |
| `TOKEN_SYMBOL` | Ticker symbol (e.g. `MBRT`) |
| `ASSET_NAME` | On-chain asset identifier |
| `ASSET_DESC` | Asset description stored on-chain |
| `ASSET_LOC` | Physical location string |
| `ASSET_VALUE` | Total asset value in USD cents |
| `TOTAL_TOKENS` | Hard supply cap (in wei, 18 decimals) |
| `INITIAL_MINT` | Tokens minted to deployer at launch |

To tokenize a different asset: update these constants, re-run `deploy.py`.

---

## Deploying from a DD Report (AI Integration)

The `research_agents` system can deploy a contract automatically using parameters extracted from a due diligence report. See `research_agents/SOP.md → Tokenizing an Asset`.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `❌ Run python scripts/compile.py first` | `compiled/RWAToken.json` missing | Run compile step |
| `Cannot connect to http://127.0.0.1:8545` | Hardhat node not running | Start Hardhat in a separate terminal |
| `❌ Set DEPLOYER_PRIVATE_KEY in .env` | `.env` file missing | `cp .env.example .env` |
| Streamlit shows "contract not deployed" | `config.json` missing | Run `python scripts/deploy.py` |
| Admin tab: "not owner" warning | Wrong private key in sidebar | Use the deployer key from `.env` |
| Tests fail after contract changes | Cached compiled artifact stale | Re-run `python scripts/compile.py` |

---

## File Structure

```
rwa_platform_py/
├── contracts/
│   └── RWAToken.vy          Vyper smart contract
├── scripts/
│   ├── compile.py           Vyper → ABI + bytecode
│   └── deploy.py            deploy to Ethereum node
├── tests/
│   └── test_rwa_token.py    pytest test suite
├── frontend/
│   └── app.py               Streamlit web app
├── compiled/
│   └── RWAToken.json        generated by compile.py
├── config.json              generated by deploy.py (contract address)
├── .env                     local config (not committed)
├── .env.example             template
└── SOP.md                   this file
```
