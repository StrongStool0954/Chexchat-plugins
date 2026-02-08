import hexchat
import threading
import time
import urllib.request

# Speedtest queue helper module
__module_name__ = 'speedtest_queue'
__module_version__ = '5.4'
__module_description__ = 'Fetch speedtest results from HTTP server for IRC queue commands'

# Configuration
CHECK_INTERVAL = 1800  # 30 minutes in seconds
RED_CHANNEL = '#red-invites'
OPS_NICK = 'hermes'
SPEEDTEST_HTTP_URL = 'http://10.200.200.10:8888/speedtest'  # Proxmox host pm01

# State
latest_speedtest_url = None
last_check_time = 0
timer_hook = None
speedtest_running = False

def run_speedtest():
    """Fetch latest speedtest URL from HTTP server."""
    global speedtest_running

    if speedtest_running:
        hexchat.prnt('[SPEEDTEST] Fetch already in progress, please wait...')
        return None

    try:
        speedtest_running = True
        hexchat.prnt(f'[SPEEDTEST] Fetching from {SPEEDTEST_HTTP_URL}...')

        # Fetch URL from HTTP server
        request = urllib.request.Request(SPEEDTEST_HTTP_URL, method='GET')
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status == 200:
                url = response.read().decode('utf-8').strip()

                # Get age from response headers
                age_minutes = response.headers.get('X-Speedtest-Age-Minutes', 'unknown')

                hexchat.prnt(f'[SPEEDTEST] Loaded URL: {url}')
                hexchat.prnt(f'[SPEEDTEST] Age: {age_minutes} minutes')
                return url
            else:
                hexchat.prnt(f'[SPEEDTEST ERROR] HTTP {response.status}')
                return None

    except urllib.error.HTTPError as e:
        if e.code == 503:
            hexchat.prnt('[SPEEDTEST ERROR] No speedtest available yet on server')
        else:
            hexchat.prnt(f'[SPEEDTEST ERROR] HTTP {e.code}: {e.reason}')
        return None
    except urllib.error.URLError as e:
        hexchat.prnt(f'[SPEEDTEST ERROR] Cannot reach server: {e.reason}')
        return None
    except Exception as e:
        hexchat.prnt(f'[SPEEDTEST ERROR] {e}')
        return None
    finally:
        speedtest_running = False

def run_speedtest_async():
    """Run speedtest in a background thread to avoid blocking HexChat."""
    def worker():
        global latest_speedtest_url, last_check_time
        url = run_speedtest()
        if url:
            latest_speedtest_url = url
            last_check_time = time.time()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

def periodic_speedtest(userdata):
    """Fetch speedtest URL from HTTP server periodically."""
    run_speedtest_async()
    return 1  # Keep timer running

def cmd_joinred(word, word_eol, userdata):
    """Command: /joinred - Join RED queue with latest speedtest."""
    global latest_speedtest_url

    if latest_speedtest_url is None:
        hexchat.prnt('[JOINRED] No speedtest URL available yet. Running speedtest now...')
        run_speedtest_async()
        hexchat.prnt('[JOINRED] Please wait for speedtest to complete, then try again.')
        return hexchat.EAT_ALL

    # Calculate age of speedtest
    age_minutes = int((time.time() - last_check_time) / 60) if last_check_time > 0 else 0

    # Check if already in channel
    context = hexchat.find_context(channel=RED_CHANNEL)

    def send_message(userdata):
        """Send the queue message (called immediately or after delay)."""
        message = f'!queue {latest_speedtest_url}'
        hexchat.command(f'MSG {RED_CHANNEL} {message}')
        hexchat.prnt(f'[JOINRED] Sent to {RED_CHANNEL}: {message}')
        hexchat.prnt(f'[JOINRED] Speedtest age: {age_minutes} minutes old')
        return 0  # Don't repeat timer

    if context is None:
        # Not in channel - join and wait 5 seconds before sending
        hexchat.prnt(f'[JOINRED] Not in {RED_CHANNEL}, joining now...')
        hexchat.command(f'JOIN {RED_CHANNEL}')
        hexchat.prnt('[JOINRED] Waiting 5 seconds for join to complete...')
        hexchat.hook_timer(5000, send_message)  # 5000ms = 5 seconds
    else:
        # Already in channel - send immediately
        send_message(None)

    return hexchat.EAT_ALL

def cmd_joinops(word, word_eol, userdata):
    """Command: /joinops - Join OPS queue with latest speedtest."""
    global latest_speedtest_url

    if latest_speedtest_url is None:
        hexchat.prnt('[JOINOPS] No speedtest URL available yet. Running speedtest now...')
        run_speedtest_async()
        hexchat.prnt('[JOINOPS] Please wait for speedtest to complete, then try again.')
        return hexchat.EAT_ALL

    # Calculate age of speedtest
    age_minutes = int((time.time() - last_check_time) / 60) if last_check_time > 0 else 0

    # Send to OPS nick
    message = f'!queue {latest_speedtest_url}'
    hexchat.command(f'MSG {OPS_NICK} {message}')

    hexchat.prnt(f'[JOINOPS] Sent to {OPS_NICK}: {message}')
    hexchat.prnt(f'[JOINOPS] Speedtest age: {age_minutes} minutes old')

    return hexchat.EAT_ALL

