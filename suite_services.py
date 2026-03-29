#!/usr/bin/env python3
"""
Trevor SANDY
Last Update March 24, 2026
Copyright (c) 2025-Present by Trevor SANDY

AI-Suite uses this script for the installation command that handles the AI-Suite
functional module selection, llama CPU/GPU configuration, and starting Supabase
and Open WebUI Filesystem when specified.

If specified, the Supabase stack is started first. The script waits for it to initialize,
then starts open-webui filesystem tool - if specified, and then starts the AI-Suite
stack. All stacks use the same Docker Compose services project name ("ai-suite")
so they appear grouped together in Docker Desktop.

This script is also used for operation commands that start, stop, stop-llama,
pause, unpause, update and install the AI-Suite services using the optional
--operation argument. A llama (Ollama/LLaMA.cpp) check is performed when it is
assumed llama is running from the Docker Host. If llama is determined to be installed
but not running, an attempt to launch the Ollama/LLaMA.cpp service is executed
on install, start and unpause. The check will also attempt to stop the llama service
(in addition to stopping the AI-Suite services) when the stop-llama operational
command is specified.

Both installation and operation commands utilize the optional --profile
arguments to specify which AI-Suite functional modules and which llama CPU/GPU
configuration to use. When no functional profile argument is specified, the
default functional module open-webui is used, Likewise, if no CPU/GPU configuration
profile is specified, it is assumed llama is being run from the Docker Host.
Multiple profile arguments (functional modules) are supported.

The --environment command allows the installation to be defined as private (default)
or public. A public install restricts the communication ports exposed to the network.

For full installation and operation details, see the AI-Suite repository README.md

Portions of this script has been adapted from start_services.py by Cole Medin

This program is free software; you can redistribute it and/or modify it under
the terms of the Apache License, Version 2.0.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import sys
import argparse
import datetime
import dotenv
import getpass
import gzip
import logging
import hashlib
import pathlib
import platform
import queue
import re
import shutil
import subprocess
import textwrap
import threading
import time

# Info attributes
INFO = {
    "name"       : "AI-Suite",
    "version"    : (0, 5, 0),
    "title"      : "AI-Suite installation and operation",
    "file"       : os.path.basename(__file__),
    "description": "A dockerized suite of AI agents in a no-code, workflow, LLM environment",
    "author"     : "Trevor SANDY <trevor.sandy@gmail.com>",
    "author_url" : "https://github.com/trevorsandy/",
    "repository" : "https://github.com/trevorsandy/ai-suite",
    "issues"     : "https://github.com/trevorsandy/ai-suite/issues",
    "license"    : "Apache License 2.0",
    "copyright"  : "Copyright (c) 2025-present by Trevor SANDY"
}

# Logging
# Source - https://stackoverflow.com/a/35804945
def addLoggingLevel(levelName, levelNum, methodName=None):
    """Adds a new logging level to the logging module and the
       currently configured logging class.
    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
       raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
       raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
       raise AttributeError('{} already defined in logger class'.format(methodName))

    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)
    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)

# Custom logging level
addLoggingLevel("NOTICE", 22)

class Formatter(logging.Formatter):
    """A class that formats colored logs using Select Graphic Rendition parameters."""
    FORMATS = {
        logging.NOTSET: "%(prefix)s%(msg)s%(suffix)s",
        logging.DEBUG: "%(name)-8s: %(levelname)-8s %(lineno)d: %(prefix)s%(message)s%(suffix)s"
    }

    RED     = 31
    RED_BG  = 41 # Red background (White foreground)
    GREEN   = 32
    YELLOW  = 33
    BLUE    = 34
    MAGENTA = 35
    CYAN    = 36
    WHITE   = 37
    COLOR   = {'msg': WHITE, 'level': WHITE, 'name': BLUE}
    LOG_LEVEL_COLOR = {
        logging.CRITICAL : {'msg': RED_BG, 'level': RED_BG, 'name': BLUE} ,
        logging.ERROR    : {'msg': RED,    'level': RED,    'name': BLUE} ,
        logging.WARNING  : {'msg': YELLOW, 'level': YELLOW, 'name': BLUE} ,
        logging.NOTICE   : {'msg': MAGENTA,'level': WHITE,  'name': BLUE} , # type:ignore[reportAttributeAccessIssue]
        logging.INFO     : {'msg': CYAN,   'level': CYAN,   'name': BLUE} ,
        logging.DEBUG    : {'msg': WHITE,  'level': WHITE,  'name': BLUE}
    }

    def __init__(self, fmt: str):
        super().__init__()
        self.FORMATS[logging.NOTSET] = fmt

    @staticmethod
    def suffix():
        """Return Select Graphic Rendition parameters reset"""
        return '\033[0m'

    @staticmethod
    def prefix(color, bright=False, bold=False, faint=False, italic=False, underline=False):
        """Return Select Graphic Rendition Control Sequence Introducer parameters"""
        # Resolve format conflicts
        faint = False if faint and bright or bold else faint
        # Set CSI parameters
        codes = []
        color = color if isinstance(color, int) else 0 # black
        if bright:
            color += 60
        if bold:
            codes.append('1;')
        if faint:
            codes.append('2;')
        if italic:
            codes.append('3;')
        if underline:
            codes.append('4;')
        codes.append(str(color))
        rendition = ''.join(codes) if codes else color
        return ('\033[{0}m').format(rendition)

    @staticmethod
    def style(level:int | None = None, color:int | None = None, **kwargs):
        """Return Select Graphic Rendition style parameters
           kwargs (level): bright:bool, bold:bool, faint:bool, italic:bool, underline:bool,
                           emoji:str
           kwargs (record): name_color:int, name_prefix:str, level_name_color:int,
                            level_name_prefix:str + kwargs (level)
           kwargs (prefix): header_prefix:str, header:str, prefix:str, msg:str + kwargs (level)
        """
        d = {'bright': False, 'bold': False, 'faint': False, 'italic': False, 'underline': False, 'emoji': '',
            'name_color': None, 'name_prefix': '', 'level_name_color': None, 'level_name_prefix': '',
            'header_prefix': '', 'header': '', 'header_suffix': '', 'msg_prefix': '', 'msg': ''}
        d.update(kwargs)
        bright, bold, faint, italic, underline, emoji, \
        name_color, name_prefix, level_name_color, level_name_prefix, \
        header_prefix, header, header_suffix, msg_prefix, msg = \
        d['bright'], d['bold'], d['faint'], d['italic'], d['underline'], d['emoji'], \
        d['name_color'], d['name_prefix'], d['level_name_color'], d['level_name_prefix'], \
        d['header_prefix'], d['header'], d['header_suffix'], d['msg_prefix'], d['msg']
        # Resolve format conflicts
        faint = False if faint and bright or bold else faint
        if isinstance(level, int) and level not in [50, 40, 30, 20, 19, 18, 10]:
            color = level
            level = logging.INFO
        # Construct a SGR dictionary with the specified arguments
        suffix = Formatter.suffix()
        no_msg_prefix = header and not msg
        emoji = "🐛" if not emoji and level == logging.DEBUG else emoji
        emoji = emoji + " " if emoji else ""
        level = logging.INFO if not level else level
        name = True if name_prefix or name_color else False
        level_name = True if level_name_prefix or level_name_color else False
        if not color:
            color = Formatter.LOG_LEVEL_COLOR.get(level, Formatter.COLOR)['msg']
        if header:
            if not header_prefix:
                header_prefix = Formatter.prefix(color, bright, True, faint, italic, underline)
            header_suffix = suffix + " " if not no_msg_prefix else ""
        if not msg_prefix and not no_msg_prefix:
            msg_prefix = Formatter.prefix(color, bright, bold, faint, italic, underline)
        prefix = ("{0}{1}{2}{3}{4}{5}").format(
                  emoji, header_prefix, header, header_suffix, msg_prefix, msg)
        style = {'prefix': prefix, 'suffix': suffix}
        if name:
            if not name_prefix:
                name_prefix = Formatter.prefix(name_color, bright, bold, faint, True, underline)
            style.update({'name_prefix': name_prefix})
        if level_name:
            if not level_name_prefix:
                bold_level_names = [logging.ERROR, logging.CRITICAL, logging.NOTICE, logging.DEBUG] # type:ignore[reportAttributeAccessIssue]
                bold = True if level in bold_level_names else bold
                underline = True if level in [logging.WARNING, logging.NOTICE] else underline # type:ignore[reportAttributeAccessIssue]
                level_name_prefix = Formatter.prefix(level_name_color, bright, bold, faint, italic, underline)
            style.update({'level_name_prefix': level_name_prefix})
        # These (msg\header) constitute the stream message so set purge_msg to purge
        # the log file record msg\message when applying the stream format.
        if msg or header:
            style.update({'purge_msg': 'True'})
        # Return the SGR dictionary
        return style

    def format(self, record):
        """Format log record attributes with color or emojie prefix, and reset suffix"""
        # Save record
        saved_record = record
        # Get log level color dictionary
        color = self.LOG_LEVEL_COLOR.get(record.levelno, self.COLOR)
        # Get SGR reset parameter
        suffix = self.suffix()
        # Apply name attribute SGR parameters
        name = record.name
        name_prefix = None
        if hasattr(record, 'name_prefix'):
            name_prefix = getattr(record, 'name_prefix')
        if not name_prefix:
            name_prefix = self.prefix(color['name'], italic=True)
        record.name = ('{0}{1}{2}').format(name_prefix, name, suffix)
        # Apply level name attribute SGR parameters
        levelname = record.levelname
        levelname_prefix = None
        if hasattr(record, 'level_name_prefix'):
            levelname_prefix = getattr(record, 'level_name_prefix')
        if not levelname_prefix:
            bold_levelnames = [logging.ERROR, logging.CRITICAL, logging.NOTICE, logging.DEBUG] # type:ignore[reportAttributeAccessIssue]
            bold = record.levelno in bold_levelnames
            underline = record.levelno in [logging.WARNING]
            levelname_prefix = self.prefix(color['level'], bold=bold, underline=underline)
        record.levelname = ('{0}{1}{2}').format(levelname_prefix, levelname, suffix)
        # Apply msg attribute SGR parameters
        if not hasattr(record, 'prefix'):
            italic = record.levelno in [logging.CRITICAL, logging.DEBUG]
            faint = record.levelno in [logging.INFO]
            record.prefix = self.prefix(color['msg'], italic=italic, faint=faint)
        if not hasattr(record, 'suffix'):
            record.suffix = suffix
        # When purge_msg is present, message\msg is designated for the log file.
        # The stream message is in the prefix attribute, so purge message\msg.
        if hasattr(record, 'purge_msg'):
            record.message = ''
            record.msg = ''
        # Format record
        format = self.FORMATS.get(record.levelno, self.FORMATS[logging.NOTSET])
        formatter = logging.Formatter(format)
        formatted = formatter.format(record)
        # Restore record
        record = saved_record
        # Return formatted record
        return formatted

# File logging
LFH = logging.FileHandler(f'{str(INFO.get("name")).lower()}.log', 'a', 'utf-8')
LFHF = logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s', '%m-%d %H:%M')
LFH.setFormatter(LFHF)
LFH.setLevel(logging.DEBUG)

# Stream (Console) logging
LSH = logging.StreamHandler()
LSHF = Formatter('%(name)-8s: %(levelname)-8s %(prefix)s%(message)s%(suffix)s')
LSH.setFormatter(LSHF)
LSH.setLevel(logging.NOTSET)


def run_command(cmd, cwd=None):
    """Run a shell command and print it."""
    raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
    try:
        completed = subprocess.run(cmd, cwd=cwd, check=True)
        if completed.returncode != 0:
            log.error(f"Command: {completed.stderr}")
    except Exception as e:
        log.error(f"Exception: {e}.")

def fail(msg):
    """."""
    log.error(f"{msg}")
    raise RuntimeError(msg)

def exists(cmd):
    """."""
    found = shutil.which(cmd) is not None
    log.info(f"Check exists '{cmd}': {found}")
    return found

def retry(func, retries=3, base_delay=2, desc="operation"):
    """."""
    for attempt in range(1, retries + 1):
        log.info(f"{desc} (attempt {attempt}/{retries})")
        if func():
            return True
        delay = base_delay ** attempt
        log.info(f"{desc} failed → retry in {delay}s")
        time.sleep(delay)
    return False

def run_parallel(q):
    """."""
    def worker():
        while not q.empty():
            name, func = q.get()
            log.info(f"→ {name}")
            try:
                if not func():
                    fail(f"{name} failed")
            finally:
                q.task_done()

    threads = []
    for _ in range(min(2, q.qsize())):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

def unix_prefix():
    """."""
    cmd = ["bash", "-c"]
    if system == "Windows":
        cmd = ["wsl", "-e"] + cmd
    return cmd

def is_wsl2():
    """."""
    try:
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.lower()
        if "default version: 2" in output or "version: 2" in output:
            return True
        elif "version: 1" in output:
            raise RuntimeError("WSL1 is not supported. Use: wsl --set-version <distro> 2")
        return False
    except Exception:
        return False

