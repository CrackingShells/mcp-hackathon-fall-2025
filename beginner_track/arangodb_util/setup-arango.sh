#!/bin/bash

# ArangoDB Setup Script for Linux/macOS
# Initializes ArangoDB container with database and user
# Usage: ./setup-arango.sh [-r PASSWORD] [-d DBNAME] [-u USERNAME] [-p PASSWORD] [-s]

set -e

# Default values
ROOT_PASSWORD="changeme"
DB_NAME="mcp_arangodb_test"
USER="mcp_arangodb_user"
PASSWORD="mcp_arangodb_password"
SEED=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--root-password)
            ROOT_PASSWORD="$2"
            shift 2
            ;;
        -d|--db-name)
            DB_NAME="$2"
            shift 2
            ;;
        -u|--username)
            USER="$2"
            shift 2
            ;;
        -p|--password)
            PASSWORD="$2"
            shift 2
            ;;
        -s|--seed)
            SEED=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -r, --root-password PASSWORD   Root password (default: changeme)"
            echo "  -d, --db-name DBNAME           Database name (default: mcp_arangodb_test)"
            echo "  -u, --username USERNAME        Database user (default: mcp_arangodb_user)"
            echo "  -p, --password PASSWORD        User password (default: mcp_arangodb_password)"
            echo "  -s, --seed                     Seed with sample data"
            echo "  -h, --help                     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Configuring ArangoDB (container: mcp_arangodb_test) ..."

# Wait until container is healthy or at least Up
MAX_TRIES=10
for ((i=0; i<MAX_TRIES; i++)); do
    STATUS=$(docker ps --filter name=mcp_arangodb_test --format "{{.Status}}" 2>/dev/null || echo "")
    if [[ $STATUS =~ (healthy|Up) ]]; then
        echo -e "${GREEN}✓${NC} ArangoDB container is $STATUS"
        break
    fi
    if [ $i -lt $((MAX_TRIES - 1)) ]; then
        echo "Waiting for ArangoDB container... ($((i + 1))/$MAX_TRIES)"
        sleep 2
    fi
done

if [ $i -ge $MAX_TRIES ]; then
    echo -e "${RED}✗ ArangoDB container not healthy${NC}. Check 'docker compose logs arangodb'"
    exit 1
fi

# Create temp directory for JS scripts
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

SETUP_JS="$TMP_DIR/setup-db.js"
SEED_JS="$TMP_DIR/seed.js"

# Prepare database and user setup script
cat > "$SETUP_JS" << 'EOF'
const users = require('@arangodb/users');
const db = require('@arangodb').db;

// Create database if it doesn't exist
if (!db._databases().includes('${DB_NAME}')) {
    db._createDatabase('${DB_NAME}');
    console.log('Created database: ${DB_NAME}');
} else {
    console.log('Database already exists: ${DB_NAME}');
}

// Create or update user
users.save('${USER}', '${PASSWORD}', true);
users.grantDatabase('${USER}', '${DB_NAME}', 'rw');
console.log('Created/updated user: ${USER}');
EOF

# Substitute variables in setup script
sed -i.bak "s/\${DB_NAME}/$DB_NAME/g; s/\${USER}/$USER/g; s/\${PASSWORD}/$PASSWORD/g" "$SETUP_JS"
rm -f "$SETUP_JS.bak"

# Copy setup script to container
echo "Copying setup script to container..."
docker cp "$SETUP_JS" mcp_arangodb_test:/tmp/setup-db.js

# Execute database setup
echo "Creating database and user..."
docker exec -t mcp_arangodb_test arangosh \
    --server.username root \
    --server.password "$ROOT_PASSWORD" \
    --javascript.execute /tmp/setup-db.js

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to create database/user${NC}. Inspect with: docker compose logs arangodb"
    exit 1
fi

echo -e "${GREEN}✓${NC} Database and user created successfully"

# Optional: Seed sample data
if [ "$SEED" = true ]; then
    cat > "$SEED_JS" << 'EOF'
const db = require('@arangodb').db;
db._useDatabase('${DB_NAME}');

// Create sample collection
if (!db._collection('users')) {
    db._createDocumentCollection('users');
    console.log('Created collection: users');
}

// Insert sample documents
db.users.insert([
    { name: 'Alice', status: 'active' },
    { name: 'Bob', status: 'inactive' }
]);
console.log('Inserted sample documents');
EOF

    # Substitute variables in seed script
    sed -i.bak "s/\${DB_NAME}/$DB_NAME/g" "$SEED_JS"
    rm -f "$SEED_JS.bak"

    # Copy and execute seed script
    echo "Seeding sample data..."
    docker cp "$SEED_JS" mcp_arangodb_test:/tmp/seed.js

    docker exec -t mcp_arangodb_test arangosh \
        --server.username root \
        --server.password "$ROOT_PASSWORD" \
        --javascript.execute /tmp/seed.js

    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}⚠${NC}  Seeding failed; continue without sample data."
    else
        echo -e "${GREEN}✓${NC} Sample data created successfully"
    fi
fi

echo -e "${GREEN}Done${NC}. Database '$DB_NAME' and user '$USER' ready."
echo ""
echo "Connection Details:"
echo "  URL: http://localhost:8529"
echo "  Database: $DB_NAME"
echo "  Username: $USER"
echo "  Web UI: http://localhost:8529 (login with root:$ROOT_PASSWORD)"
