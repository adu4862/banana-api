import requests
import sys
import socket

print(f"Python executable: {sys.executable}")

try:
    import socks
    print(f"Socks module found: {socks.__file__}")
except ImportError:
    print("Socks module NOT found")

proxies = {
    'http': 'socks5://192.168.1.13:10808',
    'https': 'socks5://192.168.1.13:10808'
}

try:
    print("Attempting request with SOCKS proxy...")
    # Use a site that is likely accessible or will fail with connection error, not dependency error
    resp = requests.get('http://www.google.com', proxies=proxies, timeout=5)
    print(f"Success: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
