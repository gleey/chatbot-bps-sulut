"""Tests untuk KeyRotator dan ModelRotator."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import support  # noqa: F401; isolate environment before application imports

from llm_engine import _KeyRotator, _ModelRotator


class TestKeyRotator(unittest.TestCase):

    def setUp(self):
        self.keys = ["key_aaaa", "key_bbbb", "key_cccc"]
        self.rotator = _KeyRotator(self.keys, cooldown=1)

    def test_initial_all_available(self):
        available = self.rotator.get_available_keys()
        self.assertEqual(len(available), 3)
        self.assertEqual([i for i, _ in available], [0, 1, 2])

    def test_mark_failed_removes_from_available(self):
        self.rotator.mark_failed(0)
        available = self.rotator.get_available_keys()
        self.assertEqual(len(available), 2)
        self.assertNotIn(0, [i for i, _ in available])

    def test_has_available_true(self):
        self.assertTrue(self.rotator.has_available())

    def test_has_available_false_when_all_failed(self):
        self.rotator.mark_failed(0)
        self.rotator.mark_failed(1)
        self.rotator.mark_failed(2)
        self.assertFalse(self.rotator.has_available())

    def test_cooldown_resets_failed_keys(self):
        self.rotator.mark_failed(0)
        time.sleep(1.1)  # lewat cooldown (1 detik)
        available = self.rotator.get_available_keys()
        self.assertEqual(len(available), 3)

    def test_empty_keys(self):
        rotator = _KeyRotator([], cooldown=1)
        self.assertEqual(rotator.get_available_keys(), [])
        self.assertFalse(rotator.has_available())

    def test_single_key_failure(self):
        rotator = _KeyRotator(["only_key"], cooldown=1)
        rotator.mark_failed(0)
        self.assertFalse(rotator.has_available())


class TestModelRotator(unittest.TestCase):

    def setUp(self):
        self.models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        self.rotator = _ModelRotator(self.models, cooldown=1)

    def test_initial_all_available(self):
        available = self.rotator.get_available_models()
        self.assertEqual(len(available), 3)

    def test_mark_failed_removes_from_available(self):
        self.rotator.mark_failed(0)
        available = self.rotator.get_available_models()
        self.assertEqual(len(available), 2)
        self.assertNotIn(0, [i for i, _ in available])

    def test_cooldown_resets(self):
        self.rotator.mark_failed(1)
        time.sleep(1.1)
        available = self.rotator.get_available_models()
        self.assertEqual(len(available), 3)

    def test_has_available_true(self):
        self.assertTrue(self.rotator.has_available())

    def test_all_models_failed(self):
        self.rotator.mark_failed(0)
        self.rotator.mark_failed(1)
        self.rotator.mark_failed(2)
        self.assertFalse(self.rotator.has_available())

    def test_empty_models(self):
        rotator = _ModelRotator([], cooldown=1)
        self.assertEqual(rotator.get_available_models(), [])
        self.assertFalse(rotator.has_available())


class TestRotatorIntegration(unittest.TestCase):
    """Test integrasi dengan mock client Gemini."""

    def setUp(self):
        # Reset modul agar rotator fresh
        import importlib
        import llm_engine
        importlib.reload(llm_engine)
        # Reset offline mode agar test state_machine tidak terpengaruh
        llm_engine.set_offline_mode(False)

    def test_429_rotates_to_next_key(self):
        """Key[0] kena 429, sistem coba key[1] dan berhasil."""
        from unittest.mock import patch, MagicMock
        from google.genai import errors as genai_errors

        import llm_engine
        llm_engine._key_rotator.failed.clear()
        llm_engine._model_rotator.failed.clear()

        error_429 = genai_errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
        success_response = MagicMock()
        success_response.text = '{"intent": "cari_data", "balasan": "ok"}'

        with patch("llm_engine.genai.Client") as MockClient:
            client_instance = MockClient.return_value
            call_count = {"n": 0}

            def side_effect(*args, **kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise error_429
                return success_response

            client_instance.models.generate_content.side_effect = side_effect

            history = [{"role": "user", "parts": [{"text": "halo"}]}]
            result = llm_engine.analisis_pesan(history)

            self.assertEqual(result["intent"], "cari_data")
            # Key[0] gagal → key[1] berhasil
            self.assertEqual(call_count["n"], 2)
            # Key[0] harus ditandai gagal, key[1] tidak
            self.assertIn(0, llm_engine._key_rotator.failed)
            self.assertNotIn(1, llm_engine._key_rotator.failed)

    def test_404_rotates_to_next_model(self):
        """Model[0] kena 404, sistem pindah ke model[1]."""
        from unittest.mock import patch, MagicMock
        from google.genai import errors as genai_errors

        import llm_engine
        llm_engine._key_rotator.failed.clear()
        llm_engine._model_rotator.failed.clear()

        error_404 = genai_errors.ClientError(404, {"error": {"message": "missing", "status": "NOT_FOUND"}})
        success_response = MagicMock()
        success_response.text = '{"intent": "cari_data", "balasan": "ok"}'

        with patch("llm_engine.genai.Client") as MockClient:
            client_instance = MockClient.return_value
            call_count = {"n": 0}

            def side_effect(*args, **kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise error_404
                return success_response

            client_instance.models.generate_content.side_effect = side_effect

            history = [{"role": "user", "parts": [{"text": "halo"}]}]
            result = llm_engine.analisis_pesan(history)

            self.assertEqual(result["intent"], "cari_data")
            # Model[0] gagal → pindah model[1] → key[0] (reset) → berhasil
            self.assertEqual(call_count["n"], 2)
            # Model[0] harus ditandai gagal
            self.assertIn(0, llm_engine._model_rotator.failed)

    def test_all_fail_falls_to_offline(self):
        """Semua key × model gagal → fallback offline."""
        from unittest.mock import patch, MagicMock
        from google.genai import errors as genai_errors

        import llm_engine
        llm_engine._key_rotator.failed.clear()
        llm_engine._model_rotator.failed.clear()

        error_429 = genai_errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})

        with patch("llm_engine.genai.Client") as MockClient:
            client_instance = MockClient.return_value
            client_instance.models.generate_content.side_effect = error_429

            history = [{"role": "user", "parts": [{"text": "data inflasi"}]}]
            result = llm_engine.analisis_pesan(history)

            # Fallback offline harus aktif
            self.assertTrue(llm_engine.is_offline_mode())
            # Intent harus "cari_data" karena kata "data" dan "inflasi"
            self.assertEqual(result["intent"], "cari_data")


if __name__ == "__main__":
    unittest.main()
