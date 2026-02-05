import hexchat
import subprocess
import re
import time
import urllib.request
import urllib.parse

# Position monitoring module
__module_name__ = 'position_monitor'
__module_version__ = '1.5'
__module_description__ = 'Monitors IRC queue position and alerts when it changes'

# Configuration
POSITION_NICK = 'Gatekeeper'  # Nick to query for position
CHECK_INTERVAL = 1800  # 30 minutes in seconds
AUTO_START = True  # Automatically start monitoring when plugin loads
PUSHOVER_APP_TOKEN = 'au3h6frhkc6vpb9ot2hjw7izzvkg57'
PUSHOVER_USER_TOKEN = 'uqmniwsjk1pre1pzj18rxrjmm8e8hy'

# State tracking
current_position = None
position_total = None
last_check_time = 0
timer_hook = None

# Pattern to match position responses: "You are in position 58 of 59."
POSITION_PATTERN = re.compile(
    r'position (\d+) of (\d+)',
    re.IGNORECASE
)

def send_pushover_notification(title, message):
    """Sends a notification via Pushover."""
    if not PUSHOVER_APP_TOKEN or not PUSHOVER_USER_TOKEN:
        hexchat.prnt('[ERROR] Cannot send notification - Pushover tokens not configured')
        return

    try:
        data = urllib.parse.urlencode({
            'token': PUSHOVER_APP_TOKEN,
            'user': PUSHOVER_USER_TOKEN,
            'message': message,
            'title': title,
            'sound': 'pushover',
            'priority': 1
        }).encode('utf-8')

        req = urllib.request.Request('https://api.pushover.net/1/messages.json', data=data)
        response = urllib.request.urlopen(req, timeout=10)
        result = response.read().decode('utf-8')

        hexchat.prnt(f'[PUSHOVER] Notification sent: {title}')
        hexchat.prnt(f'[PUSHOVER] Response: {result}')
    except Exception as e:
        hexchat.prnt(f'[PUSHOVER ERROR] Failed to send notification: {e}')

def check_position(userdata):
    """Send position query to the configured nick."""
    global last_check_time

    # Send the !position command as a private message
    hexchat.command(f'MSG {POSITION_NICK} !position')
    last_check_time = time.time()
    hexchat.prnt(f'[POSITION] Querying position from {POSITION_NICK}')

    return 1  # Return 1 to keep the timer running

def handle_private_message_print(word, word_eol, userdata):
    """Handle incoming private messages from print event."""
    global current_position, position_total

    # word[0] = nick, word[1] = message
    nick = word[0]
    message = word[1] if len(word) > 1 else ""

    # Only process messages from the position nick
    if nick != POSITION_NICK:
        return hexchat.EAT_NONE

    # Try to parse position from message
    match = POSITION_PATTERN.search(message)
    if match:
        new_position = int(match.group(1))
        new_total = int(match.group(2))

        hexchat.prnt(f'[POSITION] Current: {new_position} of {new_total}')

        # Check if this is the first check or if position changed
        if current_position is None:
            # First check - send initial position notification
            notification_title = "IRC Queue Position Monitor Started"
            notification_message = (
                f'Position monitoring is now active!\n\n'
                f'Your current position: {new_position} of {new_total}\n\n'
                f'You will be notified when your position changes.'
            )

            send_pushover_notification(notification_title, notification_message)
            hexchat.prnt(f'[POSITION] Initial position: {new_position} of {new_total} (notification sent)')

        elif current_position != new_position:
            # Position changed - send notification
            direction = "up" if new_position < current_position else "down"
            change = abs(new_position - current_position)

            notification_title = "IRC Queue Position Changed"
            notification_message = (
                f'Your position moved {direction} by {change}\n\n'
                f'Old position: {current_position} of {new_total}\n'
                f'New position: {new_position} of {new_total}'
            )

            send_pushover_notification(notification_title, notification_message)
            hexchat.prnt(f'[POSITION] Position changed from {current_position} to {new_position}')

        # Update stored position
        current_position = new_position
        position_total = new_total

    return hexchat.EAT_NONE

