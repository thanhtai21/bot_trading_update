#!/bin/bash
# bmt-smart-upgrade.sh - Smart upgrade script cho BMT Trading Bot
# Sử dụng: ./bmt-smart-upgrade.sh [--dry-run] [--help]

# ==== CẤU HÌNH ====
USER="user"
PROJECT_DIR="/home/user/BWM/MT5_Bot - 0.75 lot - Linux"
SERVICE_NAME="bmt-trading-bot.service"
SESSION_NAME="bmt-bot"
LOG_DIR="$HOME/BMT_logs"
BOT_SCRIPT="$PROJECT_DIR/trading_bot_v2.py"
BACKUP_DIR="$HOME/BMT_backups"

# ==== MÀU ====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

# ==== FUNCTIONS ====

print_header() {
    echo -e "${CYAN}🚀 BMT Smart Upgrade Script${NC}"
    echo -e "${CYAN}====================================${NC}"
}

print_step() {
    echo -e "\n${GREEN}▶ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✅ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  ${1}${NC}"
}

print_error() {
    echo -e "${RED}❌ ${1}${NC}"
}

log_message() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GRAY}[$timestamp]${NC} $1"
}

create_directories() {
    print_step "Tạo thư mục cần thiết"
    
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    
    print_success "Thư mục đã sẵn sàng: $LOG_DIR, $BACKUP_DIR"
}

check_system_status() {
    print_step "Kiểm tra trạng thái hệ thống hiện tại"
    
    # Kiểm tra service
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_success "✅ Bot đang chạy trong systemd"
    else
        print_warning "⚠️  Bot không chạy trong systemd"
    fi
    
    # Kiểm tra tmux session
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        print_success "✅ Bot đang chạy trong tmux session ($SESSION_NAME)"
    else
        print_warning "⚠️  Không có tmux session $SESSION_NAME"
    fi
}

stop_bot_safely() {
    print_step "Dừng bot một cách an toàn"
    
    # Dừng systemd service
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "🛑 Đang dừng systemd service $SERVICE_NAME..."
        sudo systemctl stop "$SERVICE_NAME"
        
        # Đợi 3 giây
        for i in {1..6}; do
            if ! systemctl is-active --quiet "$SERVICE_NAME"; then
                break
            fi
            echo "⏳ Đang chờ bot dừng ($i/6)..."
            sleep 1
        done
        
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            print_error "❌ Bot vẫn đang chạy sau 6 giây! Cố gắng kill..."
            sudo systemctl kill "$SERVICE_NAME"
            sleep 2
        else
            print_success "✅ Systemd service đã được dừng"
        fi
    else
        print_success "✅ Systemd service đã dừng"
    fi
    
    # Dừng tmux session
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "🛑 Đang dừng tmux session $SESSION_NAME..."
        tmux kill-session -t "$SESSION_NAME"
        print_success "✅ Tmux session đã được dừng"
    else
        print_success "✅ Không có tmux session hoạt động"
    fi
    
    # Kiểm tra lại
    local service_active=false
    local tmux_active=false
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        service_active=true
        print_error "❌ Service vẫn đang chạy!"
    fi
    
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        tmux_active=true
        print_error "❌ Tmux session vẫn đang chạy!"
    fi
    
    if [[ "$service_active" == false && "$tmux_active" == false ]]; then
        print_success "✅ Bot đã hoàn toàn dừng"
    else
        print_warning "⚠️  Bot vẫn đang chạy - có thể để lại process"
    fi
}

