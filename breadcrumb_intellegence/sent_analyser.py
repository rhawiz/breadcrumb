import requests
url = 'http://text-processing.com/api/sentiment/'

def analyse_text(text):
    data = 'text={}'.format(text)
    response = requests.post(url=url, data=data)
    if response:
        return response.json()

    return ''

