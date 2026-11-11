# Verification record

Updated 11 November 2026 (Africa/Johannesburg). This is an implementation record, not a penetration-test certificate. The implementation, bounded live AWS checks, and browser study workflow are verified below. Remaining owner/browser acceptance is listed explicitly.

## Automated results

| Check | Observed result |
| --- | --- |
| Python regression suite | **73 passed**, plus **28 subtests passed**; includes the original 14 memory/privacy tests. One deprecation warning comes from the harmless JavaScript rejection fixture in pypdf 6 |
| Browser logic tests | **14 passed** across four Vitest files; microphone cleanup, backend-readiness gating, 16/44.1/48 kHz resampling, visible source excerpts, escaped markup, and the heard-question correction control are covered |
| TypeScript and production build | Passed using Vite 7.3.8; a production artifact check ensures the microphone worklet is a local JS file, not a CSP-blocked data URL |
| Python dependency consistency | `pip check`: no broken requirements |
| npm vulnerability audit | Successful refreshed scan on 11 November: **zero reported vulnerabilities**. An earlier attempt failed DNS; the later successful scan supersedes it |
| Actual Windows DPAPI | Wrapped-key creation and reopening passed on Windows, in addition to AES-GCM persistence and tamper-detection tests |

The Python suite exercises owner setup, password login, MFA gating, single-use recovery including concurrent reuse, session expiry/logout, revocation of other sessions on MFA changes, anonymous access, CSRF, host/origin checks and WebSocket rejection. It checks that validation errors do not echo password values.

Upload cases cover traversal filenames, incorrect media types, bad signatures, malformed files, oversize files, encrypted PDFs, JavaScript, embedded attachments, all-scanned files and page limits. The real isolated parser subprocess runs in these tests. Rejected uploads leave no document record. Interrupted indexes can be retried after restart; late results cannot recreate records after document deletion.

Study cases verify masked embedding/model payloads and narration, document scoping, citation checks and missing-evidence handling, editable question source-review flags, hidden answer keys, immediate practice feedback, deferred self-test feedback, partial-credit score limits, saved attempts, idempotent final submission, cascaded deletion, quotas and sanitized audit data. Nova's tool schema is expanded and checked with a JSON Schema validator, while full Pydantic validation remains local.

**Test AWS transport is synthetic.** These tests establish application contracts and enforcement, not live model quality or resistance to every prompt injection. Browser voice logic tests use mocked microphone/socket/audio objects for permission denial, queued playback interruption, muting, stop cleanup, delayed permission resolution and reconnecting.

## Manual inspection already observed

- In-app Chromium browser: owner login, dashboard and PDF upload; original PDF rendering and page navigation; local device voice enumeration and page narration; pause, resume, stop and speed selection. No console errors were observed during that check.
- Desktop layout inspected at 1440 × 1000. The final 390 × 844 practice and PDF views were inspected without page-level horizontal overflow. Following a page-2 reference switched from Ask Jozi to Read PDF. A ResizeObserver now refits the canvas when its panel becomes visible or changes width; resize events are debounced to avoid reparsing on every intermediate size.
- On 11 November, the in-app Chromium browser completed real-AWS generation of three question types, editing and saving a prompt, source-review flagging, deterministic MCQ marking, written marking, saved-progress resume, and final practice review (7/9). An intentionally incomplete AES-GCM answer received 3/5 with an explanation and page-2 reference.
- Self-test saved all three answers without exposing feedback, then showed marks only after final submission (8/9). The deliberately wrong MCQ received 0/1; the correct medium answer received 5/5.
- Both export links downloaded separate PDFs. Their one-page question paper and answer key were rendered and inspected; neither showed clipping, and the paper excluded saved answers.
- Security settings showed actual DPAPI/encryption status and unchanged default allowances. A harmless malformed PDF sent to the isolated QA API returned 400 without adding a document. Five bad QA logins returned 401 and the sixth returned 429; sanitized blocked events were recorded.
- A later in-app-browser file-chooser upload failed before reaching the API with `ERR_BLOB_REFERENCED_FILE_UNAVAILABLE`. This browser-tool limitation does not establish an application upload failure; the earlier browser upload and isolated real-parser/API checks are recorded separately.
- Separate standard question-paper and answer-key PDFs were rendered and inspected. A 20-question stress fixture produced an 11-page paper and a 17-page answer key. Interior pages were rendered and inspected for long-question wrapping, margins, page numbers, fonts and clipping; no clipping was observed on those inspected pages. Temporary render artifacts are under `tmp/pdfs`, excluded from version control.
- The local production server starts on `127.0.0.1:8765` with the Windows local application-data store.

