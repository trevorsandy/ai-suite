#!/bin/bash
# Trevor SANDY
# Last Update February 24, 2026
# Copyright (C) 2026 by Trevor SANDY
#
# This script is adapted from Inder Singh's setup.sh shell script.
# Copyright 2026 Inder Singh. Licensed under Apache License 2.0.
# Original source:
#    https://github.com/singh-inder/supabase-automated-self-host/raw/main/setup.sh
#
# This script is executed on --operation update or install by suite_services.py
# when --profile no-auto-config is not specified.
#

set -euo pipefail

VERSION="0.5.0"

# https://stackoverflow.com/a/28085062/18954618
: "${CI:=false}"
: "${WITH_REDIS:=false}"
: "${SUDO_USER:="$(whoami)"}"
: "${DEBUG_ON:=false}"
: "${DRY_RUN:=0}"
: "${BACKUP:=1}"
: "${INTERNAL_ELEVATED:=0}"

# Reset BASH time counter
SECONDS=0

# Colors
SGR=''
END=''
HEADER=''
BODY='  - '
BOLD=''
DIM=''
ITALIC=''
UNDERLINE=''
RED=''
GREEN=''
#YELLOW=''
BLUE=''
MAGENTA=''
CYAN=''
WHITE=''
DIM_CYAN=''
BOLD_MAGENTA=''
ITALIC_RED_BG=''
UNDERLINE_YELLOW=''
COLON=":"
NAME="${AC_NAME:="AI-Suite"}:"
NOTICE="${NAME} NOTICE"
QUESTION="${NAME} QUESTION"
CRITICAL="${NAME} CRITICAL"
ERROR="${NAME} ERROR"
WARNING="${NAME} WARNING"
DEBUG="${NAME} DEBUG"
INFO="${NAME} INFO"

# Check if terminal supports colors https://unix.stackexchange.com/a/10065/642181
sgr() { [ -n "${END}" ] && echo "${SGR}$*m" || : ; }

is_sgr() { [ "${1:0:5}" == "${SGR}" ] && echo "${END}" || echo "$2" ; }

if [ -t 1 ]; then
    total_colors=$(tput colors)
    if [[ -n "$total_colors" && $total_colors -ge 8 ]]; then
        SGR='\033['
        END="${SGR}0m"
        BOLD='1;'
        DIM='2;'
        ITALIC='3;'
        UNDERLINE='4;'
        # https://stackoverflow.com/a/28938235/18954618
        RED=$(sgr '31')
        GREEN=$(sgr '32')
        #YELLOW=$(sgr '33')
        BLUE=$(sgr '34')
        MAGENTA=$(sgr '35')
        CYAN=$(sgr '36')
        WHITE=$(sgr '37')
        DIM_CYAN=$(sgr "${DIM}36")
        BOLD_MAGENTA=$(sgr "${BOLD}95")
        ITALIC_RED_BG=$(sgr "${ITALIC}41")
        UNDERLINE_YELLOW=$(sgr "${UNDERLINE}93")
        COLON="${END}$(sgr "97"):"
        HEADER="$(sgr "${BOLD}${UNDERLINE}92")"
        BODY="$(sgr "37")  -${END} $(sgr "32")"
        NAME="$(sgr "${ITALIC}94")${NAME%?}${COLON}${END}"
        NOTICE="${NAME} $(sgr "${BOLD}95")NOTICE${END}"
        QUESTION="${NAME} $(sgr "${BOLD}92")QUESTION${END}"
        CRITICAL="${NAME} $(sgr "${BOLD}41")CRITICAL${END}"
        ERROR="${NAME} $(sgr "${BOLD}91")ERROR${END}"
        WARNING="${NAME} $(sgr "${BOLD}${UNDERLINE}93")WARNING${END}"
        DEBUG="${NAME} $(sgr "${BOLD}97")DEBUG${END}"
        INFO="${NAME} $(sgr "36")INFO${END}"
    fi
fi

# Logging
log_critical() {
    echo -e "${CRITICAL} $(is_sgr "${1}" "${ITALIC_RED_BG}")$1${END}"
}
log_error() {
    echo -e "${ERROR} $(is_sgr "${1}" "${RED}")$1${END}"
}
log_warning() {
    echo -e "${WARNING} $(is_sgr "${1}" "${UNDERLINE_YELLOW}")$1${END}"
}
log_debug() {
    test "$DEBUG_ON" != true && return
    echo -e "${DEBUG} $(is_sgr "${1}" "${WHITE}")$1${END}"
}
log_info() {
    echo -e "${INFO} $(is_sgr "${1}" "${DIM_CYAN}")$1${END}"
}
critical_exit() {
    log_critical "$*" >&2
    exit 1
}

SCRIPT="$(basename "$(test -L "$0" && readlink "$0" || echo "$0")")"
if [ "${SCRIPT}" == "auto_config.sh" ]; then
    [ -z "${AC_LOG_PATH}" ] && AC_LOG_PATH="$(pwd)" || :
    LOG="$AC_LOG_PATH/$SCRIPT.log"
    if [[ -f "${LOG}" && -r "${LOG}" ]]; then rm "${LOG}"; fi
    exec > >(tee -a "${LOG}" )
    exec 2> >(tee -a "${LOG}" >&2)
