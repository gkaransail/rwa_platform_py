import json, os
from pathlib import Path

import streamlit as st
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="RWA Platform",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).parent.parent


def load_contract_data():
    compiled_path = ROOT / "compiled" / "RWAToken.json"
    config_path   = ROOT / "config.json"

    if not compiled_path.exists():
        return None, None, "Run `python scripts/compile.py` first."
    if not config_path.exists():
        return None, None, "Run `python scripts/deploy.py` to deploy the contract."

    compiled = json.loads(compiled_path.read_text())
    config   = json.loads(config_path.read_text())
    return compiled["abi"], config["address"], None


def get_contract(w3, abi, address):
    return w3.eth.contract(address=address, abi=abi)


def send_tx(w3, contract_fn, private_key, gas=300_000):
    account = w3.eth.account.from_key(private_key)
    tx = contract_fn.build_transaction({
        "from":     account.address,
        "nonce":    w3.eth.get_transaction_count(account.address),
        "gas":      gas,
        "gasPrice": w3.eth.gas_price,
    })
    signed  = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def fmt_tokens(raw_wei):
    if raw_wei is None:
        return "—"
    return f"{raw_wei / 10**18:,.2f}"


def fmt_usd(cents):
    if cents is None:
        return "—"
    return f"${cents / 100:,.2f}"


with st.sidebar:
    st.markdown("## ⬡ RWA Platform")
    st.caption("Real-World Asset Tokenization")
    st.divider()

    rpc_url = st.text_input(
        "Node RPC URL",
        value=os.getenv("RPC_URL", "http://127.0.0.1:8545"),
    )

    private_key = st.text_input(
        "Your Private Key",
        type="password",
        placeholder="0xac0974be...",
    )

    if private_key:
        try:
            acct  = Web3().eth.account.from_key(private_key)
            short = f"{acct.address[:6]}…{acct.address[-4:]}"
            st.success(f"Account: {short}")
        except Exception:
            st.error("Invalid private key format")
            private_key = None

    st.divider()
    st.caption("⚠️ Only enter test account keys. Never use real wallet keys in any web app.")


w3 = Web3(Web3.HTTPProvider(rpc_url))

if not w3.is_connected():
    st.error(f"Cannot connect to {rpc_url}. Start the node: `npx hardhat node`")
    st.stop()

st.caption(f"✅ Connected to node · Chain ID {w3.eth.chain_id} · Block #{w3.eth.block_number}")

abi, address, err = load_contract_data()
if err:
    st.warning(f"⚠️ {err}")
    st.code("python scripts/compile.py\npython scripts/deploy.py")
    st.stop()

contract = get_contract(w3, abi, address)

asset_name  = contract.functions.assetName().call()
asset_desc  = contract.functions.assetDescription().call()
asset_loc   = contract.functions.assetLocation().call()
asset_value = contract.functions.assetValueUSD().call()
total_sup   = contract.functions.totalTokenSupply().call()
circ_sup    = contract.functions.totalSupply().call()
token_val   = contract.functions.tokenValueUSD().call()
owner_addr  = contract.functions.owner().call()
is_paused   = contract.functions.paused().call()
token_name  = contract.functions.name().call()
symbol      = contract.functions.symbol().call()

user_address = None
is_owner     = False
if private_key:
    user_address = Web3().eth.account.from_key(private_key).address
    is_owner     = user_address.lower() == owner_addr.lower()


tab_asset, tab_portfolio, tab_transfer, tab_admin = st.tabs([
    "📋 Asset Overview",
    "💼 My Portfolio",
    "↗ Transfer",
    "🔐 Admin",
])


with tab_asset:
    st.title(asset_name)
    st.caption(f"📍 {asset_loc}")

    if is_paused:
        st.error("⏸ Token transfers are currently PAUSED")

    st.markdown(f"> {asset_desc}")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Asset Value",   fmt_usd(asset_value))
    col2.metric("Token Price",         fmt_usd(token_val))
    col3.metric("Tokens Issued",       fmt_tokens(circ_sup), delta=f"of {fmt_tokens(total_sup)}")
    col4.metric("Token Symbol",        symbol)

    if total_sup > 0:
        pct = circ_sup / total_sup
        st.write("**Issuance Progress**")
        st.progress(pct, text=f"{pct*100:.1f}% issued ({fmt_tokens(circ_sup)} of {fmt_tokens(total_sup)} {symbol})")

    st.divider()
    st.caption(f"Contract: `{address}`")
    st.caption(f"Token: {token_name} ({symbol}) · Owner: `{owner_addr}`")


with tab_portfolio:
    st.header("My Portfolio")

    if not user_address:
        st.info("Enter your private key in the sidebar to view your portfolio.")
        st.stop()

    balance_raw  = contract.functions.balanceOf(user_address).call()
    on_whitelist = contract.functions.whitelist(user_address).call()
    own_bps      = contract.functions.ownershipBps(user_address).call()

    balance_tokens = balance_raw / 10**18
    value_usd      = balance_tokens * (token_val / 100) if token_val else 0
    ownership_pct  = own_bps / 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Token Balance",  f"{balance_tokens:,.2f} {symbol}")
    col2.metric("Portfolio Value", f"${value_usd:,.2f}")
    col3.metric("Ownership",      f"{ownership_pct:.2f}%")
    col4.metric("KYC Status",     "✅ Whitelisted" if on_whitelist else "❌ Not whitelisted")

    st.divider()
    st.caption(f"Address: `{user_address}`")

    if not on_whitelist:
        st.warning("Your address is not whitelisted. You cannot send or receive tokens until the issuer approves your KYC.")


