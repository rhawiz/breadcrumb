from rest_framework import serializers
from api.models import *
from rest_framework.utils import model_meta


class TestSerizalizer(serializers.ModelSerializer):
    class Meta:
        model = TestModel
        fields = ('field1', 'field2')


class UserSerializer(serializers.ModelSerializer):
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


class CreateUserProfileSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    aliases = serializers.JSONField(required=False)

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'password', 'first_name', 'last_name', 'aliases')

    def create(self, validated_data):
        # TODO: Fix AttributeError
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
