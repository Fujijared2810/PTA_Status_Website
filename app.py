from flask import Flask, render_template_string
from flask_socketio import SocketIO
import requests
import time
import threading
from datetime import datetime
import os
import platform

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ptastatus-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
BOT_URL = os.environ.get('BOT_URL', "http://127.0.0.1:8080/")  # Use environment variable in production
BOT_NAME = "@PTAStudentBot"  # Add this line
TELEGRAM_BOT_LINK = "https://t.me/PTAStudentBot"  # Add this line - note: no @ symbol in the URL
CHECK_INTERVAL = 10  # Check every 10 seconds for more responsive updates
MAX_HISTORY_ENTRIES = 100

# Status tracking
last_check = None
is_online = False
last_online = None
status_history = []
uptime_percentage = 100.0
start_time = datetime.now()

def check_bot_status():
    global last_check, is_online, last_online, status_history, uptime_percentage
    
    while True:
        try:
            # Record check time
            check_time = datetime.now()
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
                'last_online': last_online.strftime('%Y-%m-%d %H:%M:%S') if last_online else 'Never',
                'last_check': last_check.strftime('%Y-%m-%d %H:%M:%S') if last_check else 'Never',
                'uptime_percentage': round(uptime_percentage, 2),
                'server_time': f"{platform.system()} {platform.release()}",  # Update this line
                'uptime': str(datetime.now() - start_time).split('.')[0],
                'recent_history': [
                    {
                        'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
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
                'last_online': last_online.strftime('%Y-%m-%d %H:%M:%S') if last_online else 'Never',
                'last_check': last_check.strftime('%Y-%m-%d %H:%M:%S') if last_check else 'Never',
                'uptime_percentage': round(uptime_percentage, 2),
                'server_time': f"{platform.system()} {platform.release()}",  # Update this line
                'uptime': str(datetime.now() - start_time).split('.')[0],
                'recent_history': [
                    {
                        'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
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
        :root {
            --primary: #3b82f6;
            --primary-dark: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --background: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.8);
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: rgba(148, 163, 184, 0.1);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            transition: all 0.3s ease;
        }
        
        body {
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
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
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            width: 90%;
            max-width: 850px;
            overflow: hidden;
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            opacity: 0;
            transform: translateY(20px);
            animation: fadeIn 0.6s forwards;
        }
        
        @keyframes fadeIn {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .header {
            background: linear-gradient(to right, rgba(30, 41, 59, 0.8), rgba(30, 58, 138, 0.8));
            padding: 2rem;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(148, 163, 184, 0.1) 0%, rgba(148, 163, 184, 0) 70%);
            top: -50%;
            left: -50%;
            animation: rotate 60s linear infinite;
        }
        
        @keyframes rotate {
            to {
                transform: rotate(360deg);
            }
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 800;
            display: inline-flex;
            align-items: center;
            margin-bottom: 0.5rem;
            color: var(--primary);
            text-shadow: 0 2px 10px rgba(59, 130, 246, 0.3);
            position: relative;
            z-index: 1;
        }
        
        .logo i {
            margin-right: 0.5rem;
            font-size: 1.8rem;
        }
        
        h1 {
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
            position: relative;
            z-index: 1;
        }
        
        .content {
            padding: 1.5rem 2rem;
        }
        
        .status-card {
            background-color: rgba(15, 23, 42, 0.6);
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            margin-bottom: 2rem;
            transform: scale(0.98);
            animation: pulse 2s infinite alternate;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
        }
        
        @keyframes pulse {
            to {
                transform: scale(1);
                box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
            }
        }
        
        .status-indicator {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.7rem 1.8rem;
            border-radius: 50px;
            font-weight: 700;
            font-size: 1.2rem;
            margin-bottom: 1rem;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }
        
        .status-indicator::before {
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0) 100%);
            top: 0;
            left: -100%;
            animation: shine 2s infinite;
        }
        
        @keyframes shine {
            to {
                left: 100%;
            }
        }
        
        .status-indicator.online {
            background-color: var(--success);
            color: white;
        }
        
        .status-indicator.offline {
            background-color: var(--danger);
            color: white;
        }
        
        .status-message {
            font-size: 1.1rem;
            margin-bottom: 1rem;
        }
        
        .last-seen {
            color: var(--text-muted);
            font-style: italic;
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }
        
        .uptime-bar {
            background-color: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            height: 40px;
            overflow: hidden;
            position: relative;
            margin-bottom: 2rem;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .uptime-fill {
            background: linear-gradient(90deg, #10b981, #34d399);
            height: 100%;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
        }
        
        .uptime-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 600;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
            letter-spacing: 0.5px;
        }
        
        .info-section {
            background-color: rgba(15, 23, 42, 0.6);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            border-left: 4px solid var(--primary);
        }
        
        .info-section h2 {
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
            color: var(--primary);
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 1rem;
        }
        
        .info-item {
            display: flex;
            flex-direction: column;
            padding: 0.75rem;
            border-radius: 8px;
            background-color: rgba(30, 41, 59, 0.4);
            transition: all 0.3s ease;
        }
        
        .info-item:hover {
            background-color: rgba(30, 41, 59, 0.6);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        
        .info-label {
            font-weight: 600;
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-bottom: 0.25rem;
            display: flex;
            align-items: center;
        }
        
        .info-label i {
            margin-right: 0.5rem;
            color: var(--primary);
        }
        
        .info-value {
            color: var(--text);
            font-family: 'Fira Code', monospace;
            font-size: 0.95rem;
            word-break: break-all;
        }
        
        .info-value a {
            color: var(--primary);
            text-decoration: none;
        }
        
        .info-value a:hover {
            text-decoration: underline;
        }
        
        .history-section {
            background-color: rgba(15, 23, 42, 0.6);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        
        .history-header {
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
            color: var(--primary);
            display: flex;
            align-items: center;
        }
        
        .history-header i {
            margin-right: 0.5rem;
        }
        
        .history-entry {
            padding: 0.75rem;
            border-radius: 8px;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: rgba(30, 41, 59, 0.4);
            animation: slideIn 0.3s ease;
            opacity: 0;
            animation-fill-mode: forwards;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .history-entry:nth-child(2) {
            animation-delay: 0.1s;
        }
        
        .history-entry:nth-child(3) {
            animation-delay: 0.2s;
        }
        
        .history-entry:nth-child(4) {
            animation-delay: 0.3s;
        }
        
        .history-entry:nth-child(5) {
            animation-delay: 0.4s;
        }
        
        .history-timestamp {
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        
        .history-status {
            font-weight: 600;
            padding: 0.25rem 0.75rem;
            border-radius: 50px;
            font-size: 0.8rem;
            display: flex;
            align-items: center;
        }
        
        .history-status.online {
            color: var(--success);
            background-color: rgba(16, 185, 129, 0.1);
        }
        
        .history-status.offline {
            color: var(--danger);
            background-color: rgba(239, 68, 68, 0.1);
        }
        
        .history-status i {
            margin-right: 0.25rem;
        }
        
        .connection-status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem;
            background-color: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
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
        
        .refresh-btn {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            margin-bottom: 1rem;
        }
        
        .refresh-btn:hover {
            background-color: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        }
        
        .refresh-btn i {
            margin-right: 0.5rem;
        }
        
        .footer {
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }
        
        .realtime-badge {
            background-color: var(--success);
            color: white;
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 50px;
            margin-left: 0.5rem;
            vertical-align: middle;
            letter-spacing: 0.5px;
            position: relative;
        }
        
        .realtime-badge::after {
            content: '';
            position: absolute;
            width: 6px;
            height: 6px;
            background-color: white;
            border-radius: 50%;
            top: 50%;
            left: 8px;
            transform: translateY(-50%);
            animation: blink 2s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* Mobile Responsiveness */
        @media (max-width: 768px) {
            .header {
                padding: 1.5rem;
            }
            
            .content {
                padding: 1.25rem;
            }
            
            h1 {
                font-size: 1.5rem;
            }
            
            .logo {
                font-size: 1.25rem;
            }
            
            .info-grid {
                grid-template-columns: 1fr;
            }
            
            .history-entry {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .history-status {
                margin-top: 0.5rem;
            }
        }
        
        @media (max-width: 480px) {
            body {
                padding: 0.5rem;
            }
            
            .container {
                width: 100%;
                border-radius: 8px;
            }
            
            .header {
                padding: 1rem;
            }
            
            .content {
                padding: 1rem;
            }
            
            .status-indicator {
                padding: 0.6rem 1.5rem;
                font-size: 1rem;
            }
            
            .status-message {
                font-size: 1rem;
            }
            
            h1 {
                font-size: 1.25rem;
            }
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo"><i class="fas fa-school"></i> Prodigy Trading Academy</div>
            <h1>Bot Status Monitor <span class="realtime-badge">LIVE</span></h1>
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
                    <p class="last-seen"><i class="fas fa-clock"></i> Last seen online: <span id="last-seen">{{ last_online.strftime('%Y-%m-%d %H:%M:%S') if last_online else 'Never' }}</span></p>
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
                        <span id="last-check" class="info-value">{{ last_check.strftime('%Y-%m-%d %H:%M:%S') if last_check else 'Never' }}</span>
                    </div>
                    
                    <div class="info-item">
                        <span class="info-label"><i class="fas fa-hourglass-half"></i> System Uptime</span>
                        <span id="uptime" class="info-value">{{ str(datetime.now() - start_time).split('.')[0] }}</span>
                    </div>
                </div>
            </div>
            
            <div class="history-section">
                <h2 class="history-header"><i class="fas fa-chart-line"></i> Recent Status History</h2>
                <div id="history-entries">
                    {% for entry in status_history|reverse %}
                        {% if loop.index <= 10 %}
                            <div class="history-entry" style="animation-delay: {{ loop.index * 0.1 }}s;">
                                <span class="history-timestamp">{{ entry.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</span>
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
                    <i class="fas fa-clock"></i> Last update: <span id="last-update">{{ datetime.now().strftime('%H:%M:%S') }}</span>
                </div>
                <div id="connection-status" class="connected">
                    <i class="fas fa-plug"></i> Connecting to server...
                </div>
            </div>
            
            <button id="refresh-btn" class="refresh-btn">
                <i class="fas fa-sync-alt"></i> Refresh Page
            </button>
            
            <div class="footer">
                <p>This status page automatically updates in real-time</p>
                <p>© {{ datetime.now().year }} Prodigy Trading Academy | Bot Version: Alpha Release 3.0</p>
            </div>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const socket = io();
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
                
                if (data.is_online) {
                    statusElement.innerHTML = '<i class="fas fa-circle-check mr-2"></i> ONLINE';
                    statusElement.className = 'status-indicator online';
                    statusMessageElement.textContent = 'The PTA Student Bot is currently running and serving members.';
                    document.getElementById('last-seen-container').style.display = 'none';
                } else {
                    statusElement.innerHTML = '<i class="fas fa-circle-exclamation mr-2"></i> OFFLINE';
                    statusElement.className = 'status-indicator offline';
                    statusMessageElement.textContent = 'The PTA Bot is currently offline or experiencing issues.';
                    document.getElementById('last-seen-container').style.display = 'block';
                    document.getElementById('last-seen').textContent = data.last_online;
                }
                
                // Update info section
                document.getElementById('server-time').textContent = data.server_time;
                document.getElementById('last-check').textContent = data.last_check;
                document.getElementById('uptime').textContent = data.uptime;
                
                // Update uptime bar
                const uptimePercent = data.uptime_percentage;
                document.getElementById('uptime-fill').style.width = uptimePercent + '%';
                document.getElementById('uptime-text').textContent = uptimePercent.toFixed(2) + '% Uptime';
                
                // Update history with animation
                const historyContainer = document.getElementById('history-entries');
                historyContainer.innerHTML = '';
                
                data.recent_history.forEach((entry, index) => {
                    const entryElement = document.createElement('div');
                    entryElement.className = 'history-entry';
                    entryElement.style.animationDelay = `${index * 0.1}s`;
                    
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
                
                // Update last update time
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            });
            
            // Manual refresh button
            document.getElementById('refresh-btn').addEventListener('click', function() {
                this.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing...';
                setTimeout(() => {
                    location.reload();
                }, 500);
            });
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
        environment_info=environment_info
    )

# Start monitoring thread
@socketio.on('connect')
def handle_connect():
    print("Client connected")

if __name__ == '__main__':
    # Start the monitoring thread
    monitor_thread = threading.Thread(target=check_bot_status, daemon=True)
    monitor_thread.start()
    
    # This will run in both local development and on Render
    port = int(os.environ.get('PORT', 8081))
    socketio.run(app, host='0.0.0.0', port=port)