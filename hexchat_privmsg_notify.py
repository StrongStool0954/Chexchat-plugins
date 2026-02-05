import hexchat
import urllib.request
import urllib.parse

# Private message and mention notification module
__module_name__ = 'privmsg_notify'
__module_version__ = '2.0'
__module_description__ = 'Sends Pushover notifications for private messages and mentions'

# Configuration
PUSHOVER_APP_TOKEN = 'au3h6frhkc6vpb9ot2hjw7izzvkg57'
PUSHOVER_USER_TOKEN = 'uqmniwsjk1pre1pzj18rxrjmm8e8hy'

# Optional: Exclude certain nicks from notifications (case-insensitive)
EXCLUDED_NICKS = []  # Example: ['NickServ', 'ChanServ', 'MemoServ']

# Optional: Only notify when marked as away
ONLY_NOTIFY_WHEN_AWAY = False

# Optional: Enable mention notifications
NOTIFY_ON_MENTIONS = True

def send_pushover_notification(title, message):
    """Sends a notification via Pushover."""
    if not PUSHOVER_APP_TOKEN or not PUSHOVER_USER_TOKEN:
        hexchat.prnt('[PRIVMSG ERROR] Cannot send notification - Pushover tokens not configured')
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

        hexchat.prnt(f'[PRIVMSG] Notification sent for message from: {title}')
    except Exception as e:
        hexchat.prnt(f'[PRIVMSG ERROR] Failed to send notification: {e}')

def handle_server_privmsg(word, word_eol, userdata):
    """Handle incoming PRIVMSG from server (raw IRC event)."""

    if len(word) < 4:
        return hexchat.EAT_NONE

    # Extract nick from :nick!user@host format
    source = word[0]
    if source.startswith(':'):
        source = source[1:]
    nick = source.split('!')[0]

    # Extract target (could be our nick for PM, or channel for channel message)
    target = word[2]

    # Extract message (remove leading colon)
    message = word_eol[3]
    if message.startswith(':'):
        message = message[1:]

    # Get our current nick
    my_nick = hexchat.get_info('nick')

    # Check if it's a channel message (target starts with # or &)
    if target.startswith('#') or target.startswith('&'):
        # This is a channel message - check for mentions
        if NOTIFY_ON_MENTIONS and my_nick and my_nick.lower() in message.lower():

            # Check if we should only notify when away
            if ONLY_NOTIFY_WHEN_AWAY:
                away_status = hexchat.get_info('away')
                if not away_status:
                    hexchat.prnt(f'[MENTION] Not away - skipping notification from: {nick}')
                    return hexchat.EAT_NONE

            # Send notification
            notification_title = f"Mentioned by {nick} in {target}"
            preview = message[:200] + '...' if len(message) > 200 else message
            send_pushover_notification(notification_title, preview)

        return hexchat.EAT_NONE

    # Only process private messages TO us from here on
    if target != my_nick:
        return hexchat.EAT_NONE

    # Check if nick is in excluded list (case-insensitive)
    if any(nick.lower() == excluded.lower() for excluded in EXCLUDED_NICKS):
        hexchat.prnt(f'[PRIVMSG] Ignored message from excluded nick: {nick}')
        return hexchat.EAT_NONE

    # Check if we should only notify when away
    if ONLY_NOTIFY_WHEN_AWAY:
        away_status = hexchat.get_info('away')
        if not away_status:
            hexchat.prnt(f'[PRIVMSG] Not away - skipping notification from: {nick}')
            return hexchat.EAT_NONE

    # Send notification
    notification_title = f"Private Message from {nick}"

    # Truncate long messages for notification
    preview = message[:200] + '...' if len(message) > 200 else message
    notification_message = f'{preview}'

    send_pushover_notification(notification_title, notification_message)

    return hexchat.EAT_NONE

# --- HOOKS ---

# Hook raw server PRIVMSG events (catches both private messages and channel messages)
hexchat.hook_server("PRIVMSG", handle_server_privmsg)

hexchat.prnt(f'{__module_name__} v{__module_version__} loaded')
hexchat.prnt('[PRIVMSG] Monitoring all incoming private messages')
if NOTIFY_ON_MENTIONS:
    hexchat.prnt('[MENTION] Monitoring channel mentions')
if EXCLUDED_NICKS:
    hexchat.prnt(f'[PRIVMSG] Excluded nicks: {", ".join(EXCLUDED_NICKS)}')
if ONLY_NOTIFY_WHEN_AWAY:
    hexchat.prnt('[PRIVMSG] Only notifying when marked as away')
