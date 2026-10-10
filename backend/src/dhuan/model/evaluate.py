"""Entry point for evaluation: run metrics + regenerate the model card.

`make evaluate` and `/v1/validation` both read the artifacts this produces.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dhuan.model.train import ARTIFACTS, evaluate


def run(train: bool = False, regenerate_card: bool = True) -> dict[str, object]:
    evaluate(train=train, save=True)
    if regenerate_card:
        script = Path(__file__).resolve().parents[4] / "scripts" / "generate_model_card.py"
        if script.exists():
            subprocess.run([sys.executable, str(script)], check=True)  # noqa: S603 - our own script
    loaded = json.loads((ARTIFACTS / "metrics.json").read_text())
    metrics: dict[str, object] = loaded
    return metrics


if __name__ == "__main__":
    print(json.dumps(run(train="--train" in sys.argv), indent=2, default=str))
