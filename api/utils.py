import base64
import datetime
import requests

import binascii
import os

from django.contrib.auth.models import User
from oauth2_provider.models import Application, AccessToken
from oauth2_provider.settings import oauth2_settings
from oauthlib.oauth2.rfc6749.tokens import random_token_generator


def is_ascii(s):
    return all(ord(c) < 128 for c in s)



url = 'http://text-processing.com/api/sentiment/'


def analyse_text(text_list):
    if not isinstance(text_list, list):
        text_list = [text_list]

    neg = 0.0
    neutral = 0.0
    pos = 0.0
    label = None

    counter = 0

    print text_list
    for text in text_list:
        print text_list
        text = text.strip()
        data = 'text={}'.format(text)
        response = requests.post(url=url, data=data)
        if response:
            try:
                out = response.json()
                out_neg = float(out["probability"]["neg"])
                out_neutral = float(out["probability"]["neutral"])
                out_pos = float(out["probability"]["pos"])

                neg += out_neg
                neutral += out_neutral
                pos += out_pos
                counter += 1
            except Exception as e:
                print e
                pass

    if counter > 0:
        neg /= counter
        neutral /= counter
        pos /= counter

    print neg, neutral, pos

    if neg >= neutral and neg >= pos:
        label = "neg"
    elif neutral >= neg and neutral >= pos:
        label = "neutral"
    elif pos >= neg and pos >= neutral:
        label = "pos"

    return {
        "probability": {
            "neg": neg,
            "neutral": neutral,
            "pos": pos
        },
        "label": label
    }

def generate_access_token(user):
    try:
        app = Application.objects.get(name="breadcrumb")
    except Application.DoesNotExist:
        try:
            root_user = User.objects.get(username='root')
        except User.DoesNotExist:
            # todo: this is for testing purposes only, remove this when going live
            root_user = User.objects.create(username='root', email='admin@admin.com', password='password')
        app = Application.objects.create(client_id='breadcrumb', client_secret='secret', name='breadcrumb',
                                         user=root_user, authorization_grant_type='password')

    expires = datetime.datetime.now() + datetime.timedelta(seconds=31536000)
    access_token = AccessToken.objects.create(
        user=user,
        application=app,
        token=random_token_generator(None),
        expires=expires,
        scope=oauth2_settings.user_settings['SCOPES']
    )

    return access_token


def get_user_profile_from_token(token):
    if token is None or 'Bearer' not in token:
        return None

    try:
        token = token.split(' ')[1]
        user = AccessToken.objects.get(token=token).user
    except:
        return None
    from api.models import UserProfile
    user_profile = UserProfile.objects.get(user=user)
    return user_profile

def is_valid_base64(base_64):
    try:
        base64.decodestring(base_64)
        return True
    except binascii.Error:
        return False

def supermakedirs(path, mode):
    if not path or os.path.exists(path):
        return []
    (head, tail) = os.path.split(path)
    res = supermakedirs(head, mode)
    os.mkdir(path)
    os.chmod(path, mode)
    res += [path]
    return res
