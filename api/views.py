from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework.views import APIView
from oauth2_provider.models import AccessToken, Application
from api.serializers import *
import breadcrumb_intellegence.sent_analyser as sa
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

    """
    Create a model instance.
    """

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
        url = "https://www.facebook.com/dialog/oauth?client_id=1696090350621812&response_type=code&scope=public_profile,user_friends&redirect_uri=https://www.google.com"
        response = r.get(url)
        print response.content
        return Response(data={})

