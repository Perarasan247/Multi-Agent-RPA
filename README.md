# Excellon RPA System

Production-grade multi-agent RPA system that automates the **Excellon Bajaj 5.0** Windows desktop application end to end. Built with LangGraph orchestration, pywinauto UI automation, OpenCV visual verification, and Gemini AI confirmation.

## Architecture Overview

The system uses 4 specialized agents orchestrated by a master LangGraph pipeline:

```
┌─────────────────────────────────────────────────────┐
│                 Master Orchestrator                  │
│         (LangGraph StateGraph Pipeline)              │
├──────────┬──────────┬──────────┬────────────────────┤
│ Agent 1  │ Agent 2  │ Agent 3  │ Agent 4            │
│ Login    │ Navigate │ Filter   │ Download           │
│          │          │          │                    │
│ Launch   │ Search   │ Toggle   │ Click XLSX export  │
│ Type     │ Collect  │ Tax CBs  │ Uncheck hyperlinks │
│ creds    │ 3-layer  │ Custom   │ Set filename       │
│ Connect  │ match    │ dates    │ Save to disk       │
│ Popups   │ OpenCV   │ Generate │ Handle popups      │
│ Verify   │ Gemini   │ report   │ Quit app           │
└──────────┴──────────┴──────────┴────────────────────┘
```

Each agent is an independent LangGraph sub-graph. The master orchestrator chains them sequentially with conditional error routing — if any agent fails, the pipeline halts immediately and logs the failure.

## Prerequisites

- **Windows 10/11** (desktop automation requires Windows)
- **Python 3.11+**
- **Excellon Bajaj 5.0** installed and accessible
- **Google Gemini API key** for visual verification

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd excellon-rpa-system

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### .env file

Copy `.env.example` to `.env` and fill in your values:

```bash
copy .env.example .env
```

Key settings to configure:

| Variable | Description |
|---|---|
| `APP_EXE_PATH` | Full path to Excellon.exe |
| `EXCELLON_USERNAME` | Login username |
| `EXCELLON_PASSWORD` | Login password |
| `REPORT_KEY` | Report to generate (see reports.json) |
| `FILTER_FROM_DATE` | Start date (DD/MM/YYYY) |
| `FILTER_TO_DATE` | End date (DD/MM/YYYY) |
| `DEALER_CODE` | Dealer code for filename |
| `BRANCH_CODE` | Branch code for filename |
| `SAVE_PATH` | Folder to save exported XLSX |
| `GEMINI_API_KEY` | Google Gemini API key |

### reports.json

Defines all available reports with their navigation paths and filter requirements. See the existing entries for the expected structure.

## Running the System

### Full Pipeline

Run all 4 agents sequentially:

```bash
python main.py --run
```

With overrides:

```bash
python main.py --run --report-key spareparts_purchase_statement --from-date 01/01/2026 --to-date 31/01/2026
```

### Single Agent

Run one agent in isolation (useful for testing/debugging):

```bash
python main.py --agent login
python main.py --agent navigation
python main.py --agent filter
python main.py --agent download
```

### API Server

Start the FastAPI server:

```bash
python main.py --api
```

Or directly with uvicorn:

```bash
uvicorn api.main:app --reload
```

## API Reference

### POST /run-pipeline

Run the full 4-agent pipeline.

```bash
curl -X POST http://localhost:8000/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"report_key": "spareparts_sales_statement"}'
```

**Request body** (all optional — defaults from .env):

```json
{
  "report_key": "spareparts_sales_statement",
  "from_date": "01/03/2026",
  "to_date": "31/03/2026"
}
```

**Response:**

```json
{
  "success": true,
  "report_key": "spareparts_sales_statement",
  "filename_saved": "D10836_BR001_spareparts_sales_statement_01-03-2026_to_31-03-2026_20260320_143022.xlsx",
  "agents_completed": [
    {"agent_name": "agent1_login", "success": true, "error": null},
    {"agent_name": "agent2_navigation", "success": true, "error": null},
    {"agent_name": "agent3_filter", "success": true, "error": null},
    {"agent_name": "agent4_download", "success": true, "error": null}
  ],
  "error": null,
  "duration_seconds": 47.3
}
```

### POST /run-agent/{agent_name}

Run a single agent. `agent_name` must be: `login`, `navigation`, `filter`, or `download`.

```bash
curl -X POST http://localhost:8000/run-agent/login
```

### GET /health

Health check — reports whether the Excellon app is currently running.

```bash
curl http://localhost:8000/health
```

### GET /status

Returns the status of the last pipeline run.

```bash
curl http://localhost:8000/status
```

## Adding New Reports

To add a new report to the system:

1. Open `reports.json`
2. Add a new entry with a unique key:

```json
{
  "your_new_report_key": {
    "module": "Module Name",
    "folders": ["Reports", "Category", "Subcategory"],
    "report_name": "Exact Report Name As Shown in UI",
    "filters": ["Show Taxes"]
  }
}
```

3. The `module` field must match the top-level module name in Excellon's navigation tree
4. The `folders` array must list each folder level in order from the module down to (but not including) the report itself
5. The `report_name` must be an **exact match** (case-sensitive) of the report's display name
6. The `filters` array is optional — omit it or set to `[]` if no checkboxes need to be toggled

Then run with:

```bash
python main.py --run --report-key your_new_report_key
```

## Troubleshooting

### Application won't launch

- Verify `APP_EXE_PATH` in `.env` points to the correct Excellon executable
- Ensure Excellon is properly installed
- Check `logs/agent.log` for detailed error messages

### Login fails

- Verify `EXCELLON_USERNAME` and `EXCELLON_PASSWORD` in `.env`
- Check if the application has a CAPTCHA or additional security
- Look for debug screenshots in `logs/screenshots/`

### Navigation can't find the report

- Verify the `report_name` in `reports.json` exactly matches the UI text
- Check the `folders` path matches the actual tree structure
- Enable `LOG_LEVEL=DEBUG` in `.env` for detailed tree traversal logs

### Export fails

- Ensure `SAVE_PATH` folder exists before running
- Check if Excellon requires specific export permissions
- Look for popup handling failures in the logs

### Gemini verification fails

- Verify `GEMINI_API_KEY` is valid
- The system fails safe (returns False) on Gemini errors
- Check network connectivity for API access

### General debugging

- Set `LOG_LEVEL=DEBUG` in `.env` for maximum verbosity
- Debug screenshots are saved to `logs/screenshots/` when `LOG_LEVEL=DEBUG`
- All actions are logged to `logs/agent.log` with timestamps

## Running Tests

```bash
python -m pytest tests/ -v
```

Or individual test files:

```bash
python -m pytest tests/test_agent2_navigation.py -v
```
