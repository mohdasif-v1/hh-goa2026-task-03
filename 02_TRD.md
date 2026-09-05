# Technical Requirements Document (TRD)
## Face → Web → Blockchain Verification Pipeline
### HH Goa 2026 — Shortlisting Task 3

---

## 1. System Architecture

### 1.1 High-level data flow
```
┌─────────────────┐
│  Input face scan │
│   (image file)   │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────┐      ┌───────────────────────────┐
│   face_match.py           │◄─────┤  data/gallery/*.jpg (local) │
│  detect → embed → compare │      │  pre-enrolled subject photos │
└────────┬─────────────────┘      └───────────────────────────┘
         │  (best match, confidence)
         ▼
┌───────────────────────────────┐      ┌────────────────────────────┐
│  Look up enrollment record       │◄─────┤ data/enrollment.json         │
│  (search_terms, search_image_url)│      │ builder-authored, consented   │
└────────┬──────────────────────┘      └────────────────────────────┘
         │
         ▼
┌─────────────────────────┐      ┌──────────────────┐
│   web_search.py            │──────►│   SerpApi (live)   │
│  live reverse-image /       │◄──────┤   real HTTP call    │
│  text search call            │      └──────────────────┘
└────────┬─────────────────┘
         │  (selected post: url, title, timestamp)
         ▼
┌─────────────────────────┐
│   fingerprint.py            │
│  canonical JSON → SHA-256    │
└────────┬─────────────────┘
         │  (fingerprint hex string)
         ▼
┌─────────────────────────┐      ┌──────────────────────────┐
│   chain.py — WRITE           │──────►│ Polygon Amoy testnet RPC   │
│  build+sign+send raw tx      │◄──────┤ (public, free)             │
│  (data = fingerprint bytes)  │      └──────────────────────────┘
└────────┬─────────────────┘
         │  (tx_hash)
         ▼
┌─────────────────────────┐      ┌──────────────────────────┐
│   chain.py — VERIFY          │──────►│ Polygon Amoy testnet RPC   │
│  fetch tx by hash             │◄──────┤                            │
│  decode data field             │      └──────────────────────────┘
│  recompute fingerprint now    │
│  compare                        │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────────────┐
│   cli.py                     │
│  VERIFIED / TAMPERED output   │
└─────────────────────────┘
```

### 1.2 Component responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Load `.env`, expose constants (RPC URL, chain ID, API keys, thresholds) | `python-dotenv` |
| `face_match.py` | Face detection, embedding generation, gallery comparison | `deepface` (or `face_recognition` fallback), OpenCV, Pillow |
| `web_search.py` | Build and execute the live search query, parse and select a result | `requests`, SerpApi |
| `fingerprint.py` | Canonicalize discovered content, compute SHA-256 | `hashlib`, stdlib `json` |
| `chain.py` | Build/sign/send raw transaction; fetch/decode/verify | `web3.py` |
| `cli.py` | Render step-by-step colored terminal output | `rich` |
| `app.py` | Orchestrate the full pipeline in order, handle top-level errors | all of the above |

---

## 2. Technology Stack & Justification

| Choice | Alternative considered | Why this choice for a 1-day solo build |
|---|---|---|
| Python 3.11 | Node.js | Best-supported ecosystem for both face-recognition libs and web3 tooling in one language |
| DeepFace | InsightFace, face_recognition (dlib) | Pure pip install, no C-compiler/cmake dependency chain that can eat an hour on install alone |
| SerpApi | Direct Google Custom Search API, scraping | Purpose-built reverse-image/Lens engine, generous free tier, simple REST call |
| Polygon Amoy testnet | Ethereum Sepolia, local Ganache | Fast blocks, reliable public faucet, well-documented RPC, real public explorer for judge-facing credibility |
| Raw transaction data field | Custom Solidity smart contract | Removes compile/deploy/ABI risk entirely; still fully on-chain and independently verifiable |
| `rich` | Plain `print` | Near-zero cost, dramatically improves the recording's visual clarity |

---

## 3. Data Schemas

### 3.1 Enrollment record — `data/enrollment.json`
```json
{
  "id": "subject_001",
  "display_name": "<builder's name>",
  "gallery_dir": "data/gallery/subject_001",
  "search_image_url": "https://<public, already-indexed photo URL>",
  "search_terms": ["\"<builder's name>\" GitHub", "\"<builder's name>\" portfolio"],
  "consent_note": "Self-enrolled by the builder; used for demo purposes only."
}
```

### 3.2 Face match result (in-memory / logged)
```json
{
  "matched_id": "subject_001",
  "confidence": 0.87,
  "model": "ArcFace",
  "distance_metric": "cosine",
  "threshold_used": 0.68,
  "match": true
}
```

