import datetime
import os
import re
import tempfile
import requests
import config
import face_match

def build_query(enrollment_record: dict) -> dict:
    """Chooses image-URL-based reverse search if search_image_url is present,
    else falls back to text search using search_terms.
    """
    if enrollment_record.get("search_image_url"):
        return {
            "engine": "google_lens",
            "url": enrollment_record["search_image_url"],
            "api_key": config.SERPAPI_KEY
        }
    else:
        terms = enrollment_record.get("search_terms", [])
        query_str = terms[0] if terms else enrollment_record.get("display_name", "")
        return {
            "engine": "google",
            "q": query_str,
            "api_key": config.SERPAPI_KEY
        }

def classify_social_url(url: str) -> tuple[str, str]:
    """Classifies a URL into candidate_platform and candidate_type.
    Returns (candidate_platform, candidate_type).
    Explicit Candidate Types:
    - POST: 'linkedin_post', 'instagram_post', 'x_post', 'other_social_post'
    - PROFILE: 'profile' (e.g. /in/, /company/, /accounts/, /profile/, twitter/github user profiles)
    - UNKNOWN / GENERIC: 'generic_webpage'
    Only POST types are eligible for candidate media extraction and face verification.
    """
    if not url:
        return "N/A", "generic_webpage"

    u = url.lower()
    
    # LinkedIn
    if "linkedin.com" in u:
        if "/posts/" in u or "/activity/" in u or "/feed/update/" in u or "/pulse/" in u:
            return "LinkedIn", "linkedin_post"
        elif "/in/" in u or "/company/" in u or "/pub/" in u or "/profile/" in u:
            return "LinkedIn", "profile"
        return "LinkedIn", "profile"

    # Instagram
    if "instagram.com" in u:
        if "/p/" in u or "/reel/" in u or "/tv/" in u:
            return "Instagram", "instagram_post"
        elif "/accounts/" in u or "/profile/" in u:
            return "Instagram", "profile"
        # Standard Instagram profile handle check (e.g. instagram.com/username)
        parts = [p for p in u.split("instagram.com/")[-1].split("?")[0].split("/") if p]
        if len(parts) == 1 and parts[0] not in ["explore", "reels", "direct"]:
            return "Instagram", "profile"
        return "Instagram", "profile"

    # X / Twitter
    if "x.com" in u or "twitter.com" in u:
        if "/status/" in u:
            return "X / Twitter", "x_post"
        elif "/status" not in u:
            return "X / Twitter", "profile"
        return "X / Twitter", "profile"

    # GitHub
    if "github.com" in u:
        parts = [p for p in u.split("github.com/")[-1].split("?")[0].split("/") if p]
        if len(parts) >= 2 and parts[1] not in ["followers", "following", "stars", "tab", "repositories"]:
            return "GitHub", "other_social_post"  # Repository/Release/Discussions post
        return "GitHub", "profile"

    # Facebook
    if "facebook.com" in u:
        if "/posts/" in u or "/photos/" in u or "/permalink.php" in u or "/watch/" in u:
            return "Facebook", "other_social_post"
        return "Facebook", "profile"

    # YouTube
    if "youtube.com" in u or "youtu.be" in u:
        if "/watch" in u or "/shorts/" in u or "youtu.be/" in u:
            return "YouTube", "other_social_post"
        return "YouTube", "profile"

    return "Web", "generic_webpage"


