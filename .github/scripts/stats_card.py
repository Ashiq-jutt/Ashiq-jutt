"""Builds metrics.stats.svg: a stats card that only shows the numbers worth showing.

Runs in GitHub Actions with GH_TOKEN set to a personal access token (repo, read:user),
so private contributions are counted too.
"""
import datetime
import html
import json
import os
import urllib.request

USER = os.environ.get("GH_USER", "Ashiq-jutt")
OUT = os.environ.get("OUT", "metrics.stats.svg")


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        json.dumps({"query": query, "variables": variables}).encode(),
        {"Authorization": f"bearer {os.environ['GH_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def fetch():
    user = gql(
        """query($login: String!) { user(login: $login) {
             name createdAt
             repositories(ownerAffiliations: OWNER) { totalCount }
             pullRequests { totalCount }
             repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY], includeUserRepositories: true) { totalCount }
           } }""",
        {"login": USER},
    )
    created = datetime.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)

    # contributionsCollection covers at most one year per call, so walk year by year.
    commits = contributions = 0
    start = created
    while start < now:
        end = min(start + datetime.timedelta(days=365), now)
        year = gql(
            """query($login: String!, $from: DateTime!, $to: DateTime!) { user(login: $login) {
                 contributionsCollection(from: $from, to: $to) {
                   totalCommitContributions
                   contributionCalendar { totalContributions }
                 } } }""",
            {"login": USER, "from": start.isoformat(), "to": end.isoformat()},
        )["contributionsCollection"]
        commits += year["totalCommitContributions"]
        contributions += year["contributionCalendar"]["totalContributions"]
        start = end

    return {
        "name": user["name"] or USER,
        "years": (now - created).days // 365,
        "contributions": contributions,
        "commits": commits,
        "prs": user["pullRequests"]["totalCount"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
    }


def render(s):
    tiles = [
        ("Total contributions", f"{s['contributions']:,}"),
        ("Commits", f"{s['commits']:,}"),
        ("Pull requests", f"{s['prs']:,}"),
        ("Repos contributed to", f"{s['contributed_to']:,}"),
        ("Repositories", f"{s['repos']:,}"),
        ("Years on GitHub", f"{s['years']}+"),
    ]
    w, h, cols = 800, 230, 3
    cells = []
    for i, (label, value) in enumerate(tiles):
        x = 30 + (i % cols) * 250
        y = 92 + (i // cols) * 68
        cells.append(
            f'<text x="{x}" y="{y}" class="value">{html.escape(value)}</text>'
            f'<text x="{x}" y="{y + 22}" class="label">{html.escape(label)}</text>'
        )
    updated = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(s['name'])}'s GitHub stats">
<style>
  text {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; }}
  .title {{ font-size: 20px; font-weight: 600; fill: #e6edf3; }}
  .value {{ font-size: 28px; font-weight: 700; fill: #58a6ff; }}
  .label {{ font-size: 14px; fill: #8b949e; }}
  .foot {{ font-size: 11px; fill: #6e7681; }}
</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="#0d1117" stroke="#30363d"/>
<text x="30" y="42" class="title">{html.escape(s['name'])}'s GitHub Stats</text>
{''.join(cells)}
<text x="{w - 30}" y="{h - 14}" class="foot" text-anchor="end">Includes private contributions · updated {updated}</text>
</svg>
"""


if __name__ == "__main__":
    stats = fetch()
    print(json.dumps(stats))
    with open(OUT, "w") as f:
        f.write(render(stats))
