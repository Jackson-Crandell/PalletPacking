#!/bin/bash

# EC2 Headless Display Setup Script
# This script sets up a virtual display for 3D rendering on EC2 instances

echo "Setting up headless display environment for EC2..."

# Update package list
sudo apt-get update

# Install X Virtual Framebuffer and OpenGL libraries
sudo apt-get install -y \
    xvfb \
    x11-xserver-utils \
    xfonts-base \
    xfonts-100dpi \
    xfonts-75dpi \
    xfonts-cyrillic \
    mesa-utils \
    libgl1-mesa-dev \
    libgl1-mesa-dri \
    libglu1-mesa-dev \
    freeglut3-dev \
    libglew-dev \
    libglfw3-dev \
    libglm-dev

# Install additional graphics libraries
sudo apt-get install -y \
    libosmesa6-dev \
    libglapi-mesa \
    libegl1-mesa-dev \
    libgles2-mesa-dev \
    libxrandr2 \
    libxinerama1 \
    libxcursor1 \
    libxi6

echo "Packages installed successfully!"

# Set up environment variables for headless rendering
echo "Setting up environment variables..."

# Create environment setup script
cat > ~/setup_display_env.sh << 'EOF'
#!/bin/bash

# Set up virtual display
export DISPLAY=:99
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330
export GALLIUM_DRIVER=llvmpipe
export LIBGL_ALWAYS_SOFTWARE=1

# Start Xvfb if not running
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "Starting virtual display..."
    Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
    sleep 2
    echo "Virtual display started on :99"
else
    echo "Virtual display already running"
fi

# Verify display is working
echo "Testing display connection..."
if xdpyinfo -display :99 >/dev/null 2>&1; then
    echo "✓ Display :99 is working"
else
    echo "✗ Display setup failed"
    exit 1
fi
EOF

chmod +x ~/setup_display_env.sh

echo "Environment setup script created at ~/setup_display_env.sh"

# Create systemd service for automatic Xvfb startup
echo "Creating systemd service for automatic display startup..."

sudo tee /etc/systemd/system/xvfb.service > /dev/null << 'EOF'
[Unit]
Description=X Virtual Frame Buffer Service
After=network.target

[Service]
Type=simple
User=ubuntu
Environment=DISPLAY=:99
ExecStart=/usr/bin/Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable xvfb.service
sudo systemctl start xvfb.service

echo "Xvfb service created and started"

# Add environment variables to bashrc
echo "Adding environment variables to ~/.bashrc..."
cat >> ~/.bashrc << 'EOF'

# Headless rendering environment
export DISPLAY=:99
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330
export GALLIUM_DRIVER=llvmpipe
export LIBGL_ALWAYS_SOFTWARE=1
EOF

echo ""
echo "✓ EC2 headless display setup complete!"
echo ""
echo "Next steps:"
echo "1. Run: source ~/.bashrc"
echo "2. Or run: source ~/setup_display_env.sh"
echo "3. Test with: python test_headless_rendering.py"
echo ""
echo "The Xvfb service will automatically start on boot."