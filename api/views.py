import pickle
from importlib import import_module

import sys
import tweepy
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponseRedirect, JsonResponse
from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from django.contrib.sessions.models import Session
from rest_framework import generics
from rest_framework.decorators import permission_classes, authentication_classes, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from breadcrumbcore.ai.sentimentanalyser import analyse_text as sa
from api.serializers import *
from breadcrumbcore.searchengines.googlesearch import GoogleWebSearch

# Create your views here.
from api.utils import get_user_profile_from_token
from api.tasks import scan_user_content


class UserProfileDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class AccountList(generics.RetrieveUpdateDestroyAPIView):
    queryset = SocialAccount.objects.all()
    serializer_class = SocialAccountSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        data = {"access_token": token}
        serializer = SocialAccountSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class UserProfileList(generics.ListAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class Scan(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)
        scan_user_content.delay(str(user_profile.pk))
        return Response(status=status.HTTP_200_OK)


class Signup(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


class Login(APIView):
    queryset = AccessToken.objects.all()

    def post(self, request, *args, **kwargs):
        login_serializer = LoginSerializer(data=request.data)
        login_serializer.is_valid(raise_exception=True)
        login_serializer.save()
        return Response(data=login_serializer.data)


class UploadImage(APIView):
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        data = request.data
        data["access_token"] = request.META.get('HTTP_AUTHORIZATION', None)
        serializer = UploadImageSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)


class FacebookLogin(APIView):
    def get(self, request, *args, **kwargs):
        base_url = "https://www.facebook.com/dialog/oauth?scope=email,public_profile,user_friends,user_likes,user_photos,user_posts&client_id={client_id}&redirect_uri={callback_url}"
        redirect_url = base_url.format(client_id=settings.FACEBOOK_CLIENT_ID,
                                       callback_url=settings.FACEBOOK_CALLBACK_URL)
        s = SessionStore()
        s['is_login'] = True
        s.save(must_create=True)
        try:
            return HttpResponseRedirect(redirect_url)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LinkFacebookAccount(APIView):
    authentication_classes = (OAuth2Authentication,)

    # permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        base_url = "https://www.facebook.com/dialog/oauth?scope=email,public_profile,user_friends,user_likes,user_photos,user_posts&client_id={client_id}&redirect_uri={callback_url}"
        redirect_url = base_url.format(client_id=settings.FACEBOOK_CLIENT_ID,
                                       callback_url=settings.FACEBOOK_CALLBACK_URL)
        s = SessionStore()
        s['is_login'] = False
        s['access_token'] = kwargs.get("access_token")
        s.save(must_create=True)
        try:
            return HttpResponseRedirect(redirect_url)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FacebookCallback(APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', None)
        data = {'code': code}
        session_key = Session.objects.latest('expire_date').session_key
        s = SessionStore(session_key=session_key)
        is_login = s.get('is_login')
        access_token = s.get('access_token')
        s.delete('is_login')
        s.delete('access_token')
        s.delete()
        if is_login:
            serializer = FacebookLoginSerializer(data=data)
        else:
            data["access_token"] = access_token
            serializer = LinkFacebookAccountSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)


class LinkTwitterAccount(APIView):
    authentication_classes = (OAuth2Authentication,)

    # permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET,
            settings.TWITTER_CALLBACK_URL
        )
        try:
            redirect_url = auth.get_authorization_url()
            s = SessionStore()
            s['request_token'] = auth.request_token
            s['is_login'] = False
            s['access_token'] = request.META.get('HTTP_AUTHORIZATION', None)
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, *args, **kwargs):
        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET,
            settings.TWITTER_CALLBACK_URL
        )
        try:
            redirect_url = auth.get_authorization_url()
            s = SessionStore()
            s['request_token'] = auth.request_token
            s['is_login'] = False
            s['access_token'] = kwargs.get("access_token")
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwitterLogin(APIView):
    def get(self, request, *args, **kwargs):
        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET,
            settings.TWITTER_CALLBACK_URL
        )
        try:
            redirect_url = auth.get_authorization_url()
            s = SessionStore()
            s['request_token'] = auth.request_token
            s['is_login'] = True
            s['access_token'] = None
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwitterCallback(APIView):
    def get(self, request, *args, **kwargs):
        if 'denied' in request.GET:
            return Response()
        session_key = Session.objects.latest('expire_date').session_key
        s = SessionStore(session_key=session_key)
        is_login = s.get('is_login')
        access_token = s.get('access_token')

        data = {
            'oauth_verifier': request.GET['oauth_verifier'],
            'request_token': s.get("request_token"),
        }
        s.delete('request_token')
        s.delete('is_login')
        s.delete('access_token')
        s.save()
        if is_login:
            serializer = TwitterLoginSerializer(data=data)
        else:
            data["access_token"] = access_token
            serializer = LinkTwitterAccountSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_data = serializer.data
        return Response(data=response_data)
