# Plan: open-source OCR instead of Claude, so Table Reader can run on a server

Written 2026-10-09. **Plan only — nothing built yet.** Builds on `PLAN.md` (the app) and `NEXT-SESSION.md` (current
state). Phases here are numbered **O0–O7** so they don't clash with PLAN.md's phases.

## 1. Goal

Read scans and photos with OCR software that runs on our own machine (no Claude plan, no per-page fee, no sign-in),
so the whole app can later be hosted on a server and used from a browser. Everything after the reading step stays
as it is: job folders, yellow cells, corrections in `edits.json`, CSV, payroll.

## 2. The honest starting point

**What the September sample folder contains** (counted 2026-10-09, counts only):

| Kind | Amount | Needs OCR? |
|---|---|---|
| Photos (JPEG/PNG) | 91 files | Yes. Mostly handwritten logbooks, IN/OUT cards, stamped time cards, tick grids |
| Scanned PDFs (no text layer) | 82 documents | Yes |
| **Digital PDFs (real text layer)** | **30 documents, 79 of 220 PDF pages** (+5 mixed) | **No.** The text and numbers are inside the file, exact |
| Excel (.xlsx/.xls) | 10 files | **No.** Cells can be read directly (skipped today) |

**What Tesseract can and cannot do with these:**
- **Good:** clean printed or typed text, e.g. computer reports scanned at a decent resolution.
- **Poor:** handwriting. Its word-level accuracy collapses on free or joined writing. Dot-matrix stamped times,
  phone photos taken at an angle and faint ticks are also hard.
- **Missing:** it doesn't understand tables. Rows and columns have to be found by our own code (grid lines, word
  positions).

So **Tesseract alone would turn most handwritten cells yellow**. Nothing would be guessed, because the never-guess
rule still applies, but staff would type much more by hand than today. To keep the handwriting quality we have now,
the realistic open-source option is a **self-hosted open-weight document model** (a "vision-language model", the
same kind of AI as Claude but running on our own GPU).

## 3. Recommended design: one reading step, several engines, chosen per page

```
upload ─► pages.py ─► for each page, the router picks the cheapest engine that can read it:
                       0. Excel file              → read the cells directly (exact)
                       1. PDF page with text layer → take the words + positions from the PDF (exact)
                       2. printed / typed scan     → classic OCR (Tesseract or RapidOCR) + table finder
                       3. handwriting / stamps     → self-hosted document model on a GPU (if we have one)
                     ─► same raw page dict as today ─► ocr.normalize_page (never-guess gate) ─► reading/page-N.json
```

- **Engine interface** (new `engines/` package). Each engine has `status()` → `{ready, message}` and
  `read_page(image) -> raw page`. The raw page uses the same shape Claude returns today: `quality`, `header_fields`,
  `column_labels`, `rows`, `notes`, cells with `value / raw_text / confidence / unclear_reason`. `jobs.Jobs(reader=…)`
  already takes a reader function, so jobs, edits, CSV and payroll do not change.
- **Claude becomes one engine among several**, kept for the desktop app and as a fallback:
  - On a server it **cannot** be the signed-in CLI on a personal Pro plan.
  - The server option is an Anthropic **API key**, paid per page; PLAN.md §7 already listed this as the fallback.
- **Provenance:** every page records which engine and model read it (`engine`, `model`, `timing`). The screen and CSV
  can then say "read by Tesseract 5", and the bake-off can compare engines.
- **Never-guess stays the single gate.** `normalize_page` already blanks any value with a low confidence, a `?`, or a
  reason. Each engine only has to supply honest confidence numbers:

| Engine | Where its confidence comes from |
|---|---|
| Excel / PDF text layer | Exact: 100, nothing flagged |
| Tesseract | Per-word confidence 0–100. A cell's confidence = its weakest word |
| RapidOCR / PaddleOCR | Recognition score 0–1 × 100 |
| Document model (vLLM) | Token probabilities (`logprobs`) of the cell's text, plus the model's own doubts (same compact `doubts` format as today) |

- **Extra safety for classic OCR: two engines must agree.** Run Tesseract **and** RapidOCR on the same cell crop. Same
  text → trusted. Different text → yellow, with both readings shown as "marks seen". This is cheap on a CPU and catches
  "confident but wrong", the error the never-guess rule exists to stop.
- **Thresholds per engine.** `UNSURE_BELOW = 70` was tuned for Claude. Each engine gets its own threshold, set from
  the bake-off (O0) so that confidently wrong cells stay near zero.

## 4. Engine candidates (to be measured in O0, not chosen on paper)

