"""Isolated command used so PDF timeout can terminate the renderer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import ReportContext
from .pdf_renderer import render_pdf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    arguments = parser.parse_args()
    payload = json.loads(arguments.context.read_text(encoding="utf-8"))
    render_pdf(
        ReportContext.model_validate(payload),
        arguments.output,
        arguments.font,
    )


if __name__ == "__main__":
    main()