### 3.3 Search result selection (in-memory / logged)
```json
{
  "provider": "serpapi_google_lens",
  "query_used": "https://<search_image_url>",
  "raw_result_count": 6,
  "selected_result": {
    "url": "https://github.com/<username>",
    "title": "<page title>",
    "snippet": "<short excerpt>",
    "retrieved_at": "2026-09-06T10:15:00Z"
  }
}
```

### 3.4 Canonical content object (input to fingerprinting) — `fingerprint.py`
```json
{
  "url": "https://github.com/<username>",
  "title": "<page title>",
  "snippet": "<short excerpt>",
  "retrieved_at": "2026-09-06T10:15:00Z"
}
```
Canonicalization rule: keys sorted alphabetically, no extraneous whitespace, UTF-8
encoded, before hashing — this guarantees the same content always produces the same
hash regardless of dict ordering in Python.

### 3.5 Fingerprint record — saved to `output/run_logs/<timestamp>.json`
```json
{
  "canonical_object": { "...": "as above" },
  "sha256": "8a71c9f4...",
  "tx_hash": "0xabc123...",
  "chain": "polygon-amoy",
  "chain_id": 80002,
  "explorer_url": "https://amoy.polygonscan.com/tx/0xabc123...",
  "verification_result": "VERIFIED"
}
```

---

## 4. Module-Level Technical Specification

### 4.1 `config.py`
```python
# Responsibilities:
# - load .env
# - expose: SERPAPI_KEY, RPC_URL, CHAIN_ID, PRIVATE_KEY, WALLET_ADDRESS,
#           FACE_MATCH_THRESHOLD, GALLERY_DIR
```
Environment variables required (`.env.example`):
```
SERPAPI_KEY=
RPC_URL=https://rpc-amoy.polygon.technology
CHAIN_ID=80002
PRIVATE_KEY=            # throwaway testnet key ONLY, never a real wallet
WALLET_ADDRESS=
FACE_MATCH_THRESHOLD=0.65
```

### 4.2 `face_match.py`
Key functions:
- `load_gallery(gallery_dir: str) -> dict[str, list[np.ndarray]]`
  Loads and embeds all enrolled images once per run.
- `embed_face(image_path: str) -> np.ndarray`
  Wraps DeepFace's `represent()` call, returns a single embedding vector; raises a
  clear error if no face is detected.
- `match_against_gallery(embedding, gallery) -> MatchResult`
  Computes cosine similarity against every enrolled embedding, returns the best match,
  its confidence, and whether it clears `FACE_MATCH_THRESHOLD`.

Error handling: if no face is detected in the input image, fail fast with a specific
message ("no face detected in input image") rather than a raw stack trace — this matters
for a clean recording.

### 4.3 `web_search.py`
Key functions:
- `build_query(enrollment_record: dict) -> dict`
  Chooses image-URL-based reverse search if `search_image_url` is present, else falls
  back to text search using `search_terms`.
- `run_search(query: dict) -> list[dict]`
  Executes the live SerpApi call (`google_lens` engine for image URL, `google` engine
  for text fallback), returns parsed results.
- `select_best_result(results: list[dict], enrollment_record: dict) -> dict`
  Programmatic selection logic — e.g. prefer a result whose domain or title contains a
  known identifier from the enrollment record (username, display name). This function
  is what proves selection isn't hardcoded: it operates on live API output every run.

Error handling: if the API returns zero results, surface this clearly rather than
silently falling through — this is a known limitation to disclose, not paper over.

### 4.4 `fingerprint.py`
Key functions:
- `canonicalize(content: dict) -> str`
  `json.dumps(content, sort_keys=True, separators=(",", ":"))`
- `fingerprint(content: dict) -> str`
  `hashlib.sha256(canonicalize(content).encode("utf-8")).hexdigest()`

This module has no external dependencies and no side effects — keep it pure and easily
testable, since it's the piece a judge is most likely to mentally audit.

### 4.5 `chain.py`
Key functions:
- `get_web3() -> Web3`
  Connects to `RPC_URL`, confirms connection (`w3.is_connected()`).
- `send_fingerprint(fingerprint_hex: str) -> str`
  Builds a transaction: `to=WALLET_ADDRESS` (self), `value=0`,
  `data=bytes.fromhex(fingerprint_hex)`, `gas`, `gasPrice`/`maxFeePerGas` fetched from
  the network, `nonce` from `w3.eth.get_transaction_count`. Signs with `PRIVATE_KEY`,
  sends via `w3.eth.send_raw_transaction`, waits for receipt, returns `tx_hash`.
- `verify_fingerprint(tx_hash: str, expected_fingerprint_hex: str) -> bool`
  Fetches the transaction, extracts `.input` (strips leading `0x`), compares byte-for-
  byte against `expected_fingerprint_hex`. Returns `True`/`False`.