def handle_server_privmsg(word, word_eol, userdata):
    """Handle incoming PRIVMSG from server (raw IRC event)."""
    global current_position, position_total

    # word[0] = :nick!user@host
    # word[1] = PRIVMSG
    # word[2] = target (our nick)
    # word[3] = :message text

    if len(word) < 4:
        return hexchat.EAT_NONE

    # Extract nick from :nick!user@host format
    source = word[0]
    if source.startswith(':'):
        source = source[1:]
    nick = source.split('!')[0]

    # Extract message (remove leading colon)
    message = word_eol[3]
    if message.startswith(':'):
        message = message[1:]

    # Only process messages from the position nick
    if nick != POSITION_NICK:
        return hexchat.EAT_NONE

    hexchat.prnt(f'[POSITION DEBUG] Received message from {nick}: {message}')

    # Try to parse position from message
    match = POSITION_PATTERN.search(message)
    if match:
        new_position = int(match.group(1))
        new_total = int(match.group(2))

        hexchat.prnt(f'[POSITION] Current: {new_position} of {new_total}')

        # Check if this is the first check or if position changed
        if current_position is None:
            # First check - send initial position notification
            notification_title = "IRC Queue Position Monitor Started"
            notification_message = (
                f'Position monitoring is now active!\n\n'
                f'Your current position: {new_position} of {new_total}\n\n'
                f'You will be notified when your position changes.'
            )

            send_pushover_notification(notification_title, notification_message)
            hexchat.prnt(f'[POSITION] Initial position: {new_position} of {new_total} (notification sent)')

        elif current_position != new_position:
            # Position changed - send notification
            direction = "up" if new_position < current_position else "down"
            change = abs(new_position - current_position)

            notification_title = "IRC Queue Position Changed"
            notification_message = (
                f'Your position moved {direction} by {change}\n\n'
                f'Old position: {current_position} of {new_total}\n'
                f'New position: {new_position} of {new_total}'
            )

            send_pushover_notification(notification_title, notification_message)
            hexchat.prnt(f'[POSITION] Position changed from {current_position} to {new_position}')

        # Update stored position
        current_position = new_position
        position_total = new_total

    return hexchat.EAT_NONE

def start_monitoring(word, word_eol, userdata):
    """Command to start position monitoring: /position_start"""
    global timer_hook

    if timer_hook is not None:
        hexchat.prnt('[POSITION] Monitoring is already running')
        return hexchat.EAT_ALL

    # Do an immediate check
    check_position(None)

    # Schedule periodic checks
    timer_hook = hexchat.hook_timer(CHECK_INTERVAL * 1000, check_position)
    hexchat.prnt(f'[POSITION] Started monitoring - checking every {CHECK_INTERVAL//60} minutes')

    return hexchat.EAT_ALL

def stop_monitoring(word, word_eol, userdata):
    """Command to stop position monitoring: /position_stop"""
    global timer_hook

    if timer_hook is None:
        hexchat.prnt('[POSITION] Monitoring is not running')
        return hexchat.EAT_ALL

    hexchat.unhook(timer_hook)
    timer_hook = None
    hexchat.prnt('[POSITION] Stopped monitoring')

    return hexchat.EAT_ALL

def check_status(word, word_eol, userdata):
    """Command to check current status: /position_status"""
    global current_position, position_total, last_check_time

    if timer_hook is None:
        hexchat.prnt('[POSITION] Monitoring is NOT running')
        hexchat.prnt('[POSITION] Use /position_start to begin monitoring')
    else:
        hexchat.prnt('[POSITION] Monitoring is ACTIVE')
        hexchat.prnt(f'[POSITION] Checking every {CHECK_INTERVAL//60} minutes')

    if current_position is not None:
        hexchat.prnt(f'[POSITION] Last known position: {current_position} of {position_total}')
        if last_check_time > 0:
            elapsed = int(time.time() - last_check_time)
            hexchat.prnt(f'[POSITION] Last checked: {elapsed} seconds ago')
    else:
        hexchat.prnt('[POSITION] No position data yet')

    return hexchat.EAT_ALL

def manual_check(word, word_eol, userdata):
    """Command to manually check position: /position_check"""
    check_position(None)
    return hexchat.EAT_ALL

# --- HOOKS ---

# Hook private messages to capture position responses (multiple methods for reliability)
hexchat.hook_server("PRIVMSG", handle_server_privmsg)
hexchat.hook_print("Private Message", handle_private_message_print)
hexchat.hook_print("Private Message to Dialog", handle_private_message_print)

# Register commands
hexchat.hook_command("position_start", start_monitoring, help="/position_start - Start monitoring queue position")
hexchat.hook_command("position_stop", stop_monitoring, help="/position_stop - Stop monitoring queue position")
hexchat.hook_command("position_status", check_status, help="/position_status - Show monitoring status")
hexchat.hook_command("position_check", manual_check, help="/position_check - Manually check position now")

hexchat.prnt(f'{__module_name__} v{__module_version__} loaded')
hexchat.prnt('[POSITION] Commands: /position_start /position_stop /position_status /position_check')
hexchat.prnt(f'[POSITION] Configured to monitor: {POSITION_NICK}')

# Auto-start monitoring if enabled
if AUTO_START:
    start_monitoring([], [], None)
    hexchat.prnt('[POSITION] Auto-start enabled - monitoring started automatically')
