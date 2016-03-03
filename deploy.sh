sudo git pull
sudo pip install -r requirements.txt
sudo python manage.py migrate
sudo /opt/bitnami/ctlscript.sh restart apache