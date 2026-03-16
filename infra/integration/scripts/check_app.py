"""Quick diagnostic: verify GitHub App config, installation, and repo access."""
import os, time, jwt, httpx

APP_ID = os.environ.get("GITHUB_APP_ID", "")
KEY_PATH = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "/secrets/app.pem")

with open(KEY_PATH) as f:
    pem = f.read()

now = int(time.time())
jwt_token = jwt.encode({"iat": now - 60, "exp": now + 600, "iss": APP_ID}, pem, algorithm="RS256")

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

r = httpx.get("https://api.github.com/app", headers=headers)
data = r.json()
print(f"App: {data.get('name')}")
print(f"Events: {data.get('events')}")

r2 = httpx.get("https://api.github.com/app/installations", headers=headers)
installs = r2.json()
print(f"Installations: {len(installs)}")

for inst in installs:
    print(f"  ID: {inst['id']}, Account: {inst['account']['login']}")
    token_r = httpx.post(
        f"https://api.github.com/app/installations/{inst['id']}/access_tokens",
        headers=headers,
    )
    if token_r.status_code == 201:
        inst_token = token_r.json()["token"]
        repos_r = httpx.get(
            "https://api.github.com/installation/repositories?per_page=100",
            headers={**headers, "Authorization": f"token {inst_token}"},
        )
        if repos_r.status_code == 200:
            repos = [r["full_name"] for r in repos_r.json().get("repositories", [])]
            has_gitpoli = "erasmo-dominguez-stuff/gitpoli" in repos
            print(f"  Total repos: {len(repos)}")
            print(f"  gitpoli included: {has_gitpoli}")
            if not has_gitpoli:
                print(f"  Repos: {repos}")
