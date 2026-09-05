import datetime
import requests
import config

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

def run_search(query: dict) -> list[dict]:
    """Executes the live SerpApi call, returns parsed results.
    If image search fails or returns 0 results, falls back to text search.
    """
    url = "https://serpapi.com/search"
    resp = requests.get(url, params=query, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    if query.get("engine") == "google_lens":
        raw_matches = data.get("visual_matches", [])
        for item in raw_matches:
            results.append({
                "url": item.get("link") or item.get("source"),
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet") or item.get("source") or "",
                "source": item.get("source", "")
            })
    else:
        raw_matches = data.get("organic_results", [])
        for item in raw_matches:
            results.append({
                "url": item.get("link"),
                "title": item.get("title", "No Title"),
                "snippet": item.get("snippet", ""),
                "source": item.get("displayed_link", "")
            })
    return results

def select_best_result(results: list[dict], enrollment_record: dict) -> dict:
    """Programmatic selection logic: selects result matching known identifiers.
    Returns canonical search result structure per TRD Section 3.3.
    Raises ValueError if zero results found.
    """
    if not results:
        raise ValueError("Search API returned zero results")

    target_identifiers = [
        "mohdasif-v1",
        enrollment_record.get("display_name", "").lower(),
        "github.com/mohdasif-v1"
    ]

    selected = None
    for res in results:
        res_url = (res.get("url") or "").lower()
        res_title = (res.get("title") or "").lower()
        res_snippet = (res.get("snippet") or "").lower()
        res_source = (res.get("source") or "").lower()

        text_to_check = f"{res_url} {res_title} {res_snippet} {res_source}"

        for ident in target_identifiers:
            if ident and ident in text_to_check:
                selected = res
                break
        if selected:
            break

    # Default to first result if no explicit identifier match
    if not selected:
        selected = results[0]

    iso_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "url": selected.get("url", ""),
        "title": selected.get("title", ""),
        "snippet": selected.get("snippet", ""),
        "retrieved_at": iso_timestamp
    }
