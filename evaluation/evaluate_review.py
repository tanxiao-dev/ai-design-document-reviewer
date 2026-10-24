from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal, cast


AdjudicationStatus = Literal[
    "VALID_NEW_FINDING",
    "FALSE_POSITIVE",
    "NEEDS_CONFIRMATION",
    "OUT_OF_SCOPE_FOR_BASIC_DESIGN",
]
ALLOWED_ADJUDICATION_STATUSES = {
    "VALID_NEW_FINDING",
    "FALSE_POSITIVE",
    "NEEDS_CONFIRMATION",
    "OUT_OF_SCOPE_FOR_BASIC_DESIGN",
}
ReviewScope = Literal[
    "BASIC_DESIGN_CORE",
    "BASIC_DESIGN_CONFIRMATION",
    "DETAIL_DESIGN",
]
ALLOWED_REVIEW_SCOPES = {
    "BASIC_DESIGN_CORE",
    "BASIC_DESIGN_CONFIRMATION",
    "DETAIL_DESIGN",
}


@dataclass(frozen=True)
class ExpectedIssue:
    id: str
    category: str
    description: str
    severity: str
    keywords: tuple[str, ...]
    review_scope: ReviewScope | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExpectedIssue":
        required = {"id", "category", "description", "severity", "keywords"}
        missing = required - data.keys()
        if missing:
            raise ValueError(
                f"Expected issueに必須項目がありません: {', '.join(sorted(missing))}"
            )
        if not isinstance(data["keywords"], list):
            raise ValueError("Expected issueのkeywordsは配列で指定してください。")
        review_scope = data.get("review_scope")
        if review_scope is not None and review_scope not in ALLOWED_REVIEW_SCOPES:
            allowed = ", ".join(sorted(ALLOWED_REVIEW_SCOPES))
            raise ValueError(
                f"未対応のreview_scopeです: {review_scope} (allowed: {allowed})"
            )
        return cls(
            id=str(data["id"]),
            category=str(data["category"]),
            description=str(data["description"]),
            severity=str(data["severity"]),
            keywords=tuple(str(item) for item in data["keywords"]),
            review_scope=(
                cast(ReviewScope, review_scope)
                if review_scope is not None
                else None
            ),
        )


@dataclass(frozen=True)
class MatchCandidate:
    expected_index: int
    ai_index: int
    score: float
    matched_keywords: tuple[str, ...]
    category_matched: bool
    description_similarity: float


@dataclass(frozen=True)
class IssueMatch:
    expected: ExpectedIssue
    ai_issue: dict[str, Any]
    score: float
    matched_keywords: tuple[str, ...]
    category_matched: bool
    description_similarity: float


@dataclass(frozen=True)
class IssueAdjudication:
    issue_id: str
    status: AdjudicationStatus
    comment: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueAdjudication":
        required = {"issue_id", "status", "comment"}
        missing = required - data.keys()
        if missing:
            raise ValueError(
                "Adjudicationに必須項目がありません: "
                f"{', '.join(sorted(missing))}"
            )

        status = str(data["status"])
        if status not in ALLOWED_ADJUDICATION_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_ADJUDICATION_STATUSES))
            raise ValueError(
                f"未対応のadjudication statusです: {status} (allowed: {allowed})"
            )
        return cls(
            issue_id=str(data["issue_id"]),
            status=cast(AdjudicationStatus, status),
            comment=str(data["comment"]),
        )


@dataclass(frozen=True)
class EvaluationReport:
    document: str
    expected_count: int
    ai_count: int
    matches: tuple[IssueMatch, ...]
    missed: tuple[ExpectedIssue, ...]
    extras: tuple[dict[str, Any], ...]
    recall: float | None
    precision: float | None
    f1: float | None
    basic_design_core_expected: int
    basic_design_core_matched: int
    basic_design_core_missed: int
    basic_design_core_recall: float | None
    adjudications: tuple[IssueAdjudication, ...] = ()

    @property
    def matched_count(self) -> int:
        return len(self.matches)


def normalize_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return "".join(character for character in normalized if character.isalnum())


