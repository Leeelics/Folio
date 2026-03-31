# Generate Hierarchical AGENTS.md Files

## TL;DR

Generate hierarchical AGENTS.md knowledge base for the Folio project:
- Update root `./AGENTS.md` with expanded structure
- Create `./app/services/AGENTS.md` - service layer patterns
- Create `./app/api/AGENTS.md` - API route conventions  
- Create `./app/models/AGENTS.md` - domain model patterns
- Create `./streamlit_app/pages/AGENTS.md` - UI page patterns
- Create `./tests/AGENTS.md` - testing patterns & fixtures

## Context

### Project Overview
- **Name**: Folio - Personal Financial Management System
- **Stack**: FastAPI + Streamlit + PostgreSQL + Python 3.11+
- **Size**: 62 Python files, ~18,613 lines of code
- **Structure**: Backend (`app/`) + Frontend (`streamlit_app/`) + Tests (`tests/`)

### Existing Documentation
- `AGENTS.md` exists at root (35 lines) - needs expansion
- `CLAUDE.md` exists at root (183 lines) - comprehensive reference

### Directory Scores (for AGENTS.md placement)
| Directory | Files | Score | Action |
|-----------|-------|-------|--------|
| . (root) | - | ∞ | Update existing |
| app/services | 15 | 18 | Create new |
| app/api | 9 | 16 | Create new |
| app/models | 7 | 12 | Create new |
| streamlit_app/pages | 7 | 12 | Create new |
| tests | 8 | 11 | Create new |

## Work Objectives

### Core Objective
Generate 6 AGENTS.md files (1 update + 5 new) to create a hierarchical knowledge base that guides AI agents working on different parts of the codebase.

### Concrete Deliverables
1. `./AGENTS.md` (updated) - Root repository guidelines
2. `./app/services/AGENTS.md` - Service layer conventions
3. `./app/api/AGENTS.md` - API routing patterns
4. `./app/models/AGENTS.md` - Model/domain patterns
5. `./streamlit_app/pages/AGENTS.md` - Streamlit page patterns
6. `./tests/AGENTS.md` - Testing conventions

### Definition of Done
- [ ] All 6 AGENTS.md files exist with correct content
- [ ] Root AGENTS.md references all subdir guides
- [ ] No duplicate content between parent/child files
- [ ] Each file is 50-150 lines (root) or 30-80 lines (subdirs)
- [ ] Files follow telegraphic style (no fluff)

### Must Have
- Project structure overview
- Conventions specific to this project
- Anti-patterns and warnings
- Quick reference commands
- Cross-references between files

### Must NOT Have
- Generic Python/FastAPI advice
- Content duplicated from CLAUDE.md
- Tutorial-style explanations
- Boilerplate that applies to all projects

## Verification Strategy

### QA Scenarios
1. **File Creation Verification**: `ls -la` shows all 6 AGENTS.md files
2. **Content Validation**: Each file has required sections
3. **Cross-reference Check**: Root file links to all subdir files
4. **Size Check**: No file exceeds max line limits

## Execution Strategy

### Wave 1: Root AGENTS.md (Sequential - Foundation)
Update root AGENTS.md with:
- Quick reference table
- Project structure diagram
- Subdirectory guide links
- Architecture patterns
- Development workflow

### Wave 2: Subdirectory AGENTS.md Files (Parallel)
Generate 5 subdirectory files simultaneously:

**Wave 2A: Backend Services**
- `app/services/AGENTS.md` - AssetManager, InvestmentManager patterns
- `app/api/AGENTS.md` - Route organization, dependency injection

**Wave 2B: Data Layer**
- `app/models/AGENTS.md` - SQLAlchemy 2.0 patterns, domain splits

**Wave 2C: Frontend & Tests**
- `streamlit_app/pages/AGENTS.md` - Page naming, API client usage
- `tests/AGENTS.md` - Test patterns, fixtures, async DB setup

### Wave 3: Validation (Sequential)
- Verify all files created
- Check cross-references work
- Ensure no duplication
- Validate size constraints

## TODOs

### Wave 1: Root AGENTS.md

- [x] 1. Update root AGENTS.md with hierarchical structure

  **What to do**:
  - Read existing `./AGENTS.md` and `./CLAUDE.md`
  - Create expanded root guide with:
    - Quick reference command table
    - Project structure tree
    - Links to subdirectory guides
    - Architecture patterns (Backend/Frontend/Database)
    - Development workflow
    - External API reference
  - Include "Subdirectory Guides" section linking to all child AGENTS.md files
  - Add "Phase Status" section from CLAUDE.md
  
  **Must NOT do**:
  - Duplicate detailed API endpoint lists from CLAUDE.md
  - Include generic Python advice
  - Exceed 150 lines
  
  **References**:
  - `./AGENTS.md` - existing guidelines to preserve
  - `./CLAUDE.md` - source for phase status, workflow, API reference
  - `./pyproject.toml` - commands and scripts
  
  **Acceptance Criteria**:
  - [ ] File exists at `./AGENTS.md`
  - [ ] Contains "Subdirectory Guides" section with 5 links
  - [ ] Contains quick reference table with 6+ commands
  - [ ] 50-150 lines total
  - [ ] Preserves existing critical guidelines
  
  **QA Scenarios**:
  ```
  Scenario: Root AGENTS.md structure validation
    Tool: Bash (cat/head/grep)
    Steps:
      1. cat ./AGENTS.md | head -20
      2. grep -c "Subdirectory Guides" ./AGENTS.md
      3. grep -c "app/api/AGENTS.md" ./AGENTS.md
      4. wc -l ./AGENTS.md
    Expected: 
      - File exists
      - "Subdirectory Guides" found (count >= 1)
      - At least 5 subdirectory links present
      - Line count between 50-150
  ```
  
  **Commit**: YES
  - Message: `docs: expand root AGENTS.md with hierarchical structure`
  - Files: `AGENTS.md`

