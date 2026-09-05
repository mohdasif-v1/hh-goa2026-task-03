# Implementation Plan
## Face → Web → Blockchain Verification Pipeline
### HH Goa 2026 — Shortlisting Task 3 — Solo, 1-Day Sprint

This plan assumes a ~12-hour working day plus buffer. Every hour block has: goal,
concrete steps, commands, a "done when" checkpoint, and a contingency if it goes wrong.
Do not revisit a decision once its checkpoint is hit — move forward and fix later if
truly broken.

---

## Pre-flight (before Hour 0 — do this the night before if possible)
- Identify the already-publicly-indexed photo of yourself you'll use as the search
  anchor (GitHub avatar URL, LinkedIn photo URL, personal site photo URL). Confirm the
  URL loads in a browser directly (not behind login).
- Create a GitHub repo, empty, named e.g. `face-chain-verifier`.

---

## Hour 0 (0:00–0:30) — Lock external dependencies first
**Goal**: every external account/credential/fund request that has unpredictable lag is
started immediately, before any code is written.

Steps:
1. `git init`, push an empty repo with `.gitignore` (Python template) and
   `.env.example`.
2. Sign up for SerpApi, copy the free-tier API key into a scratch note (not `.env` yet).
3. Generate a throwaway Ethereum-compatible keypair (e.g. via `eth_account` in a
   throwaway Python shell, or any wallet generator you trust) — this becomes your
   `PRIVATE_KEY` / `WALLET_ADDRESS`. **Never reuse a real wallet's key.**
4. Go to the official Polygon Amoy faucet, request testnet funds for that address.
   **This step alone can take 15 minutes to a few hours to land — start it now, not
   later.**

Done when: SerpApi key in hand, throwaway wallet generated, faucet request submitted.

Contingency: if the faucet UI is down or rate-limited, try a second official faucet
source for Amoy; keep retrying in the background while continuing other hours' work —
do not block on this.

---

## Hour 0.5–1 (0:30–1:00) — Environment setup and the one irreversible decision
**Goal**: decide face library once, correctly, and move on.

Steps:
```bash
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install deepface opencv-python pillow requests python-dotenv web3 rich python-dotenv
```
Smoke test:
```python
from deepface import DeepFace
result = DeepFace.represent(img_path="path/to/any_face.jpg", model_name="ArcFace")
print(len(result[0]["embedding"]))
```
Decision rule: if this install/run fights you (dependency conflicts, missing system
libraries) for more than ~15 minutes of active troubleshooting, stop and switch to:
```bash
pip install face_recognition
```
Whichever works, that is your final choice for the day — do not revisit.

Done when: you can produce an embedding vector from a test image, in either library.

---

## Hour 1–3 (1:00–3:00) — Face pipeline
**Goal**: `face_match.py` reliably matches your own enrolled photos.

Steps:
1. Create `data/gallery/subject_001/` with 2-3 clear, well-lit photos of yourself.
2. Write `config.py` (loads `.env`, exposes constants — see TRD Section 4.1).
3. Write `face_match.py`:
   - `load_gallery()` — embed every enrolled image once.
   - `embed_face(image_path)` — embed a new input image.
   - `match_against_gallery(embedding, gallery)` — cosine similarity, return best match
     + confidence, compare against `FACE_MATCH_THRESHOLD`.
4. Test with a small script: run 2-3 *different* photos of yourself as "input scans"
   through `match_against_gallery` and confirm consistent, confident matches.

Done when: at least 2 different self-photos correctly and confidently match against the
gallery, and confidence scores are printed (not just true/false).

Contingency: if confidence scores are inconsistent/low across your own photos, add one
more gallery image with different lighting/angle rather than lowering the threshold
arbitrarily — a threshold that's too permissive undermines the "genuine match" story.

---

## Hour 3–5 (3:00–5:00) — Search pipeline
**Goal**: `web_search.py` performs a real, live search and picks a real result.

