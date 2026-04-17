#!/usr/bin/env bash
# flatercula2/install2.sh
# -------------  Flatercula Installer (post‑fix)  -------------
# 2026-01-25 v0.0.1 (fixed copy/permissions)

cd "$(dirname "$0")"

echo "Installing OS‑level dependencies..."

if command -v apt > /dev/null; then
    sudo apt update
    sudo apt install -y python3-full python3-pip curl ffmpeg python3-requests python3-soundfile python3-whisper python3-numpy python3-psutil python3-pyqt6 build-essential 
    sudo -H pip3 install portaudio --break-system-packages
elif command -v dnf > /dev/null; then
    sudo dnf install -y python3-full python3-pip curl ffmpegsudo -H pip3 install portaudio --break-system-packages
    sudo -H pip3 install portaudio --break-system-packages
fi

sudo pip3 install -r requirements.txt

echo "Pre‑loading Whisper base model..."
sudo python3 -c "import whisper; whisper.load_model('base')"

echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh |OLLAMA_VERSION=0.15.0 sh

echo "Pulling qwen2.5:7b model..."
sudo ollama pull qwen2.5:7b

sudo rm -rf /opt/flatercula2    
sudo mkdir -p /opt/flatercula2
sudo cp -r flatercula2 /opt

sudo chmod -R 755 /opt/flatercula2
sudo chmod +x /opt/flatercula2/flatercula2.sh
sudo chmod +x /opt/flatercula2/flatercula2_cli.sh
sudo chmod +x /opt/flatercula2/ollamafile.sh

sudo ln -sf /opt/flatercula2/flatercula2.sh /usr/local/bin/flatercula
sudo ln -sf /opt/flatercula2/flatercula2.sh /usr/local/bin/flatercula2
sudo ln -sf /opt/flatercula2/flatercula2_cli.sh /usr/local/bin/flatercula-cli
sudo ln -sf /opt/flatercula2/flatercula2_cli.sh /usr/local/bin/flatercula2-cli

cat > /usr/share/applications/flatercula.desktop <<'EOF'
[Desktop Entry]
Type=Application
Exec=gnome-terminal -- /bin/bash /opt/flatercula2/flatercula2.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Flatercula (GUI)
Comment=AI‑UI Agent GUI
Icon=/opt/flatercula2/logo.png
EOF

cat > /usr/share/applications/flatercula_cli.desktop <<'EOF'
[Desktop Entry]
Type=Application
Exec=gnome-terminal -- /bin/bash /opt/flatercula2/flatercula2_cli.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Flatercula (CLI)
Comment=AI‑UI Agent CLI
Icon=/opt/flatercula2/logo_cli.png
EOF

sudo mkdir -p /etc/xdg/autostart
sudo cp /usr/share/applications/flatercula.desktop /etc/xdg/autostart/
sudo cp /usr/share/applications/flatercula_cli.desktop /etc/xdg/autostart/

echo "Installation finished."
echo "You may reboot now or just restart the ollama service. #flatercula/#flatercula-cli"
