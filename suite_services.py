#!/usr/bin/env python3
"""
start_services.py

This script starts the Supabase stack first - if specified, waits for it to initialize,
and then starts the AI-Suite stack. Both stacks use the same Docker Compose services name
("ai-suite") so they appear grouped together in Docker Desktop.
"""

import os
import sys
import subprocess
import shutil
import time
import argparse
import platform
import dotenv

def run_command(cmd, cwd=None):
    """Run a shell command and print it."""
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def clone_supabase_repo():
    """Clone the Supabase repository using sparse checkout if not already present."""
    if not os.path.exists("supabase"):
        print("Cloning the Supabase repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/supabase/supabase.git"
        ])
        os.chdir("supabase")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "docker"])
        run_command(["git", "checkout", "master"])
        os.chdir("..")
    else:
        print("Supabase repository already exists, updating...")
        os.chdir("supabase")
        run_command(["git", "pull"])
        os.chdir("..")

def prepare_supabase_env():
    """Copy .env to .env in supabase/docker."""
    env_path = os.path.join("supabase", "docker", ".env")
    env_source_path = os.path.join(".env")
    print(f"Copying .env in root to {env_path}...")
    shutil.copyfile(env_source_path, env_path)
    

def stop_and_remove_ai_suite(profile=None):
    """Stop and remove AI-Suite containers (using its compose file) for the
       specified profiles.
    """
    print("Stopping and removing unified project 'ai-suite' containers for the " \
          "specified profiles...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile:
        for option in profile:
            cmd.extend(["--profile", option])
    cmd.extend(["-f", "docker-compose.yml", "down", "--remove-orphans"])
    run_command(cmd)

def operate_ai_suite(operation=None, profile=None, environment=None):
    """Start, stop or pause the AI-Suite containers (using its compose file) for
       the specified profiles.
    """
    if not operation:
        operation = "stop"

    with open('.operating', 'w') as f:
        f.write(operation)

    if operation == 'start':
        start_ai_suite(profile, environment)
        return

    if operation == 'stop':
        insert = "Stopping"
    else:
        insert = "Pausing" if operation == 'pause' else None
    print(f"{insert} unified project 'ai-suite' containers for the specified profiles...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile:
        for option in profile:
            cmd.extend(["--profile", option])
    cmd.extend(["-f", "docker-compose.yml", operation])
    run_command(cmd)

def start_supabase(environment=None):
    """Start the Supabase services (using its compose file)."""
    print("Starting Supabase services...")
    cmd = ["docker", "compose", "-p", "ai-suite", "-f", "supabase/docker/docker-compose.yml"]
    if environment and environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.supabase.yml"])
    cmd.extend(["up", "-d", "--remove-orphans"])
    run_command(cmd)

def start_ai_suite(profile=None, environment=None, volume_prune=False):
    """Start the AI-Suite services (using its compose file) for the specified profiles."""
    print("Starting unified project 'ai-suite' services for the specified profiles...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile:
        for option in profile:
            cmd.extend(["--profile", option])
    else:
        cmd.extend(["--profile", 'open-webui'])
    cmd.extend(["-f", "docker-compose.yml"])
    if environment and environment == "private":
        cmd.extend(["-f", "docker-compose.override.private.yml"])
    if environment and environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d", "--remove-orphans"])
    run_command(cmd)
    if volume_prune:
        cmd = ["docker", "volume", "prune", "--force"]
        run_command(cmd)

def generate_searxng_secret_key():
    """Generate a secret key for SearXNG based on the current platform."""
    print("Checking SearXNG settings...")

    # Define paths for SearXNG settings files
    settings_path = os.path.join("searxng", "settings.yml")
    settings_base_path = os.path.join("searxng", "settings-base.yml")

    # Check if settings-base.yml exists
    if not os.path.exists(settings_base_path):
        print(f"Warning: SearXNG base settings file not found at {settings_base_path}")
        return

    # Check if settings.yml exists, if not create it from settings-base.yml
    if not os.path.exists(settings_path):
        print(f"SearXNG settings.yml not found. Creating from {settings_base_path}...")
        try:
            shutil.copyfile(settings_base_path, settings_path)
            print(f"Created {settings_path} from {settings_base_path}")
        except Exception as e:
            print(f"Error creating settings.yml: {e}")
            return
    else:
        print(f"SearXNG settings.yml already exists at {settings_path}")

    print("Generating SearXNG secret key...")

    # Run the appropriate the platform command
    try:
        if system == "Windows":
            print("Using Windows PowerShell to generate secret key...")
            # PowerShell command to generate a random key and replace in the settings file
            ps_command = [
                "powershell", "-Command",
                "$randomBytes = New-Object byte[] 32; " +
                "(New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomBytes); " +
                "$secretKey = -join ($randomBytes | ForEach-Object { \"{0:x2}\" -f $_ }); " +
                "(Get-Content searxng/settings.yml) -replace 'ultrasecretkey', $secretKey | Set-Content searxng/settings.yml"
            ]
            subprocess.run(ps_command, check=True)

        elif system == "Darwin":  # macOS
            print("Using macOS sed command with empty string parameter...")
            # macOS sed command requires an empty string for the -i parameter
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", "", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)

        else:  # Linux and other Unix-like systems
            print("Using standard Linux/Unix sed command...")
            # Standard sed command for Linux
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)

        print("SearXNG secret key generated successfully.")

    except Exception as e:
        print(f"Error generating SearXNG secret key: {e}")
        print("You may need to manually generate the secret key using the commands:")
        print("  - Linux: sed -i \"s|ultrasecretkey|$(openssl rand -hex 32)|g\" searxng/settings.yml")
        print("  - macOS: sed -i '' \"s|ultrasecretkey|$(openssl rand -hex 32)|g\" searxng/settings.yml")
        print("  - Windows (PowerShell):")
        print("    $randomBytes = New-Object byte[] 32")
        print("    (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomBytes)")
        print("    $secretKey = -join ($randomBytes | ForEach-Object { \"{0:x2}\" -f $_ })")
        print("    (Get-Content searxng/settings.yml) -replace 'ultrasecretkey', $secretKey | Set-Content searxng/settings.yml")

def check_and_fix_docker_compose_for_searxng():
    """Check and modify docker-compose.yml for SearXNG first run."""
    docker_compose_path = "docker-compose.yml"
    if not os.path.exists(docker_compose_path):
        print(f"Warning: Docker Compose file not found at {docker_compose_path}")
        return

    try:
        # Read the docker-compose.yml file
        with open(docker_compose_path, 'r') as f:
            content = f.read()

        # Default to first run
        is_first_run = True

        # Check if Docker is running and if the SearXNG container exists
        try:
            # Check if the SearXNG container is running
            container_check = subprocess.run(
                ["docker", "ps", "--filter", "name=searxng", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            searxng_containers = container_check.stdout.strip().split('\n')

            # If SearXNG container is running, check inside for uwsgi.ini
            if any(container for container in searxng_containers if container):
                container_name = next(container for container in searxng_containers if container)
                print(f"Found running SearXNG container: {container_name}")

                # Check if uwsgi.ini exists inside the container
                container_check = subprocess.run(
                    ["docker", "exec", container_name, "sh", "-c", "[ -f /etc/searxng/uwsgi.ini ] && echo 'found' || echo 'not_found'"],
                    capture_output=True, text=True, check=False
                )

                if "found" in container_check.stdout:
                    print("Found uwsgi.ini inside the SearXNG container - not first run")
                    is_first_run = False
                else:
                    print("uwsgi.ini not found inside the SearXNG container - first run")
                    is_first_run = True
            else:
                print("No running SearXNG container found - assuming first run")
                is_first_run = True
        except Exception as e:
            print(f"Error checking Docker container: {e} - assuming first run")

        cap_drop = "cap_drop:\n      - ALL\n"
        cap_drop_comment = "   #cap_drop:\n   #  - ALL  # Temporarily commented out for first run\n"

        if is_first_run and cap_drop in content:
            print(f"First run detected for SearXNG. Temporarily commenting {cap_drop} directive...")
            # Temporarily comment out the cap_drop line
            modified_content = content.replace(cap_drop, cap_drop_comment)

            # Write the modified content back
            with open(docker_compose_path, 'w') as f:
                f.write(modified_content)

            print(f"Note: After the first run completes successfully, uncomment {cap_drop} in docker-compose.yml for security.")
        elif not is_first_run and cap_drop_comment in content:
            print(f"SearXNG has been initialized. Uncommenting {cap_drop} directive for security...")
            # Uncomment the cap_drop line
            modified_content = content.replace(cap_drop_comment, cap_drop)

            # Write the modified content back
            with open(docker_compose_path, 'w') as f:
                f.write(modified_content)

    except Exception as e:
        print(f"Error checking/modifying docker-compose.yml for SearXNG: {e}")

# Treat Selfhosted Supavisor Pooler Keeps Restarting.
# See: https://github.com/supabase/supabase/issues/30210
def convert_supabase_pooler_line_endings():
    """converting Windows line endings to Linux/Unix/MacOS line endings."""
    if system == "Windows":
        print("Converting supavisor pooler line endings...")
        WINDOWS_LINE_ENDING = b'\r\n'
        UNIX_LINE_ENDING = b'\n'
        file_path = r"supabase/docker/volumes/pooler/pooler.exs"
        with open(file_path, 'rb') as f:
            content = f.read()
        # Windows ➡ Unix
        content = content.replace(WINDOWS_LINE_ENDING, UNIX_LINE_ENDING)
        with open(file_path, 'wb') as f:
            f.write(content)

def include_supabase_docker_compose(supabase=False):
    """Add or remove supabase supabase_docker_compose_file"""
    supabase_docker_compose_path = "supabase/docker/docker-compose.yml"
    if not os.path.exists(supabase_docker_compose_path) and supabase:
        print(f"Error: Supabase Docker Compose file not found at {supabase_docker_compose_path}")
        return
    docker_compose_path = "docker-compose.yml"
    if not os.path.exists(docker_compose_path):
        print(f"Error: Docker Compose file not found at {docker_compose_path}")
        return

    try:
        with open(docker_compose_path, 'r') as f:
            content = f.read()
        supabase_docker_compose_include = f"include:\n  - ./{supabase_docker_compose_path}\n\n"
        if supabase and supabase_docker_compose_include not in content:
            print(f"Including ./{supabase_docker_compose_path} in {docker_compose_path}...")
            with open(docker_compose_path, 'w') as f:
                f.write(supabase_docker_compose_include + content)
        elif not supabase and supabase_docker_compose_include in content:
            print(f"Excluding ./{supabase_docker_compose_path} from {docker_compose_path}...")
            modified_content = content.replace(supabase_docker_compose_include, "")
            with open(docker_compose_path, 'w') as f:
                f.write(modified_content)
    except Exception as e:
        print(f"Error processing {docker_compose_path}: {e}")

def set_variable_in_env_file(env_file: str | None, key: str | None , value: str | None, header: str | None):
    """Set an environment variable and optional header in .env file"""
    if env_file is None:
        env_file = os.path.join(".env")
    try:
        with open(env_file, 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip().split('=')
            if len(line) > 1 and key == line[0].strip():
                return
    except FileNotFoundError:
        print(f"File '{env_file}' not found.")

    if dotenv.load_dotenv(env_file):
        variable = "".join(filter(None, [header, key])) if header else key
        print(f"Set default {key} in {env_file} file...")
        if variable is not None and value is not None:
            dotenv.set_key(env_file, variable, value)

def main():
    ollama_profiles = ['cpu', 'gpu-nvidia', 'gpu-amd']
    client_profiles = ['open-webui', 'open-webui-all', 'n8n', 'n8n-all', 'ai-all']
    profiles = client_profiles + ['open-webui-fs', 'open-webui-pipe',
               'flowise', 'supabase', 'searxng', 'langfuse', 'neo4j', 'caddy'] + \
               ollama_profiles
    parser = argparse.ArgumentParser(
        description='Launch, start, stop, or pause the AI-Suite with specified ' \
                    'profile arguments (functional modules) and environment.',
        usage='\n- Launch AI-Suite specified profile arguments (functional modules)\n' \
              '...with Ollama running in the Host:\n' \
              'python suite_services.py --profile n8n opencode\n' \
              '...with Ollama runing in Docker using CPU:\n' \
              'python suite_services.py --profile n8n opencode cpu\n' \
              '...in public (production) environment:\n' \
              'python suite_services.py --profile n8n opencode --environment public\n' \
              '- Perform stop, start, pause and unpause suite operation:\n' \
              'python suite_services.py --profile n8n opencode cpu --operation stop')
    parser.add_argument('--profile', nargs='+', choices=profiles,
                        help='Docker Compose Profile arguments (default: open-webui '
                             '- with Ollama running in the Host)')
    parser.add_argument('--environment', choices=['private', 'public'], default='private',
                        help='Environment used by Docker Compose to expose or restrict '
                             'communication ports (default: private)')
    parser.add_argument('--operation', choices=['stop', 'start', 'pause', 'unpause'],
                        help='Operation to be performed by Docker Compose')

    args = parser.parse_args()

    # Detect platform
    global system
    system = platform.system()
    if system == "Windows":
        print("Detected Windows platform...")
    elif system == "Darwin":  # macOS
        print("Detected macOS platform...")
    else:  # Linux and other Unix-like systems
        print("Detected Linux/Unix platform...")

    # Detect default profile - no arguments specified
    default_profile = False if args.profile else True

    # Process operation command as needed
    if args.operation:
        status = None
        if os.path.exists('.operating'):
            with open('.operating', 'r') as f:
                status = f.readline() 
        if args.operation == status:
            if status == 'stop':
                insert = 'Stopped'
            else:
                insert = 'Paused' if status == 'pause' else 'Started'
            print(f"AI-Suite is already {insert} - exiting...")
            sys.exit(0)
        elif args.operation == 'unpause' and not status == 'pause':
            print(f"AI-Suite cannot unpause as it is not paused - exiting...")
            sys.exit(0)
        operate_ai_suite(args.operation, args.profile, args.environment)
        sys.exit(0)
    os.remove('.operating') if os.path.exists('.operating') else None
    
    # Manually set default profile argument
    if default_profile:
        args.profile = ['open-webui']

    env_file = os.path.join(".env")

    # Set default projects path in .env file
    if any(profile for profile in args.profile if profile in ['opencode'] + client_profiles):
        key = "PROJECTS_PATH"
        value = os.path.join(os.path.expanduser('~'), "projects")
        header = " ".join(["\n############", "\n# Projects", "\n############\n\n"])
        set_variable_in_env_file(env_file, key, value, header)
    
    # Setup Supabase
    supabase = \
        any(profile for profile in args.profile if profile == 'supabase')
    if supabase:
        args.profile.remove('supabase')
        clone_supabase_repo()
        convert_supabase_pooler_line_endings()
        prepare_supabase_env()

    # Include or exclude supabase_docker_compose in docker-compose.yml
    include_supabase_docker_compose(supabase)

    # Generate SearXNG secret key and check docker-compose.yml
    if any(profile for profile in args.profile if profile == 'searxng'):
        generate_searxng_secret_key()
        check_and_fix_docker_compose_for_searxng()

    stop_and_remove_ai_suite(args.profile)

    # Start Supabase first
    if supabase:
        start_supabase(args.environment)
        # Give Supabase some time to initialize
        print("Waiting for Supabase to initialize...")
        time.sleep(10)

    # If arguments n8n and open-webui specified, remove open-webui.
    if any(profile for profile in args.profile if profile == 'n8n'):
        if any(profile for profile in args.profile if profile == 'open-webui'):
            print("Profiles 'n8n' and 'open-webui' detected - removing 'open-webui'...")
            args.profile.remove('open-webui')
    
    # If more than one Ollama profile specified, use first profile
    if any(profile for profile in args.profile if profile in ollama_profiles):
        first_profile = False
        for ollama_profile in ollama_profiles:
            if not first_profile:
                if any(profile for profile in args.profile if profile == ollama_profile):
                    print(f"AI-Suite will use Ollama profile '{ollama_profile}'...")
                    first_profile = True
            else:
                args.profile.remove(ollama_profile)

    # Then start the AI-Suite services
    start_ai_suite(args.profile, args.environment, volume_prune=True)

    with open('.operating', 'w') as f:
        f.write('start')

if __name__ == "__main__":
    main()
