#!/bin/bash
# Hostinger VPS deployment script
# Usage: ./deploy.sh [setup|deploy|logs|restart]

set -e

APP_DIR="/home/$(whoami)/tenders"
COMPOSE_FILE="docker-compose.prod.yml"

case "$1" in
  setup)
    echo "=== Initial Hostinger VPS Setup ==="

    # Install Docker if not present
    if ! command -v docker &> /dev/null; then
      echo "Installing Docker..."
      curl -fsSL https://get.docker.com | sh
      sudo usermod -aG docker $USER
      echo "Docker installed. Log out and back in, then re-run this script."
      exit 0
    fi

    # Install Docker Compose plugin if not present
    if ! docker compose version &> /dev/null; then
      echo "Installing Docker Compose plugin..."
      sudo apt-get update && sudo apt-get install -y docker-compose-plugin
    fi

    # Create cert directory
    mkdir -p "$APP_DIR/nginx/certs"

    echo "=== Setup complete ==="
    echo "Next steps:"
    echo "  1. Copy your .env files to backend/.env, frontend/.env, ml-backend/.env"
    echo "  2. Place SSL certs in nginx/certs/ (fullchain.pem + privkey.pem)"
    echo "  3. Run: ./deploy.sh deploy"
    ;;

  deploy)
    echo "=== Deploying ==="
    cd "$APP_DIR"
    git pull origin main
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d --build
    docker compose -f "$COMPOSE_FILE" ps
    echo "=== Deploy complete ==="
    ;;

  logs)
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" logs -f "${2:-}"
    ;;

  restart)
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" restart "${2:-}"
    ;;

  status)
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" ps
    ;;

  *)
    echo "Usage: ./deploy.sh [setup|deploy|logs|restart|status]"
    echo ""
    echo "  setup    - Install Docker & prep VPS (run once)"
    echo "  deploy   - Pull latest code and rebuild containers"
    echo "  logs     - Tail logs (optional: service name)"
    echo "  restart  - Restart services (optional: service name)"
    echo "  status   - Show running containers"
    ;;
esac
