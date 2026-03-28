# Excellon RPA System

Automated report generation and export pipeline for the **Excellon Bajaj 5.0** Windows desktop application. Built with LangGraph orchestration, pywinauto UI automation, OpenCV visual detection, and Google Gemini AI verification.

## Architecture

The system runs 4 specialized agents in sequence, each responsible for one phase of the workflow:

```
                         Excellon RPA Pipeline
 ┌──────────────────────────────────────────────────────────────────┐
 │                      Master Orchestrator                         │
 │                  (LangGraph StateGraph Pipeline)                 │
 │                                                                  │
 │   Agent 1         Agent 2          Agent 3         Agent 4       │
 │   LOGIN           NAVIGATION       FILTER          DOWNLOAD      │
 │  ─────────       ────────────     ──────────      ───────────    │
 │  Launch app      Search bar       Open filter     Click XLSX     │
 │  Credentials     OpenCV detect    panel           File export    │
 │  Press Connect   Gemini verify    Tax checkboxes  Save As        │
 │  Handle popups   Double-click     Custom dates    Rename file    │
 │  Verify home     Open report      Generate        Close app      │
 │                                                                  │
 │       ──►             ──►              ──►              ──►      │
 │                 Error at any stage halts pipeline                 │
 └──────────────────────────────────────────────────────────────────┘
```

Each agent is an independent LangGraph sub-graph with its own state and node definitions. The orchestrator chains them with conditional error routing -- if any agent fails, the pipeline halts and reports the failure.

### Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Orchestration | LangGraph | State graph pipelines, conditional routing |
| UI Automation | pywinauto, pyautogui | Window interaction, keyboard/mouse control |
| Window Detection | pygetwindow, ctypes | Fast window enumeration (Win32 API) |
| Computer Vision | OpenCV | Highlight detection in search results |
| AI Verification | Google Gemini 2.0 Flash | Visual confirmation of correct item selection |
| Configuration | Pydantic Settings | Type-safe .env configuration |
| API | FastAPI + Uvicorn | REST API for remote execution |
| Logging | Loguru | Structured logging with rotation |

## Prerequisites

- **Windows 10/11** (requires Windows desktop for UI automation)
- **Python 3.11+**
- **Excellon Bajaj 5.0** installed and accessible via ClickOnce shortcut
- **Google Gemini API key** (for visual verification in navigation)

## Installation

