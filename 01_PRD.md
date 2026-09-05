# Product Requirements Document (PRD)
## Face → Web → Blockchain Verification Pipeline
### HH Goa 2026 — Shortlisting Task 3

---

## 1. Overview

### 1.1 Problem Statement
Digital content (photos, posts, claims) can be copied, altered, or misattributed with no
easy way for a third party to confirm "this is the original, unaltered thing I found."
This project builds a pipeline that takes a face scan, finds a genuine matching piece of
public content about that identity on the web, and produces a cryptographically
verifiable, tamper-evident record of that content on a public blockchain — so anyone can
later re-check that the content hasn't been altered since it was discovered.

### 1.2 Product Vision
A single-command CLI tool that demonstrates, end-to-end and live, the chain:
**biometric match (consented) → real-time web discovery → cryptographic fingerprinting →
public, immutable verification.** The product is a technical proof-of-concept for a
hackathon shortlisting round, not a production identity system.

### 1.3 Why This Matters (framing for judges)
The interesting technical claim isn't "we can find someone's face online" — that's a
solved, ethically fraught problem this project deliberately avoids. The interesting claim
is: **once content is found, can we make tampering with it detectable, permanently,
using nothing but a public ledger and a hash function?** That's the part worth building
well.

---

## 2. Ethical Scope & Guardrails (binding constraints, not suggestions)

| Constraint | Reason | How it's enforced in the product |
|---|---|---|
| The face gallery contains only the builder's own, self-enrolled photos | Avoids biometric identification of third parties | `data/gallery/` is populated manually by the builder before any run; no code path adds unknown faces |
| The "web search" step looks up content the builder has already published and consented to be found | Avoids doxxing / non-consensual identification | The search query is derived from a pre-written enrollment record (`search_terms`, `search_image_url`) that the builder authored themselves |
| The demo never claims to identify an unknown/unconsented person | Matches the task's own safety intent | README states this explicitly; spoken/on-screen framing in the recording repeats it |
| Only a hash/fingerprint of discovered content is put on-chain, never raw personal content | Minimizes on-chain exposure of personal data | `fingerprint.py` hashes before anything touches `chain.py` |

Any deviation from these four rows is out of scope for this build, full stop.

---

## 3. Goals and Non-Goals

### 3.1 Goals
1. Demonstrate a believable, working face-detection-and-matching step.
2. Demonstrate a **genuine, live** web/reverse-image search call — not a hardcoded
   result — that returns a real post about the enrolled (consented) identity.
3. Demonstrate a real cryptographic fingerprint of that discovered content.
4. Demonstrate writing that fingerprint to a public blockchain testnet and later
   re-verifying it — including a moment where tampering is deliberately introduced and
   caught.
5. Ship a clean GitHub repo + README that a judge can read in under 3 minutes and
   understand exactly what was built, how to run it, and what its limits are.
6. Produce one unedited screen recording showing the full pipeline running start to
   finish, matching the task's own example CLI output style.

### 3.2 Non-Goals (explicitly excluded from this build)
- Identifying any person other than the builder.
- Any smart contract deployment (raw transaction data field is used instead — see TRD).
- A hosted website or frontend UI of any kind (task explicitly says none is required).
- Batch processing of multiple identities.
- Production-grade security, key management, or scalability.
- Support for video input, only static images.
- Any attempt to defeat or circumvent a search provider's terms of service.

---

## 4. Users & Personas

| Persona | Need | How the product serves them |
|---|---|---|
| Hackathon judge (primary) | Quickly assess technical depth and rubric alignment | Clear README, rubric-mapped success criteria (Section 6), one clean recording |
| Builder (secondary) | A reusable personal proof-of-concept and a portfolio artifact | Clean repo structure, documented limitations, honest scope |

---

## 5. User Stories

1. *As a judge*, I want to watch a single recording and see a face go in and a
   blockchain-verified result come out, so I can assess the full pipeline without
   reading code first.
2. *As a judge*, I want to see the web search step actually execute at runtime (not a
   pasted-in result), so I can trust the "genuine search" requirement was met.
3. *As a judge*, I want to see what happens when the discovered content is altered after
   the fact, so I can confirm the blockchain step is doing real verification work, not
   just storing data decoratively.
4. *As the builder*, I want a flat, understandable repo structure so I can build this
   solo in one day without architecture overhead I won't use again.
5. *As the builder*, I want the README to proactively state limitations and ethical
   framing, so the submission is defensible under judge scrutiny without needing to
   explain it live.

---

## 6. Functional Requirements (mapped to the task's technical requirements)

### FR-1: Face Identification
- **Input**: a static image file (the "face scan")
- **Behavior**: detect a face in the image, generate a numeric embedding, compare
  against a small local gallery of pre-enrolled photos, return the best match and a
  similarity/confidence score
- **Acceptance criteria**:
  - Running the same enrolled subject's photo returns a confidently correct match
    (similarity above a defined threshold, e.g. >0.6 cosine similarity depending on
    model)
  - Running an unrelated face image does not falsely match the enrolled subject
    (demonstrate this once, briefly, in testing — doesn't need to be in the final
    recording but should be verified)
  - Confidence score is printed, not just a boolean match/no-match