def evaluate_data(
    expected_data: dict[str, Any],
    review_data: dict[str, Any],
    adjudication_data: dict[str, Any] | None = None,
) -> EvaluationReport:
    expected_items = expected_data.get("expected_issues")
    ai_items = review_data.get("issues")
    if not isinstance(expected_items, list):
        raise ValueError("expected_issuesは配列で指定してください。")
    if not isinstance(ai_items, list):
        raise ValueError("AI review結果のissuesは配列で指定してください。")
    if not all(isinstance(item, dict) for item in ai_items):
        raise ValueError("AI review結果の各issueはオブジェクトで指定してください。")

    expected = [ExpectedIssue.from_dict(item) for item in expected_items]
    candidates: list[MatchCandidate] = []
    for expected_index, expected_issue in enumerate(expected):
        for ai_index, ai_issue in enumerate(ai_items):
            candidate = _build_candidate(
                expected_index, ai_index, expected_issue, ai_issue
            )
            if candidate is not None:
                candidates.append(candidate)

    candidates.sort(key=lambda item: (-item.score, item.expected_index, item.ai_index))
    used_expected: set[int] = set()
    used_ai: set[int] = set()
    selected: list[MatchCandidate] = []
    for candidate in candidates:
        if (
            candidate.expected_index in used_expected
            or candidate.ai_index in used_ai
        ):
            continue
        used_expected.add(candidate.expected_index)
        used_ai.add(candidate.ai_index)
        selected.append(candidate)

    selected.sort(key=lambda item: item.expected_index)
    matches = tuple(
        IssueMatch(
            expected=expected[item.expected_index],
            ai_issue=ai_items[item.ai_index],
            score=item.score,
            matched_keywords=item.matched_keywords,
            category_matched=item.category_matched,
            description_similarity=item.description_similarity,
        )
        for item in selected
    )
    missed = tuple(
        item for index, item in enumerate(expected) if index not in used_expected
    )
    extras = tuple(item for index, item in enumerate(ai_items) if index not in used_ai)
    adjudications = _load_adjudications(adjudication_data, extras)

    expected_count = len(expected)
    ai_count = len(ai_items)
    matched_count = len(matches)
    if expected_count == 0:
        recall = None
        precision = None
        f1 = None
    else:
        recall = matched_count / expected_count
        precision = matched_count / ai_count if ai_count else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

    core_expected_count = sum(
        item.review_scope == "BASIC_DESIGN_CORE" for item in expected
    )
    core_matched_count = sum(
        item.expected.review_scope == "BASIC_DESIGN_CORE" for item in matches
    )
    core_missed_count = core_expected_count - core_matched_count
    core_recall = (
        core_matched_count / core_expected_count
        if core_expected_count
        else None
    )

    return EvaluationReport(
        document=str(
            expected_data.get("document")
            or review_data.get("document_name")
            or "unknown"
        ),
        expected_count=expected_count,
        ai_count=ai_count,
        matches=matches,
        missed=missed,
        extras=extras,
        recall=recall,
        precision=precision,
        f1=f1,
        basic_design_core_expected=core_expected_count,
        basic_design_core_matched=core_matched_count,
        basic_design_core_missed=core_missed_count,
        basic_design_core_recall=core_recall,
        adjudications=adjudications,
    )


def _load_adjudications(
    adjudication_data: dict[str, Any] | None,
    extras: tuple[dict[str, Any], ...],
) -> tuple[IssueAdjudication, ...]:
    if adjudication_data is None:
        return ()

    items = adjudication_data.get("adjudications")
    if not isinstance(items, list):
        raise ValueError("adjudicationsは配列で指定してください。")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("各adjudicationはオブジェクトで指定してください。")

    adjudications = tuple(IssueAdjudication.from_dict(item) for item in items)
    issue_ids = [item.issue_id for item in adjudications]
    if len(issue_ids) != len(set(issue_ids)):
        raise ValueError("adjudicationのissue_idが重複しています。")

    extra_ids = {str(item.get("id", "")) for item in extras}
    unknown_ids = sorted(set(issue_ids) - extra_ids)
    if unknown_ids:
        raise ValueError(
            "Extra Issueに存在しないissue_idがadjudicationに含まれています: "
            f"{', '.join(unknown_ids)}"
        )
    return adjudications


