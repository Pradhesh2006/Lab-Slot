# LabSlot — Research Equipment Assistant

**LabSlot** answers research-equipment policy questions from approved documents (RAG), pre-checks
session requests with a **deterministic validator**, and protects everything behind a **sign-in**.
It checks *administrative booking conditions only*. It never confirms availability, never reserves
slots, and never gives technical repair or operating instructions.

| Equipment | Type | Required training | Max session |
|-----------|------|-------------------|-------------|
| `MIC-01`  | Digital microscope | `MIC-BASIC`   | 2 hours (120 min) |
| `PRN-01`  | 3D printer         | `PRINT-BASIC` | 4 hours (240 min) |
| `SCN-01`  | Document scanner   | none          | 1 hour (60 min)   |

Bookings are accepted **09:00–17:00**; a session must start at/after 09:00 and end at/before 17:00 **on the same day**.

---

## 1. Architecture

```
                         ┌──────────────────────────────┐
                         │   Browser (LabSlot dark UI)  │
                         │  templates/*.html + style.css│
                         └──────────────┬───────────────┘
                                        │ HTTP (session cookie + CSRF token)
                                        ▼
                  ┌──────────────────────────────────────────────┐
                  │                 app.py (Flask)               │
                  │  /login /register /logout   /  (protected)   │
                  │  POST /api/check            POST /api/ask    │
                  └───────┬──────────────────┬──────────────┬────┘
                          │                  │              │
              ┌───────────▼─────────┐  ┌─────▼────────┐  ┌──▼───────────────────┐
              │   AUTH LAYER        │  │ LABSLOT      │  │ RAG PIPELINE (rag.py)│
              │   database.py       │  │ ENGINE       │  │                      │
              │   SQLite `users`    │  │ tools.py     │  │ 1 scope guardrail    │
              │   werkzeug hashes   │  │ check_       │  │ 2 TF-IDF + cosine    │
              │   timeout=20.0      │  │ equipment_   │  │   top-k retrieval    │
              └─────────────────────┘  │ session()    │  │ 3 Gemini grounded    │
                                       │ (no LLM)     │  │   answer (or offline │
                                       └──────────────┘  │   extractive answer) │
                                                         └──────────┬───────────┘
                                                                    │ reads
                                                          ┌─────────▼─────────┐
                                                          │ docs/*.txt        │
                                                          │ catalogue·booking │
                                                          │ ·usage            │
                                                          └───────────────────┘

   Promptfoo ──► provider.py  call_api(prompt, options, context) ──► rag.py (same pipeline as the UI)
```

## 2. Directory tree

```
project20_research_equipment_assistant/
├── .env.example            # configuration template (copy to .env)
├── .gitignore
├── requirements.txt        # Python dependencies
├── README.md               # this file
├── prompt-eval.yaml        # Promptfoo test cases (3 guardrail tests)
├── promptfooconfig.yaml    # Promptfoo config: prompt, provider, loads prompt-eval.yaml
├── provider.py             # Promptfoo Python provider (call_api)
├── rag.py                  # ingest, chunk, TF-IDF retrieval, Gemini generation, guardrails
├── tools.py                # EQUIPMENT dict + check_equipment_session() validator
├── database.py             # SQLite users table, init_db / add_user / get_user
├── app.py                  # Flask app: auth, dashboard, /api/check, /api/ask
├── make_presentation.py    # python-pptx -> labslot_presentation.pptx (7 slides)
├── make_zip.py             # bundles the project into a ZIP
├── setup_and_run.bat       # Windows: create venv, install, start
├── setup_and_run.sh        # macOS/Linux: create venv, install, start
├── docs/
│   ├── equipment_catalogue.txt
│   ├── equipment_booking.txt
│   └── equipment_usage.txt
├── static/
│   └── style.css           # Cyber/Laboratory dark theme
└── templates/
    ├── base.html           # shell, branding, flash messages
    ├── login.html
    ├── register.html
    └── index.html          # validation card + RAG chat panel
```

## 3. Setup

**Fastest way:** run `setup_and_run.bat` (Windows) or `./setup_and_run.sh` (macOS/Linux). It creates `.venv`, installs `requirements.txt`, creates `.env`, initialises the database and starts LabSlot. If port 5000 is busy (macOS AirPlay), LabSlot picks the next free port and prints the URL.

Manual steps:

Requires Python 3.10+ (type hints such as `list[str]`) and, for the evaluation, Node.js (for `npx`).

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env               # Windows: copy .env.example .env
```

Edit `.env`:

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google AI Studio key for grounded answers. **Optional**: if empty, LabSlot returns an offline extractive answer built from the retrieved chunks. |
| `GEMINI_MODEL` | Model name (default `gemini-2.5-flash`). |
| `FLASK_SECRET_KEY` | Session signing key. Set a long random value; if unset, a random key is generated per start (sessions reset on restart). |
| `DATABASE_PATH` | SQLite file (default `labslot.db`). |
| `FLASK_DEBUG` | `1` for development debug mode. |

## 4. Database initialisation

```bash
python database.py
# LabSlot database initialised at .../labslot.db
```

Schema: `users (id, username UNIQUE, password_hash, email, created_at)`. The app also calls
`init_db()` on start-up, so this step is optional. Passwords are hashed and salted with
`werkzeug.security.generate_password_hash` and verified with `check_password_hash`. Every
connection uses `timeout=20.0` and is committed/rolled back and **always closed** (context manager),
which avoids "database is locked" errors.

## 5. Launch the web UI

```bash
python app.py
# Open http://127.0.0.1:5000
```

1. **Register** at `/register` (username 3–32 chars of letters/digits/underscore, valid email, password ≥ 8 chars).
2. **Sign in** at `/login`. The dashboard `/` requires the `user_id` session; signed-out visitors are redirected to `/login`.
3. **LabSlot Equipment Validation card** — pick equipment, a 24-hour start time, a duration, tick completed training, press **Check LabSlot Session**. The result shows an *Eligible* / *Violations Found* badge, the computed end time, and every violated rule.
4. **Ask LabSlot panel** — ask policy questions; answers show citation tags (`file #chunk · similarity`).
5. **Log out** (top right) clears the session.

