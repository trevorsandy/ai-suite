#!/bin/bash
# Trevor SANDY
# Last Update February 09, 2026
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
: "${AIS:=false}"
: "${AIS_LOCAL:=false}"
: "${WITH_REDIS:=false}"
: "${SUDO_USER:=""}"

ME="$(basename "$(test -L "$0" && readlink "$0" || echo "$0")")"

# Colors
sgr() { echo -e "\033[$*m"; }

BOLD=''
DIM=''
ITALIC=''
UNDERLINE=''
END=''
RED=''
RED_BG=''
GREEN=''
YELLOW=''
BLUE=''
MAGENTA=''
CYAN=''
WHITE=''
DIM_CYAN=''
ITALIC_RED_BG=''
UNDERLINE_YELLOW=''
ME_HDR="${ME}"
CRITICAL='CRITICAL:'
ERROR='ERROR:'
WARNING='WARNING:'
INFO='INFO:'

# Check if terminal supports colors https://unix.stackexchange.com/a/10065/642181
if [ -t 1 ]; then
    total_colors=$(tput colors)
    if [[ -n "$total_colors" && $total_colors -ge 8 ]]; then
        BOLD='1;'
        DIM='2;'
        ITALIC='3;'
        UNDERLINE='4;'
        # https://stackoverflow.com/a/28938235/18954618
        END="$(sgr '0')"
        RED="$(sgr '31')"
        RED_BG="$(sgr '41')" # Red background (White foreground)
        GREEN="$(sgr '32')"
        YELLOW="$(sgr '33')"
        BLUE="$(sgr '34')"
        MAGENTA="$(sgr '35')"
        CYAN="$(sgr '36')"
        WHITE="$(sgr '37')"
        DIM_CYAN="$(sgr "${DIM}36")"
        ITALIC_RED_BG="$(sgr "${ITALIC}41")"
        UNDERLINE_YELLOW="$(sgr "${UNDERLINE}93")"
        ME_HDR="$(sgr "${ITALIC}34")${ME}${END}"
        CRITICAL="${ME_HDR} $(sgr "${BOLD}41")CRITICAL:${END}"
        ERROR="${ME_HDR} $(sgr "${BOLD}91")ERROR:${END}"
        WARNING="${ME_HDR} $(sgr "${UNDERLINE}93")WARNING:${END}"
        INFO="${ME_HDR} $(sgr '36')INFO:${END}"
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
log_info() {
    echo -e "${INFO} ${DIM_CYAN}$1${END}"
}
critical_exit() {
    log_critical "$*"
    exit 1
}
FNAME="supabase_setup.sh"
if [ "${ME}" = "${FNAME}" ]; then
    [ -z "${LOG_PATH}" ] && LOG_PATH==`pwd` || :
    LOG="$LOG_PATH/$ME.log"
    if [ -f ${LOG} -a -r ${LOG} ]; then
        rm ${LOG}
    fi
    exec > >(tee -a ${LOG} )
    exec 2> >(tee -a ${LOG} >&2)
fi

# Process arguments
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Setup self-hosted AI-Suite with nginx/caddy and authelia 2FA."
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help message and exit"
    echo "  --proxy PROXY        Set the reverse proxy to use (nginx or caddy). Default: caddy"
    echo "  --with-authelia      Enable or disable Authelia 2FA support"
    echo ""
    echo "Examples:"
    echo "  $0 --proxy nginx --with-authelia    # Set up Supabase with nginx and Authelia 2FA"
    echo "  $0 --proxy caddy                    # Set up Supabase with caddy and no 2FA"
    echo ""
    echo "For more information, visit the project repository:"
    echo "https://github.com/trevorsandy/ai-suite"
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
    critical_exit "proxy can only be caddy or nginx"
fi

log_info "${END}${GREEN}Configuration Summary"
log_info "${END}  ${GREEN}Proxy:${END} ${WHITE}${proxy}"
log_info "${END}  ${GREEN}Authelia 2FA:${END} ${WHITE}${with_authelia}"

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

packages=(curl wget jq openssl git)

package_is_installed() {
  local i=1
  type $1 >/dev/null 2>&1 || { local i=0; } # set i to 0 if not found
  if [ "$i" == 1 ]; then
      log_info "${END}${GREEN}✔${END} ${WHITE}${1}"
  else
      log_info "${END}${RED}✘${END} ${WHITE}${1}"
  fi
  echo "$i"
}