def run_search(query: dict, enrollment_record: dict = None) -> list[dict]:
    """Executes live SerpApi call(s) and extracts candidates with all available image URLs."""
    url = "https://serpapi.com/search"
    results = []

    # 1. Google Lens search if query engine is google_lens
    if query.get("engine") == "google_lens":
        resp = requests.get(url, params=query, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_matches = data.get("visual_matches", [])
        for item in raw_matches:
            link_url = item.get("link") or item.get("source") or ""
            platform, cand_type = classify_social_url(link_url)
            
            img_urls = []
            for k in ["thumbnail", "image", "original"]:
                v = item.get(k)
                if v and isinstance(v, str) and v.startswith("http"):
                    img_urls.append(v)
            primary_img = img_urls[0] if img_urls else None

            results.append({
                "url": link_url,
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet") or item.get("source") or "",
                "source": item.get("source", ""),
                "image_url": primary_img,
                "all_image_urls": img_urls,
                "candidate_platform": platform,
                "candidate_type": cand_type,
                "raw_item": item
            })

    # 2. Organic Google search targeting social sites if enrollment_record provides search terms
    if enrollment_record and enrollment_record.get("display_name"):
        disp_name = enrollment_record["display_name"]
        site_queries = [
            f'"{disp_name}" site:linkedin.com/posts/',
            f'"{disp_name}" site:instagram.com/p/',
            f'"{disp_name}" site:instagram.com/reel/',
            f'"{disp_name}" site:x.com/*/status/',
            f'"{disp_name}" site:twitter.com/*/status/'
        ]
        for sq in site_queries:
            org_query = {
                "engine": "google",
                "q": sq,
                "api_key": config.SERPAPI_KEY
            }
            try:
                r = requests.get(url, params=org_query, timeout=10)
                if r.status_code == 200:
                    org_data = r.json()
                    org_matches = org_data.get("organic_results", [])
                    for item in org_matches:
                        link_url = item.get("link", "")
                        platform, cand_type = classify_social_url(link_url)
                        
                        img_urls = []
                        pagemap = item.get("pagemap", {})
                        if "cse_image" in pagemap and isinstance(pagemap["cse_image"], list):
                            for ci in pagemap["cse_image"]:
                                if ci.get("src") and ci.get("src").startswith("http"):
                                    img_urls.append(ci.get("src"))
                        if "og_image" in pagemap and isinstance(pagemap["og_image"], list):
                            for ogi in pagemap["og_image"]:
                                if ogi.get("src") and ogi.get("src").startswith("http"):
                                    img_urls.append(ogi.get("src"))

                        # Fallback: if SerpApi provided no image URL for social post link, attempt to extract og:image/twitter:image from public candidate page
                        if not img_urls and cand_type in ["linkedin_post", "instagram_post", "x_post", "other_social"]:
                            page_img = fetch_page_preview_image(link_url)
                            if page_img:
                                img_urls.append(page_img)

                        primary_img = img_urls[0] if img_urls else None
                        results.append({
                            "url": link_url,
                            "title": item.get("title", "No Title"),
                            "snippet": item.get("snippet", ""),
                            "source": item.get("displayed_link", ""),
                            "image_url": primary_img,
                            "all_image_urls": img_urls,
                            "candidate_platform": platform,
                            "candidate_type": cand_type,
                            "raw_item": item
                        })
            except Exception:
                pass

    return results

def is_profile_avatar_url(image_url: str) -> bool:
    """Checks if an image URL is a profile avatar, account display photo, or user icon rather than post content media.
    Filters out profile photos (e.g. licdn profile-displayphoto, avatar images, author profile pictures).
    """
    if not image_url:
        return True
    u = image_url.lower()
    avatar_patterns = [
        "profile-displayphoto",
        "profile-displaybackgroundimage",
        "profile-avatar",
        "/avatar/",
        "_avatar_",
        "profile_images",
        "profile-photo",
        "profile_photo",
        "/profile/",
        "user_avatar",
        "default_avatar",
        "account_photo",
        "account-photo",
        "user-photo",
        "author_photo"
    ]
    for p in avatar_patterns:
        if p in u:
            return True
    return False

def is_search_thumbnail_url(image_url: str) -> bool:
    """Checks if an image URL is a generic search engine snippet thumbnail or placeholder image."""
    if not image_url:
        return False
    u = image_url.lower()
    thumb_patterns = [
        "encrypted-tbn",
        "gstatic.com/images",
        "serpapi.com/searches",
        "favicon",
        "placeholder",
        "generic_thumbnail",
        "default_thumb"
    ]
    for p in thumb_patterns:
        if p in u:
            return True
    return False

def fetch_page_post_media_image(url: str) -> tuple[str | None, str]:
    """Fetches public HTML page for a social post and extracts images strictly belonging to the post content.
    Excludes profile/avatar images and search thumbnails.
    Returns (image_url, image_source_type).
    image_source_type: 'post_media_og' | 'post_inline_media' | 'none'
    """
    if not url or not url.startswith("http"):
        return None, "none"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        if r.status_code != 200:
            return None, "none"
        html = r.text

        # Meta tag extraction handling any attribute order
        meta_matches = re.findall(r'<meta\s+[^>]*?(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*?content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        meta_matches += re.findall(r'<meta\s+[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\'](?:og:image|twitter:image)["\']', html, re.IGNORECASE)
        
        for raw_img in meta_matches:
            img_url = raw_img.replace("&amp;", "&")
            if img_url.startswith("http") and not is_profile_avatar_url(img_url) and not is_search_thumbnail_url(img_url):
                return img_url, "post_media_og"

        # Next check feedshare / post image tags in HTML body for LinkedIn/other social
        feed_matches = re.findall(r'https://media\.licdn\.com/dms/image/[^\s\"\'\`>]+feedshare[^\s\"\'\`>]+', html)
        for fm in feed_matches:
            img_url = fm.replace("&amp;", "&")
            if img_url.startswith("http") and not is_profile_avatar_url(img_url) and not is_search_thumbnail_url(img_url):
                return img_url, "post_inline_media"

    except Exception:
        pass
    return None, "none"

def run_search(query: dict, enrollment_record: dict = None) -> list[dict]:
    """Executes live SerpApi call(s) and extracts candidates with strictly provenance-filtered post images."""
    url = "https://serpapi.com/search"
    results = []

    # 1. Google Lens search if query engine is google_lens
    if query.get("engine") == "google_lens":
        resp = requests.get(url, params=query, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_matches = data.get("visual_matches", [])
        for item in raw_matches:
            link_url = item.get("link") or item.get("source") or ""
            platform, cand_type = classify_social_url(link_url)
            
            img_urls = []
            img_source_types = []
            for k in ["original", "image", "thumbnail"]:
                v = item.get(k)
                if v and isinstance(v, str) and v.startswith("http"):
                    if not is_profile_avatar_url(v) and not is_search_thumbnail_url(v):
                        img_urls.append(v)
                        img_source_types.append("serpapi_visual_match")

            # Fallback for visual matches on social post links if no post image came directly from SerpApi
            if not img_urls and cand_type in ["linkedin_post", "instagram_post", "x_post", "other_social_post"]:
                post_img, stype = fetch_page_post_media_image(link_url)
                if post_img:
                    img_urls.append(post_img)
                    img_source_types.append(stype)

            primary_img = img_urls[0] if img_urls else None
            results.append({
                "url": link_url,
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet") or item.get("source") or "",
                "source": item.get("source", ""),
                "image_url": primary_img,
                "all_image_urls": img_urls,
                "image_source_types": img_source_types,
                "candidate_platform": platform,
                "candidate_type": cand_type,
                "raw_item": item
            })

    # 2. Organic Google search targeting social sites if enrollment_record provides search terms
    if enrollment_record and enrollment_record.get("display_name"):
        disp_name = enrollment_record["display_name"]
        site_queries = [
            f'"{disp_name}" site:linkedin.com/posts/',
            f'"{disp_name}" site:instagram.com/p/',
            f'"{disp_name}" site:instagram.com/reel/',
            f'"{disp_name}" site:x.com/*/status/',
            f'"{disp_name}" site:twitter.com/*/status/'
        ]
        for sq in site_queries:
            org_query = {
                "engine": "google",
                "q": sq,
                "api_key": config.SERPAPI_KEY
            }
            try:
                r = requests.get(url, params=org_query, timeout=10)
                if r.status_code == 200:
                    org_data = r.json()
                    org_matches = org_data.get("organic_results", [])
                    for item in org_matches:
                        link_url = item.get("link", "")
                        platform, cand_type = classify_social_url(link_url)
                        
                        img_urls = []
                        img_source_types = []
                        pagemap = item.get("pagemap", {})
                        if "og_image" in pagemap and isinstance(pagemap["og_image"], list):
                            for ogi in pagemap["og_image"]:
                                src = ogi.get("src")
                                if src and src.startswith("http") and not is_profile_avatar_url(src) and not is_search_thumbnail_url(src):
                                    img_urls.append(src)
                                    img_source_types.append("post_media_og")
                        if "cse_image" in pagemap and isinstance(pagemap["cse_image"], list):
                            for ci in pagemap["cse_image"]:
                                src = ci.get("src")
                                if src and src.startswith("http") and not is_profile_avatar_url(src) and not is_search_thumbnail_url(src):
                                    img_urls.append(src)
                                    img_source_types.append("post_media_og")

                        if not img_urls and cand_type in ["linkedin_post", "instagram_post", "x_post", "other_social_post"]:
                            post_img, stype = fetch_page_post_media_image(link_url)
                            if post_img:
                                img_urls.append(post_img)
                                img_source_types.append(stype)

                        primary_img = img_urls[0] if img_urls else None
                        results.append({
                            "url": link_url,
                            "title": item.get("title", "No Title"),
                            "snippet": item.get("snippet", ""),
                            "source": item.get("displayed_link", ""),
                            "image_url": primary_img,
                            "all_image_urls": img_urls,
                            "image_source_types": img_source_types,
                            "candidate_platform": platform,
                            "candidate_type": cand_type,
                            "raw_item": item
                        })
            except Exception:
                pass

    return results

def normalize_url(url: str) -> str:
    """Normalizes URL for matching."""
    if not url:
        return ""
    u = url.lower().strip()
    for prefix in ["https://", "http://", "www."]:
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.rstrip("/")

def verify_candidate_face(candidate_image_url: str, gallery: dict, search_anchor_url: str = None) -> tuple[bool, float, int, int | None, list[dict], str]:
    """Downloads candidate image and runs face_match.extract_all_faces() with MTCNN strict detection.
    Rejects search anchors, profile avatars, and search thumbnails.
    Compares every detected face embedding against gallery enrolled faces.
    Returns (is_face_match, min_cosine_distance, face_count, matched_face_index, faces_detail, status_detail).
    """
    if not candidate_image_url or not candidate_image_url.startswith("http"):
        return False, 1.0, 0, None, [], "UNVERIFIED — POST IMAGE NOT AVAILABLE"

    if is_profile_avatar_url(candidate_image_url):
        return False, 1.0, 0, None, [], "REJECTED — PROFILE AVATAR NOT POST MEDIA"

    if is_search_thumbnail_url(candidate_image_url):
        return False, 1.0, 0, None, [], "REJECTED — SEARCH THUMBNAIL NOT POST MEDIA"

    if search_anchor_url and candidate_image_url.strip().lower() == search_anchor_url.strip().lower():
        return False, 1.0, 0, None, [], "REJECTED — CANDIDATE MATCHES SEARCH ANCHOR"

    tmp_file = None
    try:
        resp = requests.get(candidate_image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or not resp.content:
            return False, 1.0, 0, None, [], "UNVERIFIED — POST IMAGE NOT AVAILABLE"

        fd, tmp_file = tempfile.mkstemp(suffix=".jpg")
        os.write(fd, resp.content)
        os.close(fd)

        # Strict face detection with MTCNN backend
        try:
            detected_faces = face_match.extract_all_faces(tmp_file)
        except ValueError:
            # Rejection due to no valid face detected in candidate image
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            return False, 1.0, 0, None, [], "REJECTED — NO FACE DETECTED"

        face_count = len(detected_faces)
        match_result = face_match.match_against_gallery(detected_faces, gallery)

        if os.path.exists(tmp_file):
            os.remove(tmp_file)

        if match_result.match:
            return True, match_result.distance, face_count, match_result.matched_face_index, match_result.faces_detail, "VERIFIED SOCIAL MEDIA FACE MATCH"
        else:
            return False, match_result.distance, face_count, match_result.matched_face_index, match_result.faces_detail, "REJECTED — FACE MISMATCH"
    except Exception:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        return False, 1.0, 0, None, [], "UNVERIFIED — POST IMAGE NOT AVAILABLE"

def select_best_result(results: list[dict], enrollment_record: dict, gallery: dict = None) -> dict:
    """Rigorous candidate selection requiring:
    1. Candidate must be a valid social post (linkedin_post, instagram_post, x_post, or other_social).
    2. Image must be post content media (image_belongs_to_post == True), NOT profile photo, author avatar, or search thumbnail.
    3. Image must pass strict MTCNN face detection and ArcFace cosine distance verification against gallery.
    """
    iso_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if gallery is None:
        gallery = face_match.load_gallery(config.GALLERY_DIR)

    search_anchor = enrollment_record.get("search_image_url")
    own_profiles = enrollment_record.get("own_known_profiles", [])
    normalized_profiles = [normalize_url(p) for p in own_profiles if p]

    if not results:
        return {
            "candidate_url": "",
            "candidate_title": "",
            "candidate_platform": "N/A",
            "candidate_type": "N/A",
            "candidate_image_url": "",
            "image_source_type": "none",
            "image_belongs_to_post": False,
            "image_is_profile_avatar": False,
            "image_is_search_anchor": False,
            "face_count": 0,
            "matched_face_index": None,
            "faces_detail": [],
            "cosine_distance": 1.0,
            "face_match_score": 1.0,
            "ownership_match": False,
            "verification_status": "NO VERIFIED SOCIAL MEDIA POST FOUND",
            "verification_reason": "Search API returned zero candidates",
            "url": "",
            "title": "",
            "snippet": "",
            "retrieved_at": iso_timestamp
        }

    verified_candidate = None

    for res in results:
        cand_url_raw = res.get("url") or ""
        cand_url_norm = normalize_url(cand_url_raw)
        cand_type = res.get("candidate_type", "generic_webpage")
        cand_platform = res.get("candidate_platform", "Web")
        all_imgs = res.get("all_image_urls") or ([res.get("image_url")] if res.get("image_url") else [])
        img_stypes = res.get("image_source_types") or (["serpapi_visual_match"] * len(all_imgs))

        # Ownership match check
        is_owner = False
        if cand_url_norm:
            for prof in normalized_profiles:
                if cand_url_norm == prof or cand_url_norm.startswith(prof + "/"):
                    is_owner = True
                    break

        # Check post type requirement (linkedin_post, instagram_post, x_post, or other_social)
        is_social_post = cand_type in ["linkedin_post", "instagram_post", "x_post", "other_social"]
        if not is_social_post:
            continue

        if not all_imgs:
            continue

        for idx, cand_img_url in enumerate(all_imgs):
            if not cand_img_url:
                continue

            stype = img_stypes[idx] if idx < len(img_stypes) else "serpapi_visual_match"
            is_avatar = is_profile_avatar_url(cand_img_url)
            is_anchor = bool(search_anchor and cand_img_url.strip().lower() == search_anchor.strip().lower())
            is_thumb = is_search_thumbnail_url(cand_img_url)
            
            belongs_to_post = not is_avatar and not is_anchor and not is_thumb

            if not belongs_to_post:
                continue

            is_face_match, dist, fcount, matched_face_idx, fdetails, status_det = verify_candidate_face(cand_img_url, gallery, search_anchor_url=search_anchor)

            if is_face_match and belongs_to_post and fcount >= 1 and matched_face_idx is not None:
                verified_candidate = {
                    "candidate_url": cand_url_raw,
                    "candidate_title": res.get("title", ""),
                    "candidate_platform": cand_platform,
                    "candidate_type": cand_type,
                    "candidate_image_url": cand_img_url,
                    "image_source_type": stype,
                    "image_belongs_to_post": True,
                    "image_is_profile_avatar": False,
                    "image_is_search_anchor": False,
                    "face_count": fcount,
                    "matched_face_index": matched_face_idx,
                    "faces_detail": fdetails,
                    "cosine_distance": dist,
                    "face_match_score": dist,
                    "ownership_match": is_owner,
                    "verification_status": "VERIFIED SOCIAL MEDIA FACE MATCH",
                    "verification_reason": f"Post media image verified via face match (cosine_distance: {dist:.4f}, faces: {fcount}, matched_face_idx: {matched_face_idx}, stype: {stype})",
                    "url": cand_url_raw,
                    "title": res.get("title", ""),
                    "snippet": res.get("snippet", ""),
                    "retrieved_at": iso_timestamp
                }
                break

        if verified_candidate:
            break

    if verified_candidate:
        return verified_candidate

    # Return structured NO VERIFIED POST FOUND when no social post content image contains a verified face match
    first_cand = results[0] if results else {}
    first_url = first_cand.get("url", "")
    is_first_owner = any(normalize_url(first_url) == p or normalize_url(first_url).startswith(p + "/") for p in normalized_profiles)

    first_img = first_cand.get("image_url", "")
    is_first_avatar = is_profile_avatar_url(first_img)
    is_first_anchor = bool(search_anchor and first_img.strip().lower() == search_anchor.strip().lower())
    
    return {
        "candidate_url": first_url,
        "candidate_title": first_cand.get("title", ""),
        "candidate_platform": first_cand.get("candidate_platform", "Web"),
        "candidate_type": first_cand.get("candidate_type", "generic_webpage"),
        "candidate_image_url": first_img,
        "image_source_type": "none",
        "image_belongs_to_post": False,
        "image_is_profile_avatar": is_first_avatar,
        "image_is_search_anchor": is_first_anchor,
        "face_count": 0,
        "matched_face_index": None,
        "faces_detail": [],
        "cosine_distance": 1.0,
        "face_match_score": 1.0,
        "ownership_match": is_first_owner,
        "verification_status": "NO VERIFIED SOCIAL MEDIA POST FOUND",
        "verification_reason": "No social media post content image matched the enrolled gallery face embeddings",
        "url": "",
        "title": "",
        "snippet": "",
        "retrieved_at": iso_timestamp
    }



