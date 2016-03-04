import datetime
from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework.views import APIView
from oauth2_provider.models import AccessToken, Application
from api.serializers import *
import breadcrumb_intellegence.sentiment_analyser as sa
import requests as r


# Create your views here.

class run_deploy(APIView):
    def get(self, request, *args, **kwargs):
        import subprocess
        import os
        deploy_path = os.path.abspath('/opt/bitnami/apps/django/django_projects/breadcrumb/deploy.sh')
        try:
            subprocess.call([deploy_path])
            return Response(data="Successfully redeployed application")
        except Exception, e:
            return Response(data="Failed to redeploy at {}: {}".format(deploy_path, e))


class TestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TestModel.objects.all()
    serializer_class = TestSerizalizer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class TestListView(generics.ListCreateAPIView):
    queryset = TestModel.objects.all()
    serializer_class = TestSerizalizer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class UserProfileDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class UserProfileList(generics.ListAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class Signup(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = CreateUserProfileSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        headers = self.get_success_headers(serializer.data)
        response = UserProfileSerializer(instance).data
        return Response(response, status=status.HTTP_201_CREATED, headers=headers)


class Login(APIView):
    queryset = AccessToken.objects.all()

    def post(self, request, *args, **kwargs):
        login_serializer = LoginSerializer(data=request.data)
        login_serializer.is_valid(raise_exception=True)
        login_serializer.save()
        return Response(data=login_serializer.data)


class SentAnalyser(APIView):
    def post(self, request, *args, **kwargs):
        text = request.data.get('text', None)

        if not text:
            return Response(data={"text": ["This field is required."]})

        data = sa.analyse_text(text)
        print data

        return Response(data=data)


class SocialLogin(APIView):
    def post(self, request, *args, **kwargs):
        # todo: Put these all into serializers
        acceptable_providers = ['facebook', 'twitter']
        access_token = request.data.get('access_token', None)
        provider = request.data.get('access_token', None)
        if not access_token:
            return Response(data={"access_token": ["This field is required."]})

        if not provider:
            return Response(data={"provider": ["This field is required."]})

        if provider not in acceptable_providers:
            return Response(data={"provider": ["Not a valid provider, choices are:{}".format(acceptable_providers)]})

        url = "https://graph.facebook.com/me?access_token={}"
        response = r.get(url)
        print response.content
        return Response(data={})


class ExtractSocial(APIView):
    def post(self, request, *args, **kwargs):
        grant_type = 'fb_exchange_token'
        client_id = '195217574177770'
        client_secret = 'd7c48a5db8ca2a126b71d487fd456817'
        fb_exchange_token = 'EAACxjKIpqZBoBABd2ETtO8qTMvy4W6ygVa9ZCH3e6HW5UXeLAZA8XJSLt1ZBXlFEouPXdQngtpxnkCTMyGTeSbRQd3t3aV6b24VVYX3MbsVz4oD4zTPojTQTc8ZCs7CY4xR9BiWmYbQ8FqMkR7msZAmidO3ke66onkYAjezaK0dQZDZD'

        fb_access_token_url = "https://graph.facebook.com/oauth/access_token?grant_type={}&client_id={}&client_secret={}&fb_exchange_token={}".format(
            grant_type, client_id, client_secret, fb_exchange_token)

        fb_access_token_response =  r.get(fb_access_token_url).content

        access_token = fb_access_token_response.split('&')[0].split('=')[1]
        expires = fb_access_token_response.split('&')[1].split('=')[1]

        ts_now = time.time()
        ts_expires = ts_now + float(expires)

        print datetime.datetime.fromtimestamp(ts_expires).strftime('%Y-%m-%d %H:%M:%S')

        user_feed_url = "https://graph.facebook.com/me?access_token={}&fields=feed.include_hidden(true)".format(access_token)
        user_feed_paginated = r.get(user_feed_url).json().get('feed')
        user_feed= []

        while 'paging' in user_feed_paginated:
            print 1
            user_feed.append(user_feed_paginated.get('data'))
            user_feed_url = user_feed_paginated.get('paging').get('next')
            user_feed_paginated = r.get(user_feed_url).json().get('feed')


        print user_feed

        data = user_feed
        return Response(data=data)
