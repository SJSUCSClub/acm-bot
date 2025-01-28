cd /home/acm/acm-bot
source ./venv/bin/activate
git pull

python3 -m pip install -r requirements.txt

cd ./monitor

python3 main.py &
