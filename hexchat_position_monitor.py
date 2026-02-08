import hexchat
import subprocess
import re
import time
import urllib.request
import urllib.parse
import os

# Position monitoring module
__module_name__ = 'position_monitor'
__module_version__ = '1.9'
__module_description__ = 'Monitors IRC queue position and alerts when it changes'

# Configuration
POSITION_NICK = 'Gatekeeper'  # Nick to query for position
RED_CHANNEL = '#red-invites'  # Channel to monitor for quits
CHECK_INTERVAL = 1800  # 30 minutes in seconds (normal mode)
FREQUENT_CHECK_INTERVAL = 600  # 10 minutes in seconds (when position <= threshold)
FREQUENT_CHECK_THRESHOLD = 15  # Switch to frequent checks when position is this or lower
AUTO_START = True  # Automatically start monitoring when plugin loads
QUIT_CHECK_COOLDOWN = 60  # 1 minute cooldown between quit-triggered checks
QUIT_CHECK_DELAY = 60  # 1 minute delay before checking position after quit
PUSHOVER_APP_TOKEN = 'au3h6frhkc6vpb9ot2hjw7izzvkg57'
PUSHOVER_USER_TOKEN = 'uqmniwsjk1pre1pzj18rxrjmm8e8hy'

# TTS Configuration
ENABLE_TTS = True  # Enable text-to-speech announcements
TTS_THRESHOLD = None  # Announce all position changes (set to number like 10 to only announce when position <= 10)
PIPER_PATH = os.path.expanduser('~/.local/bin/piper')
PIPER_MODEL = os.path.expanduser('~/.local/share/piper/models/en_US-lessac-medium.onnx')

# State tracking
current_position = None
position_total = None
last_check_time = 0
timer_hook = None
quit_check_pending = False
last_quit_check_time = 0
current_check_interval = CHECK_INTERVAL  # Track current interval mode

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