### Wave 2: Subdirectory AGENTS.md Files (Parallel)

- [x] 2. Create app/services/AGENTS.md

  **What to do**:
  - Create service layer guide covering:
    - Service module organization (14 services)
    - Key services: AssetManager, InvestmentManager, BrokerageAccountService
    - External API integration patterns (OKX, Tushare, AkShare)
    - Error handling for external APIs
    - Currency conversion patterns
  - Document service dependencies and initialization
  
  **Must NOT do**:
  - Document implementation details of each service
  - Include full class signatures
  - Duplicate API route info from api/AGENTS.md
  
  **References**:
  - `./app/services/` - 15 files
  - `./app/services/asset_manager.py` - OKX integration, exchange rates
  - `./app/services/investment_manager.py` - Portfolio logic
  - `./app/services/stock_client.py` - Market data clients
  
  **Acceptance Criteria**:
  - [ ] File exists at `./app/services/AGENTS.md`
  - [ ] Documents 3-5 key services
  - [ ] Includes external API integration patterns
  - [ ] 30-80 lines
  
  **QA Scenarios**:
  ```
  Scenario: Services guide validation
    Tool: Bash (test -f, wc, grep)
    Steps:
      1. test -f ./app/services/AGENTS.md
      2. wc -l ./app/services/AGENTS.md
      3. grep -c "AssetManager\|InvestmentManager" ./app/services/AGENTS.md
    Expected: File exists, 30-80 lines, mentions key services
  ```
  
  **Commit**: YES (grouped)

