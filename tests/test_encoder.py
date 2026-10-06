"""Tests for the encoder module.

Tests cover Encoding dataclass, prompt construction, code extraction,
and file saving logic with mocked Claude API calls.
"""

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from anthropic import Anthropic
from click.testing import CliRunner

from axiom_corpus.cli import main
from axiom_corpus.encoder import (
    SYSTEM_PROMPT,
    Encoding,
    _extract_code_block,
    encode_and_save,
    encode_section,
)
from axiom_corpus.models import Citation, Section, Subsection

# =============================================================================
# Helpers
# =============================================================================


def _make_section():
    return Section(
        citation=Citation(title=26, section="32"),
        title_name="Internal Revenue Code",
        section_title="Earned income tax credit",
        text="A tax credit is allowed...",
        subsections=[
            Subsection(identifier="a", text="Allowance of credit"),
            Subsection(identifier="b", text="Percentages and amounts"),
        ],
        source_url="https://uscode.house.gov/view.xhtml?req=26+USC+32",
        retrieved_at=date(2024, 1, 1),
    )


# =============================================================================
# Tests
# =============================================================================


class TestEncoding:
    def test_create(self):
        enc = Encoding(
            citation="26 USC 32",
            dsl="variable eitc { ... }",
            test_cases=[{"name": "test1"}],
            encoded_by="claude-opus",
            encoded_at=datetime(2024, 1, 1),
            model="claude-opus-4-20250514",
            prompt_tokens=1000,
            completion_tokens=2000,
        )
        assert enc.citation == "26 USC 32"
        assert enc.prompt_tokens == 1000


class TestExtractCodeBlock:
    def test_extract_rulespec(self):
        text = """Here is the code:

```rulespec
variable eitc {
  entity TaxUnit
}
```

And some more text.
"""
        result = _extract_code_block(text, "rulespec")
        assert "variable eitc" in result
        assert "entity TaxUnit" in result

    def test_extract_yaml(self):
        text = """Test cases:

```yaml
- name: test1
  input:
    earned_income: 10000
```
"""
        result = _extract_code_block(text, "yaml")
        assert "name: test1" in result

    def test_no_match(self):
        text = "No code blocks here"
        result = _extract_code_block(text, "rulespec")
        assert result == ""


