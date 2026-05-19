#!/bin/bash
# Trevor SANDY
# Last Update May, 19 2026
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

VERSION="0.4.0"

# If AC is unset we assume the script is being run manually
# shellcheck disable=SC1091
[[ -z ${AC+x} && -f access/.ac.env ]] && {
set -a && source access/.ac.env && set +a ; }

if [[ -n ${AC_USE_SUDO+x} ]]; then
    read -rs -t 0.1 AC_SUDO_PASSWORD || true
fi

# https://stackoverflow.com/a/28085062/18954618
: "${CI:=false}"
: "${APP_NAME:="AI-Suite"}"
: "${WITH_REDIS:=false}"
: "${SUDO_USER:="$(whoami)"}"
: "${DEBUG_ON:=false}"
: "${BACKUP:=1}"      # on local install, backup hosts file before update
: "${VERBOSE:=1}"     # toggle verbose messages in hosts edit payload script
: "${SILENT:=$([[ "$CI" == true ]] && echo 1 || echo 0)}"
: "${DRY_RUN:=$([[ "$DEBUG_ON" == true ]] && echo 1 || echo 0)}"

# Reset BASH time counter
SECONDS=0

# Colors
SGR=''
END=''
# Core SGR support detection
if [[ "${SILENT:-0}" == 0 && -t 1 ]]; then
    if colors=$(tput colors 2>/dev/null) && [[ "$colors" -ge 8 ]]; then
        SGR=$'\033['
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
PROMPT="${APP} PROMPT"
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

    COLON="${SGR}97m:"
    APP="${SGR}${ITALIC}94m${APP_NAME}${COLON}${END}"
fi

# Log level names
declare -A LOG_LEVEL_NAME=(
    [NOTICE]='NOTICE'
    [PROMPT]='PROMPT'
    [CRITICAL]='CRITICAL'
    [ERROR]='ERROR'
    [WARNING]='WARNING'
    [DEBUG]='DEBUG'
    [INFO]='INFO'
)

# Log level styles
declare -A LOG_LEVEL_STYLE=(
    [NOTICE]="${SGR}${BOLD}95m"     # MAGENTA
    [PROMPT]="${SGR}${BOLD}92m"     # GREEN
    [CRITICAL]="${SGR}${BOLD}41m"   # RED_BG
    [ERROR]="${SGR}${BOLD}91m"      # RED
    [WARNING]="${SGR}${BOLD}${UNDERLINE}93m" # YELLOW
    [DEBUG]="${SGR}${BOLD}97m"      # WHITE
    [INFO]="${SGR}36m"              # CYAN
)

# Log message styles
declare -A LOG_MESSAGE_STYLE=(
    [NOTICE]="$BOLD_MAGENTA"
    [PROMPT]="$GREEN"
    [CRITICAL]="$ITALIC_RED_BG"
    [ERROR]="$RED"
    [WARNING]="$UNDERLINE_YELLOW"
    [DEBUG]="$WHITE"
    [INFO]="$DIM_CYAN"
)

# Prefix cache (precomputed for speed)
log_header_prefix() {
    local -n _ref=$1
    local level=$2
    local prefix
    if [[ -n "$SGR" ]]; then
        prefix="${APP} ${LOG_LEVEL_STYLE[$level]}${LOG_LEVEL_NAME[$level]}${END}"
    else
        prefix="${APP} ${LOG_LEVEL_NAME[$level]}"
    fi
    _ref=$prefix
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

    if [[ -n "$SGR" && "$*" == *$'\033['* ]]; then
        message="${END}$*"
    else
        message="${message}$*"
    fi

    if [[ "$LOG_TIMESTAMP" == true ]]; then
        printf -v header '%(%Y-%m-%d %H:%M:%S)T %s' -1 "$header"
    fi

    if [[ "$level" == CRITICAL || "$level" == ERROR ]]; then
        printf '%s %s%s\n' "$header" "$message" "$END" >&2
    else
        printf '%s %s%s\n' "$header" "$message" "$END"
    fi
}

# Semantic tokens
log_header_prefix PROMPT 'PROMPT'
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

strip_sgr() {
    local line sgr=$'\033'
    while IFS= read -r line; do
        while [[ $line == *"${sgr}["*m* ]]; do
            line="${line/${sgr}\[[0-79;]\{1,11\}m/}"
        done
        printf '%s\n' "$line"
    done
    # - The substitution regex explained:
    # line            original line
    # /               substitution delimeter '/'
    # $sgr            match the SGR escape sequence '\x1b' before the color or attribute code
    # \[              matches the first open bracket - escape '\[' to distinguish from regex [
    # [0-79;]\{1,11\} matches '1 to 11' of any character in '012345679;' - escape the curly braces
    #                 with '\{' to keep the shell from mangling them
    #                 we have 11 times due to bold, dim, italic, underline and color * 2 plus reset * 1
    # m               match the SGR escape sequence reset character 'm' - this trails the color code
    # /               substitution delimeter '/'
}

# Real-time tee with SGR stripping
SCRIPT="${BASH_SOURCE[0]##*/}"
if [[ "$SCRIPT" == "${0##*/}" ]]; then
    LOG_PATH="${AC_LOG_PATH:-$PWD}"
    LOG="$LOG_PATH/$SCRIPT.log"
    [[ -f "$LOG" && -r "$LOG" ]] && rm "$LOG"
    # Strip SGR color sequence codes from output"
    exec > >(tee >(strip_sgr >>"$LOG"))
    exec 2> >(tee >(strip_sgr >>"$LOG") >&2)
fi

# Capture elapsed execution time
# shellcheck disable=SC2329
finish_elapsed_time() {
    set +x
    local ELAPSED
    ELAPSED="$((SECONDS / 3600))hrs $(((SECONDS / 60) % 60))min $((SECONDS % 60))sec"
    printf '%s\n' "${INFO} ${CYAN}Elapsed time:${END} ${GREEN}$ELAPSED${END}"
    printf '%s\n' "${INFO} ${GREEN}-------------------------------------------${END}"
}

# shellcheck disable=SC2329
finish () {
    local vars=(AC_SUDO_PASSWORD AC_PASSWORD password confirm_password)
    local var
    for var in "${vars[@]}"; do [ -v "$var" ] && unset "$var" ; done

    rm -rf "$gen_tmpdir" 2>/dev/null

    local header="${END}✅ ${HEADER}"
    local status="Completed"

    if [ "$completion" == "Success!" ]; then
        :
    elif [ "$completion" == "Partial!" ]; then
        header="${END}⚠️ ${HEADER}"
        status="Finished"
    else
        header="${END}❌ ${SGR}${BOLD}${UNDERLINE}91m"
        status="Terminated"
    fi

    if [ "$status" == "Completed" ]; then
        local bin binaries=()
        for bin in "$yq_bin" "$up_bin"; do [ -f "$bin" ] && binaries+=("$bin") ; done
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
  SILENT:int      No prompt for elevated privilege - 1 when CI=true, default: $SILENT
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

  AC_SEARXNG:false       Configure proxy for SearXNG domain name
  AC_LLAMA:false         Configure proxy for LLAMA (LLaMA.cpp/Ollama) domain name
  AC_LLAMACPP:false      Using LLaMA.cpp LLM (instead of Ollama)

  AC_USE_SUDO:false        Using Sudo so read AC_SUDO_PASSWORD
  AC_OPENCLAW_SANDBOX:None Configure Docker OpenClaw gateway sandbox

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
    log_debug "subdomains - args @ (${#@}): ${*}"
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
    log_debug "subdomains - init (${#subdomains[@]}): ${subdomains[*]}"
}

completion=''
subdomains=()
with_authelia=false
using_sudo_user=false
proxy='caddy'
install_type='Default'
user_confirm='Default'
config_mode="Interactive"
up_ver="v1.1.0"
up_bin='./access/url-parser'
yq_ver="v4.53.2" # v4.45.4
yq_bin='./access/yq'

PLATFORM='unknown'
HOST_IP='127.0.0.1'
HOSTS_PATH='/etc/hosts'
WIN_HOSTS_PATH='C:\\Windows\\System32\\drivers\\etc\\hosts'

[ "${DEBUG_ON}" == true ] && log_debug "Enabled"

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

