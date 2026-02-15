#!/bin/bash
# Trevor SANDY
# Last Update February 15, 2026
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

# https://stackoverflow.com/a/28085062/18954618
: "${CI:=false}"
: "${WITH_REDIS:=false}"
: "${SUDO_USER:="$(whoami)"}"

# Colors
END=''
COLOR=''
BOLD=''
DIM=''
ITALIC=''
UNDERLINE=''
RED=''
#RED_BG=''
GREEN=''
#YELLOW=''
BLUE=''
#MAGENTA=''
CYAN=''
WHITE=''
DIM_CYAN=''
ITALIC_RED_BG=''
UNDERLINE_YELLOW=''
NAME="AI-Suite"
QUESTION="${NAME} QUESTION:"
CRITICAL="${NAME} CRITICAL:"
ERROR="${NAME} ERROR:"
WARNING="${NAME} WARNING:"
DEBUG="${NAME} DEBUG:"
INFO="${NAME} INFO:"

# Check if terminal supports colors https://unix.stackexchange.com/a/10065/642181
sgr() { [ -n "${END}" ] && echo -e "\033[$*m" || : ; }
if [ -t 1 ]; then
    total_colors=$(tput colors)
    if [[ -n "$total_colors" && $total_colors -ge 8 ]]; then
        END='\033[0m'
        BOLD='1;'
        DIM='2;'
        ITALIC='3;'
        UNDERLINE='4;'
        # https://stackoverflow.com/a/28938235/18954618
        RED=$(sgr '31')
        #RED_BG=$(sgr '41') # Red background (White foreground)
        GREEN=$(sgr '32')
        #YELLOW=$(sgr '33')
        BLUE=$(sgr '34')
        #MAGENTA=$(sgr '35')
        CYAN=$(sgr '36')
        WHITE=$(sgr '37')
        DIM_CYAN=$(sgr "${DIM}36")
        ITALIC_RED_BG=$(sgr "${ITALIC}41")
        UNDERLINE_YELLOW=$(sgr "${UNDERLINE}93")
        NAME="$(sgr "${ITALIC}34")${NAME}${END}"
        QUESTION="${NAME} $(sgr "${BOLD}92")QUESTION:${END}"
        CRITICAL="${NAME} $(sgr "${BOLD}41")CRITICAL:${END}"
        ERROR="${NAME} $(sgr "${BOLD}91")ERROR:${END}"
        WARNING="${NAME} $(sgr "${BOLD}${UNDERLINE}93")WARNING:${END}"
        DEBUG="${NAME} $(sgr "${BOLD}97")DEBUG:${END}"
        INFO="${NAME} $(sgr "36")INFO:${END}"
    fi
fi

