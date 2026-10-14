"""Location of the bundled config folder (rates, labels, doc types, checks).

The tool is installed editable (setup.ps1 runs ``pip install -e .``), so the
config folder sits beside ``src/`` and can be edited in place each year.
"""

from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