### FR-2: Web / Social Media Search
- **Input**: the matched identity's approved search identifier (an image URL and/or
  text search terms from the enrollment record)
- **Behavior**: call a real search/reverse-image API at runtime, retrieve real results,
  programmatically select the best matching post
- **Acceptance criteria**:
  - The API call happens live during the run (visible via a printed raw response
    excerpt or log entry, at least once during development, for credibility)
  - The result URL is not hardcoded anywhere in the codebase
  - The selected result genuinely relates to the enrolled subject (a real, findable
    piece of public content the builder published themselves)

### FR-3: Blockchain Verification
- **Input**: a canonical representation of the discovered content (URL, caption/title,
  timestamp, and image hash if applicable)
- **Behavior**: SHA-256 the canonical representation, write that fingerprint into a
  transaction on a public testnet, later re-fetch that transaction and compare a
  freshly-recomputed fingerprint against it
- **Acceptance criteria**:
  - A real transaction hash is produced and shown, resolvable on a public block
    explorer
  - Re-verification against unmodified content prints VERIFIED
  - Re-verification against deliberately altered content prints TAMPERED /
    MISMATCH — this specific negative-case demonstration is required, not optional,
    because it's the clearest proof the verification step has teeth

### FR-4: No Website
- The entire experience is a CLI application. No requirement or acceptance criteria
  involve a browser-facing UI.

### FR-5: Repository & Documentation
- **Acceptance criteria**:
  - Public (or judge-accessible) GitHub repo with full source
  - README contains: project description, ethical framing paragraph, setup/run
    instructions, which blockchain and why, known limitations
  - `.env.example` present; no real secrets committed

### FR-6: Screen Recording
- **Acceptance criteria**:
  - Single take, 3–7 minutes is a reasonable target (task doesn't hard-require this
    length but it mirrors the sibling task's guidance and is a sane pacing target)
  - Shows: input scan → face match with confidence → live search executing → post
    found → fingerprint generated → blockchain transaction sent → explorer link
    resolvable → verification against unmodified content → verification against
    tampered content

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Reliability | The full pipeline must run start-to-finish without manual intervention once triggered, aside from confirming API keys/wallet funding beforehand |
| Reproducibility | A fresh clone + documented setup steps should let a judge run it themselves if they choose to (not required, but strengthens the submission) |
| Cost | Entire build must run on free tiers only (no budget) |
| Time | Must be buildable solo within one day (~12 working hours) |
| Transparency | Every external call (search API, blockchain RPC) should be easy to spot in logs/output — nothing should look "faked" even by accident |
| Security (scoped to demo) | No real personal secrets or production wallets used; throwaway testnet keypair only |

---

## 8. Success Metrics (rubric alignment)

Although this task doesn't publish its own point-weighted rubric (unlike the sibling AI
Teacher task), it shares the same shortlisting program, so the same judging instincts
apply: **does this demonstrate genuine, live technical work, or does it look
pre-baked?** The product's success is measured by:

1. Every one of the task's 5 technical/submission requirements is met, verifiably, on
   camera.
2. The tamper-detection moment is present and clearly shown — this is the single
   highest-signal proof of "genuine verification" versus "decorative blockchain use."
3. The README's ethical framing pre-empts the most obvious judge concern (biometric
   identification of strangers) before it's even raised.
4. Nothing in the recording requires the judge to take the builder's word for
   something that could instead be shown on screen (e.g., show the explorer link
   loading, don't just say "it's on the blockchain").

---

## 9. Assumptions

- The builder has at least one already-publicly-indexed photo of themselves online
  (GitHub avatar, LinkedIn, personal site, etc.) to use as the search anchor.
- A SerpApi (or equivalent) free-tier account can be created same-day.
- A Polygon Amoy testnet faucet will fund a throwaway wallet within the working day
  (this is the single largest external-dependency risk — start it first).
- Python 3.11 and pip are available in the build environment.

## 10. Risks (product-level; see TRD for technical mitigations)

| Risk | Impact | Likelihood | Owner action |
|---|---|---|---|
| Faucet delay | High (blocks Blockchain requirement entirely) | Medium | Request funds in the first 10 minutes of the day |
| Search API returns no indexed match | High (blocks Web Search requirement) | Low–Medium if using an already-indexed photo | Use a photo published well before today |
| Face library install friction eats hours | Medium | Medium | Time-box the install to 30 min, fallback library pre-decided |
| Recording captures a flaky run | Medium | Low if a dry run is done first | Do a full dry run before the final recording take |

## 11. Glossary
- **Fingerprint**: a SHA-256 hash of a canonical JSON representation of discovered content.
- **Testnet**: a blockchain network used for testing, with no real monetary value.
- **Raw transaction data field**: the arbitrary-data payload every Ethereum-compatible
  transaction can carry, usable to store a hash without deploying a smart contract.
- **Enrollment record**: a local JSON file describing a consented test subject and their
  approved search identifiers, authored by the builder before any run.
