from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.app.config import Settings
from backend.app.document_parser import DocumentParseError, extract_document_text
from backend.app.review_service import ReviewServiceError, create_review_service
from backend.app.schemas import ReviewResponse

EVALUATION_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = EVALUATION_DIR / "results"


def build_output_path(document_path: Path, model: str, output_dir: Path) -> Path:
    document_label = document_path.stem.removeprefix("sample_").removesuffix(
        "_design"
    )
    safe_document = _safe_filename_part(document_label)
    safe_model = _safe_filename_part(model)
    return output_dir / f"{safe_document}_{safe_model}.json"


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned or "unknown"


def run_review(document_path: Path, settings: Settings, output_dir: Path) -> Path:
    if settings.demo_mode:
        raise RuntimeError(
            "OPENAI_API_KEYが未設定です。評価用の実レビュー結果はデモモードでは保存しません。"
        )
    if not document_path.is_file():
        raise FileNotFoundError(f"設計書が見つかりません: {document_path}")
    if document_path.stat().st_size > settings.max_file_size_bytes:
        max_mb = settings.max_file_size_bytes // (1024 * 1024)
        raise ValueError(f"ファイルサイズは{max_mb}MB以下にしてください。")

    content = document_path.read_bytes()
    document_text = extract_document_text(document_path.name, content)
    review = create_review_service(settings).review(document_text)
    response = ReviewResponse.from_review(
        document_name=document_path.name,
        review=review,
        demo_mode=False,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_output_path(document_path, settings.openai_model, output_dir)
    payload = {
        "model": settings.openai_model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **response.model_dump(mode="json"),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="既存のOpenAI review serviceを実行し、評価用JSONを保存します。"
    )
    parser.add_argument("document", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="結果保存先（default: evaluation/results）",
    )
    args = parser.parse_args(argv)

    try:
        output_path = run_review(
            document_path=args.document,
            settings=Settings.from_env(),
            output_dir=args.output_dir,
        )
    except (
        DocumentParseError,
        ReviewServiceError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"Review error: {exc}", file=sys.stderr)
        return 2

    print(f"Review result saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
