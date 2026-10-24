from types import SimpleNamespace
from unittest.mock import Mock

from app.config import Settings
from app.review_service import (
    DemoReviewService,
    OpenAIReviewService,
    create_review_service,
)
from app.schemas import AIReviewResult


def test_demo_mode_returns_fixed_review() -> None:
    settings = Settings(openai_api_key=None)
    service = create_review_service(settings)

    result = service.review("任意の設計書本文")

    assert isinstance(service, DemoReviewService)
    assert len(result.issues) == 3
    assert result.issues[0].id == "ISSUE-001"


def test_openai_service_uses_responses_structured_output() -> None:
    service = OpenAIReviewService(api_key="test-key", model="test-model")
    expected = AIReviewResult(summary="指摘はありません。", issues=[])
    parse_mock = Mock(return_value=SimpleNamespace(output_parsed=expected))
    service._client.responses.parse = parse_mock

    result = service.review("# 設計書")

    assert result == expected
    parse_mock.assert_called_once()
    call_options = parse_mock.call_args.kwargs
    assert call_options["model"] == "test-model"
    assert call_options["text_format"] is AIReviewResult
    assert call_options["store"] is False
    assert call_options["input"][0]["role"] == "system"
