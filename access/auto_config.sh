#!/bin/bash
# Trevor SANDY
# Last Update March, 01 2026
# Copyright (C) 2026 by Trevor SANDY
#
# Auto-configure, with user prompts, self-hosted AI-Suite with Caddy/Nginx proxy and
# Authelia 2FA identity and access management using auto-generated credentials.
#
# This script is executed on --operation update or install by suite_services.py
# when if AC=True in .env. It can also be run stand-alone.
#
# Portions of this code are derived from Inder Singh's setup.sh shell script.
# Copyright 2026 Inder Singh. Licensed under Apache License 2.0.
# Original source:
#    https://github.com/singh-inder/supabase-automated-self-host/raw/main/setup.sh

set -euo pipefail

VERSION="0.2.0"

# https://stackoverflow.com/a/28085062/18954618
: "${CI:=false}"
: "${APP_NAME:="AI-Suite"}"
: "${WITH_REDIS:=false}"
: "${SUDO_USER:="$(whoami)"}"
: "${DEBUG_ON:=false}"
: "${BACKUP:=1}"
: "${SILENT:=$([[ "$CI" == true ]] && echo 1 || echo 0)}"
: "${DRY_RUN:=$([[ "$DEBUG_ON" == true ]] && echo 1 || echo 0)}"
: "${INTERNAL_ELEVATED:=0}"

# Reset BASH time counter
SECONDS=0

# Colors
SGR=''
END=''
# Core SGR support detection
if [[ "$SILENT" == 0 && -t 1 ]]; then
    if colors=$(tput colors 2>/dev/null) && [[ "$colors" -ge 8 ]]; then
        SGR='\033['
        END="${SGR}0m"
    fi
fi
# Primitive style flags
BOLD=''
DIM=''
ITALIC=''
UNDERLINE=''
# Base colors
RED=''
GREEN=''
YELLOW=''
BLUE=''
MAGENTA=''
CYAN=''
WHITE=''
# Composite tokens
DIM_CYAN=''
BOLD_MAGENTA=''
ITALIC_RED_BG=''
UNDERLINE_YELLOW=''
# Semantic tokens
HEADER=''
BODY='  - '
COLON=':'
APP="${APP_NAME}${COLON}"
QUESTION="${APP} QUESTION"
ERROR="${APP} ERROR"
INFO="${APP} INFO"

# Apply SGR layer once
if [[ -n "$SGR" ]]; then
    BOLD='1;'
    DIM='2;'
    ITALIC='3;'
    UNDERLINE='4;'

    RED="${SGR}31m"
    GREEN="${SGR}32m"
    # shellcheck disable=SC2034
    YELLOW="${SGR}33m"
    BLUE="${SGR}34m"
    MAGENTA="${SGR}35m"
    CYAN="${SGR}36m"
    WHITE="${SGR}37m"

    DIM_CYAN="${SGR}${DIM}36m"
    BOLD_MAGENTA="${SGR}${BOLD}95m"
    ITALIC_RED_BG="${SGR}${ITALIC}41m"
    UNDERLINE_YELLOW="${SGR}${UNDERLINE}93m"

    HEADER="${SGR}${BOLD}${UNDERLINE}92m"
    BODY="${SGR}37m  -${END} ${SGR}32m"

    COLON="${SGR}97m:${END}"
    APP="${SGR}3;94m${APP_NAME}${COLON}${END}"
fi

# Log level names
declare -A LOG_LEVEL_NAME=(
    [NOTICE]='NOTICE'
    [QUESTION]='QUESTION'
    [CRITICAL]='CRITICAL'
    [ERROR]='ERROR'
    [WARNING]='WARNING'
    [DEBUG]='DEBUG'
    [INFO]='INFO'
)

# Log level styles
declare -A LOG_LEVEL_STYLE=(
    [NOTICE]="${SGR}${BOLD}95m"     # MAGENTA
    [QUESTION]="${SGR}${BOLD}92m"   # GREEN
    [CRITICAL]="${SGR}${BOLD}41m"   # RED_BG
    [ERROR]="${SGR}${BOLD}91m"      # RED
    [WARNING]="${SGR}${BOLD}${UNDERLINE}93m" # YELLOW
    [DEBUG]="${SGR}${BOLD}97m"      # WHITE
    [INFO]="${SGR}36m"              # CYAN
)

# Log message styles
declare -A LOG_MESSAGE_STYLE=(
    [NOTICE]="$BOLD_MAGENTA"
    [QUESTION]="$GREEN"
    [CRITICAL]="$ITALIC_RED_BG"
    [ERROR]="$RED"
    [WARNING]="$UNDERLINE_YELLOW"
    [DEBUG]="$WHITE"
    [INFO]="$DIM_CYAN"
)

# Prefix cache (precomputed for speed)
log_header_prefix() {
    local -n header_prefix_ref=$1
    local level=$2
    local prefix
    if [[ -n "$SGR" ]]; then
        prefix="${APP} ${LOG_LEVEL_STYLE[$level]}${LOG_LEVEL_NAME[$level]}${END}"
    else
        prefix="${APP} ${LOG_LEVEL_NAME[$level]}"
    fi
    # shellcheck disable=SC2034
    header_prefix_ref=$prefix
}

declare -A LOG_HEADER_PREFIX

for level in "${!LOG_LEVEL_NAME[@]}"; do
    log_header_prefix LOG_HEADER_PREFIX["$level"] "$level"
done

LOG_TIMESTAMP="${LOG_TIMESTAMP:-false}"

# Injection-aware logger
log() {
    local level="$1"; shift
    [[ "$level" == DEBUG && "$DEBUG_ON" != true ]] && return

    local header="${LOG_HEADER_PREFIX[$level]}"
    local message="${LOG_MESSAGE_STYLE[$level]}"

    if [[ -n "$SGR" && "$*" == "$SGR"* ]]; then
        message="${END}$*"
    else
        message="${message}$*"
    fi

    if [[ "$LOG_TIMESTAMP" == true ]]; then
        header="$(date '+%Y-%m-%d %H:%M:%S') $header"
    fi

    if [[ "$level" == CRITICAL || "$level" == ERROR ]]; then
        printf '%b %b%b\n' "$header" "$message" "$END" >&2
    else
        printf '%b %b%b\n' "$header" "$message" "$END"
    fi
}

# Semantic tokens
log_header_prefix QUESTION 'QUESTION'
log_header_prefix ERROR 'ERROR'
log_header_prefix INFO 'INFO'

# Wrappers
log_notice()   { log NOTICE "$*"; }
log_critical() { log CRITICAL "$*"; }
log_error()    { log ERROR "$*"; }
log_warning()  { log WARNING "$*"; }
log_debug()    { log DEBUG "$*"; }
log_info()     { log INFO "$*"; }

critical_exit() {
    log_critical "$*"
    exit 1
}

# Real-time tee with SGR stripping
SCRIPT="${BASH_SOURCE[0]##*/}"
if [[ "$SCRIPT" == "${0##*/}" ]]; then
    AC_LOG_PATH="${AC_LOG_PATH:-$(pwd)}"
    LOG="$AC_LOG_PATH/$SCRIPT.log"
    [[ -f "$LOG" && -r "$LOG" ]] && rm "$LOG"
    # Strip SGR color sequence codes from output"
    exec > >(tee >(sed 's/\x1b\[[0-79;]\{1,11\}m//g' >> "$LOG"))
    exec 2> >(tee >(sed 's/\x1b\[[0-79;]\{1,11\}m//g' >> "$LOG") >&2)
    # - The sed regex explained:
    # sed             application binary
    # '               open single quote
    # s               substitution flag
    # /               delimeter '/'
    # \x1b            match the SGR escape sequence '\x1b' before the color or attribute code
    # \[              matches the first open bracket - escape '\[' to distinguish from regex [
    # [0-79;]\{1,11\} matches '1 to 11' of any character in '012345679;' - escape the curly braces
    #                 with '\{' to keep the shell from mangling them
    #                 we have 11 times due to bold, dim, italic, underline and color * 2 plus reset * 1
    # m               match the SGR escape sequence reset character 'm' - this trails the color code
    # //              empty string between delimeters '/' to replace everything with
    # g               match globally - i.e., multiple times per line
    # '               close single quote
    # "$LOG"          the log file: auto_config.sh.log
fi

# Capture elapsed execution time
# shellcheck disable=SC2329
finish_elapsed_time() {
    set +x
    local ELAPSED
    ELAPSED="$((SECONDS / 3600))hrs $(((SECONDS / 60) % 60))min $((SECONDS % 60))sec"
    echo -e "${INFO} ${CYAN}Elapsed time:${END} ${GREEN}$ELAPSED${END}"
    echo -e "${INFO} ${GREEN}-------------------------------------------${END}"
}

