"""
Cold-Chain Monitoring System - Fog Node (Local Manager)
Subscribes to MQTT, displays Flask web dashboard,
uploads data to ThingSpeak cloud, sends email alerts,
AI-powered analysis via OpenAI GPT.

Team 21 - CS131 IoT
"""

import json
import time
import threading
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import deque
from flask import Flask, render_template_string, jsonify, request as flask_request

# ===== CONFIGURATION =====
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "coldchain/data"

THINGSPEAK_API_KEY = ""
THINGSPEAK_URL = "https://api.thingspeak.com/update"
THINGSPEAK_INTERVAL = 15

EMAIL_SENDER = "gneenstone@gmail.com"
EMAIL_PASSWORD = "bhtn ycji hunp luno"
EMAIL_RECEIVER = "plin068@ucr.edu"
EMAIL_COOLDOWN = 60

OPENAI_API_KEY = ""

# ===== STATE =====
latest_data = {
    "temp_filtered": 0,
    "light": 0,
    "door": 0,
    "risk": "N/A",
    "timestamp": "waiting..."
}
history = deque(maxlen=300)  # ~10 minutes of data at 2s intervals
offline_buffer = []
last_thingspeak_time = 0
last_email_time = 0

# ===== EMAIL ALERT =====
def send_alert_email(subject, body):
    global last_email_time
    now = time.time()
    if now - last_email_time < EMAIL_COOLDOWN:
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        last_email_time = now
        print("[EMAIL] Alert sent: {}".format(subject))
    except Exception as e:
        print("[EMAIL] Failed to send: {}".format(e))

def check_alerts(data):
    temp = data.get("temp_filtered", 0)
    door = data.get("door", 0)
    risk = data.get("risk", "LOW")
    light = data.get("light", 0)
    timestamp = data.get("timestamp", "unknown")
    alerts = []
    if temp > 30.0:
        alerts.append("Temperature CRITICAL: {}C (threshold: 30C)".format(temp))
    if door == 1:
        alerts.append("Door is OPEN (light level: {})".format(light))
    if risk != "LOW":
        alerts.append("Risk Level: {}".format(risk))
    if alerts:
        subject = "Cold-Chain ALERT - {}".format(risk)
        body = """
        <html><body style="font-family:Arial;padding:20px;">
        <h2 style="color:#e74c3c;">Cold-Chain Monitoring Alert</h2>
        <p><strong>Time:</strong> {}</p><hr>
        <ul>{}</ul><hr>
        <h3>Current Readings:</h3>
        <table style="border-collapse:collapse;">
        <tr><td style="padding:5px 15px;border:1px solid #ddd;"><strong>Temperature</strong></td><td style="padding:5px 15px;border:1px solid #ddd;">{}C</td></tr>
        <tr><td style="padding:5px 15px;border:1px solid #ddd;"><strong>Light</strong></td><td style="padding:5px 15px;border:1px solid #ddd;">{}</td></tr>
        <tr><td style="padding:5px 15px;border:1px solid #ddd;"><strong>Door</strong></td><td style="padding:5px 15px;border:1px solid #ddd;">{}</td></tr>
        <tr><td style="padding:5px 15px;border:1px solid #ddd;"><strong>Risk</strong></td><td style="padding:5px 15px;border:1px solid #ddd;">{}</td></tr>
        </table><hr>
        <p style="color:#999;font-size:12px;">Cold-Chain Monitor - Team 21 CS131 IoT</p>
        </body></html>
        """.format(timestamp, "".join(["<li>{}</li>".format(a) for a in alerts]),
                   temp, light, "OPEN" if door else "CLOSED", risk)
        send_alert_email(subject, body)

