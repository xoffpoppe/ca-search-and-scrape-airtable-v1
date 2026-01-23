#!/bin/bash
# CA Search and Scrape v1 - GitHub Deployment Script
# Run this script on your local machine after extracting the ZIP

set -e  # Exit on any error

echo "============================================"
echo "CA Search and Scrape v1 - GitHub Deployment"
echo "============================================"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install Git first."
    exit 1
fi

# Get GitHub username
read -p "Enter your GitHub username: " GITHUB_USERNAME

# Get repository name (default: ca-search-and-scrape-v1)
read -p "Enter repository name [ca-search-and-scrape-v1]: " REPO_NAME
REPO_NAME=${REPO_NAME:-ca-search-and-scrape-v1}

# Get Personal Access Token
echo ""
echo "⚠️  You need a GitHub Personal Access Token"
echo "Create one at: https://github.com/settings/tokens"
echo "Required scope: 'repo'"
echo ""
read -sp "Enter your GitHub Personal Access Token: " GITHUB_TOKEN
echo ""

# Validate we're in the right directory
if [ ! -f "Dockerfile" ] || [ ! -d "src" ]; then
    echo "❌ Error: This script must be run from the ca-search-and-scrape-v1 directory"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo ""
echo "📦 Initializing git repository..."
git init

echo "📝 Adding files..."
git add .

echo "💾 Creating initial commit..."
git commit -m "Initial commit - CA Search and Scrape v1

Combined actor that searches Vistage/Salesforce for candidates and 
automatically scrapes high-confidence matches (≥70%).

Features:
- Cascading search (LinkedIn → Domain → Name+Company)
- Fuzzy matching with 100+ nickname variations
- Auto-scrape for ≥70% confidence
- Returns search-only results for <70%
- Single browser session (efficient)
- Complete timing information"

echo "🌐 Creating GitHub repository..."
# Create repo using GitHub API
curl -s -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/user/repos \
     -d "{\"name\":\"$REPO_NAME\",\"description\":\"Combined Vistage candidate search and scrape actor\",\"private\":true}" \
     > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Repository created successfully"
else
    echo "⚠️  Repository might already exist, continuing..."
fi

echo "🔗 Adding remote..."
git remote add origin "https://$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/$REPO_NAME.git"

echo "📤 Pushing to GitHub..."
git branch -M main
git push -u origin main

echo ""
echo "============================================"
echo "✅ SUCCESS!"
echo "============================================"
echo ""
echo "Repository URL: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo ""
echo "Next steps:"
echo "1. Go to Apify Console: https://console.apify.com/actors"
echo "2. Click 'Create new' → 'Git repository'"
echo "3. Paste: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo "4. Branch: main"
echo "5. Click 'Create'"
echo ""
echo "🎉 Your actor is ready to deploy!"
