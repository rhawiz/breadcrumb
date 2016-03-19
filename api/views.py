from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from breadcrumbcore.ai.sentimentanalyser import analyse_text as sa
from api.serializers import *
from breadcrumbcore.searchengines.googlesearch import GoogleWebSearch

# Create your views here.
from api.utils import get_user_profile_from_token
from api.tasks import scan_user_content


class run_deploy(APIView):
    def get(self, request, *args, **kwargs):
        import subprocess
        import os
        deploy_path = os.path.abspath('/opt/bitnami/apps/django/django_projects/breadcrumb/deploy.sh')
        subprocess.call(["/usr/bin/sudo", "chmod 755 {}".format(deploy_path)])
        try:
            subprocess.call(["/usr/bin/sudo", "cd /opt/bitnami/apps/django/django_projects/breadcrumb/", "git pull"])
            subprocess.call(["/usr/bin/sudo", "cd /opt/bitnami/apps/django/django_projects/breadcrumb/",
                             "pip install -r requirements.txt"])
            subprocess.call(["/usr/bin/sudo", "cd /opt/bitnami/apps/django/django_projects/breadcrumb/",
                             "python manage.py makemigrations"])
            subprocess.call(["/usr/bin/sudo", "cd /opt/bitnami/apps/django/django_projects/breadcrumb/",
                             "python manage.py migrate"])
            subprocess.call(["/usr/bin/sudo", "/opt/bitnami/ctlscript.sh restart apache"])
            # subprocess.call(["/usr/bin/sudo", deploy_path])

            return Response(data="Successfully redeployed application")
        except Exception, e:
            return Response(data="Failed to redeploy at {}: {}".format(deploy_path, e))


class Search(APIView):
    def get(self, request, *args, **kwargs):

        search_text = kwargs.get('search_text', None)
        num = 50
        pages = 1

        google_search = GoogleWebSearch(query=search_text, num=num, sentiment_analyser=sa)
        results = google_search.search(pages=pages)

        results = sorted(results, key=lambda k: k['analysis']['probability']['neg'], reverse=True)

        return Response(data=results)

    def post(self, request, *args, **kwargs):

        search_text = kwargs.get('search_text', None)

        if not search_text:
            return Response(data=['Provide search text'])

        num = request.data.get('num', None)
        pages = request.data.get('pages', None)

        if not num:
            num = 50
        if not pages:
            pages = 1

        google_search = GoogleWebSearch(query=search_text, num=num, sentiment_analyser=sa)
        results = google_search.search(pages=pages)

        results = sorted(results, key=lambda k: k['analysis']['probability']['neg'], reverse=True)

        return Response(data=results)


class TestView(APIView):
    def get(self, request, *args, **kwargs):
        test_data = [
            {
                'field1': 'obj1',
                'dict': {
                    'dict_field1': 2,
                }
            },
            {
                'field1': 'obj2',
                'dict': {
                    'dict_field1': 1,
                }
            },
            {
                'field1': 'obj3',
                'dict': {
                    'dict_field1': 3,
                }
            },
        ]

        return Response(data=sorted(test_data, key=lambda k: k['dict']['dict_field1']))


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


class Scan(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)
        scan_user_content(user_profile)
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

        data = sa(text)
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
            return Response(
                data={"provider": ["Not a valid provider, choices are:{}".format(acceptable_providers)]})

        url = "https://graph.facebook.com/me?access_token={}"
        response = r.get(url)
        print response.content
        return Response(data={})


class SocialSignup(APIView):
    def post(self, request, *args, **kwargs):
        serializer = FacebookLoginSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        return Response(data=serializer.data)


class ExtractSocial(APIView):
    def post(self, request, *args, **kwargs):
        grant_type = 'fb_exchange_token'
        client_id = '195217574177770'
        client_secret = 'd7c48a5db8ca2a126b71d487fd456817'
        fb_exchange_token = 'EAACxjKIpqZBoBABd2ETtO8qTMvy4W6ygVa9ZCH3e6HW5UXeLAZA8XJSLt1ZBXlFEouPXdQngtpxnkCTMyGTeSbRQd3t3aV6b24VVYX3MbsVz4oD4zTPojTQTc8ZCs7CY4xR9BiWmYbQ8FqMkR7msZAmidO3ke66onkYAjezaK0dQZDZD'

        fb_access_token_url = "https://graph.facebook.com/oauth/access_token?grant_type={}&client_id={}&client_secret={}&fb_exchange_token={}".format(
            grant_type, client_id, client_secret, fb_exchange_token)

        fb_access_token_response = r.get(fb_access_token_url).content
        # access_token = fb_access_token_response.split('&')[0].split('=')[1]

        if 'access_token' in request.data:
            access_token = request.data.get('access_token')
        else:
            access_token = 'EAACxjKIpqZBoBAIrwnP4rWovBr6dZBy9BZAiyTDVgQRZAZCYKI2cXZBUilh0VgRICRvWxeken2NJfYdBuulqyKFVPUkx6KTS4mlOltsuPDYNYNALw58gPvk7gPwZCS3WZA3mZAH8ALyLGuSX6pWmzYcU4pceTa0fgHkOErQjwZCs9w0wZDZD'
        # expires = fb_access_token_response.split('&')[1].split('=')[1]

        ts_now = time.time()
        # ts_expires = ts_now + float(expires)



        user_feed_url = "https://graph.facebook.com/me?access_token={}&fields=feed.include_hidden(true)".format(
            access_token)

        user_feed_paginated = r.get(user_feed_url).json().get('feed')

        if not user_feed_paginated:
            return Response(data={'Error': 'Invalid Access Token: {}'.format(access_token),
                                  'facebook_response': r.get(user_feed_url).json()})
        all_user_feed = user_feed_paginated.get('data')

        while user_feed_paginated:
            if 'paging' in user_feed_paginated:
                user_feed_url = user_feed_paginated.get('paging').get('next', None)
                user_feed_paginated = r.get(user_feed_url).json()
                all_user_feed += user_feed_paginated.get('data')
            else:
                user_feed_paginated = None
        user_feed = []

        for content in all_user_feed:
            if 'message' in content:
                user_feed.append(content)

        for content in user_feed:
            sent_dict = sa(content.get('message'))
            content['sentiment_analysis'] = sent_dict
        user_feed = sorted(user_feed, key=lambda k: k['sentiment_analysis']['probability']['neg'], reverse=True)
        data = user_feed
        return Response(data=data)


class FacebookCallback(APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', None)
        data = {'code': code}
        serializer = FacebookLoginSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        print serializer.save()
        return Response(data=serializer.data)