```bash
git clone <repo-url>
cd excellon-rpa-system

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Application
APP_EXE_PATH=C:\Users\YourName\Desktop\Excellon Bajaj 5.appref-ms
APP_WINDOW_TITLE=Excellon

# Login Credentials
EXCELLON_USERNAME=our_username
EXCELLON_PASSWORD=your_password

# Report Selection (must match a key in reports.json)
REPORT_KEY=sale_statement

# Date Range (DD/MM/YYYY)
FILTER_FROM_DATE=01/03/2026
FILTER_TO_DATE=31/03/2026

# Download Settings
DEALER_CODE=D10836
BRANCH_CODE=BR001
SAVE_PATH=D:\Projects\excellon-rpa-system\download
DOWNLOAD_FORMAT=xlsx

# Google Gemini (for visual verification)
GEMINI_API_KEY=your_gemini_api_key

# API Server (optional)
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### Report Definitions

Reports are defined in `reports.json`. Each entry specifies the navigation path and filter configuration:

```json
{
  "sale_statement": {
    "module": "SALES MODULE",
    "folders": ["REPORTS", "SALES", "Statements"],
    "report_name": "Sale Statement",
    "filters": ["Show Taxes", "Show Tax Detail"]
  }
}
```

| Field | Description |
|---|---|
| `module` | Top-level module in Excellon's navigation tree |
| `folders` | Folder path from module to the report (excluding the report itself) |
| `report_name` | Exact display name of the report in the UI |
| `filters` | Checkboxes to enable in the filter panel (optional) |

**Available reports:**

| Key | Report | Path |
|---|---|---|
| `sale_statement` | Sale Statement | Sales > Reports > Sales > Statements |
| `purchase_statement` | Purchase Statement | Sales > Reports > Procurement > Statements |
| `purchase_invoice_statement` | Purchase Invoice Statement | Sales > Reports > Procurement > Statements |
| `stock_valuation` | Stock Valuation | Sales > Reports > Inventory > Stock |
| `hsrp_installation_report` | HSRP Installation Report | Sales > HSRP |
| `hsrp_pending_chassis_report` | HSRP Pending Chassis Report | Sales > HSRP |

## Usage

### Full Pipeline

Run all 4 agents sequentially (login, navigate, filter, download):

```bash
python main.py --run
```

With date and report overrides:

```bash
python main.py --run --report-key purchase_statement --from-date 01/01/2026 --to-date 31/01/2026
```

### Single Agent

Run one agent in isolation (the application must already be in the correct state):

```bash
python main.py --agent login        # Launch app and log in
python main.py --agent navigation   # Search and open a report
python main.py --agent filter       # Set filters and generate report
python main.py --agent download     # Export XLSX and close app
```

### API Server

Start the REST API for remote execution:

```bash
python main.py --api
```

## API Reference

### POST /run-pipeline

Run the full 4-agent pipeline.

```bash
curl -X POST http://localhost:8000/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"report_key": "sale_statement", "from_date": "01/03/2026", "to_date": "31/03/2026"}'
```

All request body fields are optional (defaults from `.env`).

### POST /run-agent/{agent_name}

Run a single agent. Valid names: `login`, `navigation`, `filter`, `download`.

```bash
curl -X POST http://localhost:8000/run-agent/filter
```

### GET /health

Returns whether the Excellon application is currently running.

### GET /status

Returns the result of the last pipeline run.

## Project Structure

```
excellon-rpa-system/
├── main.py                          # CLI entry point
├── reports.json                     # Report definitions
├── requirements.txt                 # Python dependencies
├── .env                             # Configuration (not committed)
│
├── orchestrator/                    # Pipeline orchestration
│   ├── graph.py                     #   Master pipeline (chains 4 agents)
│   ├── state.py                     #   GlobalState TypedDict
│   └── router.py                    #   Conditional routing logic
│
├── agents/
│   ├── agent1_login/                # Agent 1: Login
│   │   ├── graph.py                 #   LangGraph sub-graph
│   │   └── nodes/                   #   8 nodes (launch, wait, type, connect, popups, verify)
│   │
│   ├── agent2_navigation/           # Agent 2: Navigation
│   │   ├── graph.py                 #   LangGraph sub-graph
│   │   └── nodes/                   #   8 nodes (search, collect, match, confirm, click, verify)
│   │
│   ├── agent3_filter/               # Agent 3: Filter
│   │   ├── graph.py                 #   LangGraph sub-graph
│   │   └── nodes/                   #   6 nodes (panel, checkboxes, date range, dates, generate)
│   │
│   └── agent4_download/             # Agent 4: Download
│       ├── graph.py                 #   LangGraph sub-graph
│       └── nodes/                   #   5 nodes (export, popup, save, decline, close)
│
├── automation/                      # UI automation utilities
│   ├── window_manager.py            #   Window detection and focus (pygetwindow + UIAWrapper)
│   ├── keyboard_mouse.py            #   Typing and clicking helpers
│   ├── popup_handler.py             #   Popup detection and dismissal
│   ├── search_handler.py            #   Search bar interaction
│   ├── ui_tree_reader.py            #   Navigation tree traversal
│   ├── screenshot.py                #   Screen capture
│   └── uia_retry.py                 #   Retried UIA element search
│
├── vision/                          # Computer vision
│   ├── highlight_detector.py        #   OpenCV highlight detection in search results
│   └── gemini_verifier.py           #   Gemini API visual verification
│
├── config/                          # Configuration
│   ├── settings.py                  #   Pydantic settings from .env
│   └── report_loader.py             #   reports.json loader
│
├── api/                             # REST API
│   ├── main.py                      #   FastAPI app
│   ├── routes.py                    #   Endpoint definitions
│   └── schemas.py                   #   Request/response models
│
├── logs/                            # Runtime logs
│   ├── agent.log                    #   Application log
│   └── screenshots/                 #   Debug screenshots
│
├── download/                        # Exported report files
└── tests/                           # Test suite
```

## How It Works

### Agent 1: Login

Launches the Excellon ClickOnce application, waits for the login dialog, types credentials into the User Name and Password fields, and presses Connect. Handles 0-N post-login popups (Login Confirmation, Application Installation Alert, HSRP Compliance) by clicking Yes/OK. Detects if the user is already logged in and skips to verification.

### Agent 2: Navigation

Types the report name into the search bar, then uses a 3-layer matching strategy to find the correct item:

1. **OpenCV highlight detection** -- finds highlighted regions in the search results panel
2. **Width-based disambiguation** -- the exact match has all words highlighted (widest region)
3. **Gemini row-OCR** -- when widths are similar, crops each row and asks Gemini to confirm the exact text match

Double-clicks the identified item to open the report.

### Agent 3: Filter

Opens the filter panel, toggles configured checkboxes (e.g., Show Taxes), selects "Custom" from the Date Range dropdown, enters From/To dates, and presses Generate Report. Waits for data to load before proceeding.

### Agent 4: Download

Clicks the XLSX File export button, presses OK on the Export Options popup, handles the Save As dialog (renames file with date, dealer code, branch code, and report key), clicks Yes on overwrite confirmation if needed, declines the "open file?" prompt, and closes the application with Alt+F4.

**Output filename format:**
```
DD-MM-YYYY, DEALER_CODE, BRANCH_CODE, report_key, from_date to to_date.xlsx
```

## Adding New Reports

1. Add an entry to `reports.json`:

```json
{
  "your_report_key": {
    "module": "SALES MODULE",
    "folders": ["REPORTS", "CATEGORY", "Subcategory"],
    "report_name": "Exact Report Name",
    "filters": ["Show Taxes"]
  }
}
```

2. Run with the new key:

```bash
python main.py --run --report-key your_report_key
```

The `report_name` must exactly match the text shown in Excellon's navigation tree. The `filters` array lists checkbox labels to enable -- omit or set to `[]` if none are needed.

## Troubleshooting

| Problem | Solution |
|---|---|
| Application won't launch | Verify `APP_EXE_PATH` points to the correct `.appref-ms` or `.exe` file |
| Login fails / hangs | Check `EXCELLON_USERNAME` and `EXCELLON_PASSWORD` in `.env` |
| Navigation can't find report | Verify `report_name` in `reports.json` exactly matches the UI text |
| Export popup not dismissed | The node presses Enter after 1s -- ensure the popup appears before then |
| Save As dialog not found | Check that `SAVE_PATH` directory exists and is writable |
| Gemini verification fails | Verify `GEMINI_API_KEY` is valid and has API access |
| Agent hangs indefinitely | Never use `app.top_window()` or `app.windows()` -- use `get_main_window()` instead |

**Debug mode:** Set `LOG_LEVEL=DEBUG` in `.env` for verbose output. Debug screenshots are saved to `logs/screenshots/` on failures.

**Logs:** All actions are logged to `logs/agent.log` with timestamps.

## Running Tests

```bash
python -m pytest tests/ -v
```

Individual test files:

```bash
python -m pytest tests/test_agent2_navigation.py -v
```

## License

Proprietary. Internal use only.