fi

# Capture elapsed execution time
# shellcheck disable=SC2329
finish_elapsed_time() {
    set +x
    ELAPSED="$((SECONDS / 3600))hrs $(((SECONDS / 60) % 60))min $((SECONDS % 60))sec"
    echo -e "${INFO} ${CYAN}Elapsed time:${END} ${GREEN}$ELAPSED${END}"
    echo -e "${INFO} ${GREEN}-------------------------------------------${END}"
}

# shellcheck disable=SC2329
finish () {
    vars=(AC_SUDO_PASSWORD AC_PASSWORD password confirm_password)
    for var in "${vars[@]}"; do [ -v "$var" ] && unset "$var" ; done

    if [ "$success" ]; then
        HEADER="${END}✅ ${HEADER}"
        status="Finished"
        binaries=()
        for bin in "$yq_bin" "$url_parser_bin"; do [ -f "$bin" ] && binaries+=("$bin") ; done
        if (( ${#binaries[@]} != 0 )); then log_info "Clean downloaded binaries..." ; fi
        #for bin in "${binaries[@]}"; do log_info "  ✘ $(basename "${bin}")"; (rm "$bin"); done
    else
        HEADER="${END}❌ $(sgr "${UNDERLINE}91")"
        status="Terminated"
    fi

    log_info "${HEADER}Configuration ${status}"
    #-------------------------------------------
    finish_elapsed_time

    # Clean SGR color sequence codes from the log file..."
    # - The regex explained:
    # sed             application binary
    # -i              perform in-place file editing
    # "               open double quote
    # s               substitution flag
    # /               delimeter '/'
    # \x1b            match the SGR escape sequence '\x1b' before the color or attribute code
    # \[              matches the first open bracket - escape '\[' to distinguish from regex [
    # [0-79;]\{1,11\} matches '1 to 11' of any character in '012345679;' - escape '\{' the curly braces
    #                 to keep the shell from mangling them - replace '.' by '[0-79;]' for more accuracy
    #                 we have 11 times due to bold, dim, italic, underline and color * 2 plus reset * 1
    # m               match the SGR escape sequence reset character 'm' - this trails the color code
    # //              empty string between delimeters '/' to replace everything with
    # g               match globally - i.e., multiple times per line
    # "               close double quote
    # "$LOG"          the log file: auto_config.sh.log
    sed -i "s/\x1b\[[0-79;]\{1,11\}m//g" "$LOG"
}

# Process arguments
usage() {
    cat <<EOF
$0 v$VERSION

Usage: [ENVIRONMENT] $0 [OPTIONS]

Setup self-hosted $AC_NAME with Caddy/Nginx proxy and Authelia 2FA
identity and access management with auto-generated credentials.

Environment:
  CI:false             Non-interactive mode - e.g running a GitHub build test
  SUDO_USER:$(whoami)  Non-root SUDO user ID - brew does not allow installation as root user
  WITH_REDIS:bool      Setup Authelia to use Redis - optional if using --with-authelia option

  Auto-configure environment variables:
  AC:false               Auto-Configure mode - expects required inputs from env vars
  AC_SUDO_PASSWORD:str   SUDO user password - directed to sudo using a Here string
  AC_SUDO_USER:str       Non-root SUDO user ID - brew does not allow installation as root user
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
  AC_LOG_PATH:str        Directory path where configuration runtime log is deposited

  1. Add your local domain to the hosts file to loop back to your machine like localhost.
     For example: 127.0.0.1 https://supabase.local.com
  2. If not using an SMTP server, enter any well formatted email address.
     You can view codes sent by Authelia in ./authelia/notifications.txt.
  3. Only alphanumeric charactes and spaces are allowed.
  4. Used if AC_WITH_AUTHELIA=true. Recommended if global (public) install, otherwise optional

Options:
  -h, --help           Show this help message and exit
  --proxy PROXY        Set the reverse proxy to use (Caddy or Nginx) - Default: Caddy
  --with-authelia      Enable or disable Authelia 2FA support - Default: false (disable)
  --subdomain <name>   Subdomain(s) beyond open-webui n8n and supabase - ignore for all
  --version            Display this script version
  --help.              Display this information

Examples:
  chmod +x $0                         # Make $0 executable
  $0                                  # Basic username and password authentication
  $0 --proxy nginx --with-authelia    # Configuration with Nginx and Authelia 2FA
  $0 --proxy caddy                    # Configuration with Caddy and no 2FA

For more information, see README.md:
https://github.com/trevorsandy/ai-suite/blob/Dev/README.md
EOF
}

has_argument() {
    [[ ("$1" == *=* && -n ${1#*=}) || (-n "$2" && "$2" != -*) ]]
}

extract_argument() { echo "${2:-${1#*=}}"; }

update_subdomains() {
    for name in "$@"; do
        for subdomain in "${subdomains[@]}"; do
            test "$name" == "$subdomain" && return
        done
        subdomains+=("$name")
    done
}

ac_install_type=''
ac_user_confirm=''
proxy="caddy"
success=false
with_authelia=false
url_parser_bin="./access/url-parser"
yq_bin="./access/yq"
using_sudo_user=false
subdomains=(open-webui n8n supabase)

ORIGINAL_ARGS=("$@")
PLATFORM="unknown"
HOSTS_PATH="/etc/hosts"

trap finish EXIT

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
        [[ $# -eq 0 ]] && critical_exit "--subdomains require at least one container name."
        update_subdomains "$1"
        ;;
    --internal-elevated)
        INTERNAL_ELEVATED=1
        ;;
    *)
        echo -e "${ERROR} ${RED}Invalid option:${END} $1" >&2
        usage
        exit 1
        ;;
    esac
    shift
done

if [[ "$proxy" != "caddy" && "$proxy" != "nginx" ]]; then
    critical_exit "Only caddy or nginx proxy supported - received $proxy"
fi

# Set all subdomains if no subdomain specified, else append default domains
if (( ${#subdomains[@]} == 3 )); then
    subdomains+=(flowise langfuse searxng neo4j llamacpp ollama)
fi

if [ "$AC" == true ]; then
    SUDO_USER="${AC_SUDO_USER:=${SUDO_USER}}"
    with_authelia="${AC_WITH_AUTHELIA:=${with_authelia}}"
    WITH_REDIS="${AC_WITH_REDIS:=${WITH_REDIS}}"
    proxy="${AC_PROXY:=${proxy}}"
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
elif [ "$CI" == true ]; then
    ac_config_mode="Continuous integration"
else
    ac_config_mode="Interactive"
fi

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
    case $(uname -m) in
    x86_64) echo "amd64" ;;
    aarch64 | arm64) echo "arm64" ;;
    armv7l) echo "arm" ;;
    i686 | i386) echo "386" ;;
    *) echo "err" ;;
    esac
}

is_wsl() { grep -qi microsoft /proc/version 2>/dev/null ; }

#https://stackoverflow.com/a/18434831/18954618
detect_os() {
    case $(uname | tr '[:upper:]' '[:lower:]') in
    linux*) echo "linux" ;;
    # darwin*) echo "darwin" ;;
    *) echo "err" ;;
    esac
}

os="$(detect_os)"
arch="$(detect_arch)"

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
log_debug "HOSTS_PATH: $HOSTS_PATH"

if [[ "$arch" == "err" ]]; then critical_exit "Unsupported CPU architecture"; fi

is_unix_root() { if [ -n "$1" ]; then return "$(id -u "$1")"; else return "$(id -u)"; fi }

is_windows_admin() {
    powershell.exe -NoProfile -Command \
      "[bool](([Security.Principal.WindowsPrincipal] \
      [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole( \
      [Security.Principal.WindowsBuiltInRole]::Administrator))"
}

: "${SILENT:=$(is_unix_root "" && echo 1 || echo 0)}"

packages=(curl wget jq openssl git)
if [ -x "$(command -v apt-get)" ]; then
    packages+=("apt-get:apache2-utils")
elif [ -x "$(command -v apk)" ]; then
    packages+=("apk:apache2-utils")
elif [ -x "$(command -v dnf)" ]; then
    packages+=("dnf:httpd-tools")
elif [ -x "$(command -v zypper)" ]; then
    packages+=("zypper:apache2-utils")
elif [ -x "$(command -v pacman)" ]; then
    packages+=("apt-get:apache")
elif [ -x "$(command -v pkg)" ]; then
    packages+=("pkg:apachew24")
elif [ -x "$(command -v brew)" ]; then
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
    package="$1"
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

privilage() {
    local prompt
    if is_unix_root; then
        echo "is_unix__root"
    elif prompt=$(sudo -nv 2>&1); then
        echo "has_sudo__pass_set"
    elif echo "$prompt" | grep -q '^sudo:'; then
        echo "has_sudo__needs_pass"
    elif command -v su >/dev/null 2>&1; then
        echo "has_su__needs_pass"
    else
        echo "none"
    fi
}

prompt_message() {
    local BOLD_CYAN
    BOLD_CYAN=$(sgr "${BOLD}36")
    local prompt_message="${INFO} ${WHITE}Supply${END} ${BOLD_CYAN}$1${END} ${WHITE}password for command:${END}"
    echo -e "$prompt_message ${BLUE}$([ "$1" == "su" ] && echo "su -c" || echo "su")${END}"
}

sudo_prompt() {
    # https://superuser.com/questions/553932
    if [ -n "${AC_SUDO_PASSWORD}" ]; then
        (sudo -S -v <<<"${AC_SUDO_PASSWORD}" > /dev/null 2>&1)
    else
        echo -e "$(prompt_message "sudo") ${WHITE}$1${END}"
    fi
}

run_pkg_cmd() {
    local cmd=$*
    local user_privilage
    user_privilage=$(privilage)
    case "$user_privilage" in
    is_unix__root)
        $cmd ;;
    has_sudo__pass_set)
        # shellcheck disable=SC2086
        sudo $cmd ;;
    has_sudo__needs_pass)
        sudo_prompt "$cmd"
        # shellcheck disable=SC2086
        sudo $cmd ;;
    has_su__needs_pass)
        echo -e "$(prompt_message "su") ${WHITE}$cmd${END}"
        su -c "$cmd" ;;
    *) : ;;
    esac
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
if command -v docker &> /dev/null; then
    log_info "${GREEN}  ✔${END} ${WHITE}Docker"