# ===== AI ANALYSIS =====
def generate_ai_summary():
    """Build a detailed summary of collected data for GPT."""
    data_list = list(history)
    if len(data_list) == 0:
        return None, "No data available yet."

    temps = [d.get("temp_filtered", 0) for d in data_list if d.get("temp_filtered", 0) != 0]
    lights = [d.get("light", 0) for d in data_list]
    doors = [d.get("door", 0) for d in data_list]
    risks = [d.get("risk", "LOW") for d in data_list]

    if not temps:
        return None, "No temperature data available."

    total = len(data_list)
    time_span_sec = total * 2
    time_span_min = time_span_sec / 60.0
    first_time = data_list[0].get("timestamp", "?")
    last_time = data_list[-1].get("timestamp", "?")

    # Temperature stats
    avg_temp = sum(temps) / len(temps)
    min_temp = min(temps)
    max_temp = max(temps)

    # Temperature trend (compare first third vs last third)
    third = len(temps) // 3
    if third > 0:
        first_avg = sum(temps[:third]) / third
        last_avg = sum(temps[-third:]) / third
        if last_avg - first_avg > 1.5:
            trend = "rising significantly"
        elif last_avg - first_avg > 0.5:
            trend = "rising slightly"
        elif first_avg - last_avg > 1.5:
            trend = "falling significantly"
        elif first_avg - last_avg > 0.5:
            trend = "falling slightly"
        else:
            trend = "stable"
    else:
        trend = "insufficient data"

    # Temperature exceedance analysis
    temp_above_30 = sum(1 for t in temps if t > 30.0)
    temp_above_25 = sum(1 for t in temps if t > 25.0)
    time_above_30_sec = temp_above_30 * 2
    time_above_25_sec = temp_above_25 * 2
    pct_above_30 = (temp_above_30 / len(temps)) * 100 if temps else 0
    pct_above_25 = (temp_above_25 / len(temps)) * 100 if temps else 0

    # Door event analysis
    door_open_readings = sum(1 for d in doors if d == 1)
    door_open_time_sec = door_open_readings * 2
    door_open_pct = (door_open_readings / total) * 100 if total > 0 else 0
    # Count door open events (transitions from 0 to 1)
    door_events = 0
    for i in range(1, len(doors)):
        if doors[i] == 1 and doors[i-1] == 0:
            door_events += 1
    # If first reading is door open, count it
    if len(doors) > 0 and doors[0] == 1:
        door_events += 1

    # Risk distribution
    risk_low = sum(1 for r in risks if r == "LOW")
    risk_med = sum(1 for r in risks if r == "MEDIUM")
    risk_high = sum(1 for r in risks if r == "HIGH")
    risk_low_pct = (risk_low / total) * 100 if total > 0 else 0
    risk_med_pct = (risk_med / total) * 100 if total > 0 else 0
    risk_high_pct = (risk_high / total) * 100 if total > 0 else 0

    summary = """Cold-Chain Monitoring System - Detailed Data Report
=== DATA COLLECTION ===
Time range: {} to {}
Duration: {:.1f} minutes ({} seconds)
Total readings: {} (every 2 seconds)

=== TEMPERATURE ANALYSIS ===
Current: {:.1f}C
Average: {:.1f}C | Min: {:.1f}C | Max: {:.1f}C
Trend: {}
Time above 30C (DANGER): {} readings = {} seconds ({:.1f}% of monitoring period)
Time above 25C (CAUTION): {} readings = {} seconds ({:.1f}% of monitoring period)

=== DOOR STATUS ===
Door open events: {} times
Total door-open duration: {} seconds ({:.1f}% of monitoring period)
Current door status: {}

=== RISK LEVEL DISTRIBUTION ===
LOW (safe): {} readings ({:.1f}%)
MEDIUM (caution): {} readings ({:.1f}%)
HIGH (critical): {} readings ({:.1f}%)

=== CURRENT STATUS ===
Temperature: {:.1f}C | Door: {} | Risk: {} | Light: {}""".format(
        first_time, last_time,
        time_span_min, time_span_sec,
        total,
        temps[-1],
        avg_temp, min_temp, max_temp,
        trend,
        temp_above_30, time_above_30_sec, pct_above_30,
        temp_above_25, time_above_25_sec, pct_above_25,
        door_events,
        door_open_time_sec, door_open_pct,
        "OPEN" if doors[-1] else "CLOSED",
        risk_low, risk_low_pct,
        risk_med, risk_med_pct,
        risk_high, risk_high_pct,
        temps[-1], "OPEN" if doors[-1] else "CLOSED", risks[-1], lights[-1]
    )
    return summary, None

