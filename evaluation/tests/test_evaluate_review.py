import json
from copy import deepcopy
from pathlib import Path

import pytest

from evaluation.evaluate_review import evaluate_data, format_report

EVALUATION_DIR = Path(__file__).resolve().parents[1]


def expected_issue(
    issue_id: str,
    *,
    category: str = "権限",
    description: str = "権限の定義が不足している",
    keywords: list[str] | None = None,
    review_scope: str | None = None,
) -> dict[str, object]:
    issue: dict[str, object] = {
        "id": issue_id,
        "category": category,
        "description": description,
        "severity": "High",
        "keywords": keywords or ["権限", "管理者"],
    }
    if review_scope is not None:
        issue["review_scope"] = review_scope
    return issue


def ai_issue(
    issue_id: str,
    *,
    category: str = "権限",
    problem: str = "管理者の権限が定義されていません。",
) -> dict[str, str]:
    return {
        "id": issue_id,
        "finding_type": "Issue",
        "category": category,
        "severity": "High",
        "location": "利用者と権限",
        "original_text": "管理者",
        "problem": problem,
        "suggestion": "ロールごとの権限を定義してください。",
    }


def test_expected_issue_matches_ai_issue() -> None:
    report = evaluate_data(
        {"document": "sample.md", "expected_issues": [expected_issue("P01")]},
        {"issues": [ai_issue("ISSUE-001")]},
    )

    assert report.matched_count == 1
    assert report.matches[0].expected.id == "P01"
    assert report.matches[0].ai_issue["id"] == "ISSUE-001"
    assert report.recall == 1.0
    assert report.precision == 1.0


def test_legacy_expected_issue_without_scope_remains_compatible() -> None:
    report = evaluate_data(
        {"document": "legacy.md", "expected_issues": [expected_issue("P01")]},
        {"issues": [ai_issue("ISSUE-001")]},
    )

    assert report.recall == 1.0
    assert report.precision == 1.0
    assert report.basic_design_core_expected == 0
    assert report.basic_design_core_recall is None


def test_unmatched_expected_issue_is_missed() -> None:
    report = evaluate_data(
        {
            "document": "sample.md",
            "expected_issues": [
                expected_issue("P01"),
                expected_issue(
                    "P02",
                    category="性能",
                    description="応答時間の数値基準がない",
                    keywords=["応答時間", "秒以内"],
                ),
            ],
        },
        {"issues": [ai_issue("ISSUE-001")]},
    )

    assert report.matched_count == 1
    assert [item.id for item in report.missed] == ["P02"]
    assert report.recall == 0.5


def test_unmatched_ai_issue_is_extra() -> None:
    report = evaluate_data(
        {"document": "sample.md", "expected_issues": [expected_issue("P01")]},
        {
            "issues": [
                ai_issue("ISSUE-001"),
                ai_issue(
                    "ISSUE-002",
                    category="可用性",
                    problem="バックアップ方針の確認が必要です。",
                ),
            ]
        },
    )

    assert report.matched_count == 1
    assert [item["id"] for item in report.extras] == ["ISSUE-002"]
    assert report.precision == 0.5


def test_multiple_keywords_can_match_when_category_differs() -> None:
    report = evaluate_data(
        {
            "document": "sample.md",
            "expected_issues": [
                expected_issue(
                    "P06",
                    category="内部矛盾",
                    description="予約IDの定義が矛盾している",
                    keywords=["予約ID", "8桁", "VARCHAR(6)"],
                )
            ],
        },
        {
            "issues": [
                ai_issue(
                    "ISSUE-006",
                    category="データ定義",
                    problem="予約IDは8桁ですがDBはVARCHAR(6)で保持できません。",
                )
            ]
        },
    )

    assert report.matched_count == 1
    assert report.matches[0].category_matched is False
    assert report.matches[0].matched_keywords == ("予約ID", "8桁", "VARCHAR(6)")


def test_empty_ai_result_marks_expected_as_missed() -> None:
    report = evaluate_data(
        {"document": "sample.md", "expected_issues": [expected_issue("P01")]},
        {"issues": []},
    )

    assert report.matched_count == 0
    assert len(report.missed) == 1
    assert report.recall == 0.0
    assert report.precision == 0.0
    assert report.f1 == 0.0


