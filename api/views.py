from django.shortcuts import render
from rest_framework import generics
from api.models import *
from api.serializers import *
# Create your views here.

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

class UserProfileList(generics.ListCreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = CreateUserProfileSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class Signup(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = CreateUserProfileSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