def cmd_speedtest(word, word_eol, userdata):
    """Command: /speedtest - Manually fetch speedtest URL from HTTP server."""
    hexchat.prnt('[SPEEDTEST] Fetching speedtest URL from HTTP server...')
    run_speedtest_async()
    return hexchat.EAT_ALL

def cmd_speedtest_trigger(word, word_eol, userdata):
    """Command: /speedtest_trigger - Trigger fresh speedtest on server."""
    hexchat.prnt('[SPEEDTEST] Triggering fresh speedtest on server...')

    try:
        trigger_url = SPEEDTEST_HTTP_URL.replace('/speedtest', '/trigger')
        request = urllib.request.Request(trigger_url, method='POST', data=b'')

        with urllib.request.urlopen(request, timeout=10) as response:
            message = response.read().decode('utf-8').strip()
            if response.status == 202:
                hexchat.prnt(f'[SPEEDTEST] {message}')
                hexchat.prnt('[SPEEDTEST] Use /speedtest to fetch the new URL once ready')
            elif response.status == 429:
                hexchat.prnt(f'[SPEEDTEST] {message}')
            else:
                hexchat.prnt(f'[SPEEDTEST] Unexpected response: {response.status}')

    except urllib.error.HTTPError as e:
        hexchat.prnt(f'[SPEEDTEST ERROR] HTTP {e.code}: {e.reason}')
    except urllib.error.URLError as e:
        hexchat.prnt(f'[SPEEDTEST ERROR] Cannot reach server: {e.reason}')
    except Exception as e:
        hexchat.prnt(f'[SPEEDTEST ERROR] {e}')

    return hexchat.EAT_ALL

def cmd_speedtest_status(word, word_eol, userdata):
    """Command: /speedtest_status - Show current speedtest info."""
    global latest_speedtest_url, last_check_time

    if latest_speedtest_url:
        age_minutes = int((time.time() - last_check_time) / 60)
        hexchat.prnt('[SPEEDTEST STATUS]')
        hexchat.prnt(f'  Latest URL: {latest_speedtest_url}')
        hexchat.prnt(f'  Age: {age_minutes} minutes old')
        hexchat.prnt(f'  Last check: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_check_time))}')
        hexchat.prnt(f'  Next automatic check: in {CHECK_INTERVAL // 60} minutes')
    else:
        hexchat.prnt('[SPEEDTEST STATUS] No speedtest run yet')
        hexchat.prnt(f'  Next automatic check: in {CHECK_INTERVAL // 60} minutes')

    if speedtest_running:
        hexchat.prnt('  Currently running: YES')

    return hexchat.EAT_ALL

def start_monitoring():
    """Start periodic speedtest URL fetching."""
    global timer_hook

    if timer_hook is not None:
        hexchat.prnt('[SPEEDTEST] Monitoring already running')
        return

    # Fetch initial speedtest URL
    hexchat.prnt('[SPEEDTEST] Starting speedtest URL monitoring')
    hexchat.prnt(f'[SPEEDTEST] Fetching from HTTP server: {SPEEDTEST_HTTP_URL}')
    run_speedtest_async()

    # Schedule periodic fetches
    timer_hook = hexchat.hook_timer(CHECK_INTERVAL * 1000, periodic_speedtest)
    hexchat.prnt(f'[SPEEDTEST] Will fetch URL every {CHECK_INTERVAL // 60} minutes')

def stop_monitoring():
    """Stop periodic speedtest monitoring."""
    global timer_hook

    if timer_hook is None:
        hexchat.prnt('[SPEEDTEST] Monitoring not running')
        return

    hexchat.unhook(timer_hook)
    timer_hook = None
    hexchat.prnt('[SPEEDTEST] Stopped automated speedtest monitoring')

def cmd_start_monitoring(word, word_eol, userdata):
    """Command: /speedtest_start - Start URL monitoring."""
    start_monitoring()
    return hexchat.EAT_ALL

def cmd_stop_monitoring(word, word_eol, userdata):
    """Command: /speedtest_stop - Stop URL monitoring."""
    stop_monitoring()
    return hexchat.EAT_ALL

# Register commands
hexchat.hook_command("joinred", cmd_joinred, help="/joinred - Send !queue with speedtest to #red-invites")
hexchat.hook_command("joinops", cmd_joinops, help="/joinops - Send !queue with speedtest to hermes")
hexchat.hook_command("speedtest", cmd_speedtest, help="/speedtest - Fetch speedtest URL from HTTP server")
hexchat.hook_command("speedtest_trigger", cmd_speedtest_trigger, help="/speedtest_trigger - Trigger fresh speedtest on server")
hexchat.hook_command("speedtest_status", cmd_speedtest_status, help="/speedtest_status - Show speedtest info")
hexchat.hook_command("speedtest_start", cmd_start_monitoring, help="/speedtest_start - Start URL monitoring")
hexchat.hook_command("speedtest_stop", cmd_stop_monitoring, help="/speedtest_stop - Stop URL monitoring")

# Auto-start monitoring
hexchat.prnt(f'{__module_name__} v{__module_version__} loaded')
hexchat.prnt('[SPEEDTEST] Commands: /joinred /joinops /speedtest /speedtest_trigger /speedtest_status')
hexchat.prnt(f'[SPEEDTEST] Config: RED={RED_CHANNEL}, OPS={OPS_NICK}')
hexchat.prnt(f'[SPEEDTEST] Server: {SPEEDTEST_HTTP_URL}')
start_monitoring()
