import pytest
from pydantic import ValidationError

from app.schemas import AIReviewResult, ReviewIssue, ReviewResponse


def make_issue(severity: str = "High") -> ReviewIssue:
    return ReviewIssue.model_validate(
        {
            "id": "ISSUE-001",
            "finding_type": "Issue",
            "category": "曖昧表現",
            "severity": severity,
            "location": "概要",
            "original_text": "速やかに処理する。",
            "problem": "時間の基準がありません。",
            "suggestion": "秒数を定義してください。",
        }
    )


def test_structured_output_model_and_counts() -> None:
    review = AIReviewResult(summary="要確認です。", issues=[make_issue()])

    response = ReviewResponse.from_review("design.md", review, demo_mode=False)

    assert response.issue_count == 1
    assert response.high_count == 1
    assert response.medium_count == 0
    assert response.low_count == 0


def test_severity_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        make_issue("Critical")
