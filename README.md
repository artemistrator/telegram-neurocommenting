# Project Documentation and File Overview

This document provides a comprehensive overview of the LeadRadar Telegram Automation project. It details the purpose of each file, its interactions, and its status (Active vs. Legacy).

## Project Architecture

The project is a Telegram automation system designed to parse channels, monitor keywords, and automate commenting.

*   **Backend Framework**: FastAPI (`backend/main.py`)
*   **Database & CMS**: Directus (Headless CMS + PostgreSQL)
*   **Telegram Client**: Telethon (Python)
*   **Frontend**: HTML/JS (Vanilla + Tailwind) served by FastAPI.

The system uses a **micro-worker architecture**: specific background tasks (parsing, commenting, subscribing) are handled by dedicated worker scripts in `backend/workers/` that communicate via the Directus database.

---

## 📂 Backend (`backend/`)

The core logic of the application has been moved to this directory.

### Core Files
*   **`backend/main.py`**
    *   **Role**: The entry point of the FastAPI application.
    *   **Functionality**:
        *   Initializes the FastAPI app and CORS settings.
        *   Mounts static files (`/static`) and serves HTML pages (`/`).
        *   Includes routers from `backend/routers/`.
        *   Manages the **Telegram Monitor** subprocess (`monitor.py`) via API endpoints (`/api/monitor/...`).
        *   **Interactions**: Imports routers, `monitor.py` (subprocess), and uses `DirectusClient`.
*   **`backend/directus_client.py`**
    *   **Role**: A singleton wrapper for the Directus API.
    *   **Functionality**: Handles authentication (login), token management, and provides helper methods (`get`, `post`, `update_item`, `create_item`) for interacting with Directus collections.
    *   **Interactions**: Used by **all** routers and workers to read/write data.

### 🔌 Routers (`backend/routers/`)
Directus-integrated API endpoints serving the frontend.

*   **`accounts.py`**
    *   **Role**: Manages Telegram accounts.
    *   **Functionality**: List accounts, import from ZIP, manual creation, delete, proxy assignment, setup triggering, and profile refreshing (syncing name/avatar from Telegram).
    *   **Interactions**: Reads/Writes to `accounts` and `proxies` collections in Directus. Uses `Telethon` for profile refreshing.
*   **`dashboard.py`**
    *   **Role**: Provides statistics for the main dashboard.
    *   **Functionality**: Aggregates data like total leads, active accounts, messages sent.
    *   **Interactions**: Read-only access to `found_posts`, `accounts`, `server_logs`.
*   **`parser_router.py`**
    *   **Role**: API for the Parser page.
    *   **Functionality**: Manage search keywords, fetch found channels, and add them to the monitoring list.
    *   **Interactions**: Reads/Writes `search_keywords`, `found_channels`, `channels`.
*   **`proxies.py`**
    *   **Role**: Proxy management.
    *   **Functionality**: CRUD operations for proxies, import from text, check connectivity.
    *   **Interactions**: Reads/Writes `proxies` collection.
*   **`templates.py`**
    *   **Role**: AI Persona/Template management.
    *   **Functionality**: CRUD for setup templates (which include commenting styles, prompts, and bio info).
    *   **Interactions**: Reads/Writes `setup_templates` collection.

### 👷 Workers (`backend/workers/`)
Standalone scripts designed to run periodically or permanently in the background.

*   **`subscription_worker.py`**
    *   **Role**: Manages joining Telegram channels.
    *   **Functionality**:
        *   Fetches `subscription_queue` items.
        *   Uses `found_channels` to find targets.
        *   Distributes joining tasks among active `commenter` accounts.
        *   Handles rate limits and delays.
        *   Supports a **MOCK_MODE** (`dry run`) and **REAL** mode (Telethon).
    *   **Interactions**: `subscription_queue`, `accounts`, `found_channels`, `channels`.
*   **`parser_worker.py`**
    *   **Role**: "Listener" logic integration.
    *   **Functionality**:
        *   Identifies unprocessed `parsed_posts` (status='published').
        *   Filters posts based on keywords defined in templates.
        *   Generates comments (via AI/Templates) and adds them to `comment_queue`.
    *   **Interactions**: `parsed_posts`, `comment_queue`, `setup_templates`.
*   **`commenting_worker.py`**
    *   **Role**: Executes the actual commenting.
    *   **Functionality**:
        *   Reads `comment_queue` (pending items).
        *   Logs into the assigned Telegram account.
        *   Posts the generated comment to the target channel/post.
    *   **Interactions**: `comment_queue`, `accounts`.
*   **`search_parser_worker.py`**
    *   **Role**: Searches for NEW channels globally.
    *   **Functionality**:
        *   Uses `search_keywords` to search Telegram global search.
        *   Filters results (subscriber count, etc.).
        *   Saves new discoveries to `found_channels`.
    *   **Interactions**: `search_keywords`, `found_channels`.
*   **`setup_worker.py`**
    *   **Role**: Automates account setup (Warmup/Initialization).
    *   **Functionality**:
        *   Watches for accounts with `setup_status='pending'`.
        *   Applies profile info (Bio, Avatar, Name) from the linked `setup_template`.
        *   Creating a personal channel for the account if required.
    *   **Interactions**: `accounts`, `setup_templates`.