# shellcheck disable=SC2329
finish () {
    local vars=(AC_SUDO_PASSWORD AC_PASSWORD password confirm_password)
    local var
    for var in "${vars[@]}"; do [ -v "$var" ] && unset "$var" ; done

    local header="${END}✅ ${HEADER}"
    local status="Completed"

    if [ "$completion" == "Success!" ]; then
        :
    elif [ "$completion" == "Partial!" ]; then
        header="${END}⚠️ ${HEADER}"
        status="Finished"
    else
        header="${END}❌ ${SGR}${UNDERLINE}91m"
        status="Terminated"
    fi

    if [ "$status" == "Completed" ]; then
        local bin binaries=()
        for bin in "$yq_bin" "$url_parser_bin"; do [ -f "$bin" ] && binaries+=("$bin") ; done
        if (( ${#binaries[@]} > 0 )); then log_info "Clean downloaded binaries..." ; fi
        for bin in "${binaries[@]}"; do log_info "  ✘ $(basename "${bin}")"; (rm "$bin"); done
    fi

    log_info "${header}Configuration $status"
    #-------------------------------------------
    finish_elapsed_time
}

trap finish EXIT

# Process arguments
usage() {
    cat <<EOF
$0 v$VERSION

Usage: [ENVIRONMENT] $0 [OPTIONS]

Auto-configure, with user prompts, self-hosted $APP_NAME with Caddy/Nginx proxy and
Authelia 2FA identity and access management using auto-generated credentials.

Environment:
  CI:bool         Non-interactive mode - e.g running a GitHub build test, default: $CI
  APP_NAME:str    The application name in $0 - default: $APP_NAME
  SUDO_USER:str   Non-root user - brew does not allow installation as root, default: $SUDO_USER
  WITH_REDIS:bool Set Authelia to use Redis - optional if --with-authelia, default: $WITH_REDIS
  DEBUG_ON:bool   Turn on debug mode, log_debug statements enabled - default: $DEBUG_ON
  DRY_RUN:int     Simulate adding domains to hosts file - 1 when DEBUG_ON=true, default: $DRY_RUN
  SILENT:int      No prompt for elevated privilage - 1 when CI=true, default: $SILENT
  BACKUP:int      Backup hosts file before update - default: $BACKUP

  Auto-configure environment variables:
  AC:false               Auto-configure mode - expects required inputs from 'env' variables
  AC_SUDO_PASSWORD:str   SUDO user password - optional, user prompt if not set and not elevated
  AC_SUDO_USER:str       Non-root SUDO user - brew does not allow installation as root user
  AC_DOMAIN:str          Domain (optional) - Required for global (public) configuration
  AC_LOCAL:false         Local (private) installation - 1. requires additional configuration
  AC_PROXY:caddy         Set the reverse proxy to use (Caddy or Nginx)
  AC_USERNAME:str        User name for PROXY configuration - only alphanumeric characters allowed
  AC_PASSWORD:str        User password for PROXY configuration
  AC_CONFIRM:false       Send confirmation email on user registration - 2. SMTP server required
  AC_WITH_AUTHELIA:false Enable Authelia 2FA (two factor authentication) support
  AC_EMAIL:str           User email address for Authelia - required if AC_WITH_AUTHELIA=true
  AC_DISPLAY_NAME:str    User display name for Authelia - 3. required if AC_WITH_AUTHELIA=true
  AC_WITH_REDIS:false    Use Redis with Authelia - 4. recommended if AC_WITH_AUTHELIA=true
  AC_SUBDOMAINS:str      Subdomain(s) to create domain name(s) - 5. all subdomains used if not set
  AC_LOG_PATH:str        Directory path where configuration runtime log is deposited

  AC_SEARXNG:false  Configure proxy for SearXNG domain name
  AC_LLAMA:false    Configure proxy for LLAMA (LLaMA.cpp/Ollama) domain name
  AC_LLAMACPP:false Using LLaMA.cpp LLM (instead of Ollama)

  1. Automatically adds your local domain name(s) to the hosts file to loop back to your
     machine like localhost - for example: 127.0.0.1   open-webui.local.pc.
  2. If not using an SMTP server, enter any well formatted email address.
     You can view codes sent by Authelia in ./authelia/notifications.txt.
  3. Only alphanumeric charactes and spaces are allowed.
  4. Used if AC_WITH_AUTHELIA=true. Recommended if global (public) install, otherwise optional
  5. Subdomains (external Docker containers):
     - open-webui
     - n8n
     - supabase
     - flowise
     - langfuse
     - searxng
     - neo4j
     - llamacpp or ollama - only one LLM at a tume can be configured

Options:
  -h, --help         Show this help message and exit
  --proxy PROXY      Set the reverse proxy to use (Caddy or Nginx) - default: Caddy
  --with-authelia    Enable or disable Authelia 2FA support - default: false (disable)
  --subdomain <name> Subdomain(s) to create domain name(s) - all used if not set
  --version          Display this script version: v$VERSION
  --help             Display this information

Examples:
  chmod +x $0                          # Make $0 executable
  $0                                   # Basic username and password authentication
  $0 --proxy nginx --with-authelia     # Configuration with Nginx and Authelia 2FA
  $0 --proxy caddy                     # Configuration with Caddy and no 2FA
  env <AC_VAR> <AC_VAR> <AC_VAR>... $0 # Auto-configure mode using environment variables

For more information on , see README.md:
https://github.com/trevorsandy/ai-suite/blob/Dev/README.md
EOF
}

bash_version_at_or_above_4_4() {
    [[ -z $BASH_VERSION ]] && return 1
    local required_ver="4.4"
    if [ "$(printf '%s\n' "$required_ver" "$BASH_VERSION" | sort -V | head -n1)" = "$required_ver" ]; then
       return
    fi
    return 1
}

has_argument() {
    [[ ("$1" == *=* && -n ${1#*=}) || (-n "$2" && "$2" != -*) ]]
}

extract_argument() { echo "${2:-${1#*=}}"; }

update_subdomains() {
    local sub_domain
    local sub_domains=()
    log_debug "update_subdomains - @ (${#@}): ${*}"
    for sub_domain in "$@"; do
        IFS=' ' read -r -a sub_domains <<< "$sub_domain"
    done
    for sub_domain in "${sub_domains[@]}"; do
        local exists=false
        local subdomain
        for subdomain in "${subdomains[@]}"; do
            [[ "$sub_domain" == "$subdomain" ]] && { exists=true; break; }
        done
        [[ "$exists" == false ]] && \
        subdomains+=("$sub_domain")
    done
    log_debug "update - subdomains (${#subdomains[@]}): ${subdomains[*]}"
}

completion=''
subdomains=()
ac_install_type=''
ac_user_confirm=''
with_authelia=false
using_sudo_user=false
proxy="caddy"
url_parser_bin="./access/url-parser"
yq_bin="./access/yq"

ORIGINAL_ARGS=("$@")
PLATFORM="unknown"
HOSTS_PATH="/etc/hosts"

# https://medium.com/@wujido20/handling-flags-in-bash-scripts-4b06b4d0ed04
while [ $# -gt 0 ]; do
    case "$1" in
    -h | --help)
        usage
        exit 0
        ;;
    --version)
        echo -e "${INFO} ${CYAN}Version:${END} ${WHITE}$VERSION${END}"
        exit 0
        ;;
    --with-authelia)
        with_authelia=true
        ;;
    --proxy)
        if has_argument "$@"; then
            proxy="$(extract_argument "$@")"
            shift
        fi
        ;;
    --subdomains)
        shift
        [[ $# -eq 0 ]] && critical_exit "--subdomains option require at least one arguement."
        update_subdomains "$1"
        ;;
    --internal-elevated)
        INTERNAL_ELEVATED=1
        ;;
    *)
        echo -e "${ERROR} ${RED}Invalid option:${END} ${WHITE}$1${END}" >&2
        usage
        exit 1
        ;;
    esac
    shift
done

if ! bash_version_at_or_above_4_4; then
    critical_exit "Bash version 4.4 and above is required. Current version is $BASH_VERSION."
fi

if [[ "$proxy" != "caddy" && "$proxy" != "nginx" ]]; then
    critical_exit "Only caddy or nginx proxy supported - received $proxy"
fi

: "${AC:=false}"
: "${AC_SUDO_PASSWORD:=}"
: "${AC_SUDO_USER:="$SUDO_USER"}"
: "${AC_DOMAIN:=}"
: "${AC_LOCAL:=false}"
: "${AC_PROXY:="$proxy"}"
: "${AC_USERNAME:=}"
: "${AC_PASSWORD:=}"
: "${AC_CONFIRM:=false}"
: "${AC_WITH_AUTHELIA:="$with_authelia"}"
: "${AC_EMAIL:=}"
: "${AC_DISPLAY_NAME:=}"
: "${AC_WITH_REDIS:="$WITH_REDIS"}"
: "${AC_SUBDOMAINS:=}"
: "${AC_LOG_PATH:=}"
: "${AC_SEARXNG:=false}"
: "${AC_LLAMA:=false}"
: "${AC_LLAMACPP:=false}"

if [ "$AC" == true ]; then
    SUDO_USER="${AC_SUDO_USER}"
    with_authelia="${AC_WITH_AUTHELIA}"
    WITH_REDIS="${AC_WITH_REDIS}"
    proxy="${AC_PROXY}"
    update_subdomains "${AC_SUBDOMAINS[@]}"
    if [ "$AC_CONFIRM" == true ]; then
        ac_user_confirm="Email notification"
    else
        ac_user_confirm="Default"
    fi
    ac_config_mode="Auto-configuration"
    if [ "$AC_LOCAL" == true ]; then
        ac_install_type="Private (Local)"
    else
        ac_install_type="Public (Global)"
    fi
    log_info "${HEADER}Auto-configure Environment Variables"
    #-------------------------------------------
    log_info "${BODY}AC:${END} ${WHITE}true"
    while IFS= read -r var; do
        [[ $var == AC_* ]] || continue
        declare -n _ref="$var"
        ref=$_ref
        [[ $var == AC_*ASSWORD ]] && ref='***'
        log_info "${BODY}$var:${END} ${WHITE}$ref"
    done < <(compgen -A variable)
elif [ "$CI" == true ]; then
    ac_config_mode="Continuous integration"
else
    ac_config_mode="Interactive"
fi

# Set all subdomains if no subdomain specified
if (( ${#subdomains[@]} == 0 )); then
    subdomains+=(open-webui n8n supabase flowise langfuse searxng neo4j llamacpp ollama)
fi

log_debug "subdomains (${#subdomains[@]}): ${subdomains[*]}"

log_info "${HEADER}Configuration Summary"
#-------------------------------------------
log_info "${BODY}Proxy:${END} ${WHITE}${proxy}"
log_info "${BODY}Authelia 2FA:${END} ${WHITE}${with_authelia}"
log_info "${BODY}Redis:${END} ${WHITE}${WITH_REDIS}"
log_info "${BODY}Setup Mode:${END} ${WHITE}${ac_config_mode}"
[ -n "${ac_install_type}" ] && \
log_info "${BODY}Installation:${END} ${WHITE}${ac_install_type}" || :
[ -n "${ac_user_confirm}" ] && \
log_info "${BODY}User Confirmation:${END} ${WHITE}${ac_user_confirm}" || :
[ "${DEBUG_ON}" == true ] && log_debug "Enabled"

detect_arch() {
    local -n _ref=$1
    case $(uname -m) in
    x86_64) _ref='amd64' ;;
    aarch64 | arm64) _ref='arm64' ;;
    armv7l) _ref='arm' ;;
    i686 | i386) _ref='386' ;;
    *) _ref='err' ;;
    esac
}

#https://stackoverflow.com/a/18434831/18954618
detect_os() {
    local -n _ref=$1
    case $(uname | tr '[:upper:]' '[:lower:]') in
    linux*) _ref='linux' ;;
    # darwin*) _ref='darwin' ;;
    *) _ref='err' ;;
    esac
}

is_wsl() {
    case "$(uname -r)" in
    *icrosoft*WSL2 | *icrosoft*wsl2) return ;;
    *icrosoft) critical_exit "Microsoft WSL1 is not supported. Use WSL2 with 'wsl --set-version <distro> 2'" ;;
    *) return 1 ;;
    esac
}

arch=''
detect_arch arch
os=''
detect_os os

case "$os" in
linux*)
    if is_wsl; then
        HOSTS_PATH="/mnt/c/Windows/System32/drivers/etc/hosts"
        PLATFORM="wsl"
    else
        PLATFORM="linux"
    fi
    ;;
darwin*) PLATFORM="mac" ;;
err) critical_exit "Unsupported platform." ;;
esac

log_debug "PLATFORM: $PLATFORM"
log_debug "BASH_VERSION: $BASH_VERSION"
log_debug "HOSTS_PATH: $HOSTS_PATH"

if [[ "$arch" == "err" ]]; then critical_exit "Unsupported CPU architecture"; fi

is_unix_root() { if [ -n "$1" ]; then return "$(id -u "$1")"; else return "$(id -u)"; fi }

is_windows_admin() {
    local -n _ref=$1
    local var
    IFS= read -r var < <(
        powershell.exe -NoProfile -Command \
        "[int]([Security.Principal.WindowsPrincipal] \
        [Security.Principal.WindowsIdentity]::GetCurrent() \
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"
    )
    var=${var%$'\r'}
    if [[ $var -eq 1 ]]; then
        _ref=true
        return 0
    else
        _ref=false
        return 1
    fi
}

available() { command -v "$1" >/dev/null; }
packages=(curl wget jq openssl git)
if available apt-get; then
    packages+=("apt-get:apache2-utils")
elif available apk; then
    packages+=("apk:apache2-utils")
elif available dnf; then
    packages+=("dnf:httpd-tools")
elif available zypper; then
    packages+=("zypper:apache2-utils")
elif available pacman; then
    packages+=("apt-get:apache")
elif available pkg; then
    packages+=("pkg:apachew24")