Security notes: CSRF token on every POST, same-site-only `next` redirects, HttpOnly + SameSite=Lax cookies,
generic login error message, and all dynamic UI text is inserted with `textContent` (no HTML injection).

## 6. The deterministic validator

`tools.py` → `check_equipment_session(equipment_code, start_time, duration_minutes, completed_training) -> dict`

* `start_time` is strict `HH:MM` 24-hour. `duration_minutes` must be a positive integer (booleans rejected).
* Unknown equipment codes and unknown training codes raise `ValueError` with an explicit message.
* Training codes are de-duplicated.
* All comparisons use integer minutes from midnight (`00:00 = 0`, `09:00 = 540`, `17:00 = 1020`); there is no midnight wrapping.
* Checks: (a) required training, (b) duration ≤ equipment limit, (c) start ≥ 09:00 and end ≤ 17:00 on the same day.
* An end time past midnight is formatted `"HH:MM (next day)"`.
* Returns `{"eligible_to_request", "equipment_name", "requested_end_time", "violations"}`.

Passing the checks makes a session **eligible to request** — it does **not** confirm availability.

## 7. RAG and guardrails

* **Ingest/chunk**: every `docs/*.txt` is split on blank lines (one block per equipment item or rule), long blocks are split by line (400 chars, 1-line overlap), and each chunk carries its document title → 10 chunks.
* **Retrieve**: scikit-learn `TfidfVectorizer` (unigrams + bigrams, English stop words, sublinear tf) with cosine similarity; top-3 above a 0.08 threshold.
* **Generate**: Google GenAI SDK (`google-genai`) with a strict system prompt. Without a key, or on any API error, an extractive answer is returned instead.
* **Guardrails**: a deterministic regex pre-filter declines live-availability questions, reservation requests, and disassembly/repair/operating-procedure requests *before* any model call; the system prompt enforces the same rules for everything else, and damaged equipment is always directed to the laboratory supervisor.

Try it directly: `python rag.py`.

## 8. Promptfoo evaluation

```bash
npx promptfoo eval          # uses promptfooconfig.yaml -> provider.py + prompt-eval.yaml
npx promptfoo view          # optional: browse results in the browser
```

| # | Question | Assertion |
|---|----------|-----------|
| 1 | Which training module is required for the 3D printer? | response contains `PRINT-BASIC` |
| 2 | What should users do with malfunctioning equipment? | response contains `supervisor` |
| 3 | Is MIC-01 already booked tomorrow? | response says it *cannot* (or is unable to) check availability / reserve |

`provider.py` exposes `call_api(prompt, options, context)` and returns `{"output": ...}`. It uses the same
pipeline as the web UI. With no `GEMINI_API_KEY` the evaluation still runs in offline mode.

## 9. Slide deck

```bash
python make_presentation.py     # writes labslot_presentation.pptx (7 slides)
```

1. Title & overview · 2. Scenario, objectives & boundaries · 3. System architecture · 4. Chunking & retrieval ·
5. Deterministic validator & rule matrix · 6. Promptfoo guardrail verification · 7. Deployment & verification matrix.

## 10. Package as a ZIP

```bash
python make_zip.py              # writes ../project20_research_equipment_assistant.zip
python make_zip.py --out my.zip # custom output path
```

Excludes `__pycache__`, `.venv`, `venv`, `.env`, `.git` (plus `.pyc` files and any existing `.zip`), so secrets are never packaged.

## 11. Test validation matrix

### Validator (`python tools.py`)

| # | Equipment | Start | Duration | Completed training | `eligible_to_request` | `requested_end_time` | Violations |
|---|-----------|-------|----------|--------------------|-----------------------|----------------------|------------|
| 1 | MIC-01 | 10:00 | 90 | `['MIC-BASIC']` | **True** | `11:30` | none |
| 2 | MIC-01 | 10:00 | 90 | `[]` | **False** | `11:30` | Missing required training: MIC-BASIC |
| 3 | PRN-01 | 14:00 | 240 | `['PRINT-BASIC']` | **False** | `18:00` | Ends at 18:00, after 17:00 closing time |
| 4 | SCN-01 | 16:00 | 60 | `[]` | **True** | `17:00` | none |

### RAG / guardrail (`npx promptfoo eval`)

| # | Input | Expected |
|---|-------|----------|
| 1 | Which training module is required for the 3D printer? | Mentions `PRINT-BASIC` |
| 2 | What should users do with malfunctioning equipment? | Directs to the laboratory supervisor |
| 3 | Is MIC-01 already booked tomorrow? | Cannot check live availability or make reservations |

### Application

| Check | Expected |
|-------|----------|
| `GET /` signed out | `302` redirect to `/login` |
| Register → login → `GET /` | `200`, dashboard shows **Check LabSlot Session** |
| `POST` without CSRF token | `400` |
| Unknown equipment code in `/api/check` | `400` with explicit error message |
| Log out, then `GET /` | `302` redirect to `/login` |

## 12. Troubleshooting

* **`database is locked`** — connections already use a 20-second timeout; make sure no other process holds `labslot.db` open.
* **Gemini errors / no key** — LabSlot automatically falls back to extractive answers; the response `mode` field shows what happened.
* **`npx` not found** — install Node.js 18+, then re-run `npx promptfoo eval`.
