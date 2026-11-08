import json
import os
import re
from collections import Counter
from datetime import date, datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


USERNAME = "alexcsl"
ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    headers = {"User-Agent": "alexcsl-profile-stats"}
    if url.startswith("https://api.github.com/") and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8")


class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-date" in attrs and "data-level" in attrs:
            self.days[date.fromisoformat(attrs["data-date"])] = int(attrs["data-level"])


def generate():
    profile = json.loads(fetch(f"https://api.github.com/users/{USERNAME}"))
    repos = []
    page = 1
    while True:
        batch = json.loads(fetch(
            f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        ))
        repos.extend(repo for repo in batch if not repo["private"])
        if len(batch) < 100:
            break
        page += 1
    source_repos = [repo for repo in repos if not repo["fork"]]
    languages = Counter(repo["language"] for repo in source_repos if repo["language"])
    calendar_html = fetch(f"https://github.com/users/{USERNAME}/contributions")
    calendar = Calendar()
    calendar.feed(calendar_html)
    heading = re.search(
        r'id="js-contribution-activity-description"[^>]*>(.*?)</h2>',
        calendar_html, re.S,
    )
    if len(calendar.days) < 350 or not heading:
        raise ValueError("GitHub contribution markup changed; keeping the previous SVG")
    summary = " ".join(heading.group(1).split())
    if not re.fullmatch(r"[\d,]+ contributions? in the last year", summary):
        raise ValueError("Unexpected contribution summary; keeping the previous SVG")
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="370" viewBox="0 0 900 370" role="img" aria-labelledby="title desc">',
        '<title id="title">Alexander CSL on GitHub</title>',
        f'<desc id="desc">{escape(summary)}. {len(repos)} public repositories. Updated {updated} UTC.</desc>',
        '<rect x="1" y="1" width="898" height="368" rx="18" fill="#101a2b" stroke="#303d50"/>',
        '<g font-family="sans-serif" fill="#e6edf3">',
        '<text x="32" y="40" font-size="12" fill="#78dcca" letter-spacing="2">BUILD / EXPLORE / REPEAT</text>',
        '<text x="32" y="76" font-size="25" font-weight="700">A year of learning in public</text>',
        f'<text x="32" y="101" font-size="13" fill="#aab8cc">{escape(summary)}</text>',
    ]
    metrics = [
        (len(repos), "Public repos"),
        (sum(repo["stargazers_count"] for repo in source_repos), "Stars on original repos"),
        (profile["followers"], "Followers"),
    ]
    for index, (value, label) in enumerate(metrics):
        x = 32 + index * 282
        svg.extend([
            f'<text x="{x}" y="150" font-size="28" font-weight="700">{value:,}</text>',
            f'<text x="{x}" y="171" font-size="12" fill="#aab8cc">{label}</text>',
        ])
    colors = ["#1c293b", "#165c58", "#238c79", "#43bea0", "#8ae9c2"]
    first = min(calendar.days)
    first_sunday = first.toordinal() - (first.weekday() + 1) % 7
    for day, level in sorted(calendar.days.items()):
        week = (day.toordinal() - first_sunday) // 7
        row = (day.weekday() + 1) % 7
        x, y = 32 + week * 15.8, 192 + row * 15
        svg.append(
            f'<rect x="{x:.1f}" y="{y}" width="12" height="12" rx="3" fill="{colors[level]}">'
            f'<title>{day.isoformat()}: contribution level {level} of 4</title></rect>'
        )
    language_text = "   /   ".join(f"{name} {count}" for name, count in languages.most_common(5))
    svg.extend([
        f'<text x="32" y="325" font-size="12" fill="#aab8cc">Primary languages by original public repo: {escape(language_text)}</text>',
        f'<text x="32" y="350" font-size="11" fill="#aab8cc">Updated {updated} UTC</text>',
        '<text x="696" y="350" font-size="11" fill="#aab8cc">Less</text>',
    ])
    for index, color in enumerate(colors):
        svg.append(f'<rect x="{728 + index * 17}" y="340" width="12" height="12" rx="3" fill="{color}"/>')
    svg.extend(['<text x="820" y="350" font-size="11" fill="#aab8cc">More</text>', '</g></svg>'])
    destination = ROOT / "assets" / "github-activity.svg"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(f"Generated {destination.name}: {summary}, {len(repos)} public repositories")


if __name__ == "__main__":
    generate()
