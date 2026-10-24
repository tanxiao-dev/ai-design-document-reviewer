from pathlib import Path

import pytest

from backend.app.config import Settings
from evaluation.run_review import build_output_path, run_review


def test_output_filename_contains_document_and_model(tmp_path: Path) -> None:
    output_path = build_output_path(
        Path("samples/sample_problematic_design.md"),
        "gpt/example:model",
        tmp_path,
    )

    assert output_path == tmp_path / "problematic_gpt-example-model.json"


def test_run_review_rejects_demo_mode_before_api_call(tmp_path: Path) -> None:
    settings = Settings(openai_api_key=None)

    with pytest.raises(RuntimeError, match="デモモードでは保存しません"):
        run_review(Path("not-read.md"), settings, tmp_path)

    assert list(tmp_path.iterdir()) == []