else
    log_info "${RED}  ✘${END} ${WHITE}Docker"
fi
missing_packages=()
package_manager=''
pkg_pair=()
for i in "${packages[@]}"; do
    package="$i"
    IFS=':' read -r -a pkg_pair <<< "$i"
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
    local variable_to_update_name="$1"
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

    # Use eval to dynamically assign the new value to the variable name. This indirectly updates the variable in the caller's scope.
    if [ -n "$answer" ]; then eval "$variable_to_update_name=$answer"; fi
}

elide() {
    echo "$@" | \
    awk -v max=35 '{ if (length($0) > max) print substr($0, 1, max-3) "..."; else print; }'
}

to_upper() { echo "$1" | awk '{print toupper($0)}' ; }

# Populate module hostname (URL)
log_info "${HEADER}Populate Domain Names"
#-------------------------------------------
DOMAINS=()
N8N_DOMAIN=''
LLAMA_DOMAIN=''
OLLAMA_DOMAIN=''
LLAMACPP_DOMAIN=''
SUPABASE_DOMAIN=''
# Modules listedd in reverse order
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
    local domain_variable="$1"
    local subdomain="$2"
    local scheme="https"
    local url=""

    while [ -z "$url" ]; do
        if test -z "$subdomain"; then subdomain="${subdomains[0]}"; fi
        if [ "$CI" == true ]; then
            url="$scheme://$subdomain.example.com"
        elif [ "$AC" == true ]; then
            url="$scheme://$subdomain.${AC_DOMAIN:-"local.pc"}"
        else
            read -rp "$(format_prompt "Enter your hostname URL:") " url
        fi

        if ! protocol="$("$url_parser_bin" --url "$url" --get scheme 2>/dev/null)"; then
            log_error "Could not extract protocol from hostname URL: $url."
            protocol=""
        fi

        if ! host="$("$url_parser_bin" --url "$url" --get host 2>/dev/null)"; then
            log_error "Could not extract host from hostname URL: $url."
            host=""
        fi
        if ! test "$AC" == true && test -z "$protocol" || test -z "$host"; then url="" && continue; fi

        # cookies.authelia_url needs to be https https://www.authelia.com/configuration/session/introduction/#authelia_url
        if [[ "$with_authelia" == true && "$protocol" != "https" ]]; then
            log_error "As --with-authelia is enabled, the hostname URL protocol must be https."
            protocol=""
        elif [[ "$protocol" != "http" && "$protocol" != "https" ]]; then
            log_error "The hostname URL protocol must be http or https"
            protocol=""
        fi
        if ! test "$AC" == true && test -z "$protocol"; then url="" && continue; fi

        if [[ -z "$domain_variable" || "$with_authelia" == true ]]; then
            if ! registered_domain="$("$url_parser_bin" --url "$url" --get registeredDomain 2>/dev/null)"; then
                registered_domain=""
            fi
            if test -z "$registered_domain" || test "$registered_domain" == "."; then
                registered_domain=""
            fi
            if [ -z "$registered_domain" ]; then
                log_error "Failed to extract the registered domain from $url."
                if ! test "$AC" == true; then url="" && continue; fi
            fi
        fi
    done

    if [[ -n "$protocol" && -n "$host" ]]; then
        if test -n "$domain_variable"; then
            eval "$domain_variable=${host}"
            add_domain=true
            for d in "${DOMAINS[@]}"; do \
            test "$host" == "$d" && add_domain=false; break || : ; done
            test "$add_domain" == true && DOMAINS+=("${host}")
            # echo -e "${NOTICE} ${WHITE}-${END} ${MAGENTA}$domain_variable:${END} ${WHITE}${host}${END}"
        elif test -n "$registered_domain"; then
            for subdomain in "${subdomains[@]}"; do
                if test "$subdomain" == "open-webui"; then sub="webui"; else sub="$subdomain"; fi
                domain_variable="$(to_upper "${sub}_DOMAIN")"
                domain_name="${subdomain}.${registered_domain}"
                DOMAINS+=("$domain_name")
                # echo -e "${NOTICE} ${WHITE}-${END} ${MAGENTA}$domain_variable:${END} ${WHITE}${host_name}${END}"
                eval "$domain_variable=$domain_name"
            done
        else
            critical_exit "Failed to get registered domain from hostname URL."
        fi
    else
        critical_exit "Failed to get protocol and host from hostname URL."
    fi
}

