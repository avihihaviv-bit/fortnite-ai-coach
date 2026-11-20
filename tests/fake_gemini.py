"""A fake google-genai client for tests. ALL responses here are TEST DATA, never shown to users."""

from __future__ import annotations

import json
from types import SimpleNamespace


class FakeAPIError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def segment_json(start="00:05", skill="editing", good=True, mistake=True, score=70) -> str:
    """TEST DATA segment result."""
    data = {
        "segment_summary": "TEST DATA summary",
        "mistakes": [{
            "code": "EDIT_EXPOSED_AFTER", "skill": skill, "severity": "high", "start": start, "end": start,
            "what_happened": "TEST DATA: stayed in the open edit", "better_option": "TEST DATA: reset the edit",
            "why": "TEST DATA: took free damage", "how_to_practice": "TEST DATA: edit course, reset every edit",
            "evidence": "TEST DATA: health bar drops after the edit", "confidence": 0.8}] if mistake else [],
        "good_plays": [{
            "code": "EDIT_HARD_FAST", "skill": "editing", "difficulty": "hard", "start": start, "end": start,
            "what_happened": "TEST DATA: fast triple edit into a shot", "evidence": "TEST DATA: hit marker visible",
            "confidence": 1.0}] if good else [],
        "skill_assessments": [{"skill": skill, "score": score, "evidence_count": 2, "confidence": 0.7,
                               "rationale": "TEST DATA"}],
        "not_determinable": ["TEST DATA: sensitivity"],
    }
    return json.dumps(data)


class FakeClient:
    def __init__(self, models=("gemini-2.5-flash", "gemini-2.5-flash-lite"), responses=None, list_error=None,
                 blocked_models=()):
        self.blocked_models = set(blocked_models)  # listed, but refused for this key (like retired models)
        self.pings = []
        self.uploads = 0
        self.generate_calls = []
        self._responses = list(responses or [])
        self._models = models
        self._list_error = list_error
        self._file = SimpleNamespace(name="files/test-1", uri="https://example.invalid/files/test-1",
                                     mime_type="video/mp4", state=SimpleNamespace(name="ACTIVE"))
        self.files = SimpleNamespace(upload=self._upload, get=lambda name: self._file)
        self.models = SimpleNamespace(list=self._list, generate_content=self._generate)

    def _list(self):
        if self._list_error:
            raise self._list_error
        return [SimpleNamespace(name=f"models/{m}", supported_actions=["generateContent"]) for m in self._models]

    def _upload(self, file, config=None):
        self.uploads += 1
        return SimpleNamespace(name=self._file.name, uri=self._file.uri, mime_type="video/mp4",
                               state=SimpleNamespace(name="PROCESSING"))

    def _generate(self, model, contents, config):
        if model in self.blocked_models:
            raise FakeAPIError(404, f"models/{model} is no longer available to new users. TEST DATA")
        if isinstance(contents, str) and "single word OK" in contents:  # connection-test ping
            self.pings.append(model)
            return SimpleNamespace(text="OK", usage_metadata=None)
        self.generate_calls.append((model, contents, config))
        r = self._responses.pop(0) if self._responses else segment_json()
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(text=r, usage_metadata=SimpleNamespace(prompt_token_count=1000, candidates_token_count=200))