| Engine | Kind | Licence | Hardware | Handwriting | Tables | Notes |
|---|---|---|---|---|---|---|
| **Tesseract 5** | classic OCR | Apache-2.0 | CPU | poor | no (our code) | Needs the `tesseract` program + language data (eng, msa, chi_sim). On Windows, extra install to bundle |
| **RapidOCR** (PP-OCRv5 models on ONNX) | classic OCR | Apache-2.0 | CPU | fair on neat print-style writing | via RapidTable (ONNX) | Pure `pip`, no separate program: easiest to package. Check Python 3.14 wheels |
| **PaddleOCR 3.x / PP-StructureV3** | classic OCR + layout/table | Apache-2.0 | CPU (slow) / GPU | fair | yes (HTML) | Heavier install (PaddlePaddle) |
| **GLM-OCR** (0.9B) | small document model | MIT | GPU (small); CPU possible but slow | good | yes (HTML/Markdown) | Outputs Markdown/HTML, needs a parser into our page shape |
| **PaddleOCR-VL 1.6** (0.9B) | small document model | check in O0 | GPU (vLLM/SGLang) | good | yes | Top of current document benchmarks |
| **Qwen3-VL 8B** (or 4B) | general vision-language model | Apache-2.0 | GPU, ~24 GB for 8B | good | follows our own JSON prompt | Can reuse `COMPACT_PROMPT` + schema almost unchanged (vLLM structured output) |
| Claude (API key) | hosted | paid per use | none | very good | yes | Kept as fallback / baseline |

**Avoid for a hosted service unless the licence is checked and accepted:** Surya/Marker (GPL code, model weights
restricted for larger companies) and anything AGPL (network copyleft). Every engine's licence and model-weight terms
are re-checked in O0 before any code depends on it.

## 5. Phases

