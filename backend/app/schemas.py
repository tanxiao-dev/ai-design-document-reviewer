from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["High", "Medium", "Low"]
FindingType = Literal["Issue", "Confirmation"]


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="一意な指摘ID（例: ISSUE-001）")
    finding_type: FindingType = Field(
        description="実在する問題はIssue、追加確認事項はConfirmation"
    )
    category: str = Field(description="指摘カテゴリ")
    severity: Severity = Field(description="重要度")
    location: str = Field(description="章・節・段落。特定できない場合は位置不明")
    original_text: str = Field(description="根拠となる原文。引用できない場合は空文字")
    problem: str = Field(description="指摘内容と、その理由")
    suggestion: str = Field(description="実行可能な修正案")


class AIReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="設計書全体の日本語によるレビュー要約")
    issues: list[ReviewIssue] = Field(description="根拠を確認できた指摘と確認事項")


class ReviewResponse(BaseModel):
    document_name: str
    summary: str
    issue_count: int
    high_count: int
    medium_count: int
    low_count: int
    demo_mode: bool
    issues: list[ReviewIssue]

    @classmethod
    def from_review(
        cls,
        document_name: str,
        review: AIReviewResult,
        demo_mode: bool,
    ) -> "ReviewResponse":
        return cls(
            document_name=document_name,
            summary=review.summary,
            issue_count=len(review.issues),
            high_count=sum(item.severity == "High" for item in review.issues),
            medium_count=sum(item.severity == "Medium" for item in review.issues),
            low_count=sum(item.severity == "Low" for item in review.issues),
            demo_mode=demo_mode,
            issues=review.issues,
        )
