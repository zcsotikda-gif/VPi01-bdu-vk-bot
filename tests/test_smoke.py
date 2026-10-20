import unittest

from vk_bot.config import Settings
from vk_bot.llm_client import LLMClient


class TestSmoke(unittest.TestCase):
    def test_settings_attributes(self):
        s = Settings()
        self.assertIsInstance(s.ai_provider, str)
        self.assertIsInstance(s.base_url, str)
        self.assertIsInstance(s.model_id, str)
        self.assertIsNotNone(s.timestamp)

    def test_llm_client_init(self):
        s = Settings()
        client = LLMClient(s)
        self.assertIs(client.settings, s)

if __name__ == "__main__":
    unittest.main()
