#!/usr/bin/env python3
"""
Silver Proxy - Self-hosted, self-backend proxy with built-in web interface
No installation required - just run it!
"""

import socket
import threading
import select
import sys
import time
from datetime import datetime
from html import escape

class SilverProxy:
    def __init__(self, proxy_port=8888, web_port=8080):
        self.proxy_port = proxy_port
        self.web_port = web_port
        self.host = '0.0.0.0'
        self.proxy_socket = None
        self.web_socket = None
        self.running = False
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'http_requests': 0,
            'https_requests': 0,
            'bytes_transferred': 0,
            'start_time': None,
            'recent_requests': []
        }
        self.stats_lock = threading.Lock()
        
    def start(self):
        """Start both proxy and web interface"""
        self.stats['start_time'] = datetime.now()
        
        # Start proxy server
        proxy_thread = threading.Thread(target=self.start_proxy)
        proxy_thread.daemon = True
        proxy_thread.start()
        
        # Start web interface
        web_thread = threading.Thread(target=self.start_web_interface)
        web_thread.daemon = True
        web_thread.start()
        
        print("=" * 60)
        print("  ╔═══════════════════════════════════════════════════════╗")
        print("  ║           SILVER PROXY - Self-Hosted Edition          ║")
        print("  ╚═══════════════════════════════════════════════════════╝")
        print("=" * 60)
        print(f"\n  🔵 Proxy Server:    http://localhost:{self.proxy_port}")
        print(f"  🌐 Web Interface:   http://localhost:{self.web_port}")
        print(f"\n  📊 Dashboard:       http://localhost:{self.web_port}/")
        print(f"  ⚙️  Configuration:   http://localhost:{self.web_port}/config")
        print(f"  📈 Statistics:      http://localhost:{self.web_port}/stats")
        print("\n" + "=" * 60)
        print("  Press Ctrl+C to stop the server")
        print("=" * 60 + "\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Stopping Silver Proxy...")
            self.running = False
            
    def start_proxy(self):
        """Start the proxy server"""
        try:
            self.proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.proxy_socket.bind((self.host, self.proxy_port))
            self.proxy_socket.listen(100)
            self.running = True
            
            print(f"[✓] Proxy server listening on port {self.proxy_port}")
            
            while self.running:
                try:
                    client_socket, client_address = self.proxy_socket.accept()
                    
                    with self.stats_lock:
                        self.stats['total_connections'] += 1
                        self.stats['active_connections'] += 1
                    
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except Exception as e:
                    if self.running:
                        print(f"[!] Proxy error: {e}")
                        
        except Exception as e:
            print(f"[!] Failed to start proxy: {e}")
        finally:
            if self.proxy_socket:
                self.proxy_socket.close()
                
    def start_web_interface(self):
        """Start the web interface server"""
        try:
            self.web_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.web_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.web_socket.bind((self.host, self.web_port))
            self.web_socket.listen(50)
            
            print(f"[✓] Web interface listening on port {self.web_port}")
            
            while self.running:
                try:
                    client_socket, client_address = self.web_socket.accept()
                    web_thread = threading.Thread(
                        target=self.handle_web_request,
                        args=(client_socket,)
                    )
                    web_thread.daemon = True
                    web_thread.start()
                    
                except Exception as e:
                    if self.running:
                        print(f"[!] Web server error: {e}")
                        
        except Exception as e:
            print(f"[!] Failed to start web interface: {e}")
        finally:
            if self.web_socket:
                self.web_socket.close()
                
    def handle_client(self, client_socket, client_address):
        """Handle proxy client connection"""
        try:
            request = client_socket.recv(8192)
            
            if not request:
                client_socket.close()
                with self.stats_lock:
                    self.stats['active_connections'] -= 1
                return
                
            first_line = request.split(b'\n')[0]
            method = first_line.split(b' ')[0]
            
            if method == b'CONNECT':
                self.handle_https(client_socket, request, client_address)
            else:
                self.handle_http(client_socket, request, client_address)
                
        except Exception as e:
            pass
        finally:
            try:
                client_socket.close()
            except:
                pass
            with self.stats_lock:
                self.stats['active_connections'] -= 1
                
    def handle_http(self, client_socket, request, client_address):
        """Handle HTTP requests"""
        try:
            first_line = request.split(b'\n')[0]
            url = first_line.split(b' ')[1]
            
            http_pos = url.find(b'://')
            if http_pos == -1:
                temp = url
            else:
                temp = url[(http_pos + 3):]
                
            port_pos = temp.find(b':')
            webserver_pos = temp.find(b'/')
            
            if webserver_pos == -1:
                webserver_pos = len(temp)
                
            if port_pos == -1 or webserver_pos < port_pos:
                port = 80
                webserver = temp[:webserver_pos]
            else:
                port = int(temp[(port_pos + 1):webserver_pos])
                webserver = temp[:port_pos]
            
            with self.stats_lock:
                self.stats['http_requests'] += 1
                self.log_request('HTTP', webserver.decode(), port, client_address)
            
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(10)
            server_socket.connect((webserver, port))
            server_socket.send(request)
            
            while True:
                ready, _, _ = select.select([client_socket, server_socket], [], [], 5)
                
                if not ready:
                    break
                    
                for sock in ready:
                    data = sock.recv(8192)
                    if not data:
                        server_socket.close()
                        return
                    
                    with self.stats_lock:
                        self.stats['bytes_transferred'] += len(data)
                    
                    if sock is server_socket:
                        client_socket.send(data)
                    else:
                        server_socket.send(data)
                        
            server_socket.close()
            
        except Exception as e:
            pass
            
    def handle_https(self, client_socket, request, client_address):
        """Handle HTTPS CONNECT requests"""
        try:
            first_line = request.split(b'\n')[0]
            url = first_line.split(b' ')[1]
            
            host_port = url.split(b':')
            webserver = host_port[0].decode()
            port = int(host_port[1]) if len(host_port) > 1 else 443
            
            with self.stats_lock:
                self.stats['https_requests'] += 1
                self.log_request('HTTPS', webserver, port, client_address)
            
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(10)
            server_socket.connect((webserver, port))
            
            client_socket.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            
            client_socket.setblocking(0)
            server_socket.setblocking(0)
            
            while True:
                ready, _, _ = select.select([client_socket, server_socket], [], [], 5)
                
                if not ready:
                    break
                    
                for sock in ready:
                    try:
                        data = sock.recv(8192)
                        if not data:
                            server_socket.close()
                            return
                        
                        with self.stats_lock:
                            self.stats['bytes_transferred'] += len(data)
                        
                        if sock is server_socket:
                            client_socket.send(data)
                        else:
                            server_socket.send(data)
                    except:
                        pass
                        
            server_socket.close()
            
        except Exception as e:
            pass
            
    def log_request(self, protocol, host, port, client_address):
        """Log a request"""
        log_entry = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'protocol': protocol,
            'host': host,
            'port': port,
            'client': f"{client_address[0]}:{client_address[1]}"
        }
        self.stats['recent_requests'].insert(0, log_entry)
        self.stats['recent_requests'] = self.stats['recent_requests'][:50]
        
    def handle_web_request(self, client_socket):
        """Handle web interface requests"""
        try:
            request = client_socket.recv(4096).decode('utf-8', errors='ignore')
            
            if not request:
                client_socket.close()
                return
                
            lines = request.split('\n')
            if not lines:
                client_socket.close()
                return
                
            first_line = lines[0].split()
            if len(first_line) < 2:
                client_socket.close()
                return
                
            method = first_line[0]
            path = first_line[1]
            
            if path == '/' or path == '/index.html':
                response = self.get_dashboard_page()
            elif path == '/stats':
                response = self.get_stats_page()
            elif path == '/config':
                response = self.get_config_page()
            elif path == '/api/stats':
                response = self.get_stats_json()
            else:
                response = self.get_404_page()
                
            client_socket.send(response.encode('utf-8'))
            
        except Exception as e:
            pass
        finally:
            try:
                client_socket.close()
            except:
                pass
                
    def get_dashboard_page(self):
        """Get dashboard HTML"""
        uptime = datetime.now() - self.stats['start_time']
        uptime_str = str(uptime).split('.')[0]
        
        recent_logs = ""
        for log in self.stats['recent_requests'][:10]:
            recent_logs += f"""
            <tr>
                <td>{escape(log['time'])}</td>
                <td><span class="badge badge-{log['protocol'].lower()}">{escape(log['protocol'])}</span></td>
                <td>{escape(log['host'])}:{log['port']}</td>
                <td>{escape(log['client'])}</td>
            </tr>
            """
        
        html = f"""HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<head>
    <title>Silver Proxy Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #666;
            font-size: 1.1em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: transform 0.3s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        .stat-label {{
            color: #888;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        .stat-value {{
            color: #333;
            font-size: 2em;
            font-weight: bold;
        }}
        .stat-icon {{
            font-size: 2em;
            margin-bottom: 10px;
        }}
        .logs-section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .logs-section h2 {{
            color: #667eea;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .badge {{
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .badge-http {{
            background: #4CAF50;
            color: white;
        }}
        .badge-https {{
            background: #2196F3;
            color: white;
        }}
        .nav {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
        }}
        .nav a {{
            background: white;
            color: #667eea;
            padding: 12px 25px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.3s;
        }}
        .nav a:hover {{
            transform: translateY(-2px);
            box-shadow: 0 7px 20px rgba(0,0,0,0.3);
        }}
        .nav a.active {{
            background: #667eea;
            color: white;
        }}
        .refresh-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 1em;
            margin-bottom: 20px;
        }}
        .refresh-btn:hover {{
            background: #5568d3;
        }}
    </style>
    <script>
        function autoRefresh() {{
            setTimeout(function() {{
                location.reload();
            }}, 5000);
        }}
    </script>
</head>
<body onload="autoRefresh()">
    <div class="container">
        <div class="header">
            <h1>⚡ Silver Proxy</h1>
            <p>Self-Hosted Proxy Server Dashboard</p>
        </div>
        
        <div class="nav">
            <a href="/" class="active">Dashboard</a>
            <a href="/stats">Statistics</a>
            <a href="/config">Configuration</a>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">🔌</div>
                <div class="stat-label">Total Connections</div>
                <div class="stat-value">{self.stats['total_connections']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-label">Active Connections</div>
                <div class="stat-value">{self.stats['active_connections']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📄</div>
                <div class="stat-label">HTTP Requests</div>
                <div class="stat-value">{self.stats['http_requests']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔒</div>
                <div class="stat-label">HTTPS Requests</div>
                <div class="stat-value">{self.stats['https_requests']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-label">Data Transferred</div>
                <div class="stat-value">{self.format_bytes(self.stats['bytes_transferred'])}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⏱️</div>
                <div class="stat-label">Uptime</div>
                <div class="stat-value" style="font-size: 1.3em;">{uptime_str}</div>
            </div>
        </div>
        
        <div class="logs-section">
            <h2>📝 Recent Activity</h2>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Protocol</th>
                        <th>Destination</th>
                        <th>Client</th>
                    </tr>
                </thead>
                <tbody>
                    {recent_logs if recent_logs else '<tr><td colspan="4" style="text-align:center;">No requests yet</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""
        return html
        
    def get_stats_page(self):
        """Get statistics page"""
        uptime = datetime.now() - self.stats['start_time']
        
        html = f"""HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<head>
    <title>Silver Proxy - Statistics</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            color: #667eea;
            font-size: 2.5em;
        }}
        .nav {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
        }}
        .nav a {{
            background: white;
            color: #667eea;
            padding: 12px 25px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.3s;
        }}
        .nav a:hover {{
            transform: translateY(-2px);
        }}
        .nav a.active {{
            background: #667eea;
            color: white;
        }}
        .stats-container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .stat-row {{
            padding: 15px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
        }}
        .stat-row:last-child {{
            border-bottom: none;
        }}
        .stat-label {{
            color: #666;
            font-weight: 600;
        }}
        .stat-value {{
            color: #333;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Statistics</h1>
        </div>
        
        <div class="nav">
            <a href="/">Dashboard</a>
            <a href="/stats" class="active">Statistics</a>
            <a href="/config">Configuration</a>
        </div>
        
        <div class="stats-container">
            <h2 style="margin-bottom: 20px; color: #667eea;">Detailed Statistics</h2>
            <div class="stat-row">
                <span class="stat-label">Server Start Time</span>
                <span class="stat-value">{self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Server Uptime</span>
                <span class="stat-value">{str(uptime).split('.')[0]}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Total Connections</span>
                <span class="stat-value">{self.stats['total_connections']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Active Connections</span>
                <span class="stat-value">{self.stats['active_connections']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">HTTP Requests</span>
                <span class="stat-value">{self.stats['http_requests']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">HTTPS Requests</span>
                <span class="stat-value">{self.stats['https_requests']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Total Requests</span>
                <span class="stat-value">{self.stats['http_requests'] + self.stats['https_requests']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Total Data Transferred</span>
                <span class="stat-value">{self.format_bytes(self.stats['bytes_transferred'])}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Proxy Port</span>
                <span class="stat-value">{self.proxy_port}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Web Interface Port</span>
                <span class="stat-value">{self.web_port}</span>
            </div>
        </div>
    </div>
</body>
</html>"""
        return html
        
    def get_config_page(self):
        """Get configuration page"""
        html = f"""HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<head>
    <title>Silver Proxy - Configuration</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            color: #667eea;
            font-size: 2.5em;
        }}
        .nav {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
        }}
        .nav a {{
            background: white;
            color: #667eea;
            padding: 12px 25px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.3s;
        }}
        .nav a:hover {{
            transform: translateY(-2px);
        }}
        .nav a.active {{
            background: #667eea;
            color: white;
        }}
        .config-container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .config-section {{
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }}
        .config-section h3 {{
            color: #667eea;
            margin-bottom: 15px;
        }}
        .config-item {{
            margin-bottom: 15px;
        }}
        .config-label {{
            font-weight: 600;
            color: #333;
            display: block;
            margin-bottom: 5px;
        }}
        .config-value {{
            color: #666;
            font-family: 'Courier New', monospace;
            background: white;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚙️ Configuration</h1>
        </div>
        
        <div class="nav">
            <a href="/">Dashboard</a>
            
