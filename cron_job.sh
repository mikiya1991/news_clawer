#!/bin/bash
# Setup cron job for X.com Tweet Scraper on macOS
# This script helps configure the scraper to run periodically

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/main.py"
LOG_DIR="$SCRIPT_DIR/logs"

# Create logs directory
mkdir -p "$LOG_DIR"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}X.com Tweet Scraper - Cron Job Setup${NC}"
echo "========================================"
echo ""
echo "This script will help you setup a cron job to run the scraper periodically."
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found${NC}"
    exit 1
fi

# Ask for frequency
echo "How often should the scraper run?"
echo "1) Every hour"
echo "2) Every 6 hours"
echo "3) Every 12 hours"
echo "4) Daily"
echo "5) Custom"
read -p "Select option (1-5): " frequency

case $frequency in
    1)
        CRON_SCHEDULE="0 * * * *"
        FREQUENCY_DESC="every hour"
        ;;
    2)
        CRON_SCHEDULE="0 */6 * * *"
        FREQUENCY_DESC="every 6 hours"
        ;;
    3)
        CRON_SCHEDULE="0 */12 * * *"
        FREQUENCY_DESC="every 12 hours"
        ;;
    4)
        CRON_SCHEDULE="0 0 * * *"
        FREQUENCY_DESC="daily at midnight"
        ;;
    5)
        read -p "Enter cron schedule (e.g., '*/30 * * * *' for every 30 minutes): " CRON_SCHEDULE
        FREQUENCY_DESC="custom schedule: $CRON_SCHEDULE"
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

# Create cron command
CRON_COMMAND="$CRON_SCHEDULE cd $SCRIPT_DIR && /usr/bin/python3 $PYTHON_SCRIPT --collect --headless"

echo ""
echo -e "${YELLOW}Cron Job Details:${NC}"
echo "Schedule: $FREQUENCY_DESC"
echo "Command: $CRON_COMMAND"
echo ""

# Add to crontab
read -p "Continue with setup? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "$PYTHON_SCRIPT"; then
        echo -e "${YELLOW}Cron job already exists. Updating...${NC}"
        # Remove old cron job
        (crontab -l 2>/dev/null | grep -v "$PYTHON_SCRIPT"; echo "$CRON_COMMAND") | crontab -
    else
        # Add new cron job
        (crontab -l 2>/dev/null; echo "$CRON_COMMAND") | crontab -
    fi
    
    echo -e "${GREEN}✓ Cron job installed successfully!${NC}"
    echo ""
    echo "Current cron jobs:"
    crontab -l
    echo ""
    echo -e "${GREEN}The scraper will run $FREQUENCY_DESC${NC}"
    echo "Logs will be saved to: $LOG_DIR"
else
    echo "Setup cancelled."
    exit 1
fi

echo ""
echo "Setup Options:"
echo "1. View cron logs: tail -f $LOG_DIR/scraper.log"
echo "2. Remove cron job: crontab -e (then delete the line)"
echo "3. Run scraper now: python3 $PYTHON_SCRIPT --collect"
echo "4. Manual login: python3 $PYTHON_SCRIPT --login"
echo ""
