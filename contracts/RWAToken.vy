# pragma version 0.4.1
"""
@title  RWAToken
@notice ERC-20 security token representing fractional ownership of a
        real-world asset (property, fund, etc.).

        Vyper is a Python-like language for writing smart contracts.
        Key differences from Python:
          - Every variable and parameter must declare its type
          - No inheritance — you write everything explicitly
          - Integer overflow/underflow is checked automatically
          - @external = callable from outside   @internal = private helper
          - @view = read-only (free to call)    no decorator = can modify state (costs gas)

        What this contract does:
          1. Issues tokens that represent % ownership of a real asset
          2. Only KYC-approved (whitelisted) addresses can hold or send tokens
          3. The owner (issuer) controls minting, burning, and the whitelist
          4. Token transfers can be paused in emergencies
"""

# ── Events ────────────────────────────────────────────────────────────────────
# Events are like logs — emitted when something happens.
# External tools (frontends, explorers) listen for these to track activity.
# `indexed` means you can filter/search by that field efficiently.

event Transfer:
    sender:   indexed(address)
    receiver: indexed(address)
    value:    uint256

event Approval:
    owner:   indexed(address)
    spender: indexed(address)
    value:   uint256

event Whitelisted:
    account: indexed(address)
    status:  bool

event Minted:
    to:     indexed(address)
    amount: uint256

event Burned:
    from_addr: indexed(address)
    amount:    uint256


# ── State variables ───────────────────────────────────────────────────────────
# `public(...)` auto-generates a getter function (so you can read it from outside).
# `HashMap` is like a Python dict but lives on-chain. Unset keys default to 0/False/"".

# Standard ERC-20 fields (every token must have these)
name:        public(String[64])
symbol:      public(String[8])
decimals:    public(uint8)
totalSupply: public(uint256)

balanceOf:  public(HashMap[address, uint256])
allowance:  public(HashMap[address, HashMap[address, uint256]])

# RWA-specific fields
totalTokenSupply: public(uint256)       # hard cap — can never mint beyond this
assetName:        public(String[128])
assetDescription: public(String[512])
assetLocation:    public(String[128])
assetValueUSD:    public(uint256)       # total value in USD cents (1_00 = $1.00)

# Access control
owner:     public(address)
paused:    public(bool)
whitelist: public(HashMap[address, bool])


# ── Constructor ───────────────────────────────────────────────────────────────
# Called exactly once when the contract is deployed. Sets initial state.
# `msg.sender` is the address that deployed the contract.

@deploy
def __init__(
    _token_name:         String[64],
    _token_symbol:       String[8],
    _asset_name:         String[128],
    _asset_description:  String[512],
    _asset_location:     String[128],
    _asset_value_usd:    uint256,
    _total_token_supply: uint256,
):
    self.name             = _token_name
    self.symbol           = _token_symbol
    self.decimals         = 18
    self.totalTokenSupply = _total_token_supply
    self.assetName        = _asset_name
    self.assetDescription = _asset_description
    self.assetLocation    = _asset_location
    self.assetValueUSD    = _asset_value_usd
    self.owner            = msg.sender

    # Auto-whitelist the deployer so they can receive minted tokens
    self.whitelist[msg.sender] = True
    log Whitelisted(account=msg.sender, status=True)


# ── Internal helper ───────────────────────────────────────────────────────────
# @internal means only other functions in this contract can call this.
# We reuse this logic in transfer() and transferFrom() to avoid duplication.

@internal
def _transfer(sender: address, receiver: address, amount: uint256):
    assert not self.paused,              "RWAToken: paused"
    assert self.whitelist[sender],       "RWAToken: sender not whitelisted"
    assert self.whitelist[receiver],     "RWAToken: recipient not whitelisted"
    assert self.balanceOf[sender] >= amount, "RWAToken: insufficient balance"

    self.balanceOf[sender]   -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=sender, receiver=receiver, value=amount)


# ── ERC-20 standard functions ─────────────────────────────────────────────────
# These are the functions every ERC-20 token must have.
# Any app (Uniswap, MetaMask, etc.) knows how to call these.

@external
def transfer(receiver: address, amount: uint256) -> bool:
    """Send tokens from your own address to receiver."""
    self._transfer(msg.sender, receiver, amount)
    return True


@external
def transferFrom(sender: address, receiver: address, amount: uint256) -> bool:
    """
    Send tokens on behalf of `sender` (requires prior approve() call).
    Used by exchanges and DeFi protocols.
    """
    self.allowance[sender][msg.sender] -= amount   # reverts if allowance too low
    self._transfer(sender, receiver, amount)
    return True


@external
def approve(spender: address, amount: uint256) -> bool:
    """Allow `spender` to move up to `amount` of your tokens."""
    self.allowance[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, value=amount)
    return True


# ── Whitelist (KYC compliance) ────────────────────────────────────────────────

@external
def setWhitelist(account: address, status: bool):
    """Add or remove an address from the KYC whitelist. Owner only."""
    assert msg.sender == self.owner, "RWAToken: not owner"
    self.whitelist[account] = status
    log Whitelisted(account=account, status=status)


# ── Token issuance ────────────────────────────────────────────────────────────

@external
def mint(to: address, amount: uint256):
    """Create new tokens and assign them to `to`. Owner only."""
    assert msg.sender == self.owner,          "RWAToken: not owner"
    assert self.whitelist[to],                "RWAToken: recipient not whitelisted"
    assert self.totalSupply + amount <= self.totalTokenSupply, "RWAToken: cap exceeded"

    self.balanceOf[to] += amount
    self.totalSupply   += amount
    log Transfer(sender=empty(address), receiver=to, value=amount)  # Transfer from zero address = mint
    log Minted(to=to, amount=amount)


@external
def burn(from_addr: address, amount: uint256):
    """Destroy tokens (e.g. investor exit or forced redemption). Owner only."""
    assert msg.sender == self.owner,                "RWAToken: not owner"
    assert self.balanceOf[from_addr] >= amount,     "RWAToken: insufficient balance"

    self.balanceOf[from_addr] -= amount
    self.totalSupply           -= amount
    log Transfer(sender=from_addr, receiver=empty(address), value=amount)  # Transfer to zero address = burn
    log Burned(from_addr=from_addr, amount=amount)


# ── Emergency controls ────────────────────────────────────────────────────────

@external
def pause():
    """Freeze all token transfers. Owner only."""
    assert msg.sender == self.owner, "RWAToken: not owner"
    self.paused = True


@external
def unpause():
    """Resume token transfers. Owner only."""
    assert msg.sender == self.owner, "RWAToken: not owner"
    self.paused = False


@external
def updateAssetDetails(_name: String[128], _description: String[512], _value_usd: uint256):
    """Update on-chain asset metadata (e.g. after a revaluation). Owner only."""
    assert msg.sender == self.owner, "RWAToken: not owner"
    self.assetName        = _name
    self.assetDescription = _description
    self.assetValueUSD    = _value_usd


# ── View helpers ──────────────────────────────────────────────────────────────
# @view functions are free to call — they read state but never change it.

@view
@external
def tokenValueUSD() -> uint256:
    """Price per token in USD cents, based on current asset valuation."""
    if self.totalSupply == 0:
        return 0
    return (self.assetValueUSD * 10**18) // self.totalSupply


@view
@external
def ownershipBps(account: address) -> uint256:
    """Ownership in basis points (100 bps = 1%, 10000 bps = 100%)."""
    if self.totalSupply == 0:
        return 0
    return (self.balanceOf[account] * 10000) // self.totalSupply