def is_root_user():
    """Return True if the numeric user ID of the current shell is root."""
    try:
        cmd = unix_prefix() + ["id -u"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        uid = int(result.stdout.strip())
        return uid == 0
    except (subprocess.CalledProcessError, ValueError):
        return False

def sudo_user():
    if system == "Windows":
        if not is_wsl2():
            fail("WSL2 is not available on your Windows platform")
        cmd = ["wsl", "-e", "bash", "-c", "whoami"]
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            log.error(f"Exception: WSL non-root whoami: {e.stderr}")
        return ""
    else:
        return getpass.getuser()

def sudo_prompt(pwd):
    """Pre-cache sudo credentials using password."""
    if pwd:
        cmd = unix_prefix() + ["sudo", "-S", "-v"]
        subprocess.run(
            cmd,
            input=pwd + "\n",
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

def unix_privilege():
    """."""
    if is_root_user():
        return "is_unix__root"
    if shutil.which("sudo"):
        result = subprocess.run(
            ["sudo", "-n", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return "has_sudo__pass_set"
        else:
            return "has_sudo__needs_pass"
    if shutil.which("su"):
        return "has_su__needs_pass"
    return "none"

def run_pkg_cmd(cmd):
    """."""
    raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=(system == "Windows")
        )
        log.info(result.stdout.strip())
        if result.stderr:
            log.warning(f"{result.stderr.strip()}")
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        log.error(f"Exception: Command error: {e}")
        return False, ""

def run_unix_pkg_cmd(cmd):
    """."""
    cmd = unix_prefix() + cmd
    privilege = unix_privilege()
    if privilege == "is_unix__root":
        return run_pkg_cmd(cmd)
    elif privilege == "has_sudo__pass_set":
        full_cmd = ["sudo"] + unix_prefix() + cmd
        return run_pkg_cmd(full_cmd)
    elif privilege == "has_sudo__needs_pass":
        full_cmd = ["sudo"] + unix_prefix() + cmd
        return run_pkg_cmd(full_cmd)
    elif privilege == "has_su__needs_pass":
        return run_pkg_cmd(["su", "-c"] + unix_prefix() + cmd)
    else:
        fail("No privilege escalation available.")
    return False, ""

def install_package(package, pwd=None):
    """."""
    if not package:
        log.error("Package required!")
        return False

    if system == "Windows":
        if package == 'docker-compose':
            return True
        if package == 'docker':
            if exists("winget"):
                return run_pkg_cmd(["winget", "install", "-e", "--id", "Docker.DockerDesktop"])[0]
            else:
                return True

    privilege = unix_privilege()
    if privilege == "is_unix__root":
        log.info("Running as Root")
    elif privilege.startswith("has_sudo"):
        log.info("Running as user with sudo privilege")
        if privilege == "has_sudo__needs_pass":
            if pwd:
                sudo_prompt(pwd)
    elif privilege.startswith("has_su"):
        log.info("Running as Super User (su)")
    else:
        fail("No privilege escalation available")

    if system == "Darwin" and exists("brew"):
        sudo_user = None
        if is_root_user():
            fail(f"You cannot install {package} as root on macOS")
        cmd = []
        cmd.extend(["brew", "install"])
        if package == 'docker':
            cmd.extend(["--cask"])
        cmd.extend([package])
        return run_pkg_cmd(cmd)[0]

    if system == "Linux" or is_wsl2():
        if exists("apt-get"):
            apt_pkg = "docker.io" if package == 'docker' else package
            return run_unix_pkg_cmd(["DEBIAN_FRONTEND=noninteractive echo $DEBIAN_FRONTEND"])[0] and \
            run_unix_pkg_cmd(["apt-get", "update"])[0] and \
            run_unix_pkg_cmd(["apt-get", "install", "-y", apt_pkg])[0]
        elif exists("apk"):
            return run_unix_pkg_cmd(["apk", "update"])[0] and \
            run_unix_pkg_cmd(["apk", "add", "--no-cache", package])[0]
        elif exists("dnf"):
            return run_unix_pkg_cmd(["dnf", "makecache"])[0] and \
            run_unix_pkg_cmd(["dnf", "install", "-y", package])[0]
        elif exists("zypper"):
            return run_unix_pkg_cmd(["zypper", "refresh"])[0] and \
            run_unix_pkg_cmd(["zypper", "install", package])[0]
        elif exists("pacman"):
            return run_unix_pkg_cmd(["pacman", "-Syu", "--noconfirm", package])[0]
        elif exists("pkg"):
            return run_unix_pkg_cmd(["pkg", "update"])[0] and \
            run_unix_pkg_cmd(["pkg", "install", "-y", package])[0]
        else:
            fail("Install package failed! Package manager not found.")
    return False

def check_prerequisites():
    """Check if required tools are installed and return missing tools"""
    required_tools = ['Docker', 'Git']

    missing_tools = []
    for tool in required_tools:
        if shutil.which(tool.lower()) is None:
            missing_tools.append(tool)
    if missing_tools:
        log.critical("Missing required tools: [{}].".format(", ".join(missing_tools)))
        return missing_tools

    try:
        start_docker()
    except Exception as e:
        log.critical(f"Exception: Start Docker Desktop: {e}")
    return missing_tools

def start_docker():
    """Install Docker and ensure it is running and usable."""
    log.info("Starting Docker bootstrap...", extra=log_bright)
    # --- Version check ---
    if not _docker_check_version():
        fail("Docker version invalid or too old")
    # --- Ensure running ---
    if not _docker_is_running():
        log.info("Docker not ready → ensuring daemon is running...")
        if not _docker_start_daemon():
            fail("Docker start failed")
        if not _docker_wait_ready():
            fail("Docker not ready after startup")
    elif _docker_is_ready():
        log.info("Docker is running ✅", extra=LSHF.style(color=LSHF.GREEN))
    # --- Parallel tasks ---
    q = queue.Queue()
    ok, out = run_pkg_cmd(["docker", "compose", "version"])
    if not ok and not exists("docker-compose"):
        q.put((
            "Install Docker Compose",
            lambda: retry(lambda: install_package('docker-compose'), desc="Compose install")
        ))
    else:
        log.info(out, extra=log_bright)
    q.put(("Run hello-world test", _docker_test_container))
    run_parallel(q)
    log.info("✅ Docker environment is fully ready", extra=LSHF.style(bold=True, color=LSHF.GREEN))
    return True

def _docker_start_daemon():
    """."""
    if system == "Windows":
        path = os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe")
        if not os.path.exists(path):
            fail("Docker Desktop not found")
        # Already running → do NOT restart
        if _docker_desktop_is_running():
            log.info("Docker Desktop is running (or starting)", extra=log_bright)
            return True
        log.info("Starting Docker Desktop...", extra=log_bright)
        try:
            # Use Windows-native launch (most reliable)
            os.startfile(path)
        except Exception as e:
            log.warning(f"os.startfile failed: {e}")
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", path],
                    cwd=os.path.dirname(path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e2:
                log.error(f"Fallback launch failed: {e2}")
                return False
        return True
    elif system == "Darwin":
        log.info("Starting Docker Desktop (macOS)...", extra=log_bright)
        subprocess.Popen(["open", "-a", "Docker"])
        return True
    elif system == "Linux":
        log.info("Starting Docker daemon (systemd)...", extra=log_bright)
        return run_unix_pkg_cmd(["systemctl", "start", "docker"])[0]
    return False

def _docker_wait_ready(timeout=300):
    """
    Docker readiness:
    Windows:
      1. Wait for process
      2. Wait for pipe
      3. Wait for docker API
    """
    start = time.time()
    log.info("Waiting for Docker to become ready...")
    # ---------------- WINDOWS ---------------- #
    if system == "Windows":
        pipe = r"\\.\pipe\dockerDesktopLinuxEngine"
        # --- Step 1: wait for process ---
        log.info("Waiting for Docker Desktop process...")
        while time.time() - start < timeout:
            if _docker_desktop_is_running():
                log.info("Docker Desktop process detected")
                break
            time.sleep(2)
        else:
            log.error("Docker Desktop process did not appear")
            return False
        # Give it time to avoid flash-exit race
        time.sleep(8)
        # --- Step 2: wait for pipe (WSL backend) ---
        log.info("Waiting for Docker engine pipe...")
        while time.time() - start < timeout:
            if not _docker_desktop_is_running():
                log.error("Docker Desktop exited during startup")
                return False
            if os.path.exists(pipe):
                log.info("Docker engine pipe detected")
                break
            time.sleep(2)
        else:
            log.error("Docker pipe not created (backend failed?)")
            return False
        # --- Step 3: wait for API ---
        log.info("Waiting for Docker API...")
        delay = 2
        while time.time() - start < timeout:
            if not _docker_desktop_is_running():
                log.error("Docker Desktop exited before API became ready")
                return False
            log.info("Requested Docker info (API Check)", extra=log_bright)
            if  _docker_is_ready():
                log.info("Docker is ready (API OK)", extra=log_bright)
                return True
            time.sleep(delay)
            delay = min(delay + 1, 10)
        log.error("Docker API did not respond in time")
        return False
    # ---------------- LINUX / MAC ---------------- #
    else:
        delay = 2
        while time.time() - start < timeout:
            log.info("Requested Docker info (API Check)", extra=log_bright)
            if _docker_is_ready():
                log.info("Docker ready (API OK)", extra=log_bright)
                return True
            time.sleep(delay)
            delay = min(delay + 1, 10)
        log.error("Docker did not become ready in time")
        return False

def _docker_is_ready():
    """."""
    ok, _ = run_pkg_cmd(["docker", "info"])
    return ok

def _docker_is_running():
    """."""
    ok = False
    if system == "Windows":
        ok = os.path.exists(r"\\.\pipe\dockerDesktopLinuxEngine")
    else:
        ok = os.path.exists("/var/run/docker.sock")
    if not ok:
        return False
    ok, _ = run_pkg_cmd(["docker", "system", "info"])
    return ok

def _docker_desktop_is_running():
    """Windows-only process check to avoid double-start."""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Docker Desktop.exe"],
        capture_output=True,
        text=True
    )
    return "Docker Desktop.exe" in result.stdout

def _docker_test_container():
    """."""
    ok, out = run_pkg_cmd(["docker", "run", "--rm", "hello-world"])
    if ok and "Hello from Docker!" in out:
        log.info(out, extra=log_bright)
        return True
    return False

def _docker_parse_version(version):
    """."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)

def _docker_check_version():
    """."""
    ok, version = run_pkg_cmd(["docker", "--version"])
    if not ok:
        return False
    parsed_version = _docker_parse_version(version)
    min_docker_version = (20, 10, 0)
    ok = parsed_version >= min_docker_version
    log_style = log_bright if ok else LSHF.style(color=LSHF.YELLOW)
    log.info(f"{version}", extra=(log_style))
    return ok

def launch_llama_process(args, llama_log):
    """Launch Ollama/LLaMA.cpp server on the host"""
    log_file = "".join(['>', llama_log, ' 2>&1'])
    if system == "Windows":
        win = "".join(['/c,"', llama_exe])
        cmd = ['powershell', '-Command', 'Start-Process cmd -Args', win, args,
               "".join([log_file, '"']), '-WindowStyle Hidden']
    else:  # Unix-based systems (Linux, macOS)
        cmd = [llama_exe, args, log_file]
    raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if completed.returncode != 0:
            log.error(f"Command: {llama} process: {completed.stderr}")
    except Exception as e:
        log.error(f"Exception: {llama} process: {e} - assuming {llama} did not start.")
    global attempted_launch
    attempted_launch = True
    log.info(f"Waiting for {llama} on host to initialize...", extra=log_bright)
    wait_with_progress(4)
    check_llama_process(None, {})

def check_llama_cpp_model(operation, env_vars, using_hf):
    """Check if the specified llama.cpp model exists, offer to download if not"""
    model_path = normalize_path(env_vars.get('LLAMACPP_MODEL_PATH'))
    model_name = env_vars.get('LLAMACPP_DEFAULT_MODEL', 'gemma-4b')
    if not os.path.exists(model_path):
        proceed = True
        # Dictionary of common llama.cpp model names and their download identifiers
        llama_cpp_models = {
            "LLAMACPP_MODEL_GEMMA": "LLAMACPP_MODEL_GEMMA_ID",
            "LLAMACPP_MODEL_DEEPSEEK": "LLAMACPP_MODEL_DEEPSEEK_ID",
            "LLAMACPP_MODEL_MISTRAL": "LLAMACPP_MODEL_MISTRAL_ID",
            "LLAMACPP_MODEL_LLAMA": "LLAMACPP_MODEL_LLAMA_ID",
            "LLAMACPP_MODEL_QWEN": "LLAMACPP_MODEL_QWEN_ID",
            "LLAMACPP_MODEL_USER": "LLAMACPP_MODEL_USER_ID"
        }
        if operation != 'install' and not using_hf:
            log.info(f"{llama} model not found at {model_path}")
            response = input(f"Would you like to download the {model_name} model now? (y/n): ")
            proceed = response.lower() == 'y'
        response = None
        if proceed:
            model_dir = os.path.dirname(model_path)
            if not os.path.exists(model_dir):
                os.makedirs(model_dir,exist_ok=True)
            best_match = None
            best_match_key = None
            best_match_score = 0
            for model_key in llama_cpp_models.keys():
                known_model = env_vars.get(model_key)
                if not known_model:
                    continue
                match_score = sum(c1 == c2 for c1, c2 in zip(model_name.lower(), known_model.lower()))
                if match_score > best_match_score:
                    best_match = known_model
                    best_match_key = model_key
                    best_match_score = match_score
            if best_match and best_match_key and best_match_score > len(best_match) / 2:
                log.info(f"Using {llama} model: {best_match}...")
                return env_vars.get(llama_cpp_models[best_match_key])
            else:
                response = f"Unknown model '{model_name}', download model manually - Models:"
                proceed = False
        else: # User elected not to proceed
            response = "Download the model manually and update your .env file - Models:"
        if not proceed:
            llama_server_args = env_vars.get('LLAMACPP_SERVER_ARGS')
            if operation == 'install':
                log.critical(response)
            else:
                log.notice(response) # type:ignore[reportAttributeAccessIssue]
            command_prefix = LSHF.prefix(LSHF.BLUE)
            command_model_prefix = LSHF.prefix(LSHF.BLUE, bold=True)
            llama_app_prefix = LSHF.prefix(LSHF.GREEN, bold=True)
            llama_server_args_prefix = LSHF.prefix(LSHF.GREEN)
            model_id_prefix = LSHF.prefix(LSHF.GREEN, italic=True)
            suffix = LSHF.suffix()
            for model_key, model_value in llama_cpp_models.items():
                model = env_vars.get(model_key)
                model_id = env_vars.get(model_value)
                if not model_id:
                    continue
                raw_msg = (
                    "{0} Command: {1} {2} {3}").format(
                    model, llama_app, llama_server_args, model_id)
                emoji = '🔗' if model_id.startswith('https://') else '🚀'
                model_command_prefix = (
                    "{0}•{1} "
                    "{2} "
                    "{3}{4}{5} "
                    "{6}command:{7}").format(
                    command_prefix, suffix, emoji,
                    command_model_prefix, model, suffix,
                    command_prefix, suffix)
                model_prefix = (
                    "{0} "
                    "{1}{2}{3} "
                    "{4}{5}{6} "
                    "{7}{8}").format(
                    model_command_prefix,
                    llama_app_prefix, llama_app, suffix,
                    llama_server_args_prefix, llama_server_args, suffix,
                    model_id_prefix, model_id)
                model_style = {'prefix': model_prefix, 'suffix': suffix}
                model_style.update({'purge_msg': 'True'})
                log.info(raw_msg, extra=model_style)
            log.info("Exiting...", extra=log_bright)
            return None
    log.info(f"Using {llama} model: {model_name}...")
    return model_name

def check_llama_process(operation=None, env_vars={}):
    """Check for Ollama/LLaMA.cpp (on host) and attempt to launch if not running."""
    if not attempted_launch:
        log.info(f"Checking for {llama} process on host...")
    llama_running = False
    llama_proc = llama_app.lower()
    try:
        if system == "Windows":
            cmd = ["tasklist"]
        else:  # Unix-based systems (Linux, macOS)
            cmd = ["pgrep", "-f", llama_proc]
        raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
        log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if system == "Windows":
            llama_running = True if llama_proc in completed.stdout.lower() else False
        else:  # Unix-based systems (Linux, macOS)
            llama_running = completed.returncode == 0 if completed else False
    except Exception as e:
        log.error(f"Exception: {llama} process: {e} - assuming {llama} is not running.")

    header = "See log for details:"
    stop_llama = operation == 'stop-llama'
    start_llama = not stop_llama and not operation in ['stop', 'pause']
    llama_log_dir = "llama.cpp" if llama_cpp else ""
    llama_log_file = os.path.join(os.getcwd(), llama_log_dir, 'llama_start.log')

    if llama_running:
        if stop_llama:
            log.info(f"Stopping {llama} process on host...")
            if system == "Windows":
                cmd = ["taskkill", "/f", "/im", llama_proc]
            else:  # Unix-based systems (Linux, macOS)
                cmd = ["ps", "-C", llama_proc, "-o", "pid=|xargs", "kill", "-9"]
            raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
            log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
            os.system(" ".join(cmd))
        else:
            if attempted_launch:
                log.info(f"{llama} on host is now running...", extra=LSHF.style(color=LSHF.GREEN))
                log.info(" ".join([header, llama_log_file]),
                         extra=LSHF.style(color=LSHF.GREEN, header=header, msg=llama_log_file))
            else:
                log.info(f"{llama} on host is running...", extra=LSHF.style(color=LSHF.GREEN))
    else:
        if attempted_launch:
            log.critical(f"Failed to launch {llama} on host...")
            log.critical("", extra=LSHF.style(color=LSHF.RED_BG, header=header, msg=llama_log_file))
            log.critical("Exiting...")
            sys.exit(1)
        log.info(f"{llama} is not running...", extra=log_bright)
        if start_llama:
            if llama_found:
                log.info(f"Attempting to launch {llama} on host...")
                llama_args = []
                if llama_cpp:
                    regex = r"(?:-hf|--hf-file|-m|--model|--model-url)"
                    llama_hf_repo = env_vars.get('LLAMA_ARG_HF_REPO')
                    llama_server_args = env_vars.get('LLAMACPP_SERVER_ARGS')
                    llama_models_dir = normalize_path(env_vars.get('LLAMACPP_MODELS_DIR'))
                    llama_model_arg = re.search(regex, llama_server_args)
                    if llama_models_dir:
                        if os.path.isdir(llama_models_dir):
                            default_models_dir = normalize_path(os.path.join('llama.cpp','models'))
                            if llama_models_dir != default_models_dir and os.listdir(llama_models_dir):
                                regex = r"\b{--models-dir}\b"
                                if not re.search(regex, llama_server_args):
                                    llama_args.extend(["--models-dir", llama_models_dir])
                        else:
                            log.error(f"Models directory {llama_models_dir} does not exist.")
                    if llama_server_args:
                        llama_args.extend([llama_server_args])
                    can_download = True if llama_hf_repo else False
                    llama_cpp_configured = can_download
                    if not llama_cpp_configured:
                        using_hf = False
                        if llama_model_arg:
                            using_hf = llama_model_arg.group() in ['-hf', '--hf-file']
                            can_download = llama_model_arg.group() not in ['-m', '--model']
                        llama_model = check_llama_cpp_model(operation, env_vars, using_hf)
                        if llama_model:
                            if not llama_model_arg:
                                llama_args.extend(['-hf'])
                            llama_args.extend([llama_model])
                            llama_cpp_configured = True
                    if can_download and operation in ['install', 'update']:
                        log_insert = "llama_start.log" if llama_on_host else "Docker container log"
                        log.info(f"Configured to download {llama} model (this may take a while).")
                        log.info(f"Check {log_insert} for download progress...")
                    elif not llama_cpp_configured:
                        sys.exit(1)
                else:
                    llama_server_args = env_vars.get('OLLAMA_SERVER_ARGS')
                    if llama_server_args:
                        llama_args.extend([llama_server_args])

                args = " ".join(llama_args)
                launch_llama_process(args, llama_log_file)
            else:
                log.critical(f"The {llama_app} file was not found at {llama_exe}.")
                log.critical(f"If {llama} is installed in a non-standard location, set the LLAMA_PATH")
                log.critical(f"environment variable with its full path (including the {llama} file)")
                log.critical(f"in the .env file and re-run {file} - exiting...")
                sys.exit(1)

def clone_supabase_repo():
    """Clone the Supabase repository using sparse checkout if not already present."""
    if not os.path.exists("supabase"):
        log.info("Cloning the Supabase repository...")
        run_command([
            "git", "-c", "core.autocrlf=input",
            "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/supabase/supabase.git"
        ])
        os.chdir("supabase")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "docker"])
        run_command(["git", "-c", "core.autocrlf=input", "checkout", "master"])
        os.chdir("..")
    else:
        log.info("Supabase repository already exists, updating...")
        os.chdir("supabase")
        run_command(["git", "-c", "core.autocrlf=input", "pull"])
        os.chdir("..")

def clone_open_webui_tools_filesystem_repo():
    """Clone the Open WebUI Tools Filesystem repository using sparse checkout if
       not already present.
    """
    repo_path = os.path.join("open-webui", "tools", "servers")
    if not os.path.exists(repo_path):
        os.chdir("open-webui")
        log.info("Cloning the Open WebUI Tools Filesystem repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/open-webui/openapi-servers.git", "tools"
        ])
        os.chdir("tools")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "servers/filesystem"])
        run_command(["git", "checkout", "main"])
        os.chdir("../../")
    else:
        repo_path = os.path.join("open-webui", "tools")
        log.info("Open WebUI Tools Filesystem repository already exists, updating...")
        os.chdir(repo_path)
        run_command(["git", "pull"])
        os.chdir("../../")

def clone_open_webui_functions_repos():
    """Clone the Open WebUI Functions repository using sparse checkout if not
       already present.
    """
    repo_path = os.path.join("open-webui", "functions", "open-webui")
    if not os.path.exists(repo_path):
        os.mkdir("open-webui/functions")
        os.chdir("open-webui/functions")
        log.info("Cloning the Open WebUI Functions repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/open-webui/functions.git", "open-webui"
        ])
        os.chdir("open-webui")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "functions/filters", "functions/pipes/openai"])
        run_command(["git", "checkout", "main"])
        os.chdir("../../../")
    else:
        log.info("Open WebUI Functions repository already exists, updating...")
        os.chdir(repo_path)
        run_command(["git", "pull"])
        os.chdir("../../../")

    repo_path = os.path.join("open-webui", "functions", "owndev")
    if not os.path.exists(repo_path):
        os.chdir("open-webui/functions")
        log.info("Cloning the Open WebUI Owndev Functions repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/owndev/Open-WebUI-Functions.git", "owndev"
        ])
        os.chdir("owndev")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "pipelines/n8n", "filters", "docs"])
        run_command(["git", "checkout", "main"])
        os.chdir("../../../")
    else:
        log.info("Open WebUI Functions repository already exists, updating...")
        os.chdir(repo_path)
        run_command(["git", "pull"])
        os.chdir("../../../")

    os.chdir(repo_path)
    docs_dir = os.path.join("docs")
    retain = ["n8n-integration.md", "n8n-tool-usage-display.md"]
    os.chdir(docs_dir)
    for item in os.listdir(os.getcwd()):
        if item not in retain:
            if pathlib.Path(item).is_file():
                os.remove(item)
            elif pathlib.Path(item).is_dir():
                shutil.rmtree(item)
    os.chdir("../../../../")

def prepare_supabase_env(env_vars):
    """Write env_vars to .env in supabase/docker. and copy Athelia db schema"""
    env_file = os.path.join("supabase", "docker", ".env")
    built_env_vars = env_vars
    built_env_vars['COMPOSE_IGNORE_ORPHANS'] = 'true'
    write_dotenv_file(env_file, built_env_vars)

    athelia_sh_path = os.path.join("access", "authelia", "db", "schema-authelia.sh")
    supabase_db_dir = os.path.join("supabase", "docker", "volumes", "db")
    if not os.path.exists(athelia_sh_path):
        log.error(f"File {athelia_sh_path} not found.")
        return
    convert_line_endings(athelia_sh_path)
    shutil.copy(athelia_sh_path, supabase_db_dir)

def prepare_open_webui_tools_filesystem_env(env_vars):
    """Write env_vars to .env and compose.yaml to open-webui/tools/servers/filesystem."""
    env_file = os.path.join("open-webui", "tools", "servers", "filesystem", ".env")
    built_env_vars = env_vars
    built_env_vars['COMPOSE_IGNORE_ORPHANS'] = 'true'
    write_dotenv_file(env_file, built_env_vars)

    docker_compose_path = os.path.join("open-webui", "tools", "servers", "filesystem", "compose.yaml")
    log.info(f"Writing {docker_compose_path}...")
    try:
        with open(docker_compose_path, 'w', newline='\n') as f:
            f.write(textwrap.dedent("""\
                services:
                  open-webui-filesystem:
                    container_name: open-webui-filesystem
                    restart: unless-stopped
                    build:
                      context: .
                    ports:
                      - 8091:8091
                    extra_hosts:
                      - host.docker.internal:host-gateway
                    volumes:
                      - ${PROJECTS_PATH:-../shared}:/nonexistent/tmp
                    environment:
                      - PROJECTS_PATH
                """))
    except FileNotFoundError:
        log.error(f"Exception: File '{docker_compose_path}' not found.")

def prepare_opencode_config(env_vars):
    """Set the default OpenCode model in opencode.jsonc"""
    file_path = os.path.join("opencode", "opencode.jsonc")
    if not os.path.exists(file_path):
        log.error(f"File {file_path} not found.")
        return
    log.info(f"Setting OpenCode {llama} model in {file_path}...")
    llm = llama.strip().lower()
    ollama_model = env_vars.get('OLLAMA_DEFAULT_MODEL')
    llamacpp_model = env_vars.get('LLAMACPP_DEFAULT_MODEL')
    old_model = f"{llm}/{ollama_model}" if llama_cpp else f"{llm}/{llamacpp_model}"
    new_model = f"{llm}/{llamacpp_model}" if llama_cpp else f"{llm}/{ollama_model}"
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        modified_content = content.replace(old_model.encode(), new_model.encode())
        with open(file_path, 'wb') as f:
            f.write(modified_content)
    except Exception as e:
        log.error(f"Exception: Configuration - {llama} model: {e}")

def clean_dir_path(dir_path, restore=True, quiet=False):
    """delete and recreate directory path"""
    if os.path.exists(dir_path):
        if not quiet:
            log.info(f"Cleaning directory: {dir_path}...")
        shutil.rmtree(dir_path)
        if restore:
            os.makedirs(dir_path, exist_ok=True)

def destroy_ai_suite(profile, install):
    """Stop and remove AI-Suite containers and volumes (using compose file)
       for the specified profile arguments.
    """
    if not profile:
        log.error("Profile required to destroy containers")
        return
    insert = "and volumes for" if install else "for"
    insert = f"Destroying {name} containers {insert}"
    log.info(f"{insert} profile arguments: {profile}...", extra=log_bright)
    cmd = ["docker", "compose", "-p", "ai-suite"]
    for argument in profile:
        cmd.extend(["--profile", argument])
    cmd.extend(["-f", "docker-compose.yml", "down"])
    if install:
        cmd.extend(["--volumes"])
    run_command(cmd)
    if install:
        supabase_data = os.path.join("supabase", "docker", "volumes", "db", "data")
        clean_dir_path(supabase_data, restore=False)
        cmd = ["docker", "volume", "prune", "--force"]
        run_command(cmd)
    log.info("="*60, extra=LSHF.style(logging.INFO, LSHF.BLUE))
    log.info(f"{name} services 'down' completed.", extra=log_bright)

def operate_ai_suite(operation, profile, environment, env_vars):
    """Start, stop, pause or pull the AI-Suite containers (using its compose file)
       for the specified profile arguments and environment argument.
    """
    if not profile:
        log.error("Profile required to perform operations")
        return
    if not operation:
        operation = "stop"

    with open('./state/.operation', 'w', newline='\n') as f:
        f.write(operation + ':' + llama.lower())

    supabase = False
    open_webui = False
    # WebUI built - nothing to pull, Supabase pulled with suite via include.
    if operation != 'pull':
        supabase = any(p for p in profile if p in ['supabase', 'ai-all'])
        open_webui = any(p for p in profile if p in open_webui_all_profiles)

    if operation == 'start' and environment:
        load_dotenv_vars(env_vars)
        if supabase:
            start_supabase(environment, False)
            log.info("Waiting for Supabase to initialize...", extra=log_bright)
            wait_with_progress(10)
        if open_webui:
            start_open_webui_tools_filesystem(environment, False)
            log.info("Waiting for Open WebUI Tool Filesystem to initialize...",
                     extra=log_bright)
            wait_with_progress(2)
        start_ai_suite(profile, environment, False)
        display_service_endpoints(profile, supabase, env_vars)
        return

    if operation == 'stop':
        insert = "Stopping"
    elif operation == 'pull':
        insert = "Pulling"
    else:
        insert = "Pausing" if operation == 'pause' else None
    container = "images" if operation == 'pull' else "containers"
    log.info(f"{insert} '{name}' {container} for profile arguments: {profile}...")
    base = ["docker", "compose", "-p", "ai-suite"]
    if supabase:
        cmd = base + ["-f", "supabase/docker/docker-compose.yml", operation]
        run_command(cmd)
    if open_webui:
        cmd = base + ["-f", "open-webui/tools/servers/filesystem/compose.yaml", operation]
        run_command(cmd)
    cmd = base
    if profile:
        for argument in profile:
            cmd.extend(["--profile", argument])
    cmd.extend(["-f", "docker-compose.yml", operation])
    run_command(cmd)
    insert = operation
    if operation == 'pull':
        insert.join(' and prune')
        cmd = ["docker", "image", "prune", "--force"]
        run_command(cmd)
    log.info("="*60, extra=LSHF.style(logging.INFO, LSHF.BLUE))
    log.info(f"{name} services image '{operation}' completed.", extra=log_bright)

def start_built_container(compose_file=None, environment=None, build=False):
    """Start the locally built container services (using its compose file)."""
    cmd = ["docker", "compose", "-p", "ai-suite", "-f", compose_file]
    if environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d"])
    if build:
        cmd.extend(["--build"])
    run_command(cmd)

def start_supabase(environment=None, build=False):
    """Start the Supabase services (using its compose file)."""
    log.info("Starting Supabase services...")
    compose_file = "supabase/docker/docker-compose.yml"
    start_built_container(compose_file, environment, build)

def start_open_webui_tools_filesystem(environment=None, build=False):
    """Start the Open WebUI Tools Filesystem services (using its compose file)."""
    log.info("Starting Open WebUI Tools Filesystem services...")
    compose_file = "open-webui/tools/servers/filesystem/compose.yaml"
    start_built_container(compose_file, environment, build)

def start_ai_suite(profile=None, environment=None, build=False):
    """Start the AI-Suite services (using its compose file) for the specified
       profile arguments and environment argument.
    """
    log.info(f"Starting {name} services for profile arguments: {profile}...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile:
        for argument in profile:
            cmd.extend(["--profile", argument])
    else:
        cmd.extend(["--profile", 'open-webui'])
    cmd.extend(["-f", "docker-compose.yml"])
    if environment == "private":
        cmd.extend(["-f", "docker-compose.override.private.yml"])
    if environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d"])
    if build:
        cmd.extend(["--remove-orphans"])
    run_command(cmd)

def generate_searxng_secret_key():
    """Generate a secret key for SearXNG based on the current platform."""
    log.info("Checking SearXNG settings...")
    # Define paths for SearXNG settings file
    settings_path = os.path.join("searxng", "settings.yml")
    settings_base_path = os.path.join("searxng", "settings-base.yml")
    # Check if settings-base.yml exists
    if not os.path.exists(settings_base_path):
        log.warning(f"SearXNG base settings file not found at {settings_base_path}")
        return
    # Check if settings.yml exists, if not create it from settings-base.yml
    if not os.path.exists(settings_path):
        log.info(f"SearXNG settings.yml not found. Creating from {settings_base_path}...")
        try:
            shutil.copyfile(settings_base_path, settings_path)
            log.info(f"Created {settings_path} from {settings_base_path}")
        except Exception as e:
            log.error(f"Exception: Create SearXNG settings.yml: {e}")
            return
    else:
        log.info(f"SearXNG settings.yml already exists at {settings_path}")
    log.info("Generating SearXNG secret key...")
    # Run the appropriate platform command
    try:
        if system == "Windows":
            log.info("Using Windows PowerShell to generate secret key...")
            # PowerShell command to generate a random key and replace in the settings file
            ps_command = [
                "powershell", "-Command",
                "$randomBytes = New-Object byte[] 32; " +
                "(New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomBytes); " +
                "$secretKey = -join ($randomBytes | ForEach-Object { \"{0:x2}\" -f $_ }); " +
                "(Get-Content searxng/settings.yml) -replace 'ultrasecretkey', $secretKey | Set-Content searxng/settings.yml"]
            subprocess.run(ps_command, check=True)
        elif system == "Darwin":  # macOS
            log.info("Using macOS sed command with empty string parameter...")
            # macOS sed command requires an empty string for the -i parameter
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", "", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)
        else:  # Linux and other Unix-like systems
            log.info("Using standard Linux/Unix sed command...")
            # Standard sed command for Linux
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)
        log.info("SearXNG secret key generated successfully.", extra=log_bright)
    except Exception as e:
        log.error(f"Exception: Generate SearXNG secret key: {e}.")
        log.info("You may need to manually generate the secret key:", extra=log_bright)
        if system == "Windows":
            log.info(
                """- Windows (PowerShell):
                     $randomBytes = New-Object byte[] 32
                     (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomBytes)
                     $secretKey = -join ($randomBytes | ForEach-Object { "{0:x2}" -f $_ })
                     (Get-Content searxng/settings.yml) -replace 'ultrasecretkey', $secretKey | Set-Content searxng/settings.yml""",
                extra=log_bright)
        elif system == "Darwin":
            log.info(
                """- macOS:
                     sed -i '' "s|ultrasecretkey|$(openssl rand -hex 32)|g" searxng/settings.yml""", extra=log_bright)
        else:
            log.info(
                """- Linux:
                     sed -i "s|ultrasecretkey|$(openssl rand -hex 32)|g" searxng/settings.yml""", extra=log_bright)

def check_and_fix_docker_compose_for_searxng():
    """Check and modify docker-compose.yml for SearXNG first run."""
    docker_compose_path = "docker-compose.yml"
    if not os.path.exists(docker_compose_path):
        log.error(f"Docker Compose file not found at {docker_compose_path}")
        return
    try:
        # Default to first run
        is_first_run = True
        # Check if Docker is running and if the SearXNG container exists
        try:
            # Check if the SearXNG container is running
            container_check = subprocess.run(
                ["docker", "ps", "--filter", "name=searxng", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True)
            searxng_containers = container_check.stdout.strip().split('\n')
            # If SearXNG container is running, check inside for uwsgi.ini
            if any(container for container in searxng_containers if container):
                container_name = next(container for container in searxng_containers if container)
                log.info(f"Found running SearXNG container: {container_name}")
                # Check if uwsgi.ini exists inside the container
                container_check_cmd = \
                    "[ -f /etc/searxng/uwsgi.ini ] && echo 'found' || echo 'not_found'"
                container_check = subprocess.run(
                    ["docker", "exec", container_name, "sh", "-c", container_check_cmd],
                    capture_output=True, text=True, check=False)
                if "found" in container_check.stdout:
                    log.info("Found uwsgi.ini inside the SearXNG container - not first run")
                    is_first_run = False
                else:
                    log.info("uwsgi.ini not found inside the SearXNG container - first run")
                    is_first_run = True
            else:
                msg = "No running SearXNG container found - assuming first run"
                log.notice(msg) # type:ignore[reportAttributeAccessIssue]
                is_first_run = True
        except Exception as e:
            log.error(f"Exception: Check Docker container running: {e} - assuming first run")

        # Temporarily comment out the cap_drop line on first run
        if is_first_run:
            log.info("First run detected for SearXNG. Temporarily commenting 'cap_drop:' directive...")
            with open(docker_compose_path, 'r+', newline='\n') as f:
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                commented = False
                searxng_found = False
                for line in lines:
                    if not commented:
                        compare = line.strip()
                        if compare == 'searxng:':
                            searxng_found = True
                        if searxng_found:
                            if compare == 'cap_drop:':
                                line = "   #cap_drop:\n"
                            if compare == '- ALL':
                                line = "   #  - ALL  # Temporarily commented out for first run\n"
                                commented = True
                                searxng_found = False
                                log.info("SearXNG 'cap_drop:' directive temporarily commented...")
                    f.write(line)
            msg = "After the first run completes successfully, uncomment 'cap_drop:' " \
                      "in docker-compose.yml for security."
            log.notice(msg) # type:ignore[reportAttributeAccessIssue]
        else:
            # Read the docker-compose.yml file
            with open(docker_compose_path, 'r') as f:
                content = f.read()
            # Uncomment the cap_drop line
            cap_drop_comment = "   #cap_drop:\n   #  - ALL  # Temporarily commented out for first run\n"
            if cap_drop_comment in content:
                log.info(f"SearXNG has been initialized. Uncommenting 'cap_drop:' directive for security...")
                cap_drop = "    cap_drop:\n      - ALL\n"
                modified_content = content.replace(cap_drop_comment, cap_drop)
                # Write the modified content back
                with open(docker_compose_path, 'w', newline='\n') as f:
                    f.write(modified_content)
    except Exception as e:
        log.error(f"Exception: Check/modify docker-compose.yml for SearXNG: {e}")

def convert_line_endings(file_path):
    """Convert Windows line endings to Linux/Unix/MacOS line endings."""
    try:
        CR_LF = b'\r\n'
        LF = b'\n'
        with open(file_path, 'rb') as f:
            content = f.read()
        modified_content = content.replace(CR_LF, LF)
        with open(file_path, 'wb') as f:
            f.write(modified_content)
    except FileNotFoundError:
        log.error(f"Exception: File '{file_path}' not found.")

# Treat Selfhosted Supavisor Pooler Keeps Restarting.
# No longer needed as I am treating line edgings on git pull above
# See: https://github.com/supabase/supabase/issues/30210
def convert_supabase_pooler_line_endings():
    """Convert Pooler.exs to Linux/Unix/MacOS line endings."""
    if system == "Windows":
        file_path = "supabase/docker/volumes/pooler/pooler.exs"
        if not os.path.exists(file_path):
            log.error(f"Pooler file not found at {file_path}")
            return
        log.info("Converting supavisor pooler line endings...")
        convert_line_endings(file_path)


def docker_compose_include(supabase, filesystem, verbose):
    """Add or remove Supabase and Filesystem include compose.yml in docker-compose.yml"""
    compose_file = "docker-compose.yml"
    supabase_compose_file = "supabase/docker/docker-compose.yml"
    filesystem_compose_file = "open-webui/tools/servers/filesystem/compose.yaml"
    if not os.path.exists(compose_file):
        log.error(f"Docker Compose file '{compose_file}' not found - include skipped...")
        return
    if supabase and not os.path.exists(supabase_compose_file):
        if verbose:
            log.warning(f"Include file '{supabase_compose_file}' not found.")
        supabase = False
    if filesystem and not os.path.exists(filesystem_compose_file):
        if verbose:
            log.warning(f"Include file '{filesystem_compose_file}' not found.")
        filesystem = False
    if verbose:
        supabase_ins = "add" if supabase else "remove"
        filesystem_ins = "add" if filesystem else "remove"
        log.info(
            f"Perform {supabase_ins} Supabase and {filesystem_ins} Filesystem "
            f"'include:' in {compose_file}...")
    include = supabase or filesystem
    compose_include = "include:\n"
    supabase_include = f"  - ./{supabase_compose_file}\n"
    filesystem_include = f"  - ./{filesystem_compose_file}\n"

    try:
        with open(compose_file, 'r') as f:
            content = f.read()

        if include:
            if compose_include in content:
                content = content.replace(compose_include, "")
            else:
                if verbose:
                    log.info(f"Adding 'include:' element to {compose_file}...")
                content = "\n" + content
        elif compose_include in content and verbose:
            if verbose:
                log.info(f"Removing 'include:' element from {compose_file}...")

        if supabase and supabase_include not in content:
            if verbose:
                log.info(f"Adding include file ./{supabase_compose_file}...")
            content = supabase_include + content
        elif not supabase and supabase_include in content:
            if verbose:
                log.info(f"Removing include file ./{supabase_compose_file}...")
            content = content.replace(supabase_include, "")

        if filesystem and filesystem_include not in content:
            if verbose:
                log.info(f"Adding include file ./{filesystem_compose_file}...")
            content = filesystem_include + content
        elif not filesystem and filesystem_include in content:
            if verbose:
                log.info(f"Removing include file ./{filesystem_compose_file}...")
            content = content.replace(filesystem_include, "")

        if include and not compose_include in content:
            content = compose_include + content
        elif not include and compose_include in content:
            content = content.replace(compose_include + "\n", "")

        with open(compose_file, 'w', newline='\n') as f:
            f.write(content)
    except Exception as e:
        log.error(f"Exception: Set 'include:' in {compose_file}: {e}")

def normalize_path(path):
    """Normalize path for current platform"""
    if path:
        if path.startswith('~'):
            path = os.path.expanduser(path)
        elif path.strip() == '.':
            path = os.getcwd()
        path = os.path.abspath(path)
    return path

def get_dotenv_vars(env_file=None, force=False, auto_config=False, profile=None):
    """Load environment variables from .env file"""
    if env_file is None:
        env_file = os.path.join(".env")

    valid_env_file = os.path.exists(env_file)
    if not valid_env_file:
        if os.path.exists(".env.example"):
            shutil.copy('.env.example', '.env')
            valid_env_file = os.path.exists(env_file)
            if valid_env_file:
                auto_config = str(dotenv.get_key(env_file, 'AC')).lower() == 'true'
            valid_env_file = False
            if not auto_config:
                log.warning("The .env file was not found - it was created from .env.example template")
                log.critical("⚠️ IMPORTANT: Edit .env file with secure passwords and keys - exiting...")
                return {}
        else:
            log.critical("The .env.example file was not found - exiting...")
            return {}
    else:
        auto_config = str(dotenv.get_key(env_file, 'AC')).lower() == 'true'

    if not auto_config:
        with open(env_file, 'r') as f:
            env_content = f.read()
        default_secrets = []
        modules = profile if profile else ['ai-all']
        if modules:
            if any(m for m in modules if m in ['n8n', 'n8n-all', 'ai-all']):
                default_secrets.extend([
                    'N8N_ENCRYPTION_KEY=generate using gen_n8ncrypt',
                    'N8N_RUNNERS_AUTH_TOKEN=generate using gen_hex:32',
                    'N8N_USER_MANAGEMENT_JWT_SECRET=generate using gen_hex:32',
                    'POSTGRES_PASSWORD=generate using gen_hex:16'])
            if any(m for m in modules if m in ['supabase', 'ai-all']):
                default_secrets.extend([
                    'JWT_SECRET=generate using gen_key:secret',
                    'ANON_KEY=generate using gen_key:anon_sym',
                    'SERVICE_ROLE_KEY=generate using gen_key:service_role_sym',
                    'ANON_KEY_ASYMMETRIC=generate using gen_key:anon_asym',
                    'SERVICE_ROLE_ASYMMETRIC=generate using gen_key:service_role_asym',
                    'SUPABASE_PUBLISHABLE_KEY=generate using gen_key:client',
                    'SUPABASE_SECRET_KEY=generate using gen_key:server',
                    'JWT_KEYS=generate using gen_key:keys',
                    'JWT_JWKS=generate using gen_key:jwks',
                    'SECRET_KEY_BASE=generate using gen_token:48',
                    'VAULT_ENC_KEY=generate using gen_hex:16',
                    'PG_META_CRYPTO_KEY=generate using gen_token:24',
                    'DASHBOARD_PASSWORD=generate using gen_hex:16',
                    'LOGFLARE_PUBLIC_ACCESS_TOKEN=generate using gen_token:24',
                    'LOGFLARE_PRIVATE_ACCESS_TOKEN=generate using gen_token:24',
                    'S3_PROTOCOL_ACCESS_KEY_ID=generate using gen_hex:16',
                    'S3_PROTOCOL_ACCESS_KEY_SECRET=generate using gen_hex:16'])
            if any(m for m in modules if m in ['flowise', 'ai-all']):
                default_secrets.extend([
                    'FLOWISE_PASSWORD=generate using gen_hex:16'])
            if any(p for p in modules if p in ['neo4j', 'ai-all']):
                default_secrets.extend([
                    'NEO4J_PASSWORD=generate using gen_hex:16'])
            if any(m for m in modules if m in ['langfuse', 'ai-all']):
                default_secrets.extend([
                    'CLICKHOUSE_PASSWORD=generate using gen_hex:16',
                    'MINIO_ROOT_PASSWORD=generate using gen_hex:16',
                    'LANGFUSE_SALT=generate using gen_hex:16',
                    'NEXTAUTH_SECRET=generate using gen_hex:16',
                    'ENCRYPTION_KEY=generate using gen_hex:16'])
            if any(m for m in modules if m in ['caddy', 'nginx']):
                default_secrets.extend([
                    'PROXY_AUTH_PASSWORD=generate using gen_bcrypt'])
            if any(m for m in modules if m in ['authelia']):
                default_secrets.extend([
                    'AUTHELIA_SESSION_SECRET=generate using gen_hex:32',
                    'AUTHELIA_STORAGE_ENCRYPTION_KEY=generate using gen_hex:32',
                    'AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET=generate using gen_hex:32'])
        unset_secrets = []
        for secret in default_secrets:
            if secret in env_content:
                unset_secrets.append(secret)
        if unset_secrets and not force:
            log.critical("YOUR .env FILE CONTAINS DEFAULT VALUES THAT NEED TO BE CHANGED!")
            for secret in unset_secrets:
                log.critical(f"⚠️ CHANGE THIS VALUE ⚠️: {secret}")
            log.critical("Exiting...")
            return {}

    env_vars = dotenv.dotenv_values(env_file)
    if not valid_env_file:
        os.remove(env_file) if os.path.exists(env_file) else None
    path = env_vars.get('PROJECTS_PATH')
    path = os.path.join('~', 'projects') if not path else path
    env_vars['PROJECTS_PATH'] = normalize_path(path)

    return env_vars

def load_dotenv_vars(env_vars):
    """Load working environment variables into environment"""
    if env_vars:
        log.info("Loading working environment variables...")
        for env, var in env_vars.items():
            if not var:
                continue
            os.environ[env] = var
    else:
        env_file = os.path.join(".env")
        if not os.path.exists(env_file):
            if not get_dotenv_vars():
                sys.exit(1)
        log.info("Loading .env environment variables...")
        dotenv.load_dotenv(env_file)

def write_dotenv_file(env_file, env_vars):
    """Copy .env to .env in target compose file destination."""
    if env_file is None:
        log.error("The .env file path to be written is not defined!")
        return
    if env_vars is None:
        log.error("The env_vars dictionary to be written is empty!")
        return
    log.info(f"Writing .env file to {env_file}...")
    with open(env_file, 'w', newline='\n') as f:
        now = " ".join(['on:', datetime.datetime.now().ctime()])
        f.seek(0)
        f.truncate()
        f.write(f"# {now} - Generated {name} working .env environment variables.")
        f.write('\n')
        for env, var in env_vars.items():
            if not var:
                continue
            quoted_var = var if var.isalnum() else f"'{var}'"
            f.write("".join([env, '=', quoted_var, '\n']))

def set_dotenv_var(env_file, env, var, header):
    """Set or unset an environment variable and add optional header in .env file"""
    if not env:
        log.error("A valid .env key was not specified.")
        return
    if env_file is None:
        env_file = os.path.join(".env")
    if not var:
        try:
            with open(env_file, 'r+', newline='\n') as f:
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                for line in lines:
                    line_array = line.strip().split('=')
                    if len(line_array) > 1 and env == line_array[0].strip():
                        var_array = line_array[1].strip().split('#')
                        mod_line = line
                        if len(var_array) > 1 and var == var_array[0].strip():
                            mod_line = ''.join([env, '=    #', var_array[1], '\n'])
                        elif len(var_array) == 1:
                            mod_line = ''.join([env, '=\n'])
                        line = mod_line
                        log.notice(f"Value for {env} removed...") # type:ignore[reportAttributeAccessIssue]
                    f.write(line)
        except FileNotFoundError:
            log.error(f"Exception: File '{env_file}' not found.")
        return
    quote_mode = "auto"
    if header is not None:
        with open(env_file, 'r') as f:
            content = f.read()
        if not header in content:
            quote_mode = "never"
            env = "".join([header, env])
    msg_var = '***' if env == 'AC_PASSWORD' else var
    log.info(f"Set '{env}' to '{msg_var}' in {env_file}...")
    dotenv.set_key(env_file, env, var, quote_mode)

def configure_n8n_database_settings(supabase):
    """Set n8n database depends_on and Postgres profiles and volume in Docker Compose file."""
    compose_file = os.path.join("docker-compose.yml")
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        old_vol = "postgres_data" if supabase else "langfuse_postgres_data"
        old_vol_regex = r"\b{}\b\:".format(old_vol)
        if re.search(old_vol_regex, content):
            new_vol = "langfuse_postgres_data:" if supabase else "postgres_data:"
            log.info(f"Set Postgres volume: to '{new_vol}' from '{old_vol}' in {compose_file}...")
            modified_content = re.sub(old_vol_regex, new_vol, content)
            with open(compose_file, 'w', newline='\n') as f:
                f.write(modified_content)

        postgres_profiles = 'postgres:\n    profiles: ["n8n", "langfuse", "n8n-all",'
        supabase_profiles = 'postgres:\n    profiles: ["langfuse",'
        old_profiles = postgres_profiles if supabase else supabase_profiles
        old_profiles_regex = re.escape(old_profiles)
        if re.search(old_profiles_regex, content):
            new_profiles = supabase_profiles if supabase else postgres_profiles
            insert = "'langfuse'" if supabase else "'n8n' and 'langfuse'"
            log.info(f"Set Postgres profiles: to include {insert} in {compose_file}...")
            modified_content = re.sub(old_profiles_regex, new_profiles, content)
            with open(compose_file, 'w', newline='\n') as f:
                f.write(modified_content)

        with open(compose_file, 'r+', newline='\n') as f:
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            n8n_updated = False
            n8n_update = False
            old_db = "postgres:" if supabase else "db:"
            new_db = "db:" if supabase else "postgres:"
            for line in lines:
                if not n8n_updated:
                    if line == '  n8n-import:\n':
                        n8n_update = True
                    if line == '  n8n-runner:\n':
                        n8n_updated = True
                        n8n_update = False
                    if n8n_update:
                        if line == f'      {old_db}\n':
                            line = f"      {new_db}\n"
                    if n8n_updated:
                        log.info(f"Set n8n database depends_on: to '{new_db}' "
                                f"from '{old_db}' in {compose_file}...")
                f.write(line)
    except Exception as e:
        log.error(f"Exception: Update n8n database settings in {compose_file}: {e}")

def docker_container_is_running(container):
    """:return: True if container name found in output check, else False."""
    cmd = " ".join(['docker', 'ps', '--format', '"{{.Names}}"', '--filter',
                   f'name=^/{container}$'])
    try:
        bytes = subprocess.check_output(cmd, shell=True)
        running = bytes.find(container.encode()) != -1
        if log.root.level == logging.DEBUG:
            color = LSHF.WHITE if running else LSHF.RED
            style = LSHF.style(logging.INFO, color)
            insert = ('is', 'running.') if running else ('not', 'running!')
            raw_msg = " ".join([container, insert[0], insert[1]])
            log.debug("Container {}".format(raw_msg), extra=style)
        return running
    except subprocess.CalledProcessError:
        return False

def docker_object_exists(object, name):
    """Confirm Docker volume or container exist"""
    if object not in ['container', 'volume']:
        log.error(f"Invalid object: {object}, expected container or volume.")
        return False
    if not name:
        log.error(f"Object {object} name was not specified.")
        return False
    cmd = ['docker', object, 'inspect', '--format', '"{{ .Name }}"', name]
    try:
        stdout = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        return stdout.find(name) != 1
    except subprocess.CalledProcessError as e:
        log.error(e.stderr)
        return False

def docker_volume_data(operation):
    """Backup or restore named volume mount data to or from backup file"""
    if not operation:
        operation = "backup-data"
    elif not operation in ['backup-data', 'restore-data']:
        log.error(f"Invalid operation: {operation}, expected backup-data or restore-data.")
        return

    data_volumes = [
        ('n8n_node_data',             '/home/node/.n8n',          'n8n'),
        ('neo4j_data',                '/data',                    'neo4j'),
        ('neo4j_config_data',         '/config',                  'neo4j'),
        ('ollama_data',               '/root/.ollama',            'ollama'),
        ('opencode_data',             '/root/.config/opencode',   'opencode'),
        ('open_webui_data',           '/app/backend/data',        'open-webui'),
        ('open_webui_pipelines_data', '/app/pipelines',           'open-webui-pipelines'),
        ('postgres_data',             '/var/lib/postgresql/data', 'postgres'),
        ('qdrant_data',               '/qdrant/storage',          'qdrqnt'),
        ('redis_valkey_data',         '/data',                    'redis'),
        ('langfuse_clickhouse_data',  '/var/lib/clickhouse',      'clickhouse'),
        ('langfuse_minio_data',       '/data',                    'minio'),
        ('llamacpp_data',             '/root/.cache',             'llamacpp'),
        ('caddy_data',                '/data',                    'caddy'),
        ('caddy_config_data',         '/config',                  'caddy'),
        ('db-config',                 '/etc/postgresql-custom',   'supabase-db'),
        ('deno-cache',                '/root/.cache/deno',        'supabase-edge-functions')
    ]
    restore_data = operation == 'restore-data'
    backup_dir = os.path.join(os.getcwd(), "backup")
    for volume, mount, container in data_volumes:
        file_name = f"{volume}.tar.gz"
        cmd = ["docker", "run", "--rm",
               "--mount", f"source={volume},target={mount}",
               "-v", f"{backup_dir}:/backup", container]
        if restore_data:
            backup_file = os.path.join(backup_dir, file_name)
            if not os.path.exists(backup_file):
                continue
            with gzip.open(backup_file, "rb") as f:
                data = f.read(1)
            if len(data) == 0:
                continue
            cmd.extend(["tar", "-xzvf", f"/backup/{file_name}", "-C", "/"])
        else: # backup data
            if not docker_object_exists('volume', volume):
                continue
            cmd.extend(["tar", "-czvf", f"/backup/{file_name}", mount])
        run_command(cmd)

def wait_with_progress(seconds: int, level=logging.INFO, color=None, width=60):
    """Progress bar for waiting on service to initialize"""
    begin = time.monotonic()
    end = LSHF.suffix()
    colors = LSHF.LOG_LEVEL_COLOR.get(level, LSHF.COLOR)
    level_name = logging.getLevelName(level)
    level_color = colors['level']
    name_color = colors['name']
    fill_color = colors['msg'] if not color else color
    header = ("{}{}{}{}:{} {}{}{} {}").format(
        LSHF.prefix(color=name_color, italic=True), name, end,
        LSHF.prefix(LSHF.WHITE), end,
        LSHF.prefix(level_color), level_name, end, LSHF.prefix(fill_color))
    while True:
        elapsed = time.monotonic() - begin
        progress = min(elapsed, seconds)
        percent = progress / seconds
        filled = int(width * percent)
        bar = '█' * filled + '-' * (width - filled)
        rendition = ("\r{}|{}| {:6.2f}%{}").format(header, bar, percent * 100, end)
        print(rendition, end="", flush=True)
        if elapsed >= seconds:
            break
        time.sleep(0.05) # smooth updates (~20 FPS)
    print() # move to next line when done

def docker_container_is_running(container):
    """:Return True if container name found in output check, else False."""
    cmd = " ".join(['docker', 'inspect', '-f', '{{.State.Running}}', container])
    try:
        check = subprocess.check_output(cmd).decode().strip()
        running = check == "true"
        if log.root.level == logging.DEBUG:
            color = LSHF.WHITE if running else LSHF.RED
            style = LSHF.style(logging.INFO, color)
            insert = ('is', 'running.') if running else ('not', 'running!')
            raw_msg = " ".join([container, insert[0], insert[1]])
            log.debug("Container {}".format(raw_msg), extra=style)
        return running
    except subprocess.CalledProcessError:
        return False

def display_service_endpoints(profile, supabase, env_vars={}):
    """Display AI-Suite installation or operationstatus"""
    if not profile:
        log.error("Profile required to display service endpoints")
        return

    host = env_vars.get('AC_DOMAIN', 'localhost')
    private = str(env_vars.get('AC_LOCAL')).lower()
    protocol = 'http' if private else 'https'
    url = f'{protocol}://{host}'

    # This dictionary holds a list of touples (container, Module Name, Endpoint)
    # grouped by module - aka profile argument
    ai_suite_modules = {
        'n8n': [
            ('n8n',                 'n8n',            url + ':5678'),
            ('mcp-gateway',         'MCP Gateway',    url + ':8060/'),
            ('qdrant',              'QDrant',         url + ':6333/dashboard'),
            ('postgres',            'PostgreSQL',     url + ':5432/'),
            ('supabase-kong',       'Supabase',       url + ':8000'),
            ('supabase-analytics',  'Logflare',       url + ':4000/dashboard'),
            ('redis',               'Redis',          url + ':6379/'),
            ('n8n-runner',          'n8n Runner',           ''),
            ('n8n-worker',          'n8n Worker',           ''),
            ('n8n-worker-runner',   'n8n Worker Runner',    '')
        ],
        'n8n-all': [
            ('n8n',                 'n8n',                    url + ':5678'),
            ('open-webui',          'Open WebUI',             url + ':8080/'),
            ('open-webui-filesystem','Open WebUI Filesystem', url + ':8091/docs'),
            ('mcp-gateway',         'MCP Gateway',            url + ':8060/'),
            ('open-webui-mcpo',     'Open WebUI MCPO',        url + ':8090/'),
            ('qdrant',              'QDrant',                 url + ':6333/dashboard'),
            ('postgres',            'PostgreSQL',             url + ':5432/'),
            ('supabase-kong',       'Supabase',               url + ':8000'),
            ('supabase-analytics',  'Logflare',               url + ':4000/dashboard'),
            ('redis',               'Redis',                  url + ':6379/'),
            ('n8n-runner',          'n8n Runner',           ''),
            ('n8n-worker',          'n8n Worker',           ''),
            ('n8n-worker-runner',   'n8n Worker Runner',    '')
        ],
        'opencode': [
            ('opencode',            'Opencode', './opencode/run_opencode_docker.py'),
            ('mcp-gateway',         'MCP Gateway',            url + ':8060/')
        ],
        'open-webui': [
            ('open-webui',          'Open WebUI',             url + ':8080/'),
            ('mcp-gateway',         'MCP Gateway',            url + ':8060/'),
            ('open-webui-mcpo',     'Open WebUI MCPO',        url + ':8090/'),
            ('open-webui-filesystem','Open WebUI Filesystem', url + ':8091/docs')
        ],
        'open-webui-mcpo': [
            ('mcp-gateway',         'MCP Gateway',     url + ':8060/'),
            ('open-webui-mcpo',     'Open WebUI MCPO', url + ':8090/')
        ],
        'flowise': [
            ('flowise',             'Flowise',         url + ':3001/')
        ],
        'supabase': [
            ('supabase-kong',       'Supabase',        url + ':8000'),
            ('supabase-analytics',  'Logflare',        url + ':4000/dashboard'),
            ('supabase-pooler',     'Supavisor',       url + ':6543'),
            ('supabase-studio',     'Studio',              ''),
            ('supabase-auth',       'Auth',                ''),
            ('supabase-rest',       'PostgREST',           ''),
            ('realtime-dev.supabase-realtime', 'Realtime', ''),
            ('supabase-storage',    'Storage',             ''),
            ('supabase-imgproxy',   'imgproxy',            ''),
            ('supabase-meta',       'postgres-meta',       ''),
            ('supabase-db',         'PostgreSQL',          ''),
            ('supabase-edge-functions', 'Edge Runtime',    ''),
            ('supabase-vector',     'Vector',              '')
        ],
        'langfuse': [
            ('langfuse-web',        'Langfuse Web',    url + ':3000/'),
            ('langfuse-worker',     'Langfuse Worker', url + ':3030/'),
            ('clickhouse',          'ClickHouse',      url + ':8123/'),
            ('postgres',            'PostgreSQL',      url + ':5432/'),
            ('redis',               'Redis',           url + ':6379/'),
            ('minio',               'MinIO',           url + ':9001/')
        ],
        'searxng': [
            ('searxng',             'SearXNG',         url + ':8081/')
        ],
        'neo4j': [
            ('neo4j',               'Neo4j',           url + ':7473/')
        ],
        'caddy': [
            ('caddy',               'Caddy',           url + ':443/'),
            ('authelia',             'Authelia',         url + ':9091/')
        ],
        'nginx': [
            ('nginx',               'Nginx',           url + ':443/'),
            ('authelia',             'Authelia',         url + ':9091/')
        ],
        'cpu': [
            ('ollama',              'Ollama',          url + ':11434/')
        ],
        'gpu-nvidia': [
            ('ollama',              'Ollama',          url + ':11434/')
        ],
        'gpu-amd': [
            ('ollama',              'Ollama',          url + ':11434/')
        ],
        'cpp-cpu': [
            ('llamacpp',            'LLaMA.cpp',       url + ':8040')
        ],
        'cpp-gpu-nvidia': [
            ('llamacpp',            'LLaMA.cpp',       url + ':8040')
        ],
        'cpp-gpu-amd': [
            ('llamacpp',            'LLaMA.cpp',       url + ':8040')
        ]
    }

    module_list = []
    container_list = []
    module_names = set()
    proxy_in_profile = any(p in profile for p in ('caddy', 'nginx'))
    if supabase is None:
        supabase = any(p for p in profile if p in ['supabase', 'ai-all'])

    def skip_module(module, module_name):
        if llama_cpp and module in ('cpu', 'gpu-nvidia', 'gpu-amd'):
            return True
        if not llama_cpp and module in ('cpp-cpu', 'cpp-gpu-nvidia', 'cpp-gpu-amd'):
            return True
        if module in ('n8n', 'n8n-all'):
            if supabase and module_name == 'Postgres':
                return True
            if not supabase and module_name in ('Supabase', 'Logflare'):
                return True
        if module in ('caddy', 'nginx') and module not in profile:
            return True
        if module_name == 'Authelia' and not proxy_in_profile:
            return True
        return False

    def skip_container(container):
        if not container or container in container_list:
            return True
        if not supabase and 'supabase-' in container:
            return True
        if llama_on_host and container in ('ollama', 'llamacpp'):
            return True
        return False

    modules = ai_suite_modules.keys() if 'ai-all' in profile else profile

    for module in modules:
        module_items = ai_suite_modules.get(module, [])
        for container, module_name, endpoint in module_items:
            if module_name in module_names:
                continue
            if skip_module(module, module_name):
                continue
            module_names.add(module_name)
            module_list.append((container, module_name, endpoint))
            if skip_container(container):
                continue
            container_list.append(container)

    failed_container_list = [
        container for container in container_list
        if not docker_container_is_running(container)
    ]

    started_ok = len(failed_container_list) == 0
    header = ("{} IS RUNNING").format(name.upper()) if started_ok else \
             ("{} STARTUP ENCOUNTERED FAILURES").format(name.upper())
    emoji = '✅' if started_ok else '⚠️'
    color = LSHF.GREEN if started_ok else LSHF.YELLOW
    header_style = {
        'prefix': ("{0}  {1}{2}").format(
            emoji, LSHF.prefix(color, bold=True, underline=started_ok), header),
        'suffix': LSHF.suffix()}
    header_style.update({'purge_msg': 'True'})
    info_style = LSHF.style(logging.INFO, color)
    line_style = LSHF.style(logging.INFO, LSHF.BLUE)
    fail_style = LSHF.style(logging.INFO, LSHF.RED)

    context_size = env_vars.get('LLAMA_ARG_CTX_SIZE') if llama_cpp else \
                   env_vars.get('OLLAMA_CONTEXT_LENGTH')
    model_name = env_vars.get('LLAMACPP_DEFAULT_MODEL') if llama_cpp else \
                 env_vars.get('OLLAMA_DEFAULT_MODEL')
    projects_path = env_vars.get('PROJECTS_PATH')

    log.info("")
    log.info("="*60, extra=line_style)
    log.info(header, extra=header_style)
    log.info("="*60, extra=line_style)
    log.info(f"LLM: {llama}", extra=info_style)
    log.info(f"Model: {model_name}", extra=info_style)
    log.info(f"Context Size: {context_size} tokens", extra=info_style)
    log.info(f"Projects Path: {projects_path}", extra=info_style)
    log.info("")
    log.info("Access Points:", extra=info_style)
    for container, module_name, access_point in module_list:
        if not access_point:
            continue
        emoji = '🚀' if module_name.lower() == 'opencode' else '🔗'
        module_prefix = LSHF.prefix(LSHF.GREEN)
        apoint_prefix = LSHF.prefix(LSHF.BLUE)
        if container in failed_container_list:
            emoji = '❌'
            module_prefix = LSHF.prefix(LSHF.YELLOW, italic=True)
            apoint_prefix = LSHF.prefix(LSHF.RED, italic=True)
        endpoint_prefix = ("{}• {:23s}{}{} {}{}").format(
            module_prefix, module_name + ":", LSHF.suffix(), emoji,
            apoint_prefix, access_point)
        endpoint_style = {'prefix': endpoint_prefix, 'suffix': LSHF.suffix()}
        endpoint_style.update({'purge_msg':'True'})
        raw_msg = ("• {:23s}{} {}").format(module_name + ":", emoji, access_point)
        log.info(raw_msg, extra=endpoint_style)
    if not started_ok:
        log.info("")
        msg = "This Docker container is not running:"
        if len(failed_container_list) > 1:
            msg = "These Docker containers are not running:"
        log.info(msg, extra=info_style)
        for container, module_name, access_point in module_list:
            if container in failed_container_list:
                log.info(("❌ {:30s} {}").format(container, module_name), extra=fail_style)
    log.info("="*60, extra=line_style)

def display_ac_env_vars(ac_env_vars):
    """Display auto-configure environment variable settings"""
    if not ac_env_vars:
        return

    header = ("{} Auto-configure Access Env Settings").format(name)
    emoji = '🚀'
    color = LSHF.GREEN
    header_style = {
        'prefix': ("{0} {1}{2}").format(
            emoji, LSHF.prefix(color, bold=True, underline=True), header),
        'suffix': LSHF.suffix()}
    header_style.update({'purge_msg': 'True'})
    line_style = LSHF.style(logging.INFO, LSHF.BLUE)
    env_prefix = LSHF.prefix(color)
    var_prefix = LSHF.prefix(LSHF.BLUE)

    log.info("")
    log.info("="*60, extra=line_style)
    log.info(header, extra=header_style)
    log.info("="*60, extra=line_style)

    for env_item in ac_env_vars:
        env_pair = env_item.split('=')
        if env_pair[0].endswith('_PASSWORD'):
            env_pair[1] = '***'
        emoji = '🌐'
        env_var_prefix = ("{}• {} {:18s}{}= {}{}").format(
            env_prefix, emoji, env_pair[0], LSHF.suffix(),
            var_prefix, env_pair[1])
        env_var_style = {'prefix': env_var_prefix, 'suffix': LSHF.suffix()}
        env_var_style.update({'purge_msg':'True'})
        raw_msg = ("• {} {:18s}= {}").format(emoji, env_pair[0], env_pair[1])
        log.info(raw_msg, extra=env_var_style)
    log.info("="*60, extra=line_style)

def setup_ai_suite_ac_auto_config(prompt_store, env_vars:dict={}):
    """Setup env_vars for self-hosted AI-Suite with Caddy/Nginx proxy and Authelia
       2FA identity and access management.
    """
    if not env_vars:
        log.error("The auto-configure env_vars dictionary is empty!")
        return []
    ac = env_vars.get('AC', 'False')
    if ac and ac.lower() != 'true':
        log.notice("Auto-configure is disabled. Set AC=True in .env to enable.") # type:ignore[reportAttributeAccessIssue]
        return []

    log.info(f"Auto-configuring {name} proxy and access...", extra=log_bright)

    prompt = prompt_store['p']
    if prompt:
        response = input(f"Use default auto-configure .env settings? y/n: (n)").strip()
    else:
        response = 'y'
    prompt = False if response.lower() == 'y' else prompt
    prompt_store['p'] = prompt
    response = None
    public = False

    # AC - bool
    ac_env_vars = [f'AC="{str(ac).lower()}"']
    # AC_SUDO_USER - str
    sudo_user = getpass.getuser()
    non_root = "non-root"
    if system == "Windows":
        non_root = " ".join(["WSL", non_root])
        cmd = ["wsl", "-e", "bash", "-c", "whoami"]
        try:
            completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
            sudo_user = completed.stdout.strip()
        except subprocess.CalledProcessError as e:
            log.error(f"Exception: WSL whoami: {e.stderr}")
    default = env_vars.get('AC_SUDO_USER', sudo_user)
    if prompt:
        response = input(f"Enter a {non_root} sudo user (current user: {default}): ").strip()
    default = response if response else default
    ac_env_vars.append(f'AC_SUDO_USER="{default}"')
    # AC_USERNAME - str
    default = env_vars.get('AC_USERNAME', 'AISuiteProxyUser')
    change_default = True if not default.isalnum() else False
    if prompt or change_default:
        response = None
        while not response:
            response = input(f"Enter proxy user name (required: {default}): ").strip()
            if not response:
                response = "AISuiteProxyUser"
                log.notice(f"The proxy user name was auto-generated as {response} and saved to .env.") # type:ignore[reportAttributeAccessIssue]
            if not response.isalnum():
                log.warning(f"Only alphanumeric characters are allowed. Response: {response}.")
                response = None
    default = response.strip() if response else default
    ac_env_vars.append(f'AC_USERNAME="{default}"')
    # AC_PASSWORD - str
    password = env_vars.get('AC_PASSWORD', '*******')
    change_default = True if password == '*******' else False
    if prompt or change_default:
        password = getpass.getpass(f"Enter hidden proxy user password (required: ***): ")
    if not password and change_default:
        import secrets
        password_length = 13
        password = secrets.token_urlsafe(password_length)
        log.notice(f"The proxy user password was auto-generated and saved to .env.") # type:ignore[reportAttributeAccessIssue]
    ac_env_vars.append(f'AC_PASSWORD="{password}"')
    # AC_LOG_PATH - str
    default = env_vars.get('AC_LOG_PATH', './access')
    ac_env_vars.append(f'AC_LOG_PATH="{default}"')
    # AC_LOCAL - bool
    default = env_vars.get('AC_LOCAL', 'False')
    default = True if str(default).lower() == 'true' else False
    if prompt:
        response = input("Is this a local (private) installation? y/n ({}): "
                         .format('y' if default else 'n')).strip()
    default = True if response and response.lower() == 'y' else default
    ac_env_vars.append(f'AC_LOCAL={str(default).lower()}')
    public = not default
    # AC_DOMAIN - str
    default = env_vars.get('AC_DOMAIN', 'ai-suite.fr' if public else 'local.pc')
    if prompt:
        response = input(f"Enter a domain ({default}): ").strip()
    default = response if response else default
    ac_env_vars.append(f'AC_DOMAIN="{default}"')
    # AC_CONFIRM - bool
    default = env_vars.get('AC_CONFIRM', 'False')
    default = True if str(default).lower() == 'true' else False
    if prompt:
        response = input("Send confirmation email on user registration? y/n ({}): "
                         .format('y' if default else 'n')).strip()
    default = True if response and response.lower() == 'y' else default
    ac_env_vars.append(f'AC_CONFIRM={str(default).lower()}')
    # AC_WITH_EXIM - bool
    if default:
        default = env_vars.get('AC_WITH_EXIM', 'False')
        default = True if str(default).lower() == 'true' else False
        #if prompt:
        #.   response = input("Add Exim SMTP server? y/n ({}): "
        #                     .format('y' if default else 'n')).strip()
        default = True if response and response.lower() == 'y' else default
        #ac_env_vars.append(f'AC_WITH_EXIM={str(default).lower()}')
    # AC_PROXY - str
    default = env_vars.get('AC_PROXY', 'Caddy')
    if prompt:
        response = input(f"Enter proxy (Caddy or Nginx: {default}): ").strip()
    if response:
        response = response.strip().lower()
        if response not in ['caddy', 'nginx']:
            log.warning(f"Invalid proxy specified: {response}. Using {default}.")
            response = None
    default = response if response else default
    ac_env_vars.append(f'AC_PROXY={default.lower()}')
    # AC_WITH_AUTHELIA - bool
    default = env_vars.get('AC_WITH_AUTHELIA', 'False')
    default = True if str(default).lower() == 'true' else False
    if prompt:
        response = input("Include Authelia 2FA (Two Factor Authentication)? y/n ({}): "
                         .format('y' if default else 'n')).strip()
    default = True if response and response.lower() == 'y' else default
    ac_env_vars.append(f'AC_WITH_AUTHELIA={str(default).lower()}')
    if default:
        # AC_EMAIL - str
        default = env_vars.get('AC_EMAIL', 'ai-suite.aisuiteautheliauser@local.pc')
        if prompt:
            response = input(f"Enter Authelia user email (required: {default}): ").strip()
        default = response if response else default
        ac_env_vars.append(f'AC_EMAIL="{default}"')
        # AC_DISPLAY_NAME - str
        default = env_vars.get('AC_DISPLAY_NAME', f'{name} User')
        change_default = True if not all(c.isalnum() or c.isspace() for c in default) else False
        if prompt or change_default:
            response = None
            while not response:
                response = input(f"Enter Authelia user display name (required: {default}): ").strip()
                if not response:
                    response = "AI Suite Authelia User"
                    log.notice(f"The Authelia user display name was auto-generated as {response} and saved to .env.") # type:ignore[reportAttributeAccessIssue]
                if not all(c.isalnum() or c.isspace() for c in response):
                    log.warning(f"Only alphanumeric characters and spaces are allowed. Response: {response}.")
                    response = None
        default = response.strip() if response else default
        ac_env_vars.append(f'AC_DISPLAY_NAME="{default}"')
        # AC_WITH_REDIS - bool
        default = env_vars.get('AC_WITH_REDIS', ('True' if public else 'False'))
        default = True if str(default).lower() == 'true' else False
        if prompt:
            response = input("Use Redis with Authelia? y/n ({}{}): "
                             .format('recommended: ' if public else '',
                                     'y' if default else 'n')).strip()
        default = True if response and response.lower() == 'y' else default
        ac_env_vars.append(f'AC_WITH_REDIS={str(default).lower()}')

    return ac_env_vars

def run_ai_suite_ac_auto_config(sudo_password, ac_env_vars):
    """Configure self-hosted AI-Suite with Caddy/Nginx proxy and Authelia 2FA
       identity and access management.
    """
    if not ac_env_vars:
        log.error(f"The auto-configure env_var list is empty!")
        return
    ac_script = os.path.normpath(os.path.join("access", "foo.sh"))
    if not os.path.exists(ac_script):
        log.error(f"Auto-configure script not found at {ac_script}")
        return
    if system == 'Windows':
        ac_script = ac_script.replace("\\", "/")
    ac_script = "".join(["./", ac_script])
    ac_log_file = "".join([ac_script, ".log"])
    ac_log = "".join([">", ac_log_file, " 2>&1"])
    cmd_msg = []
    for element in ac_env_vars:
        array = element.split('=')
        if array[0].endswith('_PASSWORD'):
            cmd_msg.append(f'{array[0]}="***"')
        else:
            cmd_msg.append(element)
    cmd = ["bash", "-c"]
    if system == "Windows":
        cmd = ["wsl", "-e"] + cmd
    cmd_msg = cmd + [" ".join(["env"] + cmd_msg + [ac_script])]
    raw_msg = " ".join([log_run_cmd, " ".join(cmd_msg)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd_msg)))
    cmd = cmd + [" ".join(["env"] + ac_env_vars + [ac_script])]
    try:
        completed = subprocess.run(
            cmd,
            input=(sudo_password) if sudo_password else None,
            text=True,
            check=True
        )
        sudo_password = None
        if completed.returncode != 0:
            log.error(f"Command: auto-configure: {completed.stderr}")
        else:
            info_style = LSHF.style(logging.INFO, LSHF.GREEN)
            log.info(f"See details in run log: {ac_log_file}", extra=info_style)
    except Exception as e:
        sudo_password = None
        if e:
            e_list = str(e).split(',')
            if len(e_list) == len(cmd):
                e_string = str(e_list[-1:])
                e_list = e_string.split(' ')
            if len(e_list) >= len(ac_env_vars):
                e_msg = []
                for e_item in e_list:
                    e_pair = e_item.split('=')
                    if e_pair[0].endswith('_PASSWORD'):
                        e_msg.append(f'{e_pair[0]}="***"')
                    else:
                        e_msg.append(e_item)
                log.error("Exception: auto-configure: {}.".format(" ".join(e_msg)))

def main():
    # Name and file globals
    global name, file
    name = INFO.get('name', 'placeholder')
    file = INFO.get('file', 'placeholder.py')

    # Detect operational status and current llama (Ollama/LLaMA.cpp) configuration
    global llama, llama_cpp
    status = None
    llama_cpp = False
    env_file = os.path.join(".env")
    if os.path.exists('./state/.operation'):
        with open('./state/.operation', 'r') as f:
            op_array = f.readline().split(':')
        status = op_array[0].strip() if op_array else None
        if len(op_array) > 1:
            llama_cpp = op_array[1].strip() == 'llama.cpp'
    elif os.path.exists(env_file):
        os.makedirs('./state', exist_ok=True)
        lpv = dotenv.get_key(env_file, 'LLAMA_PATH')
        if lpv:
            llama_cpp = True if os.path.basename(lpv).lower().startswith('llama-server') else False
    llama = "LLaMA.cpp" if llama_cpp else "Ollama"

    # Profile, environment and operation arguments
    # TODO: resolve nested lists - if any
    global open_webui_all_profiles
    llama_host_profiles = ['ollama', 'llama.cpp']
    ollama_docker_profiles = ['cpu', 'gpu-nvidia', 'gpu-amd']
    llamacpp_docker_profiles = ['cpp-cpu', 'cpp-gpu-nvidia', 'cpp-gpu-amd']
    llama_docker_profiles = ollama_docker_profiles + llamacpp_docker_profiles
    n8n_profiles = ['n8n', 'n8n-all']
    n8n_all_profiles = n8n_profiles + ['ai-all']
    open_webui_utils_profiles = ['open-webui-mcpo', 'open-webui-pipe']
    open_webui_profiles = ['open-webui', 'open-webui-all']
    open_webui_all_profiles = open_webui_profiles + n8n_all_profiles
    agent_all_profiles = open_webui_all_profiles + ['opencode']
    server_profiles = ['supabase', 'flowise', 'searxng', 'langfuse', 'neo4j']
    subdomain_profiles = n8n_profiles + open_webui_profiles + server_profiles + \
                         llama_host_profiles
    proxy_profiles = ['caddy', 'nginx']
    profiles = agent_all_profiles + open_webui_utils_profiles + server_profiles + \
               llama_host_profiles + llama_docker_profiles + proxy_profiles
    managemant_operations = ['stop', 'stop-llama', 'start', 'pause', 'unpause']
    data_operations = ['backup-data', 'restore-data']
    installation_operations = ['update', 'install']
    managemant_and_data_operations = managemant_operations + data_operations
    operations = managemant_and_data_operations + installation_operations
    environments = ['private', 'public']
    log_levels = ['OFF', 'CRITICAL', 'ERROR', 'WARNING', 'NOTICE', 'INFO', 'DEBUG']
    parser = argparse.ArgumentParser(
        prog=f'{file}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=textwrap.dedent(f'''\
            usage:
              python PROG [options: help | profile environment operation log]

            options:
              - help:
                python {file} -h, --help                    show this help message and exit

              - profile:
                python {file} -p, --profile <arguments...>  specify {name} functional and LLM modules

              - environment:
                python {file} -e, --environment <argument>  specify the type of deployment network

              - operation:
                python {file} -o, --operation <argument>    perform {name} setup or management operations

              - log:
                python {file} -l, --log <argument>.         enable, disable and specify logging levels

            profile arguments:
              - functional modules:
                open-webui                                  Open WebUI client
                n8n                                         n8n
                opencode                                    OpenCode
                open-webui-mcpo open-webui-pipe             Open WebUI pipelines, tools and functions
                flowise                                     Flowise
                supabase                                    Supabase database
                searxng langfuse neo4j                      management, analytics and monitoring utilities
                caddy                                       Caddy proxy
                nginx                                       Nginx proxy
                open-webui-all                              Open WebUI complete bundle
                n8n-all                                     n8n, Open WebUI and selected utilities bundle
                ai-all                                      full {name} bundle

              - LLM modules:
                cpu gpu-nvidia gpu-amd                      Ollama CPU/GPU options running in Docker
                cpp-cpu cpp-gpu-nvidia cpp-gpu-amd          LLaMA.cpp CPU/GPU options rinning in Docker
                ollama llama.cpp                            llama options running on the {name} Host

            environment arguments:
              private public                                self-hosted network options

            operation arguments:
              update install                                installation options
              stop stop-llama start pause unpause           operation options
              backup-data restore-data                      volume mount data options

            log arguments:
              OFF CRITICAL ERROR WARNING NOTICE INFO DEBUG  console logging options
            '''),
        description=textwrap.dedent(f'''\
            {INFO.get("description")}

            With {file}, you can install, start, stop, pause, update or install
            {name} with specified profile arguments (functional modules) and environment.
            ___________________________

            Command syntax:

            python {file} [--profile <arguments...>] [--environment <argument>] [--operation <argument>] [--log <argument>]

            Example commands:

            - Install functional modules n8n and opencode...
              ...with {llama} running on the Host:
              python {file} --profile n8n opencode

              ...with Ollama CPU running in Docker:
              python {file} --profile n8n opencode cpu

              ...with LLaMA.cpp AMD GPU in Docker and on production environment:
              python {file} --profile n8n opencode cpp-gpu-amd --environment public

            - Perform (stop, start, pause, unpause) operation...
              ...to stop n8n and opencode:
              python {file} --profile n8n opencode --operation stop

              ...to stop n8n, opencode and {llama} running on the Host:
              python {file} --profile n8n opencode --operation stop-llama

            - Perform (install, update) operation...
              ...to update all modules and restart using Ollama running on the Host:
              python {file} --operation update

              ...to update all modules and restart using Ollama CPU running in Docker:
              python {file} --profile ai-all cpu --operation update

              ...to install all modules and start using Ollama running on the Host:
              python {file} --operation install

              ...to install all modules and start using LLaMA.cpp Nvidia GPU running in Docker:
              python {file} --profile ai-all cpp-gpu-nvidia --operation install

              ...with debug logging enabled:
              python {file} --profile ai-all cpp-gpu-nvidia --operation install --log debug

            - Perform (backup-data, restore-data) operation...
              ...to backup volume mount data to backup file:
              python {file} --operation backup-data
            '''),
        epilog=textwrap.dedent(f'''\
            - Title: {INFO.get("title")}
            - File: {INFO.get("file")}
            - Author: {INFO.get("author")}
            - Author URL: {INFO.get("author_url")}
            - Repository: {INFO.get("repository")}
            - Report Issues: {INFO.get("issues")}
            - License: {INFO.get("license")}
            - Copyright: {INFO.get("copyright")}
            '''))
    parser.add_argument('-p', '--profile', type=str.lower, nargs='+', choices=profiles,
                        help='Docker Compose Profile arguments for functional modules and llama'
                             f'CPU/GPU options (default: open-webui - with {llama} running on Host)')
    parser.add_argument('-e', '--environment', type=str.lower, choices=environments, default='private',
                        help='Environment arguments used by Docker Compose to expose '
                             'or restrict network communication ports (default: private)')
    parser.add_argument('-o', '--operation', type=str.lower, choices=operations,
                        help='Docker container, volumes and image management arguments along '
                              f'with argument to stop {llama} running on Host.')
    parser.add_argument('-l', '--log', type=str.upper, choices=log_levels, default='INFO',
                        help='Enable stream (console) logging and set log level. File logging is always '
                             'enabled at DEBUG and is not affected by this argument (default: INFO)')

    args = parser.parse_args()

    # Detect default profile - no arguments specified
    default_profile = False if args.profile else True
    args.profile = [] if default_profile else args.profile

    # Setup logging
    global log, log_bright, log_run_cmd
    log_bright = None
    log_run_cmd = "Running command:"
    log_level = logging.NOTSET
    log_handlers: list[logging.Handler] = [LFH]
    if args.log != 'OFF':
        log_level = getattr(logging, args.log, log_level)
        LSH.setLevel(log_level)
        log_handlers.extend([LSH])
        log_bright = LSHF.style(logging.INFO, bright=True)
        if args.operation == 'install':
            open(f'{name.lower()}.log', 'w').close() if \
            os.path.exists(f'{name.lower()}.log') else None
    logging.basicConfig(handlers=log_handlers, level=log_level)
    log = logging.getLogger(name)

    # Name and version banner
    version = INFO.get('version', (-1, -1, -1))
    banner = f"""{name} version: {'.'.join(map(str, version))} LLM: {llama}"""
    print(banner) if args.log == 'OFF' else None
    log.info("="*60, extra=LSHF.style(color=LSHF.BLUE))
    log.info(banner, extra=log_bright)
    raw_msg = " ".join(["Command:", " ".join(sys.argv)])
    log.info(raw_msg, extra=LSHF.style(header="Command:", msg=" ".join(sys.argv)))
    log.info("="*60, extra=LSHF.style(color=LSHF.BLUE))

    # Detect platform
    global system
    system = platform.system()
    if system == "Windows":
        log.info("Detected Windows platform...")
    elif system == "Darwin":  # macOS
        log.info("Detected macOS platform...")
    else:  # Linux and other Unix-like systems
        log.info("Detected Linux/Unix platform...")

    # Check prerequisites
    missing_tools = check_prerequisites()
    prompt_store = {'p':True} # Set False to bypass auto-configure prompts when debugging etc...
    sudo_password = None
    install_tools = False
    if prompt_store['p']:
        if missing_tools:
            msg = f"Install missing tools? y/n: (n)"
            install_tools = True if input(msg).strip().lower() == "y" else False
        # AC_SUDO_PASSWORD - stdin
        if not is_root_user():
            msg = "Enter sudo password for elevated tasks or skip for prompt: "
            sudo_password = getpass.getpass(msg)

    # Install missing tools
    if install_tools:
        log.info("Installing required tools before continuing...")
        if 'Docker' in missing_tools:
            if not retry(lambda: install_package('docker'), desc=f"Docker install"):
                log.info(f"Installing Docker...")
                fail(f"Docker installation failed")
            else:
                missing_tools.remove('Docker')
        for tool in missing_tools:
            log.info(f"Installing {tool}...")
            if not retry(lambda: install_package(tool.lower()), desc=f"{tool} install"):
                fail(f"{tool} installation failed")
    elif missing_tools:
        log.critical("Install required tools before continuing...")
        sys.exit(1)

    # Load working environment variables
    mod_env_vars = {}
    ac_auto_config = \
        any(p for p in args.profile if p not in managemant_and_data_operations)
    env_vars = get_dotenv_vars(auto_config=ac_auto_config, profile=args.profile)
    if not env_vars:
         log.critical("No environment variables detected")
         sys.exit(1)

    # Setup Supabase repository if using Supabase
    if any(p for p in args.profile if p == 'supabase'):
        if not any(p for p in args.profile if p in n8n_all_profiles):
            log.warning("Profile argument 'supabase' requires argument in "
                       f"{n8n_all_profiles} - removing 'supabase'...")
            args.profile.remove('supabase')
    supabase = \
        any(p for p in args.profile if p in ['supabase', 'ai-all'])
    if supabase:
        args.profile.remove('supabase') if 'supabase' in args.profile else None
        mod_env_vars.update({'POSTGRES_HOST': 'db'})
        clone_supabase_repo()
        convert_supabase_pooler_line_endings()

    # Automatic configuration
    ac_env_vars = []
    if ac_auto_config:
        accepted = True
        rejected = False
        response = None
        replay = False
        attempt = 1
        max_attempts = 3
        ac_env_vars = setup_ai_suite_ac_auto_config(prompt_store, env_vars)
        if ac_env_vars:
            display_ac_env_vars(ac_env_vars)
        if prompt_store['p']:
            msg = f"Are these auto-configure settings ok to continue? y/n: (y)"
            response = input(msg).strip().lower() or "y"
        accepted = True if response and response == 'y' else accepted if not response else False
        if not accepted:
            info_style = LSHF.style(logging.INFO, LSHF.YELLOW)
            while attempt < max_attempts:
                msg = f"Would you like to replay the selection? y/n: (n)"
                if prompt_store['p']:
                    replay = input(msg).strip() or "n"
                if replay == 'y':
                    accepted = True
                    response = None
                    ac_env_vars = setup_ai_suite_ac_auto_config(prompt_store, env_vars)
                    if ac_env_vars:
                        display_ac_env_vars(ac_env_vars)
                    if prompt_store['p']:
                        msg = f"Are these auto-configure settings ok to continue? y/n: (y)"
                        response = input(msg).strip().lower() or "y"
                    accepted = True if response and response == 'y' else accepted if not response else False
                    if accepted == 'y':
                        break
                else:
                    rejected = True
                    break
                attempt += 1
                if attempt == max_attempts:
                    log.info("Maximum selection attempts reached! ", extra=info_style)
                    rejected = True
            if rejected:
                msg = f"Auto-configure proxy and access settings was not accepted."
                log.info(msg, extra=info_style)
                ac_env_vars = []
        ac_auto_config = True if ac_env_vars else False
    if ac_auto_config:
        log.info("Configure proxy, identity and access management...")
        if sudo_password:
            ac_env_vars.append('AC_USE_SUDO=1')
        else:
            log.notice(f"The sudo password prompt will trigger on first elevated task.") # type:ignore[reportAttributeAccessIssue]
        # Add docker-compose proxy profiles
        proxy_set = False
        authelia_set = False
        for element in ac_env_vars:
            if element.startswith('AC_PROXY='):
                array = element.split('=')
                if array[1]:
                    args.profile.append(array[1]) if array[1] not in args.profile else None
                    proxy_set = True
                for proxy in proxy_profiles:
                    if any(p for p in args.profile if p == proxy):
                        if proxy != array[1]:
                            args.profile.remove(proxy)
            if element.startswith('AC_WITH_AUTHELIA='):
                array = element.split('=')
                if array[1] and str(array[1]).rstrip("\r\n") == "true":
                    args.profile.append("authelia") if "authelia" not in args.profile else None
                    authelia_set = True
            if proxy_set and authelia_set:
                break
        # Selected subdomains from docker container names
        ac_subdomains = []
        default = any(p for p in args.profile if p == 'ai-all')
        if not default:
            for profile in subdomain_profiles:
                if any(p for p in args.profile if p == profile):
                    if profile.endswith('-all'):
                        profile.replace('-all', '')
                    ac_subdomains.append(profile)
        if ac_subdomains:
            ac_env_vars.append(f'AC_SUBDOMAINS="{" ".join(ac_subdomains)}"')
        # Miscalleanous environment variables
        ac_env_vars.append(f'AC_LLAMA={str(False).lower()}')
        ac_env_vars.append(f'AC_LLAMACPP={str(llama_cpp).lower()}')
        ac_env_vars.append(f'AC_SEARXNG={str(False).lower()}')
        ac_env_vars.append(f'APP_NAME={name}')
        # Debug configuration
        if log_level == logging.DEBUG:
            ac_env_vars.append(f'DEBUG_ON={str(True).lower()}')
            os.makedirs('./access', exist_ok=True)
            with open('access/.ac.env', 'w', newline='\n') as f:
                for var in ac_env_vars:
                    pair = var.split('=')
                    key = str(pair[0]).strip()
                    val = str(pair[1]).rstrip("\r\n")
                    is_bool = True if (val == "true" or val == "false") else False
                    val = val.replace('"', '')
                    val = f'{val}\n' if is_bool else f'"{val}"\n'
                    f.write(f'{key}={val}')
                if sudo_password:
                    f.write('AC_USE_SUDO=1')
        run_ai_suite_ac_auto_config(sudo_password, ac_env_vars)
        env_vars = get_dotenv_vars(auto_config=ac_auto_config, profile=args.profile)
        if not env_vars:
            log.critical("No environment variables detected")
            sys.exit(1)
    # TEMP: End here if working on auto-config and no breakpoints set...
    # if ac_auto_config:
        # log.debug("TEMP: Finished!")
        # sys.exit(0)
    # TEMP: block end

    # Process llama (Ollama/LLaMA.cpp) status checks
    llama_arg = "cpu"
    conflicting_profile_arguments = []
    global llama_on_host
    llama_on_host = default_profile or not \
        any(p for p in args.profile if p in llama_docker_profiles)
    llama_host_env = "LLAMA_ARG_HOST" if llama_cpp else "OLLAMA_HOST"
    if llama_on_host:
        global llama_found, llama_app, llama_exe, attempted_launch
        attempted_launch = False
        llama_found = False
        llama_path = normalize_path(env_vars.get('LLAMA_PATH'))
        if any(p for p in args.profile if p == 'llama.cpp'):
            llama_cpp = True
        llama = "LLaMA.cpp" if llama_cpp else "Ollama"
        if llama_path:
            llama_exe = os.path.normpath(llama_path)
            llama_app = os.path.basename(llama_exe)
            llama_found = os.path.exists(llama_exe)
        if not llama_found:
            llama_app = "llama-server" if llama_cpp else "ollama"
            if system == "Windows":
                llama_app = "".join([llama_app, '.exe'])
                llama_dir = os.path.join("llama.cpp", "bin") if llama_cpp else "Ollama"
                for llama_sub in ['~\\AppData\\Local\\Programs', os.getcwd()]:
                    llama_exe = normalize_path(os.path.join(llama_sub, llama_dir, llama_app))
                    if os.path.exists(llama_exe):
                        llama_found = True
                        break
            else: # Unix-based systems (Linux, macOS)
                for llama_path in ['/bin', '/usr/local/bin', '/usr/bin']:
                    llama_exe = os.path.join(llama_path, llama_app)
                    if os.path.exists(llama_exe):
                        llama_found = True
                        break
            mod_env_vars.update({'LLAMA_PATH': llama_exe})
        # Check if llama exe (llama-server, ollama) matches profile argument (llama.cpp, ollama)
        if (llama_cpp and not llama_app.lower().startswith('llama-server')) or \
           (not llama_cpp and not llama_app.lower().startswith('ollama')):
            llama_cpp = llama_app.lower().startswith('llama-server')
            llama = "LLaMA.cpp" if llama_cpp else "Ollama"
            llama_mismatch = "ollama" if llama_cpp else "llama.cpp"
            log.warning(f"The executable '{llama_app}' did not match the '{llama}' "
                        f"profile argument - argument updated to '{llama.lower()}'...")
            args.profile.remove(llama_mismatch) if llama_mismatch in args.profile else None
            args.profile.extend([llama.lower()]) if llama_cpp else None
         # Check if any llama CPU/GPU profile arguments specified and remove if found
        for profile_arg in llama_docker_profiles:
            if any(p for p in args.profile if p == profile_arg):
                conflicting_profile_arguments.append(profile_arg)
        if len(conflicting_profile_arguments):
            log.warning(f"Profile arguments for {llama} CPU/GPU in Docker and {llama} "
                         "running on host cannot be specified together...")
            for profile_arg in conflicting_profile_arguments:
                log.warning(f"Removing '{profile_arg}'...")
                args.profile.remove(profile_arg)
        llama_host = "host.docker.internal"
        llama_host_var = llama_host if llama_cpp else llama_host + ":${OLLAMA_PORT}"
        mod_env_vars.update({llama_host_env: llama_host_var})
        # Load llama environment variables when running llama on host
        log.debug(f"Loading {llama} environment variables....")
        llama_env_prefix = "LLAMA_ARG_" if llama_cpp else "OLLAMA_"
        for env, var in env_vars.items():
            if not var or not env.startswith(llama_env_prefix):
                continue
            log.debug(f" - {env}: {var}", extra=LSHF.style(logging.WARNING))
            os.environ[env] = var
        check_llama = not args.operation in data_operations
        if check_llama:
            check_llama_process(args.operation, env_vars)
    else:
        llama_cpp = any(p for p in args.profile if p in llamacpp_docker_profiles)
        llama = "LLaMA.cpp" if llama_cpp else "Ollama"
        llama_host_var = "0.0.0.0" if llama_cpp else "ollama:${OLLAMA_PORT}"
        mod_env_vars.update({llama_host_env: llama_host_var, 'LLAMA_PATH': None})
        # Check if more than one llama CPU/GPU argument specified, use first argument
        if any(p for p in args.profile if p in llama_docker_profiles):
            first_argument = False
            for profile_arg in llama_docker_profiles:
                if not first_argument:
                    if any(p for p in args.profile if p == profile_arg):
                        log.info(f"{name} will use {llama} profile argument '{profile_arg}'...")
                        first_argument = True
                else:
                    args.profile.remove(profile_arg)
        # Check if any llama host profile arguments specified and remove if found
        for profile_arg in llama_host_profiles:
            if any(p for p in args.profile if p == profile_arg):
                conflicting_profile_arguments.append(profile_arg)
        if len(conflicting_profile_arguments):
            log.warning(f"Profile arguments for {llama} running on host and {llama} "
                        "CPU/GPU in Docker cannot be specified together...")
            for profile_arg in conflicting_profile_arguments:
                log.warning(f"Removing '{profile_arg}'...")
                args.profile.remove(profile_arg)

    # Assemble .env updates, set respective keys in .env file and reload .env vars
    oai_base_url_var = "${LLAMACPP_HOST}" if llama_cpp else "${OLLAMA_HOST}"
    mod_env_vars.update({'OPENAI_API_BASE_URL': oai_base_url_var})
    for env, var in mod_env_vars.items():
        set_dotenv_var(env_file, env, var, None)
    env_vars = get_dotenv_vars(env_file, True)
    # Check .env interpolation
    debug_style = LSHF.style(logging.WARNING)
    log.debug("DotEnv dictionary updates:")
    log.debug(f" - PROJECTS_PATH: {env_vars['PROJECTS_PATH']}", extra=debug_style)
    log.debug("DotEnv file updates:")
    for env in [llama_host_env, 'OPENAI_API_BASE_URL']:
        log.debug(f" - {env}: {env_vars[env]}", extra=debug_style)
    valid_llama_path = env_vars.get('LLAMA_PATH')
    if valid_llama_path and valid_llama_path.strip():
        log.debug(f" - LLAMA_PATH: {env_vars['LLAMA_PATH']}", extra=debug_style)
    if llama_cpp:
        log.debug(f"DotEnv {llama} file updates:")
        for env in ['LLAMACPP_DEFAULT_MODEL', 'LLAMACPP_MODEL_PATH', 'LLAMA_ARG_HF_REPO']:
            log.debug(f" - {env}: {env_vars[env]}", extra=debug_style)

    # Process operation argument
    install = False
    build = False
    if args.operation:
        if args.operation == 'stop-llama':
            args.operation = "stop"
        if args.operation == status:
            if status == 'stop':
                insert = "Stopped"
            else:
                insert = "Paused" if status == 'pause' else "Started"
            log.info(f"{name} is already {insert} - exiting...")
            sys.exit(0)
        elif args.operation == 'unpause' and not status == 'pause':
            log.info(f"{name} cannot unpause as it is not paused - exiting...")
            sys.exit(0)
        elif args.operation in ['backup-data', 'restore-data']:
            docker_volume_data(args.operation)
            sys.exit(0)
        if default_profile:
            args.profile = ['ai-all']
        build = args.operation in ['update', 'install']
        if build:
            install = args.operation == 'install'
            if args.operation == 'update':
                user_confirm = input(textwrap.dedent(f"""\
                    Performing an {name} update can impact its integrity.
                    Consider backing up your data to enable rollback.
                    [Type 'Got-It' to continue]: """))
                if len(user_confirm) == 0 or user_confirm.lower() != 'got-it':
                    log.info(f"Received [{user_confirm}].") if user_confirm else None
                    log.info(f"{name} update was not confirmed - exiting...",
                             extra=LSHF.style(logging.INFO, 34, bold=True))
                    sys.exit(0)
            args.operation = 'pull'
            insert = "Installing" if install == 'install' else "Updating"
            if default_profile:
                log.info(f"{insert} all container images including {llama}...")
                llama_arg = "cpp-cpu" if llama_cpp else "cpu"
                args.profile.extend([llama_arg])
            else:
                log.info(f"""{insert} container images for {args.profile}...""")
            docker_compose_include(True, True, False)
            destroy_ai_suite(args.profile, install)
        operate_ai_suite(args.operation, args.profile, args.environment, env_vars)
        if build:
            insert = "Installing" if install else "Updating"
            log.info(f"{insert} '{name}' with profile arguments: {args.profile}...")
        else:
            sys.exit(0)
    else:
        log.notice(f"Updating '{name}' with profile arguments: {args.profile}...") # type:ignore[reportAttributeAccessIssue]

    os.remove('./state/.operation') if os.path.exists('./state/.operation') else None

    # Manually set default profile argument
    if default_profile:
        if build:
            args.profile.remove(llama_arg) if llama_arg in args.profile else None
        else:
            args.profile = ['open-webui']

    # Configure n8n Postgres database
    if any(p for p in args.profile if p in n8n_all_profiles):
        configure_n8n_database_settings(supabase)

    # Set Supabase supabase/docker/.env from .env
    if supabase:
        prepare_supabase_env(env_vars)
    elif 'langfuse' in args.profile:
        log.warning("Profile argument 'langfuse' requires Supabase - "
                    "removing 'langfuse'...'")
        args.profile.remove('langfuse')

    # Generate SearXNG secret key and check docker-compose.yml
    if any(p for p in args.profile if p in ['searxng', 'ai-all']):
        generate_searxng_secret_key()
        check_and_fix_docker_compose_for_searxng()

    # Setup Open WebUI Functions and Tools Filesystem repos
    open_webui = \
        any(p for p in args.profile if p in open_webui_all_profiles)
    if open_webui:
        clone_open_webui_functions_repos()
        clone_open_webui_tools_filesystem_repo()
        prepare_open_webui_tools_filesystem_env(env_vars)

    # Setup OpenCode default model in opencode.jsonc
    opencode = \
        any(p for p in args.profile if p in ['opencode', 'ai-all'])
    if opencode:
        prepare_opencode_config(env_vars)

    # Add or remove Supabase and Filesystem include compose.yml in docker-compose.yml
    docker_compose_include(supabase, open_webui, True)

    # Stop and remove AI-Suite containers
    if not build:
        destroy_ai_suite(args.profile, False)

    # Load environment variables
    load_dotenv_vars(env_vars)

    # Start Supabase first
    if supabase:
        start_supabase(args.environment, build)
        # Give Supabase some time to initialize
        log.info("Waiting for Supabase to initialize...", extra=log_bright)
        wait_with_progress(10)

    # Start Open WebUI Tools Filesystem
    if open_webui:
        start_open_webui_tools_filesystem(args.environment, build)
        log.info("Waiting for Open WebUI Tool Filesystem to initialize...",
                 extra=log_bright)
        wait_with_progress(2)

    # Unset Compose ignore orphans variable
    env = "COMPOSE_IGNORE_ORPHANS"
    if env in os.environ:
        del os.environ[env]

    # Check if open-webui-mcpo specified with required profile arguments, else remove open-webui-mcpo
    if any(p for p in args.profile if p == 'open-webui-mcpo'):
        if not any(p for p in args.profile if p in open_webui_all_profiles):
            log.warning("Profile argument 'open-webui-mcpo' requires argument in "
                       f"{open_webui_all_profiles} - removing 'open-webui-mcpo'...")
            args.profile.remove('open-webui-mcpo')

    # Check if open-webui-pipe specified with required profile arguments, else remove open-webui-pipe
    if any(p for p in args.profile if p == 'open-webui-pipe'):
        if not any(p for p in args.profile if p in open_webui_all_profiles):
            log.warning("Profile argument 'open-webui-pipe' requires argument in "
                       f"{open_webui_all_profiles} - removing 'open-webui-pipe'...")
            args.profile.remove('open-webui-pipe')

    # Check if profile arguments n8n and open-webui specified, remove redundant open-webui
    if any(p for p in args.profile if p == 'n8n'):
        if any(p for p in args.profile if p == 'open-webui'):
            log.info("Profile arguments 'n8n' and 'open-webui' detected "
                     "- removing 'open-webui'...")
            args.profile.remove('open-webui')

    # Check if more than one llama CPU/GPU argument specified, use first argument
    if any(p for p in args.profile if p in llama_docker_profiles):
        first_argument = False
        for profile_arg in llama_docker_profiles:
            if not first_argument:
                if any(p for p in args.profile if p == profile_arg):
                    log.info(f"{name} will use {llama} profile argument '{profile_arg}'...")
                    first_argument = True
            else:
                args.profile.remove(profile_arg) if profile_arg in args.profile else None

    # Then start the AI-Suite services
    start_ai_suite(args.profile, args.environment, build)
    display_service_endpoints(args.profile, supabase, env_vars)

    with open('./state/.operation', 'w', newline='\n') as f:
        f.write('start' + ':' + llama.lower())

if __name__ == "__main__":
    main()
