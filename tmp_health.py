import json
import urllib.request

resp = urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)
data = json.load(resp)
print('health:', data)
