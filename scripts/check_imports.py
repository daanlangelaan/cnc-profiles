# scripts/check_imports.py
import traceback

def check(modname: str, attr: str):
    print(f"\n=== Checking {modname}.{attr} ===")
    try:
        mod = __import__(modname, fromlist=['*'])
        path = getattr(mod, "__file__", "<??>")
        has_attr = hasattr(mod, attr)
        print(f"OK: {modname} loaded from {path}")
        print(f"Has attribute '{attr}': {has_attr}")
        if not has_attr:
            print(f"TIP: define `{attr}` in {modname.replace('.', '/')}.py")
    except Exception:
        print(f"EXC while importing {modname}:")
        traceback.print_exc()

if __name__ == "__main__":
    check("cncapp.excel_import", "load_excel")
    check("cncapp.pipeline", "run")
