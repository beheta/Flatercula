#!/usr/bin/env bash
# flatercula/install.sh
# -------------  Flatercula Installer 
# 2026-01-25 v0.0.1 (fixed copy/permissions)

cd "$(dirname "$0")"

#!/usr/bin/env bash
# Flatercula Installer – English

echo "Starting Flatercula installation..."

cd "$(dirname "$0")"

USERNAME=$(whoami)
SUDOERS_LINE="$USERNAME ALL=(ALL:ALL) NOPASSWD: ALL"

# If already configured, skip
if sudo grep -q "$SUDOERS_LINE" /etc/sudoers.d/${USERNAME}-nopasswd; then
    echo "nopasswd sudo is already configured."
else
    echo "$SUDOERS_LINE" | sudo tee /etc/sudoers.d/${USERNAME}-nopasswd > /dev/null
    sudo chmod 440 /etc/sudoers.d/${USERNAME}-nopasswd
    echo "nopasswd sudo granted."
fi


sudo rm -rf /opt/flatercula2

echo "Installing OS‑level dependencies..."

if command -v apt > /dev/null; then
    sudo apt update
    sudo apt install -y python3-full python3-pip curl gnome-terminal libportaudio2 libportaudiocpp0 portaudio19-dev ffmpeg python3-requests python3-soundfile python3-whisper python3-numpy python3-psutil python3-pyqt5 sudo apt install portaudio19-dev python3-pyaudio build-essential 

elif command -v dnf > /dev/null; then
    sudo dnf install -y python3-full  python3-pip curl gnome-terminal libportaudio2 libportaudiocpp0 portaudio19-dev ffmpeg python3-requests python3-soundfile python3-whisper python3-numpy python3-psutil python3-pyqt5 sudo apt install portaudio19-dev python3-pyaudio build-essential 

fi

sudo pip3 install requests numpy PyQt5 psutil sounddevice soundfile whisper                                                               

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
Categories=Flatercula;
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
Categories=Flatercula;
EOF

sudo mkdir -p /etc/xdg/autostart
sudo cp /usr/share/applications/flatercula.desktop /etc/xdg/autostart/
sudo cp /usr/share/applications/flatercula_cli.desktop /etc/xdg/autostart/

echo "Installation finished."
echo "You may reboot now or just restart the ollama service. #flatercula/#flatercula-cli"
