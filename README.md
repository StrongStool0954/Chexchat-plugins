# HexChat Notification Plugins

A collection of HexChat plugins for IRC notifications via Pushover.

## Plugins

### 1. hexchat_position_monitor.py (v1.5)
Monitors queue position from Gatekeeper bot and sends notifications when your position changes.

**Features:**
- Auto-queries position every 30 minutes
- Sends notification on first check (to verify setup)
- Only notifies when position actually changes
- Auto-starts monitoring on plugin load

**Commands:**
- `/position_start` - Start monitoring
- `/position_stop` - Stop monitoring
- `/position_status` - Show current status and position
- `/position_check` - Manually check position now

**Configuration:**
Edit the top of the file to customize:
```python
POSITION_NICK = 'Gatekeeper'  # Nick to query
CHECK_INTERVAL = 1800  # Seconds between checks (30 min)
AUTO_START = True  # Auto-start on load
```

### 2. hexchat_gatekeeper_alerts.py (v1.2)
Monitors Gatekeeper for netsplit events and interview announcements.

**Features:**
- Alerts when Gatekeeper quits with netsplit pattern (*.net *.split)
- Alerts on interview announcements matching pattern

**Configuration:**
Edit the patterns at the top of the file:
```python
QUIT_REASON_PATTERN = re.compile(r'.*\.net \*\.split', re.IGNORECASE)
INTERVIEW_PATTERN = re.compile(r'Currently interviewing: ConQwest', re.IGNORECASE)
```

### 3. hexchat_privmsg_notify.py (v2.0)
Universal notification plugin for private messages and channel mentions.

**Features:**
- Notifies on any private message received
- Notifies when your nick is mentioned in any channel
- Optional exclude list for certain nicks (NickServ, etc.)
- Optional away-only mode

**Configuration:**
```python
EXCLUDED_NICKS = []  # Nicks to ignore
ONLY_NOTIFY_WHEN_AWAY = False  # Only notify when away
NOTIFY_ON_MENTIONS = True  # Enable mention detection
```

## Installation

1. Copy plugin files to: `~/.var/app/io.github.Hexchat/config/hexchat/addons/`
2. Configure Pushover credentials in each file
3. Restart HexChat or load manually:
   ```
   /load /path/to/plugin.py
   ```

## Requirements

- HexChat with Python plugin support
- Pushover account and app token

## Technical Details

All plugins use:
- Raw server PRIVMSG hooks for reliable message capture
- urllib for Pushover API (no subprocess dependencies)
- Proper error handling and logging

## Author

Created with Claude Code
