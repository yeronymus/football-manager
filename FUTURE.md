# Future Plans: Football Manager Mini App

## Goal
Transition the bot's core user interaction (Profile & History) from chat-based commands to a rich Telegram Mini App (WebView).

## Features to Migrate

### 1. Match History (`/my_history`)
- **Current State**: Text message with a list of last 10 games.
- **Future State**: Full-screen WebView.
- **Requirements**:
    - Display all past matches (infinite scroll or pagination).
    - Click on a match to see full details:
        - Score.
        - Team rosters (Team A vs Team B).
        - Goal scorers.
        - MVP.
    - Filter by date or location.

### 2. User Profile (`/my_profile`)
- **Current State**: Text message with stats + Inline Buttons for editing.
- **Future State**: Profile Screen in WebView.
- **Requirements**:
    - Visual display of User Stats (Goals, MVP, Matches, Rating graph).
    - **Edit Profile Form**:
        - Change Name (Text Input).
        - Change Position (Visual Selector).
        - Manage Alt Positions.
    - eliminating the need for chat-based FSM state machines for editing.

## Technical Implementation
- Develop new views in `app/web/` (e.g., `profile.html`, `history.html`).
- Use `Telegram.WebApp` to fetch user data via `initData`.
- Create API endpoints:
    - `GET /api/user/profile`
    - `POST /api/user/profile` (Update)
    - `GET /api/user/history`
    - `GET /api/game/{id}`
- Configure BotFather to use the Main Menu Button to launch the App instead of commands (optional, or hybrid).
