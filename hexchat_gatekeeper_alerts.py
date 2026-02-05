import hexchat
import subprocess
import re
import os
import urllib.request
import urllib.parse

# Define pattern for netsplit detection
# This matches the "*.net *.split" phrase commonly seen during server splits
QUIT_REASON_PATTERN = re.compile(
    r'.*\.net \*\.split',
    re.IGNORECASE
)

# Define pattern for interview notification
# This matches "Currently interviewing: ConQwest"
INTERVIEW_PATTERN = re.compile(
    r'Currently interviewing: ConQwest',
    re.IGNORECASE
)

# Pushover alerting module
__module_name__ = 'gatekeeper_alerts'
__module_version__ = '1.2'
__module_description__ = 'Alerts when Gatekeeper quits with netsplit or posts interview messages'

# PUSHOVER CREDENTIALS - Configured locally (not in git)
PUSHOVER_APP_TOKEN = 'au3h6frhkc6vpb9ot2hjw7izzvkg57'
PUSHOVER_USER_TOKEN = 'uqmniwsjk1pre1pzj18rxrjmm8e8hy'

# --- HELPER FUNCTIONS ---

def send_pushover_message(message, title='Gatekeeper Alert', sound='siren'):
    """Sends an alert message to Pushover."""
    if not PUSHOVER_APP_TOKEN or not PUSHOVER_USER_TOKEN:
        hexchat.prnt('[ERROR] Cannot send notification - tokens not configured')
        return

    try:
        data = urllib.parse.urlencode({
            'token': PUSHOVER_APP_TOKEN,
            'user': PUSHOVER_USER_TOKEN,
            'message': message,
            'title': title,
            'sound': sound,
            'priority': 1
        }).encode('utf-8')

        req = urllib.request.Request('https://api.pushover.net/1/messages.json', data=data)
        response = urllib.request.urlopen(req, timeout=10)
        result = response.read().decode('utf-8')

        hexchat.prnt(f'[PUSHOVER] Notification sent: {title}')
    except Exception as e:
        hexchat.prnt(f'[PUSHOVER ERROR] Failed to send notification: {e}')

def callback_gatekeeper_quit(word, wordeol, userdata):
    """Triggers when Gatekeeper quits with netsplit pattern."""
    nick = word[0]
    reason = word[1]

    # Only alert if the nick is Gatekeeper AND it matches the split pattern
    if nick == "Gatekeeper" and QUIT_REASON_PATTERN.search(reason):
        message = f'🚨 NETSPLIT DETECTED\n\nGatekeeper has quit ({reason})'
        send_pushover_message(message)
        hexchat.prnt(f'[GATEKEEPER] Netsplit detected: {reason}')

    return hexchat.EAT_NONE

def callback_gatekeeper_message(word, wordeol, userdata):
    """Triggers when Gatekeeper posts a message matching the interview pattern."""
    nick = word[0]
    message_text = word[1]

    # Only alert if the nick is Gatekeeper AND message matches interview pattern
    if nick == "Gatekeeper" and INTERVIEW_PATTERN.search(message_text):
        message = f'📢 INTERVIEW STARTED\n\nGatekeeper: {message_text}'
        send_pushover_message(message)
        hexchat.prnt(f'[GATEKEEPER] Interview detected: {message_text}')

    return hexchat.EAT_NONE

# --- HOOKS ---

# Monitor quit events for Gatekeeper netsplit
hexchat.hook_print("Quit", callback_gatekeeper_quit)

# Monitor channel messages for Gatekeeper interview announcements
hexchat.hook_print("Channel Message", callback_gatekeeper_message)

hexchat.prnt(f'{__module_name__} v{__module_version__} loaded: Monitoring Gatekeeper for netsplit and interview events.')