# Logging
log_critical() {
    echo -e "${CRITICAL} ${ITALIC_RED_BG}$1${END}"
}
log_error() {
    echo -e "${ERROR} ${RED}$1${END}"
}
log_warning() {
    echo -e "${WARNING} ${UNDERLINE_YELLOW}$1${END}"
}
log_debug() {
    echo -e "${DEBUG} ${WHITE}$1${END}"
}
log_info() {
    echo -e "${INFO} ${DIM_CYAN}$1${END}"
}
critical_exit() {
    log_critical "$*"
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

# Process arguments
usage() {
    echo "Usage: [ENVIRONMENT] $0 [OPTIONS]"
    echo ""
    echo "Setup self-hosted AI-Suite with Caddy/Nginx proxy and Authelia 2FA"
    echo "identity and access management."
    echo ""
    echo "Environment:"
    echo "  CI:false             Non-interactive mode - e.g running a GitHub build test"
    echo "  SUDO_USER:$(whoami)  Non-root SUDO user ID - brew does not allow installation as root user"
    echo "  WITH_REDIS:bool      Setup Authelia to use Redis - optional if using --with-authelia option"
    echo ""
    echo "  Auto-configure environment variables:"
    echo "  AC:false               Auto-Configure mode - expects required inputs using env env=input"
    echo "  AC_LOCAL:false         Local (private) installation - * requires additional configuration"
    echo "  AC_LOG_PATH:str        Directory path where install runtime log is deposited"
    echo "  AC_DOMAIN:str          Domain (optional) - Required for global (public) configuration"
    echo "  AC_USERNAME:str        User name for PROXY configuration"
    echo "  AC_PASSWORD:str        User password for PROXY configuration"
    echo "  AC_CONFIRM:false       Send confirmation email on user registration - ** SMTP server required"
    echo "  AC_EMAIL:str           User email address for Authelia - required if AC_WITH_AUTHELIA"
    echo "  AC_DISPLAY_NAME:str    User display name for Authelia  - required if AC_WITH_AUTHELIA"
    echo "  AC_SUDO_PASSWORD:str   SUDO user password - directed to sudo using a Here string"
    echo "  AC_SUDO_USER:str       Non-root SUDO user ID - brew does not allow installation as root user"
    echo "  AC_PROXY:caddy         Set the reverse proxy to use (Caddy or Nginx)"
    echo "  AC_WITH_AUTHELIA:false Enable Authelia 2FA support"
    echo "  AC_WITH_REDIS:false    Setup Authelia to use Redis - recommended if AC_WITH_AUTHELIA and not AC_LOCAL"
    echo ""
    echo "  * Add your local domain to the hosts file to loop back to your machine like localhost."
    echo "    For example: 127.0.0.1 https://supabase.local.com"
    echo ""
    echo "  ** If not using an SMTP server, enter any well formatted email address."
    echo "     You can view codes sent by Authelia in ./authelia/notifications.txt."
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help message and exit"
    echo "  --proxy PROXY        Set the reverse proxy to use (Caddy or Nginx) - Default: Caddy"
    echo "  --with-authelia      Enable or disable Authelia 2FA support - Default: false (disable)"
    echo ""
    echo "Examples:"
    echo "  chmod +x $0                         # Make $0 executable"
    echo "  $0                                  # Basic username and password authentication"
    echo "  $0 --proxy nginx --with-authelia    # Configuration with Nginx and Authelia 2FA"
    echo "  $0 --proxy caddy                    # Configuration with Caddy and no 2FA"
    echo ""
    echo "For more information, see README.md:"
    echo "https://github.com/trevorsandy/ai-suite/blob/Dev/README.md"
}

has_argument() {
    [[ ("$1" == *=* && -n ${1#*=}) || (-n "$2" && "$2" != -*) ]]
}

extract_argument() { echo "${2:-${1#*=}}"; }

with_authelia=false
proxy="caddy"

# https://medium.com/@wujido20/handling-flags-in-bash-scripts-4b06b4d0ed04
while [ $# -gt 0 ]; do
    case "$1" in
    -h | --help)
        usage
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

ac_install_type=''
ac_user_confirm=''
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

COLOR=$(sgr "${BOLD}${UNDERLINE}92")
log_info "${END}${COLOR}Configuration Summary:"
log_info "  -${END} ${GREEN}Proxy:${END} ${WHITE}${proxy}"
log_info "  -${END} ${GREEN}Authelia 2FA:${END} ${WHITE}${with_authelia}"
log_info "  -${END} ${GREEN}Redis:${END} ${WHITE}${WITH_REDIS}"
log_info "  -${END} ${GREEN}Setup Mode:${END} ${WHITE}${ac_config_mode}"
[ -n "${ac_install_type}" ] && \
log_info "  -${END} ${GREEN}Installation:${END} ${WHITE}${ac_install_type}" || :
[ -n "${ac_user_confirm}" ] && \
log_info "  -${END} ${GREEN}User Confirmation:${END} ${WHITE}${ac_user_confirm}" || :

detect_arch() {
    case $(uname -m) in
    x86_64) echo "amd64" ;;
    aarch64 | arm64) echo "arm64" ;;
    armv7l) echo "arm" ;;
    i686 | i386) echo "386" ;;
    *) echo "err" ;;
    esac
}

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

if [[ "$os" == "err" ]]; then critical_exit "This script only supports linux os"; fi
if [[ "$arch" == "err" ]]; then critical_exit "Unsupported cpu architecture"; fi

is_root() {
    if [ -n "$1" ]; then return "$(id -u "$1")"; else return "$(id -u)"; fi
}

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
    if is_root; then
        if test -n "$SUDO_USER"; then
            if is_root "$SUDO_USER"; then
                log_error "Current user ($(whoami)) and SUDO_USER ($SUDO_USER) is root!"
                critical_exit "Homebrew cannot run package install as ($SUDO_USER)!"
            fi
        else
            critical_exit "Homebrew cannot run package install as ($(whoami))!"
        fi
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
        log_info "${END}  ${GREEN}✔${END} ${WHITE}${package}"
    else
        log_info "${END}  ${RED}✘${END} ${WHITE}${package}"
    fi
    return $i
}

privilage() {
    local prompt
    if prompt=$(sudo -nv 2>&1); then
        echo "has_sudo__pass_set"
    elif echo "$prompt" | grep -q '^sudo:'; then
        echo "has_sudo__needs_pass"
    else
        echo "no_sudo"
    fi
}

