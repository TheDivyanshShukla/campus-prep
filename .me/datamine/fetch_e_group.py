import requests

url = "https://www.rgpvonline.com/btech-e-all-question-papers.html"
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-ua": "\"Opera GX\";v=\"127\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "upgrade-insecure-requests": "1",
    "Referer": "https://www.rgpvonline.com/"
}

response = requests.get(url, headers=headers)
with open("e_group_sample.html", "w", encoding="utf-8") as f:
    f.write(response.text)