# If 'module_DOMAIN' 'subdomain' arguments are empty, all AI Suite domains will be populated.
set_domain_names "" ""

log_info "${BODY}protocol:${END} ${WHITE}$protocol"
log_info "${BODY}host (${AC_NAME}):${END} ${WHITE}$host"
log_info "${BODY}registered_domain:${END} ${WHITE}$registered_domain"

log_info "${BODY}SUPABASE_PUBLIC_URL:${END} ${WHITE}$protocol://$SUPABASE_DOMAIN"
log_info "${BODY}N8N WEBHOOK_URL:${END} ${WHITE}$protocol://$N8N_DOMAIN"

if [[ "$AC_LLAMACPP" == true ]]; then
    LLAMA_DOMAIN="$LLAMACPP_DOMAIN"
else
    LLAMA_DOMAIN="$OLLAMA_DOMAIN"
fi
log_info "${BODY}LLAMA_DOMAIN:${END} ${WHITE}$LLAMA_DOMAIN"

# Confirm subdomains have been converted to domain names
sub_i=0
for sub in "${subdomains[@]}"; do
    var=$(to_upper "$(test "$sub" == "open-webui" && echo "webui" || echo "$sub")_DOMAIN")
    test -z "$(declare -p "$var" 2> /dev/null)" && continue
    var_name="${MAGENTA}${var}:${END}"
    domain_name="${CYAN}${DOMAINS[$sub_i]}${END}"
    [ -v "$var" ] && echo -e "${NOTICE} ${WHITE}-${END} ${var_name} ${domain_name}"
    (( sub_i+1 ))
