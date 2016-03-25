#!/usr/bin/sh

sudo git pull
sudo pip uninstall breadcrumbcore
sudo pip install -r requirements.txt
sudo python manage.py makemigrations api
sudo python manage.py migrate
sudo /opt/bitnami/ctlscript.sh restart apache
sudo redis-server --daemonize yes