elif available brew; then
    # brew does not allow installation as root so run install as target SUDO user with SUDO privileges
    if test -n "$SUDO_USER"; then
        if is_unix_root "$SUDO_USER"; then
            log_error "Current user ($(whoami)) and SUDO_USER ($SUDO_USER) is root!"
            critical_exit "Homebrew cannot run package install as ($SUDO_USER)!"
        fi
        using_sudo_user=true
    else
        critical_exit "Homebrew cannot run package install as ($(whoami))!"
    fi
    packages+=("brew:httpd")
else
    critical_exit "Package manager apt, apk, dnf, zypper, pacman, pkg, or brew not found."
fi

package_is_installed() {
    local i=1 # set i to 0 if package not found
    local package="$1"
    case "${package_manager}" in
    apt-get) dpkg -s apache2-utils > /dev/null 2>&1 || { local i=0; } ;;
    apk) apk info -e apache2-utils > /dev/null 2>&1 || { local i=0; } ;;
    dnf) dnf list installed httpd-tools &> /dev/null || { local i=0; } ;;
    zypper) rpm -q apache2-utils > /dev/null 2>&1 || { local i=0; } ;;
    pacman) pacman -Qi apache > /dev/null 2>&1 || { local i=0; } ;;
    pkg) pkg info apache24 > /dev/null 2>&1 || { local i=0; } ;;
    brew) brew list --formula | grep -qx httpd || { local i=0; } ;;
    *) type "${package}" > /dev/null 2>&1 || { local i=0; } ;;
    esac
    if [ "$i" == 1 ]; then
        log_info "${GREEN}  ✔${END} ${WHITE}${package}"
    else
        log_info "${RED}  ✘${END} ${WHITE}${package}"
    fi
    return $i
}

format_prompt() {
    local -n _ref=$1
    local user=$2
    local BOLD_CYAN="${SGR}${BOLD}36m"
    local prompt="${INFO} ${WHITE}Supply${END} ${BOLD_CYAN}$user${END} ${WHITE}password for command:${END}"
    [[ "$user" == "su" ]] && user="su -c"
    _ref='%b %b%b%b' "$prompt" "${BLUE}" "$user" "${END}"
}

sudo_prompt() {
    # https://superuser.com/questions/553932
    if [ -n "${AC_SUDO_PASSWORD}" ]; then
        (sudo -S -v <<<"${AC_SUDO_PASSWORD}" > /dev/null 2>&1)
    else
        local prompt
        format_prompt prompt 'sudo'
        printf '%b %b%b%b\n' "$prompt" "${WHITE}" "$1" "${END}"
    fi
}

unix_privilage() {
    local -n _ref=$1
    local current
	local privilage
    if is_unix_root; then
        privilage='is_unix__root'
    elif current=$(sudo -nv 2>&1); then
        privilage='has_sudo__pass_set'
    elif echo "$current" | grep -q '^sudo:'; then
        privilage='has_sudo__needs_pass'
    elif command -v su >/dev/null 2>&1; then
        privilage='has_su__needs_pass'
    else
        privilage='none'
    fi

    _ref="$privilage"

    case "$privilage" in
    has_sudo__pass_set)
        sudo bash "$0" --internal-elevated "${ORIGINAL_ARGS[@]}"
        ;;
    has_sudo__needs_pass)
        [[ "$SILENT" -eq 1 ]] && critical_exit "Silent mode requires passwordless sudo."
        sudo_prompt '--internal-elevated'
        sudo bash "$0" --internal-elevated "${ORIGINAL_ARGS[@]}"
        ;;
    has_su__needs_pass)
        [[ "$SILENT" -eq 1 ]] && critical_exit "Silent mode cannot use su."
        local prompt
        local cmd="bash $0 --internal-elevated ${ORIGINAL_ARGS[*]}"
        format_prompt prompt 'su'
        echo -e "$prompt ${WHITE}$cmd${END}"
        su -c "$cmd"
        ;;
    none)
        critical_exit "No privilege escalation available."
        ;;
    esac
}

run_pkg_cmd() {
    local cmd=$*

    if [[ "$INTERNAL_ELEVATED" -eq 1 ]]; then
        $cmd
        return
    fi

    local user_privilage
    unix_privilage user_privilage

    if [[ "$user_privilage" == "is_unix_root" ]]; then
        $cmd
    fi
}

install_packages() {
    case "${package_manager}" in
    apt-get)
        run_pkg_cmd apt-get update
        run_pkg_cmd export DEBIAN_FRONTEND="noninteractive" apt-get install -y "${packages[@]}"
        ;;
    apk)
        run_pkg_cmd apk update
        run_pkg_cmd add --no-cache "${packages[@]}"
        ;;
    dnf)
        run_pkg_cmd dnf makecache
        run_pkg_cmd dnf install -y "${packages[@]}"
        ;;
    zypper)
        run_pkg_cmd zypper refresh
        run_pkg_cmd zypper install "${packages[@]}"
        ;;
    pacman)
        run_pkg_cmd pacman -Syu --noconfirm "${packages[@]}"
        ;;
    pkg)
        run_pkg_cmd pkg update
        run_pkg_cmd pkg install -y "${packages[@]}"
        ;;
    brew)
        run_pkg_cmd -u "$SUDO_USER" brew install "${packages[@]}"
        using_sudo_user=true
        ;;
    *)
        critical_exit "Install packages failed! Package manager not found."
        ;;
    esac
}

log_info "${HEADER}Required Packages"
#-------------------------------------------
if available docker; then
    log_info "${GREEN}  ✔${END} ${WHITE}Docker"
else
    log_info "${RED}  ✘${END} ${WHITE}Docker"
fi

