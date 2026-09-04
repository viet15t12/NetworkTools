import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = "192.168.121.17"
PORT = 443
USER = "admin"
PASS = "admin"
POOL_NAME = "TEST_LEASE" # Nhắm thẳng vào cái pool vừa tạo

url = f"https://{HOST}:{PORT}/restconf/data/Cisco-IOS-XE-native:native/ip/dhcp/pool={POOL_NAME}"
headers = {"Accept": "application/yang-data+json"}

res = requests.get(url, auth=(USER, PASS), headers=headers, verify=False)

if res.status_code == 200:
    print("\n[+] ĐÃ BẮT ĐƯỢC CẤU TRÚC JSON LEASE:")
    print(json.dumps(res.json(), indent=4))
else:
    print(f"[-] Lỗi: HTTP {res.status_code} - {res.text}")