## Live AWS and protocol checks

These checks used a separate encrypted QA store and synthetic content, with real AWS calls:

- CLI and Boto3 STS authentication succeeded after selecting the existing project with the confirmed Stockholm login region.
- Titan V2 indexed the three-page sample. Nova 2 Lite answered least privilege with a validated page-1 excerpt, abstained on photosynthesis, and refused an embedded instruction to reveal credentials.
- Live quiz generation returned MCQ, short and medium questions. The final strict contract requires explanations and flags AI drafts for source review. Written marking returned partial credit (2/3 and 2/5) with explanations; MCQ marking returned the deterministic full mark for the correct choice.
- Live-generated question and answer PDFs were rendered and visually inspected. They were separate and readable, with source pages and no clipping on the inspected pages.
- Latest authenticated Nova 2.5 Sonic WebSocket test: **83 audio frames, two cited answers, one interruption, a new supported answer after interruption, and clean Stop closure**, after successfully retrying a transient startup connection failure. Both answers referenced page 1. Input was local synthetic speech, not a recording of the owner's microphone.
- A separate live reconnect succeeded. Logging out revoked the session and closed its active voice WebSocket cleanly. A regression test also covers SDK cancellation during early Stop.
- Startup was separately checked without user speech: priming the upstream audio stream with silence completed readiness in 15.3 seconds, followed by clean early Stop. Wrapped startup timeouts are eligible for bounded retries; configuration errors are not.
- On 11 November, CLI and Python SDK authentication were refreshed and verified again. A new synthetic speech test saying “A E S dash G C M” produced the supported AES-GCM answer with page 2, followed by an interrupted reply and a new MFA answer with page 1: **154 audio frames, two citation events, one interruption, and clean Stop**. The owner then confirmed that the letters were heard correctly through their own microphone.

The spelling change uses Nova's documented LOW endpointing sensitivity, bounded redacted PDF acronym hints, and conservative explicit-letter checking. An unknown spelling such as “A U B S dash G C M” requests a correction without making a study-model call. Captions preserve “What Jozi heard”; Correct in text stops voice and opens an editable PDF question. These checks cannot detect every recognition error, and prompting does not retrain an accent model. See [AWS turn-taking controls](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-turn-taking.html).

PDF voice now uses a forced document tool and a per-turn speech gate. Late results from an interrupted turn cannot reopen the gate for the new turn. This constrains delivery; semantic correctness and privacy detection still need human review.

## Remaining owner/browser acceptance

| Item | Current state |
| --- | --- |
| AWS credentials | **Verified** with CLI and Boto3 STS. Project/login home region is **eu-north-1** |
| Model regions | Study runtime and Sonic explicitly use **us-east-1**, independently of the login region |
| Live Titan indexing | **Passed** against real AWS |
| Live Nova 2 Lite answers, abstention, injection handling, quiz generation and written marking | **Passed the bounded synthetic-content checks above**; this is not a guarantee for all documents |
| Browser Sonic microphone and speaker playback | Owner confirmed hearing Jozi and a PDF answer. After reporting misheard letters, the owner confirmed the updated acronym recognition works. Final owner confirmation of the live-caption page button, interruption and Stop together remains open |
| Current Chrome and Edge full workflow | In-app Chromium study workflow passed; owner browser voice playback and revised letter recognition confirmed. A complete Edge workflow has not been observed |
| Keyboard and final responsive QA | Modal Shift+Tab containment and Escape dismissal with focus restoration passed. Visible focus styling, hidden mobile navigation, responsive tabs, and final 390 × 844 layouts were inspected. This is not a full accessibility audit |
| Complete sign-in → upload → voice question → citation → questions/edit → practice → export → security demonstration | Individual browser/backend stages passed as recorded above. One uninterrupted owner walkthrough, including the revised live-caption citation click, remains pending |

Intermittent local DNS failures were observed for AWS sign-in, STS and the npm registry before later calls succeeded. Correct-region sign-in and selecting the existing active session completed authentication. No TLS checks were disabled.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=tmp\test-results.xml
npm.cmd --prefix web test
npm.cmd --prefix web run build
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix web audit
```

Use the synthetic sample in `examples/cybersecurity-study.pdf`, the [demonstration guide](DEMO.md), [AWS sign-in runbook](AWS-LOGIN.md), and [threat model](SECURITY.md). Update this record with actual live results after the remaining checks; do not change a pending item to passed based only on code inspection.