backup_and_pull() {
    print_step "Sao chép backup và pull code mới"
    
    local backup_file="$BACKUP_DIR/bmt_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    # Tạo backup
    echo "📦 Tạo backup code..."
    tar -czf "$backup_file" -C "$(dirname "$PROJECT_DIR")" "$(basename "$PROJECT_DIR")"
    print_success "✅ Backup được tạo tại: $backup_file"
    
    # Pull code mới
    echo "📥 Đang pull code từ repository..."
    cd "$PROJECT_DIR"
    
    if git status | grep -q "\[uncommitted\]"; then
        print_warning "⚠️  Phát hiện các thay đổi chưa được commit"
        read -p "❓ Có muốn stash lại các thay đổi không? (y/N): " -r
        if [[ "$REPLY" == "y" || "$REPLY" == "Y" ]]; then
            echo "🗃️  Stashing changes..."
            git stash push -m "Auto-stash before upgrade $(date)"
            print_success "✅ Changes đã được stash"
        else
            print_warning "⚠️  Bỏ qua changes - có thể có xung đột"
        fi
    fi
    
    local branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --abbrev-ref HEAD)
    
    # Pull từ upstream
    if git pull origin "$branch" 2>&1; then
        print_success "✅ Code đã được pull thành công"
        
        # Hiển thị commit mới
        echo "📋 Các commit gần đây (branch '$branch'):"
        git log --oneline -5
    else
        print_error "❌ Pull thất bại!"
        echo "<< Chi tiết lỗi pull >>"
        git pull origin "$branch"
        return 1
    fi
    
    # Kiểm tra logs
    if [[ -f "$LOG_DIR/bmt_startup.log" ]] && [[ -s "$LOG_DIR/bmt_startup.log" ]]; then
        mv "$LOG_DIR/bmt_startup.log" "$LOG_DIR/bmt_startup.log.backup.$(date +%Y%m%d_%H%M%S)"
        print_success "✅ Log đã được backup"
    fi
}

start_bot_new() {
    print_step "Bắt đầu phiên bản bot mới"
    
    # Tải lại systemd
    echo "🔄 Tải lại systemd..."
    sudo systemctl daemon-reload
    
    # Kích hoạt và bắt đầu service
    echo "🚀 Bắt đầu service systemd..."
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start "$SERVICE_NAME"
    
    # Kiểm tra service
    local max_attempts=10
    local attempt=1
    local service_running=false
    
    while [[ "$attempt" -le "$max_attempts" ]]; do
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            service_running=true
            break
        fi
        echo "⏳ Đang chờ bot bắt đầu ($attempt/$max_attempts)..."
        sleep 3
        ((attempt++))
    done
    
    if [[ "$service_running" == true ]]; then
        print_success "✅ Bot bắt đầu thành công"
        
        # Tạo tmux session (tùy chọn)
        echo -e "\n🎯 Tạo tmux session (tùy chọn)..."
        echo -e "$YELLOW"Chọn 'y' để tạo tmux session chạy song song (hoặc nhấn Enter để bỏ qua):${NC}"
        read -p ">>> " create_session
        
        if [[ "$create_session" =~ ^[Yy]$ ]]; then
            cd "$PROJECT_DIR"
            tmux new-session -d -s "$SESSION_NAME" "$BOT_SCRIPT" \
                -name "BMT Bot" \
                -t "$(basename "$SESSION_NAME")"
            
            if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
                print_success "✅ Session tmux $SESSION_NAME đã được tạo"
                echo "💡 Sử dụng commands:"
                echo "   - Attach: tmux attach -t $SESSION_NAME"
                echo "   - Detach (bot vẫn chạy): Ctrl+b, sau đó nhấn D"
                echo "   - Kill: tmux kill-session -t $SESSION_NAME"
            else
                print_error "❌ Không thể tạo tmux session"
            fi
        fi
        
    else
        print_error "❌ Bot không thể bắt đầu!"
        return 1
    fi
}

check_bot_status() {
    print_step "Kiểm tra lại toàn bộ trạng thái bot"
    
    echo -e "\n${GREEN}📊 Status Kiểm Tra:${NC}"
    echo -e "----------------------------------"
    
    # Trạng thái systemd
    local systemd_status=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "inactive")
    if [[ "$systemd_status" == "active" ]]; then
        echo -e "${GREEN}✅ Systemd Service:     HOẠT ĐỘNG${NC}"
        systemctl status "$SERVICE_NAME" --no-pager | grep "Active:"
    else
        echo -e "${RED}❌ Systemd Service:     $systemd_status${NC}"
    fi
    
    # Trạng thái tmux
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo -e "${GREEN}✅ Tmux Session:       HOẠT ĐỘNG ($SESSION_NAME)${NC}"
        tmux list-sessions -t "$SESSION_NAME"
    else
        echo -e "${GRAY}⏸️  Tmux Session:       KHÔNG HOẠT ĐỘNG${NC}"
    fi
    
    # Live log tail
    echo -e "\n${GREEN}📋 Log Activity (Đọc từ log trong 10s):${NC}"
    echo -e "----------------------------------"
    if [[ -f "$LOG_DIR/bmt_startup.log" ]]; then
        timeout 10 tail -f "$LOG_DIR/bmt_startup.log" 2>/dev/null || echo "\n⏰ Log tạm dừng sau 10s..."
    else
        echo "⚠️  Không tìm thấy log file"
    fi
}

