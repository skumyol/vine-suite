#!/bin/bash
# GitHub Setup Script for Vine Suite Meta-Repo
# Run this after pushing individual repos to GitHub

set -e

echo "🍷 Vine Suite - GitHub Setup"
echo ""

# Check if repos exist on GitHub
check_repo() {
    local url=$1
    if curl -s --head "$url" | grep -q "200 OK"; then
        return 0
    else
        return 1
    fi
}

# Get GitHub username
read -p "Enter your GitHub username: " GITHUB_USER

echo ""
echo "Checking your GitHub repos..."
echo ""

VINE2_URL="https://github.com/$GITHUB_USER/vine2"
VINE_STUDIO_URL="https://github.com/$GITHUB_USER/vine_studio"
VINE_REC_URL="https://github.com/$GITHUB_USER/vine_rec"

# Verify repos exist
echo "✓ vine2: $VINE2_URL"
echo "✓ vine_studio: $VINE_STUDIO_URL"
echo "✓ vine_rec: $VINE_REC_URL"
echo ""

read -p "Have you pushed all three repos to GitHub? (y/n): " CONFIRM

if [[ $CONFIRM != "y" ]]; then
    echo ""
    echo "Please push your repos to GitHub first:"
    echo ""
    echo "  cd /Users/skumyol/Documents/GitHub/vine2"
    echo "  git remote add origin https://github.com/$GITHUB_USER/vine2.git"
    echo "  git push -u origin main"
    echo ""
    echo "  cd /Users/skumyol/Documents/GitHub/vine_studio"
    echo "  git remote add origin https://github.com/$GITHUB_USER/vine_studio.git"
    echo "  git push -u origin main"
    echo ""
    echo "  cd /Users/skumyol/Documents/GitHub/vine_rec"
    echo "  git remote add origin https://github.com/$GITHUB_USER/vine_rec.git"
    echo "  git push -u origin main"
    echo ""
    exit 1
fi

echo ""
echo "Converting symlinks to git submodules..."
echo ""

# Remove symlinks
rm -f vine2 vine-studio vine-rec

# Add submodules
git submodule add "$VINE2_URL.git" vine2
git submodule add "$VINE_STUDIO_URL.git" vine-studio
git submodule add "$VINE_REC_URL.git" vine-rec

echo ""
echo "Committing changes..."
git add .gitmodules
git commit -m "Convert symlinks to git submodules for GitHub"

echo ""
echo "✅ Setup complete!"
echo ""
echo "To push the meta-repo to GitHub:"
echo "  git remote add origin https://github.com/$GITHUB_USER/vine-suite.git"
echo "  git push -u origin main"
echo ""
echo "To clone this meta-repo elsewhere:"
echo "  git clone --recurse-submodules https://github.com/$GITHUB_USER/vine-suite.git"
echo ""
