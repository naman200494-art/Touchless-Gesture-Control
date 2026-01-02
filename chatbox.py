import os
import requests
from dotenv import load_dotenv
from google import genai  # pip install google-genai

load_dotenv()  # loads .env from project root

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()

def get_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment variables.")
    return genai.Client(api_key=GEMINI_API_KEY)

def google_search(query: str, num_results: int = 5):
    """
    Use Google Custom Search to fetch web results.
    Returns a list of dicts with title, link, snippet.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": num_results,
    }
    try:
        resp = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        results = []
        for it in items:
            results.append({
                "title": it.get("title", ""),
                "link": it.get("link", ""),
                "snippet": it.get("snippet", ""),
            })
        return results
    except Exception as e:
        print("Google search error:", e)
        return []

def build_search_context(results):
    if not results:
        return ""
    lines = []
    for i, it in enumerate(results, 1):
        lines.append(f"{i}. {it.get('title','')} ({it.get('link','')})\n{it.get('snippet','')}")
    return "\n\n".join(lines)

def generate_chat_reply(user_message: str, history: list[dict] | None = None) -> str:
    """
    Generate a reply from Gemini, optionally using Google search results
    for fresher information. History is a list of {role, content}.
    """
    client = get_gemini_client()

    # Build conversation history text
    history_text = ""
    if history:
        for turn in history[-10:]:
            role = turn.get("role", "").upper()
            content = turn.get("content", "")
            history_text += f"{role}: {content}\n"

    # Try web search
    search_results = google_search(user_message)
    search_context = build_search_context(search_results)

    if search_context:
        system_prompt = (
            "You are an AI assistant in a Virtual Control Hub web app. "
            "You can see the conversation history and some web search results. "
            "Use the search results for factual, up-to-date information. "
            "If the search results are irrelevant, ignore them. "
            "Answer clearly and concisely.\n\n"
        )
        contents = (
            system_prompt +
            f"Conversation so far:\n{history_text}\n" +
            f"User message: {user_message}\n\n" +
            "Web search results:\n" +
            search_context
        )
    else:
        system_prompt = (
            "You are an AI assistant in a Virtual Control Hub web app. "
            "You see the conversation history below. Continue the conversation helpfully.\n\n"
        )
        contents = system_prompt + history_text + f"User message: {user_message}"

    resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=contents,
)


    return getattr(resp, "text", str(resp))
