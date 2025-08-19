#!/bin/bash

# EC2 Deployment Script for Pallet Packing Application
# This script sets up the complete environment for running the pallet packing app on EC2

set -e  # Exit on any error

echo "🚀 Starting EC2 Deployment for Pallet Packing Application"
echo "==========================================================="

# Function to print colored output
print_status() {
    echo -e "\033[1;32m✓ $1\033[0m"
}

print_warning() {
    echo -e "\033[1;33m⚠ $1\033[0m"
}

print_error() {
    echo -e "\033[1;31m✗ $1\033[0m"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as ubuntu user."
   exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update
print_status "System packages updated"

# Install Python and pip if not already installed
echo "🐍 Installing Python dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv python3-dev
print_status "Python dependencies installed"

# Install system packages for headless rendering
echo "🖥️ Installing headless rendering packages..."
sudo apt-get install -y \
    xvfb \
    x11-xserver-utils \
    xfonts-base \
    xfonts-100dpi \
    xfonts-75dpi \
    xfonts-cyrillic \
    mesa-utils \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libglu1-mesa \
    freeglut3-dev \
    libglew-dev \
    libglfw3-dev \
    libglm-dev \
    libosmesa6-dev \
    libglapi-mesa \
    libegl1-mesa-dev \
    libgles2-mesa-dev \
    build-essential

print_status "Headless rendering packages installed"

# Install additional development tools
echo "🔧 Installing development tools..."
sudo apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    htop \
    nginx \
    sqlite3
print_status "Development tools installed"

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment and install Python packages
echo "📚 Installing Python packages..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

print_status "Python packages installed"

# Set up environment variables for headless rendering
echo "🔧 Setting up environment variables..."

# Create environment setup script
cat > setup_env.sh << 'EOF'
#!/bin/bash
# Environment setup for headless rendering
export DISPLAY=:99
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330
export GALLIUM_DRIVER=llvmpipe
export LIBGL_ALWAYS_SOFTWARE=1

# Django settings
export DJANGO_SETTINGS_MODULE=pallet_packing_web.settings
export PYTHONPATH=$PYTHONPATH:$(pwd)

echo "Environment variables set for headless rendering"
EOF

chmod +x setup_env.sh
print_status "Environment setup script created"

# Add environment variables to bashrc
if ! grep -q "DISPLAY=:99" ~/.bashrc; then
    cat >> ~/.bashrc << 'EOF'

# Headless rendering environment for Pallet Packing App
export DISPLAY=:99
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330
export GALLIUM_DRIVER=llvmpipe
export LIBGL_ALWAYS_SOFTWARE=1
EOF
    print_status "Environment variables added to ~/.bashrc"
else
    print_warning "Environment variables already in ~/.bashrc"
fi

# Set up Xvfb as a systemd service
echo "🖥️ Setting up Xvfb service..."
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

sudo systemctl daemon-reload
sudo systemctl enable xvfb.service
sudo systemctl start xvfb.service

# Check if service is running
if sudo systemctl is-active --quiet xvfb.service; then
    print_status "Xvfb service started and enabled"
else
    print_warning "Xvfb service may not be running properly"
fi

# Run Django migrations
echo "🗄️ Setting up Django database..."
source venv/bin/activate
source setup_env.sh

python manage.py makemigrations
python manage.py migrate
print_status "Django database setup completed"

# Create superuser (optional)
echo "👤 Creating Django superuser..."
echo "You can create a superuser account for Django admin access."
read -p "Do you want to create a superuser now? (y/n): " create_superuser

if [[ $create_superuser =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
    print_status "Superuser created"
else
    print_warning "Skipped superuser creation"
fi

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput
print_status "Static files collected"

# Test the headless rendering setup
echo "🧪 Testing headless rendering setup..."
python test_headless_rendering.py

if [ $? -eq 0 ]; then
    print_status "Headless rendering test passed"
else
    print_warning "Headless rendering test had some issues - check output above"
fi

# Create startup script
echo "🚀 Creating startup script..."
cat > start_server.sh << 'EOF'
#!/bin/bash
# Startup script for Pallet Packing Application

# Activate virtual environment
source venv/bin/activate

# Set environment variables
source setup_env.sh

# Start Django development server
echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000
EOF

chmod +x start_server.sh
print_status "Startup script created"

# Create production startup script with gunicorn
echo "🏭 Creating production startup script..."
pip install gunicorn

cat > start_production.sh << 'EOF'
#!/bin/bash
# Production startup script for Pallet Packing Application

# Activate virtual environment
source venv/bin/activate

# Set environment variables
source setup_env.sh

# Start with gunicorn
echo "Starting production server with gunicorn..."
gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 300 pallet_packing_web.wsgi:application
EOF

chmod +x start_production.sh
print_status "Production startup script created"

# Create nginx configuration
echo "🌐 Setting up nginx configuration..."
sudo tee /etc/nginx/sites-available/pallet-packing << EOF
server {
    listen 80;
    server_name $(curl -s http://169.254.169.254/latest/meta-data/public-hostname);

    location /static/ {
        alias $(pwd)/staticfiles/;
    }

    location /media/ {
        alias $(pwd)/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/pallet-packing /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

print_status "Nginx configuration setup completed"

# Create systemd service for the app
echo "🔧 Creating systemd service for the application..."
sudo tee /etc/systemd/system/pallet-packing.service > /dev/null << EOF
[Unit]
Description=Pallet Packing Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 --timeout 300 pallet_packing_web.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pallet-packing.service

print_status "Systemd service created"

# Final instructions
echo ""
echo "🎉 EC2 Deployment Completed Successfully!"
echo "========================================"
echo ""
echo "Your Pallet Packing Application is now ready to run on EC2!"
echo ""
echo "📋 Next Steps:"
echo "1. Start the application:"
echo "   ./start_server.sh              # For development"
echo "   ./start_production.sh          # For production (recommended)"
echo ""
echo "2. Or use systemd service:"
echo "   sudo systemctl start pallet-packing"
echo "   sudo systemctl status pallet-packing"
echo ""
echo "3. Access your application:"
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
PUBLIC_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname)
echo "   http://$PUBLIC_IP"
echo "   http://$PUBLIC_HOSTNAME"
echo ""
echo "4. Test headless rendering:"
echo "   python test_headless_rendering.py"
echo ""
echo "📝 Important Notes:"
echo "• Make sure your EC2 security group allows HTTP (port 80) and custom port 8000"
echo "• The Xvfb service will start automatically on boot"
echo "• Check logs: sudo journalctl -u xvfb.service"
echo "• Check app logs: sudo journalctl -u pallet-packing.service"
echo ""
echo "🔧 Troubleshooting:"
echo "• If rendering fails, run: sudo systemctl restart xvfb.service"
echo "• Check display: echo \$DISPLAY (should show :99)"
echo "• Test display: xdpyinfo -display :99"
echo ""
print_status "Deployment script completed!"