"""Check name persistence without touching the user's actual memory file."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from name_memory import NameMemory
import voice_agent


class NameMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / ".memory" / "user.json"
        self.memory = NameMemory(self.path)

    def test_name_survives_a_new_memory_instance(self) -> None:
        self.memory.save_name("  Zoë   Dlamini  ")
        self.assertEqual(NameMemory(self.path).load_name(), "Zoë Dlamini")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"name": "Zoë Dlamini"})
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_a_correction_replaces_the_saved_name(self) -> None:
        self.memory.save_name("Zoe")
        self.memory.save_name("Zoë")
        self.assertEqual(NameMemory(self.path).load_name(), "Zoë")

    def test_invalid_name_does_not_replace_existing_memory(self) -> None:
        self.memory.save_name("Zoë")
        for invalid_name in (" \n ", "a" * 201):
            with self.subTest(name=invalid_name):
                with self.assertRaises(ValueError):
                    self.memory.save_name(invalid_name)
                self.assertEqual(self.memory.load_name(), "Zoë")

    def test_forgetting_removes_the_name_across_restarts(self) -> None:
        self.memory.save_name("Zoë")
        self.memory.forget_name()
        self.assertIsNone(NameMemory(self.path).load_name())
        self.assertFalse(self.path.exists())
        self.memory.forget_name()

    def test_missing_or_malformed_memory_does_not_invent_a_name(self) -> None:
        self.assertIsNone(self.memory.load_name())
        self.path.parent.mkdir(parents=True)
        for invalid_data in ("{broken", "[]", '{"name": 12}', '{"name": "  "}'):
            with self.subTest(data=invalid_data):
                self.path.write_text(invalid_data, encoding="utf-8")
                self.assertIsNone(self.memory.load_name())

    def test_voice_tools_and_startup_prompt_use_the_same_memory(self) -> None:
        with patch.object(voice_agent, "NAME_MEMORY", self.memory):
            self.assertIn("Saved", voice_agent.remember_name("Zoë Dlamini"))
            self.assertIn('Saved preferred name: "Zoë Dlamini"', voice_agent.build_system_prompt())
            voice_agent.forget_name()
            self.assertIn("Saved preferred name: null", voice_agent.build_system_prompt())


if __name__ == "__main__":
    unittest.main()