def test_reference_with_no_expected_and_no_ai_issues_has_na_metrics() -> None:
    expected_data = json.loads(
        (EVALUATION_DIR / "expected_reference.json").read_text(encoding="utf-8")
    )

    report = evaluate_data(expected_data, {"issues": []})

    assert report.expected_count == 0
    assert report.ai_count == 0
    assert report.recall is None
    assert report.precision is None
    assert report.f1 is None
    output = format_report(report)
    assert "Expected Issues: 0" in output
    assert "Extra Issues: 0" in output
    assert "Recall: N/A" in output
    assert "Precision: N/A" in output
    assert "F1: N/A" in output
    assert "Extra issues require human adjudication." in output


def test_reference_extras_require_human_adjudication() -> None:
    report = evaluate_data(
        {"document": "reference.md", "expected_issues": []},
        {
            "issues": [
                ai_issue(
                    "ISSUE-001",
                    category="文書粒度",
                    problem="運用手順を別紙にするか確認が必要です。",
                )
            ]
        },
    )

    assert len(report.extras) == 1
    assert report.recall is None
    assert report.precision is None
    assert report.f1 is None
    output = format_report(report)
    assert "Extra Issues: 1" in output
    assert "Extra issues require human adjudication." in output
    assert "False Positive" not in output


@pytest.mark.parametrize(
    "status",
    [
        "VALID_NEW_FINDING",
        "FALSE_POSITIVE",
        "NEEDS_CONFIRMATION",
        "OUT_OF_SCOPE_FOR_BASIC_DESIGN",
    ],
)
def test_extra_issue_accepts_supported_human_adjudication(status: str) -> None:
    review_data = {
        "issues": [
            ai_issue(
                "ISSUE-001",
                category="インターフェース詳細",
                problem="詳細設計で確認する必要があります。",
            )
        ]
    }
    original_review = deepcopy(review_data)

    report = evaluate_data(
        {"document": "reference.md", "expected_issues": []},
        review_data,
        {
            "adjudications": [
                {
                    "issue_id": "ISSUE-001",
                    "status": status,
                    "comment": "基本設計のスコープを人手で確認する。",
                }
            ]
        },
    )

    assert report.adjudications[0].status == status
    assert report.adjudications[0].comment == "基本設計のスコープを人手で確認する。"
    assert report.recall is None
    assert report.precision is None
    assert report.f1 is None
    assert review_data == original_review
    output = format_report(report)
    assert f"Adjudication: {status}" in output
    assert "Comment: 基本設計のスコープを人手で確認する。" in output


def test_human_adjudication_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="未対応のadjudication status"):
        evaluate_data(
            {"document": "reference.md", "expected_issues": []},
            {"issues": [ai_issue("ISSUE-001")]},
            {
                "adjudications": [
                    {
                        "issue_id": "ISSUE-001",
                        "status": "UNREVIEWED",
                        "comment": "",
                    }
                ]
            },
        )


def test_human_adjudication_must_reference_an_extra_issue() -> None:
    with pytest.raises(ValueError, match="Extra Issueに存在しないissue_id"):
        evaluate_data(
            {"document": "reference.md", "expected_issues": []},
            {"issues": [ai_issue("ISSUE-001")]},
            {
                "adjudications": [
                    {
                        "issue_id": "ISSUE-999",
                        "status": "NEEDS_CONFIRMATION",
                        "comment": "",
                    }
                ]
            },
        )


def test_reference_adjudication_template_contains_four_unjudged_extras() -> None:
    data = json.loads(
        (
            EVALUATION_DIR
            / "adjudication"
            / "reference_gpt-5.6-terra.json"
        ).read_text(encoding="utf-8")
    )

    assert data["document"] == "sample_reference_design.md"
    assert len(data["adjudications"]) == 4
    assert [item["issue_id"] for item in data["adjudications"]] == [
        f"ISSUE-{index:03d}" for index in range(1, 5)
    ]
    assert {
        item["status"] for item in data["adjudications"]
    } == {"NEEDS_CONFIRMATION"}
    assert all("comment" in item for item in data["adjudications"])