Important detail: `expected_fingerprint_hex` for the VERIFY step should be recomputed
from the content **at verification time**, not simply re-read from the earlier saved
log — that's what makes the tamper-detection demo meaningful rather than circular.

### 4.6 `cli.py`
Renders each pipeline stage as a `rich`-styled step, mirroring the task's own example
CLI output format (numbered steps, checkmarks, boxed summary at the end). Keep this
module purely presentational — it should take already-computed results as arguments and
never itself call an external API, so the "real work" is clearly separated from "how it
looks on screen."

### 4.7 `app.py`
Straight-line orchestration, no branching logic beyond error handling:
```python
def main():
    config = load_config()
    gallery = load_gallery(config.GALLERY_DIR)
    match = embed_and_match(input_image, gallery)
    enrollment = load_enrollment_record(match.matched_id)
    results = run_search(build_query(enrollment))
    selected = select_best_result(results, enrollment)
    content = build_canonical_content(selected)
    fp = fingerprint(content)
    tx_hash = send_fingerprint(fp)
    verified = verify_fingerprint(tx_hash, fingerprint(content))  # re-derive, don't reuse
    render_summary(match, selected, fp, tx_hash, verified)
```

---

## 5. Tamper-Detection Demonstration (technical mechanics)

This is a required demo beat (see PRD FR-3), not just a nice-to-have. Implementation:
1. Complete a full successful run; note the `content` dict and its fingerprint/tx_hash.
2. Mutate one field of `content` (e.g. append a character to `title`).
3. Recompute the fingerprint of the mutated content.
4. Call `verify_fingerprint(tx_hash, new_fingerprint)` — this will return `False`
   because the on-chain data field still contains the *original* fingerprint's bytes.
5. Print `TAMPERED` with both hashes shown side by side so the mismatch is visually
   obvious on the recording.

---

## 6. Security Considerations (scoped to a demo project)

- The private key used must be a **freshly generated, throwaway testnet keypair** —
  never a real wallet's key, and never committed to git (`.env` is gitignored).
- Testnet funds have no real value; this is explicitly a non-production system and the
  README says so.
- No raw personal image or biometric data is ever sent on-chain — only a SHA-256
  fingerprint of metadata, per PRD's ethical guardrails.
- API keys (SerpApi) are loaded from environment variables only.

---

## 7. Error Handling & Logging Strategy

| Failure point | Detection | Behavior |
|---|---|---|
| No face detected in input | DeepFace raises / returns empty | Print clear error, exit gracefully, do not proceed to search |
| No gallery match above threshold | Confidence below `FACE_MATCH_THRESHOLD` | Print "no confident match found", exit |
| Search API returns zero results | Empty results list | Print explicit limitation message, exit (log this scenario in `output/run_logs/` for the README's "known limitations" section) |
| RPC not connected | `w3.is_connected()` is False | Print connection error with RPC URL, exit |
| Insufficient testnet funds | Transaction send fails / reverts | Print a clear "fund the wallet" message with the faucet URL |
| Verification mismatch (intentional tamper demo) | Byte comparison fails | This is an expected, desired output path — print TAMPERED clearly, not as an error |

Every run's key artifacts (match result, search result, fingerprint, tx hash,
verification outcome) are written to `output/run_logs/<timestamp>.json` for
reproducibility and for pulling exact values into the README/demo narration.

---

## 8. Testing Strategy

1. **Unit-level, manual**: run `face_match.py` standalone against 3-4 known images
   before wiring anything else.
2. **Unit-level, manual**: run `fingerprint.py` standalone against a fixed test dict,
   confirm the same input always produces the same hash, and any change produces a
   different one.
3. **Integration, dry run #1**: full pipeline, unmodified content → expect VERIFIED.
4. **Integration, dry run #2**: full pipeline, then deliberately mutate content →
   expect TAMPERED.
5. **Final rehearsal**: one uninterrupted run exactly as it will be recorded, timed, no
   code changes after this point.

---

## 9. Deployment / Run Instructions (for the README)

```bash
git clone <repo-url>
cd face-chain-verifier
python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env   # fill in SERPAPI_KEY, PRIVATE_KEY, WALLET_ADDRESS
python app.py --input data/input/scan.jpg
```

---

## 10. Known Technical Limitations (for README, verbatim in spirit)

- Face matching accuracy depends on the underlying model (ArcFace/Facenet via DeepFace)
  and is not evaluated against a large benchmark — this is a small-gallery demo, not a
  production biometric system.
- Reverse-image/search quality is bounded by the third-party API's index and free-tier
  rate limits.
- The blockchain step stores a fingerprint only, by design; it cannot recover or store
  the original content itself.
- No smart contract is used; verification logic lives in the app, not on-chain. This is
  an explicit, disclosed trade-off for a 1-day timeline, not an oversight.