def _build_candidate(
    expected_index: int,
    ai_index: int,
    expected: ExpectedIssue,
    ai_issue: dict[str, Any],
) -> MatchCandidate | None:
    searchable_fields = [
        ai_issue.get("category", ""),
        ai_issue.get("location", ""),
        ai_issue.get("original_text", ""),
        ai_issue.get("problem", ""),
    ]
    searchable_text = normalize_text(" ".join(str(item) for item in searchable_fields))
    matched_keywords = tuple(
        keyword
        for keyword in expected.keywords
        if normalize_text(keyword) and normalize_text(keyword) in searchable_text
    )

    expected_category = normalize_text(expected.category)
    ai_category = normalize_text(ai_issue.get("category", ""))
    category_matched = bool(
        expected_category
        and ai_category
        and (
            expected_category in ai_category
            or ai_category in expected_category
        )
    )

    expected_description = normalize_text(expected.description)
    comparison_fields = [
        normalize_text(ai_issue.get("problem", "")),
        normalize_text(ai_issue.get("original_text", "")),
    ]
    description_similarity = max(
        (
            SequenceMatcher(None, expected_description, value).ratio()
            for value in comparison_fields
            if value
        ),
        default=0.0,
    )

    required_keyword_hits = 1 if len(expected.keywords) <= 1 else 2
    qualifies = (
        len(matched_keywords) >= required_keyword_hits
        or (category_matched and len(matched_keywords) >= 1)
        or description_similarity >= 0.58
    )
    if not qualifies:
        return None

    severity_matched = expected.severity == str(ai_issue.get("severity", ""))
    score = (
        len(matched_keywords) * 3
        + int(category_matched) * 2
        + description_similarity * 2
        + int(severity_matched) * 0.5
    )
    return MatchCandidate(
        expected_index=expected_index,
        ai_index=ai_index,
        score=score,
        matched_keywords=matched_keywords,
        category_matched=category_matched,
        description_similarity=description_similarity,
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSONのルートはオブジェクトである必要があります: {path}")
    return data


def format_report(report: EvaluationReport) -> str:
    def format_metric(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.2f}"

    lines = [
        f"Document: {report.document}",
        "",
        f"Expected Issues: {report.expected_count}",
        f"AI Issues: {report.ai_count}",
        "",
        f"Matched: {report.matched_count}",
        f"Missed: {len(report.missed)}",
        f"Extra Issues: {len(report.extras)}",
        "Extra issues require human adjudication.",
        "",
        f"Recall: {format_metric(report.recall)}",
        f"Precision: {format_metric(report.precision)}",
        f"F1: {format_metric(report.f1)}",
        "",
        f"Basic Design Core Expected: {report.basic_design_core_expected}",
        f"Basic Design Core Matched: {report.basic_design_core_matched}",
        f"Basic Design Core Missed: {report.basic_design_core_missed}",
        "Basic Design Core Recall: "
        f"{format_metric(report.basic_design_core_recall)}",
        "",
        "Matched Issues:",
    ]
    if report.matches:
        for match in report.matches:
            ai_id = match.ai_issue.get("id", "ID不明")
            keyword_text = ", ".join(match.matched_keywords) or "なし"
            lines.append(
                f"{match.expected.id} -> {ai_id} "
                f"(keywords: {keyword_text}; "
                f"category: {'yes' if match.category_matched else 'no'}; "
                f"score: {match.score:.2f})"
            )
    else:
        lines.append("(none)")

    lines.extend(["", "Missed Issues:"])
    if report.missed:
        lines.extend(f"{item.id}: {item.description}" for item in report.missed)
    else:
        lines.append("(none)")

    adjudication_by_id = {
        item.issue_id: item for item in report.adjudications
    }
    lines.extend(["", "Extra Issue Details:"])
    if report.extras:
        for index, item in enumerate(report.extras, start=1):
            ai_id = item.get("id", f"AI-{index:03d}")
            category = item.get("category", "カテゴリ不明")
            problem = item.get("problem", "")
            lines.append(f"{ai_id}: [{category}] {problem}")
            adjudication = adjudication_by_id.get(str(ai_id))
            if adjudication is None:
                lines.append("  Adjudication: (not provided)")
            else:
                lines.append(f"  Adjudication: {adjudication.status}")
                lines.append(
                    f"  Comment: {adjudication.comment or '(none)'}"
                )
    else:
        lines.append("(none)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Expected issuesとAIレビュー結果をヒューリスティックに比較します。"
    )
    parser.add_argument("expected_json", type=Path)
    parser.add_argument("review_json", type=Path)
    parser.add_argument(
        "--adjudication",
        type=Path,
        help="Extra Issueに対する人手判定JSON（AI review結果自体は変更しません）",
    )
    args = parser.parse_args(argv)

    try:
        report = evaluate_data(
            load_json(args.expected_json),
            load_json(args.review_json),
            load_json(args.adjudication) if args.adjudication else None,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 2

    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
