import datetime
from django.contrib.auth.models import User
from oauth2_provider.models import Application, AccessToken
from oauth2_provider.settings import oauth2_settings
from oauthlib.oauth2.rfc6749.tokens import random_token_generator

def generate_access_token(user):

    try:
        app = Application.objects.get(name="breadcrumb")
    except Application.DoesNotExist:
        try:
            root_user = User.objects.get(username='root')
        except User.DoesNotExist:
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