# LLMUsage — Startup Due-Diligence Research Tool

> An **LLM-orchestrated multi-stage research pipeline** that automates first-cut startup screening and investment parameter research for a given sector and geography.
> Built by **CosTheta Technologies Pvt Ltd** for **Merisis Advisors Pvt Ltd**.

---

## Table of Contents

- [Overview](#overview)
- [Key Capabilities](#key-capabilities)
- [System Architecture](#system-architecture)
- [Module Map](#module-map)
- [Class Diagram](#class-diagram)
- [End-to-End Data Flow](#end-to-end-data-flow)
- [Interaction Diagrams](#interaction-diagrams)
  - [Stage 1: Startup Discovery (GetSeedStartups5)](#stage-1-startup-discovery)
  - [Stage 2: Investment Parameters (InvestmentParametersGenerator)](#stage-2-investment-parameters)
  - [Stage 3: Data Population (PopulateData)](#stage-3-data-population)
  - [GUI Thread Interaction (StartupFinderApp)](#gui-thread-interaction)
- [LLM Orchestration Design](#llm-orchestration-design)
- [Error Handling & Resilience](#error-handling--resilience)
- [Output Format](#output-format)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)

---

## Overview

Given a **sector** (e.g. "Supply-Chain Finance") and a **geography** (e.g. "India"), this tool:

1. Discovers related sectors and generates a curated list of startup candidates via Gemini
2. Classifies, deduplicates, and rationalises the startup list using rule-based logic + LLM batch processing
3. Generates a ranked, sector-specific list of investment evaluation parameters
4. Researches each startup against every parameter via individual Gemini API calls
5. Outputs a rich, linked HTML report with sources — ready for analyst review

The entire pipeline is driven by **structured Pydantic contracts**, **retry logic with exponential backoff**, and **JSON self-repair** on malformed LLM responses.

---

## Key Capabilities

| Capability | Detail |
|---|---|
| Sector discovery | Finds related business sectors to broaden the startup search universe |
| Startup generation | Multi-pass LLM calls to reach a configurable target (up to 200 startups) |
| Classification | Classifies each startup into its primary sector; batch-processed |
| Name rationalisation | Rule-based first-word deduplication followed by LLM batch rationalisation |
| Correlation scoring | Scores each discovered sector by relevance to the primary search area |
| Parameter generation | Gemini generates N ranked investment parameters specific to sector + geo |
| Per-startup research | One Gemini call per startup × parameter set; summary + source URLs per cell |
| Resilience | Exponential backoff, JSON salvage via regex, partial-result checkpointing |
| Multi-model design | Gemini as primary; Grok validation hooks stubbed and ready for activation |
| GUI | Tkinter desktop app with threaded execution and live log streaming |
| Output | Merged HTML report with clickable source links; importable into Excel |

---

## System Architecture

```
graph TB
    subgraph UI["🖥️ UI Layer"]
        APP["StartupFinderApp\n(Tkinter GUI)"]
        THREAD["Background Thread\n(threading.Thread)"]
    end

    subgraph PIPELINE["🔄 Orchestration Pipeline"]
        S1["GetSeedStartups5\nSector discovery + startup list"]
        S2["InvestmentParametersGenerator\nRanked parameter list"]
        S3["PopulateData\nPer-startup research"]
    end

    subgraph LLM["🤖 LLM Layer"]
        GEMINI["Google Gemini API\n(Flash / Pro)"]
        GROK["Grok API\n(mock — validation hook)"]
    end

    subgraph OUTPUT["📄 Output Layer"]
        HTML_TEMP["Intermediate _debug.html\n(per batch of 4 startups)"]
        HTML_FINAL["Merged Final HTML Report\n(sector_geo.html)"]
    end

    APP --> THREAD
    THREAD --> S1
    THREAD --> S2
    THREAD --> S3

    S1 --> GEMINI
    S2 --> GEMINI
    S3 --> GEMINI
    S1 -.->|optional| GROK

    S3 --> HTML_TEMP
    HTML_TEMP --> HTML_FINAL
```

---

## Module Map

```
LLMUsage/
│
├── StartupFinderApp.py              ← Entry point · Tkinter GUI · orchestrates all 3 stages
│
├── GetSeedStartups5.py              ← Stage 1: Startup discovery pipeline
│   ├── get_similar_business()           Find related sectors
│   ├── find_seed_startups_workflow()    Multi-pass startup generation
│   ├── filter_startups_by_sector_workflow()  Classify + filter
│   ├── rationalize_simple_list()        Dedup + LLM batch rationalisation
│   ├── get_sector_correlations()        Score sector relevance
│   ├── validate_classifications_with_grok()   (mock hook)
│   ├── reclassify_others_with_grok()    (mock hook)
│   └── call_gemini_api_with_retry()     Core retry wrapper
│
├── InvestmentParametersGenerator.py ← Stage 2: Generate ranked investment parameters
│   └── get_investment_parameters()      Gemini call → ordered JSON list
│
├── PopulateData.py                  ← Stage 3: Per-startup research + HTML output
│   ├── populate_data()                  Main loop: one Gemini call per startup
│   ├── save_to_html()                   Render batch to HTML table
│   └── merge_html_files()               Combine batch files into final report
│
└── Output Data/                     ← Generated HTML reports (gitignored)
    ├── sector_geo_1_debug.html          Intermediate batch files
    ├── sector_geo_2_debug.html
    └── sector_geo.html                  Final merged report
```

---

## Class Diagram

```
classDiagram
    class StartupFinderApp {
        +root: tk.Tk
        +gemini_model: str
        +api_key_entry: tk.Entry
        +sector_entry: tk.Entry
        +geo_entry: tk.Entry
        +n_startups_var: IntVar
        +n_params_var: IntVar
        +startup_results_text: ScrolledText
        +parameters_results_text: ScrolledText
        +log_text: ScrolledText
        +start_search_thread()
        +run_search()
        +update_startup_results(success, result)
        +update_parameter_results(success, result)
        +update_log_results(success, result)
        +load_api_key_from_env()
        +update_gemini_model(selection)
    }

    class SimilarResponse {
        +similar_business: List~str~
    }

    class StartupsResponse {
        +startups: List~str~
    }

    class Classification {
        +company_name: str
        +primary_sector: str
    }

    class ClassificationsResponse {
        +classifications: List~Classification~
    }

    class RationalizedName {
        +original_names: List~str~
        +rationalized_name: str
    }

    class RationalizationResponse {
        +rationalized_entities: List~RationalizedName~
    }

    class CorrelationScore {
        +sector: str
        +correlation_score: float
    }

    class CorrelationResponse {
        +correlations: List~CorrelationScore~
    }

    ClassificationsResponse "1" --> "0..*" Classification
    RationalizationResponse "1" --> "0..*" RationalizedName
    CorrelationResponse "1" --> "0..*" CorrelationScore

    StartupFinderApp ..> StartupsResponse : uses
    StartupFinderApp ..> ClassificationsResponse : uses
    StartupFinderApp ..> RationalizationResponse : uses
    StartupFinderApp ..> CorrelationResponse : uses
```

---

## End-to-End Data Flow

```
flowchart TD
    USER(["👤 User\nsector + geo + n_startups + n_params"])

    USER --> S1

    subgraph S1["Stage 1 · GetSeedStartups5"]
        A1["get_similar_business()\n→ SimilarResponse"]
        A2["find_seed_startups_workflow()\nMulti-pass → StartupsResponse × N"]
        A3["Merge + deduplicate\ncandidate pool"]
        A4["filter_startups_by_sector_workflow()\n→ ClassificationsResponse × batches"]
        A5["rationalize_simple_list()\nRule-based → LLM batch → RationalizationResponse"]
        A6["get_sector_correlations()\n→ CorrelationResponse"]
        A1 --> A2 --> A3 --> A4 --> A5 --> A6
    end

    A6 --> STARTUPS[("✅ Final startup list\nList~str~")]

    STARTUPS --> S2

    subgraph S2["Stage 2 · InvestmentParametersGenerator"]
        B1["get_investment_parameters()\nContext-aware prompt\n→ JSON {parameters: List~str~}"]
    end

    B1 --> PARAMS[("✅ Ranked parameter list\nList~str~  (N items)")]

    STARTUPS & PARAMS --> S3

    subgraph S3["Stage 3 · PopulateData"]
        C1["For each startup:\nGemini prompt with all parameters\n→ JSON {param: {summary, sources}}"]
        C2["JSON self-repair\n(backslash / quote fixes)"]
        C3["save_to_html(batch)\n→ _debug.html every 4 startups"]
        C4["merge_html_files()\n→ final sector_geo.html"]
        C1 --> C2 --> C3 --> C4
    end

    C4 --> REPORT(["📄 HTML Report\nStartup × Parameter matrix\nwith summaries + source links"])
```

---

## Interaction Diagrams

### Stage 1: Startup Discovery

```
sequenceDiagram
    participant APP as StartupFinderApp
    participant GSS as GetSeedStartups5
    participant GEMINI as Gemini API

    APP->>GSS: get_similar_business(area, geo, model)
    GSS->>GEMINI: prompt: "find sectors similar to {area}"
    GEMINI-->>GSS: SimilarResponse {similar_business: [...]}
    GSS-->>APP: (True, ["FinTech", "MSME Lending", ...])

    APP->>GSS: find_seed_startups_workflow(area, geo, target, model)
    loop Until target reached or max passes
        GSS->>GEMINI: prompt: "find startups in {area} in {geo}"
        GEMINI-->>GSS: StartupsResponse {startups: [...]}
        GSS->>GSS: merge + deduplicate
    end
    GSS-->>APP: (True, [500 startup names])

    APP->>GSS: filter_startups_by_sector_workflow(startups, area, similar, target, model)
    loop Batches of ~50
        GSS->>GEMINI: prompt: "classify these companies by sector"
        GEMINI-->>GSS: ClassificationsResponse {classifications: [...]}
    end
    GSS->>GSS: rationalize_simple_list()
    note over GSS: Rule-based: first-word dedup
    loop Batches of 100
        GSS->>GEMINI: prompt: "rationalise duplicate names"
        GEMINI-->>GSS: RationalizationResponse
    end
    GSS->>GEMINI: get_sector_correlations()
    GEMINI-->>GSS: CorrelationResponse {correlations: [...]}
    GSS-->>APP: (True, final_list), all_classified_dict
```

---

### Stage 2: Investment Parameters

```
sequenceDiagram
    participant APP as StartupFinderApp
    participant IPG as InvestmentParametersGenerator
    participant GEMINI as Gemini API

    APP->>IPG: get_investment_parameters(api_key, startup_list, area, geo, model, nParameters)
    note over IPG: Builds context-rich prompt with\nexample parameters + ordering instruction
    IPG->>GEMINI: prompt: "generate {N} ranked investment parameters\nfor {area} in {geo}"
    GEMINI-->>IPG: JSON {"parameters": ["Param1", "Param2", ...]}
    IPG->>IPG: json.loads() + validate list length
    IPG-->>APP: (True, ["Param1", "Param2", ... "ParamN"])
```

---

### Stage 3: Data Population

```
sequenceDiagram
    participant APP as StartupFinderApp
    participant PD as PopulateData
    participant GEMINI as Gemini API
    participant FS as File System

    APP->>PD: populate_data(api_key, startup_list, parameter_list, area, geo, model, log_widget)

    loop For each startup (i of N)
        PD->>GEMINI: prompt: "populate {parameters} for {startup_name}"
        GEMINI-->>PD: JSON {param: {summary, sources}}

        alt JSON valid
            PD->>PD: store in batch_data + all_startup_data
        else JSON malformed
            PD->>PD: attempt backslash repair
            PD->>PD: attempt single-quote key repair
            alt repair succeeds
                PD->>PD: store repaired data
            else repair fails
                PD->>PD: store error record
            end
        end

        PD->>PD: time.sleep(5)

        alt Every 4 startups OR last startup
            PD->>FS: save_to_html(batch_data) → sector_geo_N_debug.html
            PD->>PD: reset batch_data
            PD->>PD: time.sleep(120)  ← rate limit guard
        end
    end

    PD->>FS: merge_html_files() → sector_geo.html
    PD->>FS: delete _debug.html temp files
    PD-->>APP: (True, {startup_data: all_startup_data})
```

---

### GUI Thread Interaction

```
sequenceDiagram
    participant USER as User
    participant GUI as StartupFinderApp (Main Thread)
    participant BG as Background Thread

    USER->>GUI: Click "Generate Full Report"
    GUI->>GUI: Disable button
    GUI->>GUI: Clear all output panels
    GUI->>BG: threading.Thread(target=run_search).start()

    BG->>BG: Stage 1: get_top_startups()
    BG->>GUI: root.after(0, update_startup_results)
    GUI-->>USER: Startup list displayed

    BG->>BG: Stage 2: get_investment_parameters()
    BG->>GUI: root.after(0, update_parameter_results)
    GUI-->>USER: Parameter list displayed

    BG->>BG: Stage 3: populate_data()
    loop Per startup
        BG->>GUI: log_widget.after(0, insert log line)
        GUI-->>USER: Live log update
    end

    BG->>GUI: root.after(0, update_log_results)
    GUI->>GUI: Re-enable button
    GUI-->>USER: Success dialog + HTML report path
```

---

## LLM Orchestration Design

### Structured Output Contracts

Every Gemini call is paired with a **Pydantic model** that validates the response before it enters the pipeline. If the model returns malformed JSON, the system attempts salvage before failing.

| Call | Pydantic Contract | Fallback |
|---|---|---|
| Similar sectors | `SimilarResponse` | Abort stage |
| Startup generation | `StartupsResponse` | `salvage_startup_names()` via regex |
| Classification | `ClassificationsResponse` | `salvage_classifications()` via regex |
| Name rationalisation | `RationalizationResponse` | Keep names as-is |
| Sector correlation | `CorrelationResponse` | Default all scores to 0.0 |
| Parameter generation | Raw JSON dict | Return error |
| Per-startup research | Raw JSON dict | Backslash repair → quote repair → error record |

### Retry Logic

`call_gemini_api_with_retry()` implements exponential backoff:

```
flowchart LR
    CALL["API Call\n(attempt N)"] --> CHECK{Success?}
    CHECK -->|Yes| RETURN["Return result"]
    CHECK -->|ResourceExhausted\nor ServiceUnavailable| WAIT["Sleep delay × 2\n(exponential backoff)"]
    WAIT --> RETRY{Attempts\n< max_retries?}
    RETRY -->|Yes| CALL
    RETRY -->|No| FAIL["Return error"]
    CHECK -->|Other exception| FAIL
```

### Rate Limit Management

`PopulateData` manages three API rate limits:

| Limit | Mitigation |
|---|---|
| **TPM** (tokens/min) | `time.sleep(5)` between every startup |
| **RPM** (requests/min) | Batch size of 4; `time.sleep(120)` between batches |
| **RPD** (requests/day) | Intermediate HTML checkpointing — partial results are never lost |

### Multi-Model Design

The system is architected for two-model validation. Grok hooks are implemented and stubbed:

- `validate_classifications_with_grok()` — cross-checks Gemini's sector classifications
- `reclassify_others_with_grok()` — attempts to reclassify companies that fell into "Other"

Enable by setting `grokEnabled = True` in `GetSeedStartups5.py` and providing a live Grok API implementation.

---

## Error Handling & Resilience

```
flowchart TD
    API["Gemini API Call"] --> RESP{Response OK?}
    RESP -->|Blocked / Empty| BLOCK["Log block reason\nStore error record\nContinue to next startup"]
    RESP -->|Valid JSON| PARSE["Parse + validate\nPydantic model"]
    RESP -->|Malformed JSON| REPAIR

    subgraph REPAIR["JSON Self-Repair Ladder"]
        R1["Try: strip markdown fences\n(```json ... ```)"]
        R2["Try: fix invalid backslash escapes\nre.sub for non-standard \\"]
        R3["Try: fix single-quoted keys\nre.sub for 'key':"]
        R4["Raise original error\n→ store error record"]
        R1 --> R2 --> R3 --> R4
    end

    PARSE --> USE["Use data"]
    REPAIR --> USE
    BLOCK --> NEXT["Next startup"]
    R4 --> NEXT
```

---

## Output Format

The final HTML report is a **startup × parameter matrix**:

- **Rows**: one per startup, with the startup name in the first column (blue, bold, centred)
- **Columns**: one per investment parameter, in descending order of importance (as ranked by Gemini)
- **Each cell**: a ≤50-word summary + numbered clickable source links
- **Headers**: black background, white text

The report opens directly in any browser and can be imported into Excel for further analysis.

---

## Installation

```bash
# Clone
git clone https://github.com/UBags/LLMUsage.git
cd LLMUsage

# Virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows

# Install dependencies
pip install google-generativeai pydantic python-dotenv requests
```

### API Key

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_api_key_here
```

Get a key at [https://aistudio.google.com/](https://aistudio.google.com/).

---

## Usage

### Option A — GUI (recommended)

```bash
python StartupFinderApp.py
```

1. Enter your Gemini API key (or load from `.env`)
2. Choose model: **Flash** (free, fast) or **Pro** (paid, higher quality)
3. Enter **Sector** and **Geography**
4. Set number of startups (3–200) and parameters (15–75)
5. Click **Generate Full Report**
6. Find the HTML report in `Output Data/`

### Option B — Command line (Stage 1 only)

Edit the configuration block at the bottom of `GetSeedStartups5.py`:

```python
search_area = "Supply-Chain Finance"
search_geo  = "India"
initial_target = 500
final_target   = 150
model = "gemini-2.5-pro"
grokEnabled = False
```

Then run:

```bash
python GetSeedStartups5.py
```

---

## Configuration

| Parameter | Location | Default | Description |
|---|---|---|---|
| `search_area` | `GetSeedStartups5.py` | `"Supply-Chain Finance"` | Primary sector to search |
| `search_geo` | `GetSeedStartups5.py` | `"India"` | Geography |
| `initial_target` | `GetSeedStartups5.py` | `500` | Initial candidate pool size |
| `final_target` | `GetSeedStartups5.py` | `150` | Target after filtering |
| `model` | `GetSeedStartups5.py` | `"gemini-2.5-pro"` | Gemini model name |
| `grokEnabled` | `GetSeedStartups5.py` | `False` | Enable Grok validation pass |
| `nParameters` | `InvestmentParametersGenerator.py` | `40` | Number of investment parameters |
| Batch size | `PopulateData.py` | `4` | Startups per intermediate save |
| Inter-startup sleep | `PopulateData.py` | `5s` | Rate limit guard per startup |
| Inter-batch sleep | `PopulateData.py` | `120s` | Rate limit guard per batch |

---

*Developed by CosTheta Technologies Pvt Ltd.*
*Copyright © 2025 Uddipan Bagchi. All rights reserved.*