| Phase | Work | Done when | Size |
|---|---|---|---|
| **O0. Bake-off** (decides everything else) | Gold set: 25–30 pages across every card type (stamped time cards, handwritten IN/OUT cards, logbooks, tick grids, scanned reports, digital PDFs). The user checks **every** cell in the app, so the corrected reading becomes the answer key (kept on this PC, never in git). Extend `bench.py` with `bench.py engines --gold …` to run each engine and print counts only: correct-and-trusted, **wrong-but-trusted**, yellow, missing rows/columns, seconds per page, RAM/GPU used. Claude's existing readings of the same pages give the baseline | A table per document type: which engine is good enough, and on what hardware | M |
| **O1. Engine interface** (no behaviour change) | `engines/base.py`; move the current Claude CLI code to `engines/claude_cli.py`; one setting chooses the engine (config file / environment variable, not a settings screen). Claude status box becomes a generic "Reading engine" box. `OcrError` and plain-language messages kept. All 268 tests still pass + fake-engine tests | The app works exactly as today, through the new interface | S |
| **O2. No-OCR paths** (useful even on the desktop) | Excel → table directly (`openpyxl`, `xlrd`; adapt the PayTrace `readers.py` tabular reader). Digital PDF pages → words with positions from pypdfium2 → rows/columns from word positions; a row whose words don't line up with the columns is flagged, never forced. Exact values, confidence 100 | ~30 digital PDFs and 10 Excel files read in seconds, without Claude or OCR | S–M |
| **O3. Classic OCR engine** | Clean the image (grey, deskew, contrast) and detect orientation (Tesseract OSD or PaddleOCR's orientation model). Find the table: ruled lines → cell grid, else cluster word positions into rows/columns. OCR the whole page once with word boxes and assign words to cells; re-read only doubtful cells on their crop. Two-engine agreement (§3). Header text above the table → `header_fields`. Columns of times/numbers get a character whitelist | Printed/scanned reports read with near-zero wrong-but-trusted cells on the gold set | L |
| **O4. Document-model engine** (only if O0 says yes and a GPU is available) | vLLM server running the model chosen in O0 (OpenAI-compatible API). Engine sends the page image + our prompt/schema (Qwen3-VL) or parses the model's HTML table (GLM-OCR / PaddleOCR-VL). Confidence from logprobs. Keep the rotation looks (`MAX_LOOKS`). Timeouts, retries and "the reading server is not answering" messages | Handwritten cards on the gold set at or near Claude's level, with wrong-but-trusted ≤ Claude's | M–L |
| **O5. Router + calibration** | Pick the engine per page: text layer → O2; else a quick check (classic OCR confidence/coverage, or a small classifier) decides printed → O3, handwritten → O4. Thresholds per engine from O0 data. Page shows "Read by …" | Whole sample of 10 files per type runs end to end with the right engine per page | M |
| **O6. Server version** (separate track, §6) | Accounts, HTTPS, per-company storage, worker pool, Docker image | Runs on a server; two users from two companies cannot see each other's files | L |
| **O7. Pilot** | Same documents read by the new engines and by Claude; staff check them as usual; measure % yellow, minutes of checking per page, any wrong value that was not yellow | Agreed accuracy/time target met (decide the target before starting) | — |

Recommended order: **O0 → O1 → O2 → O3 → (O4 if GPU) → O5 → O7, with O6 in parallel once O1 is done.** O1 and O2 pay
off immediately on the desktop: exact digital PDFs and Excel, and fewer Claude pages.

## 6. What "host it on a server" also needs (not OCR, but blocks hosting)

The app is built for one person on their own PC. On a server these change:

| Today (desktop) | Needed on a server |
|---|---|
| Only `localhost` may connect; no logins | Logins (per person), HTTPS, sessions; maybe one login per client company |
| Files in `Documents\Table Reader\` | Server data folder (or object storage) **per company/user**, backups, encryption at rest |
| One document read at a time, in-process thread | Job queue + worker processes (CPU OCR workers; GPU model server shared) |
| Claude sign-in box, **Quit** button, `start.py`, PyInstaller `.exe` | Removed; replaced by a Docker image (Python 3.12/3.13 + Tesseract + language data + ONNX models baked in) and a separate vLLM container if O4 |
| No delete | Delete files, keep-for-N-days rule, export everything |
| Personal data never leaves the PC | Payroll/HR data now on a server: **PDPA**. Who runs the server, where it is, who can see it, access log, written sign-off from management |
| Logs on the PC | Server logs with **no** names/values (same rule as today's scripts) |

**`CLAUDE.md` rules that will need to change** (only after the user agrees): "OCR only through the signed-in Claude
Code CLI", "keep everything on the local PC" and "no accounts". The "never guess" rule and "Claude's/the engine's
reading is never modified" stay exactly as they are.

## 7. Hardware and running cost (to confirm with real quotes)

| Setup | Engines possible | Expected speed per page |
|---|---|---|
| CPU-only server (e.g. 4 vCPU, 8–16 GB RAM) | O2 + O3 (Tesseract/RapidOCR) | O2 under a second; O3 a few seconds (measure in O0) |
| Server with one GPU (≥16 GB VRAM for 0.9B models, ~24 GB for an 8B model) | O2 + O3 + O4 | A few seconds per page (measure in O0) |
| Small models on CPU only (llama.cpp/ONNX) | O4 slowly | Possibly a minute or more per page: only for small volumes |

A GPU server costs far more per month than a CPU one. If volumes are low, a mixed setup may be cheaper:
**CPU server + Claude API key only for handwritten pages**. O0 gives the numbers to decide.

## 8. Risks

- **Handwriting accuracy drops** without a document model: more yellow cells, more typing. Mitigation: O0 measures it
  first; O4; keep Claude as a fallback engine.
- **Confident but wrong** classic OCR (Tesseract's confidences are not well calibrated). Mitigation: two-engine
  agreement, per-engine thresholds from the gold set, payroll still refuses unconfirmed days.
- **Dot-matrix stamped times** are hard for every engine; expect them yellow unless O4 does well on them.
- **Table finding** on photos (skewed, curled logbooks, no ruled lines) is the hardest part of O3. Rows that don't
  line up are flagged, never forced into a column.
- **Python 3.14:** some OCR libraries (onnxruntime, PaddlePaddle) may not ship 3.14 wheels yet. The server image can
  pin 3.12/3.13; the desktop build may need the same.
- **Packaging on Windows:** Tesseract needs its own program + data files bundled; RapidOCR is pip-only.
- **Licences of model weights** can differ from the code licence: checked in O0.
- **Privacy:** moving to a server is a bigger privacy change than the OCR swap itself (§6).

## 9. Decisions (answered by the user 2026-10-09)

| # | Question | Answer | Consequence |
|---|---|---|---|
| 1 | Server hardware | **CPU only** | No GPU model server. O4 must run a *small* document model on CPU (llama.cpp / ONNX), or not at all |
| 2 | Keep today's handwriting/stamp quality? | **Yes** | Tesseract/RapidOCR alone cannot meet it. Hinges on a small document model being good **and** fast enough on CPU |
| 3 | Users | **Only our own staff** | One organisation: simple logins, no per-client separation (O6 smaller) |
| 4 | Claude as backup | **No** | No Claude engine on the server; the desktop CLI engine may stay only until the switch |
| 5 | Gold set | **Yes, user will check 25–30 pages fully** | O0 scores against a real answer key |
| 6 | Speed target | **Average under 1 minute per page** (on the server CPU) | Engines measured on this laptop's slower U-series CPU give an upper bound |
| — | Other tools | User asked Claude to find and try other OCR tools | O0 widened: small document models on CPU, not only Tesseract |

**The tension:** 1 + 2 + 4 together only work if a small open model on CPU reads handwriting close to Claude's level
in under a minute per page. If O0 shows none does, the choice falls back to the user: a GPU server, or accept more
yellow cells on handwritten cards (printed and digital documents are unaffected).
