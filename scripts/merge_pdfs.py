from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Merge multiple PDFs into one.")
    p.add_argument(
        "--input",
        required=True,
        help="Input folder containing PDFs (merged in filename sort order)",
    )
    p.add_argument("--output", required=True, help="Output PDF path")
    return p


def main() -> int:
    args = build_parser().parse_args()
    in_dir = Path(args.input)
    out_pdf = Path(args.output)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    pdfs = sorted([p for p in in_dir.glob("*.pdf") if p.is_file()])
    if not pdfs:
        raise SystemExit(f"No PDFs found in: {in_dir}")

    writer = PdfWriter()

    for pdf in pdfs:
        reader = PdfReader(str(pdf))
        for page in reader.pages:
            writer.add_page(page)

    with out_pdf.open("wb") as f:
        writer.write(f)

    print(f"Merged {len(pdfs)} PDFs into: {out_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