done

#-------------------------------------------

[[ "$CI" != true && "$AC" != true ]] && \
log_info "${HEADER}Capture Credentials" || :
#-------------------------------------------
# Get Username
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

# Get User Password
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

# Get Auto-confirm Registered User
auto_confirm=""
if [[ "$CI" == true ]]; then auto_confirm=false; \
elif [[ "$AC" == true ]]; then auto_confirm="$AC_CONFIRM"; fi

prompt="Do you want to send confirmation email when registering a user?\n\
        If yes, you'll have to setup your own SMTP server [y/n]: "

while [ -z "$auto_confirm" ]; do
    confirmation_prompt auto_confirm "$prompt"
    if [[ "$auto_confirm" == true ]]; then
        auto_confirm=false
    elif [[ "$auto_confirm" == false ]]; then
        auto_confirm=true
    fi
done

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

    # Get Authelia Email Address
    while [ -z "$email" ]; do
        read -rp "$(format_prompt "Enter your email address for Authelia:") " email

        # split email string on @ symbol
        IFS="@" read -r before_at after_at <<<"$email"

        if [[ -z "$before_at" || -z "$after_at" ]]; then
            log_error "Invalid email address: $email"
            email=""
        fi
    done

    # Get Authelia Display Name
    while [ -z "$display_name" ]; do
        read -rp "$(format_prompt "Enter your display name for Authelia:") " display_name

        if [[ ! "$display_name" =~ ^[a-zA-Z0-9[:space:]]+$ ]]; then
            log_warning "Only alphanumeric characters and spaces are allowed. Your rsponse: $display_name"
            display_name=""
        fi
    done

    # Get Setup Authelia to use Redis
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

