# RWA Tokenization Platform — Python Edition

Full-stack real-world asset tokenization, **100% Python**:

| Layer | Technology | Why |
|---|---|---|
| Smart contract | **Vyper** | Python-like syntax, compiles to Ethereum bytecode |
| Compile + deploy | **web3.py** | Python library to talk to Ethereum |
| Tests | **pytest + eth-tester** | Python test runner with in-memory EVM |
| Frontend | **Streamlit** | Python web app, no JavaScript needed |

> Compare with the JS version in `rwa_platform/` to see how the same project looks in two different stacks.

---

## File reading order for beginners

### 1. `contracts/RWAToken.vy` — Read this first

Vyper is a deliberately simple language. If you know Python, you can read Vyper.

Key differences from Python:
```python
# Python:
def transfer(receiver, amount):
    self.balance[sender] -= amount

# Vyper (0.4.x):
@external
def transfer(receiver: address, amount: uint256) -> bool:
    self.balanceOf[sender] -= amount   # every variable needs a type
    return True
```

Things to look for in the file:
- `@external` — callable from outside the contract (like a public API endpoint)
- `@internal` — private helper, only callable from within the contract
- `@view` — read-only function, free to call (no gas)
- `HashMap[address, uint256]` — like a Python dict, but lives on-chain
- `msg.sender` — the address that called this function (like `request.user` in web apps)
- `assert condition, "error message"` — reverts the whole transaction if false
- `log EventName(arg1, arg2)` — emits an event (like a console.log that the blockchain stores)

---

### 2. `tests/test_rwa_token.py` — Read this second

The tests are the best specification of what the contract does. Read the test names top to bottom — they read like a requirements doc.

```
TestDeployment::test_token_name_and_symbol
TestDeployment::test_owner_is_whitelisted
TestWhitelist::test_non_owner_cannot_whitelist    ← access control
TestMinting::test_cannot_exceed_cap              ← supply cap
TestTransfers::test_cannot_transfer_to_non_whitelisted  ← KYC compliance
TestPause::test_transfer_blocked_when_paused     ← emergency stop
```

The test setup:
```python
# eth-tester gives you a fake blockchain entirely in Python memory
tester = EthereumTester(PyEVMBackend())
w3 = Web3(Web3.EthereumTesterProvider(tester))

# Deploy a fresh contract before each test
tx_hash = factory.constructor(...).transact({"from": owner})
```

---

### 3. `scripts/compile.py` — Read this third

Short file. Calls the Vyper compiler and saves ABI + bytecode to `compiled/RWAToken.json`.

```python
from vyper import compile_code
compiled = compile_code(source, output_formats=["abi", "bytecode"])
```

**What is ABI?** The contract's "menu" — a JSON description of every function and what types it accepts. Required by web3.py and Streamlit to call the contract correctly.

**What is bytecode?** The compiled machine code that gets deployed to the blockchain.

---

### 4. `scripts/deploy.py` — Read this fourth

Shows the full transaction lifecycle:

```python
# Step 1: build the unsigned transaction
tx = factory.constructor(...).build_transaction({
    "from": account.address,
    "nonce": w3.eth.get_transaction_count(account.address),  # prevents replay attacks
    "gas": 3_000_000,
})

# Step 2: sign it locally (private key never sent to the node)
signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

# Step 3: broadcast the signed bytes
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

# Step 4: wait for it to be mined
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
```

**What is a nonce?** A counter on your account. Every transaction you send must have a unique nonce to prevent the same transaction being submitted twice.

**What is gas?** The fee you pay to run code on Ethereum. Higher gas = miners prioritise your transaction.

---

### 5. `frontend/app.py` — Read this last

Streamlit turns a Python script into a web app. The important concept here is **reading vs writing**:

```python
# READING — free, instant, no signing needed
balance = contract.functions.balanceOf(address).call()

# WRITING — costs gas, must be signed, triggers MetaMask-equivalent popup
receipt = send_tx(w3, contract.functions.transfer(to, amount), private_key)
```

The `send_tx()` helper shows the full sign-and-send pattern you'll use in every web3 app.

---

## Quick start

```bash
# 1. Create a virtual environment (keeps packages isolated to this project)
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# (the default values work for local Hardhat node — no edits needed)

# 4. Compile the contract
python scripts/compile.py

# 5. Run tests (no node needed — uses in-memory EVM)
pytest tests/ -v

# 6. Start local Ethereum node (needs Node.js + Hardhat from the JS project)
cd ../rwa_platform/contracts && npx hardhat node

# 7. Deploy
cd ../../rwa_platform_py && python scripts/deploy.py

# 8. Start the app
streamlit run frontend/app.py
```

---

## Project structure

```
rwa_platform_py/
│
├── contracts/
│   └── RWAToken.vy          ← Vyper contract (READ FIRST)
│
├── scripts/
│   ├── compile.py           ← Vyper → ABI + bytecode
│   └── deploy.py            ← deploy to Ethereum node
│
├── tests/
│   └── test_rwa_token.py    ← pytest (READ SECOND)
│
├── frontend/
│   └── app.py               ← Streamlit web app
│
├── compiled/                ← generated by compile.py (gitignored)
│   └── RWAToken.json
│
├── config.json              ← generated by deploy.py (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Glossary

| Term | Python analogy | Explanation |
|---|---|---|
| **Smart contract** | A Python class deployed to a server you can't take down | Code + data living permanently on the blockchain |
| **Vyper** | Python with strict types | Python-like language that compiles to Ethereum bytecode |
| **ERC-20** | An interface/protocol | The standard all fungible tokens implement (transfer, balanceOf, etc.) |
| **ABI** | A `.pyi` type stub file | Describes every function: name, argument types, return types |
| **bytecode** | A compiled `.pyc` file | What actually runs on the EVM (Ethereum Virtual Machine) |
| **address** | A unique user ID | 42-character hex string identifying a wallet or contract |
| **gas** | CPU credits | Fee paid per computation step; prevents infinite loops |
| **transaction** | An HTTP POST request | State-changing call; signed, broadcast, mined, then permanent |
| **nonce** | A request sequence number | Prevents duplicate transactions from being mined twice |
| **provider** | A database read connection | Read-only connection to the blockchain |
| **signer** | An authenticated session | Wallet that can sign and pay for transactions |
| **whitelist** | An allowlist | Addresses approved to hold/transfer this token (KYC-verified) |
| **eth-tester** | pytest's `tmp_path` fixture | Temporary in-memory blockchain, wiped between tests |

---

## Experiments to try

1. **Run one test in verbose mode** to see what's happening step by step:
   ```bash
   pytest tests/test_rwa_token.py::TestTransfers -v -s
   ```

2. **Read a value from the deployed contract** in a Python shell:
   ```python
   from web3 import Web3
   import json
   w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
   config   = json.load(open("config.json"))
   compiled = json.load(open("compiled/RWAToken.json"))
   token = w3.eth.contract(address=config["address"], abi=compiled["abi"])
   print(token.functions.assetName().call())
   print(token.functions.totalSupply().call() / 10**18, "tokens")
   ```

3. **Change the asset** — edit the constants in `scripts/deploy.py` (ASSET_NAME, ASSET_VALUE, etc.), redeploy, and watch the Streamlit UI update.

4. **Write a new test** — add a test case to `tests/test_rwa_token.py` and run it. Try: "investor can read their own ownership percentage".

5. **Break the contract intentionally** — change `assert self.whitelist[to]` in the contract, recompile, rerun tests, and see which tests fail.
