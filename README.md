# HH Goa 2026 — Face Identification & Blockchain Verification

## Overview
This repository contains the complete production implementation for **HH Goa 2026 Shortlisting Task 3**:
**Consented Face Identification → Reverse Image Search Discovery → Social Post Provenance & Face Verification → Deterministic SHA-256 Evidence Fingerprinting → Polygon Amoy Blockchain Registration & On-Chain Verification (`ContentRegistry.sol`).**

---

## Technical Pipeline Architecture

The application enforces three strictly decoupled verification stages:

1. **Stage 1: Primary Face Identification (Local Gallery)**
   - Input scan is detected via MTCNN with strict face detection (`enforce_detection=True`).
   - Generates a 512-dimensional vector embedding using the **ArcFace** deep learning model.
   - Computes minimum cosine distance ($d = 1.0 - \text{cosine\_similarity}$) against enrolled reference photos in `data/gallery/subject_001/`.
   - Accepts subject identity if $d < \text{FACE\_MATCH\_THRESHOLD}$ (`0.600`).

2. **Stage 2: Web Reverse Search & Candidate Post Verification**
   - **Candidate Discovery**: Sends the query image/anchor dynamically to **SerpApi Google Lens**.
   - **Candidate URL Classification**: Classifies candidates explicitly into `POST` (`linkedin_post`, `instagram_post`, `x_post`, `other_social_post`), `PROFILE`, or `GENERIC_WEBPAGE`. Profile pages (such as `/in/`, `/accounts/`, user handles) are rejected upfront from candidate media extraction.
   - **Instagram Carousel Normalization**: Carousel URLs (`/p/DWmhi_Ik-E1/?img_index=1`, `img_index=2`, `img_index=3`) normalize to the parent post context while evaluating each media item.
   - **Media Provenance Verification**: Rejects profile avatars, account display photos, snippet thumbnails (`encrypted-tbn`, `gstatic`), search anchors, and unrelated page assets (`image_belongs_to_post == True`).
   - **Face Quality Gate**: Before biometric evaluation, candidate faces must satisfy bounding box width $\ge 60\text{px}$, height $\ge 60\text{px}$, and Laplacian blur variance $\ge 20.0$.
   - **ArcFace Match**: Candidate face embeddings are verified against reference gallery embeddings ($d < 0.600$), outputting `matched_face_index`.

3. **Stage 3: Blockchain Integrity Verification (Polygon Amoy)**
   - **Canonical Evidence Fingerprinting**: Builds a deterministic JSON object containing subject ID, platform, exact post URL, candidate image URL, provenance flags, face count, matched face index, cosine distance, threshold, and timestamp, and computes a SHA-256 hash (`0x...`).
   - **Polygon Amoy Registration**: Calls `registerHash(bytes32 contentHash)` on `ContentRegistry.sol` (`0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D` on Polygon Amoy, Chain ID `80002`).
   - **On-Chain Verification & Tamper Detection**: Queries `verifyHash(bytes32 contentHash)` on-chain to confirm tamper-evident proof. Modifying any evidence field alters the SHA-256 fingerprint, returning `NOT FOUND (TAMPERING DETECTED)`.

---

## System Workflow Diagram

```
┌──────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Input Face Scan  ├─────►│  face_match.py          ├─────►│ Verified Subject ID     │
└──────────────────┘      │ ArcFace + MTCNN         │      └────────────┬────────────┘
                          └─────────────────────────┘                   │
                                                                        ▼
┌──────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ SerpApi Lens /   ├─────►│  web_search.py          ├─────►│ Provenance & Face-Match │
│ Social Candidate │      │ Provenance & Quality    │      │ Verified Social Post    │
└──────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                        │
                                                                        ▼
┌───────────────────────────────────────────────────────────┐      ┌─────────────────────────┐
│ Polygon Amoy Testnet (Chain ID: 80002)                    │◄─────┤  fingerprint.py         │
│ Smart Contract: ContentRegistry.sol                       │      │ SHA-256 Evidence Hash   │
│ Address: 0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D        │──────► registerHash / verify   │
└───────────────────────────────────────────────────────────┘      └─────────────────────────┘
```

---

## Biometric Calibration & Threshold Disclaimer

- **Calibrated Threshold (`FACE_MATCH_THRESHOLD = 0.600`)**: ArcFace cosine distance threshold ($d = 1.0 - \text{cosine\_similarity}$) calibrated empirically on the benchmark matrix.
- **Operating Regime**: Calibrated specifically for clear, unoccluded frontal or moderate-pose ($\le 45^\circ$ yaw) photographs under standard lighting. Extreme side profiles ($90^\circ$ yaw) produce high cosine distances ($> 0.750$) and are excluded from the reference calibration gallery.
- **Disclaimer**: `0.600` is **NOT** a universal face-recognition threshold; it is calibrated strictly for the operating regime and reference gallery of this system.

---

## Setup & Installation

1. **Clone & Virtual Environment**:
   ```bash
   git clone https://github.com/mohdasif-v1/hh-goa-blockchain.git
   cd hh-goa-blockchain
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   ```bash
   cp .env.example .env
   ```
   Fill in your local `.env` file (never committed):
   ```ini
   SERPAPI_KEY=your_serpapi_key_here
   RPC_URL=https://rpc-amoy.polygon.technology
   CHAIN_ID=80002
   PRIVATE_KEY=your_private_key_here
   WALLET_ADDRESS=0x7ad7E2A58e41C5c589bDc7Ea1abfcAe0a27DBdA8
   FACE_MATCH_THRESHOLD=0.600
   CONTRACT_ADDRESS=0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D
   ```

---

## Running the Application

### 1. Execute Full End-to-End Pipeline & Tamper Demo
Run the complete pipeline using the target input image and search anchor with tamper-detection beats enabled:
```bash
PYTHONPATH=. ./venv/bin/python3 app.py \
  --input data/gallery/subject_001/photo4.png \
  --search-image-url "https://www.instagram.com/p/DWmhi_Ik-E1/?img_index=1" \
  --tamper-test
```

### 2. Execute Search Diagnostic Only (No Blockchain Write)
Run search discovery and face matching in diagnostic mode:
```bash
PYTHONPATH=. ./venv/bin/python3 app.py \
  --input data/gallery/subject_001/photo4.png \
  --search-image-url "https://www.instagram.com/p/DWmhi_Ik-E1/?img_index=1" \
  --search-only
```

### 3. Run Pytest Test Suite
Execute all unit and integration tests:
```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_pipeline.py
```

### 4. Run Biometric Benchmark Diagnostic
Execute the face matcher calibration benchmark:
```bash
PYTHONPATH=. ./venv/bin/python3 tools/expanded_benchmark.py
```

---

## Known Technical Limitations
- **Biometric Scope**: Small-gallery demonstration using DeepFace/ArcFace; not benchmarked for massive scale identity lookup.
- **Search API Indexing**: Web result retrieval depends on third-party search engine index freshness and SerpApi free-tier rate limits.
- **Off-Chain Content Recovery**: The blockchain stores only a 32-byte cryptographic hash for tamper verification; it does not store raw original media.

---

## Security & Privacy Statement
- `.env` is listed in `.gitignore` and is never committed.
- Private keys and API credentials are kept strictly in local environment variables and are never logged, printed, or exposed in commits.
- Gallery photographs and public post searches represent consented builder data (`subject_001`).