class TestEncodeSection:
    @patch("axiom_corpus.encoder.Anthropic")
    def test_encode_section(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(
                type="text",
                text="""Here is the encoding:

```rulespec
variable earned_income_credit {
  entity TaxUnit
  period Year
  dtype Money
}
```

```yaml
- name: basic_test
  input:
    earned_income: 10000
  expected:
    eitc: 500
```
""",
            )
        ]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 800
        mock_client.messages.create.return_value = mock_response

        section = _make_section()
        result = encode_section(section)

        assert isinstance(result, Encoding)
        assert "earned_income_credit" in result.dsl
        assert len(result.test_cases) > 0
        assert result.prompt_tokens == 500
        assert result.completion_tokens == 800

    @patch("axiom_corpus.encoder.Anthropic")
    def test_encode_section_no_tests(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [
            MagicMock(type="text", text="```rulespec\nvariable eitc {}\n```\n\nNo tests.")
        ]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        section = _make_section()
        result = encode_section(section)
        assert result.dsl == "variable eitc {}"
        assert result.test_cases == []


class TestEncodeAndSave:
    @patch("axiom_corpus.encoder.encode_section")
    def test_encode_and_save(self, mock_encode, tmp_path):
        mock_encode.return_value = Encoding(
            citation="26 USC 32",
            dsl="variable eitc { ... }",
            test_cases=[{"name": "test1", "input": {"ei": 10000}}],
            encoded_by="claude-opus",
            encoded_at=datetime(2024, 1, 1),
            model="claude-opus-4-20250514",
            prompt_tokens=500,
            completion_tokens=800,
        )

        section = _make_section()
        result = encode_and_save(section, tmp_path)

        mock_encode.assert_called_once_with(section, "claude-sonnet-5-5")
        assert result.citation == "26 USC 32"

        # Check files were created
        section_dir = tmp_path / "federal" / "statute" / "26" / "32"
        assert (section_dir / "statute.md").exists()
        assert (section_dir / "rules.yaml").exists()
        assert (section_dir / "tests.yaml").exists()
        assert (section_dir / "metadata.json").exists()

        # Check content
        statute = (section_dir / "statute.md").read_text()
        assert "26 USC" in statute

        metadata = json.loads((section_dir / "metadata.json").read_text())
        assert metadata["citation"] == "26 USC 32"
        assert metadata["prompt_tokens"] == 500

    @patch("axiom_corpus.encoder.encode_section")
    def test_encode_and_save_no_tests(self, mock_encode, tmp_path):
        mock_encode.return_value = Encoding(
            citation="26 USC 32",
            dsl="variable eitc {}",
            test_cases=[],
            encoded_by="claude-opus",
            encoded_at=datetime(2024, 1, 1),
            model="claude-opus-4-20250514",
            prompt_tokens=100,
            completion_tokens=50,
        )

        section = _make_section()
        encode_and_save(section, tmp_path)

        section_dir = tmp_path / "federal" / "statute" / "26" / "32"
        assert not (section_dir / "tests.yaml").exists()


class TestSystemPrompt:
    def test_prompt_exists(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_prompt_mentions_rulespec(self):
        assert "RuleSpec" in SYSTEM_PROMPT or "rulespec" in SYSTEM_PROMPT.lower()


@pytest.mark.parametrize(
    ("model", "expected_extra_body", "max_tokens"),
    [
        (None, {"output_config": {"effort": "low"}, "thinking": {"type": "adaptive"}}, 16000),
        ("claude-opus-5-5", {"output_config": {"effort": "low"}}, 16000),
        ("claude-haiku-4-5", {}, 8000),
        ("custom-model-id", {}, 8000),
    ],
)
def test_sonnet_request_and_thinking_response(model, expected_extra_body, max_tokens):
    """Exercise SDK serialization and response parsing without a network request."""
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": model or "claude-sonnet-5-5",
                "content": [
                    {"type": "thinking", "thinking": "", "signature": "test-signature"},
                    {"type": "text", "text": "```rulespec\nvariable eitc {}\n```"},
                    {"type": "text", "text": "```yaml\n- name: basic_test\n```"},
                ],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 100, "output_tokens": 200},
            },
        )

    with (
        Anthropic(
            api_key="test-key",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        ) as client,
        patch("axiom_corpus.encoder.Anthropic", return_value=client),
    ):
        result = (
            encode_section(_make_section())
            if model is None
            else encode_section(_make_section(), model=model)
        )

    assert len(requests) == 1
    request = requests[0]
    assert request["model"] == result.model == (model or "claude-sonnet-5-5")
    assert request["max_tokens"] == max_tokens
    assert {
        name: request[name] for name in ("output_config", "thinking") if name in request
    } == expected_extra_body
    assert not {"temperature", "top_p", "top_k", "tool_choice"} & request.keys()
    assert [message["role"] for message in request["messages"]] == ["user"]
    assert result.dsl == "variable eitc {}"
    assert result.test_cases == [{"name": "basic_test"}]
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200


@patch("axiom_corpus.encoder.Anthropic")
def test_refusal_does_not_read_content_or_save(mock_anthropic_cls, tmp_path):
    response = MagicMock(stop_reason="refusal")
    # A refusal must fail before attempting to iterate response content.
    response.content.__iter__.side_effect = AssertionError("Read refusal content")
    mock_anthropic_cls.return_value.messages.create.return_value = response

    with pytest.raises(ValueError, match="refused to encode"):
        encode_and_save(_make_section(), tmp_path)

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "content",
    [[], [MagicMock(type="thinking")], [MagicMock(type="text", text="  \n")]],
)
@patch("axiom_corpus.encoder.Anthropic")
def test_empty_text_fails_without_saving(mock_anthropic_cls, content, tmp_path):
    mock_anthropic_cls.return_value.messages.create.return_value = MagicMock(
        stop_reason="end_turn", content=content
    )

    with pytest.raises(ValueError, match="returned no text"):
        encode_and_save(_make_section(), tmp_path)

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("model", [None, "custom-model-id"])
@patch("axiom_corpus.cli.AxiomArchive")
@patch("axiom_corpus.encoder.encode_and_save")
def test_cli_encoding_model(mock_encode, mock_archive, model, tmp_path):
    section = _make_section()
    mock_archive.return_value.storage.get_section.return_value = section
    args = ["encode", "26 USC 32", "--output", str(tmp_path)]
    if model:
        args.extend(["--model", model])

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0, result.output
    mock_encode.assert_called_once_with(section, tmp_path, model=model or "claude-sonnet-5-5")
