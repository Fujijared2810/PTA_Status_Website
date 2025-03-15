from flask import Flask, render_template_string
from flask_socketio import SocketIO
import requests
import time
import threading
from datetime import datetime
import os
import platform
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ptastatus-secret-key'

# Initialize socketio differently based on environment
is_production = os.environ.get('RENDER', False)
if is_production:
    # In production: completely disable WebSockets
    socketio = SocketIO(app, 
                       cors_allowed_origins="*", 
                       async_mode='threading',
                       transport=['polling'],
                       allow_upgrades=False,  # Prevent upgrading from polling to WebSockets
                       engineio_logger=False,
                       logger=False)
else:
    # In development: use default settings
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
BOT_URL = os.environ.get('BOT_URL', "https://ptabot-status-website.onrender.com/")  # Use environment variable in production
BOT_NAME = "@PTAStudentBot"  # Add this line
TELEGRAM_BOT_LINK = "https://t.me/PTAStudentBot"  # Add this line - note: no @ symbol in the URL
CHECK_INTERVAL = 1  # Check every 10 seconds for more responsive updates
MAX_HISTORY_ENTRIES = 100

# Status tracking
last_check = None
is_online = False
last_online = None
status_history = []
uptime_percentage = 100.0
start_time = datetime.now()

def ph_time_format(dt):
    """Convert datetime to Philippine time and format in 12-hour format"""
    if dt is None:
        return 'Never'
    
    # Convert to Philippine time
    ph_tz = pytz.timezone('Asia/Manila')
    
    # Make sure datetime is timezone-aware
    if dt.tzinfo is None:
        # If no timezone info, assume it's in server local time
        # and convert to UTC first
        dt = datetime.fromtimestamp(dt.timestamp(), pytz.UTC)
    
    # Convert to Philippine time
    dt_ph = dt.astimezone(ph_tz)
    
    # Format in 12-hour format with AM/PM
    return dt_ph.strftime('%Y-%m-%d %I:%M:%S %p')

def check_bot_status():
    global last_check, is_online, last_online, status_history, uptime_percentage
    
    while True:
        try:
            # Record check time
            check_time = datetime.now(pytz.timezone('Asia/Manila'))
            last_check = check_time
            
            # Try to reach the bot URL
            response = requests.get(BOT_URL, timeout=5)
            current_status = response.status_code == 200
            
            # Update status info
            if current_status:
                last_online = check_time
                
            # Only add to history if status changed
            if not status_history or is_online != current_status:
                status_history.append({
                    'timestamp': check_time,
                    'status': current_status
                })
                
                # Keep history at reasonable size
                if len(status_history) > MAX_HISTORY_ENTRIES:
                    status_history.pop(0)
            
            is_online = current_status
            
            # Calculate uptime based on history
            if len(status_history) > 1:
                online_count = sum(1 for entry in status_history if entry['status'])
                uptime_percentage = (online_count / len(status_history)) * 100
            
            # Emit real-time update to all clients
            socketio.emit('status_update', {
                'is_online': is_online,
                'last_online': ph_time_format(last_online),
                'last_check': ph_time_format(last_check),
                'uptime_percentage': round(uptime_percentage, 2),
                'server_time': f"{platform.system()} {platform.release()}",  # Update this line
                'uptime': str(datetime.now() - start_time).split('.')[0],
                'recent_history': [
                    {
                        'timestamp': ph_time_format(entry['timestamp']),
                        'status': entry['status']
                    }
                    for entry in list(reversed(status_history))[:10]
                ]
            })
            
        except Exception as e:
            print(f"Error checking status: {e}")
            is_online = False
            
            # Add to history if this is a change
            if not status_history or status_history[-1]['status'] != False:
                status_history.append({
                    'timestamp': datetime.now(),
                    'status': False
                })
                
                # Keep history at reasonable size
                if len(status_history) > MAX_HISTORY_ENTRIES:
                    status_history.pop(0)
                    
            # Emit error update
            socketio.emit('status_update', {
                'is_online': False,
                'last_online': ph_time_format(last_online),
                'last_check': ph_time_format(last_check),
                'uptime_percentage': round(uptime_percentage, 2),
                'server_time': f"{platform.system()} {platform.release()}",  # Update this line
                'uptime': str(datetime.now() - start_time).split('.')[0],
                'recent_history': [
                    {
                        'timestamp': ph_time_format(entry['timestamp']),
                        'status': entry['status']
                    }
                    for entry in list(reversed(status_history))[:10]
                ]
            })
        
        time.sleep(CHECK_INTERVAL)

