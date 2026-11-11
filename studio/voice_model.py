"""Nova's documented forced tool choice, missing from the current Strands adapter."""
import json
import asyncio
from strands.bidi.models import BedrockNovaSonicModel
from strands.bidi.types.media import AudioDelta


class ReadyVoiceModel(BedrockNovaSonicModel):
    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        # Begin the input stream with silence so the service can finish its
        # bidirectional handshake while the browser waits for readiness.
        await self.send(AudioDelta(format="pcm", source={"bytes": b"\0" * 640}))
        # The SDK initially returns a stream handle before its HTTP connection
        # has succeeded. Do not advertise readiness before that handshake.
        await asyncio.wait_for(self._stream.await_output(), timeout=15)


def transient_voice_error(error):
    while True:
        code = str(getattr(error, "name", ""))
        if isinstance(error, (TimeoutError, ConnectionError)) or any(part in code for part in ("DNS_", "TIMEOUT", "CONNECTION_CLOSED", "SOCKET_CLOSED")):
            return True
        if error.__cause__ is None:
            return False
        error = error.__cause__


class DocumentVoiceModel(ReadyVoiceModel):
    def _get_prompt_start_event(self, tools):
        # Keep the SDK's protocol serializer; add only the documented Nova field.
        # This small adapter has a regression test and needs review on SDK upgrades.
        if not any(tool["name"] == "answer_from_pdf" for tool in tools):
            raise ValueError("PDF voice requires its document-scoped answer tool.")
        packet = json.loads(super()._get_prompt_start_event(tools))
        packet["event"]["promptStart"]["toolConfiguration"]["toolChoice"] = {"tool": {"name": "answer_from_pdf"}}
        return json.dumps(packet)


class GroundingGate:
    def __init__(self, enabled):
        self.enabled, self.ready, self.turn, self.content_id = enabled, False, 0, None

    @property
    def allows_speech(self):
        return not self.enabled or self.ready

    def interrupt(self):
        self.turn += 1
        self.ready, self.content_id = False, None

    def user(self, content_id):
        if content_id != self.content_id:
            self.turn += 1
            self.ready, self.content_id = False, content_id

    def resolve(self, turn):
        if turn != self.turn:
            return False
        self.ready = True
        return True