print_help() {
    cat << 'EOF'
🚀 BMT Smart Upgrade Script - Help

Sử dụng:
  ./bmt-smart-upgrade.sh        # Nâng cấp bình thường (khuyến nghị)
  ./bmt-smart-upgrade.sh --dry-run  # Chế độ test (không có thay đổi thực sự)
  ./bmt-smart-upgrade.sh --help    # Hiển thị help này

Options:
  --dry-run    Hiển thị những gì sẽ xảy ra mà không thực sự thay đổi
  --help       Hiển thị help này

Features:
  ✅ Safe bot stopping (systemd + tmux)
  ✅ Code backup (tự động)
  ✅ Pull code mới từ repository
  🚀 Tự động restart bot
  📊 Hiển thị logs trực tiếp
  🔧 Trạng thái kiểm tra đầy đủ

Notes:
  - Script sẽ yêu cầu input (stash của changes, create tmux session)
  - Đảm bảo có quyền truy cập write trong repository git
  - Đảm bảo service file systemd có path chính xác

Exemples:
  # Normal upgrade (interactive)
  chmod +x bmt-smart-upgrade.sh
  ./bmt-smart-upgrade.sh

  # Quick upgrade (auto-yes)
  ./bmt-smart-upgrade.sh 2>&1 | tail -20

  # Test upgrade (dry-run)
  ./bmt-smart-upgrade.sh --dry-run

  # Quick upgrade without prompts
  echo 'y' | ./bmt-smart-upgrade.sh 2>&1 | tail -30

Auto-generated by BMT Trading Bot Team
EOF
}

# ==== MAIN EXECUTION ====

# Parse arguments
DRY_RUN=false
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            print_help
            exit 0
            ;;
        *)
            ;;
    esac
    shift
    set -- "$@"
    shift
    set -- "$@"

done

# In dry-run mode, thực hiện kiểm tra an toàn
if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}🔍 DRY RUN MODE - Không có thay đổi thực sự được thực hiện${NC}"
    
    print_header
    create_directories
    check_system_status
    echo -e "\n${YELLOW}❌ Dry run dừng tại đây - Không thực hiện thay đổi thực sự${NC}"
    exit 0
fi

# ==== EXECUTION ====

trap 'echo -e "\n${YELLOW}⚠️  Script đã bị interrupt - cleanup...${NC}"
systemctl is-active --quiet "$SERVICE_NAME" && systemctl stop "$SERVICE_NAME" &>/dev/null
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "🔧 Đang dừng tmux session..."
    tmux kill-session -t "$SESSION_NAME"
fi

echo -e "\n${YELLOW}Cleanup đã hoàn tất${NC}"\n' EXIT

print_header
log_message "🚀 BMT Upgrade bắt đầu"
create_directories

# Confirm operation
read -p -e "⚠️  Xác nhận nâng cấp BMT Trading Bot? (y/N): " -r confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️  Nâng cấp đã được hủy${NC}"
    exit 1
fi

# Thực hiện quy trình nâng cấp
if stop_bot_safely; then
    if backup_and_pull; then
        if start_bot_new; then
            check_bot_status
            log_message "🎉 Upgrade hoàn tất thành công!"
            echo -e "\n${GREEN}✨ Nâng cấp hoàn tất! Bot đã sẵn sàng${NC}"
        else
            echo -e "\n${RED}❌ Bắt đầu thất bại! Vui lòng kiểm tra logs${NC}"
            systemctl status "$SERVICE_NAME"
            exit 1
        fi
    else
        echo -e "\n${RED}❌ Pull code thất bại! Không thể nâng cấp${NC}"
        exit 1
    fi
else
    echo -e "\n${RED}❌ Dừng bot thất bại! Không thể nâng cấp${NC}"
    exit 1
fi

log_message "🎯 BMT Trading Bot đã sẵn sàng"
