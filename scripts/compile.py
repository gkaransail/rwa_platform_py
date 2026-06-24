"""
compile.py — Compile the Vyper contract to ABI + bytecode.

Run this once before deploying or running tests:
    python scripts/compile.py

What it does:
  1. Reads the Vyper source code from contracts/RWAToken.vy
  2. Calls the Vyper compiler (same package you installed via pip)
  3. Saves the ABI and bytecode to compiled/RWAToken.json

ABI  = the "menu" of the contract — lists all functions and their argument types.
       The frontend (Streamlit) uses this to know how to call each function.

bytecode = the compiled EVM machine code that gets deployed to the blockchain.
"""

import json
from pathlib import Path
from vyper import compile_code

CONTRACT = Path(__file__).parent.parent / "contracts" / "RWAToken.vy"
OUTPUT   = Path(__file__).parent.parent / "compiled"  / "RWAToken.json"


def main():
    print(f"Compiling {CONTRACT.name}...")

    source = CONTRACT.read_text()

    # compile_code returns a dict with whatever output formats you request
    compiled = compile_code(source, output_formats=["abi", "bytecode"])

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "abi":      compiled["abi"],
        "bytecode": compiled["bytecode"],
    }, indent=2))

    fn_names = [fn["name"] for fn in compiled["abi"] if fn["type"] == "function"]
    print(f"✅ Compiled successfully → {OUTPUT}")
    print(f"   Functions: {', '.join(fn_names)}")


if __name__ == "__main__":
    main()