Steps:
1. Write `data/enrollment.json` (see TRD Section 3.1) with your name, your gallery
   directory, your public photo URL, and 1-2 text search terms as fallback.
2. Write `web_search.py`:
   - `build_query(enrollment_record)` — prefers image URL, falls back to text terms.
   - `run_search(query)` — calls SerpApi's `google_lens` engine (image) or `google`
     engine (text). Example (image-based):
     ```python
     import requests
     params = {
         "engine": "google_lens",
         "url": enrollment_record["search_image_url"],
         "api_key": SERPAPI_KEY,
     }
     resp = requests.get("https://serpapi.com/search", params=params)
     data = resp.json()
     ```
   - `select_best_result(results, enrollment_record)` — pick the first result whose
     `title`/`link` contains a known identifier (your GitHub username, name, etc.).
3. Run it for real. Print the raw response once during development to confirm this is
   a live call (keep a copy in your notes for later credibility/documentation, even
   though it won't be quoted verbatim in the README).

Done when: a real API call returns real results and the selection function picks a
genuinely relevant post about you, with zero hardcoded URLs anywhere in the code.

Contingency: if the image-based Lens search returns nothing useful, immediately fall
back to the text-search-term path in the same run rather than debugging the image path
further — both are legitimate "genuine search" implementations per the task's wording.

---

## Hour 5–6 (5:00–6:00) — Fingerprinting
**Goal**: deterministic, verifiable hashing of discovered content.

Steps:
1. Write `fingerprint.py` (see TRD Section 4.4): `canonicalize()` and `fingerprint()`.
2. Write a tiny manual test: hash the same dict twice (confirm identical output), then
   change one field and hash again (confirm different output).
3. Wire `app.py` so far: face match → search → build canonical content dict →
   fingerprint. Save the result to `output/run_logs/<timestamp>.json`.

Done when: fingerprinting is deterministic and demonstrably sensitive to any content
change, and a run log file is being written.

---

## Hour 6–8 (6:00–8:00) — Blockchain write + verify
**Goal**: the fingerprint is provably on a public testnet and re-verifiable.

Steps:
1. Confirm faucet funds have landed:
   ```python
   from web3 import Web3
   w3 = Web3(Web3.HTTPProvider(RPC_URL))
   print(w3.eth.get_balance(WALLET_ADDRESS))
   ```
   If zero, go back to the faucet now — everything else in this hour block depends on
   this.
2. Write `chain.py`:
   - `send_fingerprint(fingerprint_hex)` — build, sign, send a raw self-transaction
     with `data=bytes.fromhex(fingerprint_hex)`, wait for receipt, return `tx_hash`.
   - `verify_fingerprint(tx_hash, expected_fingerprint_hex)` — fetch the transaction,
     read `.input`, compare.
3. Run it for real against your Hour 5–6 fingerprint. Confirm the transaction resolves
   on `https://amoy.polygonscan.com/tx/<tx_hash>`.
4. Call `verify_fingerprint` with the correct fingerprint → expect `True`/VERIFIED.

Done when: a real, explorer-visible transaction exists, and verification against the
correct fingerprint returns true.

Contingency: if `send_raw_transaction` fails on gas estimation, explicitly set a
reasonable `gas` limit (e.g. 30000, since this is a simple value+data transfer, not a
contract call) and current network `gasPrice`/EIP-1559 fields rather than relying on
defaults.

---

## Hour 8–9.5 (8:00–9:30) — Full orchestration + CLI polish
**Goal**: one command runs the entire pipeline and prints a clean, judge-legible output.

Steps:
1. Finish `app.py` per TRD Section 4.7 — straight-line orchestration, no hidden
   branching.
2. Write `cli.py` using `rich`: numbered steps with checkmarks, a boxed final summary,
   mirroring the task's own example CLI format (face match confidence, search
   provider + result count, fingerprint, chain/tx/block, final VERIFIED banner).
3. Run the full pipeline top to bottom via `python app.py --input data/input/scan.jpg`.

Done when: a single command produces the entire step-by-step output cleanly, with no
manual intervention beyond providing the input path.

