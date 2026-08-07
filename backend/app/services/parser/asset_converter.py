from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from os import getenv
from pathlib import Path

from backend.app.config import load_dotenv


@dataclass(frozen=True)
class ConversionResult:
    status: str
    render_path: Path | None
    message: str
    tool: str | None = None


def convert_vector_asset(source_path: Path, asset_id: str) -> ConversionResult:
    """Try to convert a vector image to browser-friendly PNG.

    The current MVP keeps this optional because Windows dev machines often do
    not have a WMF-capable converter installed. Failure is explicit and lets the
    parser create a visible placeholder instead.
    """
    load_dotenv()
    magick_binary = getenv("MAGICK_BINARY", "magick")
    magick = shutil.which(magick_binary)
    if magick:
        output_path = source_path.with_name(f"{asset_id}.png")
        result = subprocess.run(
            [magick, str(source_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            message = "Converted vector asset with ImageMagick."
            if result.returncode != 0:
                stderr = (result.stderr or result.stdout or "").strip()
                message = f"Converted vector asset with ImageMagick warnings: {stderr}"
            return ConversionResult(
                status="converted",
                render_path=output_path,
                message=message,
                tool=magick_binary,
            )
        stderr = (result.stderr or result.stdout or "").strip()
        return ConversionResult(
            status="failed",
            render_path=None,
            message=f"ImageMagick failed to convert asset: {stderr}",
            tool=magick_binary,
        )

    return ConversionResult(
        status="unavailable",
        render_path=None,
        message="No WMF/EMF converter found. Install ImageMagick and rerun with --convert-images.",
        tool=None,
    )