# HTML template for status page (enhanced with real-time updates)
STATUS_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PTA Bot Status</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        /* Full stylesheet for the PTA Bot Status Monitor */
        :root {
            /* Trading-focused color palette */
            --success: #00c853;        /* Strong green for positive indicators */
            --success-light: rgba(0, 200, 83, 0.15);
            --danger: #ff3d00;         /* Bright red for negative indicators */
            --danger-light: rgba(255, 61, 0, 0.15);
            --background: #0d1117;     /* Darker black for background */
            --card-bg: #161b22;        /* Elevated card background */
            --card-bg-hover: #21262d;  /* Hover state for cards */
            --text: #e6edf3;           /* Bright white text for readability */
            --text-muted: #8b949e;     /* Secondary text */
            --border: rgba(255, 255, 255, 0.1);
            --accent: #30363d;         /* Border/accent color */
            --accent-light: #484f58;   /* Lighter accent */
            --chart-grid: #30363d;     /* Chart grid lines */
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            transition: all 0.2s ease;
        }

        body {
            font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
            background: var(--background);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 1rem;
            line-height: 1.6;
        }

        .container {
            background-color: var(--card-bg);
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            width: 90%;
            max-width: 900px;
            border: 1px solid var(--accent);
            opacity: 0;
            transform: translateY(20px);
            animation: fadeIn 0.5s forwards;
            position: relative;
            overflow: hidden;
        }

        @keyframes fadeIn {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Trading theme header with ticker-like styling */
        .header {
            background: linear-gradient(to right, #090c10, #161b22);
            padding: 1.2rem 1.5rem; /* Reduced from 1.5rem 2rem */
            position: relative;
            border-bottom: 1px solid var(--accent); /* Changed from 2px */
            overflow: hidden;
        }

        /* Create chart grid in header background */
        .header::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(to right, rgba(48, 54, 61, 0.1) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(48, 54, 61, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            opacity: 0.4;
            z-index: 0;
        }

        .logo {
            font-size: 1.2rem; /* Reduced from 1.4rem */
            font-weight: 700;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            margin-bottom: 0.3rem; /* Reduced from 0.5rem */
            color: var(--text);
            position: relative;
            z-index: 1;
        }

        .logo i {
            margin-right: 0.75rem;
            font-size: 1.6rem;
            color: var(--success);
        }

        h1 {
            font-size: 1.5rem; /* Reduced from 1.75rem */
            font-weight: 800;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            margin-bottom: 0;
            position: relative;
            z-index: 1;
        }

        .content {
            padding: 1rem 1.5rem;
        }

        .status-card {
            background-color: #1a1d24;
            border-radius: 6px;
            padding: 1.25rem; /* Reduced from 2rem */
            text-align: center;
            margin-bottom: 1.25rem; /* Reduced from 2rem */
            border-left: 4px solid var(--accent);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            position: relative;
        }

        /* Add subtle chart lines to status card */
        .status-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(to right, rgba(48, 54, 61, 0.07) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(48, 54, 61, 0.07) 1px, transparent 1px);
            background-size: 10px 30px;
            opacity: 0.5;
            pointer-events: none;
        }

        .status-indicator {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.5rem 1.25rem; /* Reduced padding */
            border-radius: 4px;
            font-weight: 700;
            font-size: 1.1rem; /* Slightly reduced */
            margin-bottom: 0.75rem; /* Reduced */
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
            border: 1px solid var(--border);
            z-index: 1;
        }

        .status-indicator.online {
            background-color: var(--success-light);
            color: var(--success);
            border-color: var(--success);
        }

        .status-indicator.offline {
            background-color: var(--danger-light);
            color: var(--danger);
            border-color: var(--danger);
        }

        .status-indicator::after {
            content: '';
            position: absolute;
            width: 100%;
            height: 200%;
            top: -50%;
            left: -100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            transform: rotate(35deg);
            animation: shine 3s infinite;
        }

        @keyframes shine {
            to {
                left: 100%;
            }
        }

        .status-message {
            font-size: 1rem; /* Reduced */
            margin-bottom: 0.75rem; /* Reduced */
            position: relative;
            z-index: 1;
        }

        .last-seen {
            color: var(--text-muted);
            font-size: 0.85rem; /* Reduced */
            margin-top: 0.35rem; /* Reduced */
            font-family: 'Fira Code', monospace;
            position: relative;
            z-index: 1;
        }

        /* Uptime bar styled like a trading chart */
        .uptime-bar {
            background-color: #1a1d24;
            border-radius: 4px;
            height: 30px; /* Reduced from 36px */
            overflow: hidden;
            position: relative;
            margin-bottom: 1.25rem; /* Reduced from 2rem */
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
            border: 1px solid var(--accent);
        }

        /* Add chart grid lines to uptime bar */
        .uptime-bar::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: linear-gradient(to right, var(--chart-grid) 1px, transparent 1px);
            background-size: 10% 100%;
            opacity: 0.2;
            pointer-events: none;
            z-index: 1;
        }

        .uptime-fill {
            background: linear-gradient(90deg, var(--success), #4caf50);
            height: 100%;
            border-radius: 4px 0 0 4px;
            position: relative;
        }

        .uptime-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(to bottom, 
                rgba(255, 255, 255, 0.1) 0%, 
                rgba(255, 255, 255, 0) 50%,
                rgba(0, 0, 0, 0.1) 100%);
        }

        .uptime-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 600;
            letter-spacing: 0.5px;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
            z-index: 2;
        }

        /* Information sections styled like trading terminals */
        .info-section {
            background-color: #1a1d24;
            border-radius: 6px;
            padding: 1.25rem; /* Reduced from 1.5rem */
            margin-bottom: 1.25rem; /* Reduced from 1.5rem */
            border: 1px solid var(--accent);
            position: relative;
            overflow: hidden;
        }

        /* Add faint grid lines like a trading terminal */
        .info-section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(to right, rgba(48, 54, 61, 0.05) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(48, 54, 61, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            opacity: 0.3;
            pointer-events: none;
        }

        .info-section h2 {
            font-size: 1rem; /* Reduced from 1.1rem */
            margin-bottom: 0.75rem; /* Reduced from 1rem */
            padding-bottom: 0.4rem; /* Reduced from 0.5rem */
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            position: relative;
            z-index: 1;
        }

        .info-section h2 i {
            margin-right: 0.5rem;
            color: var(--success);
        }

        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); /* Changed from 250px */
            gap: 0.5rem; /* Reduced from 0.75rem */
            position: relative;
            z-index: 1;
        }

        .info-item {
            display: flex;
            flex-direction: column;
            padding: 0.6rem; /* Reduced from 0.75rem */
            border-radius: 4px;
            background-color: #181e25;
            border-left: 3px solid var(--accent);
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease, border-left-color 0.3s ease;
        }

        .info-item:hover {
            background-color: #1e252e;
            border-left-color: var(--success);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        /* Add subtle ticker style animation to info items on hover */
        .info-item:hover::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--success), transparent);
            animation: tickerScan 2s infinite;
        }

        .info-item.animate-in {
            animation: fadeInUp 0.5s forwards;
        }

        @keyframes fadeInUp {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes tickerScan {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .info-label {
            font-weight: 600;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-bottom: 0.25rem;
            display: flex;
            align-items: center;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .info-label i {
            margin-right: 0.5rem;
            color: var(--success);
        }

        .info-value {
            color: var(--text);
            font-family: 'Fira Code', monospace;
            font-size: 0.9rem; /* Reduced from 0.95rem */
            word-break: break-all;
        }

        .info-value a {
            color: var(--success);
            text-decoration: none;
        }

        .info-value a:hover {
            text-decoration: underline;
        }

        /* History styled like a trading log */
        .history-section {
            background-color: #1a1d24;
            border-radius: 6px;
            padding: 1.25rem; /* Reduced from 1.5rem */
            margin-bottom: 1.25rem; /* Reduced from 1.5rem */
            border: 1px solid var(--accent);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            position: relative;
            overflow: hidden;
        }

        /* Add trading terminal style grid lines */
        .history-section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(to right, rgba(48, 54, 61, 0.05) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(48, 54, 61, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            opacity: 0.3;
            pointer-events: none;
        }

        .history-header {
            cursor: pointer;
            user-select: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .toggle-icon {
            transition: transform 0.3s ease;
        }

        .history-entries {
            max-height: 500px;
            opacity: 1;
            overflow: hidden;
            transition: max-height 0.5s ease, opacity 0.4s ease;
        }

        .history-entries.collapsed {
            max-height: 0;
            opacity: 0;
        }

        .history-header[data-expanded="true"] .toggle-icon {
            transform: rotate(180deg);
        }


        .history-header i {
            margin-right: 0.5rem;
            color: var(--success);
        }

        .history-entry {
            padding: 0.6rem; /* Reduced from 0.75rem */
            border-radius: 4px;
            margin-bottom: 0.4rem; /* Reduced from 0.5rem */
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: #181e25;
            border-left: 3px solid transparent;
            animation: slideIn 0.3s ease;
            opacity: 1;
            animation-fill-mode: forwards;
            position: relative;
            z-index: 1;
            transition: transform 0.2s ease;
        }

        /* Add new class for animation */
        .animate-entry {
            animation: slideIn 0.3s ease forwards;
            opacity: 0;
        }

        .history-entry:hover {
            transform: translateX(5px);
        }

        .history-entry.online {
            border-left-color: var(--success);
        }

        .history-entry.offline {
            border-left-color: var(--danger);
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-10px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        .history-entry:nth-child(2) { animation-delay: 0.1s; }
        .history-entry:nth-child(3) { animation-delay: 0.2s; }
        .history-entry:nth-child(4) { animation-delay: 0.3s; }
        .history-entry:nth-child(5) { animation-delay: 0.4s; }

        .history-timestamp {
            color: var(--text-muted);
            font-size: 0.85rem;
            font-family: 'Fira Code', monospace;
        }

        .history-status {
            font-weight: 600;
            padding: 0.2rem 0.6rem; /* Reduced from 0.25rem 0.75rem */
            border-radius: 3px;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        .history-status.online {
            color: var(--success);
            background-color: var(--success-light);
            border: 1px solid var(--success);
        }

        .history-status.offline {
            color: var(--danger);
            background-color: var(--danger-light);
            border: 1px solid var(--danger);
        }

        .history-status i {
            margin-right: 0.25rem;
        }

        .connection-status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0.75rem; /* Reduced from 0.75rem 1rem */
            background-color: #1a1d24;
            border-radius: 4px;
            font-size: 0.85rem; /* Reduced from 0.9rem */
            color: var(--text-muted);
            margin-bottom: 1rem; /* Reduced from 1.5rem */
            border: 1px solid var(--accent);
            position: relative;
            overflow: hidden;
        }

        /* Add ticker line animation to connection status */
        .connection-status::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--text-muted), transparent);
            animation: tickerScan 3s infinite linear;
        }

        .connection-status i {
            margin-right: 0.25rem;
        }

        .connected {
            color: var(--success);
        }

        .disconnected {
            color: var(--danger);
        }

        /* Refresh button removed */

        .footer {
            text-align: center;
            color: var(--text-muted);
            font-size: 0.75rem; /* Reduced from 0.8rem */
            padding-top: 0.75rem; /* Reduced from 1rem */
            border-top: 1px solid var(--border);
        }

        .realtime-badge {
            background-color: var(--success);
            color: black;
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            margin-left: 0.5rem;
            vertical-align: middle;
            letter-spacing: 0.5px;
            position: relative;
            font-weight: 700;
        }

        .realtime-badge::after {
            content: '';
            position: absolute;
            width: 6px;
            height: 6px;
            background-color: #000;
            border-radius: 50%;
            top: 50%;
            left: 1px;
            transform: translateY(-50%);
            animation: blink 2s infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        /* Enhanced candlestick chart in the header */
        .candlestick {
            position: absolute;
            top: 15px;
            right: 15px;
            display: flex;
            align-items: flex-end;
            height: 40px;
            opacity: 0.6;
            z-index: 1;
        }

        .candle {
            width: 8px;
            margin: 0 3px;
            position: relative;
            transition: height 0.5s ease;
        }

        .candle:hover {
            height: 90% !important;
        }

        .candle::before, .candle::after {
            content: '';
            position: absolute;
            left: 50%;
            width: 2px;
            background-color: currentColor;
            transform: translateX(-50%);
        }

        .candle::before {
            top: -5px;
            height: 5px;
        }

        .candle::after {
            bottom: -5px;
            height: 5px;
        }

        .candle-up {
            background-color: var(--success);
            color: var(--success);
        }

        .candle-down {
            background-color: var(--danger);
            color: var(--danger);
        }

        .candle-1 { height: 60%; }
        .candle-2 { height: 40%; }
        .candle-3 { height: 75%; }
        .candle-4 { height: 30%; }
        .candle-5 { height: 80%; }

        /* Mobile Responsiveness */
        @media (max-width: 768px) {
            .header { padding: 1.25rem; }
            .content { padding: 1.25rem; }
            h1 { font-size: 1.4rem; }
            .logo { font-size: 1.2rem; }
            .info-grid { grid-template-columns: 1fr; }
            
            .history-entry {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .history-status {
                margin-top: 0.5rem;
            }
        }

        @media (max-width: 480px) {
            body { padding: 0.5rem; }
            .container { width: 100%; }
            .header { padding: 1rem; }
            .content { padding: 1rem; }
            .status-indicator { padding: 0.5rem 1rem; font-size: 1rem; }
            .status-message { font-size: 0.95rem; }
            h1 { font-size: 1.2rem; }
            .candlestick { display: none; }
        }

        .status-card, .uptime-bar, .info-section, .history-section, .connection-status {
            margin-bottom: 0.75rem; /* Further reduced margins */
        }

        @keyframes typingEffect {
            from { width: 0 }
            to { width: 58% }
        }

        @keyframes blinkCursor {
            from, to { border-right-color: transparent }
            50% { border-right-color: var(--text) }
        }

        .typing-animation {
            display: inline-block;
            overflow: hidden;
            white-space: nowrap;
            border-right: 2px solid var(--text);
            width: 0;
            animation: 
                typingEffect 1.5s ease forwards,
                blinkCursor 0.75s step-end infinite;
        }

        @keyframes uptimeChange {
            0% { filter: brightness(1); }
            50% { filter: brightness(1.5); }
            100% { filter: brightness(1); }
        }

        .uptime-change {
            animation: uptimeChange 1s ease;
        }


        @keyframes statusPulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); box-shadow: 0 0 10px var(--success); }
            100% { transform: scale(1); }
        }

        .status-change-pulse {
            animation: statusPulse 0.7s ease;
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body>
    <div id="particles-js" class="particles-container"></div>
    <div class="container">
        <div class="header">
            <div class="logo"><i class="fas fa-chart-line"></i> Prodigy Trading Academy</div>
            <h1>Bot Status Monitor <span class="realtime-badge">LIVE</span></h1>
            
            <div class="candlestick">
                <div class="candle candle-up candle-1"></div>
                <div class="candle candle-down candle-2"></div>
                <div class="candle candle-up candle-3"></div>
                <div class="candle candle-down candle-4"></div>
                <div class="candle candle-up candle-5"></div>
            </div>
        </div>
        
        <div class="content">
            <div class="status-card">
                <div id="status" class="status-indicator {{ 'online' if is_online else 'offline' }}">
                    <i class="fas {{ 'fa-circle-check' if is_online else 'fa-circle-exclamation' }} mr-2"></i>
                    {{ "ONLINE" if is_online else "OFFLINE" }}
                </div>
                
                <p id="status-message" class="status-message">
                    {{ "The PTA Student Bot is currently running and serving members." if is_online else "The PTA Bot is currently offline or experiencing issues." }}
                </p>
                
                <div id="last-seen-container" style="{{ 'display: none;' if is_online else '' }}">
                    <p class="last-seen"><i class="fas fa-clock"></i> Last seen online: <span id="last-seen">{{ ph_time_format(last_online) }}</span></p>
                </div>
            </div>
            
            <div class="uptime-bar">
                <div id="uptime-fill" class="uptime-fill" style="width: {{ uptime_percentage }}%;"></div>
                <div id="uptime-text" class="uptime-text">{{ "%.2f"|format(uptime_percentage) }}% Uptime</div>
            </div>
            
            <div class="info-section">
                <h2><i class="fas fa-info-circle"></i> System Information</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label"><i class="fab fa-telegram"></i> Bot</span>
                        <span class="info-value">
                            <a href="{{ telegram_link }}" target="_blank">
                                {{ bot_name }}
                            </a>
                        </span>
                    </div>
                    
                    <div class="info-item">
                        <span class="info-label"><i class="fas fa-server"></i> Environment</span>
                        <span id="server-time" class="info-value">{{ environment_info }}</span>
                    </div>
                    
                    <div class="info-item">
                        <span class="info-label"><i class="fas fa-history"></i> Last Check</span>
                        <span id="last-check" class="info-value">{{ ph_time_format(last_check) }}</span>
                    </div>
                    
                    <div class="info-item">
                        <span class="info-label"><i class="fas fa-hourglass-half"></i> System Uptime</span>
                        <span id="uptime" class="info-value">{{ str(datetime.now() - start_time).split('.')[0] }}</span>
                    </div>
                </div>
            </div>
            
            <div class="history-section">
                <h2 class="history-header" id="history-toggle">
                    <i class="fas fa-chart-line"></i> Recent Status History
                    <span class="toggle-icon"><i class="fas fa-chevron-down"></i></span>
                </h2>
                <div id="history-entries" class="history-entries collapsed">
                    {% for entry in status_history|reverse %}
                        {% if loop.index <= 10 %}
                            <div class="history-entry {{ 'online' if entry.status else 'offline' }}" style="animation-delay: {{ loop.index * 0.1 }}s;">
                                <span class="history-timestamp">{{ ph_time_format(entry.timestamp) }}</span>
                                <span class="history-status {{ 'online' if entry.status else 'offline' }}">
                                    <i class="fas {{ 'fa-circle-check' if entry.status else 'fa-circle-exclamation' }}"></i>
                                    {{ "ONLINE" if entry.status else "OFFLINE" }}
                                </span>
                            </div>
                        {% endif %}
                    {% endfor %}
                </div>
            </div>
            
            <div class="connection-status">
                <div>
                    <i class="fas fa-clock"></i> Last update: <span id="last-update">{{ ph_time_format(datetime.now()).split(' ')[1] }}</span>
                </div>
                <div id="connection-status" class="connected">
                    <i class="fas fa-plug"></i> Connecting to server...
                </div>
            </div>

            <div class="footer">
                <p>© {{ datetime.now().year }} Prodigy Trading Academy | Bot Version: Alpha Release 3.1</p>
            </div>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Create socket with polling transport only
            const socket = io({
                transports: ['polling'],
                upgrade: false  // Disable transport upgrades
            });
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;
            
            // Apply dynamic animation to history entries
            const historyEntries = document.querySelectorAll('.history-entry');
            historyEntries.forEach((entry, index) => {
                entry.style.animationDelay = `${index * 0.1}s`;
            });
            
            socket.on('connect', function() {
                const connectionStatus = document.getElementById('connection-status');
                connectionStatus.innerHTML = '<i class="fas fa-plug"></i> Connected to server';
                connectionStatus.className = 'connected';
                reconnectAttempts = 0;
            });
            
            socket.on('disconnect', function() {
                const connectionStatus = document.getElementById('connection-status');
                connectionStatus.innerHTML = '<i class="fas fa-plug-circle-exclamation"></i> Disconnected, attempting to reconnect...';
                connectionStatus.className = 'disconnected';
                
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    setTimeout(() => {
                        socket.connect();
                    }, 2000);
                } else {
                    connectionStatus.textContent = 'Failed to reconnect. Please refresh the page.';
                }
            });
            
            socket.on('status_update', function(data) {
                // Update status indicator
                const statusElement = document.getElementById('status');
                const statusMessageElement = document.getElementById('status-message');
                const lastSeenContainer = document.getElementById('last-seen-container');
                
                // Check if status changed
                if (statusElement.className !== `status-indicator ${data.is_online ? 'online' : 'offline'}`) {
                    // Update class name to reflect new status
                    statusElement.className = `status-indicator ${data.is_online ? 'online' : 'offline'}`;
                    
                    // Update icon and text
                    statusElement.innerHTML = `<i class="fas ${data.is_online ? 'fa-circle-check' : 'fa-circle-exclamation'} mr-2"></i>
                                            ${data.is_online ? 'ONLINE' : 'OFFLINE'}`;
                    
                    // Update status message
                    statusMessageElement.textContent = data.is_online ? 
                        "The PTA Student Bot is currently running and serving members." : 
                        "The PTA Student Bot is currently offline or experiencing issues.";
                        
                    // Show/hide last seen container
                    lastSeenContainer.style.display = data.is_online ? 'none' : '';
                    
                    // If offline, update the last seen time
                    if (!data.is_online && document.getElementById('last-seen')) {
                        document.getElementById('last-seen').textContent = data.last_online;
                    }
                    
                    // Add pulse animation
                    statusElement.classList.add('status-change-pulse');
                    setTimeout(() => statusElement.classList.remove('status-change-pulse'), 700);
                }
                
                // Update info section
                document.getElementById('server-time').textContent = data.server_time;
                document.getElementById('last-check').textContent = data.last_check;
                document.getElementById('uptime').textContent = data.uptime;

                // Update uptime bar
                function animateValue(obj, start, end, duration) {
                    let startTimestamp = null;
                    const step = (timestamp) => {
                        if (!startTimestamp) startTimestamp = timestamp;
                        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                        const currentValue = start + progress * (end - start);
                        obj.textContent = currentValue.toFixed(2) + '% Uptime';
                        if (progress < 1) {
                            window.requestAnimationFrame(step);
                        }
                    };
                    window.requestAnimationFrame(step);
                }

                // Update uptime bar with animation
                const uptimePercent = data.uptime_percentage;
                const uptimeFill = document.getElementById('uptime-fill');
                const currentWidth = parseFloat(uptimeFill.style.width) || 0;

                // Add flash effect if uptime changes significantly
                if (Math.abs(uptimePercent - currentWidth) > 5) {
                    uptimeFill.classList.add('uptime-change');
                    setTimeout(() => uptimeFill.classList.remove('uptime-change'), 1000);
                }

                // Animate the width smoothly
                const animateWidth = (element, start, end, duration) => {
                    const startTime = performance.now();
                    
                    const updateWidth = (currentTime) => {
                        const elapsedTime = currentTime - startTime;
                        const progress = Math.min(elapsedTime / duration, 1);
                        const easeProgress = 1 - Math.pow(1 - progress, 3); // Cubic ease out
                        const currentWidth = start + (end - start) * easeProgress;
                        
                        element.style.width = `${currentWidth}%`;
                        
                        if (progress < 1) {
                            requestAnimationFrame(updateWidth);
                        }
                    };
                    
                    requestAnimationFrame(updateWidth);
                };

                // Animate both the width and the text counter
                animateWidth(uptimeFill, currentWidth, uptimePercent, 800);

                // Animate the text counter
                const uptimeText = document.getElementById('uptime-text');
                const currentTextValue = parseFloat(uptimeText.textContent) || 0;
                animateValue(uptimeText, currentTextValue, uptimePercent, 800);
                
                // Update history with animation only on changes
                const historyContainer = document.getElementById('history-entries');
                const previousTimestamps = Array.from(historyContainer.querySelectorAll('.history-entry')).map(
                    entry => entry.querySelector('.history-timestamp').textContent
                );

                // Don't clear and rebuild on every update
                if (historyContainer.childElementCount === 0 || 
                    data.recent_history.some(entry => !previousTimestamps.includes(entry.timestamp))) {
                    
                    // Only rebuild if there are new entries
                    historyContainer.innerHTML = '';
                    
                    data.recent_history.forEach((entry, index) => {
                        const entryElement = document.createElement('div');
                        entryElement.className = `history-entry ${entry.status ? 'online' : 'offline'}`;
                        
                        // Only apply animation class if first load or new entry
                        if (previousTimestamps.length === 0 || !previousTimestamps.includes(entry.timestamp)) {
                            entryElement.classList.add('animate-entry');
                            entryElement.style.animationDelay = `${index * 0.1}s`;
                        }
                        
                        const timestampSpan = document.createElement('span');
                        timestampSpan.className = 'history-timestamp';
                        timestampSpan.textContent = entry.timestamp;
                        
                        const statusSpan = document.createElement('span');
                        statusSpan.className = `history-status ${entry.status ? 'online' : 'offline'}`;
                        statusSpan.innerHTML = `<i class="fas ${entry.status ? 'fa-circle-check' : 'fa-circle-exclamation'}"></i> ${entry.status ? 'ONLINE' : 'OFFLINE'}`;
                        
                        entryElement.appendChild(timestampSpan);
                        entryElement.appendChild(statusSpan);
                        historyContainer.appendChild(entryElement);
                    });
                }
                
                // Update last update time
                document.getElementById('last-update').textContent = new Intl.DateTimeFormat('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true,
                    timeZone: 'Asia/Manila'
                }).format(new Date());
            });

            // Update history with animation only on changes
            const historyContainer = document.getElementById('history-entries');
            const isCurrentlyExpanded = document.getElementById('history-toggle').getAttribute('data-expanded') === 'true';
            const previousTimestamps = Array.from(historyContainer.querySelectorAll('.history-entry')).map(
                entry => entry.querySelector('.history-timestamp').textContent
            );

            // Don't clear and rebuild on every update
            if (historyContainer.childElementCount === 0 || 
                data.recent_history.some(entry => !previousTimestamps.includes(entry.timestamp))) {
                
                // Only rebuild if there are new entries
                historyContainer.innerHTML = '';
                
                data.recent_history.forEach((entry, index) => {
                    // Create entries as before...

                    // Make sure entries stay collapsed if that was the current state
                    if (!isCurrentlyExpanded) {
                        historyContainer.classList.add('collapsed');
                    }
                });
            }
            
            // Manual refresh button
            document.getElementById('refresh-btn').addEventListener('click', function() {
                this.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing...';
                setTimeout(() => {
                    location.reload();
                }, 500);
            });

            document.querySelectorAll('.info-item').forEach((item, index) => {
                setTimeout(() => {
                    item.classList.add('animate-in');
                }, index * 150);
            });

        });
        const historyToggle = document.getElementById('history-toggle');
        const historyEntries = document.getElementById('history-entries');

        historyToggle.addEventListener('click', function() {
            const isExpanded = this.getAttribute('data-expanded') === 'true';
            const newState = !isExpanded;
            
            this.setAttribute('data-expanded', newState);
            
            if (newState) {
                historyEntries.classList.remove('collapsed');
            } else {
                historyEntries.classList.add('collapsed');
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    # Get environment information
    environment_info = f"{platform.system()} {platform.release()}"
    
    return render_template_string(
        STATUS_PAGE,
        is_online=is_online,
        last_online=last_online,
        last_check=last_check,
        bot_url=BOT_URL,
        bot_name=BOT_NAME,  # Add this line
        telegram_link=TELEGRAM_BOT_LINK,  # Add this line
        check_interval=CHECK_INTERVAL,
        status_history=status_history,
        uptime_percentage=uptime_percentage,
        start_time=start_time,
        datetime=datetime,
        str=str,
        environment_info=environment_info,
        ph_time_format=ph_time_format
    )

# Start monitoring thread
@socketio.on('connect')
def handle_connect():
    print("Client connected")

if __name__ == '__main__':
    # Start the monitoring thread
    monitor_thread = threading.Thread(target=check_bot_status, daemon=True)
    monitor_thread.start()
    
    # This will run without warnings
    port = int(os.environ.get('PORT', 8081))
    
    # Determine if in production environment
    is_production = os.environ.get('RENDER', False)
    
    # Silence logging
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    if is_production:
        # Silence all engineio and socketio errors in production
        logging.getLogger('engineio').setLevel(logging.ERROR)
        logging.getLogger('socketio').setLevel(logging.ERROR)
        logging.getLogger('waitress').setLevel(logging.ERROR)
        
        # Use Waitress in production
        from waitress import serve
        print(f"Starting production server on port {port}")
        
        # Serve the application with Waitress
        serve(app, host='0.0.0.0', port=port)
    else:
        # Use development server locally
        socketio.run(app, host='0.0.0.0', port=port, debug=False)