---

## Hour 9.5–10.5 (9:30–10:30) — Tamper-detection demo
**Goal**: prove the verification step is real, not decorative.

Steps:
1. After a successful VERIFIED run, write a small script/flag (e.g.
   `--tamper-demo`) that takes the same content dict, mutates one field (append a
   character to the title), recomputes the fingerprint, and calls
   `verify_fingerprint(tx_hash, new_fingerprint)`.
2. Confirm this prints `MISMATCH` / `TAMPERED`, with both hashes shown side by side.
3. Decide the exact on-screen wording now (e.g. "Original Hash" vs "Recomputed Hash",
   "Result: TAMPERED") so it reads clearly to someone watching a recording once.

Done when: running the tamper demo path reliably and clearly prints a mismatch, right
after a clean VERIFIED run in the same session.

---

## Hour 10.5–11 (10:30–11:00) — Full dry run
**Goal**: a single uninterrupted run exactly as it will be recorded.

Steps:
1. Reset any test artifacts (clear `output/run_logs/` if desired, keep `data/` as is).
2. Run the complete flow start to finish: normal run → VERIFIED → tamper demo →
   TAMPERED, without editing code in between.
3. Fix only what breaks. Do not add new features at this point — this is a freeze,
   not a development window.

Done when: the exact sequence you intend to record runs cleanly once, back to back.

---

## Hour 11–11.5 (11:00–11:30) — Recording
**Goal**: one clean take.

Steps:
1. Set up screen recording (OBS, Loom, or built-in OS tool).
2. Narrate briefly at the start: what this is, and the one-sentence ethical framing
   ("this uses a self-enrolled, consented test subject and previously published
   content — it does not identify unknown people").
3. Run the pipeline exactly as rehearsed. Let the explorer link resolve visibly if you
   click it. Show both VERIFIED and TAMPERED outcomes in the same recording.
4. Stop recording. No editing needed — the task explicitly says a plain recording is
   sufficient.

Done when: you have one recording, in hand, showing the complete required sequence.

---

## Hour 11.5–12 (11:30–12:00) — README, push, submit
**Goal**: submission-ready repo and form.

Steps:
1. Write `README.md` with: project description, ethical framing paragraph, setup/run
   instructions (TRD Section 9), which blockchain and why no smart contract (TRD
   Section 2), known limitations (TRD Section 10).
2. Double-check `.env` is gitignored and not committed; confirm `.env.example` is
   present and complete.
3. Final commit and push.
4. Upload the recording (YouTube unlisted / Drive / Loom), copy the link.
5. Submit the form with the GitHub repo link and recording link.

Done when: form is submitted. Remember: **no resubmissions are allowed** — do not
submit until everything above is actually confirmed working, not just believed to be
working.

---

## Buffer (whatever time remains)
Reserved exclusively for:
- Faucet funds arriving late (Hour 0's biggest risk)
- A second recording take if the first has a technical issue (audio, screen capture
  glitch, an unexpected API hiccup)
- Any single remaining bug from the dry run that wasn't fully resolved in its own hour
  block

Do not use buffer time to add scope. If everything above is done early, stop — a
smaller, fully-working, fully-understood submission beats a larger, riskier one.

---

## Master checklist (quick pre-submission scan)
- [ ] Face match works on ≥2 of my own photos with confidence shown
- [ ] Search step makes a real, live API call — no hardcoded result URL anywhere
- [ ] Fingerprint is deterministic and content-sensitive
- [ ] Transaction is real, sent to Polygon Amoy, resolvable on Polygonscan
- [ ] Verification against correct content prints VERIFIED
- [ ] Verification against tampered content prints TAMPERED, shown in the same
      recording
- [ ] No website was built (not needed)
- [ ] `.env` is gitignored; `.env.example` is complete
- [ ] README covers: description, ethical framing, setup/run, blockchain choice,
      limitations
- [ ] Recording is one unedited take showing the full required sequence
- [ ] Form submitted with both links, only after everything above is confirmed