run_cmd() {
    local cmd=$*
    local BOLD_CYAN
    BOLD_CYAN=$(sgr "${BOLD}36")
    user_privilage=$(privilage)
    case "$user_privilage" in
    has_sudo__pass_set)
        sudo $cmd
        ;;
    has_sudo__needs_pass)
        # https://superuser.com/questions/553932
        if [ -n "${AC_SUDO_PASSWORD}" ]; then
            (sudo -S -v <<<"${AC_SUDO_PASSWORD}" > /dev/null 2>&1)
        else
            echo -e "${INFO} ${WHITE}Supply${END} ${BOLD_CYAN}sudo${END} ${WHITE}password for command:${END} ${BLUE}sudo${END} ${WHITE}$cmd${END}"
        fi
        sudo $cmd
        ;;
    *)
        echo -e "${INFO} ${WHITE}Supply${END} ${BOLD_CYAN}root${END} ${WHITE}password for command:${END} ${BLUE}su -c${END} ${WHITE}\"$cmd\"${END}"
        su -c "$cmd"
        ;;
    esac
}

install_packages() {
    case "${package_manager}" in
    apt-get)
        run_cmd apt-get update
        run_cmd export DEBIAN_FRONTEND="noninteractive" apt-get install -y "${packages[@]}"
        ;;
    apk)
        run_cmd apk update
        run_cmd add --no-cache "${packages[@]}"
        ;;
    dnf)
        run_cmd dnf makecache
        run_cmd dnf install -y "${packages[@]}"
        ;;
    zypper)
        run_cmd zypper refresh
        run_cmd zypper install "${packages[@]}"
        ;;
    pacman)
        run_cmd pacman -Syu --noconfirm "${packages[@]}"
        ;;
    pkg)
        run_cmd pkg update
        run_cmd pkg install -y "${packages[@]}"
        ;;
    brew)
        run_cmd -u "$SUDO_USER" brew install "${packages[@]}"
        ;;
    *) 
        critical_exit "Install packages failed! Package manager not found."
        ;;
    esac
}

