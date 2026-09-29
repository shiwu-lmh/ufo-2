import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from ufo.llm.qwen import QwenService


class QwenRequestParametersTests(unittest.TestCase):
    def test_qwen_request_bounds_output_and_disables_thinking(self):
        service = object.__new__(QwenService)
        service.config_llm = {
            "API_TYPE": "qwen",
            "REASONING_MODEL": False,
            "ENABLE_THINKING": False,
        }
        service.config = {
            "TEMPERATURE": 0.0,
            "TOP_P": 1.0,
            "MAX_TOKENS": 1200,
        }
        service.model = "qwen3.8-flash"
        service.api_type = "qwen"
        service.prices = {}
        service.use_responses = False
        service.json_schema_enabled = False
        service.client = MagicMock()
        service.client.chat.completions.create.return_value = iter(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content='{"status":"FINISH"}')
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[],
                    usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2),
                ),
            ]
        )

        service.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            n=1,
            max_tokens=1200,
            top_p=1.0,
        )

        request = service.client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["max_tokens"], 1200)
        self.assertEqual(request["extra_body"], {"enable_thinking": False})


if __name__ == "__main__":
    unittest.main()
