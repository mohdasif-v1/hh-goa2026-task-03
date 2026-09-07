import os
import sys
import cv2
import numpy as np

# Configure environment before importing deepface/tensorflow
import cli
cli.configure_environment(verbose=False)

import config
import face_match

def compute_quality(image_path: str, bbox: dict) -> tuple[int, int, int, int, float, float, str]:
    """Computes face quality metrics:
    - original image dimensions (W, H)
    - bounding box width (bw)
    - bounding box height (bh)
    - face area percentage of original image
    - estimated blur score (Laplacian variance of facial crop)
    Returns (orig_w, orig_h, bw, bh, face_area_pct, blur_score, quality_status).
    Quality Gate Criteria:
    - Min bbox width >= 60px and Min bbox height >= 60px
    - Blur score >= 20.0
    """
    img = cv2.imread(image_path)
    if img is None:
        return 0, 0, 0, 0, 0.0, 0.0, "REJECTED — IMAGE LOAD FAILED"

    orig_h, orig_w = img.shape[:2]
    bx = max(0, bbox.get("x", 0))
    by = max(0, bbox.get("y", 0))
    bw = bbox.get("w", 0)
    bh = bbox.get("h", 0)

    face_area = bw * bh
    img_area = orig_w * orig_h
    area_pct = (face_area / img_area * 100.0) if img_area > 0 else 0.0

    # Extract crop for blur estimation
    crop_x2 = min(orig_w, bx + bw)
    crop_y2 = min(orig_h, by + bh)
    crop = img[by:crop_y2, bx:crop_x2]

    if crop.size == 0:
        blur_score = 0.0
    else:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    MIN_DIM = 60
    MIN_BLUR = 20.0

    if bw < MIN_DIM or bh < MIN_DIM or blur_score < MIN_BLUR:
        quality_status = "REJECTED — FACE QUALITY TOO LOW"
    else:
        quality_status = "PASSED QUALITY GATE"

    return orig_w, orig_h, bw, bh, area_pct, blur_score, quality_status