#-------------------------------------------

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
# TODO - extend to all .env credentials (n8n, PostgreSQL, Flowise, Neo4j, Langfuse, Caddy/Nginx...)
log_info "${HEADER}Create .env File"
#-------------------------------------------
yml_bool() { echo "$(tr '[:lower:]' '[:upper:]' <<< "${1:0:1}")${1:1}" ; }

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
    -e "s|API_EXTERNAL_URL.*|API_EXTERNAL_URL=$protocol://$SUPABASE_DOMAIN/goapi|" \
    -e "s|SUPABASE_PUBLIC_URL.*|SUPABASE_PUBLIC_URL=$protocol://$SUPABASE_DOMAIN|" \
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
    .env
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
proxy_service_yaml=".services.$proxy.profiles=[\"$proxy\"] |
.services.$proxy.container_name=\"$proxy\" |
.services.$proxy.restart=\"unless-stopped\" |
.services.$proxy.ports=[\"80:80/tcp\",\"443:443/tcp\"]
"
if [[ "$AC_SUPABASE" == true ]]; then
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
                        .services.ngnix.TZ=\"France/Paris\" |
                        .services.nginx.environment.NGINX_SERVER_NAME = \"\${NGINX_SERVER_NAME:?error}\" |
                        .services.nginx.environment.CERTBOT_EMAIL = \"\${AC_EMAIL:?error}\" |
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
       .services.authelia.profiles=["caddy", "nginx"] |
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

    # TODO - add other target modules
    # TODO - modify _url to use registered domain
    # WRITE AUTHELIA configuration.yml file (Supabase target)
    log_info "${BODY}Write Authelia configuration.yml file"
    #-------------------------------------------
    host="$host" webui_domain="$WEBUI_DOMAIN" n8n_domain="$N8N_DOMAIN" flowise_domain="$FLOWISE_DOMAIN" \
        langfuse_domain="$LANGFUSE_DOMAIN" supabase_domain="$SUPABASE_DOMAIN" searxng_domain="$SEARXNG_DOMAIN" \
        neo4j_domain="$NEO4J_DOMAIN" llama_domain="$LLAMA_DOMAIN" registered_domain="$registered_domain" \
        authelia_url="$protocol://$WEBUI_DOMAIN"/authenticate redirect_url="$protocol://$WEBUI_DOMAIN" \
        update_yaml_file "$authelia_config_file_yaml" "./access/authelia/configuration.yml"

    # WRITE AUTHELIA service to docker-compose.yml file
    log_info "${BODY}Write Authelia service to docker-compose.yml file"
    #-------------------------------------------
    authelia_schema="authelia" update_yaml_file "$authelia_docker_service_yaml" "$compose_file"

    # WRITE AUTHELIA service to Supabase docker-compose.yml file
    log_info "${BODY}Write Authelia service to Supabase docker-compose.yml file"
    #-------------------------------------------
    authelia_schema="authelia" update_yaml_file "$authelia_docker_supabase_service_yaml" "./supabase/docker/$compose_file"
fi

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

# Docker: http://host.docker.internal:<port>
# Local:  http://localhost:<port>
# Global: https://my-ai-suite.fr:<port>

# | Ex | In | Service                 | Container - internal              | Domain - external          |
# | -: | -: | ----------------------: | --------------------------------: | -----------------------: |
# | ++ | ++ | `n8n`                   | n8n:5678/                         | localhost:5678/          |
# | ++ | ++ | `Open WebUI`            | open-webui:8080/                  | localhost:8080/          |
# | ++ | ++ | `Flowise`               | flowise:3001/                     | localhost:3001/          |
# |    |    | `Open webUI MCPO`       | open-webui-mcpo:8090/             | localhost:8090/          |
# |    |    | `MCP Gateway`           | mcp-gateway:8060/                 | localhost:8060/          |
# |    |    | `Open webUI Filesystem` | open-webui-filesystem:8091/docs/  | localhost:8091/docs/     |
# |    |    | `Redis`                 | redis:6379/                       | localhost:6379/          |
# |    |    | `MinIO`                 | minio:9001/                       | localhost:9001/          |
# |    |    | `QDrant`                | qdrant:6333/dashboard/            | localhost:6333/dashboard/|
# | ++ | ++ | `Subabase`              | supabase-kong:8000                | localhost:8000           |
# |    |    | `Postgres`              | postgres:5432                     | localhost:5432/          |
# | ++ | ++ | `Langfuse Web`          | langfuse-web:3000/                | localhost:3000/          |
# |    |    | `Langfuse Worker`       | langfuse-worker:3030/             | localhost:3030/          |
# |    |    | `Logflare`              | supabase-analytics:4000/dashboard/| localhost:4000/dashboard/|
# |    |    | `ClickHouse`            | clickhouse:8123/                  | localhost:8123/          |
# |    |    | `SearXNG`               | searxng:8081/                     | localhost:8081/          |
# | ++ | ++ | `Neo4j`                 | neo4j:7473/                       | localhost:7473/          |
# |    |    | `Caddy`                 | caddy:443/                        | localhost:443/           |
# |    |    | `Nginx`                 | nginx:443/Admin/                  | localhost:443/Admin/     |
# |    |    | `Authelia`              | authelia:9091/                    | localhost:9091/          |
# |    |    | `Ollama`                | ollama:11434/                     | localhost:11434/         |
# |    |    | `LLaMA.cpp`             | llamacpp:8040/                    | localhost:8040/          |

# WRITE LOCAL Caddyfile
if [[ "$proxy" == "caddy" ]]; then
    log_info "${HEADER}Write Caddyfile"
    #-------------------------------------------
    log_info "${BODY}$caddyfile_local"
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

    $([[ "$AC_LLAMACPP" == false ]] && echo "\
    # # Ollama API
    # {\$OLLAMA_HOSTNAME} {
    #     reverse_proxy ollama:11434
    # }" || echo "\
    # # LLaMA.cpp API
    # {\$LLAMACPP_HOSTNAME} {
    #     reverse_proxy llamacpp:8040
    # }")

    import $caddy_addons_path/cors.conf
" >"$caddyfile_local"
# WRITE LOCAL nginx.template
else
    log_info "${HEADER}Write Nginx Template"
    #-------------------------------------------
    log_info "${BODY}$nginx_local_template_file"

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

upstream searxng_upstream {
    server searxng:8081;
    keepalive 2;
}

$([[ "$AC_LLAMACPP" == false ]] && echo "\
# upstream ollama_upstream {
#     server ollama:11434;
#     keepalive 2;
# }" || echo "\
# upstream llamacpp_upstream {
#     server llamacpp:8040;
#     keepalive 2;
# }")

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

    # SearXNG
    location /searxng {
        proxy_pass http://searxng_upstream
    }

    $([[ "$AC_LLAMACPP" == false ]] && echo "\
    # # Ollama
    # location / {
    #     proxy_pass http://ollama_upstream
    # }" || echo "\
    # # LLaMA.cpp
    # location /llamacpp {
    #     proxy_pass http://llamacpp_upstream
    # }")

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
    local header="# $AC_NAME Local Domains:"
    local footer="# End of $AC_NAME section"

    if [[ "$BACKUP" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
        cp "$HOSTS_PATH" "$HOSTS_PATH.bak.$(date +%Y%m%d%H%M%S)"
    fi

    if [[ $DRY_RUN -eq 1 ]]; then echo "[DRY-RUN] $header"; elif \
    ! grep -q "^$header" "$HOSTS_PATH"; then \
    printf "%s\n" "$header" >> "$HOSTS_PATH"; fi

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
        unix_hosts_add
        return
    fi

    local user_privilage
    user_privilage=$(privilege)

    if [[ "$user_privilage" == "is_unix_root" ]]; then
        unix_hosts_add
        return
    fi

    case "$user_privilage" in
        has_sudo__pass_set)
            sudo bash "$0" --internal-elevated "${ORIGINAL_ARGS[@]}"
            ;;
        has_sudo__needs_pass)
            [[ "$SILENT" -eq 1 ]] && critical_exit "Silent mode requires passwordless sudo."
            sudo_prompt "--internal-elevated"
            sudo bash "$0" --internal-elevated "${ORIGINAL_ARGS[@]}"
            ;;
        has_su__needs_pass)
            [[ "$SILENT" -eq 1 ]] && critical_exit "Silent mode cannot use su."
            local cmd="bash $0 --internal-elevated ${ORIGINAL_ARGS[*]}"
            echo -e "$(prompt_message "su") ${WHITE}$cmd${END}"
            su -c "$cmd"
            ;;
        none)
            critical_exit "No privilege escalation available."
            ;;
     esac
}

windows_hosts_edit() {
    local is_elevated
    is_elevated=$(is_windows_admin)
    local ps_backup=0
    [[ "$BACKUP" -eq 1 ]] && ps_backup=1
    local ps_dryrun=0
    [[ "$DRY_RUN" -eq 1 ]] && ps_dryrun=1
    local ps_script_path="./ps_edit_hosts.ps1"
    local header="# $AC_NAME Local Domains:"
    local footer="# End of $AC_NAME section"
    local ps_domains=""
    for d in "${DOMAINS[@]}"; do
        ps_domains+="\"$d\","
    done
    ps_domains="@(${ps_domains%,})"
    local ps_script="# Edit hosts - update $AC_NAME domains
\$Domains    = $ps_domains
\$Ip         = \"$HOST_IP\"
\$Backup     = $ps_backup
\$DryRun     = $ps_dryrun
\$Header     = \"$header\"
\$Footer     = \"$footer\"
\$HostsPath  = [System.IO.Path]::GetFullPath(\"$WIN_HOSTS_PATH\")
\$TargetPath = [System.IO.Path]::GetFullPath('C:\\Windows\\System32\\drivers\\etc\\hosts')
\$Restricted = [string]::Equals(\$HostsPath, \$TargetPath, [System.StringComparison]::OrdinalIgnoreCase)
\$Elevated   = ([Security.Principal.WindowsPrincipal] \`
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (\$Restricted) {
    If (-not \$Elevated) {
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
}

if (\$Backup -eq 1 -and \$DryRun -eq 0) {
    \$Ts = Get-Date -Format \"yyyyMMddHHmmss\"
    Copy-Item \"\$HostsPath\" \"\$HostsPath.bak.\$Ts\"
}

\$Pattern = \"^\$Header\"
if (-not (Select-String -Path \"\$HostsPath\" -Pattern \$Pattern -Quiet)) {
    if (\$DryRun -eq 1) {
        Write-Host \"[DRY-RUN] \$Header\"
    } else {
        Add-Content -Path \"\$HostsPath\" -Value \"\$Header\"
    }
}

foreach (\$Domain in \$Domains) {
    \$Pattern = \"^\$Ip\s+\$Domain\"
    if (-not (Select-String -Path \"\$HostsPath\" -Pattern \$Pattern -Quiet)) {
        if (\$DryRun -eq 1) {
            Write-Host \"[DRY-RUN] \$Ip\`t\$Domain\"
        } else {
            Add-Content -Path \"\$HostsPath\" -Value \"\$Ip\`t\$Domain\"
        }
    }
}

\$Pattern = \"^\$Footer\"
if (-not (Select-String -Path \"\$HostsPath\" -Pattern \$Pattern -Quiet)) {
    if (\$DryRun -eq 1) {
        Write-Host \"[DRY-RUN] \$Header\"
    } else {
        Add-Content -Path \"\$HostsPath\" -Value \"\$Footer\"
    }
}
"

    log_debug "ps_script: $ps_script"

    echo "$ps_script" > "$ps_script_path"

    if [[ $SILENT -eq 1 ]]; then
        if [[ "$is_elevated" != "True" ]]; then
            critical_exit "Silent mode requires Administrator privilage."
        fi
    fi

    if [[ "$is_elevated" == "True" ]]; then
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
        echo ""
    else
        rm "$ps_script_path"
    fi
}

check_host_domains() {
    local quiet
    quiet=$([ "$1" == "--quiet" ] && \
    echo true || echo false)

    [ "$quiet" == false ] && \
    log_info "${HEADER}Configured Domains"
    #-------------------------------------------
    mal_domains=()
    for d in "${DOMAINS[@]}"; do
        local pattern="^\\s*$HOST_IP\\s+$d"
        if grep -qE "$pattern" "$HOSTS_PATH"; then
            [ "$quiet" == false ] && \
            log_info "${GREEN}  ✔${END} ${WHITE}$d"
        else
            [ "$quiet" == false ] && \
            log_info "${RED}  ✘${END} ${WHITE}$d"
            mal_domains+=("$d")
        fi
    done
}

HOST_IP=127.0.0.1
WIN_HOSTS_PATH="C:\\Windows\\System32\\drivers\\etc\\hosts"
mal_domains=()

if [[ "$AC_LOCAL" == true ]]; then
    check_host_domains "--quiet"
    if (( ${#mal_domains[@]} > 0 )); then
        log_info "${HEADER}Set Domains"
        #-------------------------------------------
        [ "$DEBUG_ON" == true ] && { DRY_RUN=1; mal_domains=(); }
        case "$PLATFORM" in
            linux|mac)
                unix_hosts_edit
                ;;
            wsl)
                windows_hosts_edit
                ;;
            *) critical_exit "Platform $PLATFORM is unsupported." ;;
        esac
        [[ $DRY_RUN -eq 0 ]] && { check_host_domains ""; }
    fi
fi

log_info "${END}🎉 ${HEADER}Success!"
#-------------------------------------------
success=true

if [[ "$AC" != true ]]; then
    echo -e "${INFO} 👉 ${BOLD_MAGENTA}Next steps:${END}"
    echo -e "${INFO} ${BLUE}1.${END} ${GREEN}Change into $directory:${END}"
    echo -e "${INFO}   ${WHITE}cd $directory${END}"
    echo -e "${INFO} ${BLUE}2.${END} ${GREEN}Run suite_services.py:${END}"
    echo -e "${INFO}   ${WHITE}python suite_services.py --profile ai-all --operation start${END}"
    echo -e "${INFO} 🚀 ${GREEN}Confirm everything is running from the console output${END}"
fi

edit_host_file() {
    (( ${#mal_domains[@]} == 0 )) && return
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
    local directory
    directory=$(dirname "${HOSTS_PATH}")
    local hosts_sfile
    hosts_sfile=$(basename "${HOSTS_PATH}")
    echo -e "${INFO} ${BLUE}1.${END} ${GREEN}Upon completion of the installation,${END}"
    echo -e "${INFO}     ${GREEN}edit your hosts file so your domains will loop${END}"
    echo -e "${INFO}     ${GREEN}back to your machine - just like localhost.${END}"
    echo -e "${INFO}   ${BLUE}1a.${END} ${GREEN}Create a backup of the original hosts file.${END}"
    echo -e "${INFO}      ${GREEN}From a ${CYAN}Bash${END} ${GREEN}$console, execute:${END}"
    echo -e "${INFO}      ${WHITE}cd $directory${END}"
    echo -e "${INFO}      ${WHITE}ts=\$(date +%Y%m%d%H%M%S)${END}"
    echo -e "${INFO}      ${WHITE}$copy_cmd $hosts_sfile $hosts_sfile.bak.\$ts${END}"
    echo -e "${INFO}   ${BLUE}1b.${END} ${GREEN}Open the $hosts_sfile file in your editor."
    echo -e "${INFO}     ${GREEN}Here, I am using${END} ${CYAN}vim${END}${GREEN}.${END}"
    echo -e "${INFO}      ${WHITE}sudo vim $hosts_sfile${END}"
    echo -e "${INFO}   ${BLUE}1c.${END} ${GREEN}Add domain entries with format: ${WHITE}ip-address   domain${END}${GREEN}.${END}"
    echo -e "${INFO}      ${GREEN}Save the file (${END}${WHITE}Esc${END}${GREEN},${END} ${WHITE}:wq${END}${GREEN}) and quit your editor.${END}"
    echo -e "${INFO}   ${BLUE}1d.${END} ${GREEN}In your browser, navigate to${END} ${WHITE}$protocol://$WEBUI_DOMAIN${END}${GREEN}.${END}"
    echo -e "${INFO} 🚀 ${GREEN}Confirm everything is running.${END}"
}

global_access="\
${BLUE}To access ${NAME} from the internet,${END} \
${BLUE}ensure your firewall allows traffic on ports${END} \
${WHITE}80${END} ${BLUE}and${END} ${WHITE}443${END}"

[[ "${AC_LOCAL}" == true ]] && edit_host_file || \
echo -e "${INFO} 🌐 $global_access"

exit 0