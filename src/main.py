import argparse, sys
from cncapp.models import Settings
from cncapp.excel_import import read_cutlist
from cncapp.pipeline import build_program

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="Excel cutlist (xlsx)")
    ap.add_argument("--out", dest="outfile", required=True, help="Output .tap")
    args = ap.parse_args()

    profiles = read_cutlist(args.infile)
    if not profiles:
        print("Geen profielen gevonden in Excel.", file=sys.stderr)
        sys.exit(1)

    settings = Settings()  # defaults, incl. Z-safe=85 en X0→Z85→Y300
    gcode = build_program(profiles, settings)

    with open(args.outfile, "w", encoding="utf-8") as f:
        f.write(gcode)

    print(f"OK → {args.outfile} ({len(gcode.splitlines())} regels)")

if __name__ == "__main__":
    main()
