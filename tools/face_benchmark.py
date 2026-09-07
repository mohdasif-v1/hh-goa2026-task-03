import os
import sys
import numpy as np

# Configure environment before importing deepface/tensorflow
import cli
cli.configure_environment(verbose=False)

import config
import face_match

def run_benchmark():
    gallery_dir = "data/gallery/subject_001"
    bench_dir = "data/benchmark_images"

    photos = {
        "photo4": os.path.join(gallery_dir, "photo4.png"),
        "photo5": os.path.join(gallery_dir, "photo5.png")
    }

    others = {
        "other1": os.path.join(bench_dir, "other1.jpg"),
        "other2": os.path.join(bench_dir, "other2.jpg"),
        "other3": os.path.join(bench_dir, "other3.jpg")
    }

    x_cand = {"x_candidate": os.path.join(bench_dir, "x_candidate.jpg")}

    test_matrix = [
        # SAME PERSON
        ("SAME_PERSON", "photo4", "photo5", photos["photo4"], photos["photo5"], True),
        # DIFFERENT PERSON
        ("DIFFERENT", "photo4", "other1", photos["photo4"], others["other1"], False),
        ("DIFFERENT", "photo4", "other2", photos["photo4"], others["other2"], False),
        ("DIFFERENT", "photo4", "other3", photos["photo4"], others["other3"], False),
        ("DIFFERENT", "photo5", "other1", photos["photo5"], others["other1"], False),
        ("DIFFERENT", "photo5", "other2", photos["photo5"], others["other2"], False),
        # FALSE POSITIVE X CANDIDATE
        ("FALSE_POSITIVE", "photo4", "x_candidate", photos["photo4"], x_cand["x_candidate"], False),
        ("FALSE_POSITIVE", "photo5", "x_candidate", photos["photo5"], x_cand["x_candidate"], False),
    ]

    print("\n" + "=" * 105)
    print("FACE MATCHER BENCHMARK (ArcFace + MTCNN, Calibrated Threshold = 0.600)")
    print("=" * 105)

    same_person_dists = []
    different_person_dists = []
    x_candidate_dists = []

    print(f"\n{'TYPE':<15} {'REF':<10} {'CANDIDATE':<12} {'SAME?':<7} {'DETECTED?':<11} {'COUNT':<7} {'BEST_IDX':<10} {'DISTANCE':<10} {'DECISION':<10}")
    print("-" * 105)

    for cat, ref_name, cand_name, ref_path, cand_path, is_same_person in test_matrix:
        # Extract ref embedding
        try:
            ref_emb = face_match.embed_face(ref_path)
        except Exception as e:
            print(f"{cat:<15} {ref_name:<10} {cand_name:<12} {'YES' if is_same_person else 'NO':<7} Error ref face extraction: {e}")
            continue

        # Extract candidate faces
        try:
            cand_faces = face_match.extract_all_faces(cand_path)
            detected = True
            face_count = len(cand_faces)
        except ValueError:
            detected = False
            cand_faces = []
            face_count = 0
        except Exception as e:
            detected = False
            cand_faces = []
            face_count = 0

        if not detected or face_count == 0:
            print(f"{cat:<15} {ref_name:<10} {cand_name:<12} {'YES' if is_same_person else 'NO':<7} {'NO':<11} {0:<7} {'N/A':<10} {'1.0000':<10} {'REJECT':<10}")
            if is_same_person:
                same_person_dists.append(1.0)
            elif cat == "FALSE_POSITIVE":
                x_candidate_dists.append(1.0)
            else:
                different_person_dists.append(1.0)
            continue

        # Match single ref embedding gallery against candidate faces
        single_gallery = {"ref_subject": [ref_emb]}
        match_res = face_match.match_against_gallery(cand_faces, single_gallery)

        dist = match_res.distance
        best_idx = match_res.matched_face_index if match_res.matched_face_index is not None else "N/A"
        decision = "MATCH" if match_res.match else "REJECT"

        print(f"{cat:<15} {ref_name:<10} {cand_name:<12} {'YES' if is_same_person else 'NO':<7} {'YES':<11} {face_count:<7} {str(best_idx):<10} {dist:<10.4f} {decision:<10}")

        if is_same_person:
            same_person_dists.append(dist)
        elif cat == "FALSE_POSITIVE":
            x_candidate_dists.append(dist)
            different_person_dists.append(dist)
        else:
            different_person_dists.append(dist)

    print("-" * 105)

    print("\nSTATISTICAL SUMMARY")
    print("-------------------")
    if same_person_dists:
        print(f"Same-person distances      : Min = {min(same_person_dists):.4f}, Max = {max(same_person_dists):.4f}, Mean = {np.mean(same_person_dists):.4f}")
    if different_person_dists:
        print(f"Different-person distances : Min = {min(different_person_dists):.4f}, Max = {max(different_person_dists):.4f}, Mean = {np.mean(different_person_dists):.4f}")
    if x_candidate_dists:
        print(f"X candidate distances      : Min = {min(x_candidate_dists):.4f}, Max = {max(x_candidate_dists):.4f}, Mean = {np.mean(x_candidate_dists):.4f}")

    print(f"\nCurrent Threshold           : {config.FACE_MATCH_THRESHOLD:.3f}")
    print(f"Model                       : ArcFace")
    print(f"Detector                    : {config.FACE_DETECTOR}")
    print(f"Enforce Detection           : True")
    print("=" * 105 + "\n")

if __name__ == "__main__":
    run_benchmark()
