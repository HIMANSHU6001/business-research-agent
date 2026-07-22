import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

for i in range(1, 10):
    key_name = f"GROQ_API_KEY_{i}"
    key = os.getenv(key_name)
    if not key:
        continue
    try:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 3000}
        )
        if resp.status_code == 429:
            print(f"{key_name}: ERROR 429 - Rate Limited!")
        else:
            print(f"{key_name}: OK")
        remaining = resp.headers.get("x-ratelimit-remaining-tokens-today")
        org = resp.headers.get("x-ratelimit-org")
        print(f"{key_name}: Org: {org}, Remaining TPD: {remaining}")
    except Exception as e:
        print(f"{key_name}: ERROR - {e}")