def test_basic_design_core_recall_counts_only_core_issues() -> None:
    report = evaluate_data(
        {
            "document": "scope.md",
            "expected_issues": [
                expected_issue(
                    "C01", review_scope="BASIC_DESIGN_CORE"
                ),
                expected_issue(
                    "C02",
                    category="状態遷移",
                    description="状態遷移が不足している",
                    keywords=["状態", "遷移"],
                    review_scope="BASIC_DESIGN_CORE",
                ),
            ],
        },
        {"issues": [ai_issue("ISSUE-001")]},
    )

    assert report.basic_design_core_expected == 2
    assert report.basic_design_core_matched == 1
    assert report.basic_design_core_missed == 1
    assert report.basic_design_core_recall == 0.5


def test_detail_design_miss_does_not_lower_core_recall() -> None:
    report = evaluate_data(
        {
            "document": "scope.md",
            "expected_issues": [
                expected_issue(
                    "C01", review_scope="BASIC_DESIGN_CORE"
                ),
                expected_issue(
                    "D01",
                    category="API詳細",
                    description="endpoint schemaが不足している",
                    keywords=["endpoint", "schema"],
                    review_scope="DETAIL_DESIGN",
                ),
            ],
        },
        {"issues": [ai_issue("ISSUE-001")]},
    )

    assert report.recall == 0.5
    assert report.basic_design_core_expected == 1
    assert report.basic_design_core_matched == 1
    assert report.basic_design_core_missed == 0
    assert report.basic_design_core_recall == 1.0


def test_confirmation_is_separate_from_core_metrics() -> None:
    report = evaluate_data(
        {
            "document": "scope.md",
            "expected_issues": [
                expected_issue(
                    "C01", review_scope="BASIC_DESIGN_CORE"
                ),
                expected_issue(
                    "Q01",
                    category="時刻基準",
                    description="基準タイムゾーンを確認する",
                    keywords=["タイムゾーン", "基準時刻"],
                    review_scope="BASIC_DESIGN_CONFIRMATION",
                ),
            ],
        },
        {"issues": [ai_issue("ISSUE-001")]},
    )

    assert len(report.missed) == 1
    assert report.missed[0].review_scope == "BASIC_DESIGN_CONFIRMATION"
    assert report.basic_design_core_expected == 1
    assert report.basic_design_core_recall == 1.0


def test_report_formats_basic_design_core_metrics() -> None:
    report = evaluate_data(
        {
            "document": "scope.md",
            "expected_issues": [
                expected_issue(
                    "C01", review_scope="BASIC_DESIGN_CORE"
                )
            ],
        },
        {"issues": [ai_issue("ISSUE-001")]},
    )

    output = format_report(report)
    assert "Basic Design Core Expected: 1" in output
    assert "Basic Design Core Matched: 1" in output
    assert "Basic Design Core Missed: 0" in output
    assert "Basic Design Core Recall: 1.00" in output


def test_expected_issue_scope_files_are_classified() -> None:
    problematic = json.loads(
        (EVALUATION_DIR / "expected_problematic.json").read_text(encoding="utf-8")
    )
    good = json.loads(
        (EVALUATION_DIR / "expected_good.json").read_text(encoding="utf-8")
    )

    assert {
        item["id"]: item["review_scope"]
        for item in problematic["expected_issues"]
    } == {f"P{index:02d}": "BASIC_DESIGN_CORE" for index in range(1, 12)}
    assert {
        item["id"]: item["review_scope"] for item in good["expected_issues"]
    } == {
        "G01": "BASIC_DESIGN_CORE",
        "G02": "BASIC_DESIGN_CORE",
        "G03": "DETAIL_DESIGN",
        "G04": "BASIC_DESIGN_CORE",
        "G05": "BASIC_DESIGN_CONFIRMATION",
    }


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("expected_problematic.json", 11),
        ("expected_good.json", 5),
        ("expected_reference.json", 0),
    ],
)
def test_expected_issue_file_counts(filename: str, expected_count: int) -> None:
    data = json.loads((EVALUATION_DIR / filename).read_text(encoding="utf-8"))

    assert len(data["expected_issues"]) == expected_count