with tab_transfer:
    st.header("Transfer Tokens")

    if not private_key:
        st.info("Enter your private key in the sidebar to send tokens.")
        st.stop()

    on_whitelist = contract.functions.whitelist(user_address).call()
    if not on_whitelist:
        st.error("Your address is not whitelisted. Contact the issuer to complete KYC before transferring.")
        st.stop()

    balance_raw = contract.functions.balanceOf(user_address).call()
    balance_fmt = balance_raw / 10**18
    st.caption(f"Available balance: **{balance_fmt:,.2f} {symbol}**")

    with st.form("transfer_form"):
        to_addr = st.text_input("Recipient Address", placeholder="0x…")
        amount  = st.number_input("Amount", min_value=0.0, max_value=float(balance_fmt), step=1.0)
        submit  = st.form_submit_button("Send Tokens")

    if submit:
        if not w3.is_address(to_addr):
            st.error("Invalid address format.")
        elif amount <= 0:
            st.error("Amount must be greater than 0.")
        elif not contract.functions.whitelist(to_addr).call():
            st.error("Recipient is not whitelisted. Only KYC-approved addresses can receive tokens.")
        else:
            with st.spinner("Sending transaction…"):
                try:
                    receipt = send_tx(
                        w3,
                        contract.functions.transfer(to_addr, int(amount * 10**18)),
                        private_key,
                    )
                    st.success(f"✅ Sent {amount:,.2f} {symbol} to `{to_addr[:10]}…`")
                    st.caption(f"Transaction: `{receipt.transactionHash.hex()}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Transaction failed: {e}")


with tab_admin:
    st.header("Admin Panel")

    if not private_key:
        st.info("Enter your private key in the sidebar.")
        st.stop()

    if not is_owner:
        st.warning(f"Admin functions require the owner account (`{owner_addr[:10]}…`).")
        st.stop()

    st.success("✅ Connected as owner")

    st.subheader("Contract Status")
    col1, col2 = st.columns([3, 1])
    col1.write(f"{'⏸ Transfers are **PAUSED**' if is_paused else '▶ Transfers are **active**'}")
    with col2:
        if is_paused:
            if st.button("Unpause", type="primary"):
                with st.spinner("Unpausing…"):
                    send_tx(w3, contract.functions.unpause(), private_key)
                st.rerun()
        else:
            if st.button("Pause All Transfers"):
                with st.spinner("Pausing…"):
                    send_tx(w3, contract.functions.pause(), private_key)
                st.rerun()

    st.divider()

    st.subheader("Mint Tokens")
    st.caption("Recipient must be whitelisted first.")
    with st.form("mint_form"):
        mint_to  = st.text_input("Recipient Address", placeholder="0x…", key="mint_to")
        mint_amt = st.number_input("Amount to Mint", min_value=0.0, step=1000.0, key="mint_amt")
        mint_btn = st.form_submit_button("Mint Tokens", type="primary")

    if mint_btn:
        if not w3.is_address(mint_to):
            st.error("Invalid address.")
        elif mint_amt <= 0:
            st.error("Amount must be > 0.")
        else:
            with st.spinner("Minting…"):
                try:
                    send_tx(w3, contract.functions.mint(mint_to, int(mint_amt * 10**18)), private_key)
                    st.success(f"✅ Minted {mint_amt:,.0f} {symbol} to `{mint_to[:10]}…`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.divider()

    st.subheader("Burn Tokens")
    st.caption("Permanently destroys tokens from any holder's balance.")
    with st.form("burn_form"):
        burn_from = st.text_input("Burn from Address", placeholder="0x…")
        burn_amt  = st.number_input("Amount to Burn", min_value=0.0, step=1000.0)
        burn_btn  = st.form_submit_button("Burn Tokens")

    if burn_btn:
        if not w3.is_address(burn_from):
            st.error("Invalid address.")
        else:
            with st.spinner("Burning…"):
                try:
                    send_tx(w3, contract.functions.burn(burn_from, int(burn_amt * 10**18)), private_key)
                    st.success(f"✅ Burned {burn_amt:,.0f} {symbol} from `{burn_from[:10]}…`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.divider()

    st.subheader("Manage Whitelist (KYC)")
    with st.form("whitelist_form"):
        wl_addr   = st.text_input("Investor Address", placeholder="0x…")
        wl_action = st.radio("Action", ["✅ Approve (whitelist)", "❌ Revoke"])
        wl_btn    = st.form_submit_button("Update Whitelist")

    if wl_btn:
        if not w3.is_address(wl_addr):
            st.error("Invalid address.")
        else:
            status = "Approve" in wl_action
            with st.spinner("Updating…"):
                try:
                    send_tx(w3, contract.functions.setWhitelist(wl_addr, status), private_key)
                    action_word = "approved" if status else "revoked"
                    st.success(f"✅ `{wl_addr[:10]}…` {action_word}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.caption("Check whitelist status of any address:")
    check_addr = st.text_input("Address to check", placeholder="0x…", key="check_wl")
    if check_addr and w3.is_address(check_addr):
        status = contract.functions.whitelist(check_addr).call()
        if status:
            st.success(f"✅ `{check_addr}` is whitelisted")
        else:
            st.error(f"❌ `{check_addr}` is NOT whitelisted")

    st.divider()

    st.subheader("Update Asset Details")
    with st.form("asset_form"):
        new_name  = st.text_input("Asset Name",    value=asset_name)
        new_desc  = st.text_area("Description",    value=asset_desc)
        new_value = st.number_input("Asset Value (USD)", value=float(asset_value / 100), step=10_000.0)
        asset_btn = st.form_submit_button("Update Details")

    if asset_btn:
        with st.spinner("Updating…"):
            try:
                send_tx(
                    w3,
                    contract.functions.updateAssetDetails(new_name, new_desc, int(new_value * 100)),
                    private_key,
                )
                st.success("✅ Asset details updated")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
