from __future__ import absolute_import
from celery.utils.log import get_task_logger
from celery import task
from api.models import UserProfile
logger = get_task_logger(__name__)


@task(name="scan_user_content")
def scan_user_content(user_profile):
    if isinstance(user_profile, UserProfile):
        logger.info("Scanning User Contents")
        user_profile.scan_all_content()