missing_packages=()
for i in "${packages[@]}"; do
    if [ "$(package_is_installed $i)" == 0 ]; then missing_packages+=("$i"); fi
done
packages=("${missing_packages[@]}")
unset missing_packages

if (( ${#packages[@]} != 0 )); then
    # https://stackoverflow.com/a/18216122/18954618
    if [ "$EUID" -ne 0 ]; then critical_exit "You must run $0 as root user to install packages." ; fi

    # set -e doesn't work if any command is part of an if statement. package installation errors have to be checked https://stackoverflow.com/a/821419/18954618
    # https://unix.stackexchange.com/a/571192/642181
    if [ -x "$(command -v apt-get)" ]; then
        apt-get update && apt-get install -y "${packages[@]}" apache2-utils

    elif [ -x "$(command -v apk)" ]; then
        apk update && apk add --no-cache "${packages[@]}" apache2-utils

    elif [ -x "$(command -v dnf)" ]; then
        dnf makecache && dnf install -y "${packages[@]}" httpd-tools

    elif [ -x "$(command -v zypper)" ]; then
        zypper refresh && zypper install "${packages[@]}" apache2-utils

    elif [ -x "$(command -v pacman)" ]; then
        pacman -Syu --noconfirm "${packages[@]}" apache

    elif [ -x "$(command -v pkg)" ]; then
        pkg update && pkg install -y "${packages[@]}" apache24

    elif [[ -x "$(command -v brew)" && -n "$SUDO_USER" ]]; then
        # brew doesn't allow installation with sudo privileges, thats why have to run script as user who initiated this script with sudo privileges
        sudo -u "$SUDO_USER" brew install "${packages[@]}" httpd
    else
        # diff between array expansion with "@" and "*" https://linuxsimply.com/bash-scripting-tutorial/expansion/array-expansion/
        critical_exit "Failed to install packages. Package manager not found.\nSupported package managers: apt, apk, dnf, zypper, pacman, pkg, brew"
    fi

    if [ $? -ne 0 ]; then critical_exit "Failed to install packages."; fi
fi

github_ac="https://github.com/trevorsandy"
repo_url="$github_ac/ai-suite"
if [ "$AIS" == true ]; then
    directory="$(pwd)"
else
    directory="$(basename "$repo_url")"
fi

if [[ "$AIS" == true && -d "$directory" ]]; then
    log_info "Working directory: $directory"
elif [ -d "$directory" ]; then
    log_info "$directory directory present, skipping git clone"
else
    git clone --depth=1 "$repo_url" "$directory"
fi

if [ "$AIS" == true ]; then
    if ! cd "$directory"; then critical_exit "Unable to access working directory."; fi
else
    if ! cd "$directory"/docker; then critical_exit "Unable to access $directory/docker directory."; fi
fi
if [ ! -f ".env.example" ]; then critical_exit ".env.example file not found. Exiting!"; fi

download_binary() { wget "$1" -O "$2" &>/dev/null && chmod +x "$2" &>/dev/null; }
github_ac="https://github.com/singh-inder"
url_parser_bin="./url-parser"
yq_bin="./yq"

if [ ! -x "$url_parser_bin" ]; then
    log_info "Downloading url-parser from $github_ac/url-parser"
    download_binary "$github_ac"/url-parser/releases/download/v1.1.0/url-parser-"$os"-"$arch" "$url_parser_bin"
fi

if [ ! -x "$yq_bin" ]; then
    log_info "Downloading yq from https://github.com/mikefarah/yq"
    download_binary https://github.com/mikefarah/yq/releases/download/v4.45.4/yq_"$os"_"$arch" "$yq_bin"
fi

echo -e "---------------------------------------------------------------------------\n"

format_prompt() { echo -e "${GREEN}$1${END}"; }

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

# Get Domain
domain=""
while [ -z "$domain" ]; do
    if [ "$CI" == true ]; then
        domain="https://supabase.example.com"
    elif [ "$AIS" == true ]; then
        domain="https://$SUPABASE_HOSTNAME"
    else
        read -rp "$(format_prompt "Enter your domain:") " domain
    fi

    if ! protocol="$("$url_parser_bin" --url "$domain" --get scheme 2>/dev/null)"; then
        log_error "Could not extract protocol from domain: $domain.\n"
        domain=""
        continue
    fi

    if ! host="$("$url_parser_bin" --url "$domain" --get host 2>/dev/null)"; then
        log_error "Could not extract host from domain: $domain.\n"
        domain=""
        continue
    fi

    if [[ "$with_authelia" == true ]]; then
        # cookies.authelia_url needs to be https https://www.authelia.com/configuration/session/introduction/#authelia_url
        if [[ "$protocol" != "https" ]]; then
            log_error "As you have enabled --with-authelia flag, the domain protocol must be https"
            domain=""
        else
            if
                ! registered_domain="$("$url_parser_bin" --url "$domain" --get registeredDomain 2>/dev/null)" || [ -z "$registered_domain" ] ||
                    [ "$registered_domain" = "." ]
            then
                log_error "Could not extract root domain from $domain.\n"
                domain=""
            fi
        fi

    elif [[ "$protocol" != "http" && "$protocol" != "https" ]]; then
        log_error "Domain protocol must be http or https\n"
        domain=""
    fi
done

# Get Username
username=""
if [[ "$CI" == true ]]; then username="inder"; \
elif [[ "$AIS" == true ]]; then username="$AIS_USERNAME"; fi

while [ -z "$username" ]; do
    read -rp "$(format_prompt "Enter username:") " username

    # https://stackoverflow.com/questions/18041761/bash-need-to-test-for-alphanumeric-string
    if [[ ! "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
        log_error "Only alphabets and numbers are allowed"
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
elif [[ "$AIS" == true ]]; then
    password="$AIS_PASSWORD"
    confirm_password="$AIS_PASSWORD"
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
elif [[ "$AIS" == true ]]; then auto_confirm="$AIS_AUTO_CONFIRM"; fi

while [ -z "$auto_confirm" ]; do
    confirmation_prompt auto_confirm "Do you want to send confirmation emails to register users? If yes, you'll have to setup your own SMTP server [y/n]: "
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
    elif [[ "$AIS" == true ]]; then
        email="$AIS_EMAIL"
        display_name="$AIS_DISPLAY_NAME"
        setup_redis="$WITH_REDIS"
    fi

    # Get Admin Email
    while [ -z "$email" ]; do
        read -rp "$(format_prompt "Enter your email for Authelia:") " email

        # split email string on @ symbol
        IFS="@" read -r before_at after_at <<<"$email"

        if [[ -z "$before_at" || -z "$after_at" ]]; then
            log_error "Invalid email"
            email=""
        fi
    done

    # Get Display Name
    while [ -z "$display_name" ]; do
        read -rp "$(format_prompt "Enter Display Name:") " display_name

        if [[ ! "$display_name" =~ ^[a-zA-Z0-9[:space:]]+$ ]]; then
            log_error "Only alphabets, numbers and spaces are allowed"
            display_name=""
        fi
    done

    # Get Setup Redis
    while [[ "$CI" == false && "$AIS" == false && -z "$setup_redis" ]]; do
        confirmation_prompt setup_redis "Do you want to setup redis with authelia? [y/n]: "
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

# Update .env File
anon_token=$(gen_token "anon")
service_role_token=$(gen_token "service_role")

sed -e "3d" \
    -e "s|POSTGRES_PASSWORD.*|POSTGRES_PASSWORD=$(gen_hex 16)|" \
    -e "s|JWT_SECRET.*|JWT_SECRET=$jwt_secret|" \
    -e "s|ANON_KEY.*|ANON_KEY=$anon_token|" \
    -e "s|SERVICE_ROLE_KEY.*|SERVICE_ROLE_KEY=$service_role_token|" \
    -e "s|DASHBOARD_PASSWORD.*|DASHBOARD_PASSWORD=not_being_used|" \
    -e "s|SECRET_KEY_BASE.*|SECRET_KEY_BASE=$(gen_hex 32)|" \
    -e "s|VAULT_ENC_KEY.*|VAULT_ENC_KEY=$(gen_hex 16)|" \
    -e "s|PG_META_CRYPTO_KEY.*|PG_META_CRYPTO_KEY=$(gen_hex 16)|" \
    -e "s|API_EXTERNAL_URL.*|API_EXTERNAL_URL=$domain/goapi|" \
    -e "s|SUPABASE_PUBLIC_URL.*|SUPABASE_PUBLIC_URL=$domain|" \
    -e "s|ENABLE_EMAIL_AUTOCONFIRM.*|ENABLE_EMAIL_AUTOCONFIRM=$auto_confirm|" \
    -e "s|S3_PROTOCOL_ACCESS_KEY_ID.*|S3_PROTOCOL_ACCESS_KEY_ID=$(gen_hex 16)|" \
    -e "s|S3_PROTOCOL_ACCESS_KEY_SECRET.*|S3_PROTOCOL_ACCESS_KEY_SECRET=$(gen_hex 32)|" \
    -e "s|MINIO_ROOT_PASSWORD.*|MINIO_ROOT_PASSWORD=$(gen_hex 16)|" .env.example >.env

update_yaml_file() {
    # https://github.com/mikefarah/yq/issues/465#issuecomment-2265381565
    sed -i '/^\r\{0,1\}$/s// #BLANK_LINE/' "$2"
    "$yq_bin" -i "$1" "$2"
    sed -i "s/ *#BLANK_LINE//g" "$2"
}

compose_file="docker-compose.yml"

# Add env vars in .env file
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

# DEFINE Caddyfile
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
# DEFINE nginx.template
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

    if [[ "$CI" == true || "$AIS_LOCAL" == true ]]; then
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

    # TODO: add db/schema-authelia.sh to ./authelia
    authelia_docker_supabase_service_yaml='.services.db.environment.AUTHELIA_SCHEMA = strenv(authelia_schema) |
       .services.db.volumes += "./authelia/db/schema-authelia.sh:/docker-entrypoint-initdb.d/schema-authelia.sh"'

    if [[ "$setup_redis" == true ]]; then
        authelia_config_file_yaml="${authelia_config_file_yaml}|.session.redis.host=\"redis\" | .session.redis.port=6379"
        authelia_docker_service_yaml="${authelia_docker_service_yaml}|.services.authelia.depends_on.redis.condition=\"service_healthy\""
    fi

    # WRITE AUTHELIA configuration.yml file
    host="$host" registered_domain="$registered_domain" authelia_url="$domain"/authenticate redirect_url="$domain" \
        update_yaml_file "$authelia_config_file_yaml" "./authelia/configuration.yml"

    # WRITE AUTHELIA service to docker-compose.yml file
    authelia_schema="authelia" update_yaml_file "$authelia_docker_service_yaml" "$compose_file"

    # WRITE AUTHELIA service to Supabase docker-compose.yml file
    authelia_schema="authelia" update_yaml_file "$authelia_docker_supabase_service_yaml" "./supabase/$compose_file"
fi

# WRITE env_vars to .env
echo -e "$env_vars" >>.env

# WRITE LOCAL Caddyfile
if [[ "$proxy" == "caddy" ]]; then
    mkdir -p "$caddy_local_volume"
    # https://stackoverflow.com/a/3953712/18954618
    echo "
    import $caddy_addons_path/cors.conf

    {\$DOMAIN} {
        $([[ "$CI" == true || "$AIS_LOCAL" == true ]] && echo "tls internal")
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

unset password confirm_password
if [ -n "$SUDO_USER" ]; then chown -R "$SUDO_USER": .; fi
log_info "Cleaning up!"
for bin in "$yq_bin" "$url_parser_bin"; do rm "$bin"; done

success="${GREEN}Success!${END}"
access_message="${CYAN}To access the dashboard over the internet, ensure your firewall allows traffic on ports 80 and 443${END}"

if [[ "$AIS" == true ]]; then
    echo -e "\n${INFO} 🎉 ${success}"
    echo -e "\n${INFO} 🌐 ${access_message}\n"
    exit 0
fi

echo -e "\n${INFO} 🎉 ${success}"
echo "${INFO} 👉 ${CYAN}Next steps:${END}"
echo "${INFO} ${WHITE}1.${END} ${CYAN}Change into the docker directory:${END}"
echo "${INFO}   ${WHITE}cd $directory/docker${END}"
echo "${INFO} ${WHITE}2.${END} ${CYAN}Start the services with Docker Compose:${END}"
echo "${INFO}   ${WHITE}docker compose up -d${END}"
echo "${INFO} 🚀 ${GREEN}Everything should now be running!${END}"
echo -e "\n${INFO} 🌐 ${access_message}\n"
