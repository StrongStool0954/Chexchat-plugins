import hexchat
import subprocess
import re
import os
import urllib.request
import urllib.parse
import time

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
__module_version__ = '2.0'
__module_description__ = 'Alerts on Gatekeeper netsplit and auto-rejoins queue when back'

# PUSHOVER CREDENTIALS - Configured locally (not in git)
PUSHOVER_APP_TOKEN = 'au3h6frhkc6vpb9ot2hjw7izzvkg57'
PUSHOVER_USER_TOKEN = 'uqmniwsjk1pre1pzj18rxrjmm8e8hy'

# Configuration
RED_CHANNEL = '#red-invites'
GATEKEEPER_NICK = 'Gatekeeper'
REJOIN_DELAY = 1200  # 20 minutes in seconds

# State tracking
netsplit_timer_hook = None
netsplit_detected_time = None

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

def is_gatekeeper_in_channel():
    """Check if Gatekeeper is currently in #red-invites."""
    context = hexchat.find_context(channel=RED_CHANNEL)
    if not context:
        hexchat.prnt(f'[GATEKEEPER] Cannot find {RED_CHANNEL} context')
        return False

    users = context.get_list('users')
    for user in users:
        if user.nick == GATEKEEPER_NICK:
            return True
    return False

def rejoin_and_check_gatekeeper(userdata):
    """Called 20 minutes after netsplit - rejoin channel and check for Gatekeeper."""
    global netsplit_timer_hook, netsplit_detected_time

    hexchat.prnt('[GATEKEEPER] 20 minutes elapsed since netsplit, checking status...')

    # Make sure we're in the channel
    context = hexchat.find_context(channel=RED_CHANNEL)
    if not context:
        hexchat.prnt(f'[GATEKEEPER] Not in {RED_CHANNEL}, joining...')
        hexchat.command(f'JOIN {RED_CHANNEL}')
        # Wait a moment for join to complete
        hexchat.hook_timer(3000, check_and_execute_joinred)
    else:
        # Already in channel, check immediately
        check_and_execute_joinred(None)

    # Clear timer hook
    netsplit_timer_hook = None
    return 0  # Don't repeat timer

def check_and_execute_joinred(userdata):
    """Check if Gatekeeper is present and execute /joinred if so."""
    if is_gatekeeper_in_channel():
        hexchat.prnt(f'[GATEKEEPER] ✓ {GATEKEEPER_NICK} is back in {RED_CHANNEL}!')
        hexchat.prnt('[GATEKEEPER] Executing /joinred...')

        # Execute the /joinred command
        hexchat.command('joinred')

        # Send success notification
        message = f'✅ AUTO-REJOIN SUCCESS\n\n{GATEKEEPER_NICK} is back!\nExecuted /joinred command.'
        send_pushover_message(message, sound='magic')
    else:
        hexchat.prnt(f'[GATEKEEPER] ✗ {GATEKEEPER_NICK} not found in {RED_CHANNEL}')
        hexchat.prnt('[GATEKEEPER] Will not auto-rejoin queue')

        # Send notification that Gatekeeper is still missing
        message = f'⚠️ GATEKEEPER STILL MISSING\n\n{GATEKEEPER_NICK} not back after 20 minutes.\nManual action required.'
        send_pushover_message(message, sound='falling')

    return 0  # Don't repeat timer

def callback_gatekeeper_quit(word, wordeol, userdata):
    """Triggers when Gatekeeper quits with netsplit pattern."""
    global netsplit_timer_hook, netsplit_detected_time

    nick = word[0]
    reason = word[1]

    # Only alert if the nick is Gatekeeper AND it matches the split pattern
    if nick == GATEKEEPER_NICK and QUIT_REASON_PATTERN.search(reason):
        netsplit_detected_time = time.time()

        message = f'🚨 NETSPLIT DETECTED\n\nGatekeeper has quit ({reason})\n\nWill check in 20 minutes and auto-rejoin if back.'
        send_pushover_message(message)
        hexchat.prnt(f'[GATEKEEPER] Netsplit detected: {reason}')
        hexchat.prnt(f'[GATEKEEPER] Will rejoin {RED_CHANNEL} and check for {GATEKEEPER_NICK} in 20 minutes...')

        # Cancel existing timer if any
        if netsplit_timer_hook is not None:
            hexchat.unhook(netsplit_timer_hook)

        # Schedule rejoin check in 2 minutes
        netsplit_timer_hook = hexchat.hook_timer(REJOIN_DELAY * 1000, rejoin_and_check_gatekeeper)

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

def cmd_test_gatekeeper(word, word_eol, userdata):
    """Command: /test_gatekeeper - Test the auto-rejoin functionality."""
    hexchat.prnt('[GATEKEEPER] Testing auto-rejoin functionality...')

    if is_gatekeeper_in_channel():
        hexchat.prnt(f'[GATEKEEPER] ✓ {GATEKEEPER_NICK} is currently in {RED_CHANNEL}')
        hexchat.prnt('[GATEKEEPER] Simulating check (skipping /joinred for test)')
    else:
        hexchat.prnt(f'[GATEKEEPER] ✗ {GATEKEEPER_NICK} NOT in {RED_CHANNEL}')

    return hexchat.EAT_ALL

# --- HOOKS ---

# Monitor quit events for Gatekeeper netsplit
hexchat.hook_print("Quit", callback_gatekeeper_quit)

# Monitor channel messages for Gatekeeper interview announcements
hexchat.hook_print("Channel Message", callback_gatekeeper_message)

# Register test command
hexchat.hook_command("test_gatekeeper", cmd_test_gatekeeper,
                     help="/test_gatekeeper - Test if Gatekeeper is in channel")

hexchat.prnt(f'{__module_name__} v{__module_version__} loaded')
hexchat.prnt(f'[GATEKEEPER] Monitoring {GATEKEEPER_NICK} for netsplit and interview events')
hexchat.prnt(f'[GATEKEEPER] Auto-rejoin: ON - Will check {RED_CHANNEL} after 20min delay')
hexchat.prnt(f'[GATEKEEPER] Auto-command: /joinred (if {GATEKEEPER_NICK} is back)')
