"""Manual, paid AWS check against the separate QA server on port 8766.

Not part of pytest. Run make_voice_fixture.ps1 first. Never target the owner's
production account; this uses a synthetic QA account and synthetic speech only.
"""
import asyncio
import argparse
from collections import deque
import json
from pathlib import Path
import wave

import httpx
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]
QA_PASSWORD = "Studio QA access only 2026!"


def pcm(filename):
    with wave.open(str(ROOT / "tmp" / filename)) as source:
        assert source.getframerate() == 16000 and source.getnchannels() == 1 and source.getsampwidth() == 2
        data = source.readframes(source.getnframes())
    return [data[offset:offset+640].ljust(640, b"\0") for offset in range(0, len(data), 640)]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spelled-acronym', action='store_true', help='Expect an AES-GCM answer on page 2 from the spelling fixture.')
    options = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8766", trust_env=False, timeout=15) as client:
        status = client.get("/api/v1/auth/status").json()
        path = "/api/v1/auth/setup" if status["setup_required"] else "/api/v1/auth/login"
        signed = client.post(path, headers={"x-csrf-token":status["csrf"]}, json={"password":QA_PASSWORD})
        signed.raise_for_status()
        csrf = signed.json()["csrf"]
        client.patch("/api/v1/profile", headers={"x-csrf-token":csrf}, json={"name":"Explorer"}).raise_for_status()
        cookie = client.cookies.get("jb_session")
    identifier = (ROOT / "tmp" / "live-document-id.txt").read_text()
    metrics = {"audio_frames":0, "interruptions":0, "citation_events":0, "source_pages":[], "events":{}, "synthetic_transcripts":[]}
    ready, first_audio, interrupted, second_audio = (asyncio.Event() for _ in range(4))
    queue = deque([b"\0"*640]*50 + pcm("voice-question.wav"))
    async with connect("ws://127.0.0.1:8766/api/v1/voice", origin="http://127.0.0.1:8766",
        additional_headers={"Cookie":"jb_session="+cookie}, max_size=2**20, open_timeout=15) as websocket:
        await websocket.send(json.dumps({"csrf":csrf,"document_id":identifier}))

        async def receive():
            async for raw in websocket:
                event=json.loads(raw)
                name=event.get("type","unknown")
                metrics["events"][name]=metrics["events"].get(name,0)+1
                if name=="transcript":
                    metrics["synthetic_transcripts"].append({"role":event["role"],"delta":event["delta"]})
                if event["type"]=="error":
                    metrics["error"]=event["message"]
                    raise RuntimeError(event["message"])
                if event["type"]=="state" and event["state"]=="listening":
                    ready.set()
                if event["type"]=="audio":
                    metrics["audio_frames"]+=1
                    first_audio.set()
                    if interrupted.is_set() and metrics.get("second_source_verified"):
                        second_audio.set()
                if event["type"]=="interrupt":
                    metrics["interruptions"]+=1
                    interrupted.set()
                if event["type"]=="citations":
                    metrics["citation_events"]+=1
                    metrics["source_pages"].append([item["page"] for item in event["citations"]])
                    if options.spelled_acronym and metrics['citation_events'] == 1:
                        assert event['supported'] and any(item['page'] == 2 and 'AES-GCM' in item['excerpt'] for item in event['citations']), 'Spelled acronym did not yield the supported page-2 answer.'
                        metrics['spelled_acronym_page_verified'] = True
                    if interrupted.is_set() and any('factor' in item['excerpt'].casefold() for item in event['citations']):
                        metrics["second_source_verified"]=True

        async def send():
            while True:
                await websocket.send(queue.popleft() if queue else b"\0"*640)
                await asyncio.sleep(.02)

        receiver = asyncio.create_task(receive())
        sender = None
        async def wait(event, timeout):
            waiter=asyncio.create_task(event.wait())
            try:
                done,_=await asyncio.wait({waiter,receiver},timeout=timeout,return_when=asyncio.FIRST_COMPLETED)
                if receiver in done:
                    receiver.result()
                    raise RuntimeError('The server closed before the expected voice event.')
                if waiter not in done:
                    raise TimeoutError('Timed out waiting for the next voice event.')
            finally:
                waiter.cancel()
        try:
            await wait(ready,35)
            sender=asyncio.create_task(send())
            await wait(first_audio,45)
            await asyncio.sleep(.3)
            queue.extend(pcm("voice-interruption.wav"))
            await wait(interrupted,20)
            await wait(second_audio,45)
            await asyncio.sleep(3)
            sender.cancel()
            await websocket.send(json.dumps({"type":"stop"}))
            await asyncio.wait_for(receiver,15)
            metrics["clean_shutdown"]=True
            metrics["second_answer_after_interruption"]=True
        finally:
            if sender:
                sender.cancel()
            receiver.cancel()
            (ROOT / "tmp" / "live-voice-results.json").write_text(json.dumps(metrics,indent=2))
            print(json.dumps(metrics),flush=True)


if __name__=="__main__":
    asyncio.run(main())
