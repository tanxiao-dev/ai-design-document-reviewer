from typing import Protocol

from openai import OpenAI, OpenAIError

from .config import Settings
from .prompts import SYSTEM_PROMPT, build_review_request
from .schemas import AIReviewResult, ReviewIssue


class ReviewServiceError(RuntimeError):
    """Raised when the AI review cannot be completed."""


class ReviewService(Protocol):
    def review(self, document_text: str) -> AIReviewResult: ...


class OpenAIReviewService:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def review(self, document_text: str) -> AIReviewResult:
        try:
            response = self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_review_request(document_text)},
                ],
                text_format=AIReviewResult,
                store=False,
            )
        except OpenAIError as exc:
            raise ReviewServiceError(
                "OpenAI APIによるレビューに失敗しました。設定と接続状況を確認してください。"
            ) from exc

        if response.output_parsed is None:
            raise ReviewServiceError(
                "OpenAI APIから構造化されたレビュー結果を取得できませんでした。"
            )
        return response.output_parsed


class DemoReviewService:
    def review(self, document_text: str) -> AIReviewResult:
        del document_text
        return AIReviewResult(
            summary=(
                "デモ用の固定レビュー結果です。要件の明確性、入力制約、"
                "異常時の動作について確認が必要な例を表示しています。"
            ),
            issues=[
                ReviewIssue(
                    id="ISSUE-001",
                    finding_type="Issue",
                    category="表現の曖昧さ",
                    severity="High",
                    location="処理仕様",
                    original_text="システムは適切な時間内に応答する。",
                    problem="「適切な時間」の基準値がなく、性能要件を検証できません。",
                    suggestion=(
                        "通常時とピーク時の応答時間目標を、測定条件と合わせて数値で定義してください。"
                    ),
                ),
                ReviewIssue(
                    id="ISSUE-002",
                    finding_type="Issue",
                    category="入力条件の不足",
                    severity="Medium",
                    location="入力項目定義",
                    original_text="ユーザーIDを入力する。",
                    problem=(
                        "ユーザーIDのデータ型、最大長、使用可能文字、必須／任意が定義されていません。"
                    ),
                    suggestion=(
                        "型、最大長、文字種、必須条件、前後空白の扱いを項目定義に追加してください。"
                    ),
                ),
                ReviewIssue(
                    id="ISSUE-003",
                    finding_type="Confirmation",
                    category="異常処理",
                    severity="Low",
                    location="位置不明",
                    original_text="",
                    problem=(
                        "外部サービスがタイムアウトした場合の利用者向け表示と再試行方針を確認できません。"
                    ),
                    suggestion=(
                        "タイムアウト値、再試行回数、エラー表示、運用通知の要否を確認してください。"
                    ),
                ),
            ],
        )


def create_review_service(settings: Settings) -> ReviewService:
    if settings.demo_mode:
        return DemoReviewService()
    return OpenAIReviewService(
        api_key=settings.openai_api_key or "",
        model=settings.openai_model,
    )
