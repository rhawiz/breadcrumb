sudo pip install -r requirements.txt
sudo git pull
sudo python manage.py migrate
sudo /opt/bitnami/ctlscript.sh restart apache