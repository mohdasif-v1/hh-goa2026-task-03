# HH Goa 2026 — Face Identification & Blockchain Verification

## Overview
This project implements an end-to-end, live cryptographic content verification pipeline for **HH Goa 2026 Shortlisting Task 3**:
**Consented Face Match → Genuine Web Search → SHA-256 Canonical Fingerprint → Smart Contract Registration (`ContentRegistry.sol` on Polygon Amoy) → On-Chain Verification & Tamper Detection.**

---

## Ethical Scope & Guardrails (binding constraints)
- **Consented Gallery Only**: The face gallery contains only self-enrolled photos of the consented builder (`data/gallery/subject_001`). No code path identifies unconsented third parties.
- **Pre-Approved Web Anchor**: Web search resolves content the builder published themselves (`search_image_url`, `search_terms` in `data/enrollment.json`).
- **Privacy-Preserving On-Chain Footprint**: Only a 32-byte cryptographic SHA-256 hash touches the public blockchain; no raw personal data or images are exposed on-chain.

---

## Architecture
```
┌──────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Input Face Scan  ├─────►│  face_match.py          ├─────►│ Match Confidence Score  │
└──────────────────┘      │ DeepFace / ArcFace      │      └────────────┬────────────┘
                          └─────────────────────────┘                   │
                                                                        ▼
┌──────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ SerpApi Search   ├─────►│  web_search.py          ├─────►│ Discovered Web Result   │
│ Live HTTP Call   │      │ Lens / Google Engine    │      └────────────┬────────────┘
└──────────────────┘      └─────────────────────────┘                   │
                                                                        ▼
                                  ┌─────────────────────────┐      ┌─────────────────────────┐
                                  │  fingerprint.py         ├─────►│ Canonical SHA-256 Hash │
                                  │ Canonical JSON → SHA256 │      └────────────┬────────────┘
                                  └─────────────────────────┘                   │
                                                                                ▼
┌───────────────────────────────────────────────────────────┐      ┌─────────────────────────┐
│ Polygon Amoy Testnet (Chain ID: 80002)                    │◄─────┤  chain.py               │
│ Smart Contract: ContentRegistry.sol                       │      │ registerHash(bytes32)   │
│ Address: 0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D        │──────► verifyHash(bytes32)     │
└───────────────────────────────────────────────────────────┘      └─────────────────────────┘
```

---

## Technologies Used
- **Python 3.12**
- **DeepFace & ArcFace**: Face detection and 512-d vector embedding generation
- **SerpApi**: Real-time Google Lens & Google Search execution
- **Web3.py**: Ethereum/Polygon JSON-RPC interaction and transaction signing
- **Solidity 0.8.20**: `ContentRegistry.sol` smart contract storing hashes with block timestamps
- **Polygon Amoy Testnet**: Public EVM testnet (Chain ID `80002`)
- **Rich**: Terminal formatting and UI rendering

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
   RPC_URL=https://polygon-amoy.drpc.org
   CHAIN_ID=80002
   PRIVATE_KEY=your_private_key_here
   WALLET_ADDRESS=0x7ad7E2A58e41C5c589bDc7Ea1abfcAe0a27DBdA8
   FACE_MATCH_THRESHOLD=0.65
   CONTRACT_ADDRESS=0x8e3034CAc8D8b2dFEfD49Efc06787C08fa7eAB7D
   ```

---

## Smart Contract Deployment

To re-deploy `ContentRegistry.sol` to Polygon Amoy using the configured wallet:
```bash
python deploy_contract.py
```
This compiles `contracts/ContentRegistry.sol` with `solc 0.8.20`, deploys it to Polygon Amoy, updates `CONTRACT_ADDRESS` in `.env`, and saves the ABI to `src/blockchain/abi/ContentRegistry.json`.

---

## Running the Application

### 1. End-to-End Pipeline
Run the complete pipeline from face match to on-chain verification:
```bash
python app.py --input data/gallery/subject_001/photo1.jpg
```

### 2. Tamper-Detection Demonstration
Run the pipeline followed by an intentional content mutation beat to demonstrate that altered content fails `verifyHash()` on-chain:
```bash
python app.py --input data/gallery/subject_001/photo1.jpg --tamper-test
```

### 3. Run Test Suite
Execute the automated unit and integration tests:
```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_pipeline.py
```

---

## Why Polygon Amoy & Smart Contract Architecture
- **Public Credibility**: Transactions land on Polygon Amoy testnet (`80002`) and can be verified by any third party on [PolygonScan](https://amoy.polygonscan.com/).
- **Smart Contract Storage**: Unlike raw transaction data fields, `ContentRegistry.sol` maintains a persistent `records` mapping (`bytes32 => uint256`), emitting `HashRegistered` events and exposing a view function `verifyHash(bytes32)`.

---

## Known Technical Limitations
- **Biometric Scope**: Small-gallery demonstration using DeepFace/ArcFace; not benchmarked for massive scale identity lookup.
- **Search API Indexing**: Web result retrieval depends on third-party search engine index freshness and SerpApi free-tier rate limits.
- **Off-Chain Content Recovery**: The blockchain stores only a 32-byte cryptographic hash for tamper verification; it does not store raw original media.

---

## Security Considerations
- `.env` is listed in `.gitignore` and is never committed.
- Private keys and API keys are loaded solely from local environment variables and are never logged, printed, or exposed in commit history.
