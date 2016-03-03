from rest_framework import status
from rest_framework.exceptions import APIException
from django.utils.translation import ugettext_lazy as _




ERROR_1000_MISSING_INPUT = {
    'error_code': 1000,
    'status_code': status.HTTP_400_BAD_REQUEST,
    'error_message': 'Missing input data'
}
ERROR_1001_INVALID_USER_CREDENTIALS = {
    'error_code': 1001,
    'status_code': status.HTTP_401_UNAUTHORIZED,
    'error_message': 'Invalid Credentials'
}
ERROR_1002_MISSING_PASSWORD = {
    'error_code': 1002,
    'status_code': status.HTTP_404_NOT_FOUND,
    'error_message': 'Missing input value password'
}
ERROR_1003_MISSING_LOGIN = {
    'error_code': 1003,
    'status_code': status.HTTP_400_BAD_REQUEST,
    'error_message': 'Missing Login (username/email)'
}

class CustomExceptipon(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Not found.')