package_manager=''
missing_packages=()
for package in "${packages[@]}"; do
    pkg_pair=()
    package_manager=''
    IFS=':' read -r -a pkg_pair <<< "$package"
    if (( ${#pkg_pair[@]} > 1 )); then
        package="${pkg_pair[1]}"
        package_manager="${pkg_pair[0]}"
    fi
    if package_is_installed "$package" == 0; then
        missing_packages+=("$package")
    fi
done

log_info "${HEADER}Package Manager"
#-------------------------------------------
log_info "${GREEN}  ✔${END} ${BLUE}${package_manager}"

packages=("${missing_packages[@]}")
unset missing_packages
if (( ${#packages[@]} != 0 )); then
    # https://unix.stackexchange.com/a/571192/642181
    if install_packages; then
        log_info "${HEADER}Installed Packages"
        #-------------------------------------------
        for i in "${packages[@]}"; do
            package_is_installed "$i"
        done
    else
        critical_exit "Failed to install required packages."
    fi
fi

repo_base="https://github.com/trevorsandy"
repo_url="${repo_base}/ai-suite"
if [ "$AC" == true ]; then
    directory="$(pwd)"
else
    directory="$(basename "$repo_url")"
fi

if [[ "$AC" == true && -d "$directory" ]]; then
    log_info "Working directory: $directory"
elif [ -d "$directory" ]; then
    log_info "$directory directory present, skipping git clone"
else
    git clone --depth=1 "$repo_url" "$directory"
fi

if [ "$AC" == true ]; then
    if ! cd "$directory"; then critical_exit "Unable to access working directory."; fi
else
    if ! cd "$directory"/docker; then critical_exit "Unable to access $directory/docker directory."; fi
fi
if [ ! -f ".env.example" ]; then critical_exit ".env.example file not found. Exiting!"; fi

log_info "${HEADER}Downloaded Binaries"
#-------------------------------------------
download_binary() { wget "$1" -O "$2" &>/dev/null && chmod +x "$2" &>/dev/null; }
repo_base="https://github.com/singh-inder"

if [ ! -x "$url_parser_bin" ]; then
    log_info "Downloading url-parser from ${repo_base}/url-parser..."
    download_binary "${repo_base}"/url-parser/releases/download/v1.1.0/url-parser-"$os"-"$arch" "$url_parser_bin"
fi

if [ ! -x "$yq_bin" ]; then
    log_info "Downloading yq from https://github.com/mikefarah/yq..."
    download_binary https://github.com/mikefarah/yq/releases/download/v4.45.4/yq_"$os"_"$arch" "$yq_bin"
fi

bin_status () { if test -x "$1"; then echo "${GREEN}  ✔"; else echo "${RED}  ✘"; fi }
log_info "$(bin_status "$url_parser_bin")${END} ${WHITE}url_parser"
log_info "$(bin_status "$yq_bin") ${WHITE}yq"

format_prompt() { echo -e "${QUESTION} ${GREEN}$1${END}"; }

confirmation_prompt() {
    local -n _ref="$1"
    local answer=""
    read -rp "$(format_prompt "$2")" answer

    # converts input to lowercase
    case "${answer,,}" in
    y | yes)
        answer=true
        ;;
    n | no)
        answer=false
        ;;
    *)
        log_error "Please answer yes or no"
        answer=""
        ;;
    esac

    [[ -n "$answer" ]] && _ref="$answer"
}

elide() {
    echo "$@" | \
    awk -v max=35 '{ if (length($0) > max) print substr($0, 1, max-3) "..."; else print; }'
}

# Populate module hostname (URL)
log_info "${HEADER}Populate Domain Names"
#-------------------------------------------
DOMAINS=()
domain_var() {
    local -n _ref=$1
    local sub=$2
    local base=${sub/open-webui/WEBUI}
    base=${base//-/_}
    _ref="${base^^}_DOMAIN"
}

unset_domain_vars() {
    local sub var
    for sub in "${subdomains[@]}"; do
        domain_var var "$sub"
        declare -p "$var" &>/dev/null || continue
        unset "$var"
        log_debug "Unset domain variable: $var"
    done
}

construct_domain_vars() {
    local sub=$1
    local d var val
    domain_var var "$sub"
    val="${sub}.${registered_domain}"

    local add_domain=true
    for d in "${DOMAINS[@]}"; do \
        [[ "$val" == "$d" ]] && { add_domain=false; break; }
    done
    [[ "$add_domain" == true ]] && DOMAINS+=("$val")
    
	local -n _ref="$var"
    _ref="$val"

    log_debug " ${WHITE}-${END} ${YELLOW}$var:${END} ${WHITE}$_ref"
    export _ref
}

export_domain_envs() {
    local sub var env array
    array=("${subdomains[@]}")
    array+=(llama)
    for sub in "${array[@]}"; do
        domain_var var "$sub"
        declare -p "$var" &>/dev/null || continue
        local -n ref="$var"
        env=${var,,}
        export "$env=$ref"
    done
}

get_domain_var() {
    local -n _ref=$1
    local arg=$2
    local i sub val
    for (( i=0; i<${#subdomains[@]}; i++ )); do
        (( i >= ${#DOMAINS[@]} )) && continue
        sub="${subdomains[$i]}"
        val="${DOMAINS[$i]}"
        [[ "$arg" == "$sub" ]] && {\
        _ref="$val"; \
        return; }
    done
}
# url_parser --url argument and options:
# --url: URL to parse. (e.g., https://subdomain.example.com:1234/path/resource?user=123#section1)
# host: Host with port number if present (e.g., subdomain.example.com:1234)
# hostWithoutPort: Host without port number (eg., subdomain.example.com)
# scheme: URL scheme/protocol (e.g., https)
# subdomain: Subdomain (e.g., subdomain)
# domain: Domain name (e.g., example)
# tld: Top-level domain (e.g., com)
# port: Port (if specified, e.g., 8080)
# path: URL path (e.g., /path/resource)
# fragment: URL Fragment (e.g., section1)
# registeredDomain: Registered domain from host (e.g., example.com)
# query.<parameter>: The value of the user query parameter (e.g., query.user: 123).
set_domain_names() {
    local subdomain="${1:-}"
    local url=""
    local attempts=0
    local max_attempts=5
    local _protocol="https"
    local _host=""
    local _registered_domain=""
    local _subdomain="$subdomain"

    unset_domain_vars

    : "${url_parser_bin:?url_parser_bin is not set}"
    ! declare -p subdomains 2>/dev/null | grep -q 'declare \-a' && \
        critical_exit "The subdomains variable must be a declared array"
    (( ${#subdomains[@]} > 0 )) || \
        critical_exit "The subdomains array is empty"

    while [ -z "$url" ]; do
        ((++attempts))
        [[ -z "$_subdomain" ]] && _subdomain="${subdomains[0]}"
        if [[ "$CI" == true ]]; then
            url="${_protocol}://${_subdomain}.example.com"
        elif [[ "$AC" == true ]]; then
            url="${_protocol}://${_subdomain}.${AC_DOMAIN:-local.pc}"
        else
            read -r -p "$(format_prompt "Enter your domain URL:") " url
            if ! _protocol="$("$url_parser_bin" --url "$url" --get scheme 2>/dev/null)"; then
                log_error "Could not extract protocol from hostname URL: $url."
                url="" && _protocol=""
            fi
        fi

        if ! _host="$("$url_parser_bin" --url "$url" --get host 2>/dev/null)"; then
            log_error "Could not extract host from hostname URL: $url."
            url="" && _host=""
        fi
        if ! _registered_domain="$("$url_parser_bin" --url "$url" --get registeredDomain 2>/dev/null)"; then
            _registered_domain=""
        fi
        [[ "$_registered_domain" == "." ]] && _registered_domain=""
        if [ -z "$_registered_domain" ]; then
            log_error "Parser failed to extract the registered domain from $url."
            url=""
        fi
        case "$_protocol" in
        https) ;;
        http)
            if [[ "$with_authelia" == true ]]; then
                log_error "Using --with-authelia requires https URL protocol."
                url="" && _protocol=""
            fi
            ;;
        *)
            log_error "Domain URL protocol must be http or https."
            url=""
            ;;
        esac
        if (( attempts == max_attempts )); then
            log_warning "Maximum URL parse attempts ($max_attempts) reached."
            break
        fi
        [[ -z "$url" && "$AC" != true ]] && continue
    done

    if [[ -n "$url" ]]; then
        [[ -n "$_protocol" ]] && protocol="$_protocol"
        [[ -n "$_host" ]] && host="$_host"
        [[ -n "$_registered_domain" ]] && registered_domain="$_registered_domain"
    else
        critical_exit "Failed to set domain attributes for URL."
    fi

    if [[ -n "$subdomain" ]]; then
        construct_domain_vars "$subdomain"
    else
        local sub
        for sub in "${subdomains[@]}"; do
            construct_domain_vars "$sub"
        done
    fi
}

# If 'subdomain' argument is empty, all AI Suite domains will be populated.
set_domain_names ""

log_info "${BODY}Confirm subdomains converted to domain names"

validate_domain_vars() {
    local i sub var val
    for (( i=0; i<${#subdomains[@]}; i++ )); do
        sub="${subdomains[$i]}"
        domain_var var "$sub"
        if declare -p "$var" &>/dev/null; then
            val="${DOMAINS[$i]}"
            log_notice "${WHITE}-${END} ${MAGENTA}${var}:${END} ${CYAN}${val}"
        else
            log_notice "${WHITE}-${END} ${YELLOW}${var}${END} ${WHITE}is not declared"
        fi
    done
}

validate_domain_vars

log_info "${BODY}protocol:${END} ${WHITE}$protocol"
log_info "${BODY}host (${APP_NAME}):${END} ${WHITE}$host"
log_info "${BODY}registered_domain:${END} ${WHITE}$registered_domain"

SUPABASE_domain='localhost'
declare -p SUPABASE_DOMAIN &>/dev/null && \
SUPABASE_domain=$SUPABASE_DOMAIN

log_info "${BODY}SUPABASE_PUBLIC_URL:${END} ${WHITE}$protocol://$SUPABASE_domain"
declare -p N8N_DOMAIN &>/dev/null && \
log_info "${BODY}N8N WEBHOOK_URL:${END} ${WHITE}$protocol://$N8N_DOMAIN"

LLAMA_DOMAIN='undefined'
if [[ "$AC_LLAMACPP" == true ]]; then
    get_domain_var LLAMA_DOMAIN 'llamacpp'
else
    get_domain_var LLAMA_DOMAIN 'ollama'
fi
log_info "${BODY}LLAMA_DOMAIN:${END} ${WHITE}$LLAMA_DOMAIN"

credentials="Set Credentials"
[[ "$CI" != true && "$AC" != true ]] && \
credentials="Capture And $credentials" || :
log_info "${HEADER}$credentials"
#-------------------------------------------

log_info "${BODY}Username"
username=""
if [[ "$CI" == true ]]; then username="inder"; \
elif [[ "$AC" == true ]]; then username="$AC_USERNAME"; fi

while [ -z "$username" ]; do
    read -rp "$(format_prompt "Enter username:") " username
    # https://stackoverflow.com/questions/18041761
    if [[ ! "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
        log_warning "Only alphanumeric characters are allowed. Your rsponse: $username"
        username=""
    fi
    # read command automatically trims leading & trailing whitespace. No need to handle it separately
done

log_info "${BODY}User password"
password=""
confirm_password=""
if [[ "$CI" == true ]]; then
    password="password"
    confirm_password="password"
elif [[ "$AC" == true ]]; then
    password="$AC_PASSWORD"
    confirm_password="$AC_PASSWORD"
fi

while [[ -z "$password" || "$password" != "$confirm_password" ]]; do
    read -s -rp "$(format_prompt "Enter password(password is hidden):") " password
    echo
    read -s -rp "$(format_prompt "Confirm password:") " confirm_password
    echo

    if [[ "$password" != "$confirm_password" ]]; then
        log_error "Password mismatch. Please try again!\n"
    fi
done

log_info "${BODY}Auto-confirm Registered User"
auto_confirm=""
if [[ "$CI" == true ]]; then auto_confirm=false; \
elif [[ "$AC" == true ]]; then auto_confirm="$AC_CONFIRM"; fi

prompt="Do you want to send a confirmation email when registering a user?\n\
        If yes, you'll have to setup your own SMTP server [y/n]: "

while [ -z "$auto_confirm" ]; do
    confirmation_prompt auto_confirm "$prompt"
    if [[ "$auto_confirm" == true ]]; then
        auto_confirm=false
    elif [[ "$auto_confirm" == false ]]; then
        auto_confirm=true
    fi
done

# TODO: When AC_WITH_EXIM is supported, if auto_confirm == false, prompt to setup local SMTP server

# If with_authelia, then additionally ask for email and display name
if [[ "$with_authelia" == true ]]; then
    email=""
    display_name=""
    setup_redis=""

    if [[ "$CI" == true ]]; then
        email="johndoe@gmail.com"
        display_name="Inder Singh"
        if [[ "$WITH_REDIS" == true ]]; then setup_redis=true; fi
    elif [[ "$AC" == true ]]; then
        email="$AC_EMAIL"
        display_name="$AC_DISPLAY_NAME"
        setup_redis="$WITH_REDIS"
    fi

    log_info "${BODY}Authelia Email Address"
    while [ -z "$email" ]; do
        read -rp "$(format_prompt "Enter your email address for Authelia:") " email

        # split email string on @ symbol
        IFS="@" read -r before_at after_at <<<"$email"

        if [[ -z "$before_at" || -z "$after_at" ]]; then
            log_error "Invalid email address: $email"
            email=""
        fi
    done

    log_info "${BODY}Authelia Display Name"
    while [ -z "$display_name" ]; do
        read -rp "$(format_prompt "Enter your display name for Authelia:") " display_name

        if [[ ! "$display_name" =~ ^[a-zA-Z0-9[:space:]]+$ ]]; then
            log_warning "Only alphanumeric characters and spaces are allowed. Your rsponse: $display_name"
            display_name=""
        fi
    done

    log_info "${BODY}Setup Authelia to use Redis"
    while [[ "$CI" == false && "$AC" == false && -z "$setup_redis" ]]; do
        confirmation_prompt setup_redis "Do you want to setup Authelia to use Redis? [y/n]: "
    done
fi

log_info "${HEADER}Process Credentials"
#-------------------------------------------
# In caddy basic_auth, hashed password is loaded in memory
# In nginx basic_auth, websites slows down a lot if bcrypt rounds number is
# high as the hashed password file is checked again and again on every request.
# This is only applicable when using basic_auth, not with authelia
bcrypt_rounds=12
if [[ "$proxy" == "nginx" && "$with_authelia" == false ]]; then bcrypt_rounds=6; fi

# https://www.baeldung.com/linux/bcrypt-hash#using-htpasswd
password=$(htpasswd -bnBC "$bcrypt_rounds" "" "$password" | cut -d : -f 2)

gen_hex() { openssl rand -hex "$1"; }

jwt_secret="$(gen_hex 20)"

base64_url_encode() { openssl enc -base64 -A | tr '+/' '-_' | tr -d '='; }

header='{"typ":"JWT","alg":"HS256"}'
header_base64=$(printf %s "$header" | base64_url_encode)
# iat and exp for both tokens has to be same thats why initializing here
iat=$(date +%s)
exp=$(("$iat" + 5 * 3600 * 24 * 365)) # 5 years expiry

gen_token() {
    local payload
    payload=$(jq -nc ".iat=($iat | tonumber) | .exp=($exp | tonumber) | .iss=\"supabase\" | .role=\"$1\"")
    local payload_base64
    payload_base64=$(printf %s "$payload" | base64_url_encode)

    local signed_content="${header_base64}.${payload_base64}"
    local signature
    signature=$(printf %s "$signed_content" | openssl dgst -binary -sha256 -hmac "$jwt_secret" | base64_url_encode)

    printf '%s' "${signed_content}.${signature}"
}

anon_token=$(gen_token "anon")
service_role_token=$(gen_token "service_role")

log_info "${BODY}jwt_secret:${END} ${WHITE}$(elide "$jwt_secret")"
log_info "${BODY}anon_token:${END} ${WHITE}$(elide "$anon_token")"
log_info "${BODY}service_role_token:${END} ${WHITE}$(elide "$service_role_token")"

log_info "${BODY}sudo_user:${END} ${WHITE}${SUDO_USER}"
log_info "${BODY}using_sudo_user:${END} ${WHITE}$using_sudo_user"

log_info "${BODY}proxy:${END} ${WHITE}$proxy"
log_info "${BODY}auto_confirm:${END} ${WHITE}$auto_confirm"
log_info "${BODY}with_authelia:${END} ${WHITE}$with_authelia"
log_info "${BODY}setup_redis:${END} ${WHITE}$setup_redis"
log_info "${BODY}username:${END} ${WHITE}$username"
log_info "${BODY}display_name:${END} ${WHITE}$display_name"
log_info "${BODY}email:${END} ${WHITE}$email"

# Create .env file from .env.example template
log_info "${HEADER}Create .env File"
#-------------------------------------------
yml_bool() { echo "$(tr '[:lower:]' '[:upper:]' <<< "${1:0:1}")${1:1}" ; }

log_info "${BODY}Set Supabase and Postgres credentials"
sed -e "3d" \
    -e "s|POSTGRES_PASSWORD.*|POSTGRES_PASSWORD=$(gen_hex 16)|" \
    -e "s|JWT_SECRET.*|JWT_SECRET=$jwt_secret|" \
    -e "s|ANON_KEY.*|ANON_KEY=$anon_token|" \
    -e "s|SERVICE_ROLE_KEY.*|SERVICE_ROLE_KEY=$service_role_token|" \
    -e "s|DASHBOARD_USERNAME.*|DASHBOARD_USERNAME=supabase|" \
    -e "s|DASHBOARD_PASSWORD.*|DASHBOARD_PASSWORD=not_used|" \
    -e "s|SECRET_KEY_BASE.*|SECRET_KEY_BASE=$(gen_hex 32)|" \
    -e "s|VAULT_ENC_KEY.*|VAULT_ENC_KEY=$(gen_hex 16)|" \
    -e "s|PG_META_CRYPTO_KEY.*|PG_META_CRYPTO_KEY=$(gen_hex 16)|" \
    -e "s|API_EXTERNAL_URL.*|API_EXTERNAL_URL=$protocol://$SUPABASE_domain/goapi|" \
    -e "s|SUPABASE_PUBLIC_URL.*|SUPABASE_PUBLIC_URL=$protocol://$SUPABASE_domain|" \
    -e "s|ENABLE_EMAIL_AUTOCONFIRM.*|ENABLE_EMAIL_AUTOCONFIRM=$auto_confirm|" \
    -e "s|POOLER_TENANT_ID.*|POOLER_TENANT_ID=1100|" \
    -e "s|LOGFLARE_PUBLIC_ACCESS_TOKEN.*|LOGFLARE_PUBLIC_ACCESS_TOKEN=$(gen_hex 16)|" \
    -e "s|LOGFLARE_PRIVATE_ACCESS_TOKEN.*|LOGFLARE_PRIVATE_ACCESS_TOKEN=$(gen_hex 16)|" \
    -e "s|S3_PROTOCOL_ACCESS_KEY_ID.*|S3_PROTOCOL_ACCESS_KEY_ID=$(gen_hex 16)|" \
    -e "s|S3_PROTOCOL_ACCESS_KEY_SECRET.*|S3_PROTOCOL_ACCESS_KEY_SECRET=$(gen_hex 32)|" \
    -e "s|MINIO_ROOT_PASSWORD.*|MINIO_ROOT_PASSWORD=$(gen_hex 16)|" \
    -e "s|SMTP_PASS.*|SMTP_PASS=$(gen_hex 16)|" \
    .env.example >.env

if [[ "$AC" == true ]]; then
log_info "${BODY}Set ${APP_NAME} module credentials"
sed -i \
    -e "s|N8N_ENCRYPTION_KEY.*|N8N_ENCRYPTION_KEY=$(gen_hex 32)|" \
    -e "s|N8N_RUNNERS_AUTH_TOKEN.*|N8N_RUNNERS_AUTH_TOKEN=$(gen_hex 32)|" \
    -e "s|N8N_USER_MANAGEMENT_JWT_SECRET.*|N8N_USER_MANAGEMENT_JWT_SECRET=$(gen_hex 32)|" \
    -e "s|FLOWISE_PASSWORD.*|FLOWISE_PASSWORD=$(gen_hex 16)|" \
    -e "s|NEO4J_AUTH.*|NEO4J_AUTH=neo4j/$(gen_hex 16)|" \
    -e "s|CLICKHOUSE_PASSWORD.*|CLICKHOUSE_PASSWORD=$(gen_hex 16)|" \
    -e "s|LANGFUSE_SALT.*|LANGFUSE_SALT=$(gen_hex 16)|" \
    -e "s|NEXTAUTH_SECRET.*|NEXTAUTH_SECRET=$(gen_hex 16)|" \
    -e "s|ENCRYPTION_KEY.*|ENCRYPTION_KEY=$(gen_hex 16)|" \
    .env

log_info "${BODY}Enable  module credentials"
sed -i \
    -e "s|^AC=.*|AC=$(yml_bool "${AC}")|" \
    -e "s|AC_SUDO_USER.*|AC_SUDO_USER=${AC_SUDO_USER}|" \
    -e "s|AC_DOMAIN.*|AC_DOMAIN=${AC_DOMAIN}|" \
    -e "s|AC_LOCAL.*|AC_LOCAL=$(yml_bool "${AC_LOCAL}")|" \
    -e "s|AC_PROXY.*|AC_PROXY=${AC_PROXY}|" \
    -e "s|AC_USERNAME.*|AC_USERNAME=${AC_USERNAME}|" \
    -e "s|AC_PASSWORD.*|AC_PASSWORD=${AC_PASSWORD}|" \
    -e "s|AC_CONFIRM.*|AC_CONFIRM=$(yml_bool "${AC_CONFIRM}")|" \
    -e "s|AC_WITH_AUTHELIA.*|AC_WITH_AUTHELIA=$(yml_bool "${AC_WITH_AUTHELIA}")|" \
    -e "s|AC_EMAIL.*|AC_EMAIL=${AC_EMAIL}|" \
    -e "s|AC_DISPLAY_NAME.*|AC_DISPLAY_NAME=${AC_DISPLAY_NAME}|" \
    -e "s|AC_WITH_REDIS.*|AC_WITH_REDIS=$(yml_bool "${AC_WITH_REDIS}")|" \
    -e "s|AC_LOG_PATH.*|AC_LOG_PATH=${AC_LOG_PATH}|" \
    -e "s|# N8N_PROTOCOL.*|N8N_PROTOCOL=$protocol|" \
    -e "s|# N8N_PROXY_HOPS.*|N8N_PROXY_HOPS=3|" \
    .env

[[ "$proxy" == "caddy" ]] && { \
log_info "${BODY}Enable Caddy hostname variables" ;
sed -i \
    -e "s|# WEBUI_HOSTNAME.*|WEBUI_HOSTNAME=openwebui.\${AC_DOMAIN}|" \
    -e "s|# N8N_HOSTNAME.*|N8N_HOSTNAME=n8n.\${AC_DOMAIN}|" \
    -e "s|# FLOWISE_HOSTNAME.*|FLOWISE_HOSTNAME=flowise.\${AC_DOMAIN}|" \
    -e "s|# SUPABASE_HOSTNAME.*|SUPABASE_HOSTNAME=supabase.\${AC_DOMAIN}|" \
    -e "s|# LANGFUSE_HOSTNAME.*|LANGFUSE_HOSTNAME=langfuse.\${AC_DOMAIN}|" \
    -e "s|# SEARXNG_HOSTNAME.*|SEARXNG_HOSTNAME=searxng.\${AC_DOMAIN}|" \
    -e "s|# NEO4J_HOSTNAME.*|NEO4J_HOSTNAME=neo4j.\${AC_DOMAIN}|" \
    -e "s|# OLLAMA_HOSTNAME.*|OLLAMA_HOSTNAME=ollama.\${AC_DOMAIN}|" \
    -e "s|# LLAMACPP_HOSTNAME.*|LLAMACPP_HOSTNAME=llamacpp.\${AC_DOMAIN}|" \
    -e "s|# WEBHOOK_URL=.*|WEBHOOK_URL=$protocol://\${N8N_HOSTNAME}|" \
    -e "s|# LETSENCRYPT_EMAIL.*|LETSENCRYPT_EMAIL=\${AC_EMAIL}|" \
    .env ;
}

log_info "${BODY}Enable n8n proxy variables"
sed -i \
    -e "s|#- N8N_HOST=.*|- N8N_HOST=\${N8N_HOSTNAME:-\${N8N_HOST}}|" \
    -e "s|#- N8N_PORT=.*|- N8N_PORT=\${N8N_PORT}|" \
    -e "s|#- N8N_PROTOCOL=.*|- N8N_PROTOCOL=\${N8N_PROTOCOL}|" \
    -e "s|#- N8N_PROXY_HOPS=.*|- N8N_PROXY_HOPS=\${N8N_PROXY_HOPS}|" \
    docker-compose.yml
fi

# Update yaml file using yq package
update_yaml_file() {
    # https://github.com/mikefarah/yq/issues/465#issuecomment-2265381565
    sed -i '/^\r\{0,1\}$/s// #BLANK_LINE/' "$2"
    "$yq_bin" -i "$1" "$2"
    sed -i "s/ *#BLANK_LINE//g" "$2"
}

# Create env_vars list to append .env file
env_vars=()
update_env_vars() {
    for env_key_value in "$@"; do
        env_vars+=("$env_key_value")
    done
}

log_info "${HEADER}Configure Proxy Service"
#-------------------------------------------
# DEFINE PROXY service
proxy_service_yaml=".services.$proxy.profiles=[\"$proxy\"$([[ "$proxy" == "caddy" ]] && echo ", \"ai-all\"")] |
.services.$proxy.container_name=\"$proxy\" |
.services.$proxy.restart=\"unless-stopped\" |
.services.$proxy.ports=[\"80:80/tcp\",\"443:443/tcp\"]
"
if [[ -v "SUPABASE_DOMAIN" ]]; then
    proxy_service_yaml="${proxy_service_yaml} | .services.$proxy.depends_on.kong.condition=\"service_healthy\""
fi

if [[ "$with_authelia" == true ]]; then
    proxy_service_yaml="${proxy_service_yaml} | .services.$proxy.depends_on.authelia.condition=\"service_healthy\""
fi

# DEFINE Caddyfile and Caddy Docker service insert
if [[ "$proxy" == "caddy" ]]; then
    log_info "${BODY}Define Caddyfile and Caddy Docker service insert"
    #-------------------------------------------
    caddy_local_volume="./access/caddy"
    caddyfile_local="$caddy_local_volume/Caddyfile"

    # mounted local ./caddy/addons to this path inside container
    caddy_addons_path="/etc/caddy/addons"

# DEFINE nginx.template and Nginx Docker service insert
else
    log_info "${BODY}Define nginx.template and Nginx Docker service insert"
    #-------------------------------------------
    update_env_vars "NGINX_SERVER_NAME=$host"
    # docker compose nginx service command directive. Passed via yq strenv
    nginx_cmd=""

    nginx_local_volume="./access/nginx"
    # path in local fs where nginx template file is stored
    nginx_local_template_file="$nginx_local_volume/nginx.template"

    # path inside container where template file will be mounted
    nginx_container_template_file="/etc/nginx/user_conf.d/nginx.template"

    # Pass an array of args to nginx service command directive https://stackoverflow.com/a/57821785/18954618
    # output multiline string from yq https://mikefarah.gitbook.io/yq/operators/string-operators#string-blocks-bash-and-newlines

    proxy_service_yaml="${proxy_service_yaml} |
                        .services.nginx.image=\"jonasal/nginx-certbot:6.0.1-nginx1.29.5\" |
                        .services.ngnix.expose=[\"81/tcp\",\"443/tcp\",\"443/udp\",\"80/tcp\"] |
                        .services.nginx.environment.NGINX_SERVER_NAME = \"\${NGINX_SERVER_NAME:?error}\" |
                        .services.nginx.environment.CERTBOT_EMAIL = \"\${AC_EMAIL:?error}\" |
                        .services.nginx.environment.TZ = \"\${GENERIC_TIMEZONE:-England/Greenwich}\" |
                        .services.nginx.volumes=[\"$nginx_local_volume:/etc/nginx/user_conf.d\",
                                                 \"$nginx_local_volume/letsencrypt:/etc/letsencrypt\"] |
                        .services.nginx.command=[\"/bin/bash\",\"-c\",strenv(nginx_cmd)]
                       "

    if [[ "$CI" == true || "$AC_LOCAL" == true ]]; then
        # https://github.com/JonasAlfredsson/docker-nginx-certbot/blob/master/docs/advanced_usage.md#local-ca
        proxy_service_yaml="${proxy_service_yaml} | .services.nginx.environment.USE_LOCAL_CA=1"
    fi

    # https://www.baeldung.com/linux/nginx-config-environment-variables#4-a-common-pitfall

    printf -v nginx_cmd \
        "envsubst '\$\${NGINX_SERVER_NAME}' < %s > %s/nginx.conf \\
&& /scripts/start_nginx_certbot.sh\n" \
        "$nginx_container_template_file" "$(dirname "$nginx_container_template_file")"
fi

# HANDLE NGINX PROXY service BASIC_AUTH
if [[ "$with_authelia" == false ]]; then
    log_info "${BODY}Nginx basic authorization Docker service insert"
    #-------------------------------------------
    update_env_vars "PROXY_AUTH_USERNAME=$username" "PROXY_AUTH_PASSWORD='$password'"

    proxy_service_yaml="${proxy_service_yaml} |
                        .services.$proxy.environment.PROXY_AUTH_USERNAME = \"\${PROXY_AUTH_USERNAME:?error}\" |
                        .services.$proxy.environment.PROXY_AUTH_PASSWORD = \"\${PROXY_AUTH_PASSWORD:?error}\"
                        "

    if [[ "$proxy" == "nginx" ]]; then
        # path inside nginx container for storing basic_auth credentials
        nginx_pass_file="/etc/nginx/user_conf.d/supabase-self-host-users"

        printf -v nginx_cmd "echo \"\$\${PROXY_AUTH_USERNAME}:\$\$y{PROXY_AUTH_PASSWORD}\" >%s \\
&& %s" $nginx_pass_file "$nginx_cmd"
    fi
fi

# WRITE NGINX PROXY service to docker-compose.yml file
log_info "${BODY}Write $proxy proxy service to docker-compose.yml file"
#-------------------------------------------
compose_file="docker-compose.yml"
nginx_cmd="${nginx_cmd:=""}" update_yaml_file "$proxy_service_yaml" "$compose_file"

# AUTHELIA configuration
if [[ "$with_authelia" == true ]]; then
    log_info "${HEADER}Write Authelia Config"
    #-------------------------------------------
    # Dynamically update yaml path from env https://github.com/mikefarah/yq/discussions/1253
    # https://mikefarah.gitbook.io/yq/operators/style

    # WRITE AUTHELIA users_database.yml file
    # adding disabled=false after updating style to double so that every value except disabled is double quoted
    log_info "${BODY}Write Authelia users_database.yml file"
    #-------------------------------------------
    yaml_path=".users.$username" display_name="$display_name" password="$password" email="$email" \
        "$yq_bin" -n 'eval(strenv(yaml_path)).displayname = strenv(display_name) |
               eval(strenv(yaml_path)).password = strenv(password) |
               eval(strenv(yaml_path)).email = strenv(email) |
               eval(strenv(yaml_path)).groups = ["admins","dev"] |
               .. style="double" |
               eval(strenv(yaml_path)).disabled = false' >./access/authelia/users_database.yml

    # DEFINE AUTHELIA configuration.yml file
    log_info "${BODY}Define Authelia configuration.yml file"
    #-------------------------------------------
    authelia_config_file_yaml="
            .access_control.rules[0].domain=strenv(webui_domain) |
            .access_control.rules[1].domain=strenv(n8n_domain) |
            .access_control.rules[2].domain=strenv(flowise_domain) |
            .access_control.rules[3].domain=strenv(langfuse_domain) |
            .access_control.rules[4].domain=strenv(supabase_domain) |
            .access_control.rules[5].domain=strenv(searxng_domain) |
            .access_control.rules[6].domain=strenv(neo4j_domain) |
            .access_control.rules[7].domain=strenv(llama_domain) |
            .session.cookies[0].domain=strenv(registered_domain) |
            .session.cookies[0].authelia_url=strenv(authelia_url) |
            .session.cookies[0].default_redirection_url=strenv(redirect_url)"

    server_endpoints="forward-auth"
    implementation="ForwardAuth"

    if [[ "$proxy" == "nginx" ]]; then
        server_endpoints="auth-request"
        implementation="AuthRequest"
    fi

    # auth implementation
    authelia_config_file_yaml="${authelia_config_file_yaml} | .server.endpoints.authz.$server_endpoints.implementation=\"$implementation\""

    update_env_vars "AUTHELIA_SESSION_SECRET=$(gen_hex 32)" "AUTHELIA_STORAGE_ENCRYPTION_KEY=$(gen_hex 32)" "AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET=$(gen_hex 32)"

    # DEFINE AUTHELIA configuration.yml file
    log_info "${BODY}Define Authelia Docker service"
    #-------------------------------------------

    # shellcheck disable=SC2016
    authelia_docker_service_yaml='.services.authelia.container_name = "authelia" |
       .services.authelia.profiles=["caddy", "nginx", "ai-all"] |
       .services.authelia.image = "authelia/authelia:4.38" |
       .services.authelia.volumes = ["./access/authelia:/config"] |
       .services.authelia.depends_on.db.condition = "service_healthy" |
       .services.authelia.expose = [9091] |
       .services.authelia.restart = "unless-stopped" |
       .services.authelia.healthcheck.disable = false |
       .services.authelia.environment = {
         "AUTHELIA_STORAGE_POSTGRES_ADDRESS": "tcp://db:5432",
         "AUTHELIA_STORAGE_POSTGRES_USERNAME": "postgres",
         "AUTHELIA_STORAGE_POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
         "AUTHELIA_STORAGE_POSTGRES_DATABASE": "${POSTGRES_DB}",
         "AUTHELIA_STORAGE_POSTGRES_SCHEMA": strenv(authelia_schema),
         "AUTHELIA_SESSION_SECRET": "${AUTHELIA_SESSION_SECRET:?error}",
         "AUTHELIA_STORAGE_ENCRYPTION_KEY": "${AUTHELIA_STORAGE_ENCRYPTION_KEY:?error}",
         "AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET": "${AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET:?error}"
       }'

    authelia_docker_supabase_service_yaml='.services.db.environment.AUTHELIA_SCHEMA = strenv(authelia_schema) |
       .services.db.volumes += "./access/authelia/db/schema-authelia.sh:/docker-entrypoint-initdb.d/schema-authelia.sh"'

    if [[ "$setup_redis" == true ]]; then
        log_info "${BODY}Authelia Redis configuration"
        #-------------------------------------------
        redis_docker_service_yaml=".services.authelia.profiles=[\"$proxy\", \"n8n\", \"langfuse\", \"ai-all\"]"
        update_yaml_file "$redis_docker_service_yaml" "$compose_file"

        authelia_config_file_yaml="${authelia_config_file_yaml}|.session.redis.host=\"redis\" | .session.redis.port=6379"
        authelia_docker_service_yaml="${authelia_docker_service_yaml}|.services.authelia.depends_on.redis.condition=\"service_healthy\""
    fi

    # TODO - modify _url to use domain versus host (subdomain.domain)
    # WRITE AUTHELIA configuration.yml file (Supabase target)
    log_info "${BODY}Write Authelia configuration.yml file"
    #-------------------------------------------
    (
        export_domain_envs
        host="$host" \
        registered_domain="$registered_domain" \
        authelia_url="$protocol://$WEBUI_DOMAIN/authenticate" \
        redirect_url="$protocol://$WEBUI_DOMAIN" \
        update_yaml_file "$authelia_config_file_yaml" "./access/authelia/configuration.yml"
    )

    # WRITE AUTHELIA service to docker-compose.yml file
    log_info "${BODY}Write Authelia service to docker-compose.yml file"
    #-------------------------------------------
    authelia_schema="authelia" update_yaml_file "$authelia_docker_service_yaml" "$compose_file"

    # WRITE AUTHELIA service to Supabase docker-compose.yml file
    log_info "${BODY}Write Authelia service to Supabase docker-compose.yml file"
    #-------------------------------------------
    authelia_schema="authelia" update_yaml_file "$authelia_docker_supabase_service_yaml" "./supabase/docker/$compose_file"
fi

# TODO: Setup Exim SMTP server if AC_WITH_EXIM == true (AC_WITH_EXIM is not yet supported)

# WRITE env_vars to .env file
log_info "${HEADER}Write Additional .env Variables"
#-------------------------------------------
env_pair=()
for env_var in "${env_vars[@]}"; do
    IFS='=' read -r -a env_pair <<< "$env_var"
    if (( ${#env_pair[@]} > 1 )); then
        if cat ".env" | grep -q "^${env_pair[0]}"; then
            log_info "${BODY}Update ${env_pair[0]}"
            sed -i "s|${env_pair[0]}.*|${env_pair[0]}=${env_pair[1]}|" .env
        else
            log_info "${BODY}Append ${env_pair[0]}"
            echo -e "${env_pair[0]}=${env_pair[1]}" >>.env
        fi
    fi
done

# Docker:         http://host.docker.internal:<port>
# Local:          http://localhost:<port>
# Local (proxy):  https://local.pc:<port>
# Global:         https://my-ai-suite.fr:<port>

# | Ex | In | Service                 | Container - Docker internal       | Domain - Docker external |
# | -: | -: | ----------------------: | --------------------------------: | -----------------------: |
# | ++ |    | `n8n`                   | n8n:5678/                         | localhost:5678/          |
# | ++ |    | `Open WebUI`            | open-webui:8080/                  | localhost:8080/          |
# | ++ | ++ | `Flowise`               | flowise:3001/                     | localhost:3001/          |
# |    | ++ | `Open webUI MCPO`       | open-webui-mcpo:8090/             | localhost:8090/          |
# |    | ++ | `MCP Gateway`           | mcp-gateway:8060/                 | localhost:8060/          |
# |    | ++ | `Open webUI Filesystem` | open-webui-filesystem:8091/docs/  | localhost:8091/docs/     |
# |    | ++ | `Redis`                 | redis:6379/                       | localhost:6379/          |
# |    | ++ | `MinIO`                 | minio:9001/                       | localhost:9001/          |
# |    | ++ | `QDrant`                | qdrant:6333/dashboard/            | localhost:6333/dashboard/|
# | ++ | ++ | `Subabase`              | supabase-kong:8000                | localhost:8000           |
# |    | ++ | `Postgres`              | postgres:5432                     | localhost:5432/          |
# | ++ |    | `Langfuse Web`          | langfuse-web:3000/                | localhost:3000/          |
# |    | ++ | `Langfuse Worker`       | langfuse-worker:3030/             | localhost:3030/          |
# |    | ++ | `Logflare`              | supabase-analytics:4000/dashboard/| localhost:4000/dashboard/|
# |    | ++ | `ClickHouse`            | clickhouse:8123/                  | localhost:8123/          |
# | ++ |    | `SearXNG`               | searxng:8081/                     | localhost:8081/          |
# | ++ | ++ | `Neo4j`                 | neo4j:7473/                       | localhost:7473/          |
# |    | ++ | `Caddy`                 | caddy:443/                        | localhost:443/           |
# |    | ++ | `Nginx`                 | nginx:443/Admin/                  | localhost:443/Admin/     |
# |    | ++ | `Authelia`              | authelia:9091/                    | localhost:9091/          |
# | ++ | ++ | `Ollama`                | ollama:11434/                     | localhost:11434/         |
# | ++ | ++ | `LLaMA.cpp`             | llamacpp:8040/                    | localhost:8040/          |

# NOTE: LLAMA and SearXNG are disabled in proxy config by default.
# Set AC_LLAMA and AC_SEARXNG to anything other than empty, to enable:

# WRITE LOCAL Caddyfile
if [[ "$proxy" == "caddy" ]]; then
    log_info "${HEADER}Write Caddyfile"
    #-------------------------------------------
    log_info "${BODY}caddyfile_local: $caddyfile_local"
    mkdir -p "$caddy_local_volume"
    # https://stackoverflow.com/a/3953712/18954618
    echo "
    {
        # Global options - works for both environments
        email {\$LETSENCRYPT_EMAIL}

        $([[ "$CI" == true || "$AC_LOCAL" == true ]] && echo "tls internal")

        $([[ "$with_authelia" == true ]] && echo "@authelia path /authenticate /authenticate/*
        handle @authelia {
            reverse_proxy authelia:9091
        }")

        handle {
            $([[ "$with_authelia" == false ]] && echo "basic_auth {
                {\$PROXY_AUTH_USERNAME} {\$PROXY_AUTH_PASSWORD}
            }" || echo "forward_auth authelia:9091 {
                uri /api/authz/forward-auth
                copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
            }")
        }
    }

    # N8N
    {\$N8N_HOSTNAME} {
        # For domains, Caddy will automatically use Let's Encrypt
        # For localhost/port addresses, HTTPS won't be enabled
        reverse_proxy n8n:5678
    }

    # Open WebUI
    {\$WEBUI_HOSTNAME} {
        reverse_proxy open-webui:8080
    }

    # Flowise
    {\$FLOWISE_HOSTNAME} {
        reverse_proxy flowise:3001
    }

    # Langfuse
    {\$LANGFUSE_HOSTNAME} {
        reverse_proxy langfuse-web:3000
    }

    # Supabase
    {\$SUPABASE_HOSTNAME} {
        @supa_api path /rest/v1/* /auth/v1/* /realtime/v1/* /functions/v1/* /mcp /api/mcp

        handle @supa_api {
            reverse_proxy supabase-kong:8000
        }

        handle_path /storage/v1/* {
            import cors *
            reverse_proxy storage:5000 {
                header_up X-Forwarded-Prefix /{http.request.orig_uri.path.0}/{http.request.orig_uri.path.1}
            }
        }

        handle_path /goapi/* {
            reverse_proxy kong:8000
        }

        handle_path /logflare/* {
            reverse_proxy analytics:4000
        }

        handle {
            reverse_proxy studio:3000
        }
    }

    # Neo4j
    {\$NEO4J_HOSTNAME} {
        reverse_proxy neo4j:7474
    }

    # SearXNG
    $([[ -n "$AC_SEARXNG" ]] && echo "\
{\$SEARXNG_HOSTNAME} {" || echo "\
{DISABLED_SEARXNG} {")
        encode zstd gzip

        @api {
            path /config
            path /healthz
            path /stats/errors
            path /stats/checker
        }
        @search {
            path /search
        }
        @imageproxy {
            path /image_proxy
        }
        @static {
            path /static/*
        }

        header {
            # CSP (https://content-security-policy.com)
            Content-Security-Policy \"upgrade-insecure-requests; default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self' https://github.com/searxng/searxng/issues/new; font-src 'self'; frame-ancestors 'self'; base-uri 'self'; connect-src 'self' https://overpass-api.de; img-src * data:; frame-src https://www.youtube-nocookie.com https://player.vimeo.com https://www.dailymotion.com https://www.deezer.com https://www.mixcloud.com https://w.soundcloud.com https://embed.spotify.com;\"
            # Disable some browser features
            Permissions-Policy \"accelerometer=(),camera=(),geolocation=(),gyroscope=(),magnetometer=(),microphone=(),payment=(),usb=()\"
            # Set referrer policy
            Referrer-Policy \"no-referrer\"
            # Force clients to use HTTPS
            Strict-Transport-Security \"max-age=31536000\"
            # Prevent MIME type sniffing from the declared Content-Type
            X-Content-Type-Options \"nosniff\"
            # X-Robots-Tag (comment to allow site indexing)
            X-Robots-Tag \"noindex, noarchive, nofollow\"
            # Remove \"Server\" header
            -Server
        }

        header @api {
            Access-Control-Allow-Methods \"GET, OPTIONS\"
            Access-Control-Allow-Origin \"*\"
        }

        route {
            # Cache policy
            header Cache-Control \"max-age=0, no-store\"
            header @search Cache-Control \"max-age=5, private\"
            header @imageproxy Cache-Control \"max-age=604800, public\"
            header @static Cache-Control \"max-age=31536000, public, immutable\"
        }

        # SearXNG (uWSGI)
        reverse_proxy searxng:8080 {
            header_up X-Forwarded-Port {http.request.port}
            header_up X-Real-IP {http.request.remote.host}
            # https://github.com/searx/searx-docker/issues/24
            header_up Connection \"close\"
        }
    }

    $(if [[ -n "$AC_LLAMA" ]]; then \
      [[ "$AC_LLAMACPP" == false ]] && echo "\
    # Ollama API
    {\$OLLAMA_HOSTNAME} {
        reverse_proxy ollama:11434
    }" || echo "\
    # LLaMA.cpp API
    {\$LLAMACPP_HOSTNAME} {
        reverse_proxy llamacpp:8040
    }"; fi)

    import $caddy_addons_path/cors.conf
" >"$caddyfile_local"
# WRITE LOCAL nginx.template
else
    log_info "${HEADER}Write Nginx Template"
    #-------------------------------------------
    log_info "${BODY}nginx_local_template: $nginx_local_template_file"

    mkdir -p "$(dirname "$nginx_local_template_file")"

    # mounted local ./nginx/addons to this path inside container
    nginx_addons_path="/etc/nginx/user_conf.d/addons"

    # cert path inside container https://github.com/JonasAlfredsson/docker-nginx-certbot/blob/master/docs/good_to_know.md#how-the-script-add-domain-names-to-certificate-requests
    cert_path="/etc/letsencrypt/live/automated-self-host"

    echo "
upstream n8n_upstream {
    server n8n:5678;
    keepalive 2;
}

upstream open-webui_upstream {
    server open-webui:8080;
    keepalive 2;
}

upstream flowise_upstream {
    server flowise:3001;
    keepalive 2;
}

upstream kong_upstream {
    server kong:8000;
    keepalive 2;
}

upstream logflare_upstream {
    server analytics:4000;
    keepalive 2;
}

upstream neo4j_upstream {
    server neo4j:7474;
    keepalive 2;
}

upstream langfuse_upstream {
    server langfuse-web:3000;
    keepalive 2;
}

$([[ -n "$AC_SEARXNG" ]] && echo "\
upstream searxng_upstream {
    server searxng:8081;
    keepalive 2;
}")

$(if [[ -n "$AC_LLAMA" ]]; then \
  [[ "$AC_LLAMACPP" == false ]] && echo "\
upstream ollama_upstream {
    server ollama:11434;
    keepalive 2;
}" || echo "\
upstream llamacpp_upstream {
    server llamacpp:8040;
    keepalive 2;
}"; fi)

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name \${NGINX_SERVER_NAME};
    server_tokens off;
    proxy_http_version 1.1;

    include $nginx_addons_path/common_proxy_headers.conf;

    ssl_certificate         $cert_path/fullchain.pem;
    ssl_certificate_key     $cert_path/privkey.pem;
    ssl_trusted_certificate $cert_path/chain.pem;

    ssl_dhparam /etc/letsencrypt/dhparams/dhparam.pem;

    # n8n
    location /n8n {
        proxy_pass http://n8n_upstream
    }

    # Open-webui
    location /open-webui {
        proxy_pass http://open-webui_upstream
    }

    # Flowise
    location /flowise {
        proxy_pass http://flowise_upstream
    }

    # Neo4j
    location /neo4j {
        proxy_pass http://neo4j_upstream
    }

    # Langfuse
    location /langfuse {
        proxy_pass http://langfuse_upstream
    }

    $([[ -n "$AC_SEARXNG" ]] && echo "\
    # SearXNG
    location /searxng {
        proxy_pass http://searxng_upstream
    }")

    $(if [[ -n "$AC_LLAMA" ]]; then \
      [[ "$AC_LLAMACPP" == false ]] && echo "\
    # Ollama
    location / {
        proxy_pass http://ollama_upstream
    }" || echo "\
    # LLaMA.cpp
    location /llamacpp {
        proxy_pass http://llamacpp_upstream
    }"; fi)

    # Supabase
    location /supabase/realtime {
        proxy_pass http://kong_upstream;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_read_timeout 3600s;
    }

    location /supabase/storage/v1/ {
        include $nginx_addons_path/cors.conf;
        include $nginx_addons_path/common_proxy_headers.conf;
        proxy_set_header X-Forwarded-Prefix /storage/v1;
        client_max_body_size 0;
        proxy_pass http://storage:5000/;
    }

    location /supabase/logflare {
        proxy_pass http://logflare_upstream
    }

    location /supabase/goapi/ {
        proxy_pass http://kong_upstream/;
    }

    location /supabase/rest {
        proxy_pass http://kong_upstream;
    }

    location /supabase/auth {
        proxy_pass http://kong_upstream;
    }

    location /supabase/functions {
        proxy_pass http://kong_upstream;
    }

    location /supabase/mcp {
        proxy_pass http://kong_upstream;
    }

    location /supabase/api/mcp {
        proxy_pass http://kong_upstream;
    }

    location /supabase {
        proxy_pass http://studio:3000;
    }

    $([[ $with_authelia == true ]] && echo "
    include $nginx_addons_path/authelia-location.conf;

    location /authenticate {
        include $nginx_addons_path/common_proxy_headers.conf;
        include $nginx_addons_path/proxy.conf;
        proxy_pass http://authelia:9091;
    }")

    location / {
        $(
        [[ $with_authelia == false ]] && echo "auth_basic \"Admin\";
        auth_basic_user_file $nginx_pass_file;
        " || echo "
        include $nginx_addons_path/proxy.conf;
        include $nginx_addons_path/authelia-authrequest.conf;
        "
        )
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name \${NGINX_SERVER_NAME};
    return 301 https://\$server_name\$request_uri;
}
" >"$nginx_local_template_file"
fi

if [[ "$using_sudo_user" == true ]]; then
    log_info "${BODY}Setting $(basename "$(pwd)")/* ownership to $SUDO_USER..."
    #-------------------------------------------
    chown -R "$SUDO_USER": .;
fi

# Update hosts file if local install
unix_hosts_add() {
    local header="# $APP_NAME Local Domains:"
    local footer="# End of $APP_NAME section"

    if [[ "$BACKUP" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
        cp "$HOSTS_PATH" "$HOSTS_PATH.bak.$(date +%Y%m%d%H%M%S)"
    fi

    if [[ $DRY_RUN -eq 1 ]]; then echo "[DRY-RUN] $header"; elif \
    ! grep -q "^$header" "$HOSTS_PATH"; then \
    printf "%s\n" "$header" >> "$HOSTS_PATH"; fi

    local d
    for d in "${DOMAINS[@]}"; do
        local pattern="^\\s*$HOST_IP\\s+$d"
        if ! grep -qE "$pattern" "$HOSTS_PATH"; then
            [[ $DRY_RUN -eq 1 ]] && { echo -e "[DRY-RUN] $HOST_IP\t$d"; continue; }
            printf "%s\t%s\n" "$HOST_IP" "$d" >> "$HOSTS_PATH"
        fi
    done

    if [[ $DRY_RUN -eq 1 ]]; then echo "[DRY-RUN] $footer"; elif \
    ! grep -q "^$footer" "$HOSTS_PATH"; then \
    printf "%s\n" "$footer" >> "$HOSTS_PATH"; fi
}

unix_hosts_edit() {
    if [[ "$INTERNAL_ELEVATED" -eq 1 ]]; then
        log_info "${BODY}Running normal"
        unix_hosts_add
        return
    fi

    local user_privilage
    unix_privilage user_privilage

    if [[ "$user_privilage" == "is_unix_root" ]]; then
        log_info "${BODY}Running as${END} ${WHITE}Root"
        unix_hosts_add
    fi
}

windows_hosts_edit() {
    local elevated
    if is_windows_admin elevated; then
	    log_info "${BODY}Running as${END} ${WHITE}Administrator"
    else
        log_info "${BODY}Running normal"
    fi
    local ps_script_path="./access/ps_edit_hosts.ps1"
    local header="# $APP_NAME Local Domains:"
    local footer="# End of $APP_NAME section"
    local d ps_domains=""
    for d in "${DOMAINS[@]}"; do
        ps_domains+="\"$d\","
    done
    ps_domains="@(${ps_domains%,})"
    local ps_script="# Edit hosts - update $APP_NAME domains
\$Domains    = $ps_domains
\$Backup     = $BACKUP
\$DryRun     = $DRY_RUN
\$Ip         = \"$HOST_IP\"
\$Header     = \"$header\"
\$Footer     = \"$footer\"
\$HostsPath  = [System.IO.Path]::GetFullPath(\"$WIN_HOSTS_PATH\")
\$TargetPath = [System.IO.Path]::GetFullPath('C:\\Windows\\System32\\drivers\\etc\\hosts')
\$Restricted = [string]::Equals(\$HostsPath, \$TargetPath, [System.StringComparison]::OrdinalIgnoreCase)
\$Elevated   = ([Security.Principal.WindowsPrincipal] \`
  [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (\$Restricted -and -not \$Elevated) {
    \$ScriptPath = [System.IO.Path]::GetFullPath(\$MyInvocation.MyCommand.Path)
    Start-Process powershell.exe \`
        -ArgumentList @(
            '-NoProfile',
            '-ExecutionPolicy','Bypass',
            '-File', \$ScriptPath
        ) \`
        -Verb RunAs \`
        -WindowStyle Hidden \`
        -Wait
    exit \$LASTEXITCODE
}

if (\$Backup -eq 1 -and \$DryRun -eq 0) {
    \$Ts = Get-Date -Format \"yyyyMMddHHmmss\"
    Copy-Item \"\$HostsPath\" \"\$HostsPath.bak.\$Ts\"
}

\$Pattern = \"^\$Header\"
if (-not (Select-String -Path \"\$HostsPath\" -Pattern \$Pattern -Quiet)) {
    if (\$DryRun -ne 1) {
        Add-Content -Path \"\$HostsPath\" -Value \"\$Header\"
    }
}

foreach (\$Domain in \$Domains) {
    \$Pattern = \"^\$Ip\s+\$Domain\"
    if (-not (Select-String -Path \"\$HostsPath\" -Pattern \$Pattern -Quiet)) {
        if (\$DryRun -ne 1) {
            Add-Content -Path \"\$HostsPath\" -Value \"\$Ip\`t\$Domain\"
        }
    }
}

\$Pattern = \"^\$Footer\"
if (-not (Select-String -Path \"\$HostsPath\" -Pattern \$Pattern -Quiet)) {
    if (\$DryRun -ne 1) {
        Add-Content -Path \"\$HostsPath\" -Value \"\$Footer\"
    }
}
"

    echo "$ps_script" > "$ps_script_path"

    log_debug "ps_script: $ps_script"

    if [[ $SILENT -eq 1 ]]; then
        if [[ "$elevated" != true ]]; then
            critical_exit "Silent mode requires Administrator privilage."
        fi
    fi

    if [[ "$elevated" == true ]]; then
        powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$ps_script_path"
    else
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
          Start-Process powershell.exe -WindowStyle Hidden -Wait -ArgumentList @(
             '-NoProfile',
             '-ExecutionPolicy Bypass',
             '-File',
             \"$ps_script_path\"
          )
        "
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        ! grep -q "^$header" "$HOSTS_PATH" && \
        echo "[DRY-RUN] $header"
        for d in "${DOMAINS[@]}"; do
            local pattern="^\\s*$HOST_IP\\s+$d"
            if ! grep -qE "$pattern" "$HOSTS_PATH"; then
                echo -e "[DRY-RUN] $HOST_IP\t$d";
            fi
        done
        ! grep -q "^$footer" "$HOSTS_PATH" && \
        echo "[DRY-RUN] $footer"
    else
        rm "$ps_script_path"
    fi
}

check_host_domains() {
    local d quiet=false
    quiet=$([[ "$1" == "--quiet" ]] && echo true)

    [[ "$quiet" == false ]] && \
    log_info "${HEADER}Configured Domains"
    #-------------------------------------------
    mal_domains=()
    for d in "${DOMAINS[@]}"; do
        local pattern="^\\s*$HOST_IP\\s+$d"
        if grep -qE "$pattern" "$HOSTS_PATH"; then
            [[ "$quiet" == false ]] && \
            log_info "${GREEN}  ✔${END} ${WHITE}$d"
        else
            [[ "$quiet" == false ]] && \
            log_info "${RED}  ✘${END} ${WHITE}$d"
            mal_domains+=("$d")
        fi
    done
}

HOST_IP=127.0.0.1
WIN_HOSTS_PATH="C:\\Windows\\System32\\drivers\\etc\\hosts"
mal_domains=()
domains=${#DOMAINS[@]}

if [[ "$AC_LOCAL" == true ]]; then
    check_host_arg=""
    [[ $DRY_RUN -eq 1 ]] && { check_host_arg="--quiet"; }
    check_host_domains "$check_host_arg"
    if (( ${#mal_domains[@]} > 0 )); then
        log_info "${HEADER}Set Local Domains"
        #-------------------------------------------
        [[ "$DRY_RUN" == 1 ]] && { mal_domains=(); }
        case "$PLATFORM" in
        linux|mac)
            log_info "${BODY}Update Unix hosts"
            unix_hosts_edit
            ;;
        wsl)
            log_info "${BODY}Update Windows hosts"
            windows_hosts_edit
            ;;
        *)
            critical_exit "Platform $PLATFORM is unsupported."
            ;;
        esac
        [[ $DRY_RUN -eq 0 ]] && { check_host_domains ""; }
    fi

    if (( ${#mal_domains[@]} == 0 )); then
        completion="Success!"
    elif (( ${#mal_domains[@]} < domains )); then
        completion="Partial!"
    else
        completion="Fail!"
    fi
else
    if (( domains == ${#subdomains[@]} )); then
        completion="Success!"
    elif (( domains > 0 )); then
        completion="Partial!"
    else
        completion="Fail!"
    fi
fi

emoji='😛'
if [[ "$completion" == "Partial!" ]]; then emoji='😒'; \
elif [[ "$completion" == "Fail!" ]]; then emoji='😖'; fi

log_info "${END}$emoji ${HEADER}$completion"
#-------------------------------------------

if [[ "$AC" != true ]]; then
    echo -e "${INFO} 👉 ${BOLD_MAGENTA}Next steps:${END}"
    echo -e "${INFO} ${BLUE}1.${END} ${GREEN}Change into $directory:${END}"
    echo -e "${INFO}   ${WHITE}cd $directory${END}"
    echo -e "${INFO} ${BLUE}2.${END} ${GREEN}Run suite_services.py:${END}"
    echo -e "${INFO}   ${WHITE}python suite_services.py --profile ai-all --operation start${END}"
    echo -e "${INFO} 🚀 ${GREEN}Confirm everything is running from the console output${END}"
fi

local_access() {
    [[ "$completion" == "Success!" ]] && return
    echo -e "${INFO} 👉 ${BOLD_MAGENTA}Next steps:${END}" || :
    echo -e "${INFO} ${GREEN}Manually configure these domains in:${END}"
    echo -e "${INFO}   ${WHITE}$HOSTS_PATH${END}${GREEN}.${END}"
    for d in "${mal_domains[@]}"; do
        echo -e "${INFO} ${WHITE}  -${END} ${CYAN}${HOST_IP}${END} ${WHITE}$d${END}"
    done
    local console="console"
    local copy_cmd="sudo cp"
    if [[ "$PLATFORM" == "wsl" ]]; then
        console="console, as administrator"
        copy_cmd="cp"
    fi
    local hosts_directory
    hosts_directory=$(dirname "${HOSTS_PATH}")
    local hosts_file
    hosts_file=$(basename "${HOSTS_PATH}")
    local domain_entry="${WHITE}ip-address   domain${END}${GREEN}"
    local save_command="${END}${WHITE}Esc${END}${GREEN},${END} ${WHITE}:wq${END}${GREEN}"
    local your_domain="${END} ${WHITE}$protocol://$WEBUI_DOMAIN${END}${GREEN}"
    echo -e "${INFO} ${BLUE}1.${END} ${GREEN}Upon completion of the ${APP_NAME} installation,${END}"
    echo -e "${INFO}     ${GREEN}edit your hosts file so your domains will loop${END}"
    echo -e "${INFO}     ${GREEN}back to your machine - just like localhost.${END}"
    echo -e "${INFO}   ${BLUE}1a.${END} ${GREEN}Create a backup of the original hosts file.${END}"
    echo -e "${INFO}      ${GREEN}From a ${CYAN}Bash${END} ${GREEN}$console, execute:${END}"
    echo -e "${INFO}      ${WHITE}cd $hosts_directory${END}"
    echo -e "${INFO}      ${WHITE}ts=\$(date +%Y%m%d%H%M%S)${END}"
    echo -e "${INFO}      ${WHITE}$copy_cmd $hosts_file $hosts_file.bak.\$ts${END}"
    echo -e "${INFO}   ${BLUE}1b.${END} ${GREEN}Open the $hosts_file file in your editor."
    echo -e "${INFO}     ${GREEN}Here, I am using${END} ${CYAN}vim${END}${GREEN}.${END}"
    echo -e "${INFO}      ${WHITE}sudo vim $hosts_file${END}"
    echo -e "${INFO}   ${BLUE}1c.${END} ${GREEN}Add domain entries with format: $domain_entry.${END}"
    echo -e "${INFO}      ${GREEN}Save $hosts_file and quit ($save_command) your editor.${END}"
    echo -e "${INFO}   ${BLUE}1d.${END} ${GREEN}In your browser, navigate to $your_domain.${END}"
    echo -e "${INFO} 🚀 ${GREEN}Confirm everything is running.${END}"
}

global_access() {
echo -e "${INFO} 🌐 ${BLUE}To access ${APP_NAME} from the internet,${END} \
${BLUE}ensure your firewall allows traffic on ports${END} \
${WHITE}80${END} ${BLUE}and${END} ${WHITE}443${END}"
}

if [[ "${AC_LOCAL}" == true ]]; then local_access; else global_access; fi

exit 0