def speak_tts(message):
    """Speak a message using Piper TTS."""
    if not ENABLE_TTS:
        return

    if not os.path.exists(PIPER_PATH) or not os.path.exists(PIPER_MODEL):
        hexchat.prnt('[TTS ERROR] Piper or model not found')
        return

    try:
        # Run piper in background to avoid blocking
        process = subprocess.Popen(
            [PIPER_PATH, '--model', PIPER_MODEL, '--output-raw'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Send text to piper and pipe output to aplay
        tts_output, _ = process.communicate(input=message.encode('utf-8'))

        # Play audio with aplay
        subprocess.Popen(
            ['aplay', '-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ).communicate(input=tts_output)

        hexchat.prnt(f'[TTS] Spoke: {message}')
    except Exception as e:
        hexchat.prnt(f'[TTS ERROR] Failed to speak: {e}')

def adjust_check_interval():
    """Adjust monitoring interval based on current position."""
    global timer_hook, current_check_interval

    # Determine appropriate interval based on position
    if current_position is not None and current_position <= FREQUENT_CHECK_THRESHOLD:
        desired_interval = FREQUENT_CHECK_INTERVAL
    else:
        desired_interval = CHECK_INTERVAL

    # Only update if interval needs to change and monitoring is active
    if timer_hook is not None and desired_interval != current_check_interval:
        old_interval_minutes = current_check_interval // 60
        new_interval_minutes = desired_interval // 60

        hexchat.prnt(f'[POSITION] Position within top {FREQUENT_CHECK_THRESHOLD} - switching to {new_interval_minutes} minute checks')

        # Unhook old timer and create new one with different interval
        hexchat.unhook(timer_hook)
        timer_hook = hexchat.hook_timer(desired_interval * 1000, check_position)
        current_check_interval = desired_interval

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
                f'Old position: {current_position} of {position_total}\n'
                f'New position: {new_position} of {new_total}'
            )

            send_pushover_notification(notification_title, notification_message)
            hexchat.prnt(f'[POSITION] Position changed from {current_position} to {new_position}')

            # TTS announcement
            if TTS_THRESHOLD is None or new_position <= TTS_THRESHOLD:
                speak_tts(f'Now serving number {new_position}')

        else:
            # Position stayed the same (but total might have changed)
            if position_total is not None and position_total != new_total:
                hexchat.prnt(f'[POSITION] Queue size changed from {position_total} to {new_total}, but your position ({current_position}) stayed the same (no notification)')
            else:
                hexchat.prnt(f'[POSITION] No change - still at position {current_position} of {new_total}')

        # Update stored position
        current_position = new_position
        position_total = new_total

        # Adjust check interval based on new position
        adjust_check_interval()

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
                f'Old position: {current_position} of {position_total}\n'
                f'New position: {new_position} of {new_total}'
            )

            send_pushover_notification(notification_title, notification_message)
            hexchat.prnt(f'[POSITION] Position changed from {current_position} to {new_position}')

            # TTS announcement
            if TTS_THRESHOLD is None or new_position <= TTS_THRESHOLD:
                speak_tts(f'Now serving number {new_position}')

        else:
            # Position stayed the same (but total might have changed)
            if position_total is not None and position_total != new_total:
                hexchat.prnt(f'[POSITION] Queue size changed from {position_total} to {new_total}, but your position ({current_position}) stayed the same (no notification)')
            else:
                hexchat.prnt(f'[POSITION] No change - still at position {current_position} of {new_total}')

        # Update stored position
        current_position = new_position
        position_total = new_total

        # Adjust check interval based on new position
        adjust_check_interval()

    return hexchat.EAT_NONE

def handle_quit_event(word, word_eol, userdata):
    """Monitor quits in #red-invites and trigger delayed position check."""
    global quit_check_pending, last_quit_check_time

    nick = word[0]
    reason = word[1] if len(word) > 1 else ""
    channel = hexchat.get_info("channel")

    # Only process if we're currently viewing #red-invites
    if channel == RED_CHANNEL:
        # Check if enough time has passed since last quit-triggered check (1 minute cooldown)
        if not quit_check_pending and (time.time() - last_quit_check_time) >= QUIT_CHECK_COOLDOWN:
            hexchat.prnt(f'[POSITION] {nick} quit - will check position in 1 minute...')
            quit_check_pending = True
            hexchat.hook_timer(QUIT_CHECK_DELAY * 1000, delayed_position_check)

    return hexchat.EAT_NONE

def delayed_position_check(userdata):
    """Called after quit delay to check position."""
    global quit_check_pending, last_quit_check_time

    check_position(None)
    last_quit_check_time = time.time()
    quit_check_pending = False

    return 0  # Don't repeat timer

def start_monitoring(word, word_eol, userdata):
    """Command to start position monitoring: /position_start"""
    global timer_hook, current_check_interval

    if timer_hook is not None:
        hexchat.prnt('[POSITION] Monitoring is already running')
        return hexchat.EAT_ALL

    # Do an immediate check
    check_position(None)

    # Determine initial interval based on current position
    if current_position is not None and current_position <= FREQUENT_CHECK_THRESHOLD:
        current_check_interval = FREQUENT_CHECK_INTERVAL
    else:
        current_check_interval = CHECK_INTERVAL

    # Schedule periodic checks
    timer_hook = hexchat.hook_timer(current_check_interval * 1000, check_position)
    hexchat.prnt(f'[POSITION] Started monitoring - checking every {current_check_interval//60} minutes')

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
        interval_minutes = current_check_interval // 60
        if current_check_interval == FREQUENT_CHECK_INTERVAL:
            hexchat.prnt(f'[POSITION] Checking every {interval_minutes} minutes (FREQUENT MODE - position ≤ {FREQUENT_CHECK_THRESHOLD})')
        else:
            hexchat.prnt(f'[POSITION] Checking every {interval_minutes} minutes (normal mode)')

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

# Monitor quit events in #red-invites to trigger position checks
hexchat.hook_print("Quit", handle_quit_event)

# Register commands
hexchat.hook_command("position_start", start_monitoring, help="/position_start - Start monitoring queue position")
hexchat.hook_command("position_stop", stop_monitoring, help="/position_stop - Stop monitoring queue position")
hexchat.hook_command("position_status", check_status, help="/position_status - Show monitoring status")
hexchat.hook_command("position_check", manual_check, help="/position_check - Manually check position now")

hexchat.prnt(f'{__module_name__} v{__module_version__} loaded')
hexchat.prnt('[POSITION] Commands: /position_start /position_stop /position_status /position_check')
hexchat.prnt(f'[POSITION] Configured to monitor: {POSITION_NICK}')
hexchat.prnt(f'[POSITION] Monitoring quits in {RED_CHANNEL} for position changes')
hexchat.prnt(f'[POSITION] Check intervals: {CHECK_INTERVAL//60}min normal, {FREQUENT_CHECK_INTERVAL//60}min when ≤{FREQUENT_CHECK_THRESHOLD}')
if ENABLE_TTS:
    threshold_text = f'when ≤{TTS_THRESHOLD}' if TTS_THRESHOLD else 'on all changes'
    hexchat.prnt(f'[POSITION] TTS enabled: "Now serving number {{position}}" {threshold_text}')

# Auto-start monitoring if enabled
if AUTO_START:
    start_monitoring([], [], None)
    hexchat.prnt('[POSITION] Auto-start enabled - monitoring started automatically')