if [ "$AC" == true ]; then
    SUDO_USER="${AC_SUDO_USER}"
    with_authelia="${AC_WITH_AUTHELIA}"
    WITH_REDIS="${AC_WITH_REDIS}"
    proxy="${AC_PROXY}"
    if [[ $(declare -p AC_SUBDOMAINS 2>/dev/null) == declare\ -a* ]]; then
        [[ ${#AC_SUBDOMAINS[@]} -ne 0 ]] && \
        update_subdomains "${AC_SUBDOMAINS[@]}"
    fi
    if [ "$AC_CONFIRM" == true ]; then
        user_confirm="Email notification"
    fi
    config_mode="Auto-configuration"
    if [ "$AC_LOCAL" == true ]; then
        install_type="Private (Local)"
    else
        install_type="Public (Global)"
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
else
    : "${AC:=false}"
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
    [[ "$CI" == true ]] && \
    config_mode="Continuous integration"
fi

# Set all subdomains if no subdomain specified
if (( ${#subdomains[@]} == 0 )); then
    subdomains+=(open-webui openclaw n8n supabase flowise langfuse searxng neo4j llamacpp ollama)
fi
log_info "${HEADER}Subdomains (${#subdomains[@]})"
#-------------------------------------------
for subdoman in $(printf '%s\n' "${subdomains[@]}" | sort); do
    log_info "${BODY}$subdoman"
done

log_info "${HEADER}Configuration Summary"
#-------------------------------------------
log_info "${BODY}Name:${END} ${WHITE}${APP_NAME}"
log_info "${BODY}Proxy:${END} ${WHITE}${proxy}"
log_info "${BODY}Authelia 2FA:${END} ${WHITE}${with_authelia}"
log_info "${BODY}Redis:${END} ${WHITE}${WITH_REDIS}"
log_info "${BODY}Setup Mode:${END} ${WHITE}${config_mode}"
log_info "${BODY}Installation:${END} ${WHITE}${install_type}"
log_info "${BODY}User Confirmation:${END} ${WHITE}${user_confirm}"
log_info "${BODY}Log File:${END} ${WHITE}${LOG}"

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
        HOSTS_PATH=$(wslpath "$WIN_HOSTS_PATH")
        PLATFORM="wsl"
    else
        PLATFORM="linux"
    fi
    ;;
darwin*) PLATFORM="mac" ;;
err) critical_exit "Unsupported platform." ;;
esac

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

hosts_write_uac() {
    local -n _ref=$1
    local var
    # shellcheck disable=SC2016
    IFS= read -r var < <(
        powershell.exe -NoProfile -Command '
          $HostsPath  = [System.IO.Path]::GetFullPath("'"$2"'");
          $TargetPath = [System.IO.Path]::GetFullPath("'"$3"'");
          [int]([string]::Equals($HostsPath,$TargetPath,
                [System.StringComparison]::OrdinalIgnoreCase))'
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

packages=(curl wget jq openssl node git)

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

brew_package_is_installed() {
    brew list --formula | while IFS= read -r p; do
        [ "$p" = "$1" ] && return 0
    done
    return 1
}

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
    brew) brew_package_is_installed httpd || { local i=0; } ;;
    *) type "${package}" > /dev/null 2>&1 || { local i=0; } ;;
    esac
    if [ "$i" == 1 ]; then
        log_info "${GREEN}  ✔${END} ${WHITE}${package}"
    else
        log_info "${RED}  ✘${END} ${WHITE}${package}"
    fi
    return $i
}

sudo_prompt() {
    if [[ -n "${AC_SUDO_PASSWORD+x}" ]]; then
        (printf '%s\n' "$AC_SUDO_PASSWORD" | sudo -S -v >/dev/null 2>&1)
    fi
}

unix_privilege() {
    local -n _ref=$1
    if is_unix_root ""; then
        _ref='is_unix__root'
        return
    fi
    if command -v sudo >/dev/null 2>&1; then
        if sudo -n true 2>/dev/null; then
            _ref='has_sudo__pass_set'
        else
            _ref='has_sudo__needs_pass'
        fi
        return
    fi
    if command -v su >/dev/null 2>&1; then
        _ref='has_su__needs_pass'
        return
    fi
    _ref='none'
}

run_pkg_cmd() {
    local cmd=$*
    local pld=0
    local user_privilege
    unix_privilege user_privilege
    if [[ "$user_privilege" == "is_unix__root" ]]; then
        log_info "${BODY}Running as${END} ${WHITE}Root"
    else
        local user="user with no privilege"
        case "$user_privilege" in
        has_su__*) user="${END}${WHITE}Super User" ;;
        has_sudo__*) user="User with${END} ${WHITE}sudo${END} ${GREEN}privilege" ;;
        esac
        log_info "${BODY}Running as $user"
    fi
    [[ "$1" == "-payload" ]] && { pld=1; cmd=$2; }
    case "$user_privilege" in
    is_unix__root)
        if [[ $pld -eq 0 ]]; then $cmd; else bash -c "$cmd"; fi
        ;;
    has_sudo__pass_set)
        # shellcheck disable=SC2086
        if [[ $pld -eq 0 ]]; then sudo $cmd; else sudo bash -c "$cmd"; fi
        ;;
    has_sudo__needs_pass)
        [[ "$SILENT" -eq 1 ]] && critical_exit "Silent mode requires passwordless sudo."
        sudo_prompt
        # shellcheck disable=SC2086
        if [[ $pld -eq 0 ]]; then sudo $cmd; else sudo bash -c "$cmd"; fi
        ;;
    has_su__needs_pass)
        [[ "$SILENT" -eq 1 ]] && critical_exit "Silent mode cannot use su."
        if [[ $pld -eq 0 ]]; then su -c "$cmd"; else su -s /bin/bash -c "$cmd"; fi
        ;;
    none)
        critical_exit "No privilege escalation available."
        ;;
    esac
}

install_packages() {
    case "${package_manager}" in
    apt-get)
        export DEBIAN_FRONTEND="noninteractive"
        run_pkg_cmd apt-get update
        run_pkg_cmd apt-get install -y "${packages[@]}"
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

if [ "$AC" == true ]; then
    directory="$PWD"
else
    directory="$(basename "$repo_url")"
fi

if [[ "$AC" == true && -d "$directory" ]]; then
    log_info "Working directory: $directory"
elif [ -d "$directory" ]; then
    log_info "$directory directory present, skipping git clone"
else
    repo_url="https://github.com/trevorsandy/ai-suite"
    log_info "Cloning repository from ${repo_url}..."
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
if [ ! -x "$up_bin" ]; then
    repo_base="https://github.com/singh-inder"
    log_info "Downloading url-parser $up_ver from ${repo_base}/url-parser..."
    download_binary "${repo_base}"/url-parser/releases/download/"$up_ver"/url-parser-"$os"-"$arch" "$up_bin"
fi

if [ ! -x "$yq_bin" ]; then
    log_info "Downloading yq $yq_ver from https://github.com/mikefarah/yq..."
    download_binary https://github.com/mikefarah/yq/releases/download/"$yq_ver"/yq_"$os"_"$arch" "$yq_bin"
fi

bin_status () { if test -x "$1"; then echo "${GREEN}  ✔"; else echo "${RED}  ✘"; fi }
log_info "$(bin_status "$up_bin")${END} ${WHITE}url_parser $up_ver - Singh Inder"
log_info "$(bin_status "$yq_bin") ${WHITE}yq $yq_ver - Mike Farah"

