import os
import requests
import re
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

        if repo.get("archived"):
            continue

        homepage = repo.get("homepage", "")
        if homepage and "steamcommunity.com" in homepage:
            repo["steam_url"] = homepage
            filtered.append(repo)

    return filtered


def get_workshop_title(soup):
    title_div = soup.find("div", class_="workshopItemTitle")
    if title_div:
        return title_div.text.strip()
    return None


def get_workshop_data(steam_url):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }
        r = requests.get(steam_url, headers=headers, timeout=10)
        if r.status_code != 200:
            return " ", " "

        soup = BeautifulSoup(r.text, "html.parser")

        # Subscriber count
        sub_count = "?"
        for table in soup.find_all("table", class_="stats_table"):
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) == 2 and "Subscribers" in cols[1].text:
                    sub_count = cols[0].text.strip().replace(",", "")

        # Title
        title = get_workshop_title(soup)
        return sub_count, title

    except Exception as e:
        print(f"[Scraper error] {steam_url} → {e}")
        return " ", " "


def generate_table(repos):
    rows = ["| Project | Subscribers | Links |", "|---------|-------------|--------|"]
    for repo in repos:
        steam_url = repo["steam_url"]
        github_url = repo["html_url"]
        repo_name = repo["name"]

        subs, title = get_workshop_data(steam_url)

        # Fallback to repo name if workshop title is missing
        project_name = title if title else repo_name

        steam_link = f"[Steam]({steam_url})"
        repo_link = f"[Repo]({github_url})"

        row = f"| {project_name} | {subs} | {steam_link} · {repo_link} |"
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
