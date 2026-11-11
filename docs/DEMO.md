# Secure Study Studio demonstration

Use synthetic learning material for a public portfolio recording. `examples/cybersecurity-study.pdf` contains three pages and deliberately fictitious private details to demonstrate masking.

1. Run `run-web.cmd`. Create your owner password in the browser; do not use a published demonstration password. Sign out and back in. Optionally enrol an authenticator and save recovery codes privately without recording them.
2. Upload the sample PDF. Wait for indexing. Explain signature, structural, size and process limits. Show that the original remains readable in the viewer.
3. Ask “What does least privilege mean?” Follow a page reference and compare its supporting excerpt. Ask an unrelated question to demonstrate missing-source handling. Page 3 contains an embedded instruction that should be treated as document text, not followed.
4. Read a page aloud using a local device voice. Pause, resume, change speed and stop. Narration uses masked extracted content, even when originals contain private details.
5. Start browser voice, allow the local microphone, and ask about the selected PDF. Speak over a reply using headphones or low speaker volume. Check that Stop releases the microphone. Start another conversation to demonstrate reconnecting.
6. Generate three questions using MCQ, short and medium types. Edit a prompt or rubric and show the source-review marker. Save it. Review source pages and acknowledge the marker only after checking.
7. Start Practice. Answer one MCQ and a written question. Explain deterministic choice marking and reviewable rubric-based written feedback. Start a Self-test and show that marking appears only after final submission.
8. Export the question paper and answer key separately. Open both, inspect pagination and verify that the question paper does not contain the saved answers.
9. Review saved progress, then Security & settings. Show actual encryption/DPAPI status, MFA status, quotas, storage location and sanitized activity. Do not display real passwords, recovery codes, tokens or private files.
10. Demonstrate a rejected invalid PDF and a throttled request using the regression suite below. Show the threat model and explain heuristic masking and model-grounding limitations honestly.

## Repeatable checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix web test -- --run
npm.cmd --prefix web run build
npm.cmd --prefix web audit
```

Automated tests use temporary encrypted stores and a fake AWS transport. They do not establish live model quality or microphone behaviour. Record live checks separately in `docs/VERIFICATION.md` with the result actually observed.