*   **`import_worker.py`**
    *   **Role**: Bulk account importer (Legacy/Alternative).
    *   **Functionality**: Processes ZIP files or folders of `.session` files and adds them to the DB. (Note: `backend/routers/accounts.py` now handles ZIP import directly in the API, so this might be for background/large batch ops).
*   **`listener_worker.py`**
    *   **Role**: Listens to incoming messages in monitored channels.
    *   **Functionality**: Connects "Listener" accounts to channels and saves incoming posts to `parsed_posts`.
*   **`account_health_checker.py`**
    *   **Role**: Periodic health check.
    *   **Functionality**: Verifies if accounts are still valid/alive and updates their status in Directus.

---

## 💻 Frontend

### Pages (`pages/`)
HTML templates served by FastAPI. They provide the structure for the SPA (Single Page App) feel.
*   **`layout.html`**: Master template with sidebar and Javascript resource links.
*   **`accounts.html`**: Account management table and modals.
*   **`channels.html`**: Monitored channels list.
*   **`parser.html`**: Search parser interface (Keywords & Found Channels).
*   **`proxies.html`**: Proxy list and import.
*   **`settings.html`**: Global application settings.
*   **`subscriber.html`**: Dashboard for the subscription worker queue.
*   **`templates.html`**: AI Persona/Template editor.
*   **`dashboard.html`**: Main overview stats.
*   **`home.html`**: Landing/Welcome content.

### Static Assets (`static/`)
*   **`script.js`**: Global app logic, router (loading pages into content area), and sidebar navigation handling.
*   **`js/pages/`**: Specific logic for each page.
    *   **`accounts.page.js`**: Handles account table rendering, import logic, and calls to `backend/routers/accounts.py`.
    *   **`parser.page.js`**: Logic for adding keywords and reviewing found channels.
    *   **`templates.page.js`**, **`template.modal.js`**, **`template.mapper.js`**: Complex logic for the Template editor UI.
    *   **`channels.page.js`**, **`settings.page.js`**: Page-specific controllers.

---

## 📄 Root Directory Files

### 🟢 Active System Files
*   **`monitor.py`**
    *   **Status**: **ACTIVE**
    *   **Role**: The core Telegram Monitoring script.
    *   **Functionality**: It runs as a subprocess (managed by `backend/main.py`). It connects to Telegram, listens for messages in configured chats, applies keyword/AI filtering, and sends events back to the API/Webhook.

### 🟡 Transitional / Shared
*   **`account_manager.py`**
    *   **Status**: **PARTIALLY ACTIVE / LEGACY**
    *   **Role**: Originally the main class for managing local SQLite database accounts.
    *   **Current Usage**: It is still imported by `backend/main.py` for some text-based endpoints (`/api/accounts/import-csv`), but the modern frontend primarily uses `backend/routers/accounts.py` (which uses Directus) for ZIP imports.
*   **`database.py`**
    *   **Status**: **LEGACY (SQLite)**
    *   **Role**: Handles the local `app.db` SQLite connection using `SQLModel`. The project has migrated to Directus, so this is likely only used by legacy scripts or `account_manager.py`.

### 🔴 Unused / Legacy / Utilities
The following files appear to be scripts for testing, migration, or old versions of the logic. They are likely **not** used by the running production system (Directus-based).

*   **`parser.py`**: A standalone script for parsing. Logic likely moved to `backend/workers/parser_worker.py`.
*   **`subscriber.py`**: Standalone subscription CLI tool. Logic moved to `backend/workers/subscription_worker.py`.
*   **`create_session.py`, `create_test_session.py`**: Helper scripts for manually creating Telethon sessions.
*   **`check_channel.py`**: Quick script to check if a channel exists/is valid.
*   **`test_connection.py`**: Connection tester.
*   **`reset_limit.py`, `restore_endpoint.py`, `fix_accounts_display.py`, `fix_routing.py`**: One-off maintenance scripts used during development/refactoring.
*   **`integrate_subscriber.py`**: Detailed script likely used to merge subscriber logic into the new backend.
*   **`app.db`**: The local SQLite database file. (Superseded by Directus).
*   **`accounts.json`**: Old flat-file storage for accounts.
*   **`telegram_session_*`**: Local session files. Real sessions are now often managed/imported via the worker logic or stored in `sessions/` folder managed by the new system.

---

## Directus Collections Overview (Data Model)
The system relies on these core collections:

| Collection Key | Purpose |
| :--- | :--- |
| **accounts** | Telegram accounts (Phone, Session, Status, Proxy Link, Limits). |
| **channels** | Channels being monitored for new posts (for Listener). |
| **comment_queue** | Outgoing comments waiting to be posted. |
| **commenting_profiles** | (Merged into `setup_templates`) Profile settings for commenting. |
| **found_channels** | Results from the Search Parser (candidates for subscription). |
| **found_posts** | Posts found by the Monitor that matched keywords. |
| **imports** | Logs of file imports. |
| **parsed_posts** | Valid posts extracted by the Listener worker. |
| **proxies** | Proxy servers (Host, Port, Auth) linked to accounts. |
| **search_keywords** | Keywords used by `search_parser_worker`. |
| **settings** | Global KV store for app settings. |
| **setup_templates** | AI Personas and profile configuration for accounts. |
| **subscription_queue** | Tasks for joining channels. |