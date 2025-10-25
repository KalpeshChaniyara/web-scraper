# 🧩 Apache JIRA Data Scraper

A fault-tolerant, resumable data scraper built using **Scrapy**, designed to extract issues, comments, and metadata from **Apache JIRA**.  
The system supports pagination, retry logic, checkpointing, and structured JSONL output for downstream data analysis or machine learning pipelines.

---

## 🚀 Setup Instructions & Environment Configuration

### **1️⃣ Prerequisites**
- **Python** ≥ 3.9
- **Pip** or **Poetry** for dependency management
- Access to the JIRA REST API (public or via OAuth/Token)

### **2️⃣ Clone & Install**
```bash
git clone https://github.com/yourusername/jira_scraper.git
cd jira_scraper
pip install -r requirements.txt

export JIRA_BASE_URL="https://issues.apache.org/jira"
export JIRA_AUTH_TOKEN="<your_token_here>"
export JIRA_JQL="project=HADOOP ORDER BY updated DESC"

scrapy crawl jira \
  -a jira_base_url=$JIRA_BASE_URL \
  -a jira_auth_token=$JIRA_AUTH_TOKEN \
  -a jql="$JIRA_JQL" \
  -o output.jsonl



📁 jira_scraper/
├── spiders/
│   └── jira_spider.py        # Main spider handling API pagination, retries, and checkpointing
├── pipelines.py              # Optional post-processing for transformation/export
├── items.py                  # (Optional) Schema definitions for scraped data
├── settings.py               # Scrapy config (retries, timeouts, concurrency)
└── checkpoint.json           # Progress checkpoint file


| Component                | Purpose                                                                                  |
| ------------------------ | ---------------------------------------------------------------------------------------- |
| **Spider Layer**         | Handles fetching issues, comments, changelogs via REST API with pagination.              |
| **Checkpoint Mechanism** | Saves last successful `startAt` offset for resumable scraping after interruption.        |
| **Retry Logic**          | Exponential backoff for handling transient HTTP failures (429, 5xx).                     |
| **Data Transformer**     | Converts raw JIRA JSON into structured schema (title, status, priority, comments, etc.). |
| **JSONL Output**         | Each record is a standalone JSON line, ideal for streaming or ingestion.                 |


Design Decisions

Scrapy chosen for reliability, middleware extensibility, and automatic retry handling.

Stateless pagination via startAt ensures recoverability and reproducibility.

Atomic checkpoint saving avoids corruption during abrupt shutdowns.

Modular transform layer allows easy integration of downstream NLP/ML tasks.


| Scenario                                   | Handling Strategy                                                |
| ------------------------------------------ | ---------------------------------------------------------------- |
| **HTTP 429 (Rate Limit)**                  | Retries with exponential backoff delay.                          |
| **HTTP 5xx Server Errors**                 | Retry up to 5 times before aborting gracefully.                  |
| **Empty / Malformed JSON**                 | Logged and retried automatically; invalid responses skipped.     |
| **Network Failure / Timeout**              | Captured via Scrapy middleware; request retried.                 |
| **Partial Page Fetch**                     | Checkpoint ensures next run resumes at last completed `startAt`. |
| **Missing Fields (assignee, description)** | Defaults to `None` or empty list in transformed schema.          |
