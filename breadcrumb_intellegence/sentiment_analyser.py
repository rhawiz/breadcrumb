import requests

from api.utils import is_ascii

url = 'http://text-processing.com/api/sentiment/'


def analyse_text(text):
    if is_ascii(text):
        text=text.strip()
        data = 'text={}'.format(text)
        response = requests.post(url=url, data=data)
        if response:
            return response.json()

    return {
        "probability": {
            "neg": 0.0,
            "neutral": 0.0,
            "pos": 0.0
        },
        "label": "None"
    }
