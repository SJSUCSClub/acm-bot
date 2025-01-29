#!/bin/bash
cd /home/acmcs/acm-bot
source ./venv/bin/activate

python3 -m pip install -r requirements.txt

cd ./bot

python3 main.py &