def call_openai(summary):
    """Call OpenAI GPT API with the data summary."""
    try:
        headers = {
            "Authorization": "Bearer {}".format(OPENAI_API_KEY),
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional cold-chain monitoring analyst for a medical vaccine storage facility. You receive detailed sensor data reports and must provide a comprehensive analysis. Structure your response as follows:\n\n1. DATA OVERVIEW: How long was data collected, how many readings total.\n2. TEMPERATURE ASSESSMENT: Current temp, trend, how long above danger/caution thresholds. Is the storage unit maintaining safe conditions?\n3. DOOR SECURITY: How many times was the door opened, total open duration. Were any door events concerning?\n4. RISK SUMMARY: What percentage of time was the system in each risk level?\n5. OVERALL VERDICT: Rate the overall cold-chain integrity as PASS, CAUTION, or FAIL with a brief explanation.\n6. RECOMMENDATIONS: 1-2 actionable suggestions if any issues found.\n\nUse clear headings. Be specific with numbers and percentages. Keep total response under 250 words."
                },
                {
                    "role": "user",
                    "content": summary
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        r = requests.post("https://api.openai.com/v1/chat/completions",
                         headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        else:
            return "API Error {}: {}".format(r.status_code, r.text[:200])
    except Exception as e:
        return "Error calling OpenAI: {}".format(str(e))

# ===== FLASK APP =====
app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Cold-Chain Monitor - Dashboard</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; }
        .header { background: #16213e; padding: 20px; text-align: center; }
        .header h1 { font-size: 28px; color: #e94560; }
        .header p { color: #999; margin-top: 5px; }
        .container { max-width: 1000px; margin: 20px auto; padding: 0 20px; }
        .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .card { background: #16213e; border-radius: 12px; padding: 20px; text-align: center; }
        .card .label { color: #999; font-size: 14px; margin-bottom: 8px; }
        .card .value { font-size: 36px; font-weight: bold; }
        .card .unit { font-size: 16px; color: #999; }
        .risk-LOW { color: #00ff88; }
        .risk-MEDIUM { color: #ffaa00; }
        .risk-HIGH { color: #ff4444; animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0.5; } }
        .status { background: #16213e; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .status h2 { color: #e94560; margin-bottom: 10px; }
        .alert-banner { background: #2d1b1b; border: 1px solid #e74c3c; border-radius: 8px; padding: 15px; margin-bottom: 20px; display: none; }
        .alert-banner.active { display: block; }
        .alert-banner h3 { color: #e74c3c; margin-bottom: 5px; }
        .alert-banner p { color: #ffaa00; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
        th { color: #999; }
        .door-open { color: #ffaa00; }
        .door-closed { color: #00ff88; }
        .timestamp { color: #666; font-size: 12px; text-align: center; margin-top: 10px; }
        .email-status { background: #16213e; border-radius: 12px; padding: 15px; margin-bottom: 20px; text-align: center; }
        .email-status .on { color: #00ff88; }
        .ai-section { background: #16213e; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .ai-section h2 { color: #4fc3f7; margin-bottom: 10px; }
        .ai-btn { background: #4fc3f7; color: #1a1a2e; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
        .ai-btn:hover { background: #81d4fa; }
        .ai-btn:disabled { background: #555; cursor: not-allowed; }
        .ai-result { margin-top: 15px; padding: 15px; background: #0d1117; border-radius: 8px; border-left: 4px solid #4fc3f7; line-height: 1.6; white-space: pre-wrap; display: none; }
        .ai-result.active { display: block; }
        .ai-loading { color: #4fc3f7; display: none; margin-top: 10px; }
        .ai-loading.active { display: block; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Cold-Chain Monitor</h1>
        <p>Team 21 - CS131 IoT | Real-time Dashboard</p>
    </div>
    <div class="container">
        <div class="alert-banner" id="alertBanner">
            <h3>ALERT</h3>
            <p id="alertText"></p>
        </div>
        <div class="email-status">
            Email Alerts: <span class="on">ACTIVE</span> | Sending to: plin068@ucr.edu
        </div>
        <div class="cards">
            <div class="card">
                <div class="label">Temperature</div>
                <div class="value" id="temp">--</div>
                <div class="unit">C</div>
            </div>
            <div class="card">
                <div class="label">Light Level</div>
                <div class="value" id="light">--</div>
                <div class="unit">raw</div>
            </div>
            <div class="card">
                <div class="label">Door Status</div>
                <div class="value" id="door">--</div>
                <div class="unit">&nbsp;</div>
            </div>
            <div class="card">
                <div class="label">Risk Level</div>
                <div class="value" id="risk">--</div>
                <div class="unit">&nbsp;</div>
            </div>
        </div>
        <div class="ai-section">
            <h2>AI Analysis (GPT-4o-mini)</h2>
            <button class="ai-btn" id="aiBtn" onclick="runAI()">Analyze Current Data</button>
            <div class="ai-loading" id="aiLoading">Analyzing data with AI...</div>
            <div class="ai-result" id="aiResult"></div>
        </div>
        <div class="status">
            <h2>Recent Readings</h2>
            <table>
                <thead>
                    <tr><th>Time</th><th>Temp (C)</th><th>Light</th><th>Door</th><th>Risk</th></tr>
                </thead>
                <tbody id="history"></tbody>
            </table>
        </div>
        <div class="timestamp" id="updated">Last updated: --</div>
    </div>
    <script>
        function update() {
            fetch('/api/data')
                .then(r => r.json())
                .then(d => {
                    document.getElementById('temp').textContent = d.temp_filtered;
                    document.getElementById('light').textContent = d.light;
                    let doorEl = document.getElementById('door');
                    doorEl.textContent = d.door ? 'OPEN' : 'CLOSED';
                    doorEl.className = d.door ? 'value door-open' : 'value door-closed';
                    let riskEl = document.getElementById('risk');
                    riskEl.textContent = d.risk;
                    riskEl.className = 'value risk-' + d.risk;
                    document.getElementById('updated').textContent = 'Last updated: ' + d.timestamp;
                    let banner = document.getElementById('alertBanner');
                    let alertText = document.getElementById('alertText');
                    let alerts = [];
                    if (d.temp_filtered > 30) alerts.push('Temperature CRITICAL: ' + d.temp_filtered + 'C');
                    if (d.door) alerts.push('Door is OPEN');
                    if (d.risk !== 'LOW') alerts.push('Risk Level: ' + d.risk);
                    if (alerts.length > 0) {
                        banner.className = 'alert-banner active';
                        alertText.textContent = alerts.join(' | ');
                    } else {
                        banner.className = 'alert-banner';
                    }
                });
            fetch('/api/history')
                .then(r => r.json())
                .then(rows => {
                    let html = '';
                    rows.slice(-10).reverse().forEach(r => {
                        let riskClass = 'risk-' + r.risk;
                        let doorText = r.door ? '<span class="door-open">OPEN</span>' : '<span class="door-closed">CLOSED</span>';
                        html += '<tr><td>' + r.timestamp + '</td><td>' + r.temp_filtered + '</td><td>' + r.light + '</td><td>' + doorText + '</td><td class="' + riskClass + '">' + r.risk + '</td></tr>';
                    });
                    document.getElementById('history').innerHTML = html;
                });
        }

        function runAI() {
            let btn = document.getElementById('aiBtn');
            let loading = document.getElementById('aiLoading');
            let result = document.getElementById('aiResult');
            btn.disabled = true;
            btn.textContent = 'Analyzing...';
            loading.className = 'ai-loading active';
            result.className = 'ai-result';

            fetch('/api/ai_analysis')
                .then(r => r.json())
                .then(d => {
                    result.textContent = d.analysis;
                    result.className = 'ai-result active';
                    loading.className = 'ai-loading';
                    btn.disabled = false;
                    btn.textContent = 'Analyze Current Data';
                })
                .catch(e => {
                    result.textContent = 'Error: ' + e;
                    result.className = 'ai-result active';
                    loading.className = 'ai-loading';
                    btn.disabled = false;
                    btn.textContent = 'Analyze Current Data';
                });
        }

        update();
        setInterval(update, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/data')
def api_data():
    return jsonify(latest_data)

@app.route('/api/history')
def api_history():
    return jsonify(list(history))

@app.route('/api/ai_analysis')
def api_ai_analysis():
    summary, error = generate_ai_summary()
    if error:
        return jsonify({"analysis": error})
    analysis = call_openai(summary)
    print("[AI] Analysis generated")
    return jsonify({"analysis": analysis})

# ===== THINGSPEAK UPLOAD =====
def upload_to_thingspeak(temp, light, risk):
    global last_thingspeak_time
    now = time.time()
    if now - last_thingspeak_time < THINGSPEAK_INTERVAL:
        return
    last_thingspeak_time = now
    risk_num = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(risk, 0)
    params = {
        "api_key": THINGSPEAK_API_KEY,
        "field1": temp,
        "field2": light,
        "field3": risk_num
    }
    try:
        r = requests.get(THINGSPEAK_URL, params=params, timeout=5)
        if r.status_code == 200 and r.text != "0":
            print("[THINGSPEAK] Uploaded: temp={}, light={}, risk={}".format(temp, light, risk))
            while offline_buffer:
                buf = offline_buffer.pop(0)
                time.sleep(15)
                try:
                    requests.get(THINGSPEAK_URL, params=buf, timeout=5)
                    print("[THINGSPEAK] Uploaded buffered data")
                except:
                    offline_buffer.insert(0, buf)
                    break
        else:
            print("[THINGSPEAK] Failed, buffering data")
            offline_buffer.append(params)
    except Exception as e:
        print("[THINGSPEAK] Offline, buffering: {}".format(e))
        offline_buffer.append(params)

# ===== MQTT SUBSCRIBER =====
def mqtt_thread():
    global latest_data
    try:
        import paho.mqtt.client as mqtt
        def on_connect(client, userdata, flags, reason_code, properties=None):
            print("[MQTT] Connected, subscribing to {}".format(MQTT_TOPIC))
            client.subscribe(MQTT_TOPIC)
        def on_message(client, userdata, msg):
            global latest_data
            try:
                data = json.loads(msg.payload.decode())
                latest_data = data
                history.append(data)
                check_alerts(data)
                upload_to_thingspeak(
                    data.get("temp_filtered", 0),
                    data.get("light", 0),
                    data.get("risk", "LOW")
                )
            except Exception as e:
                print("[MQTT] Error processing message: {}".format(e))
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print("[MQTT] Error: {}".format(e))

# ===== MAIN =====
if __name__ == "__main__":
    print("=" * 50)
    print("Cold-Chain Fog Node (Local Manager)")
    print("=" * 50)
    print("Dashboard: http://localhost:5000")
    print("ThingSpeak: https://thingspeak.mathworks.com/channels/3281220")
    print("Email alerts: {} -> {}".format(EMAIL_SENDER, EMAIL_RECEIVER))
    print("AI Analysis: OpenAI GPT-4o-mini enabled")
    print("")
    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
