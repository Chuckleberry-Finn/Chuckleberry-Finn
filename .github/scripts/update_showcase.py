import os
import requests
from bs4 import BeautifulSoup

GITHUB_USERNAME = "Chuckleberry-Finn"
GITHUB_TOKEN = os.environ["CHUCK_PAT"]
README_FILE = "README.md"

START_MARKER = "<!-- START:WORKSHOP -->"
END_MARKER = "<!-- END:WORKSHOP -->"



def get_repos():
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    repos = []
    page = 1

    while True:
        r = requests.get(url, headers=headers, params={
            "page": page,
            "per_page": 100,
            "visibility": "public",
            "affiliation": "owner,collaborator,organization_member"
        })
        if r.status_code != 200:
            raise Exception("GitHub API error:", r.text)
        page_repos = r.json()
        if not page_repos:
            break
        repos.extend(page_repos)
        page += 1

    # Only keep repos where homepage field has a Steam Workshop link
    filtered = []
    for repo in repos:
        homepage = repo.get("homepage", "")
        if homepage and "steamcommunity.com" in homepage:
            repo["steam_url"] = homepage
            filtered.append(repo)

    return filtered


def get_subscriber_count(steam_url):
    try:
        r = requests.get(steam_url)
        soup = BeautifulSoup(r.text, "html.parser")
        count_elem = soup.find("div", class_="numSubs")
        if count_elem:
            return count_elem.text.strip()
    except Exception:
        pass
    return "?"


def generate_table(repos):
    rows = ["| Project | Subscribers | Link |", "|---------|-------------|------|"]
    for repo in repos:
        steam_url = repo["steam_url"]
        subs = get_subscriber_count(steam_url)
        name = repo["name"]
        row = f"| {name} | {subs} | [View]({steam_url}) |"
        rows.append(row)
    return "\n".join(rows)


def update_readme(table):
    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    start = content.find(START_MARKER)
    end = content.find(END_MARKER)

    if start == -1 or end == -1:
        print("Markers not found in README.md.")
        return

    before = content[:start + len(START_MARKER)]
    after = content[end:]

    new_content = f"{before}\n\n{table}\n\n{after}"

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)


if __name__ == "__main__":
    repos = get_repos()
    table = generate_table(repos)
    update_readme(table)
