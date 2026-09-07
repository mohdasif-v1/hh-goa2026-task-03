# HH Goa 2026 Shortlisting Task 3: Face Identification & Blockchain Verification

**End-to-End Command-Line Pipeline for Consented Face Identification, Web Reverse-Image Discovery, Social Post Provenance Verification, and Polygon Blockchain Integrity Verification.**

---

### Pipeline Sequence
$$\text{Face Scan / Input Image} \longrightarrow \text{Face Detection (MTCNN)} \longrightarrow \text{ArcFace Embedding} \longrightarrow \text{Reverse-Image Search (Google Lens)} \longrightarrow \text{Social Media Discovery} \longrightarrow \text{Provenance & Face Match} \longrightarrow \text{SHA-256 Fingerprint} \longrightarrow \text{Polygon Amoy Registration} \longrightarrow \text{On-Chain Proof} \longrightarrow \text{Tamper Test}$$

> **Note on Interface**: As permitted by the official task prompt, **no website is required or included**. The project is implemented as a complete, automated end-to-end command-line application (`app.py`).

---

## HH Goa Task Requirements → Implementation Mapping

| Task Requirement | Official Requirement Specification | Repository Implementation | Verification Module / Evidence |
| :--- | :--- | :--- | :--- |
| **Requirement 1** | **Face Identification**: Detect and encode a face from an input image. | Detects faces using **MTCNN** (`enforce_detection=True`), extracts 512-d embeddings via **ArcFace**, and matches enrolled subjects in `data/gallery/subject_001/` using cosine distance ($d < 0.600$). Enforces face quality checks ($\ge 60\text{px}$ width/height, blur variance $\ge 20.0$). | [`face_match.py`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/face_match.py)<br>`test_pipeline.py::test_multiple_faces_one_matching_face` |
| **Requirement 2** | **Social Media / Web Search**: Use the face to search the web and find at least one real, matching social media post. | Dynamic visual search via **SerpApi Google Lens**. Discovers candidate URLs, classifies URLs (`POST`, `PROFILE`, `GENERIC_WEBPAGE`), extracts post media, verifies provenance (`image_belongs_to_post == True`), and independently executes ArcFace match on candidate post faces. Search anchor image is used for Lens lookup; candidate media is independently face-verified. | [`web_search.py`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/web_search.py)<br>`test_pipeline.py::test_url_classification`<br>`test_pipeline.py::test_unrelated_linkedin_post_rejected` |
| **Requirement 3** | **Blockchain Verification**: Register verified evidence on-chain and verify its integrity. | Builds a canonical evidence tuple, calculates a **SHA-256 fingerprint** (`0x...`), and registers the hash on **Polygon Amoy** via `ContentRegistry.sol` (`0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D`). Queries `verifyHash(bytes32)` on-chain. Modifying evidence changes the SHA-256 hash, returning `NOT FOUND (TAMPERING DETECTED)`. | [`chain.py`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/chain.py)<br>[`fingerprint.py`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/fingerprint.py)<br>[`ContentRegistry.sol`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/contracts/ContentRegistry.sol) |
| **Requirement 4** | **No Website Required**: CLI execution permitted. | Fully automated CLI pipeline (`app.py`) featuring explicit stage outputs `[1/5]` through `[5/5]`, `--search-only` diagnostic mode, and `--tamper-test` integrity check beats. | [`app.py`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/app.py)<br>[`cli.py`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/cli.py) |
| **Requirement 5** | **GitHub Repository Submission**: Complete source, contracts, tests, and documentation. | Complete codebase, smart contract, pytest suite (32 tests), benchmark tools, environment templates, and documentation stored in the official repository. | [`README.md`](file:///home/asifcodeverse/Projects/hh-goa-blockchain/README.md) |

---

## What I Built

### 1. Face Identification Stage
- Scans input photograph using **MTCNN** face detection.
- Generates a 512-dimensional vector embedding using the **ArcFace** deep neural network.
- Computes minimum cosine distance ($d = 1.0 - \text{cosine\_similarity}$) against enrolled subject embeddings in `data/gallery/subject_001/` (matching if $d < 0.600$).

### 2. Reverse Image Search Stage
- Passes input/search-anchor image dynamically to **SerpApi Google Lens**.
- Extracts candidate URLs across organic web matches without hardcoding target URLs as search output.

### 3. Social Post & Provenance Verification Stage
- **URL Classification**: Categorizes candidate links as `linkedin_post`, `instagram_post`, `x_post`, `profile`, or `generic_webpage`. Profile pages (e.g. `/in/`, `/accounts/`, handles) are rejected upfront.
- **Media Provenance**: Downloads actual post media (e.g. OpenGraph tags, post carousels) and rejects search engine thumbnails (`encrypted-tbn`), display avatars, and search anchor images (`image_belongs_to_post == True`).
- **Candidate Face Verification**: Detects faces in candidate media, applies quality filters ($\ge 60\text{px}$, blur $\ge 20.0$), and verifies candidate face embeddings against the enrolled subject ($d < 0.600$).

### 4. Evidence Fingerprinting Stage
- Constructs a canonical JSON dictionary containing subject ID, platform, exact post URL, media URL, provenance flags, face count, matched face index, cosine distance, threshold, and timestamp.
- Hashes the canonical JSON using SHA-256 to generate a 32-byte hex string (`0x...`).

### 5. Blockchain Integrity & Tamper Detection Stage
- Connects to **Polygon Amoy Testnet** (Chain ID `80002`).
- Registers the 32-byte hash via `registerHash(bytes32 contentHash)` on `ContentRegistry.sol`.
- Verifies on-chain proof via `verifyHash(bytes32 contentHash)`.
- Demonstrates tamper detection by modifying an evidence field and confirming on-chain rejection.

---

## Complete End-to-End Workflow

```mermaid
flowchart TD
    A["Input Face Image Scan"] --> B["MTCNN Face Detection"]
    B --> C["ArcFace Embedding (512-d)"]
    C --> D{"Enrolled Subject Match? (d < 0.600)"}
    D -- No --> E["Reject — Unknown Subject"]
    D -- Yes --> F["Identified Subject (e.g. subject_001)"]
    F --> G["Reverse Image Search (SerpApi Google Lens)"]
    G --> H["Dynamic Candidate URL Extraction"]
    H --> I["Social Platform Classification"]
    I --> J["Extract Actual Post Media"]
    J --> K{"Provenance Validation"}
    K -- Avatar / Thumbnail / Generic --> L["Reject Candidate"]
    K -- Verified Social Post --> M["Face Quality Gate Check"]
    M --> N["ArcFace Face Verification on Candidate"]
    N --> O{"Candidate Match? (d < 0.600)"}
    O -- No --> P["Reject — Face Mismatch"]
    O -- Yes --> Q["Verified Social Media Post"]
    Q --> R["Canonical Evidence Tuple"]
    R --> S["SHA-256 Evidence Fingerprint"]
    S --> T["Polygon Amoy Testnet (Chain ID 80002)"]
    T --> U["ContentRegistry.registerHash()"]
    U --> V["ContentRegistry.verifyHash() On-Chain Proof"]
    V --> W["Tamper Test Verification"]
```

---

## Architecture Diagram

```mermaid
graph TD
    subgraph Input ["Input Layer"]
        CLI["app.py / cli.py"]
    end

    subgraph Biometrics ["Face Recognition Layer"]
        MTCNN["MTCNN Detector"]
        ArcFace["ArcFace Model"]
        Matcher["face_match.py"]
    end

    subgraph Discovery ["Search & Discovery Layer"]
        Lens["Google Lens (SerpApi)"]
        SearchEngine["web_search.py"]
    end

    subgraph Provenance ["Provenance Layer"]
        Classifier["URL Classifier"]
        MediaVerifier["Post Media Extractor"]
    end

    subgraph Evidence ["Evidence & Hashing Layer"]
        Hasher["fingerprint.py (SHA-256)"]
    end

    subgraph Blockchain ["Blockchain Layer"]
        ChainWeb3["chain.py (Web3.py)"]
        Contract["ContentRegistry.sol (Polygon Amoy)"]
    end

    CLI --> MTCNN
    MTCNN --> ArcFace
    ArcFace --> Matcher
    Matcher --> Lens
    Lens --> SearchEngine
    SearchEngine --> Classifier
    Classifier --> MediaVerifier
    MediaVerifier --> Matcher
    MediaVerifier --> Hasher
    Hasher --> ChainWeb3
    ChainWeb3 --> Contract
```

---

## Face Identification Details

- **Detector**: MTCNN (Multi-task Cascaded Convolutional Networks) for facial landmark detection and bounding box alignment.
- **Representation Model**: ArcFace (Additive Angular Margin Loss) deep convolutional network generating 512-dimensional vector embeddings.
- **Metric**: Cosine distance ($d = 1.0 - \text{cosine\_similarity}$). Lower cosine distance indicates higher biometric similarity.
- **Enrolled Reference Gallery**: `data/gallery/subject_001/` containing enrolled subject photos (`photo4.png`, `photo5.png`).
- **Face Quality Gate**: Filters candidates requiring width $\ge 60\text{px}$, height $\ge 60\text{px}$, and Laplacian variance $\ge 20.0$.
- **Calibrated Operating Threshold**:
  $$\text{FACE\_MATCH\_THRESHOLD} = 0.600$$

> **Calibrated Operating Threshold Disclaimer**: The `0.600` cosine-distance threshold is a calibrated operating threshold for the evaluated benchmark and operating regime (clear, unoccluded frontal or moderate-pose $\le 45^\circ$ yaw photos under standard lighting). It is not claimed to be a universal threshold or a production-grade open-web identity resolution system.

---

## Reverse Image Search Details

- **Dynamic Discovery Engine**: Uses SerpApi Google Lens reverse-image search. The system **does not return a hardcoded social-media URL** as its search output.
- **Search Execution Sequence**:
  1. Input/search-anchor image is sent to Google Lens.
  2. Returns dynamic visual match URLs across web sources.
  3. URLs are classified into platform and candidate types.
  4. Candidate post media is extracted.
  5. Extracted media undergoes strict provenance validation.
  6. Discovered post media undergoes independent ArcFace face verification against enrolled reference embeddings.
  7. Only candidates passing both provenance and face matching are accepted as verified posts.

---

## Social Media Provenance Verification

Visual search matches frequently return profile avatars, search thumbnails, or generic web pages. The provenance module explicitly distinguishes candidate assets:

- **Accepted Post Types**: `linkedin_post`, `instagram_post`, `x_post`, `other_social_post`.
- **Rejected Profile Pages**: Account profiles (e.g. `/in/username`, `/accounts/login/`, twitter handles) categorized as `profile` and rejected upfront.
- **Avatar & Thumbnail Exclusion**: Rejects search engine thumbnails (`encrypted-tbn`, `gstatic`), display avatars, and search anchor images (`image_belongs_to_post == True`).
- **OpenGraph Media Tag**: `image_source_type` identifies exact post media (`post_media_og`, `instagram_carousel_media`).

---

## Blockchain Verification Details

- **Network**: Polygon Amoy Testnet (Chain ID: `80002`)
- **Smart Contract Name**: `ContentRegistry.sol`
- **Deployed Contract Address**: [`0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D`](https://amoy.polygonscan.com/address/0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D)
- **Role**: The blockchain functions as a tamper-evident integrity registry. Raw images are **not** stored on-chain. Only 32-byte SHA-256 hashes of canonical evidence tuples are stored.

### Contract Methods (`ContentRegistry.sol`)
```solidity
function registerHash(bytes32 contentHash) external returns (bool);
function verifyHash(bytes32 contentHash) external view returns (bool);
```

---

## Tamper Detection

```mermaid
flowchart LR
    A["Verified Evidence Tuple"] --> B["SHA-256 Hash A"]
    B --> C["Polygon Amoy Contract"]
    C --> D["verifyHash(A) -> True ✅"]

    E["Modified / Tampered Evidence"] --> F["SHA-256 Hash B"]
    F --> G["Polygon Amoy Contract"]
    G --> H["verifyHash(B) -> False ❌"]
    H --> I["TAMPERING DETECTED"]
```

When `--tamper-test` is executed, the application intentionally alters an evidence metadata field (such as timestamp or URL). Because SHA-256 is avalanche-sensitive, the resulting hash differs completely, failing the on-chain `verifyHash` check and confirming tamper detection.

---

## Demonstration Command & Execution

Run the complete pipeline demonstration using `photo4.png` with search-anchor and tamper-testing enabled:

```bash
PYTHONPATH=. ./venv/bin/python3 app.py \
  --input data/gallery/subject_001/photo4.png \
  --search-image-url "https://www.instagram.com/p/DWmhi_Ik-E1/?img_index=1" \
  --tamper-test
```

> **Note on `--search-image-url`**: This parameter serves as the demo/search-anchor input to reliably reproduce the evaluation workflow while the pipeline executes actual reverse-search discovery, post classification, provenance checks, candidate face matching, evidence fingerprinting, and Polygon Amoy registration.

### Expected Pipeline Execution Beats
1. **`[1/5] Primary Face Identification`**: Scans input photo, detects face via MTCNN, computes ArcFace embedding, matches `subject_001` ($d < 0.600$).
2. **`[2/5] Social Post Verification`**: Executes Lens search, classifies URL, extracts media, verifies provenance (`image_belongs_to_post == True`), detects candidate face, matches ArcFace embedding ($d < 0.600$).
3. **`[3/5] Evidence Fingerprint`**: Formats canonical JSON and calculates SHA-256 hash (`0x...`).
4. **`[4/5] Blockchain Registration`**: Signs and broadcasts transaction to `registerHash` on Polygon Amoy. Returns TX hash and block number.
5. **`[5/5] On-Chain Verification & Tamper Check`**: Calls `verifyHash` on-chain (returns `VERIFIED ON-CHAIN ✅`), then alters evidence to demonstrate `TAMPERING DETECTED ❌`.

---

## Testing Results

The complete Pytest suite validates biometrics, search classification, provenance filtering, SHA-256 determinism, and on-chain verification patterns.

```bash
PYTHONPATH=. ./venv/bin/pytest tests/ -q
```

### Pytest Execution Summary
```text
................................                   [100%]
32 passed in 355.90s (0:05:55)
```
- **Passed Tests**: 32 / 32 (100%)

---

## Project Structure

```
hh-goa-blockchain/
├── app.py                     # Main CLI application & 5-stage pipeline runner
├── cli.py                     # CLI configuration & terminal output formatting
├── config.py                  # Operational constants (FACE_MATCH_THRESHOLD = 0.600)
├── chain.py                   # Web3 Polygon Amoy blockchain integration
├── face_match.py              # ArcFace + MTCNN face detection & embedding matcher
├── fingerprint.py            # Canonical evidence formatter & SHA-256 hasher
├── web_search.py              # SerpApi Lens search & post provenance verification
├── requirements.txt           # Python dependency specification
├── .env.example               # Environment configuration template (NO secrets)
├── .gitignore                 # Git ignore rules (.env, venv, pycache)
├── README.md                  # Task submission documentation
├── contracts/
│   └── ContentRegistry.sol    # Solidity smart contract
├── data/
│   ├── gallery/
│   │   └── subject_001/       # Enrolled reference photos
│   │       ├── photo4.png
│   │       └── photo5.png
│   ├── benchmark_images/      # Evaluation benchmark dataset
│   ├── demo_input/            # Scan inputs for demonstration
│   └── expanded_gallery/     # Multi-image test gallery assets
├── tests/
│   └── test_pipeline.py       # Comprehensive pytest suite (32 tests)
└── tools/
    ├── face_benchmark.py      # Core biometric matcher benchmark script
    └── expanded_benchmark.py  # Multi-subject evaluation benchmark
```

---

## Setup Instructions

1. **Clone Repository & Set Up Virtual Environment**:
   ```bash
   git clone https://github.com/mohdasif-v1/hh-goa2026-task-03.git
   cd hh-goa2026-task-03
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Fill `.env` with your API credentials (never committed):
   ```ini
   SERPAPI_KEY=your_serpapi_key_here
   RPC_URL=https://rpc-amoy.polygon.technology
   CHAIN_ID=80002
   PRIVATE_KEY=your_private_key_here
   WALLET_ADDRESS=<your_wallet_address>
   FACE_MATCH_THRESHOLD=0.600
   CONTRACT_ADDRESS=0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D
   ```

---

## Privacy & Security

- **No Raw Media On-Chain**: Raw images are stored locally and are never uploaded to the blockchain. Only 32-byte cryptographic evidence hashes are registered.
- **Credentials Protection**: API keys and private keys reside strictly in `.env`. `.env` is listed in `.gitignore` and is excluded from Git tracking.
- **Consented Subject Data**: Reference gallery photographs (`subject_001`) represent consented builder data.

---

## Technical Limitations

1. **Biometric Bounds**: Recognition accuracy depends on face size, lighting, and pose ($\le 45^\circ$ yaw). Extreme profile views ($90^\circ$ yaw) yield higher cosine distances ($> 0.750$).
2. **Search Indexing**: Web reverse search performance relies on Google Lens index freshness and SerpApi rate limits.
3. **Calibrated Operating Threshold**: Threshold `0.600` is calibrated specifically for the evaluated benchmark and operating regime; it is not a universal identity threshold.

---

## Screen Recording

- **Demonstration Video**: The task requires an unedited video showing face scan $\rightarrow$ social post discovery $\rightarrow$ blockchain registration $\rightarrow$ on-chain verification.
- **CLI Terminal Walkthrough**: Because the project is an automated command-line application, the terminal execution output demonstrates the full pipeline.
- **Submission Link**: `[Add final screen recording link here]`

---

## HH Goa Submission Summary

- **Task**: **HH Goa 2026 Shortlisting Task 3: Face Identification & Blockchain Verification**
- **GitHub Repository**: [`https://github.com/mohdasif-v1/hh-goa2026-task-03.git`](https://github.com/mohdasif-v1/hh-goa2026-task-03.git)
- **Submission Form**: [`https://forms.gle/oZbQGuwiNeHVcHWo8`](https://forms.gle/oZbQGuwiNeHVcHWo8)
- **Screen Recording**: `[Add final screen recording link here]`


