from app.prompts import SYSTEM_PROMPT


def test_system_prompt_scopes_review_to_basic_design() -> None:
    assert "本レビューの対象は「基本設計書」です" in SYSTEM_PROMPT
    assert "詳細設計、インターフェース設計、運用設計" in SYSTEM_PROMPT
    assert "欠落しているという理由だけでHighのIssueにしない" in SYSTEM_PROMPT
    assert "業務状態と状態遷移" in SYSTEM_PROMPT
    assert "予約・期間・数量などの核心的な業務判定" in SYSTEM_PROMPT
    assert "性能要件の客観的で検証可能な受入基準" in SYSTEM_PROMPT
    assert "テストや合否判定ができない核心要件" in SYSTEM_PROMPT
    assert "endpointのフィールド単位schema" in SYSTEM_PROMPT
    assert "内部データ同期の実装詳細" in SYSTEM_PROMPT


def test_system_prompt_calibrates_confirmation_and_severity() -> None:
    assert "finding_type の Confirmation" in SYSTEM_PROMPT
    assert "severityは原則Low" in SYSTEM_PROMPT
    assert "High: 基本設計に重大な矛盾" in SYSTEM_PROMPT
    assert "Medium: 実装方針" in SYSTEM_PROMPT
    assert "Low: 改善提案" in SYSTEM_PROMPT