def run_expanded_benchmark():
    gallery_dir = "data/expanded_gallery/subject_001"
    demo_dir = "data/demo_input"
    bench_dir = "data/benchmark_images"

    gallery_files = sorted([f for f in os.listdir(gallery_dir) if f.endswith((".jpg", ".png"))])
    gallery_paths = {f: os.path.join(gallery_dir, f) for f in gallery_files}

    demo_file = "demo_subject_001.jpg"
    demo_path = os.path.join(demo_dir, demo_file)

    other_files = sorted([f for f in os.listdir(bench_dir) if f.startswith("other") and f.endswith((".jpg", ".png"))])
    other_paths = {f: os.path.join(bench_dir, f) for f in other_files}

    x_file = "x_candidate.jpg"
    x_path = os.path.join(bench_dir, x_file)

    print("\n" + "=" * 125)
    print("EXPANDED FACE MATCHER BENCHMARK & QUALITY GATE DIAGNOSTICS")
    print("Model: ArcFace | Detector: MTCNN | Current Config Threshold: 0.600")
    print("=" * 125)

    same_person_dists = []
    different_person_dists = []
    demo_input_dists = []
    false_x_dists = []

    print(f"\n{'PAIR / CATEGORY':<35} {'SAME?':<7} {'FACE_IDX':<9} {'BBOX_W':<7} {'BBOX_H':<7} {'AREA_%':<8} {'BLUR_SCORE':<11} {'QUALITY_STATUS':<32} {'DIST':<8} {'DECISION':<8}")
    print("-" * 140)

    # 1. SAME PERSON: Pairwise across gallery images
    g_keys = list(gallery_paths.keys())
    for i in range(len(g_keys)):
        for j in range(i + 1, len(g_keys)):
            r_name = g_keys[i]
            c_name = g_keys[j]
            r_path = gallery_paths[r_name]
            c_path = gallery_paths[c_name]

            ref_emb = face_match.embed_face(r_path)
            c_faces = face_match.extract_all_faces(c_path)
            c_f = c_faces[0]

            ow, oh, bw, bh, apct, bscore, qstat = compute_quality(c_path, c_f["facial_area"])
            dist = face_match.cosine_distance(ref_emb, c_f["embedding"])
            same_person_dists.append(dist)

            decision = "MATCH" if (dist < config.FACE_MATCH_THRESHOLD and qstat == "PASSED QUALITY GATE") else ("REJECT" if qstat == "PASSED QUALITY GATE" else "REJECT_QUALITY")
            pair_lbl = f"{r_name} <-> {c_name}"

            print(f"{pair_lbl:<35} {'YES':<7} {0:<9} {bw:<7} {bh:<7} {apct:<8.2f} {bscore:<11.1f} {qstat:<32} {dist:<8.4f} {decision:<8}")

    # 2. DIFFERENT PERSON: Gallery images vs 10 Unrelated People
    for g_name, g_path in gallery_paths.items():
        ref_emb = face_match.embed_face(g_path)
        for o_name, o_path in other_paths.items():
            try:
                c_faces = face_match.extract_all_faces(o_path)
                for idx, c_f in enumerate(c_faces):
                    ow, oh, bw, bh, apct, bscore, qstat = compute_quality(o_path, c_f["facial_area"])
                    dist = face_match.cosine_distance(ref_emb, c_f["embedding"])
                    different_person_dists.append(dist)

                    decision = "MATCH" if (dist < config.FACE_MATCH_THRESHOLD and qstat == "PASSED QUALITY GATE") else "REJECT"
                    pair_lbl = f"{g_name} <-> {o_name}"
                    print(f"{pair_lbl:<35} {'NO':<7} {idx:<9} {bw:<7} {bh:<7} {apct:<8.2f} {bscore:<11.1f} {qstat:<32} {dist:<8.4f} {decision:<8}")
            except Exception:
                pass

    # 3. DEMO INPUT: Separate demo photo vs gallery images
    demo_faces = face_match.extract_all_faces(demo_path)
    demo_f = demo_faces[0]
    for g_name, g_path in gallery_paths.items():
        ref_emb = face_match.embed_face(g_path)
        ow, oh, bw, bh, apct, bscore, qstat = compute_quality(demo_path, demo_f["facial_area"])
        dist = face_match.cosine_distance(ref_emb, demo_f["embedding"])
        demo_input_dists.append(dist)

        decision = "MATCH" if (dist < config.FACE_MATCH_THRESHOLD and qstat == "PASSED QUALITY GATE") else "REJECT"
        pair_lbl = f"DEMO({demo_file}) <-> {g_name}"
        print(f"{pair_lbl:<35} {'YES':<7} {0:<9} {bw:<7} {bh:<7} {apct:<8.2f} {bscore:<11.1f} {qstat:<32} {dist:<8.4f} {decision:<8}")

    # 4. FALSE X CANDIDATE: X candidate faces vs gallery images
    x_faces = face_match.extract_all_faces(x_path)
    for g_name, g_path in gallery_paths.items():
        ref_emb = face_match.embed_face(g_path)
        for idx, x_f in enumerate(x_faces):
            ow, oh, bw, bh, apct, bscore, qstat = compute_quality(x_path, x_f["facial_area"])
            dist = face_match.cosine_distance(ref_emb, x_f["embedding"])
            false_x_dists.append(dist)

            decision = "MATCH" if (dist < config.FACE_MATCH_THRESHOLD and qstat == "PASSED QUALITY GATE") else ("REJECT (QUAL)" if qstat != "PASSED QUALITY GATE" else "REJECT")
            pair_lbl = f"FALSE_X <-> {g_name}"
            print(f"{pair_lbl:<35} {'NO':<7} {idx:<9} {bw:<7} {bh:<7} {apct:<8.2f} {bscore:<11.1f} {qstat:<32} {dist:<8.4f} {decision:<8}")

    print("-" * 140)

    print("\n" + "=" * 60)
    print("STATISTICAL SUMMARY & DISTRIBUTIONS")
    print("=" * 60)

    def print_stats(name, dist_list):
        if dist_list:
            arr = np.array(dist_list)
            print(f"{name:<30}: Count={len(arr):<3} Min={np.min(arr):.4f}  Max={np.max(arr):.4f}  Mean={np.mean(arr):.4f}")
        else:
            print(f"{name:<30}: N/A")

    print_stats("Same-Person (Gallery Pairs)", same_person_dists)
    print_stats("Demo Input vs Gallery", demo_input_dists)
    print_stats("Different-Person (10 People)", different_person_dists)
    print_stats("False X Candidate Faces", false_x_dists)

    print("-" * 60)
    print(f"Current Config Threshold      : {config.FACE_MATCH_THRESHOLD:.3f}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    run_expanded_benchmark()