format_prompt() { echo -e "${PROMPT} ${GREEN}$1${END}"; }

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
    local max=35
    [[ "$#" -gt 1 ]] && { max=${1:-35}; shift; }
    local str="$*"
    local len=${#str}
    if (( len > max )); then printf '%s...' "${str:0:max-3}"; else printf '%s' "$str"; fi
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

construct_domain_var() {
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

    log_debug " ${WHITE}-${END}    ${YELLOW}$var:${END} ${WHITE}$_ref"
    export _ref
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

unset_domain_vars() {
    local sub var
    for sub in "${subdomains[@]}"; do
        domain_var var "$sub"
        declare -p "$var" &>/dev/null || continue
        unset "$var"
        log_debug "Unset domain variable: $var"
    done
}

export_domain_vars() {
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

validate_domain_vars() {
    local i sub var val
    for (( i=0; i<${#subdomains[@]}; i++ )); do
        sub="${subdomains[$i]}"
        domain_var var "$sub"
        if declare -p "$var" &>/dev/null; then
            val="${DOMAINS[$i]}"
            log_notice "${WHITE}-${END}    ${MAGENTA}${var}:${END} ${CYAN}${val}"
        else
            log_notice "${WHITE}-${END}    ${YELLOW}${var}${END} ${WHITE}is not declared"
        fi
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

    : "${up_bin:?url parser binary is not set}"
    [[ $(declare -p subdomains 2>/dev/null) == declare\ -a* ]] || \
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
            if ! _protocol="$("$up_bin" --url "$url" --get scheme 2>/dev/null)"; then
                log_error "Could not extract protocol from hostname URL: $url."
                url="" && _protocol=""
            fi
        fi

        if ! _host="$("$up_bin" --url "$url" --get host 2>/dev/null)"; then
            log_error "Could not extract host from hostname URL: $url."
            url="" && _host=""
        fi
        if ! _registered_domain="$("$up_bin" --url "$url" --get registeredDomain 2>/dev/null)"; then
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
        construct_domain_var "$subdomain"
    else
        local sub
        for sub in "${subdomains[@]}"; do
            construct_domain_var "$sub"
        done
    fi
}

log_info "${BODY}Set domain names from subdomains - Docker containers"

# If 'subdomain' argument is empty, all AI Suite domains will be populated.
set_domain_names

log_info "${BODY}Confirm domain name environment variables"

validate_domain_vars

log_info "${BODY}Domain name attributes"

log_info "${BODY}   protocol:${END} ${WHITE}$protocol"
log_info "${BODY}   host (${APP_NAME}):${END} ${WHITE}$host"
log_info "${BODY}   registered_domain:${END} ${WHITE}$registered_domain"

SUPABASE_domain='localhost'
declare -p SUPABASE_DOMAIN &>/dev/null && \
SUPABASE_domain=$SUPABASE_DOMAIN

log_info "${BODY}SUPABASE_PUBLIC_URL:${END} ${WHITE}$protocol://$SUPABASE_domain"
declare -p N8N_DOMAIN &>/dev/null && \
log_info "${BODY}N8N WEBHOOK_URL:${END} ${WHITE}$protocol://$N8N_DOMAIN"

n8n_encrypt_key_status="New key generated by $APP_NAME"
if [[ -z ${N8N_ENCRYPTION_KEY+x} ]]; then
    [[ -f n8n/.n8n.encryption.key ]] && {
        while IFS='=' read -r key val || [[ -n "$key" ]]; do
            [[ -z "$key" || "$key" == \#* ]] && continue
            [[ -z "$val" ]] && continue
            export "$key=$val"
        done < n8n/.n8n.encryption.key
        [[ -n ${N8N_ENCRYPTION_KEY+x} ]] && \
        n8n_encrypt_key_status="Existing key imported from file"
    }
else
    n8n_encrypt_key_status="Existing key set from environment variable"
fi
log_info "${BODY}N8N_ENCRYPTION_KEY:${END} ${WHITE}$n8n_encrypt_key_status"

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
        setup_redis="$WITH_REDIS"
    elif [[ "$AC" == true ]]; then
        email="$AC_EMAIL"
        display_name="$AC_DISPLAY_NAME"
        setup_redis="${AC_WITH_REDIS}"
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

log_info "${HEADER}Configure Secret Generators"
#-------------------------------------------
declare -A SECRETS
# In caddy basic_auth, hashed password is loaded in memory
# In nginx basic_auth, websites slows down a lot if bcrypt rounds number is
# high as the hashed password file is checked again and again on every request.
# This is only applicable when using basic_auth, not with authelia
bcrypt_rounds=12
if [[ "$proxy" == "nginx" && "$with_authelia" == false ]]; then bcrypt_rounds=6; fi

# https://www.baeldung.com/linux/bcrypt-hash#using-htpasswd
bcrypt_password=$(htpasswd -bnBC "$bcrypt_rounds" "" "$password" | cut -d : -f 2)

# shellcheck disable=SC2329
gen_bcrypt() { printf '%s' "${bcrypt_password}"; }

# shellcheck disable=SC2329
gen_hex() { openssl rand -hex "${1:-32}"; }

gen_base64() { openssl rand -base64 "${1:-32}"; }

base64_url_encode() { openssl enc -base64 -A | tr '+/' '-_' | tr -d '='; }

SECRETS[jwt_secret]="$(gen_base64 30)"

# iat and exp for anon and svc_role tokens has to be same thats why initializing here
iat=$(date +%s)
# log_info "${BODY}Anonomous User and Sevice Role token issued on: $iat"

exp=$(("$iat" + 5 * 3600 * 24 * 365)) # 5 years expiry
# log_info "${BODY}Anonomous User and Sevice Role token expire on: $exp"

header='{"typ":"JWT","alg":"HS256"}'

gen_tmpdir=""
gen_new_supabase_auth_keys () {
    # shellcheck disable=SC1091
    [[ -s "$HOME/.nvm/nvm.sh" ]] && . "$HOME/.nvm/nvm.sh"

    log_info "${BODY}Node.js version: $(node -v)"
    # log_debug "Node.js process.execPath: $(node -p 'process.execPath')"

    gen_tmpdir=$(mktemp -d)

    # Generate EC P-256 private key
    openssl ecparam -name prime256v1 -genkey -noout -out "$gen_tmpdir/ec_private.pem" 2>/dev/null

    # Node.js does the crypto-heavy work:
    #   - PEM -> JWK conversion
    #   - JWKS construction (with symmetric key included)
    #   - ES256 JWT signing
    #   - Opaque API key generation with checksum
    node -e '
const crypto = require("crypto");
const fs = require("fs");

const pem = fs.readFileSync(process.argv[1]);
const jwtSecret = process.argv[2];

// EC key -> JWK
const privateKey = crypto.createPrivateKey(pem);
const jwkPrivate = privateKey.export({ format: "jwk" });

const kid = crypto.randomUUID();

// Symmetric key as JWK (base64url-encoded)
const octKey = {
    kty: "oct",
    k: Buffer.from(jwtSecret).toString("base64url"),
    alg: "HS256"
};

// JWKS with private key (for Auth to sign tokens)
const jwksKeypair = { keys: [
    { kty: "EC", kid, use: "sig", key_ops: ["sign", "verify"], alg: "ES256", ext: true,
      crv: jwkPrivate.crv, x: jwkPrivate.x, y: jwkPrivate.y, d: jwkPrivate.d },
    octKey
]};

// JWKS with public key only (for PostgREST, Realtime, Storage to verify)
const jwksPublic = { keys: [
    { kty: "EC", kid, use: "sig", key_ops: ["verify"], alg: "ES256", ext: true,
      crv: jwkPrivate.crv, x: jwkPrivate.x, y: jwkPrivate.y },
    octKey
]};

// Sign ES256 JWT
function signES256(payload) {
    const header = { alg: "ES256", typ: "JWT", kid };
    const b64Header = Buffer.from(JSON.stringify(header)).toString("base64url");
    const b64Payload = Buffer.from(JSON.stringify(payload)).toString("base64url");
    const data = b64Header + "." + b64Payload;
    const sig = crypto.sign("SHA256", Buffer.from(data), {
        key: privateKey,
        dsaEncoding: "ieee-p1363"
    }).toString("base64url");
    return data + "." + sig;
}

const iat = Math.floor(Date.now() / 1000);
const exp = iat + 5 * 365 * 24 * 3600; // 5 years

const anonJwt = signES256({ role: "anon", iss: "supabase", iat, exp });
const serviceJwt = signES256({ role: "service_role", iss: "supabase", iat, exp });

// Generate opaque API keys with checksum
const PROJECT_REF = "supabase-self-hosted";

function generateOpaqueKey(prefix) {
    const random = crypto.randomBytes(17).toString("base64url").slice(0, 22);
    const intermediate = prefix + random;
    const checksum = crypto.createHash("sha256")
        .update(PROJECT_REF + "|" + intermediate)
        .digest("base64url")
        .slice(0, 8);
    return intermediate + "_" + checksum;
}

const publishableKey = generateOpaqueKey("sb_publishable_");
const secretKey = generateOpaqueKey("sb_secret_");

// Output as KEY=value lines for shell to parse
console.log("SUPABASE_PUBLISHABLE_KEY=" + publishableKey);
console.log("SUPABASE_SECRET_KEY=" + secretKey);
console.log("ANON_KEY_ASYMMETRIC=" + anonJwt);
console.log("SERVICE_ROLE_KEY_ASYMMETRIC=" + serviceJwt);
console.log("JWT_KEYS=" + JSON.stringify(jwksKeypair.keys));
console.log("JWT_JWKS=" + JSON.stringify(jwksPublic));
' "${gen_tmpdir}/ec_private.pem" "${SECRETS[jwt_secret]}" > "${gen_tmpdir}/output"

    [[ -f "${gen_tmpdir}/output" ]] || { log_error "${gen_tmpdir}/output not found"; return 1; }
    log_info "${BODY}Generate EC P-256 asymmetric key pair and opaque API keys"
    while IFS='=' read -r key val; do
        [[ -z "$key" ]] && continue
        val="${val%$'\r'}"
        case "$key" in
            SUPABASE_PUBLISHABLE_KEY) SECRETS[op_client]="$val" ;;
            SUPABASE_SECRET_KEY) SECRETS[op_server]="$val" ;;
            ANON_KEY_ASYMMETRIC) SECRETS[anon_asym]="$val" ;;
            SERVICE_ROLE_KEY_ASYMMETRIC) SECRETS[service_role_asym]="$val" ;;
            JWT_KEYS) SECRETS[jwt_keys]="$val" ;;
            JWT_JWKS) SECRETS[jwt_jwks]="$val" ;;
        esac
    done < "${gen_tmpdir}/output"
}

# shellcheck disable=SC2329
gen_token() {
    [[ "$1" =~ ^[0-9]+$ ]] && {
        (( $1 < 1 || $1 > 512 )) && return 1
        gen_base64 "$1"
        return 0
    }
    log_info "${BODY}Generate legacy symmetric JWT API $1 key"
    local payload header_base64 payload_base64
    payload=$(jq -nc ".role=\"$1\" | .iss=\"supabase\" | .iat=($iat | tonumber) | .exp=($exp | tonumber)")
    header_base64=$(printf %s "$header" | base64_url_encode)
    payload_base64=$(printf %s "$payload" | base64_url_encode)
    local signed_content="${header_base64}.${payload_base64}"
    local signature
    signature=$(printf %s "$signed_content" | openssl dgst -binary -sha256 -hmac "${SECRETS[jwt_secret]}" | base64_url_encode)
    SECRETS["${1}_sym"]="${signed_content}.${signature}"
}

gen_new_supabase_auth_keys
gen_token "anon"
gen_token "service_role"

# shellcheck disable=SC2329
gen_key() {
    case "$1" in
    secret) printf '%s' "${SECRETS[jwt_secret]}" ;;
    keys) printf '%s' "${SECRETS[jwt_keys]}" ;;
    jwks) printf '%s' "${SECRETS[jwt_jwks]}" ;;
    client) printf '%s' "${SECRETS[op_client]}" ;;
    server) printf '%s' "${SECRETS[op_server]}" ;;
    anon_asym) printf '%s' "${SECRETS[anon_asym]}" ;;
    service_role_asym) printf '%s' "${SECRETS[service_role_asym]}" ;;
    anon_sym) printf '%s' "${SECRETS[anon_sym]}" ;;
    service_role_sym) printf '%s' "${SECRETS[service_role_sym]}" ;;
    *) log_error "Invalid key: $1"; return 1 ;;
    esac
}

# shellcheck disable=SC2329
gen_n8ncrypt() {
    [[ -n ${N8N_ENCRYPTION_KEY+x} ]] && {
        printf '%s' "${N8N_ENCRYPTION_KEY}"
        return
    }
    gen_hex 32
}

log_info "${BODY}Proxy:${END} ${WHITE}$proxy"
log_info "${BODY}Auto confirm:${END} ${WHITE}$auto_confirm"
log_info "${BODY}With Authelia:${END} ${WHITE}$with_authelia"
log_info "${BODY}Setup Redis:${END} ${WHITE}$WITH_REDIS"
log_info "${BODY}User name:${END} ${WHITE}$username"
log_info "${BODY}Display name:${END} ${WHITE}$display_name"
log_info "${BODY}Email:${END} ${WHITE}$email"

log_info "${BODY}Sudo user:${END} ${WHITE}${SUDO_USER}"
log_info "${BODY}Using sudo user:${END} ${WHITE}$using_sudo_user"

# Create .env file from .env.example template
log_info "${HEADER}Generate .env File"
#-------------------------------------------
rename() {
    local src="${1:?source file required}"
    local dst="${2:?destination file required}"
    mv_backup=''
    if [[ -f $dst ]]; then
        mv_backup="${dst}.bak.$(date +%Y%m%d%H%M%S)"
        cp "$dst" "$mv_backup" || { log_error "Backup failed for $dst"; return 1; }
    fi
    [[ -f $src ]] || { log_error "File $src" not found; return 1; }
    mv -f "$src" "$dst" || { log_error "Rename failed for $dst"; return 1; }
}

restore() {
    local dst="${1:?destination file required}"
    [[ -f "$mv_backup" ]] && {
        [[ $mv_backup =~ $dst.bak.* ]] || \
        { log_error "File $mv_backup is not a backup of $dst"; return 1; }
        rm -f "$dst" 2>/dev/null
        mv -f "$mv_backup" "$dst" || { log_error "Restore failed for $dst"; return 1; }
        log_info "${BODY}  File $dst restored"
        mv_backup=''
    }
}

cleanup () {
    [[ -n $mv_backup ]] || return 0
    [[ -f $mv_backup ]] && rm -f "$mv_backup" 2>/dev/null;
}

normalize_lines() {
    local ending=$'\n' # LF - Linux/macOS
    for f in "$@"; do
        [ -f "$f" ] || continue
        tmp="${f}.tmp.$$"
        awk -v e="$ending" '{ sub(/\r$/, ""); printf "%s%s", $0, e }' "$f" > "$tmp" &&
        mv -f "$tmp" "$f"
    done
}

