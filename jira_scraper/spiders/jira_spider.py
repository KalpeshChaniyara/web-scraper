# jira_scraper/spiders/jira_spider.py
import json
import time
from scrapy import Spider, Request
from scrapy.exceptions import CloseSpider

class JiraSpider(Spider):
    name = "jira"
    custom_settings = {
        # control concurrency, retry settings, etc.
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 5,
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_TIMEOUT': 20,
    }

    def __init__(self, jira_base_url, jira_auth_token, jql, **kwargs):
        super().__init__(**kwargs)
        self.jira_base = jira_base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {jira_auth_token}",
            "Accept": "application/json",
        }
        self.jql = jql
        self.page_size = 50
        self.checkpoint = self.load_checkpoint()

    def start_requests(self):
        # Determine starting offset
        start_at = self.checkpoint.get("search", {}).get("last_startAt", 0)
        url = f"{self.jira_base}/rest/api/2/search"
        params = {
            "jql": self.jql,
            "startAt": start_at,
            "maxResults": self.page_size,
            "expand": "changelog",  # optionally expand
        }
        yield Request(url, method="GET", headers=self.headers,
                      callback=self.parse_search_page,
                      cb_kwargs={"start_at": start_at, "params": params})

    def parse_search_page(self, response, start_at, params):
        if response.status != 200:
            self.logger.error("Search page failed: %s", response.status)
            # you could raise CloseSpider or retry logic
            return

        data = response.json()
        issues = data.get("issues", [])
        total = data.get("total", 0)
        count = len(issues)
        self.logger.info(f"Fetched {count} issues at offset {start_at}")

        # For each issue, fetch details (if not fully expanded)
        for issue in issues:
            key = issue.get("key")
            issue_url = f"{self.jira_base}/rest/api/2/issue/{key}"
            yield Request(issue_url, method="GET", headers=self.headers,
                          callback=self.parse_issue,
                          cb_kwargs={"issue_summary": issue})

        # Pagination: request next page
        next_start = start_at + count
        if next_start < total:
            params2 = dict(params)
            params2["startAt"] = next_start
            yield Request(response.url, method="GET", headers=self.headers,
                          callback=self.parse_search_page,
                          cb_kwargs={"start_at": next_start, "params": params2})
        # else finish

        # Update checkpoint after page
        self.checkpoint.setdefault("search", {})["last_startAt"] = next_start
        self.save_checkpoint()

    def parse_issue(self, response, issue_summary):
        if response.status != 200:
            self.logger.error("Issue detail failed for %s: status %s", issue_summary.get("key"), response.status)
            return

        detail = response.json()
        # Merge summary + detail
        merged = {**issue_summary, **detail}
        transformed = self.transform(merged)
        yield transformed  # this goes to item pipeline or output

    def transform(self, merged_json):
        # Convert merged JIRA JSON into your desired schema
        out = {}
        out["issue_id"] = merged_json.get("key")
        fields = merged_json.get("fields", {})
        out["title"] = fields.get("summary")
        out["status"] = fields.get("status", {}).get("name")
        out["priority"] = fields.get("priority", {}).get("name")
        out["project"] = fields.get("project", {}).get("key")
        out["reporter"] = {"id": fields.get("reporter", {}).get("accountId"),
                           "name": fields.get("reporter", {}).get("displayName")}
        assignee = fields.get("assignee")
        if assignee:
            out["assignee"] = {"id": assignee.get("accountId"), "name": assignee.get("displayName")}
        else:
            out["assignee"] = None
        out["labels"] = fields.get("labels", [])
        out["created_at"] = fields.get("created")
        out["updated_at"] = fields.get("updated")
        # description (convert from HTML/markup as needed)
        out["description"] = fields.get("description")
        # comments
        comments = fields.get("comment", {}).get("comments", [])
        out["comments"] = [
            {
                "id": c.get("id"),
                "author": c.get("author", {}).get("displayName"),
                "created": c.get("created"),
                "text": c.get("body")
            }
            for c in comments
        ]
        # changelog (if expanded)
        cl = merged_json.get("changelog", {}).get("histories", [])
        out["changelog"] = []
        for h in cl:
            for item in h.get("items", []):
                out["changelog"].append({
                    "field": item.get("field"),
                    "from": item.get("fromString"),
                    "to": item.get("toString"),
                    "author": h.get("author", {}).get("displayName"),
                    "when": h.get("created")
                })

        out["derived"] = {}  # you can fill later
        out["raw_source_date"] = out["updated_at"]
        return out

    def load_checkpoint(self):
        try:
            with open("checkpoint.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_checkpoint(self):
        tmp = "checkpoint.json.tmp"
        with open(tmp, "w") as f:
            json.dump(self.checkpoint, f, indent=2)
        # atomic rename
        import os
        os.replace(tmp, "checkpoint.json")
