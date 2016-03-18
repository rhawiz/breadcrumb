import datetime
from django.contrib.auth.models import User
from oauth2_provider.models import Application, AccessToken
from oauth2_provider.settings import oauth2_settings
from oauthlib.oauth2.rfc6749.tokens import random_token_generator


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


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