generate_dot_env_file() {
    local template_path="${1:-${ENV_TEMPLATE_FILE:-.env.example}}"
    local compose_path="${2:-${COMPOSE_FILE:-docker-compose.yml}}"
    local dot_env_path="${ENV_FILE:-.env}"
    local template_count=0
    local compose_count=0
    local dot_env_count=0
    local generated_count=0
    local inherited_count=0
    local default_count=0
    local written_count=0
    local compose_files=()
    local TEMPLATE_KEYS=()     # preserves template order
    declare -A TEMPLATE ENV    # .env.example template defaults
    declare -A DOT_ENV_VARS=() # existing .env vars
    declare -A COMPOSE_VARS=() # compose interpolation vars
    declare -A GENERATORS=(    # external secret generators
        [gen_n8ncrypt]=gen_n8ncrypt
        [gen_bcrypt]=gen_bcrypt
        [gen_token]=gen_token
        [gen_hex]=gen_hex
        [gen_key]=gen_key
    )

    # shellcheck disable=SC2153
    if [[ $(declare -p COMPOSE_FILES 2>/dev/null) == declare\ -a* ]]; then
        [[ ${#COMPOSE_FILES[@]} -ne 0 ]] && compose_files=(COMPOSE_FILES[@])
    else
        compose_files=("${compose_path}")
    fi

    load_template_vars() {
        local template_file="$1"
        [[ -f "$template_file" ]] || return 0
        log_info "${BODY}Load variables default from $template_file"
        normalize_lines "$template_file"
        declare -A allowed=()
        for sub in "${subdomains[@]}"; do
            local base=${sub/open-webui/WEBUI}
            base=${base//-/_}
            local key="${base^^}_HOSTNAME"
            allowed["$key"]=1
        done
        allowed["WEBHOOK_URL"]=1
        allowed["N8N_PROTOCOL"]=1
        allowed["N8N_PROXY_HOPS"]=1
        allowed["LETSENCRYPT_EMAIL"]=1
        local allowed_count=0
        local check_allowed=true
        while IFS='=' read -r key val || [[ -n "$key" ]]; do
            [[ -z "$key" ]] && continue
            if [[ "$key" =~ ^[[:space:]]*\# ]]; then
                if $check_allowed; then
                    key="${key#\#}"
                    key="${key# }"
                    [[ -z "$key" ]] && continue
                    if [[ -z ${allowed[$key]-} ]]; then
                        continue
                    else
                        ((++allowed_count))
                        [[ $allowed_count -eq ${#allowed[@]} ]] && check_allowed=false
                    fi
                else
                    continue
                fi
            fi
            val="${val%$'\r'}"
            TEMPLATE["$key"]="$val"
            ENV["$key"]="$val"
            TEMPLATE_KEYS+=("$key")
        done < "$template_file"
    }

    load_dot_env_vars() {
        local file_path="$1"
        [[ -f "$file_path" ]] || return 0
        log_info "${BODY}Overlay variables from existing $file_path"
        normalize_lines "$file_path"
        while IFS='=' read -r key val; do
            [[ -z "$key" || "$key" =~ ^[[:space:]]*\# ]] && continue
            if [[ -n ${TEMPLATE[$key]+x} ]]; then
                ENV["$key"]="${val%$'\r'}"
            else
                ENV["$key"]="${val%$'\r'}"
                DOT_ENV_VARS["$key"]="${val%$'\r'}"
            fi
        done < "$file_path"
    }

    load_compose_vars() {
        local compose_file="$1"
        [[ -f "$compose_file" ]] || return 0
        log_info "${BODY}Load variables from $compose_file"
        normalize_lines "$compose_file"
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            while [[ $line =~ \$\{([A-Za-z0-9_]+)(:?[-+?])?(.*)\} ]]; do
                local var="${BASH_REMATCH[1]}"
                local op="${BASH_REMATCH[2]}"
                local val="${BASH_REMATCH[3]}"
                local match="${BASH_REMATCH[0]}"
                [[ "$op" == *"+"* || "$op" == *"?"* ]] && break
                [[ -n ${COMPOSE_VARS["$compose_file:$var"]+x} ]] && break
                [[ -n ${TEMPLATE[$var]+x} || -n ${ENV[$var]+x} ]] && break
                COMPOSE_VARS["$compose_file:$var"]="$val"
                line="${line//"$match"/}"
            done
        done < "$compose_file"
    }

    iterate_compose_vars() {
        local compose_file key var
        for compose_file in "${compose_files[@]}"; do
            for var in $(
                for key in "${!COMPOSE_VARS[@]}"; do
                    [[ ${key%%:*} == "$compose_file" ]] && printf '%s\n' "${key#*:}"
                done | sort
            ); do
                printf '%s|%s|%s\n' "$compose_file" "$var" \
                    "${COMPOSE_VARS["$compose_file:$var"]}"
            done
        done
    }

    ensure_projects_path() {
        if [[ -z "${ENV[PROJECTS_PATH]-}" ]]; then
            local projects_path="~/projects"
            if is_wsl; then
                local win_home
                if [[ -n "${USERPROFILE:-}" ]]; then
                    win_home="$USERPROFILE"
                elif command -v cmd.exe >/dev/null 2>&1; then
                    win_home="$(cmd.exe /c "echo %USERPROFILE%" 2>/dev/null | tr -d '\r')"
                else
                    win_home="${HOME}"
                fi
                projects_path="${win_home%[\\/]}\\projects"
            fi
            ENV["PROJECTS_PATH"]="$projects_path"
            if [[ -z ${TEMPLATE[PROJECTS_PATH]+x} ]]; then
                TEMPLATE_KEYS+=("PROJECTS_PATH")
            fi
            TEMPLATE["PROJECTS_PATH"]="$projects_path"
            log_info "${BODY}  PROJECTS_PATH${MAGENTA}=${WHITE}${projects_path} ${CYAN}(auto)"
        fi
    }

    resolve_dot_env_vars() {
        log_info "${BODY}Resolve variables from $template_path"
        for var in "${TEMPLATE_KEYS[@]}"; do
            local val="${ENV[$var]-}"
            local tmpl_val="${TEMPLATE[$var]-}"
            if [[ $val == generate\ using\ * ]]; then
                local spec="${val#generate using }"
                local gen="${spec%%:*}"
                local arg="${spec#*:}"
                [[ "$spec" == "$gen" ]] && arg=""
                [[ -n ${GENERATORS[$gen]+x} ]] || \
                { log_error "Unknown secret generator: $gen"; return 1; }
                val=$(
                    if [[ -n "$arg" ]]; then
                        "${GENERATORS[$gen]}" "${arg%$'\r'}"
                    else
                        "${GENERATORS[$gen]}"
                    fi
                )
                val="${val//$'\n'/}"   # remove newlines
                log_info "${BODY}  $(elide "$var")${MAGENTA}=${WHITE}$(elide "$val") ${CYAN}$gen${arg:+:$arg}"
                val="${val//$/$$}"     # escape bcrypt chars in docker-compose
                ((++generated_count))
            elif [[ -n "$val" ]]; then
                ((++inherited_count))
                log_info "${BODY}  $(elide "$var")${MAGENTA}=${WHITE}$(elide "$val")"
            else
                val="$tmpl_val"
                ENV["$var"]="$val"
                ((++default_count))
                log_info "${BODY}  $(elide "$var")${MAGENTA}=${WHITE}$(elide "$val")"
            fi
            ENV["$var"]="$val"
        done
        if [[ ${#DOT_ENV_VARS[@]} -gt 0 ]]; then
            log_info "${BODY}Resolve variables from existing .env"
            for dot_env_var in $(printf '%s\n' "${!DOT_ENV_VARS[@]}" | sort); do
                ((++inherited_count))
                log_info "${BODY}  $dot_env_var${MAGENTA}=${WHITE}${DOT_ENV_VARS[$dot_env_var]}"
            done
        fi
        local last_file=""
        while IFS='|' read -r compose_file var default; do
            if [[ "$compose_file" != "$last_file" ]]; then
                last_file="$compose_file"
                log_info "${BODY}Resolve variables from $compose_file"
            fi
            ENV["$var"]="$default"
            ((++inherited_count))
            log_info "${BODY}  $var${MAGENTA}=${WHITE}${default}"
        done < <(iterate_compose_vars)
    }

    write_dot_env() {
        local output_file="${1:-${ENV_FILE:-.env}}"
        local tmp
        tmp=$(mktemp)
        local date_time
        date_time="$(date +%Y/%m/%d-%H:%M:%S)"
        local lines_count=0
        template_count=${#TEMPLATE_KEYS[@]}
        dot_env_count=${#DOT_ENV_VARS[@]}
        log_info "${BODY}Write variables to $output_file"
        printf '# Generated by %s from %s on %s\n' "$APP_NAME" "$template_path" "$date_time" >> "$tmp"
        ((++template_count)); ((++lines_count))
        for key in "${TEMPLATE_KEYS[@]}"; do
            printf '%s=%s\n' "$key" "${ENV[$key]-}" >> "$tmp"
            ((++lines_count))
        done
        if [[ $dot_env_count -gt 0 ]]; then
            printf '\n# Variables not in %s\n' "$template_path" >> "$tmp"
            ((dot_env_count+=2)); ((lines_count+=2))
            for dot_env_var in $(printf '%s\n' "${!DOT_ENV_VARS[@]}" | sort); do
                printf '%s=%s\n' "$dot_env_var" "${DOT_ENV_VARS[$dot_env_var]}" >> "$tmp"
                ((++lines_count))
            done
        fi
        local last_file=""
        while IFS='|' read -r compose_file var default; do
            if [[ "$compose_file" != "$last_file" ]]; then
                printf '\n# Variables from %s\n' "$compose_file" >> "$tmp"
                ((compose_count+=2)); ((lines_count+=2))
                last_file="$compose_file"
            fi
            if [[ -n "$default" ]]; then
                printf '%s=%s\n' "$var" "$default" >> "$tmp"
            else
                printf '%s=\n' "$var" >> "$tmp"
            fi
            ((++compose_count)); ((++lines_count))
        done < <(iterate_compose_vars)
        # ---------- Lines sanity check ----------
        local expected_count=0
        expected_count=$(( template_count + dot_env_count + compose_count ))
        if [[ "$lines_count" -lt "$expected_count" ]]; then
            log_error "Sanity check failed: .env has fewer lines ($lines_count) than expected ($expected_count)"
            rm -f "$tmp"
            return 1
        fi
        rename "$tmp" "$output_file"
        # ---------- Written sanity check ----------
        written_count=$(wc -l < "$output_file")
        if [[ "$written_count" -ne "$lines_count" ]]; then
            log_error "Sanity check failed: written .env lines ($written_count) differ from staged ($lines_count)"
            restore "$output_file"
            return 1
        fi
        cleanup
        log_info "${BODY}  .env file written successfully"
    }

    # ---------- Summarize ----------
    summarize_results() {
        log_info "${BODY}Variables summary:"
        log_info "${BODY}  Generated: ${WHITE}$generated_count"
        log_info "${BODY}  Inherited: ${WHITE}$inherited_count"
        log_info "${BODY}  Defaults : ${WHITE}$default_count"
        log_info "${BODY}  Template : ${WHITE}$template_count"
        [[ $dot_env_count -gt 0 ]] && \
        log_info "${BODY}  Dot Env  : ${WHITE}$dot_env_count"
        log_info "${BODY}  Compose  : ${WHITE}$compose_count"
        log_info "${BODY}Lines summary:"
        log_info "${BODY}  Written  : ${WHITE}$written_count"
    }

    # ---------- Execution flow ----------
    load_template_vars "$template_path"
    load_dot_env_vars "$dot_env_path"
    load_compose_vars "$compose_path"
    load_compose_vars "supabase/docker/docker-compose.yml"
    ensure_projects_path
    resolve_dot_env_vars
    write_dot_env
    summarize_results
}

# shellcheck disable=SC2120
uncomment_compose_vars() {
    local compose_path="${1:-${COMPOSE_FILE:-docker-compose.yml}}"
    [[ -f "$compose_path" ]] || return 0
    shift || true
    local vars=("$@")
    [[ ${#vars[@]} -eq 0 ]] && \
    vars=(N8N_HOST N8N_PORT N8N_PROTOCOL N8N_PROXY_HOPS)
    local vars_count=0
    local check_vars=true
    local tmp="${compose_path}.tmp.$$"
    local initial_count=0
    initial_count=$(wc -l < "$compose_path")
    while IFS= read -r line; do
        line="${line%$'\r'}"
        [[ $check_vars == true ]] && \
        for var in "${vars[@]}"; do
            if [[ $line =~ ^([[:space:]]*)\#(.*) ]] && [[ "$line" == *"\${$var"* ]]; then
                line="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"  # remove leading #
                if [[ $line =~ ^[[:space:]]*-[[:space:]]*(.*)=(.*) ]]; then
                    local key="${BASH_REMATCH[1]}"
                    local val="${BASH_REMATCH[2]}"
                    log_info "${BODY}  ${key}${MAGENTA}=${WHITE}$(elide "$val")"
                fi
                (( ++vars_count ))
                [[ $vars_count -eq ${#vars[@]} ]] && check_vars=false
                break
            fi
        done
        printf '%s\n' "$line" >> "$tmp"
    done < "$compose_path"
    rename "$tmp" "$compose_path"
    local written_count
    written_count=$(wc -l < "$compose_path")
    if [[ "$written_count" -ne "$initial_count" ]]; then
        log_error "Sanity check failed: written $compose_path lines ($written_count) differ from expected ($initial_count)"
        restore "$compose_path"
        return 1
    fi
    cleanup
    log_info "${BODY}  File $compose_path lines summary:"
    log_info "${BODY}    Initial: ${WHITE}$initial_count"
    log_info "${BODY}    Updated: ${WHITE}$vars_count"
    log_info "${BODY}    Final  : ${WHITE}$written_count"
}

# Update yaml file using yq package
# https://github.com/mikefarah/yq/issues/465#issuecomment-2265381565
update_yaml_file() {
    local yaml_file="$2"
    local initial_count=0
    initial_count=$(wc -l < "$yaml_file")
    IFS=$'\n' read -ra la <<< "$1"
    local update_count="${#la[@]}"
    local tmp="$yaml_file.tmp.$$"
    cp "$yaml_file" "$tmp"

    sed -i '/^\r\{0,1\}$/s// #BLANK_LINE/' "$tmp"
    "$yq_bin" eval -i "$1" "$tmp"
    sed -i "s/ *#BLANK_LINE//g" "$tmp"

    local staged_count
    staged_count=$(wc -l < "$tmp")
    local changed_count
    changed_count=$(( staged_count - initial_count ))
    rename "$tmp" "$yaml_file"
    local written_count
    written_count=$(wc -l < "$yaml_file")
    if [[ "$written_count" -ne "$staged_count" ]]; then
        log_error "Sanity check failed: written $yaml_file lines ($written_count) differ from staged ($staged_count)"
        restore "$yaml_file"
        return 1
    fi
    cleanup
    log_info "${BODY}  File $yaml_file lines summary:"
    log_info "${BODY}    Initial: ${WHITE}$initial_count"
    log_info "${BODY}    Changed: ${WHITE}$changed_count"
    log_info "${BODY}    Updated: ${WHITE}$update_count"
    log_info "${BODY}    Final  : ${WHITE}$written_count"
}

# Create env_vars list to append .env file
dot_env_vars=()
update_dot_env_vars() {
    for env_key_val in "$@"; do
        dot_env_vars+=("$env_key_val")
    done
}

write_dot_env_vars() {
    local env_vars=("$@")
    local dot_env_path="${ENV_FILE:-.env}"
    [[ -f "$dot_env_path" ]] || return 0
    local tmp="${dot_env_path}.tmp.$$"
    local updated_count=0
    local appended_count=0
    local initial_count=0
    initial_count=$(wc -l < "$dot_env_path")
    cp "$dot_env_path" "$tmp"
    [[ ${#env_vars[@]} -eq 0 ]] && \
    env_vars=("${dot_env_vars[@]}")
    for env_var in "${env_vars[@]}"; do
        IFS='=' read -r key val <<< "$env_var"
        [[ -z "$key" ]] && continue
        if cat "$tmp" | grep -q "^${key}"; then
            log_info "${BODY}Update ${key}: ${WHITE}${val}"
            sed -i "s|${key}.*|${key}=${val}|" "$tmp"
            ((++updated_count))
        else
            log_info "${BODY}Append ${key}:${END} ${WHITE}${val}"
            printf '%s=%s\n' "${key}" "${val}" >> "$tmp"
            ((++appended_count))
        fi
    done
    local expected_count=0
    expected_count=$(( initial_count + appended_count ))
    rename "$tmp" "$dot_env_path"
    local written_count
    written_count=$(wc -l < "$dot_env_path")
    if [[ "$written_count" -ne "$expected_count" ]]; then
        log_error "Sanity check failed: written .env lines ($written_count) differ from expected ($expected_count)"
        restore "$dot_env_path"
        return 1
    fi
    cleanup
    log_info "${BODY}  File $dot_env_path lines summary:"
    log_info "${BODY}    Initial : ${WHITE}$initial_count"
    log_info "${BODY}    Updated : ${WHITE}$updated_count"
    log_info "${BODY}    Appended: ${WHITE}$appended_count"
    log_info "${BODY}    Final   : ${WHITE}$written_count"
}

compose_path="docker-compose.yml"

log_info "${BODY}Enable n8n proxy variables in $compose_path"
uncomment_compose_vars

generate_dot_env_file

openclaw_compose_path="./openclaw/$compose_path"
if [[ -f "$openclaw_compose_path" ]]; then
    log_info "${HEADER}Rebuild OpenClaw Services"
    #-------------------------------------------
    # Rebuild OpenClaw services with service name and container names
    log_info "${BODY}Rebuild services with service name and container names"
    # shellcheck disable=SC2016
    openclaw_service_yaml='
    {
      "name": "openclaw"
    }
    +
    (
      .services |= (
        to_entries
        | map(
            .value = (
              {
                "image": .value.image,
                "container_name": (.value.container_name // .key)
              }
              +
              (
                .value
                | with_entries(
                    select(.key != "image" and .key != "container_name")
                  )
              )
            )
          )
        | from_entries
      )
    )
    '
    update_yaml_file "$openclaw_service_yaml" "$openclaw_compose_path"

    # Add openclaw-gateway build args and set pull_policy for locally built image
    if [[ -n ${AC_OPENCLAW_SANDBOX+x} ]]; then
        log_info "${BODY}Add openclaw-gateway build args and set image pull_policy"
        # shellcheck disable=SC2016
        openclaw_service_yaml='
        .services."openclaw-gateway" |= (
          . as $orig |
          # Rebuild in desired order, then merge original
          {
            "image": "${OPENCLAW_IMAGE:-openclaw:local}",
            "pull_policy": "never"
          }
          * $orig
          # Normalize/enrich build
          | .build |= (
              (select(tag == "!!str") | {
                "context": .,
                "args": {
                  "OPENCLAW_INSTALL_DOCKER_CLI": "${OPENCLAW_INSTALL_DOCKER_CLI:-}"
                }
              })
              //
              (. * {
                "args": {
                  "OPENCLAW_INSTALL_DOCKER_CLI": "${OPENCLAW_INSTALL_DOCKER_CLI:-}"
                }
              })
            )
        ) |
        .services."openclaw-cli" |= (
          {
            "image": "openclaw:local",
            "pull_policy": "never"
          } * .
        )
        '
        update_yaml_file "$openclaw_service_yaml" "$openclaw_compose_path"
    fi
fi

log_info "${HEADER}Configure Proxy Service"
#-------------------------------------------
# DEFINE PROXY service
proxy_service_yaml=".services.$proxy.profiles=[\"$proxy\"] |
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

# DEFINE nginx.template and Nginx Docker service insert
else
    log_info "${BODY}Define nginx.template and Nginx Docker service insert"
    #-------------------------------------------
    update_dot_env_vars "NGINX_SERVER_NAME=$host"
    # docker compose nginx service command directive. Passed via yq strenv
    nginx_cmd=""

    nginx_local_volume="./access/nginx"
    # path in local fs where nginx template file is stored
    nginx_local_template_file="$nginx_local_volume/addons/nginx.template"

    # path inside container where template file will be mounted
    nginx_container_template_file="/etc/nginx/user_conf.d/nginx.template"

    # Pass an array of args to nginx service command directive https://stackoverflow.com/a/57821785/18954618
    # output multiline string from yq https://mikefarah.gitbook.io/yq/operators/string-operators#string-blocks-bash-and-newlines

    proxy_service_yaml="${proxy_service_yaml} |
                        .services.nginx.image=\"jonasal/nginx-certbot:6.0.1-nginx1.29.5\" |
                        .services.nginx.expose=[\"81/tcp\",\"443/tcp\",\"443/udp\",\"80/tcp\"] |
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
    update_dot_env_vars "PROXY_AUTH_USERNAME=$username"

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
nginx_cmd="${nginx_cmd:=""}" update_yaml_file "$proxy_service_yaml" "$compose_path"

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
    authelia_tmp=$(mktemp)
    yaml_path=".users.$username" display_name="$display_name" bcrypt_password="$bcrypt_password" email="$email" \
        "$yq_bin" -n 'eval(strenv(yaml_path)).displayname = strenv(display_name) |
               eval(strenv(yaml_path)).password = strenv(bcrypt_password) |
               eval(strenv(yaml_path)).email = strenv(email) |
               eval(strenv(yaml_path)).groups = ["admins","dev"] |
               .. style="double" |
               eval(strenv(yaml_path)).disabled = false' >"$authelia_tmp"
    # Authelia sets ownership to root so use run_pkg_cmd to run with sudo
    run_pkg_cmd mv "$authelia_tmp" ./access/authelia/users_database.yml

    # DEFINE AUTHELIA configuration.yml file
    log_info "${BODY}Define Authelia configuration.yml file"
    #-------------------------------------------
    authelia_config_file_yaml="
            .access_control.rules[0].domain=strenv(webui_domain) |
            .access_control.rules[1].domain=strenv(n8n_domain) |
            .access_control.rules[2].domain=strenv(openclaw_domain) |
            .access_control.rules[3].domain=strenv(flowise_domain) |
            .access_control.rules[4].domain=strenv(langfuse_domain) |
            .access_control.rules[5].domain=strenv(supabase_domain) |
            .access_control.rules[6].domain=strenv(searxng_domain) |
            .access_control.rules[7].domain=strenv(neo4j_domain) |
            .access_control.rules[8].domain=strenv(llama_domain) |
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

    # DEFINE AUTHELIA configuration.yml file
    log_info "${BODY}Define Authelia Docker service"
    #-------------------------------------------

    # shellcheck disable=SC2016
    authelia_docker_service_yaml='.services.authelia.profiles=["authelia"] |
       .services.authelia.container_name = "authelia" |
       .services.authelia.image = "authelia/authelia:4.38" |
       .services.authelia.restart = "unless-stopped" |
       .services.authelia.expose = [9091] |
       .services.authelia.volumes = ["./access/authelia:/config"] |
       .services.authelia.environment = {
         "AUTHELIA_STORAGE_POSTGRES_ADDRESS": "tcp://db:5432",
         "AUTHELIA_STORAGE_POSTGRES_USERNAME": "postgres",
         "AUTHELIA_STORAGE_POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
         "AUTHELIA_STORAGE_POSTGRES_DATABASE": "${POSTGRES_DB}",
         "AUTHELIA_STORAGE_POSTGRES_SCHEMA": strenv(authelia_schema),
         "AUTHELIA_SESSION_SECRET": "${AUTHELIA_SESSION_SECRET:?error}",
         "AUTHELIA_STORAGE_ENCRYPTION_KEY": "${AUTHELIA_STORAGE_ENCRYPTION_KEY:?error}",
         "AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET": "${AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET:?error}"
       } |
       .services.authelia.depends_on.db.condition = "service_healthy" |
       .services.authelia.healthcheck.disable = false'

    authelia_volume="./volumes/db/schema-authelia.sh:/docker-entrypoint-initdb.d/schema-authelia.sh"
    # shellcheck disable=SC2016
    authelia_docker_supabase_service_yaml='.services.db.environment.AUTHELIA_SCHEMA = strenv(authelia_schema) |
        .services.db.volumes |= ((. // []) as $v | $v + (["'"$authelia_volume"'"] - $v))'

    if [[ "$WITH_REDIS" == true ]]; then
        log_info "${BODY}Authelia Redis configuration in $compose_path"
        #-------------------------------------------
        redis_docker_service_yaml=".services.authelia.profiles=[\"$proxy\", \"n8n\", \"langfuse\", \"ai-all\"]"
        update_yaml_file "$redis_docker_service_yaml" "$compose_path"

        authelia_config_file_yaml="${authelia_config_file_yaml}|.session.redis.host=\"redis\" | .session.redis.port=6379"
        authelia_docker_service_yaml="${authelia_docker_service_yaml}|.services.authelia.depends_on.redis.condition=\"service_healthy\""
    fi

    # TODO - modify _url to use domain versus host (subdomain.domain)
    # WRITE AUTHELIA configuration.yml file (Supabase target)
    log_info "${BODY}Write Authelia configuration.yml file"
    #-------------------------------------------
    (
        export_domain_vars
        host="$host" \
        registered_domain="$registered_domain" \
        authelia_url="$protocol://$WEBUI_DOMAIN/authenticate" \
        redirect_url="$protocol://$WEBUI_DOMAIN" \
        update_yaml_file "$authelia_config_file_yaml" "./access/authelia/configuration.yml"
    )

    # WRITE AUTHELIA service to docker-compose.yml file
    log_info "${BODY}Write Authelia service to docker-compose.yml file"
    #-------------------------------------------
    authelia_schema="authelia" update_yaml_file "$authelia_docker_service_yaml" "$compose_path"

    # WRITE AUTHELIA service to Supabase docker-compose.yml file
    log_info "${BODY}Write Authelia service to Supabase docker-compose.yml file"
    #-------------------------------------------
    authelia_schema="authelia" update_yaml_file "$authelia_docker_supabase_service_yaml" "./supabase/docker/$compose_path"
fi

# TODO: Setup Exim SMTP server if AC_WITH_EXIM == true (AC_WITH_EXIM is not yet supported)

[[ ${#dot_env_vars[@]} -gt 0 ]] && {
# WRITE env_vars to .env file
log_info "${HEADER}Write Additional .env Variables"
#-------------------------------------------
write_dot_env_vars "${dot_env_vars[@]}"
}

# Docker:         http://host.docker.internal:<port>
# Local:          http://localhost:<port>
# Local (proxy):  https://local.pc:<port>
# Global:         https://my-ai-suite.fr:<port>

# | Ex | In | Service                 | Container - Docker internal       | Domain - Docker external |
# | -: | -: | ----------------------: | --------------------------------: | -----------------------: |
# | ++ |    | `n8n`                   | n8n:5678/                         | localhost:5678/          |
# | ++ |    | `OpenClaw`              | openclaw-gateway:18789/           | localhost:18789/          |
# | ++ |    | `Open WebUI`            | open-webui:8080/                  | localhost:8080/          |
# | ++ | ++ | `Flowise`               | flowise:3001/                     | localhost:3001/          |
# |    | ++ | `Open webUI MCPO`       | open-webui-mcpo:8090/             | localhost:8090/          |
# |    | ++ | `MCP Gateway`           | mcp-gateway:8060/                 | localhost:8060/          |
# |    | ++ | `Open webUI Filesystem` | open-webui-filesystem:8091/docs/  | localhost:8091/docs/     |
# |    | ++ | `Redis`                 | redis:6379/                       | localhost:6379/          |
# |    | ++ | `MinIO`                 | minio:9001/                       | localhost:9001/          |
# |    | ++ | `QDrant`                | qdrant:6333/dashboard/            | localhost:6333/dashboard/|
# | ++ | ++ | `Subabase`              | supabase-kong:8000                | localhost:8000           |
# |    | ++ | `Logflare`              | supabase-analytics:4000/dashboard/| localhost:4000/dashboard/|
# |    | ++ | `PostgreSQL`            | postgres:5432                     | localhost:5432/          |
# | ++ |    | `Langfuse Web`          | langfuse-web:3000/                | localhost:3000/          |
# |    | ++ | `Langfuse Worker`       | langfuse-worker:3030/             | localhost:3030/          |
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
import /etc/caddy/addons/cors.conf {
    # Global options - works for both environments
    email {\$LETSENCRYPT_EMAIL}
}

(configuration) {
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
    import configuration
    # For domains, Caddy will automatically use Let's Encrypt
    # For localhost/port addresses, HTTPS won't be enabled
    reverse_proxy n8n:5678
}

# OPENCLAW
{\$OPENCLAW_HOSTNAME} {
    import configuration
    reverse_proxy openclaw-gateway:18789
}

# Open WebUI
{\$WEBUI_HOSTNAME} {
    import configuration
    reverse_proxy open-webui:8080
}

# Flowise
{\$FLOWISE_HOSTNAME} {
    import configuration
    reverse_proxy flowise:3001
}

# Langfuse
{\$LANGFUSE_HOSTNAME} {
    import configuration
    reverse_proxy langfuse-web:3000
}

# Supabase
{\$SUPABASE_HOSTNAME} {
    import configuration
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
    import configuration
    reverse_proxy neo4j:7474
}

# SearXNG
$([[ $AC_SEARXNG == true ]] && echo "\
{\$SEARXNG_HOSTNAME} {" || echo "\
{DISABLED_SEARXNG} {")
    import configuration
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

$(if [[ $AC_LLAMA == true ]]; then \
  [[ $AC_LLAMACPP == false ]] && echo "\
# Ollama API
{\$OLLAMA_HOSTNAME} {
    reverse_proxy ollama:11434
}" || echo "\
# LLaMA.cpp API
{\$LLAMACPP_HOSTNAME} {
    import configuration
    reverse_proxy llamacpp:8040
}"; fi)
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

upstream openclaw_upstream {
    server openclaw-gateway:18789;
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

$([[ $AC_SEARXNG == true ]] && echo "\
upstream searxng_upstream {
    server searxng:8081;
    keepalive 2;
}")

$(if [[ $AC_LLAMA == true ]]; then \
  [[ $AC_LLAMACPP == false ]] && echo "\
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

    # OpenClaw
    location /openclaw {
        proxy_pass http://openclaw_upstream
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

    $([[ $AC_SEARXNG == true ]] && echo "\
    # SearXNG
    location /searxng {
        proxy_pass http://searxng_upstream
    }")

    $(if [[ $AC_LLAMA == true ]]; then \
      [[ $AC_LLAMACPP == false ]] && echo "\
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
managed_hosts_edit() {
    local return_code=0
    local error_log="${LOG}"
    local date_time
    date_time="$(date +%Y/%m/%d-%H:%M:%S)"
    local header="# >>> $APP_NAME Local Domains Begin >>>"
    local footer="# <<< $APP_NAME Local Domains End <<<"
    case "$PLATFORM" in
    linux|mac)
        local privilege
        unix_privilege privilege
        local domains
        domains=$(printf '"%s" ' "${DOMAINS[@]}")
        local payload
        # Single-quote heredoc so no escape needed but also no expansion
        read -r -d '' payload <<'EOF' || true
#!/usr/bin/env bash
# __DATE_TIME__ Edit hosts, update __APP_NAME__ local domains

set -euo pipefail

DOMAINS=(__DOMAINS__)
DRY_RUN=__DRY_RUN__
BACKUP=__BACKUP__
SILENT=__SILENT__
VERBOSE=__VERBOSE__
SGR_SEQ='__SGR_SEQ__'
HOST_IP="__HOST_IP__"
APP_NAME="__APP_NAME__"
HOSTS_PATH="__HOSTS_PATH__"
PRIVILEGE="__PRIVILEGE__"
DATE_TIME="__DATE_TIME__"
HEADER="__HEADER__"
FOOTER="__FOOTER__"

#------------------------

SGR=''
END=''
WHITE=''
BOLD_CYAN=''
BOLD_YELLOW=''
APP="${APP_NAME}:"
if [[ "$SILENT" == 0 && -n "$SGR_SEQ" ]]; then
    SGR="$SGR_SEQ"
    END="${SGR}0m"
    WHITE="${SGR}37m"
    BOLD_CYAN="${SGR}1;36m"
    BOLD_YELLOW="${SGR}1;33m"
    APP="${SGR}3;94m${APP_NAME}${END}${SGR}97m:${END}"
fi

log() {
    local COL="${BOLD_CYAN}"
    local pfx="INFO"
    local msg="${WHITE}${1:-}${END}"
    [[ "$DRY_RUN" -eq 1 ]] && {
    COL="${BOLD_YELLOW}"; pfx="DRY-RUN"; }
    printf '%s %s%s%s %s\n' "${APP}" "${COL}" "${pfx}" "${END}" "${msg}"
}
logv() { [[ "$VERBOSE" -eq 1 ]] && log "$*" ; }

snapshot_lines() {
    local file=$1
    local count=${2:-5}
    logv "Snapshot first $count lines:"
    head -n "$count" "$file" | nl -w2 -s'. ' | while read -r l; do logv "$l"; done
    logv "Snapshot last $count lines:"
    tail -n "$count" "$file" | nl -w2 -s'. ' | while read -r l; do logv "$l"; done
}

hosts_tmp=$(mktemp /tmp/hosts.XXXXXX)
chmod 644 "$hosts_tmp"

declare -A existing_map
EXISTING=()

found_block=0
inside_block=0

if [[ ! -f "$HOSTS_PATH" ]]; then
    log "Error: Hosts file not found."
    exit 1
fi

line_count=$(wc -l < "$HOSTS_PATH")

#------------------------
# Scan existing hosts
#------------------------
while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$HEADER" ]]; then
        inside_block=1
        found_block=1
        continue
    fi
    if [[ "$line" == "$FOOTER" ]]; then
        inside_block=0
        continue
    fi

    if (( inside_block )); then
        set -- $line
        [[ $# -ge 2 ]] && EXISTING+=("$2")
        continue
    fi
done < "$HOSTS_PATH"

log "Hosts file loaded."
logv "Lines read: $line_count"
snapshot_lines "$HOSTS_PATH"

# Build map for O(1) lookup
for d in "${EXISTING[@]}"; do existing_map[$d]=1; done

#------------------------
# Determine changes
#------------------------
update_required=0
domains_added=0
domains_unchanged=0
domains_removed=0

for d in "${DOMAINS[@]}"; do
    if [[ -n "${existing_map[$d]:-}" ]]; then
        log "Keep domain: $d"
        ((++domains_unchanged))
    else
        log "Add domain: $d"
        ((++domains_added))
        update_required=1
    fi
done

declare -A desired_map
for d in "${DOMAINS[@]}"; do desired_map[$d]=1; done
for d in "${EXISTING[@]}"; do
    if [[ -z "${desired_map[$d]:-}" ]]; then
        log "Remove domain: $d"
        ((++domains_removed))
        update_required=1
    fi
done

((domains_unchanged>0)) && logv "Domains unchanged: $domains_unchanged"
((domains_added>0)) && logv "Domains added: $domains_added"
((domains_removed>0)) && logv "Domains removed: $domains_removed"

if [[ $update_required -eq 0 ]]; then
    log "$DATE_TIME Hosts file already up to date."
    exit 0
fi

#------------------------
# Optional backup
#------------------------
if [[ "$BACKUP" -eq 1 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log "Backup: $HOSTS_PATH"
    else
        backup_file="$HOSTS_PATH.bak.$(date +%Y%m%d%H%M%S)"
        cp "$HOSTS_PATH" "$backup_file"
        chmod 644 "$backup_file"
        log "Backup created: $backup_file"
    fi
fi

#------------------------
# Optimized Reconstruction (Single-Pass)
#------------------------
{
    inside_block=0
    block_written=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "$HEADER" ]]; then
            inside_block=1
            found_block=1

            # Write replacement block once
            if (( block_written == 0 )); then
                echo "$HEADER"
                for d in "${DOMAINS[@]}"; do
                    echo -e "$HOST_IP\t$d"
                done
                echo "$FOOTER"
                block_written=1
            fi
            continue
        fi

        if [[ "$line" == "$FOOTER" ]]; then
            inside_block=0
            continue
        fi

        (( inside_block )) && continue

        # Lines outside the managed block
        echo "$line"

    done < "$HOSTS_PATH"

    # Append managed block if no block existed
    if (( found_block == 0 )); then
        echo "$HEADER"
        for d in "${DOMAINS[@]}"; do
            echo -e "$HOST_IP\t$d"
        done
        echo "$FOOTER"
    fi

} > "$hosts_tmp"

lines_written=$(wc -l < "$hosts_tmp")
logv "Lines written: $lines_written"
snapshot_lines "$hosts_tmp"

#------------------------
# Atomic write with sanity check + rollback
#------------------------
if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Hosts file NOT modified."
else
    ms=0.2
    max_attempts=5
    for attempt in $(seq 1 $max_attempts); do
        mv -f "$hosts_tmp" "$HOSTS_PATH" || sleep $ms
        chown root:root "$HOSTS_PATH"
        lines_actual=$(wc -l < "$HOSTS_PATH")
        if [[ "$lines_written" -eq "$lines_actual" ]]; then
            log "$DATE_TIME: Hosts file updated successfully."
            break
        elif [[ $attempt -eq $max_attempts ]]; then
            log "Error: Atomic write failed after $max_attempts attempts."
            [[ -f "$backup_file" ]] && {
                mv -f "$backup_file" "$HOSTS_PATH" || sleep $ms
                chown root:root "$HOSTS_PATH"
                log "$DATE_TIME: Hosts restored from backup."
            }
            exit 1
        else
            logv "Write attempt $attempt failed, retrying..."
            sleep $ms
        fi
    done
fi
EOF

        #---------------------------------------------
        # Inject payload environment variables
        #---------------------------------------------
        payload="${payload//__SGR_SEQ__/$SGR}"
        payload="${payload//__PRIVILEGE__/$privilege}"
        payload="${payload//__DOMAINS__/$domains}"
        payload="${payload//__DRY_RUN__/$DRY_RUN}"
        payload="${payload//__SILENT__/$SILENT}"
        payload="${payload//__VERBOSE__/$VERBOSE}"
        payload="${payload//__BACKUP__/$BACKUP}"
        payload="${payload//__DATE_TIME__/$date_time}"
        payload="${payload//__APP_NAME__/$APP_NAME}"
        payload="${payload//__HOSTS_PATH__/$HOSTS_PATH}"
        payload="${payload//__HOST_IP__/$HOST_IP}"
        payload="${payload//__HEADER__/$header}"
        payload="${payload//__FOOTER__/$footer}"

        log_debug "Hosts edit payload:"
        printf '%s' "$payload"

        run_pkg_cmd -payload "$payload"
        return_code=$?
        ;;
    wsl)
        local role="User"
        local elevated=false
        if is_windows_admin elevated; then
            role="Administrator"
        fi
        if [[ "$SILENT" -eq 1 && "$elevated" != true ]]; then
            critical_exit "Silent mode requires Administrator privilege."
        fi
        log_info "${BODY}Running as${END} ${WHITE}$role"
        local target_path='C:\\Windows\\System32\\drivers\\etc\\hosts'
        local restricted=false
        if hosts_write_uac restricted "$WIN_HOSTS_PATH" "$target_path"; then
            log_info "${BODY}Hosts file access is${END} ${WHITE}restricted"
        else
            log_info "${BODY}Hosts file access is${END} ${WHITE}open"
        fi
        if [[ $SILENT -eq 1 && "$elevated" != true ]]; then
            critical_exit "Silent mode requires Administrator privilege."
        fi
        local date_stamp
        date_stamp=$(date +%Y%m%d%H%M%S)
        local script_name="hosts_win_${date_stamp}.ps1"
        local win_temp_dir
        # shellcheck disable=SC2016
        win_temp_dir=$(powershell.exe -NoProfile -Command '$env:TEMP' | tr -d '\r')

        local win_log_path
        win_log_path=$(wslpath -w "${LOG}")
        win_log_path="${win_log_path//.sh.log/.ps.log}"
        log_debug "WIN_LOG_PATH: $win_log_path"

        local posix_log_path
        posix_log_path=$(wslpath "${win_log_path}")
        log_debug "POSIX_LOG_PATH: $posix_log_path"

        local win_script_path="${win_temp_dir}\\$script_name"
        log_debug "WIN_SCRIPT_PATH: $win_script_path"

        local posix_script_path
        posix_script_path=$(wslpath "$win_script_path")
        log_debug "POSIX_SCRIPT_PATH: $posix_script_path"

        local win_ps_launcher_path="${win_temp_dir}\\ps_launcher_${date_stamp}.ps1"
        log_debug "WIN_PS_LAUNCHER_PATH: $win_ps_launcher_path"

        local posix_ps_launcher_path
        posix_ps_launcher_path=$(wslpath "$win_ps_launcher_path")
        log_debug "POSIX_PS_LAUNCHER_PATH: $posix_ps_launcher_path"

        local win_rc_path="${win_temp_dir}\\hosts_rc_${$}_${date_stamp}.tmp"
        log_debug "WIN_RC_PATH: $win_rc_path"

        local posix_rc_path
        posix_rc_path="$(wslpath "${win_rc_path}")"
        log_debug "POSIX_RC_PATH: $posix_rc_path"

        local domains_ps
        domains_ps=$(printf '"%s",' "${DOMAINS[@]}")
        domains_ps="@(${domains_ps%,})"

        #---------------------------------------------
        # Construct PowerShell payload
        #---------------------------------------------
        # Single-quote heredoc so no escape needed but also no expansion
        local ps_payload
        read -r -d '' ps_payload <<'PSH' || true
# __DATE_TIME__ Edit hosts, update __APP_NAME__ local domains

param()
$Domains     = __DOMAINS__
$DryRun      = __DRY_RUN__
$Backup      = __BACKUP__
$Verbose     = __VERBOSE__
$HostIp      = "__HOST_IP__"
$AppName     = "__APP_NAME__"
$Header      = "__HEADER__"
$Footer      = "__FOOTER__"
$DateTime    = "__DATE_TIME__"
$LogPath     = '__LOG_PATH__'
$PsRcPath    = '__PS_RC_PATH__'
$HostsPath   = [System.IO.Path]::GetFullPath('__HOSTS_PATH__')
$TargetPath  = "$env:SystemDrive\\Windows\\System32\\drivers\\etc\\hosts"
$Restricted  = [string]::Equals($HostsPath, $TargetPath)
$Elevated    = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Log {
    param( [string]$Message = "" )
    $Prefix = if ($DryRun) { "DRY-RUN" } else { "INFO" }
    $Record = ("{0}: {1} {2}" -f $AppName, $Prefix, $Message)
    try { Add-Content -Path $LogPath -Value $Record -Encoding utf8 }
    catch { Write-Warning "${AppName}: Failed to write to log: $_" }
}

function LogV {
    param([string]$Message = "")
    if ($Verbose -ne 1) { return }
    Log "$Message"
}

function SnapshotLines {
    param([string[]]$Lines, [int]$Count = 5)
    $Hdr = if ($DryRun) { "${AppName}: DRY-RUN" } else { "${AppName}: INFO" }
    @{ First = ($Lines | Select-Object -First $Count |
           ForEach-Object -Begin { $n = 0 } -Process { "{0} {1}. {2}" -f $Hdr, (++$n), $_ }
         ) -join [Environment]::NewLine
       Last  = ($Lines | Select-Object -Last $Count |
           ForEach-Object -Begin { $n = 0 } -Process { "{0} {1}. {2}" -f $Hdr, (++$n), $_ }
         ) -join [Environment]::NewLine
    }
}

function SetDomains {
    param( [string[]]$Lines, [string[]]$Content )
    $Block = @($Header) + $Content + $Footer
    $Start = [array]::IndexOf($Lines, $Header)
    $End   = [array]::IndexOf($Lines, $Footer)
    if ($Start -ge 0 -and $End -gt $Start) {
        LogV "Update domains - replace existing block."
        $Before = $Lines | Select-Object -First $Start
        $After  = $Lines | Select-Object -Skip ($End + 1)
        return $Before + $Block + $After
    } else {
        LogV "Append domains - no existing block."
        LogV "Lines added: $($Block.Count)"
        return $Lines + $Block
    }
}

function Finish {
    param([int]$Rc)
    if ($null -eq $Rc) { $Rc = 0 }
    try { Set-Content -Path $PsRcPath -Value $Rc -NoNewline -Encoding ascii -Force }
    catch { Log "Error: Failed to write RC file: $_.Exception.Message" }
    LogV "Hosts file update return code: $Rc"
    Log "---------------------------------------"
    exit $Rc
}

if ($Restricted -and -not $DryRun -and -not $Elevated) {
    Log "This operation requires Administrator privilege."
    Finish 1
}

if (Test-Path $PsRcPath) { Remove-Item -Force $PsRcPath }

if (Test-Path $LogPath) {
    try { Clear-Content -Path $LogPath -Force -ErrorAction Stop }
    catch { Log "Error: Failed to reset log file: $_.Exception.Message" }
}

#---------------------------------------------
# Read existing hosts and snapshots
#---------------------------------------------
$Rc = 0
$Lines = @()
$Existing = @()
$Loaded = $false
if (Test-Path $HostsPath) {
    try {
        $Lines = Get-Content $HostsPath -ErrorAction Stop
        if ($Lines) {
            $Loaded = $true
            LogV "Hosts file loaded."
            LogV "Lines read: $($Lines.Count)"
            $Snap = SnapshotLines $Lines
            LogV "Pre-snapshot first 5 lines: `n$($Snap.First)"
            LogV "Pre-snapshot last 5 lines: `n$($Snap.Last)"
            $Inside = $false
            $Existing = foreach ($Line in $Lines) {
                if ($Line -eq $Header) { $Inside = $true; continue }
                if ($Line -eq $Footer) { $Inside = $false; continue }
                if ($Inside) { $Line.Split()[1] }
            }
        } else { throw "Hosts file is empty." }
    } catch {
        Log "Error: Hosts file load failed: $_.Exception.Message"
        $Rc = 1
    }
} else { Log "Error: Hosts file not found." }
if (-not $Loaded) { Finish $Rc}

#---------------------------------------------
# Determine update required
#---------------------------------------------
$Update_Required = $false
foreach ($d in $Domains) {
    if (-not ($Existing -contains $d)) {
        $Update_Required = $true
        LogV "Update required."
        break
    }
}

if (-not $Update_Required) {
    Log "$DateTime Hosts is up to date - no update required."
    Finish 0
}

#---------------------------------------------
# Backup logic
#---------------------------------------------
if ($Backup -eq 1) {
    if ($DryRun -eq 1) {
        Log "Backup: $HostsPath"
    } else {
        try {
            $Ts = Get-Date -Format "yyyyMMddHHmmss"
            $BackupFile = "$HostsPath.bak.$Ts"
            Copy-Item -Path $HostsPath -Destination $BackupFile -Force
            Log "Backup created: $BackupFile"
        } catch {
            Log "Error: Backup failed: $_.Exception.Message"
            Finish 1
        }
    }
}

#---------------------------------------------
# Re/Build domain entries
#---------------------------------------------
$DomainsAdded = 0
$DomainsRemoved = 0
$DomainsUnchanged = 0
$Entries = foreach ($d in $Domains) {
    if ($Existing -contains $d) {
        Log "Keep domain: $d" | Out-Null
        $DomainsUnchanged++
    } else {
        Log "Add domain: $d" | Out-Null
        $DomainsAdded++
    }
    "$HostIp`t$d"
}
foreach ($d in $Existing) {
    if (-not ($Domains -contains $d)) { $DomainsRemoved++ }
}

if ($DomainsUnchanged -gt 0) {
LogV "Domains unchanged: $DomainsUnchanged" }
if ($DomainsAdded -gt 0) {
LogV "Domains added: $DomainsAdded" }
if ($DomainsRemoved -gt 0) {
LogV "Domains removed: $DomainsRemoved" }
$Lines = SetDomains $Lines $Entries
LogV "Lines written: $($Lines.Count)"
$Snap = SnapshotLines $Lines
LogV "Post-snapshot first 5 lines: `n$($Snap.First)"
LogV "Post-snapshot last 5 lines: `n$($Snap.Last)"

#---------------------------------------------
# Atomic Write Hosts file using temp file + move
#---------------------------------------------
if ($DryRun -eq 1) {
    LogV "Hosts file NOT modified."
} elseif ($Lines) {
    $TmpFile = "$env:TEMP\\hosts_tmp_$($PID)_$(Get-Date -Format 'yyyyMMddHHmmss').tmp"
    $Saved = $false
    try {
        $Rc = 0
        $Retries = 0
        $Lines | Out-File -FilePath $TmpFile -Encoding ASCII -Force -ErrorAction Stop
        do {
            try {
                Move-Item -Path $TmpFile -Destination $HostsPath -Force -ErrorAction Stop
                try {
                    if ((Get-Content $HostsPath -ErrorAction Stop).Count -ne $Lines.Count) {
                        try { Copy-Item -Path $BackupFile -Destination $HostsPath -Force }
                        catch { throw "Restore backup failed." }
                        throw "Sanity check failed - restoring backup."
                    } else { $Saved = $true; $Rc = 0; break }
                } catch {
                    Log "Error: Sanity check failed: $_.Exception.Message"
                    $Rc = 1
                }
            } catch {
                LogV "Update attempt $($Retries+1) failed: $_"
                Start-Sleep -Milliseconds 200
                $Retries++
            }
        } while ($Retries -lt 5)
        if ($Saved) { Log "$DateTime Hosts file updated successfully." }
        else { throw "Hosts file update failed after $($Retries+1) attempts." }
    } catch {
        Log "Error: $($_.Exception.Message)"
        $Rc = 1
    }
} else {
    Log "Error: Hosts content is empty."
    $Rc = 1
}
Finish $Rc
PSH

        #---------------------------------------------
        # Inject payload environment variables
        #---------------------------------------------
        ps_payload="${ps_payload//__DOMAINS__/$domains_ps}"
        ps_payload="${ps_payload//__DRY_RUN__/$DRY_RUN}"
        ps_payload="${ps_payload//__VERBOSE__/$VERBOSE}"
        ps_payload="${ps_payload//__BACKUP__/$BACKUP}"
        ps_payload="${ps_payload//__HOST_IP__/$HOST_IP}"
        ps_payload="${ps_payload//__APP_NAME__/$APP_NAME}"
        ps_payload="${ps_payload//__HOSTS_PATH__/$WIN_HOSTS_PATH}"
        ps_payload="${ps_payload//__PS_RC_PATH__/$win_rc_path}"
        ps_payload="${ps_payload//__LOG_PATH__/$win_log_path}"
        ps_payload="${ps_payload//__DATE_TIME__/$date_time}"
        ps_payload="${ps_payload//__HEADER__/$header}"
        ps_payload="${ps_payload//__FOOTER__/$footer}"

        echo "$ps_payload" > "$posix_script_path" && ps_payload=""

        #log_debug "Hosts edit script: $win_script_path"
        #cat "$posix_script_path"

        #-----------------------------
        # Elevation and Restricted check before PowerShell invocation
        #-----------------------------
        if [[ "$elevated" != true && "$restricted" == true ]]; then
            local ps_launcher
            read -r -d '' ps_launcher <<'LPS' || true
$proc = Start-Process "$PSHOME\powershell.exe" `
    -Verb RunAs `
    -Wait `
    -WindowStyle Hidden `
    -PassThru `
    -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy Bypass',
        '-File',
        '__WIN_SCRIPT__'
    )
$proc.WaitForExit()
if ($proc.ExitCode -ne $null) {
    exit $proc.ExitCode
} else {
    exit $LASTEXITCODE
}
LPS

            ps_launcher="${ps_launcher//__WIN_SCRIPT__/$win_script_path}"
            #ps_launcher="${ps_launcher//__WIN_LOG__/$win_log_path}"

            log_info "Launching PowerShell with UAC prompt..."

            echo "$ps_launcher" > "$posix_ps_launcher_path"

            log_debug "PS Payload launcher: $win_ps_launcher_path"
            cat "$posix_ps_launcher_path"

            ps_payload="$win_ps_launcher_path"
        else
            log_info "Launching PowerShell as $role..."

            ps_payload="$win_script_path"
        fi

        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$ps_payload" \
            2> "${posix_log_path}.err"
        return_code=$?

        # Capture invocation or fallback RC bridge return code
        if [[ $return_code -gt 0 ]]; then
            log_debug "PowerShell invocation return code: $return_code"
            error_log="${posix_log_path}.err"
        elif [[ -f "$posix_rc_path" ]]; then
            return_code=$(<"$posix_rc_path")
            if [[ $return_code -gt 0 ]]; then
                error_log="${posix_log_path}.ps.err"
                log_debug "PowerShell RC file return code: $return_code"
            fi
            rm -f "$posix_rc_path"
        else
            return_code=1
        fi

        rm -f "$posix_script_path"

        # Check status only if DRY_RUN is active
        if [[ $DRY_RUN -eq 1 ]]; then
            log_info "[DRY-RUN] $header"
            for d in "${DOMAINS[@]}"; do
                log_info "[DRY-RUN] $HOST_IP    $d";
            done
            log_info "[DRY-RUN] $footer"
        fi
        ;;
    *)
        critical_exit "Invalid platform specified."
        ;;
    esac

    [[ $return_code -ne 0 ]] && {
    log_error "Hosts update failed with return code: $return_code.";
    log_info "${YELLOW}For details, check log:${END} ${WHITE}$error_log"; }

    # shellcheck disable=SC2086
    return $return_code
}

check_host_domains() {
    log_info "${HEADER}Configured Domains"
    #-------------------------------------------
    mal_domains=()
    for d in "${DOMAINS[@]}"; do
        local pattern="^\\s*$HOST_IP\\s+$d"
        if grep -qE "$pattern" "$HOSTS_PATH"; then
            log_info "${GREEN}  ✔${END} ${WHITE}$d"
        else
            log_info "${RED}  ✘${END} ${WHITE}$d"
            mal_domains+=("$d")
        fi
    done
}

mal_domains=()
domains=${#DOMAINS[@]}

if [[ "$AC_LOCAL" == true ]]; then
    check_host_domains
    if (( ${#mal_domains[@]} > 0 )); then
        log_info "${HEADER}Set Local Domains"
        #-------------------------------------------
        log_debug "BASH_VERSION: $BASH_VERSION"
        log_debug "AC_LOCAL: $AC_LOCAL"
        log_debug "PLATFORM: $PLATFORM"
        log_debug "SILENT: $SILENT"
        log_debug "VERBOSE: $VERBOSE"
        log_debug "BACKUP: $BACKUP"
        log_debug "DRY_RUN: $DRY_RUN"
        log_debug "DEBUG_ON: $DEBUG_ON"
        log_debug "HOST_IP: $HOST_IP"
        log_debug "HOSTS_PATH: $HOSTS_PATH"
        [[ "$PLATFORM" == "wsl" ]] && \
        log_debug "WIN_HOSTS_PATH: $WIN_HOSTS_PATH"
        if managed_hosts_edit; then
            mal_domains=()
        else
            log_error "Local domains were not set."
        fi
        [[ $DRY_RUN -eq 0 ]] && { check_host_domains; }
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