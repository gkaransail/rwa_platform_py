import json
from pathlib import Path
from vyper import compile_code

CONTRACT = Path(__file__).parent.parent / "contracts" / "RWAToken.vy"
OUTPUT   = Path(__file__).parent.parent / "compiled"  / "RWAToken.json"


def main():
    print(f"Compiling {CONTRACT.name}...")

    compiled = compile_code(CONTRACT.read_text(), output_formats=["abi", "bytecode"])

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps({"abi": compiled["abi"], "bytecode": compiled["bytecode"]}, indent=2))

    fn_names = [fn["name"] for fn in compiled["abi"] if fn["type"] == "function"]
    print(f"✅ Compiled successfully → {OUTPUT}")
    print(f"   Functions: {', '.join(fn_names)}")


if __name__ == "__main__":
    main()
