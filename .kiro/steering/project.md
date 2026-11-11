---
inclusion: always
---

# Jozi Buddy

- Local Python voice AI agent using Strands Bidi Agents and Amazon Nova Sonic.
- Use Python 3.12 and GA `strands.bidi` imports.
- Model: `amazon.nova-2-5-sonic` in `us-east-1`; default voice: `matthew`.
- One shared `AudioIO(audio_processor=True)` connects the laptop microphone and speakers with echo cancellation.
- Jozi Buddy is a warm, curious, playful Johannesburg-flavoured teammate for learning, building, and walk-and-talk conversations. Use relatable examples, optional quizzes or riddles, tiny build steps, and natural encouragement. Ask one question at a time; keep most spoken replies to one or two short sentences.
- Guide building through conversation and wait for the user's results. Keep walks voice-friendly and base observations on what the user describes. Claim actions or capabilities only when supported by available tools. Only the preferred name persists between runs.
- Run `voice_agent.py` with the project's `.venv` interpreter; Ctrl+C ends the conversation.
- Authenticate through the default AWS profile using AWS CLI v2 browser sign-in (`aws login`). Keep credentials outside the project.
- Remember the user's preferred name between runs in `.memory/user.json` through the `remember_name` tool. The `forget_name` tool removes it on request. Keep `.memory/` out of version control.
- Privacy: allow preferred-name recall, but refuse private contact details, home addresses, IDs, financial/medical information, passwords, codes, and credentials. The name tool validates input and loaded memory. Spoken refusals use system instructions; voice identity is unverified.
- Current scope extends the completed terminal workshop into Secure Study Studio: React/TypeScript/Vite/Tailwind with FastAPI under `/api/v1`. Preserve `run.cmd`; use `run-web.cmd` for the studio.
- Bind the app to loopback. Store web data under Windows LOCALAPPDATA, outside OneDrive, encrypted with AES-GCM and a DPAPI-protected key. Keep owner sessions, CSRF, upload validation and privacy controls enforced on the backend.
- Use Titan Text Embeddings V2 and the US Nova 2 Lite profile for redacted, document-scoped study tasks; Nova 2.5 Sonic for browser voice. Treat PDF content as untrusted data and validate model results and citations.
- Keep existing 14 memory/privacy tests passing. Security evidence and demonstration instructions live in `docs/`. Never claim a live AWS/browser check that was not observed.
- The user authorized publishing a public portfolio repository with installation documentation and synthetic screenshots. Keep credentials, the local library, name memory and test artifacts excluded. Public app hosting remains future work; do not expose this local owner app remotely.