log_info "${END}${COLOR}Required Packages:"
missing_packages=()
package_manager=''
pma=()
for i in "${packages[@]}"; do
    package="$i"
    IFS=':' read -r -a pma <<< "$i"
    if (( ${#pma[@]} > 1 )); then
        package="${pma[1]}"
        package_manager="${pma[0]}"
    fi
    if package_is_installed "$package" == 0; then
        missing_packages+=("$package")
    fi
done

log_info "${END}${COLOR}Package Manager:"
log_info "${END}  ${GREEN}✔${END} ${BLUE}${package_manager}"

packages=("${missing_packages[@]}")
if (( ${#packages[@]} != 0 )); then
    # https://unix.stackexchange.com/a/571192/642181
    if install_packages; then
        log_info "${END}${COLOR}Installed Packages:"
        for i in "${packages[@]}"; do
            package_is_installed "$i"
        done
    else
        critical_exit "Failed to install required packages."
    fi
fi
unset missing_packages
unset AC_SUDO_PASSWORD

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

download_binary() { wget "$1" -O "$2" &>/dev/null && chmod +x "$2" &>/dev/null; }
repo_base="https://github.com/singh-inder"
url_parser_bin="./url-parser"
yq_bin="./yq"

if [ ! -x "$url_parser_bin" ]; then
    log_info "Downloading url-parser from ${repo_base}/url-parser..."
    download_binary "${repo_base}"/url-parser/releases/download/v1.1.0/url-parser-"$os"-"$arch" "$url_parser_bin"
fi

if [ ! -x "$yq_bin" ]; then
    log_info "Downloading yq from https://github.com/mikefarah/yq..."
    download_binary https://github.com/mikefarah/yq/releases/download/v4.45.4/yq_"$os"_"$arch" "$yq_bin"
fi

log_info "${END}${COLOR}Downloaded Binaries:"
if test -x "$url_parser_bin"; then DL_STAT="${GREEN}✔"; else DL_STAT="${RED}✘"; fi
log_info "${END}  ${DL_STAT}${END} ${WHITE}url_parser":
if test -x "$yq_bin"; then DL_STAT="${GREEN}✔"; else DL_STAT="${RED}✘"; fi
log_info "${END}  ${DL_STAT}${END} ${WHITE}yq"

log_info "${END}${GREEN}-------------------------------------------------------"

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
        log_error "Please answer yes or no\n"
        answer=""
        ;;
    esac

    # Use eval to dynamically assign the new value to the variable name. This indirectly updates the variable in the caller's scope.
    if [ -n "$answer" ]; then eval "$variable_to_update_name=$answer"; fi
}

# ---------------------------------------------------------------------------

# Populate hostname
N8N_HOSTNAME=''
WEBUI_HOSTNAME=''
FLOWISE_HOSTNAME=''
SUPABASE_HOSTNAME=''
LANGFUSE_HOSTNAME=''
OLLAMA_HOSTNAME=''
LLAMACPP_HOSTNAME=''
SEARXNG_HOSTNAME=''
NEO4J_HOSTNAME=''
# url_parser --url argument and options:
# --url: URL to parse. (e.g., https://subdomain.example.com:1234/path/to/resource?user=123#section1)
# host: Host with port number if present (e.g., subdomain.example.com:1234)
# hostWithoutPort: Host without port number (eg., subdomain.example.com)
# scheme: URL scheme (e.g., https)
# subdomain: Subdomain (e.g., subdomain)
# domain: Domain name (e.g., example)
# tld: Top-level domain (e.g., com)
# port: Port (if specified, e.g., 8080)
# path: URL path (e.g., /path/to/resource)
# fragment: URL Fragment (e.g., section1)
# registeredDomain: Registered domain from host (e.g., example.com)
# query.<parameter>: The value of the user query parameter (e.g., query.user: 123).
set_hostname() {
    local hostname_variable="$1"
    local subdomain="$2"
    local scheme="https"
    local url=""

    while [ -z "$url" ]; do
        if [ "$CI" == true ]; then
            if test -z "$subdomain"; then subdomain="supabase"; fi
            url="$scheme://$subdomain.example.com"
        elif [ "$AC" == true ]; then
            if test -z "$subdomain"; then subdomain="n8n"; fi
            url="$scheme://$subdomain.${AC_DOMAIN:-"local.pc"}"
        else
            read -rp "$(format_prompt "Enter your hostname URL:") " url
        fi

        if ! protocol="$("$url_parser_bin" --url "$url" --get scheme 2>/dev/null)"; then
            log_error "Could not extract protocol from hostname URL: $url."
            url=""
            continue
        fi

        if ! host="$("$url_parser_bin" --url "$url" --get host 2>/dev/null)"; then
            log_error "Could not extract host from hostname URL: $url."
            url=""
            continue
        fi

        if [[ "$with_authelia" == true ]]; then
            # cookies.authelia_url needs to be https https://www.authelia.com/configuration/session/introduction/#authelia_url
            if [[ "$protocol" != "https" ]]; then
                log_error "As --with-authelia is enabled, the hostname URL protocol must be https."
                url=""
            else
                if
                    ! registered_domain="$("$url_parser_bin" --url "$url" --get registeredDomain 2>/dev/null)" || [ -z "$registered_domain" ] ||
                        [ "$registered_domain" = "." ]
                then
                    log_error "Could not extract the registered domain from $url."
                    url=""
                fi
            fi

        elif [[ "$protocol" != "http" && "$protocol" != "https" ]]; then
            log_error "The hostname URL protocol must be http or https"
            url=""
        fi
    done

    if [ -n "$url" ]; then
        if test -n "$hostname_variable"; then
           eval "$hostname_variable=$url"
        else
            N8N_HOSTNAME=${protocol}://n8n.${registered_domain}
            WEBUI_HOSTNAME=${protocol}://openwebui.${registered_domain}
            FLOWISE_HOSTNAME=${protocol}://flowise.${registered_domain}
            SUPABASE_HOSTNAME=${protocol}://supabase.${registered_domain}
            LANGFUSE_HOSTNAME=${protocol}://langfuse.${registered_domain}
            OLLAMA_HOSTNAME=${protocol}://ollama.${registered_domain}
            LLAMACPP_HOSTNAME=${protocol}://llamacpp.${registered_domain}
            SEARXNG_HOSTNAME=${protocol}://searxng.${registered_domain}
            NEO4J_HOSTNAME=${protocol}://neo4j.${registered_domain}
        fi
    fi
}

set_hostname "" "" # "HOSTNAME variable" "subdomain"

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
if [[ "$CI" == true ]]; then auto_confirm="false"; \
elif [[ "$AC" == true ]]; then auto_confirm="$AC_CONFIRM"; fi

while [ -z "$auto_confirm" ]; do
    confirmation_prompt auto_confirm "Do you want to send confirmation email when registering a user? If yes, you'll have to setup your own SMTP server [y/n]: "
    if [[ "$auto_confirm" == true ]]; then
        auto_confirm="false"
    elif [[ "$auto_confirm" == false ]]; then
        auto_confirm="true"
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

log_info "Processing Credentials..."

# in caddy basic_auth, hashed password is loaded in memory
# in nginx basic_auth, websites slows down a lot if bcrypt rounds number is high as the hashed password file is checked again and again on every request.
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

# ---------------------------------------------------------------------------

#--log_debug ": $"------
log_debug "BEGIN DEBUG———————"
log_debug "username: $username"
log_debug "proxy: $proxy"
log_debug "auto_confirm: $auto_confirm"
log_debug "with_authelia: $with_authelia"
log_debug "email: $email"
log_debug "display_name: $display_name"
log_debug "setup_redis: $setup_redis"
log_debug "jwt_secret: $jwt_secret"
log_debug "anon_token: $anon_token"
log_debug "service_role_token: $service_role_token"
log_debug "host Supabase): $host"
log_debug "protocol: $protocol"
log_debug "registered_domain: $registered_domain"
log_debug "N8N_HOSTNAME: $N8N_HOSTNAME"
log_debug "WEBUI_HOSTNAME: $WEBUI_HOSTNAME"
log_debug "FLOWISE_HOSTNAME: $FLOWISE_HOSTNAME"
log_debug "SUPABASE_HOSTNAME: $SUPABASE_HOSTNAME"
log_debug "LANGFUSE_HOSTNAME: $LANGFUSE_HOSTNAME"
log_debug "OLLAMA_HOSTNAME: $OLLAMA_HOSTNAME"
log_debug "LLAMACPP_HOSTNAME: $LLAMACPP_HOSTNAME"
log_debug "SEARXNG_HOSTNAME: $SEARXNG_HOSTNAME"
log_debug "NEO4J_HOSTNAME: $NEO4J_HOSTNAME"
log_debug "END DEBUG—————————"
exit 0
#-----------------------

# Create .env file from .env.example template
# TODO - extend to all .env credentials (n8n, PostgreSQL, Flowise, Neo4j, Langfuse, Caddy/Nginx...)
# Initial pass:    .env.example >.env
# Subsequent pass: .env >.env
sed -e "3d" \
    -e "s|POSTGRES_PASSWORD.*|POSTGRES_PASSWORD=$(gen_hex 16)|" \
    -e "s|JWT_SECRET.*|JWT_SECRET=$jwt_secret|" \
    -e "s|ANON_KEY.*|ANON_KEY=$anon_token|" \
    -e "s|SERVICE_ROLE_KEY.*|SERVICE_ROLE_KEY=$service_role_token|" \
    -e "s|DASHBOARD_PASSWORD.*|DASHBOARD_PASSWORD=not_being_used|" \
    -e "s|SECRET_KEY_BASE.*|SECRET_KEY_BASE=$(gen_hex 32)|" \
    -e "s|VAULT_ENC_KEY.*|VAULT_ENC_KEY=$(gen_hex 16)|" \
    -e "s|PG_META_CRYPTO_KEY.*|PG_META_CRYPTO_KEY=$(gen_hex 16)|" \
    -e "s|API_EXTERNAL_URL.*|API_EXTERNAL_URL=$SUPABASE_HOSTNAME/goapi|" \
    -e "s|SUPABASE_PUBLIC_URL.*|SUPABASE_PUBLIC_URL=$SUPABASE_HOSTNAME|" \
    -e "s|# N8N_HOSTNAME.*|N8N_HOSTNAME=$protocol://n8n.\$AC_DOMAIN|" \
    -e "s|# WEBUI_HOSTNAME.*|WEBUI_HOSTNAME=$protocol://openwebui.\$AC_DOMAIN|" \
    -e "s|# FLOWISE_HOSTNAME.*|FLOWISE_HOSTNAME=$protocol://flowise.\$AC_DOMAIN|" \
    -e "s|# SUPABASE_HOSTNAME.*|SUPABASE_HOSTNAME=$protocol://supabase.\$AC_DOMAIN|" \
    -e "s|# LANGFUSE_HOSTNAME.*|LANGFUSE_HOSTNAME=$protocol://langfuse.\$AC_DOMAIN|" \
    -e "s|# OLLAMA_HOSTNAME.*|OLLAMA_HOSTNAME=$protocol://ollama.\$AC_DOMAIN|" \
    -e "s|# LLAMACPP_HOSTNAME.*|LLAMACPP_HOSTNAME=$protocol://llamacpp.\$AC_DOMAIN|" \
    -e "s|# SEARXNG_HOSTNAME.*|SEARXNG_HOSTNAME=$protocol://searxng.\$AC_DOMAIN|" \
    -e "s|# NEO4J_HOSTNAME.*|NEO4J_HOSTNAME=$protocol://neo4j.\$AC_DOMAIN|" \
    -e "s|# LETSENCRYPT_EMAIL.*|LETSENCRYPT_EMAIL=\$AC_EMAIL|" \
    -e "s|ENABLE_EMAIL_AUTOCONFIRM.*|ENABLE_EMAIL_AUTOCONFIRM=$auto_confirm|" \
    -e "s|S3_PROTOCOL_ACCESS_KEY_ID.*|S3_PROTOCOL_ACCESS_KEY_ID=$(gen_hex 16)|" \
    -e "s|S3_PROTOCOL_ACCESS_KEY_SECRET.*|S3_PROTOCOL_ACCESS_KEY_SECRET=$(gen_hex 32)|" \
    -e "s|MINIO_ROOT_PASSWORD.*|MINIO_ROOT_PASSWORD=$(gen_hex 16)|" .env.example >.env

# Update yaml file usung yq package
update_yaml_file() {
    # https://github.com/mikefarah/yq/issues/465#issuecomment-2265381565
    sed -i '/^\r\{0,1\}$/s// #BLANK_LINE/' "$2"
    "$yq_bin" -i "$1" "$2"
    sed -i "s/ *#BLANK_LINE//g" "$2"
}

# Create env_vars list to append .env file
env_vars=""
update_env_vars() {
    for env_key_value in "$@"; do
        env_vars="${env_vars}\n$env_key_value"
    done
}

# DEFINE PROXY service
proxy_service_yaml=".services.$proxy.container_name=\"$proxy-container\" |
.services.$proxy.restart=\"unless-stopped\" |
.services.$proxy.ports=[\"80:80\",\"443:443\",\"443:443/udp\"] |
.services.$proxy.depends_on.kong.condition=\"service_healthy\"
"
if [[ "$with_authelia" == true ]]; then
    proxy_service_yaml="${proxy_service_yaml} | .services.$proxy.depends_on.authelia.condition=\"service_healthy\""
fi

# DEFINE Caddyfile and Caddy Docker service insert
if [[ "$proxy" == "caddy" ]]; then
    caddy_local_volume="./caddy"
    caddyfile_local="$caddy_local_volume/Caddyfile"

    # mounted local ./caddy/addons to this path inside container
    caddy_addons_path="/etc/caddy/addons"

    # BIND MOUNT VOLUMES CONFIG
    proxy_service_yaml="${proxy_service_yaml} |
                        .services.caddy.image=\"caddy:2.10.2\" |
                        .services.caddy.environment.DOMAIN=\"\${SUPABASE_PUBLIC_URL:?error}\" |
                        .services.caddy.volumes=[\"$caddyfile_local:/etc/caddy/Caddyfile\",
                                                 \"$caddy_local_volume/addons:$caddy_addons_path\",
                                                 \"caddy_data:/data\",
                                                 \"caddy_config_data:/config\"]"
# DEFINE nginx.template and Nginx Docker service insert
else
    update_env_vars "NGINX_SERVER_NAME=$host"
    # docker compose nginx service command directive. Passed via yq strenv
    nginx_cmd=""

    nginx_local_volume="./nginx"
    # path in local fs where nginx template file is stored
    nginx_local_template_file="$nginx_local_volume/nginx.template"

    # path inside container where template file will be mounted
    nginx_container_template_file="/etc/nginx/user_conf.d/nginx.template"

    # Pass an array of args to nginx service command directive https://stackoverflow.com/a/57821785/18954618
    # output multiline string from yq https://mikefarah.gitbook.io/yq/operators/string-operators#string-blocks-bash-and-newlines

    proxy_service_yaml="${proxy_service_yaml} |
                        .services.nginx.image=\"jonasal/nginx-certbot:6.0.1-nginx1.29.5\" |
                        .services.nginx.environment.NGINX_SERVER_NAME = \"\${NGINX_SERVER_NAME:?error}\" |
                        .services.nginx.environment.CERTBOT_EMAIL=\"your@email.org\" |
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

# HANDLE PROXY service BASIC_AUTH
if [[ "$with_authelia" == false ]]; then
    update_env_vars "PROXY_AUTH_USERNAME=$username" "PROXY_AUTH_PASSWORD='$password'"

    proxy_service_yaml="${proxy_service_yaml} |
                        .services.$proxy.environment.PROXY_AUTH_USERNAME = \"\${PROXY_AUTH_USERNAME:?error}\" |
                        .services.$proxy.environment.PROXY_AUTH_PASSWORD = \"\${PROXY_AUTH_PASSWORD:?error}\"
                        "

    if [[ "$proxy" == "nginx" ]]; then
        # path inside nginx container for storing basic_auth credentials
        nginx_pass_file="/etc/nginx/user_conf.d/supabase-self-host-users"

        printf -v nginx_cmd "echo \"\$\${PROXY_AUTH_USERNAME}:\$\${PROXY_AUTH_PASSWORD}\" >%s \\
&& %s" $nginx_pass_file "$nginx_cmd"
    fi
fi

# WRITE PROXY service to docker-compose.yml file
compose_file="docker-compose.yml"
nginx_cmd="${nginx_cmd:=""}" update_yaml_file "$proxy_service_yaml" "$compose_file"

# AUTHELIA configuration
if [[ "$with_authelia" == true ]]; then
    # Dynamically update yaml path from env https://github.com/mikefarah/yq/discussions/1253
    # https://mikefarah.gitbook.io/yq/operators/style

    # WRITE AUTHELIA users_database.yml file
    # adding disabled=false after updating style to double so that every value except disabled is double quoted
    yaml_path=".users.$username" display_name="$display_name" password="$password" email="$email" \
        "$yq_bin" -n 'eval(strenv(yaml_path)).displayname = strenv(display_name) |
               eval(strenv(yaml_path)).password = strenv(password) |
               eval(strenv(yaml_path)).email = strenv(email) |
               eval(strenv(yaml_path)).groups = ["admins","dev"] |
               .. style="double" |
               eval(strenv(yaml_path)).disabled = false' >./authelia/users_database.yml

    # DEFINE AUTHELIA configuration.yml file
    authelia_config_file_yaml='.access_control.rules[0].domain=strenv(host) |
            .session.cookies[0].domain=strenv(registered_domain) |
            .session.cookies[0].authelia_url=strenv(authelia_url) |
            .session.cookies[0].default_redirection_url=strenv(redirect_url)'

    server_endpoints="forward-auth"
    implementation="ForwardAuth"

    if [[ "$proxy" == "nginx" ]]; then
        server_endpoints="auth-request"
        implementation="AuthRequest"
    fi

    # auth implementation
    authelia_config_file_yaml="${authelia_config_file_yaml} | .server.endpoints.authz.$server_endpoints.implementation=\"$implementation\""

    update_env_vars "AUTHELIA_SESSION_SECRET=$(gen_hex 32)" "AUTHELIA_STORAGE_ENCRYPTION_KEY=$(gen_hex 32)" "AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET=$(gen_hex 32)"

    # shellcheck disable=SC2016
    authelia_docker_service_yaml='.services.authelia.container_name = "authelia" |
       .services.authelia.image = "authelia/authelia:4.38" |
       .services.authelia.volumes = ["./volumes/authelia:/config"] |
       .services.authelia.depends_on.db.condition = "service_healthy" |
       .services.authelia.expose = [9091] |
       .services.authelia.restart = "unless-stopped" |
       .services.authelia.healthcheck.disable = false |
       .services.authelia.environment = {
         "AUTHELIA_STORAGE_POSTGRES_ADDRESS": "tcp://db:5432",
         "AUTHELIA_STORAGE_POSTGRES_USERNAME": "postgres",
         "AUTHELIA_STORAGE_POSTGRES_PASSWORD" : "${POSTGRES_PASSWORD}",
         "AUTHELIA_STORAGE_POSTGRES_DATABASE" : "${POSTGRES_DB}",
         "AUTHELIA_STORAGE_POSTGRES_SCHEMA" : strenv(authelia_schema),
         "AUTHELIA_SESSION_SECRET": "${AUTHELIA_SESSION_SECRET:?error}",
         "AUTHELIA_STORAGE_ENCRYPTION_KEY": "${AUTHELIA_STORAGE_ENCRYPTION_KEY:?error}",
         "AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET": "${AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET:?error}"
       }'

    authelia_docker_supabase_service_yaml='.services.db.environment.AUTHELIA_SCHEMA = strenv(authelia_schema) |
       .services.db.volumes += "./authelia/db/schema-authelia.sh:/docker-entrypoint-initdb.d/schema-authelia.sh"'

    if [[ "$setup_redis" == true ]]; then
        authelia_config_file_yaml="${authelia_config_file_yaml}|.session.redis.host=\"redis\" | .session.redis.port=6379"
        authelia_docker_service_yaml="${authelia_docker_service_yaml}|.services.authelia.depends_on.redis.condition=\"service_healthy\""
    fi

    # WRITE AUTHELIA configuration.yml file (Supabase target)
    # TODO - add other target modules
    host="$host" registered_domain="$registered_domain" authelia_url="$SUPABASE_HOSTNAME"/authenticate redirect_url="$SUPABASE_HOSTNAME" \
        update_yaml_file "$authelia_config_file_yaml" "./authelia/configuration.yml"

    # WRITE AUTHELIA service to docker-compose.yml file
    authelia_schema="authelia" update_yaml_file "$authelia_docker_service_yaml" "$compose_file"

    # WRITE AUTHELIA service to Supabase docker-compose.yml file
    authelia_schema="authelia" update_yaml_file "$authelia_docker_supabase_service_yaml" "./supabase/$compose_file"
fi

# WRITE env_vars to .env file
echo -e "$env_vars" >>.env

# WRITE LOCAL Caddyfile
if [[ "$proxy" == "caddy" ]]; then
    mkdir -p "$caddy_local_volume"
    # https://stackoverflow.com/a/3953712/18954618
    echo "
    import $caddy_addons_path/cors.conf

    {\$DOMAIN} {
        $([[ "$CI" == true || "$AC_LOCAL" == true ]] && echo "tls internal")
        @supa_api path /rest/v1/* /auth/v1/* /realtime/v1/* /functions/v1/* /mcp /api/mcp

        $([[ "$with_authelia" == true ]] && echo "@authelia path /authenticate /authenticate/*
        handle @authelia {
            reverse_proxy authelia:9091
        }
        ")

        handle @supa_api {
            reverse_proxy kong:8000
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

        handle {
            $([[ "$with_authelia" == false ]] && echo "basic_auth {
                {\$PROXY_AUTH_USERNAME} {\$PROXY_AUTH_PASSWORD}
            }" || echo "forward_auth authelia:9091 {
                        uri /api/authz/forward-auth

                        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
            }")

            reverse_proxy studio:3000
        }

        header -server
}" >"$caddyfile_local"
# WRITE LOCAL nginx.template
else
    mkdir -p "$(dirname "$nginx_local_template_file")"

    # mounted local ./nginx/addons to this path inside container
    nginx_addons_path="/etc/nginx/user_conf.d/addons"

    # cert path inside container https://github.com/JonasAlfredsson/docker-nginx-certbot/blob/master/docs/good_to_know.md#how-the-script-add-domain-names-to-certificate-requests
    cert_path="/etc/letsencrypt/live/automated-self-host"

    echo "
upstream kong_upstream {
    server kong:8000;
    keepalive 2;
}

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

    location /realtime {
        proxy_pass http://kong_upstream;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_read_timeout 3600s;
    }

    location /storage/v1/ {
        include $nginx_addons_path/cors.conf;
        include $nginx_addons_path/common_proxy_headers.conf;
        proxy_set_header X-Forwarded-Prefix /storage/v1;
        client_max_body_size 0;
        proxy_pass http://storage:5000/;
    }

    location /goapi/ {
        proxy_pass http://kong_upstream/;
    }

    location /rest {
        proxy_pass http://kong_upstream;
    }

    location /auth {
        proxy_pass http://kong_upstream;
    }

    location /functions {
        proxy_pass http://kong_upstream;
    }

    location /mcp {
        proxy_pass http://kong_upstream;
    }

    location /api/mcp {
        proxy_pass http://kong_upstream;
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
        proxy_pass http://studio:3000;
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

unset AC_PASSWORD password confirm_password
if [ -n "$SUDO_USER" ]; then
    log_info "Setting $(basename "$(pwd)")/* ownership to $SUDO_USER..."
    chown -R "$SUDO_USER": .;
fi

log_info "Cleaning up..."
for bin in "$yq_bin" "$url_parser_bin"; do rm "$bin"; done

success="${GREEN}Success!${END}"
access_message="${CYAN}To access the dashboard over the internet, ensure your firewall allows traffic on ports 80 and 443${END}"

edit_host_file() {
    echo -e "\n${INFO} 👉 ${BLUE}Next steps:${END}"
    echo "${INFO}${BLUE}1.${END} ${GREEN}Edit your hosts file so your domain will loop back to your${END}"
    echo "${INFO}      ${GREEN}machine - just like localhost.${END}"
    echo "${INFO}   ${BLUE}1a.${END} ${GREEN}Create a backup of the original hosts file.${END}"
    echo "${INFO}      ${GREEN}sudo cp /etc/hosts /etc/hosts.bak${END}"
    echo "${INFO}   ${BLUE}1b.${END} ${GREEN}Open /etc/hosts file in your editor. Here, I am using vim.${END}"
    echo "${INFO}      ${GREEN}sudo vim /etc/hosts${END}"
    echo "${INFO}   ${BLUE}1c.${END} ${GREEN}Add a new entry with format: 'ip-address' 'hostname-or-domain-name'.${END}"
    echo "${INFO}      ${GREEN}127.0.0.1 https://supabase.local.com${END}"
    echo "${INFO}      ${GREEN}Save the file and quit your editor.${END}"
    echo ""
}

if [[ "$AC" == true ]]; then
    echo -e "\n${INFO} 🎉 ${success}"
    if [ "${AC_LOCAL}" == true ]; then edit_host_file ; fi
    echo -e "\n${INFO} 🌐 ${access_message}\n"
    exit 0
fi

echo -e "\n${INFO} 🎉 ${success}"
echo "${INFO} 👉 ${CYAN}Next steps:${END}"
echo "${INFO} ${WHITE}1.${END} ${CYAN}Change into $directory:${END}"
echo "${INFO}   ${WHITE}cd $directory${END}"
echo "${INFO} ${WHITE}2.${END} ${CYAN}Run suite_services.py:${END}"
echo "${INFO}   ${WHITE}python suite_services.py --profile ai-all --operation start${END}"
echo "${INFO} 🚀 ${GREEN}Confirm everything is running from console output${END}"
echo -e "\n${INFO} 🌐 ${access_message}\n"
