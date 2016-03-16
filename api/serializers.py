import urlparse

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import MultipleObjectsReturned
from oauth2_provider.models import Application, AccessToken
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from api.exceptions import *
from rest_framework.exceptions import *
from api.models import *
from rest_framework.utils import model_meta

from api.utils import generate_access_token
from rest_framework.fields import empty
import time
import requests as r


class TestSerizalizer(serializers.ModelSerializer):
    class Meta:
        model = TestModel
        fields = ('field1', 'field2')


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'password', 'email',
        )
        write_only_fields = ('password')

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        user.set_password(validated_data.pop('password'))
        user.save()
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)

        instance.save()
        return instance


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True, source='user.username')
    email = serializers.CharField(read_only=True, source='user.email')
    first_name = serializers.CharField(read_only=True, source='user.first_name')
    last_name = serializers.CharField(read_only=True, source='user.last_name')

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'first_name', 'last_name', 'aliases')


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, write_only=True)
    email = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    first_name = serializers.CharField(required=False, write_only=True)
    last_name = serializers.CharField(required=False, write_only=True)
    fullname = serializers.CharField(required=False, write_only=True)
    gender = serializers.IntegerField(required=False, write_only=True)
    aliases = serializers.JSONField(required=False)

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'password', 'first_name', 'last_name', 'aliases')

    def create(self, validated_data):

        if 'fullname' in validated_data:
            if validated_data['fullname'].find(' ') != -1:
                first_name, last_name = validated_data['fullname'].split(' ')
                validated_data['first_name'] = first_name
                validated_data['last_name'] = last_name

        user_serializer = UserSerializer(data=validated_data)

        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        user_profile_data = {}
        user_profile_fields = ['gender', 'aliases']
        for field in user_profile_fields:
            if field in validated_data:
                user_profile_data[field] = validated_data[field]

        user_profile_data['user'] = user

        user_profile = UserProfile.objects.create(**user_profile_data)
        user_profile.save()
        return user_profile


class FacebookLoginSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)

    class Meta:
        fields = ('code')

    def create(self, validated_data):
        access_token = validated_data.get('access_token', None)

        user_info_url = "https://graph.facebook.com/v2.5/me?access_token={}&fields=id,name,email,gender".format(
            access_token)

        user_info_response = r.get(user_info_url).json()
        fb_id = user_info_response.get('id')
        fullname = user_info_response.get('name')
        email = user_info_response.get('email')
        gender = user_info_response.get('gender')

        gender_id = 0
        if gender == 'male':
            gender_id = 1
        elif gender == 'female':
            gender_id = 2

        social_account = None
        try:
            social_account = SocialAccount.objects.get(provider='facebook', social_id=fb_id)
        except SocialAccount.DoesNotExist:
            user_profile_data = {
                'username': email,
                'email': email,
                'password': uuid.uuid4(),
                'fullname': fullname,
                'gender': gender_id
            }
            user_profile_serializer = SignupSerializer(data=user_profile_data)
            user_profile_serializer.is_valid(raise_exception=True)
            user_profile = user_profile_serializer.save()
            social_account = SocialAccount.objects.create(user_profile=user_profile, social_id=fb_id,
                                                          social_token=access_token,
                                                          provider='facebook')

        user_profile = social_account.user_profile
        access_token = generate_access_token(user_profile.user)

        access_token_data = AccessTokenSerializer(access_token).data
        self._data = access_token_data
        return user_profile

    def validate(self, data):
        code = data.get('code', None)
        client_id = getattr(settings, "FACEBOOK_CLIENT_ID", None)
        client_secret = getattr(settings, "FACEBOOK_CLIENT_SECRET", None)
        callback_url = getattr(settings, "FACEBOOK_CALLBACK_URL", None)

        if not client_id:
            raise ValidationError(detail={'client_id': 'Cannot find FACEBOOK_CLIENT_ID in django settings'})

        if not client_secret:
            raise ValidationError(detail={'client_secret': 'Cannot find FACEBOOK_CLIENT_SECRET in django settings'})

        if not callback_url:
            raise ValidationError(detail={'callback_url': 'Cannot find FACEBOOK_CALLBACK_URL in django settings'})

        if not code:
            raise ValidationError(detail={'code': 'This field is required.'})

        fb_token_url = "https://graph.facebook.com/oauth/access_token?code={}&client_id={}&client_secret={}&redirect_uri={}".format(
            code, client_id, client_secret, callback_url)

        fb_access_token_response = r.get(fb_token_url)

        fb_access_token_response_parts = urlparse.parse_qsl(fb_access_token_response.content)

        fb_access_token = None

        for part in fb_access_token_response_parts:
            if part[0] == 'access_token':
                fb_access_token = part[1]

        if not fb_access_token:
            raise ValidationError(detail={'access_token': 'Could not retrieve Facebook access token'})

        return {'access_token': fb_access_token}


class AccessTokenSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    expires = serializers.SerializerMethodField('_get_expires_timestamp')

    class Meta:
        model = AccessToken
        fields = ('user', 'token', 'expires', 'scope')

    def _get_expires_timestamp(self, obj):
        return int(time.mktime(obj.expires.timetuple()))


class LoginSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=True)
    email = serializers.CharField(required=False)

    def create(self, validated_data):
        user = validated_data.get('user')
        access_token = generate_access_token(user)

        user_data = UserSerializer(user).data
        access_token_data = AccessTokenSerializer(access_token).data
        self._data = {
            "access_token": access_token_data,
            'user': user_data,
        }

        return access_token

    def validate(self, data):

        username = data.get('username', None)
        email = data.get('email', None)
        password = data.get('password', None)

        if not password:
            raise NotAuthenticated()
        if username:
            user = authenticate(username=username, password=password)
        elif email:
            user = authenticate(username=email, password=password)
        else:
            raise NotAuthenticated()
        if not user:
            raise AuthenticationFailed()

        return {'user': user}

    class Meta:
        model = AccessToken
        fields = ('username', 'email', 'password')
