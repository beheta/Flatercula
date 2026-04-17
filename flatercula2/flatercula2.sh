#!/bin/bash
cd /opt/flatercula2
echo "AIUI Fratercula GUI starting…"
sudo systemctl restart ollama
notify-send "Flatercula started" "Flatercula is running. The first inference may take a moment."
python3 /opt/flatercula2/aiui_gui.py &
python3 /opt/flatercula2/Flatercula_pull_tool.py