- [x] 3. Create app/api/AGENTS.md

  **What to do**:
  - Create API routing guide covering:
    - 8 route files organization
    - Feature-based routing pattern
    - Router registration in main.py
    - Pydantic model patterns for request/response
    - Dependency injection (get_db)
    - Route naming conventions
  - List route files and their domains
  
  **Must NOT do**:
  - List all endpoints (that's in CLAUDE.md)
  - Include full CRUD examples
  - Document service logic
  
  **References**:
  - `./app/api/` - 9 files
  - `./app/api/core_routes.py` - Main routes pattern
  - `./app/api/investment_routes.py` - Investment domain
  - `./app/main.py` - Router registration
  
  **Acceptance Criteria**:
  - [ ] File exists at `./app/api/AGENTS.md`
  - [ ] Lists all 8 route files with domains
  - [ ] Documents router registration pattern
  - [ ] 30-80 lines
  
  **QA Scenarios**:
  ```
  Scenario: API guide validation
    Tool: Bash (test, wc, grep)
    Steps:
      1. test -f ./app/api/AGENTS.md
      2. grep -c "core_routes\|investment_routes\|stock_routes" ./app/api/AGENTS.md
    Expected: File exists, mentions key route files
  ```
  
  **Commit**: YES (grouped)

- [x] 4. Create app/models/AGENTS.md

  **What to do**:
  - Create domain model guide covering:
    - Domain-driven file split (6 model files)
    - SQLAlchemy 2.0 patterns (Mapped, mapped_column)
    - Core entities: Account, Holding, Transaction
    - Investment entities: Stock, Brokerage
    - Relationship patterns
  - Document model organization rationale
  
  **Must NOT do**:
  - Include full table schemas (in init.sql)
  - Document every column
  - Include migration patterns
  
  **References**:
  - `./app/models/` - 7 files
  - `./app/models/core.py` - Base entities
  - `./app/models/investment.py` - Investment models
  - `./app/models/brokerage.py` - Brokerage models
  
  **Acceptance Criteria**:
  - [ ] File exists at `./app/models/AGENTS.md`
  - [ ] Documents domain file organization
  - [ ] Mentions SQLAlchemy 2.0 patterns
  - [ ] 30-80 lines
  
  **QA Scenarios**:
  ```
  Scenario: Models guide validation
    Tool: Bash (test, wc, grep)
    Steps:
      1. test -f ./app/models/AGENTS.md
      2. grep -c "core.py\|investment.py\|SQLAlchemy" ./app/models/AGENTS.md
    Expected: File exists, mentions key model files
  ```
  
  **Commit**: YES (grouped)

- [x] 5. Create streamlit_app/pages/AGENTS.md

  **What to do**:
  - Create Streamlit pages guide covering:
    - Numbered naming convention (1_Assets.py → 7_Reports.py)
    - Page structure and imports
    - API client usage patterns
    - Session state management
    - Plotly/pandas integration
  - Document page organization and navigation
  
  **Must NOT do**:
  - Include full page implementations
  - Document Streamlit basics
  - Include CSS/styling details
  
  **References**:
  - `./streamlit_app/pages/` - 7 active + archive
  - `./streamlit_app/pages/1_Assets.py` - Example page
  - `./streamlit_app/api_client.py` - HTTP client
  
  **Acceptance Criteria**:
  - [ ] File exists at `./streamlit_app/pages/AGENTS.md`
  - [ ] Documents numbered naming convention
  - [ ] Mentions API client patterns
  - [ ] Warns about _archive/ folder
  - [ ] 30-80 lines
  
  **QA Scenarios**:
  ```
  Scenario: Pages guide validation
    Tool: Bash (test, wc, grep)
    Steps:
      1. test -f ./streamlit_app/pages/AGENTS.md
      2. grep -c "1_Assets\|api_client\|_archive" ./streamlit_app/pages/AGENTS.md
    Expected: File exists, mentions key patterns and archive warning
  ```
  
  **Commit**: YES (grouped)

- [x] 6. Create tests/AGENTS.md

  **What to do**:
  - Create testing guide covering:
    - Two-tier testing strategy (unit vs integration)
    - Async test database pattern (aiosqlite + StaticPool)
    - Playwright E2E tests
    - Fixture organization
    - Test naming conventions
  - Document test file purposes
  
  **Must NOT do**:
  - Include full test examples
  - Document pytest basics
  - Include coverage requirements
  
  **References**:
  - `./tests/` - 8 test files
  - `./tests/test_api.py` - Async integration pattern
  - `./tests/test_e2e.py` - Playwright E2E
  - `./pyproject.toml` - Test dependencies
  
  **Acceptance Criteria**:
  - [ ] File exists at `./tests/AGENTS.md`
  - [ ] Documents async DB test pattern
  - [ ] Lists 8 test files with purposes
  - [ ] Mentions Playwright E2E
  - [ ] 30-80 lines
  
  **QA Scenarios**:
  ```
  Scenario: Tests guide validation
    Tool: Bash (test, wc, grep)
    Steps:
      1. test -f ./tests/AGENTS.md
      2. grep -c "test_api.py\|test_e2e.py\|aiosqlite" ./tests/AGENTS.md
    Expected: File exists, mentions key test files and patterns
  ```
  
  **Commit**: YES (grouped)

### Wave 3: Final Validation

- [ ] 7. Validate all AGENTS.md files

  **What to do**:
  - Verify all 6 files exist
  - Check file sizes (root: 50-150, subdirs: 30-80)
  - Verify cross-references in root file
  - Check for duplicate content
  - Ensure telegraphic style
  
  **Acceptance Criteria**:
  - [ ] All 6 files exist
  - [ ] Root file links to all 5 subdirs
  - [ ] No file exceeds line limits
  - [ ] No obvious duplication
  
  **QA Scenarios**:
  ```
  Scenario: Complete validation
    Tool: Bash (find, wc, grep)
    Steps:
      1. find . -name "AGENTS.md" -type f | wc -l
      2. wc -l ./AGENTS.md ./app/*/AGENTS.md ./streamlit_app/pages/AGENTS.md ./tests/AGENTS.md 2>/dev/null
      3. grep "AGENTS.md" ./AGENTS.md | wc -l
    Expected: 6 files, sizes within limits, cross-references present
  ```
  
  **Commit**: YES (if fixes needed)

## Final Verification Wave

- [ ] F1. File existence check - verify all 6 AGENTS.md files exist
- [ ] F2. Content validation - each file has required sections
- [ ] F3. Cross-reference validation - root links to all children
- [ ] F4. Size validation - no file exceeds limits

## Commit Strategy

1. **Wave 1 commit**: `docs: expand root AGENTS.md with hierarchical structure`
2. **Wave 2 commit**: `docs: add subdirectory AGENTS.md guides`
3. **Wave 3 commit** (if needed): `docs: fix AGENTS.md validation issues`

## Success Criteria

### Verification Commands
```bash
# File existence
find . -name "AGENTS.md" -type f | wc -l  # Expected: 6

# Root file links to subdirs
grep "AGENTS.md" ./AGENTS.md | grep -c "app/\|streamlit/\|tests/"  # Expected: >=5

# Size checks
wc -l ./AGENTS.md  # Expected: 50-150
wc -l ./app/services/AGENTS.md ./app/api/AGENTS.md ./app/models/AGENTS.md  # Expected: 30-80 each
```

### Final Checklist
- [ ] 6 AGENTS.md files exist
- [ ] Root file links to all 5 subdirectories
- [ ] No file exceeds line limits
- [ ] No duplicate content between files
- [ ] Telegraphic style maintained
