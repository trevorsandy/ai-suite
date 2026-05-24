#!/usr/bin/env python3
"""
Trevor SANDY
Last Update May 24, 2026
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

By default, _auto-configure_ will generate secrets, the .env file and  Docker
compose file updates for AI-Suite modules, including Supabase and OpenClaw.
Additionally,  AI-Suite will automatically configure Caddy (Default) or Nginx
HTTPS reverse proxy and Authelia 2FA (Two Factor Authentication) IAM (Identity and
Access Management) on install or update.

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
import ast
import datetime
import dotenv
import getpass
import gzip
import json
import logging
import pathlib
import platform
import queue
import re
import requests
import secrets
import shlex
import shutil
import subprocess
import tarfile
import textwrap
import threading
import time
import urllib.error
import urllib.request
import zipfile


# ---- Info attributes ----
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
# - Minimum Docker Version -
MIN_DOCKER_VERSION = (20, 10, 0)
# - Minimum Python Version -
MIN_PY_VERSION = (3, 10, 14)
# ---- Offline fallback ----
_PY_FALLBACK_RELEASES = {
    (3, 14, 3): "17.2.20260307final",
    (3, 12, 6): "16.8.20240101final",
    (3, 11, 9): "16.6.20231210final",
}
# ---- In-memory cache ----
_PY_RELEASE_CACHE = {}

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


def run_command(cmd, cwd=None, re_raise=None):
    """Run a shell command and print it."""
    raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True
        )
        # if result.returncode != 0:
            # log.error(f"Command return code: {result.returncode}")
    except Exception as e:
        log.error(f"Exception: {e}.")
        if re_raise:
            raise

def run_pkg_command(cmd):
    """Run a package shell command and print it."""
    raw_msg = " ".join([log_run_cmd, " ".join(cmd)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd)))
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            shell=(system == "Windows")
        )
        if result.stderr:
            if result.returncode == 0:
                log.warning(f"{result.stderr.strip()}")
            else:
                log.error(f"{result.stderr.strip()}")
        stdout = result.stdout.strip() if result.stdout else ''
        log.info(stdout)
        return result.returncode == 0, stdout
    except subprocess.CalledProcessError as e:
        if e.stderr:
            log.error(f"Exception: Command error: {e.stderr.strip()}")
        stdout = e.stdout.strip() if e.stdout else ''
        return False, stdout

def run_unix_command(cmd):
    """."""
    cmd = unix_prefix() + cmd
    privilege = unix_privilege()
    if privilege == "is_unix__root":
        return run_pkg_command(cmd)
    elif privilege == "has_sudo__pass_set":
        full_cmd = ["sudo"] + unix_prefix() + cmd
        return run_pkg_command(full_cmd)
    elif privilege == "has_sudo__needs_pass":
        full_cmd = ["sudo"] + unix_prefix() + cmd
        return run_pkg_command(full_cmd)
    elif privilege == "has_su__needs_pass":
        return run_pkg_command(["su", "-c"] + unix_prefix() + cmd)
    else:
        fail("No privilege escalation available.")
    return False, ""

def fail(msg):
    """."""
    log.error(f"{msg}")
    raise RuntimeError(msg)

def exists(cmd):
    """."""
    found = shutil.which(cmd) is not None
    log.info(f"Check exists '{cmd}': {found}")
    return found

def elide(string: str, length=30):
    if length <= 3:
        return "." * length
    if len(string) <= length:
        return string
    return string[:length - 3] + "..."

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
    """Return True if default WSL version is 2."""
    try:
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            check=True
        )

        bytes = result.stdout
        codex = "utf-16le" if b"\x00" in bytes else "utf-8"
        output = bytes.decode(codex)
        for line in output.splitlines():
            clean = line.strip().lower()
            if clean.startswith("default version:"):
                if clean.endswith("2"):
                    return True
                elif clean.endswith("1"):
                    fail("WSL1 not supported. Use: wsl --set-version <distro> 2")
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

def to_wsl_path(path: pathlib.Path) -> str:
    path_str = path.resolve().as_posix()
    if path.drive:
        drive = path.drive[0].lower()
        return f"/mnt/{drive}{path_str[2:]}"
    return path_str

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
        try:
            subprocess.run(
                cmd,
                input=pwd + "\n",
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log.error(f"Exception: {e}")

def unix_privilege():
    """."""
    if is_root_user():
        return "is_unix__root"
    if shutil.which("sudo"):
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return "has_sudo__pass_set"
            else:
                return "has_sudo__needs_pass"
        except Exception as e:
            log.error(f"Exception: {e}")
    elif shutil.which("su"):
        return "has_su__needs_pass"
    return "none"

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
                return run_pkg_command(["winget", "install", "-e", "--id", "Docker.DockerDesktop"])[0]
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
        if is_root_user():
            fail(f"You cannot install {package} as root on macOS")
        cmd = []
        cmd.extend(["brew", "install"])
        if package == 'docker':
            cmd.extend(["--cask"])
        cmd.extend([package])
        return run_pkg_command(cmd)[0]

    if system == "Linux" or is_wsl2():
        if exists("apt-get"):
            apt_pkg = "docker.io" if package == 'docker' else package
            return run_unix_command(["DEBIAN_FRONTEND=noninteractive echo $DEBIAN_FRONTEND"])[0] and \
            run_unix_command(["apt-get", "update"])[0] and \
            run_unix_command(["apt-get", "install", "-y", apt_pkg])[0]
        elif exists("apk"):
            return run_unix_command(["apk", "update"])[0] and \
            run_unix_command(["apk", "add", "--no-cache", package])[0]
        elif exists("dnf"):
            return run_unix_command(["dnf", "makecache"])[0] and \
            run_unix_command(["dnf", "install", "-y", package])[0]
        elif exists("zypper"):
            return run_unix_command(["zypper", "refresh"])[0] and \
            run_unix_command(["zypper", "install", package])[0]
        elif exists("pacman"):
            return run_unix_command(["pacman", "-Syu", "--noconfirm", package])[0]
        elif exists("pkg"):
            return run_unix_command(["pkg", "update"])[0] and \
            run_unix_command(["pkg", "install", "-y", package])[0]
        else:
            fail("Install package failed! Package manager not found.")
    return False

def check_prerequisites():
    """Check if required tools are installed and return missing tools"""
    required_tools = ['Python', 'Docker', 'Git']
    missing_tools = []
    for tool in required_tools:
        if shutil.which(tool.lower()) is None:
            missing_tools.append(tool)
        elif tool == 'Python':
            sys_ver = sys.version_info[:3]
            versions = (sys_ver,)
            venv_ver = python_venv_version()
            if venv_ver:
                versions = (*versions, venv_ver)
            if all(v < MIN_PY_VERSION for v in versions):
                m = f"{MIN_PY_VERSION}"
                c = venv_ver if venv_ver and venv_ver > sys_ver else sys_ver
                log.warning(f"Python version {c} is less than the minimum required version {m}.")
                missing_tools.append(tool)
    if missing_tools:
        log.warning("Missing required tools: [{}].".format(", ".join(missing_tools)))
        return missing_tools
    try:
        docker_start()
    except Exception as e:
        log.critical(f"Exception: Start Docker Desktop: {e}")
    return missing_tools

def detect_arch():
    """
    Detect and normalize architecture for target platform.
    Returns:
        str: architecture string matching upstream naming
    """
    machine = platform.machine().lower()
    log.debug(f"Detected machine architecture: {machine} (system={system})")
    # ---- Normalize ----
    norm = None
    if machine in ("amd64", "x86_64", "x64"):
        norm = "x86_64"
    elif machine in ("arm64", "aarch64"):
        norm = "arm64"
    else:
        fail(f"Unsupported architecture: {machine}")
    # ---- Map ----
    if system == "Windows":
        if norm == "x86_64":
            return "64"
        elif norm == "arm64":
            return "arm64"
    else:
        # python-build-standalone naming
        if norm == "x86_64":
            return "x86_64"
        elif norm == "arm64":
            return "aarch64"
    fail(f"Unsupported architecture mapping: {norm} for system {system}")

def http_download(url, destination, timeout=30, retries=3, backoff=1.5):
    """
    Download a file with retry, redirect handling, and fallback tools.
    """
    last_error = None
    for attempt in range(retries):
        try:
            log.info(f"Downloading {url} -> {destination} (attempt {attempt + 1}/{retries})")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PythonDownloader"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response, \
                 open(destination, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
            log.info("Download completed successfully")
            return
        except Exception as e:
            last_error = e
            log.warning(f"Download failed: {e}")
            if attempt < retries - 1:
                sleep_time = backoff ** attempt
                log.debug(f"Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
    # ---- Fallback tools (curl / wget) ----
    log.warning("urllib download failed, attempting fallback tools...")
    try:
        subprocess.run(["curl", "-L", "-o", destination, url], check=True)
        log.info("Download succeeded via curl")
        return
    except Exception as e:
        log.warning(f"curl failed: {e}")
    try:
        subprocess.run(["wget", "-O", destination, url], check=True)
        log.info("Download succeeded via wget")
        return
    except Exception as e:
        log.warning(f"wget failed: {e}")
    fail(f"Download failed after retries and fallbacks: {last_error}")

def http_get_json(url, timeout=10, retries=3, backoff=1.5):
    """
    Robust HTTP GET with retry + exponential backoff.
    """
    last_error = None
    for attempt in range(retries):
        try:
            log.debug(f"HTTP GET {url} (attempt {attempt + 1}/{retries})")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PythonDownloader"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_error = e
            log.warning(f"HTTP GET failed: {e}")
            if attempt < retries - 1:
                sleep_time = backoff ** attempt
                log.debug(f"Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
    fail(f"HTTP GET failed after {retries} attempts: {last_error}")

def http_head_exists(url, timeout=10, retries=3):
    """
    Validate URL existence using HEAD request.
    Returns True if reachable, False otherwise.
    """
    for attempt in range(retries):
        try:
            log.debug(f"HTTP HEAD {url} (attempt {attempt + 1}/{retries})")
            req = urllib.request.Request(
                url,
                method="HEAD",
                headers={"User-Agent": "PythonDownloader"}
            )
            with urllib.request.urlopen(req, timeout=timeout):
                log.debug("HEAD request succeeded")
                return True
        except Exception as e:
            log.warning(f"HEAD request failed: {e}")
            if attempt < retries - 1:
                time.sleep(1.5 ** attempt)
    return False

def python_ensure_compatible_version():
    """
    Compare the .venv and system-level Python versions against the minimum
    required version. If the currently system-level and venv Python version
    is less than the minimum required version, download Python and setup or
    update the venv.
    """
    current_version = sys.version_info[:3]
    venv_dir = os.path.join(os.getcwd(), ".venv")
    venv_python = _python_get_venv_executable(venv_dir)
    # Check venv Python
    venv_version = python_venv_version(venv_python)
    if venv_version:
        log.info(f"Detected venv Python version: {_python_version_str(venv_version)}")
        if venv_version >= MIN_PY_VERSION:
            if os.path.abspath(sys.executable) == os.path.abspath(venv_python):
                log.info("Already running from compliant venv.")
                return
            else:
                log.info("Using existing compliant venv. Restarting script...", extra=log_bright)
                _python_restart_script(venv_python)
    # Check system Python
    if current_version >= MIN_PY_VERSION:
        log.info(f"System Python {_python_version_str(current_version)} is compliant.")
        return
    # System Python too old → prompt & install local Python
    c = _python_version_str(current_version)
    m = _python_version_str(MIN_PY_VERSION)
    log.info(f"Current Python: {c}, Minimum required Python: {m}", extra=log_bright)
    target_version = _python_prompt_for_version()
    try:
        _python_install_upgrade(target_version)
    except Exception:
        fail(f"Python installation failed for version {_python_version_str(target_version)}")
    log.info("Environment setup complete. Restarting with venv Python.", extra=log_bright)
    _python_restart_script(venv_python)

def python_venv_version(venv_python=None):
    """
    Return the .benv Python version touple.
    """
    if not venv_python:
        venv_dir = os.path.join(os.getcwd(), ".venv")
        venv_python = _python_get_venv_executable(venv_dir)
    if os.path.exists(venv_python):
        return _python_get_version(venv_python)
    return None

def _python_prompt_for_version():
    for attempt in range(3):
        user_input = input(
            f"Enter Python version to install [default {_python_version_str(MIN_PY_VERSION)}]: "
        ).strip()
        if not user_input:
            return MIN_PY_VERSION
        try:
            return tuple(map(int, user_input.split(".")))
        except Exception:
            log.warning(f"Invalid version format (attempt {attempt + 1}/3).")
    fail("Maximum attempts reached. Invalid version input.")

def _python_version_str(v):
    """Return a Python version string."""
    return f"{v[0]}.{v[1]}.{v[2]}"

def _python_get_version(python_executable):
    """Return version from Python executable."""
    try:
        result = subprocess.run(
            [python_executable, "-c", "import sys; print(tuple(sys.version_info[:3]))"],
            capture_output=True,
            text=True,
            check=True
        )
        return ast.literal_eval(result.stdout.strip())
    except Exception as e:
        log.error(f"Failed to get Python version: {e}")
        return None

def _python_install_upgrade(version):
    """Ensure local Python exists, create venv, install requirements, restart.
    """
    local_python = _python_prepare_local(version)
    venv_dir = os.path.join(os.getcwd(), ".venv")
    _python_create_venv(local_python, venv_dir)
    venv_python = _python_get_venv_executable(venv_dir)
    _python_generate_requirements(entry_file=__file__)
    _python_install_requirements(venv_python)

def _python_prepare_local(version):
    local_dir = os.path.join(os.getcwd(), ".python")
    if system == "Windows":
        version_str = f"{version[0]}.{version[1]}.{version[2]}"
        wpy_dir = f"WPy{detect_arch()}-{version_str}.0"
        local_dir = os.path.join(os.getcwd(), ".python", wpy_dir)
    python_exe = (
        os.path.join(local_dir, "bin", "python") if system != "Windows"
        else os.path.join(local_dir, "python", "python.exe")
    )
    if os.path.exists(python_exe) and _python_get_version(python_exe) == version:
        log.info(f"Found existing local Python {_python_version_str(version)} at {python_exe}")
        return python_exe
    if system == "Windows":
        local_dir = os.path.dirname(local_dir)
    if os.path.exists(local_dir):
        shutil.rmtree(local_dir)
    os.makedirs(local_dir, exist_ok=True)
    return _python_download_prebuilt(version, local_dir)

def _python_get_release_tag(version, url_base=None, timeout=10, retries=3):
    """
    Resolve WinPython release tag for a given Python version tuple.
    Resolution order:
        1. Cache
        2. GitHub API
        3. Offline fallback
    """
    if version in _PY_RELEASE_CACHE:
        log.debug(f"Cache hit for version {version}")
        return _PY_RELEASE_CACHE[version]
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    arch = detect_arch()
    expected_name = f"WinPython{arch}-{version_str}.0free.zip"
    log.info(f"Resolving WinPython release for Python {version_str} ({arch})")
    api_base = url_base or "https://api.github.com/repos/winpython/winpython"
    # ---- 1. GitHub API ----
    try:
        page = 1
        while True:
            url = f"{api_base}/releases?per_page=100&page={page}"
            releases = http_get_json(url, timeout=timeout, retries=retries)

            if not releases:
                break
            log.debug(f"Scanning {len(releases)} releases (page {page})")
            for release in releases:
                tag = release.get("tag_name", "")
                for asset in release.get("assets", []):
                    if asset.get("name") == expected_name:
                        log.info(f"Matched release tag: {tag}")
                        _PY_RELEASE_CACHE[version] = tag
                        return tag
            page += 1
    except Exception as e:
        log.warning(f"GitHub API resolution failed: {e}")
    # ---- 2. Offline fallback ----
    if version in _PY_FALLBACK_RELEASES:
        tag = _PY_FALLBACK_RELEASES[version]
        log.warning(f"Using fallback release tag: {tag}")
        _PY_RELEASE_CACHE[version] = tag
        return tag
    fail(f"Could not resolve WinPython release tag for Python {version_str}")

def _python_download_prebuilt(version, target_dir):
    """
    Download and install Python for the given version into target_dir.
    Windows: uses WinPython portable ZIP
    Unix: uses python-build-standalone tar.xz
    Returns path to python executable
    """
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    arch = detect_arch()
    if system == "Windows":
        release_tag = _python_get_release_tag(version)
        zip_name = f"WinPython{arch}-{version_str}.0free.zip"
        url = f"https://github.com/winpython/winpython/releases/download/{release_tag}/{zip_name}"
    else:
        # Unix: python-build-standalone
        zip_name = f"python-{version_str}-{arch}-linux-gnu-install_only.tar.xz"
        url = f"https://github.com/indygreg/python-build-standalone/releases/download/{version_str}/{zip_name}"
    local_archive = os.path.join(target_dir, zip_name)
    if not os.path.exists(local_archive):
        if http_head_exists(url):
           log.info(f"Validated download URL: {url}")
        else:
           fail(f"Download URL not reachable: {url}")
        log.info(f"Downloading Python {version_str}...")
        http_download(url, local_archive)
    # Extract and return python executable path
    python_exe = _python_install_archive(local_archive, target_dir, version)
    log.info(f"Python {version_str} ready at {python_exe}")
    return python_exe

def _python_find_executable(target_dir, version):
    """
    Search target directory recursively for python executable.
    """
    # --- Candidate names ---
    if system == "Windows":
        candidates = ["python.exe"]
    else:
        candidates = [
            "python3",
            f"python{version[0]}.{version[1]}",
            "python",
        ]
    # --- First pass: preferred locations ---
    preferred_dirs = [
        target_dir,
        os.path.join(target_dir, "python"),
        os.path.join(target_dir, "bin"),
        os.path.join(target_dir, "python", "bin"),
    ]
    for d in preferred_dirs:
        if not os.path.isdir(d):
            continue
        for name in candidates:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path
    # --- Fallback: full walk ---
    for root, _, files in os.walk(target_dir):
        for name in candidates:
            if name in files:
                return os.path.join(root, name)
    fail(f"Could not locate Python executable in {target_dir}")

def _python_install_archive(local_archive, target_dir, version):
    """
    Extract ZIP (Windows WinPython) or tar.xz (Unix) and return path to python executable.
    """
    log.info(f"Extracting {local_archive} → {target_dir} ...")
    os.makedirs(target_dir, exist_ok=True)
    if local_archive.endswith(".zip"):
        with zipfile.ZipFile(local_archive, "r") as zip_ref:
            zip_ref.extractall(target_dir)
        # locate python.exe in extracted folder
        return _python_find_executable(target_dir, version)
    elif local_archive.endswith((".tar.gz", ".tar.xz", ".tgz")):
        with tarfile.open(local_archive, "r:*") as tar_ref:
            tar_ref.extractall(target_dir)
        # python-build-standalone layout: python/bin/python3
        return os.path.join(target_dir, "python", "bin", "python3")
    else:
        raise RuntimeError(f"Unknown archive type: {local_archive}")

def _python_create_venv(local_python, venv_path):
    """
    Create a virtual environment using local Python.
    Ensures pip is installed
    """
    if os.path.exists(venv_path):
        log.info(f"Removing existing venv at {venv_path}")
        shutil.rmtree(venv_path)
    log.info(f"Creating venv at {venv_path} ...")
    try:
        subprocess.run([local_python, "-m", "venv", venv_path], check=True)
        if os.path.exists(venv_path):
            log.info(f"Venv created at {venv_path}")
    except Exception as e:
        log.warning(f"Venv creation failed: {e}. Falling back to current Python.")
        return sys.executable
    # Ensure pip
    venv_python = _python_get_venv_executable(venv_path)
    if os.path.exists(venv_python):
        try:
            subprocess.run([venv_python, "-m", "ensurepip", "--upgrade"], check=True)
        except Exception as e:
            log.warning(f"Failed to bootstrap pip in venv: {e}")
        return venv_python
    else:
        log.warning("Venv python not found. Using current Python.")
        return sys.executable

def _python_get_venv_executable(venv_dir):
    """Return the local Python venv executable."""
    binary = None
    if system == 'Windows':
        binary = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        binary = os.path.join(venv_dir, "bin", "python")
    if binary:
        log.info(f"Venv binary: {binary}")
    return binary

def _python_generate_requirements(project_dir=".", output_file=None, entry_file=None):
    """
    Generate a minimal requirements.txt by scanning:
    - Specified file:
    -   auto_config.py contains the entire project
    - Project imports (future use):
    -   Ignores standard library modules
    -   Maps imports to PyPI packages
    -   Handles common mismatches (bs4 → beautifulsoup4, yaml → PyYAML)
    -   Uses only standard library (no pkg_resources, no stdlib-list)
    """
    from importlib import util
    from importlib.metadata import distributions

    # Common import → PyPI package mapping
    IMPORT_TO_PYPI = {
        "bs4": "beautifulsoup4",
        "yaml": "PyYAML",
        "PIL": "Pillow",
        "torch": "torch",
        "tensorflow": "tensorflow",
    }
    # Modules
    imported_modules = set()
    def _scan_file(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".")[0])
        except (SyntaxError, UnicodeDecodeError):
            pass
    if entry_file:
        _scan_file(os.path.abspath(entry_file))
    else:
        EXCLUDE_DIRS = {".python", ".venv", "__pycache__", ".git", "build", "dist"}
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if file.endswith(".py"):
                    _scan_file(os.path.join(root, file))
    def _is_stdlib(module_name):
        try:
            spec = util.find_spec(module_name)
            if spec is None or spec.origin is None:
                return False
            path = spec.origin
            return "site-packages" not in path and "dist-packages" not in path
        except Exception:
            return False
    imported_modules = {m for m in imported_modules if not _is_stdlib(m)}
    dist_map = {}  # module_name -> (package_name, version, location)
    for dist in distributions():
        try:
            name = dist.metadata["Name"]
            version = dist.version
            location = str(dist.locate_file(""))
            # Try to read top-level modules from metadata
            top_level = dist.read_text("top_level.txt")
            if top_level:
                for line in top_level.splitlines():
                    module = line.strip()
                    if module:
                        dist_map[module] = (name, version, location)
            else:
                # fallback: map package name itself
                dist_map[name.lower()] = (name, version, location)
        except Exception:
            continue
    # Requirements
    requirements = set()
    for module in imported_modules:
        mapped = IMPORT_TO_PYPI.get(module, module)
        # Direct mapping via known table
        if mapped and mapped.lower() in dist_map:
            name, version, _ = dist_map[mapped.lower()]
            requirements.add(f"{name}=={version}")
            continue
        # Try to resolve via import location
        try:
            spec = util.find_spec(module)
            if spec and spec.origin:
                for name, version, location in dist_map.values():
                    if location and spec.origin.startswith(location):
                        requirements.add(f"{name}=={version}")
                        break
                else:
                    requirements.add(mapped)
        except Exception:
            requirements.add(mapped)
    requirements = sorted(requirements)
    insert = "packages" if len(requirements) > 1 else "package"
    if not output_file:
        output_file = "requirements.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(requirements))
    if os.path.exists(output_file):
        log.info(f"Generated requirements.txt ({len(requirements)} {insert})", extra=log_bright)

def _python_install_requirements(venv_python):
    """
    Install additional modules from generated requirements.txt.
    """
    if not os.path.exists("requirements.txt"):
        return
    if not os.path.exists(venv_python):
        fail(f"Venv python: {venv_python} not found!")
    log.info("Installing dependencies in venv...")
    subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([venv_python, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

def _python_restart_script(venv_python):
    """
    Restart the script after implementing or updating a local venv.
    """
    script_path = os.path.abspath(sys.argv[0])
    log.info("Restarting script in venv Python...", extra=log_bright)
    os.execv(venv_python, [venv_python, script_path] + sys.argv[1:])

def docker_start():
    """Install Docker and ensure it is running and usable."""
    log.info("Starting Docker bootstrap...", extra=log_bright)
    # --- Version check ---
    if not _docker_valid_version():
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
    ok, out = run_pkg_command(["docker", "compose", "version"])
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

def docker_get_version():
    ok, version = run_pkg_command(["docker", "--version"])
    if not ok:
        return None
    return _docker_parse_version(version)

def _docker_parse_version(version):
    """."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)

def _docker_valid_version():
    """."""
    parsed_version = docker_get_version()
    if parsed_version:
        ok = parsed_version >= MIN_DOCKER_VERSION
        log_style = log_bright if ok else LSHF.style(color=LSHF.YELLOW)
        log.info(f"{parsed_version}", extra=(log_style))
        return ok
    return False

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
        return run_unix_command(["systemctl", "start", "docker"])[0]
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
    ok, _ = run_pkg_command(["docker", "info"])
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
    ok, _ = run_pkg_command(["docker", "system", "info"])
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
    ok, out = run_pkg_command(["docker", "run", "--rm", "hello-world"])
    if ok and "Hello from Docker!" in out:
        log.info(out, extra=log_bright)
        return True
    return False

def launch_llama_process(args, env=None, llama_log=None):
    """Launch Ollama/LLaMA.cpp server on the host"""
    llama_log = "llama_start.log" if not llama_log else llama_log
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
        completed = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            text=True,
            check=True
        )
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

def check_llama_process(operation=None, env_vars=None):
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
            if not env_vars:
                log.critical("The env_vars dictionary is empty - exiting...")
                sys.exit(1)
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
                llama_host = "localhost"
                llama_port = env_vars.get('OLLAMA_PORT')
                llama_host_var = llama_host if llama_cpp else f"{llama_host}:{llama_port}"
                llama_host_env = "LLAMA_ARG_HOST" if llama_cpp else "OLLAMA_HOST"
                log.info(f"Set '{llama_host_env}' to '{llama_host_var}' in subprocess env...")
                env = os.environ.copy()
                env[llama_host_env] = llama_host_var
                args = " ".join(llama_args)
                launch_llama_process(args, env, llama_log_file)
            else:
                log.critical(f"The {llama_app} file was not found at {llama_exe}.")
                log.critical(f"If {llama} is installed in a non-standard location, set the LLAMA_PATH")
                log.critical(f"environment variable with its full path (including the {llama} file)")
                log.critical(f"in the .env file and re-run {file} - exiting...")
                sys.exit(1)

def git(*args, cwd=None, capture_output=False):
    """
    Run a git command.
    If capture_output=True, return decoded stdout.
    """
    if capture_output:
        return subprocess.check_output(
            ["git", "-c", "core.autocrlf=input", *args],
            cwd=cwd,
            stderr=subprocess.STDOUT
        ).decode().strip()
    run_command(["git", "-c", "core.autocrlf=input", *args], cwd=cwd)

def is_stable_tag(tag):
    return not re.search(r"(alpha|beta|rc)", tag, re.IGNORECASE)

def get_latest_tag(repo_path, oc_release=None):
    """
    Return the latest stable version tag sorted by semantic version.
    Behaviour:
      - If oc_release["release"] is None or "", return latest stable tag.
      - If oc_release["release"] == "commit", return None.
      - Otherwise validate and return the requested stable tag.
    """
    release = None if oc_release is None else oc_release["release"]
    if release == "commit":
        return None
    output = git("tag", "--sort=-v:refname", cwd=repo_path, capture_output=True)
    if output is None:
        raise RuntimeError("Failed to retrieve git tags")
    tags = [t for t in output.splitlines() if t]
    if not tags:
        raise RuntimeError("No tags found in repository")
    stable_tags = [t for t in tags if is_stable_tag(t)]
    if not stable_tags:
        raise RuntimeError("No stable tags found in repository")
    # Explicit tagged release requested
    if release is not None and release != "":
        if release not in stable_tags:
            raise RuntimeError(
                f"Requested OpenClaw release '{release}' "
                "was not found or is not a stable release"
            )
        return release
    # Default to latest stable release
    return stable_tags[0]

def get_latest_commit(repo_path):
    """
    Return the latest commit SHA from origin/HEAD.
    """
    output = git("rev-parse", "origin/HEAD", cwd=repo_path, capture_output=True)
    if output is None:
        raise RuntimeError("Failed to retrieve latest commit SHA")
    return output

def get_local_update_files(repo_path):
    """
    Return a sorted list of locally modified/untracked files.
    """
    output = git("status", "--porcelain", cwd=repo_path, capture_output=True)
    if not output:
        return []
    files = []
    for line in output.splitlines():
        if not line.strip():
            continue
        # porcelain format:
        # XY <path>
        path = line[3:].strip()
        # handle rename syntax:
        # old -> new
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return sorted(set(files))

def format_local_update_error(target_desc, target_ref, files):
    """
    Build a user-friendly local update conflict error message.
    """
    file_list = "\n".join(f"  - {f}" for f in files)
    return (
        "Preserving local OpenClaw updates enabled.\n\n"
        f"Unable to checkout OpenClaw {target_desc} '{target_ref}' "
        "because the following local files would be overwritten:\n\n"
        f"{file_list}\n\n"
        "Commit, stash, or discard local changes and retry.\n\n"
        "To force a clean checkout:\n"
        "  OPENCLAW_KEEP_LOCAL_UPDATES=0"
    )

def checkout_openclaw_ref(repo_path, target_ref, target_desc, preserve=False):
    """
    Checkout a repository ref safely.
    If preserve=True, preserve local modifications and
    fail with a clear error if checkout would overwrite files.
    """
    try:
        git("checkout", target_ref, cwd=repo_path)
    except subprocess.CalledProcessError as exc:
        if not preserve:
            raise
        files = get_local_update_files(repo_path)
        raise RuntimeError(
            format_local_update_error(
                target_desc,
                target_ref,
                files
            )
        ) from exc

def clone_supabase_repo(preserve=False):
    """Clone the Supabase repository using sparse checkout,
    then checkout the latest tagged release."""
    repo_path = pathlib.Path("supabase")
    if not repo_path.exists():
        log.info("Cloning the Supabase repository...")
        git(
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "https://github.com/supabase/supabase.git"
        )
        git("config", "advice.detachedHead", "false", cwd=repo_path)
        git("sparse-checkout", "init", "--cone", cwd=repo_path)
        git("sparse-checkout", "set", "docker", cwd=repo_path)
    else:
        log.info("Supabase repository already exists, updating...")
    # Fetch tags to resolve latest release
    git("fetch", "--prune", "--tags", "--force", "origin", cwd=repo_path)
    # Ensure clean working tree before switching tags
    git("reset", "--hard", cwd=repo_path)
    git("clean", "-fd", cwd=repo_path)
    # Checkout latest release tag
    latest_tag = get_latest_tag(repo_path)
    log.info(f"Checking out latest Supabase release tag: {latest_tag}", extra=log_bright)
    checkout_openclaw_ref(repo_path, latest_tag, "tag", preserve=preserve)

def clone_openclaw_repo(oc_release=None):
    """
    Clone or update the OpenClaw repository with sparse checkout.
    Checkout behaviour:
      - latest stable release tag (default)
      - requested stable release tag
      - latest commit if oc_release["release"] == "commit"
    Local update behaviour:
      - preserve=False:
          reset/clean repository before checkout
      - preserve=True:
          preserve modified/untracked local files
    """
    if oc_release is None:
        oc_release = {
            "release": "",
            "preserve": False
        }
    release = oc_release["release"]
    preserve = oc_release["preserve"]
    repo_path = pathlib.Path("openclaw")
    if not repo_path.exists():
        log.info("Cloning the OpenClaw repository...")
        git(
            "clone",
            "--filter=blob:none",
            "https://github.com/openclaw/openclaw.git"
        )
        git("config", "advice.detachedHead", "false", cwd=repo_path)
    else:
        log.info("OpenClaw repository already exists, updating...")
    # Refresh repository refs
    if release == "commit":
        git("fetch", "origin", cwd=repo_path)
    else:
        git("fetch", "--prune", "--tags", "--force", "origin", cwd=repo_path)
    if preserve:
        files = get_local_update_files(repo_path)
        if files:
            log.info("Preserving local OpenClaw repository updates", extra=log_bright)
    else:
        # Ensure clean working tree before switching refs
        git("reset", "--hard", cwd=repo_path)
        git("clean", "-fd", cwd=repo_path)
    # Checkout latest commit
    if release == "commit":
        commit_sha = get_latest_commit(repo_path)
        log.info(f"Checking out latest commit: {commit_sha}", extra=log_bright)
        checkout_openclaw_ref(repo_path, commit_sha, "commit", preserve=preserve)
        return
    # Checkout tag release
    release_tag = get_latest_tag(repo_path, oc_release)
    if release is not None and release != "":
        release_desc = "release"
    else:
        release_desc = "latest release"
    log.info(f"Checking out {release_desc} tag: {release_tag}", extra=log_bright)
    checkout_openclaw_ref(repo_path, release_tag, "tag", preserve=preserve)

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

def prepare_openclaw_env(environment, oc_store, oc_cwd):
    """
    Creates a .env file from .env.example with required values set while
    preserving comments and layout from the template.
    """
    # OpenClaw setup.sh changes (commits):
    # https://github.com/openclaw/openclaw/blob/main/scripts/docker/setup.sh
    # 19/05/2026 - ff4bf0c
    # 18/05/2026 - 47b8e56
    # ...
    # 28/04/2026 - 66f4b52
    cwd = oc_cwd or "./openclaw"
    example_path = os.path.join(cwd, ".env.example")
    output_path = os.path.join(cwd, ".env")
    home_dir = pathlib.Path.home()
    config_dir = home_dir / ".openclaw"
    config_file = config_dir / "openclaw.json"
    config_workspace_dir = config_dir / "workspace"
    config_secrets_dir = home_dir / ".openclaw-auth-profile-secrets"
    if is_wsl2():
        home_dir = to_wsl_path(home_dir)
        config_dir = to_wsl_path(config_dir)
        config_file = to_wsl_path(config_file)
        config_workspace_dir = to_wsl_path(config_workspace_dir)
        config_secrets_dir = to_wsl_path(config_secrets_dir)
    sandbox = bool(oc_store["sandbox"])
    gateway_token = secrets.token_hex(32)
    gateway_password = secrets.token_hex(16)
    env_vars: dict[str, str | int | bool | None] = {
        "OPENCLAW_HOME": str(home_dir),
        "OPENCLAW_STATE_DIR": str(config_dir),
        "OPENCLAW_CONFIG_DIR": str(config_dir),
        "OPENCLAW_CONFIG_PATH": str(config_file),
        "OPENCLAW_WORKSPACE_DIR": str(config_workspace_dir),
        "OPENCLAW_AUTH_PROFILE_SECRET_DIR": str(config_secrets_dir),
        "OPENCLAW_GATEWAY_PORT": 18789,
        "OPENCLAW_BRIDGE_PORT": 18790,
        "OPENCLAW_GATEWAY_BIND": "lan",
        "OPENCLAW_GATEWAY_TOKEN": gateway_token,
        "OPENCLAW_GATEWAY_PASSWORD": gateway_password,
        "OPENCLAW_IMAGE": (
            "openclaw:local"
            if (sandbox or oc_store["local-image"])
            else "ghcr.io/openclaw/openclaw:latest"
        ),
        "OPENCLAW_SANDBOX": int(sandbox),
        "OPENCLAW_EXTENSIONS": "",
        "OPENCLAW_IMAGE_APT_PACKAGES": "",
        "OPENCLAW_IMAGE_PIP_PACKAGES": "",
        "OPENCLAW_INSTALL_DOCKER_CLI": int(sandbox),
        "OPENCLAW_INSTALL_BROWSER": 0,
        "OPENCLAW_SKIP_ONBOARDING": (
            "false"
            if oc_store["onboard"]
            else "true"
        ),
        "OPENAI_API_KEY": (
            "llamacpp-local"
            if llama_cpp
            else "ollama-local"
        ),
        "DOCKER_GID": "",
        "COMPOSE_IGNORE_ORPHANS": "true"
    }
    overwrite_if_populated = {
        "OPENCLAW_IMAGE",
        "OPENCLAW_SANDBOX",
        "OPENCLAW_SKIP_ONBOARDING",
        "OPENAI_API_KEY"
    }
    dotenv_exists = os.path.exists(output_path)
    control_env_path = output_path if dotenv_exists else example_path
    template_env = get_dotenv_vars(control_env_path)
    for key, value in template_env.items():
        if (
            key in env_vars
            and key not in overwrite_if_populated
            and value not in (None, "")
        ):
            env_vars[key] = value
    if template_env.get("OPENCLAW_GATEWAY_TOKEN") not in (None, ""):
        env_vars["OPENCLAW_GATEWAY_PASSWORD"] = None
    if template_env.get("OPENCLAW_GATEWAY_PASSWORD") not in (None, ""):
        env_vars["OPENCLAW_GATEWAY_TOKEN"] = None
    log.info(f"Writing .env file to {output_path}...")
    def render_var(key, value):
        return f"{key}={value}\n"
    def should_replace(key, existing):
        if key not in env_vars:
            return False
        if key in overwrite_if_populated:
            return True
        return existing in ("", None)
    try:
        with open(example_path, "r", newline="\n") as f:
            lines = f.readlines()
        output: list[str] = []
        written: set[str] = set()
        for line in lines:
            stripped = line.strip()
            # Cosmetic replacements
            if stripped.startswith("# OpenClaw .env example"):
                output.append("# OpenClaw .env (from .env.example)\n")
                continue
            if stripped.startswith("# 1) Copy this file to `.env`"):
                output.append(
                    "# 1) Copied to `./openclaw/.env`\n"
                )
                continue
            # Handle active env vars
            if "=" in stripped and not stripped.startswith("#"):
                key, current = stripped.split("=", 1)
                if should_replace(key, current):
                    value = env_vars.get(key)
                    if value is not None:
                        output.append(render_var(key, value))
                    written.add(key)
                else:
                    output.append(line)
                    written.add(key)
                continue
            # Inject commented defaults
            if stripped.startswith("# "):
                commented = stripped[2:]
                if "=" in commented:
                    key, _ = commented.split("=", 1)
                    if (
                        key in env_vars
                        and key not in written
                        and env_vars[key] is not None
                    ):
                        output.append(render_var(key, env_vars[key]))
                        written.add(key)
                        continue
            output.append(line)
        # Append remaining vars not represented upstream
        remaining = {
            k: v
            for k, v in env_vars.items()
            if k not in written and v is not None
        }
        docker_settings = {
            key: remaining.pop(key)
            for key in (
                "DOCKER_GID",
                "COMPOSE_IGNORE_ORPHANS"
            )
            if key in remaining
        }
        if docker_settings:
            output.extend([
                "\n",
                "# " + "-" * 77 + "\n",
                "# Docker settings\n",
                "# " + "-" * 77 + "\n"
            ])
            for key, value in docker_settings.items():
                output.append(render_var(key, value))
        if remaining:
            output.extend([
                "\n",
                "# " + "-" * 77 + "\n",
                "# Docker setup variables\n",
                "# " + "-" * 77 + "\n"
            ])
            for key, value in remaining.items():
                output.append(render_var(key, value))
        with open(output_path, "w", newline="\n") as f:
            f.writelines(output)
    except Exception as e:
        log.error(f"Exception: OpenClaw setup env vars: {e}")
        return False
    debug_style = LSHF.style(logging.WARNING)
    for key, value in env_vars.items():
        if value is None:
            continue
        if "TOKEN" in key or "PASSWORD" in key:
            log.debug(f"{key}={elide(str(value))}", extra=debug_style)
        else:
            log.debug(f"{key}={value}", extra=debug_style)
    insert = 'updated' if dotenv_exists else 'created'
    log.info(f".env file {insert} at {output_path}", extra=log_bright)
    if environment == "public":
        _openclaw_compose_override()
    _openclaw_compose_updates()
    _openclaw_env_vars_logging()
    _openclaw_clawdoc_updates()
    return True

def prepare_openclaw_config(oc_cwd, env_vars):
    log.info("Starting OpenClaw config preparation...")
    config_dir = pathlib.Path.home() / ".openclaw"
    config_file = config_dir / "openclaw.json"
    config_workspace_dir = config_dir / "workspace"
    config_secrets_dir = pathlib.Path.home() / ".openclaw-auth-profile-secrets"
    config_src_file = pathlib.Path("./.openclaw.example.json")
    if not config_src_file.exists():
        log.error(f"Template not found: {config_src_file}")
        raise FileNotFoundError(config_src_file)
    with open(config_src_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    if not oc_cwd:
        oc_cwd = "./openclaw"
    oc_env_file=os.path.join(oc_cwd, ".env")
    oc_env : dict[str, str] = get_dotenv_vars(oc_env_file)
    if not oc_env:
         log.error("No OpenClaw setup environment variables detected!")
         return
    if env_vars is None:
        log.error("The env_vars dictionary is empty!")
        return

    token = oc_env.get("OPENCLAW_GATEWAY_TOKEN")
    log.info("Updating gateway token")
    config["gateway"]["auth"]["token"] = token
    openapi_key = oc_env.get("OPENAI_API_KEY")

    if llama_cpp:
        log.info("Configuring llama.cpp provider")
        port = env_vars.get("LLAMA_ARG_PORT", "8040")
        base_url = f"http://localhost:{port}/v1"
        models_env = [
            env_vars.get("LLAMACPP_MODEL_GEMMA_ID"),
            env_vars.get("LLAMACPP_MODEL_DEEPSEEK_ID"),
            env_vars.get("LLAMACPP_MODEL_MISTRAL_ID"),
            env_vars.get("LLAMACPP_MODEL_LLAMA_ID"),
            env_vars.get("LLAMACPP_MODEL_QWEN_ID"),
            env_vars.get("LLAMACPP_MODEL_USER_ID"),
        ]
        models_env = [m for m in models_env if m]
        service_ok = _openclaw_check_service(base_url)
        available = _openclaw_fetch_available_models(base_url) if service_ok else set()
        matches = {_openclaw_normalize(a): a for a in available}
        base_url = f"http://host.docker.internal:{port}/v1"
        valid_models = []
        for m in models_env:
            if available:
                if _openclaw_normalize(m) in matches:
                    resolved = matches[_openclaw_normalize(m)]
                    valid_models.append(resolved)
                else:
                    log.warning(f"Model not available in llama.cpp: {m}")
            else:
                log.debug(f"Skipping availability check for {m}")
                valid_models.append(m)
        if not valid_models:
            raise RuntimeError("No valid llama.cpp models found")
        primary = f"llamacpp/{valid_models[0]}"
        fallbacks = [f"llamacpp/{m}" for m in valid_models]
        config["agents"]["defaults"]["model"]["primary"] = primary
        config["agents"]["defaults"]["model"]["fallbacks"] = fallbacks
        log.info(f"Primary model: {primary}")
        log.debug(f"Fallbacks: {fallbacks}")
        config["models"] = {
            "mode": "merge",
            "providers": {
                "llamacpp": {
                    "baseUrl": base_url,
                    "apiKey": "llamacpp-local",
                    "api": "openai-completions",
                    "models": [
                        _openclaw_build_model_entry(
                            m, m.split("/")[-1]
                        )
                        for m in valid_models
                    ]
                }
            }
        }

    else:
        log.info("Configuring Ollama provider")
        port = env_vars.get("OLLAMA_PORT", "11434")
        base_url = f"http://localhost:{port}/v1"
        models_env = [
            env_vars.get("OLLAMA_DEFAULT_MODEL"),
            env_vars.get("OLLAMA_SUPPLEMENT_MODEL"),
            env_vars.get("OLLAMA_EMBEDDING_MODEL"),
        ]
        models_env = [m for m in models_env if m]
        service_ok = _openclaw_check_service(base_url)
        available = _openclaw_fetch_available_models(base_url) if service_ok else set()
        matches = {_openclaw_normalize(a): a for a in available}
        base_url = f"http://host.docker.internal:{port}/v1"
        valid_models = []
        for m in models_env:
            if available:
                if _openclaw_normalize(m) in matches:
                    resolved = matches[_openclaw_normalize(m)]
                    valid_models.append(resolved)
                else:
                    log.warning(f"Model not available in Ollama: {m}")
            else:
                log.debug(f"Skipping availability check for {m}")
                valid_models.append(m)
        if not valid_models:
            raise RuntimeError("No valid Ollama models found")
        primary = f"ollama/{valid_models[0]}"
        fallbacks = [f"ollama/{m}" for m in valid_models]
        config["agents"]["defaults"]["model"]["primary"] = primary
        config["agents"]["defaults"]["model"]["fallbacks"] = fallbacks
        log.info(f"Primary model: {primary}")
        log.debug(f"Fallbacks: {fallbacks}")
        config["models"] = {
            "mode": "merge",
            "providers": {
                "ollama": {
                    "baseUrl": base_url,
                    "apiKey": "ollama-local",
                    "api": "ollama",
                    "models": [
                        _openclaw_build_model_entry(m, m)
                        for m in valid_models
                    ]
                }
            }
        }

    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    config["meta"]["lastTouchedAt"] = now
    config["wizard"]["lastRunAt"] = now
    for config_dir in [config_dir, config_workspace_dir, config_secrets_dir]:
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            log.error(f"Permission denied creating {config_dir}: {e}")
        except OSError as e:
            log.error(f"OS error while creating {config_dir}: {e}")
    config_backup_file = None
    if config_file.exists():
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        config_backup_file = config_file.with_name(f"openclaw.json.bak.{timestamp}")
        log.info(f"Creating backup: {config_backup_file}")
        shutil.copy(config_file, config_backup_file)
    try:
        log.info(f"Writing config to {config_file}")
        with open(config_file, "w", encoding="utf-8", newline='\n') as f:
            json.dump(config, f, indent=2)
        log.info("OpenClaw .json configuration file written successfully")
    except Exception as e:
        log.error(f"Failed to write config: {e}")
        if config_backup_file and config_backup_file.exists():
            log.warning("Restoring from backup")
            shutil.copy(config_backup_file, config_file)
            log.info("Rollback completed")
        raise
    log.info("OpenClaw configuration setup completed")

def _openclaw_compose_updates(setup_path=None):
    """
    Set compose project to ai-suite and update installed Docker CLI check.
    """
    if setup_path is None:
        setup_path = "./openclaw/scripts/docker/setup.sh"
    path = pathlib.Path(setup_path)
    if not path.exists():
        raise FileNotFoundError(f"{setup_path} not found")
    try:
        with open(path, "r", newline="\n", encoding="utf-8") as f:
            lines = f.readlines()
        updated_lines: list[str] = []
        # Set compose project argument
        compose_args = 'COMPOSE_ARGS=("-p" "ai-suite")'
        compose_hint = 'COMPOSE_HINT="docker compose -p ai-suite"'
        compose_project = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(compose_args):
                updated_lines = lines
                compose_project = True
                break
            if stripped.startswith('COMPOSE_ARGS=()'):
                updated_lines.append(f'{compose_args}\n')
                compose_project = True
            elif stripped.startswith('COMPOSE_HINT="docker compose"'):
                updated_lines.append(f'{compose_hint}\n')
            else:
                updated_lines.append(line)
        if compose_project:
            log.info(f"Add compose project in {path}", extra=log_bright)
        else:
            log.error(f"COMPOSE_ARGS=() not found in {path}", extra=log_bright)
        # Update installed Docker CLI check
        lines = updated_lines
        updated_lines = []
        check_cli = False
        cli_check = 'if ! docker compose "${COMPOSE_ARGS[@]}" run --rm --entrypoint docker openclaw-gateway --version'
        cli_check_update = 'elif ! docker compose "${COMPOSE_ARGS[@]}" exec -T openclaw-gateway docker --version'
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(cli_check_update):
                updated_lines = lines
                check_cli = True
                break
            if stripped.startswith(cli_check):
                check_cli = True
                updated_lines.append('  if ! docker compose "${COMPOSE_ARGS[@]}" ps --status running | grep -q openclaw-gateway; then\n')
                updated_lines.append('    echo "WARNING: openclaw-gateway is not running. Skipping sandbox setup." >&2\n')
                updated_lines.append('    SANDBOX_ENABLED=""\n')
                updated_lines.append(f'  {cli_check_update} >/dev/null 2>&1; then\n')
            else:
                updated_lines.append(line)
        if check_cli:
            log.info(f"Update Docker CLI ckeck in {path}", extra=log_bright)
        else:
            log.error(f"Docker CLI ckeck not found in {path}")
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            f.writelines(updated_lines)
        log.info(f"Perform compose updates in {path}", extra=log_bright)
    except Exception as e:
        log.error(f"Exception: OpenClaw compose updates: {e}")

def _openclaw_compose_override(setup_path=None):
    """
    Enable docker compose public override for OpenClaw setup.
    """
    if setup_path is None:
        setup_path = "./openclaw/scripts/docker/setup.sh"
    path = pathlib.Path(setup_path)
    if not path.exists():
        raise FileNotFoundError(f"{setup_path} not found")
    try:
        with open(path, "r", newline="\n", encoding="utf-8") as f:
            lines = f.readlines()
        updated_lines: list[str] = []
        compose_public = False
        compose_public_add = False
        compose_public_file = 'COMPOSE_FILES=("$COMPOSE_FILE")'
        compose_public_found = 'AI_SUITE_DIR="$(cd "$ROOT_DIR/.." && pwd)"'
        compose_public_start = 'EXTRA_COMPOSE_FILE="$ROOT_DIR/docker-compose.extra.yml"'
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(compose_public_found):
                updated_lines = lines
                compose_public = True
                compose_public_add = True
                break
            if stripped.startswith(compose_public_start):
                updated_lines.append(line)
                updated_lines.append(f'{compose_public_found}\n')
                updated_lines.append('PUBLIC_COMPOSE_FILE="$AI_SUITE_DIR/docker-compose.override.public.yml"\n')
                updated_lines.append('ENVIRONMENT="${ENVIRONMENT:-public}"\n')
                compose_public = True
            elif stripped.startswith(compose_public_file):
                updated_lines.append(line)
                updated_lines.append('if [[ "$ENVIRONMENT" == "public" ]]; then\n')
                updated_lines.append('  COMPOSE_FILES+=("$PUBLIC_COMPOSE_FILE")\nfi\n')
                compose_public_add = True
            else:
                updated_lines.append(line)
        if not compose_public:
            log.error(f"{compose_public_start} not found in {path}")
        if not compose_public_add:
            log.error(f"{compose_public_file} not found in {path}")
        with open(path, "w", newline="\n") as f:
            f.writelines(updated_lines)
        log.info(f"Compose public override added in {path}", extra=log_bright)
    except Exception as e:
        log.error(f"Exception: OpenClaw add public override: {e}")

def _openclaw_clawdoc_updates(clawdoc_path=None):
    """
    Set ClawDock helpers home directory, OpenClaw path and comment update pull.
    """
    if clawdoc_path is None:
        clawdoc_path = "./openclaw/scripts/clawdock/clawdock-helpers.sh"
    path = pathlib.Path(clawdoc_path)
    if not path.exists():
        raise FileNotFoundError(f"{clawdoc_path} not found")
    clawdock_update = False
    clawdock_home = False
    clawdock_home_comment = '# Set home directory for .clawdock'
    clawdock_title_comment = '# ClawDock - Docker helpers for OpenClaw'
    clawdock_config = 'CLAWDOCK_CONFIG="${HOME}/.clawdock/config"'
    clawdock_paths = 'CLAWDOCK_COMMON_PATHS=('
    clawdock_pull = 'git -C "${CLAWDOCK_DIR}" pull'
    clawdock_pull_echo = 'echo "📥 Pulling latest source..."'
    try:
        # Resolve paths using native pathlib semantics
        home_dir = pathlib.Path.home()
        openclaw_dir = pathlib.Path("./openclaw").resolve()
        # Set paths to string
        if is_wsl2():
            home_dir_str = to_wsl_path(home_dir)
            openclaw_dir_str = to_wsl_path(openclaw_dir)
        else:
            home_dir_str = str(home_dir)
            openclaw_dir_str = str(openclaw_dir)
        relative_openclaw = None
        try:
            relative_openclaw = openclaw_dir.relative_to(home_dir)
        except ValueError:
            pass
        # Prefer CLAWDOCK_HOME-relative path when possible
        if relative_openclaw is not None:
            openclaw_dir_str = (f"${{CLAWDOCK_HOME}}/{relative_openclaw.as_posix()}")
        # Read clawdock-helpers.sh
        with open(path, "r", newline="\n", encoding="utf-8") as f:
            lines = f.readlines()
        updated_lines: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            # Already patched
            if stripped.startswith(clawdock_home_comment):
                updated_lines = lines
                clawdock_home = True
                clawdock_update = True
                break
            # Update script title
            if stripped.startswith(clawdock_title_comment):
                updated_lines.append(f"# ClawDock (for {name}) - Docker helpers for OpenClaw\n")
            # Insert CLAWDOCK_HOME
            elif stripped.startswith(clawdock_config):
                updated_lines.append("\n")
                updated_lines.append(f"{clawdock_home_comment}\n")
                updated_lines.append(f'CLAWDOCK_HOME="{home_dir_str}"\n')
                updated_lines.append(line)
                clawdock_home = True
            # Comment pull section
            elif stripped.startswith(clawdock_pull_echo):
                if updated_lines:
                    prev = updated_lines[-1]
                    prev_stripped = prev.lstrip()
                    if prev_stripped == 'echo ""\n':
                        updated_lines[-1] = f' #{prev_stripped}'
                updated_lines.append(f" #{stripped}")
                clawdock_update = True
            elif stripped.startswith(clawdock_pull):
                updated_lines.append(f" #{stripped}")
                clawdock_update = True
            # Add OpenClaw path
            elif stripped.startswith(clawdock_paths):
                updated_lines.append(line)
                updated_lines.append(f'  "{openclaw_dir_str}"\n')
            else:
                updated_lines.append(line)
            i += 1
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            f.writelines(updated_lines)
        # Replace home with clawdock_home
        clawdock_replace_home = False
        platform_home_dir = "${HOME}"
        clawdock_home_dir = "${CLAWDOCK_HOME}"
        with open(path, "r", newline="\n", encoding="utf-8") as f:
            content = f.read()
        if platform_home_dir in content:
            updated_content = content.replace(platform_home_dir, clawdock_home_dir)
            with open(path, "w", newline="\n", encoding="utf-8") as f:
                f.write(updated_content)
            clawdock_replace_home = True
        # Logging
        if clawdock_home:
            log.info(f"Add ClawDock home in {path}", extra=log_bright)
        else:
            log.error(f"{clawdock_config} not found in {path}")
        if clawdock_update:
            log.info(f"Comment ClawDock latest release pull in {path}", extra=log_bright)
        else:
            log.error(f"{clawdock_pull}... not found in {path}")
        if clawdock_replace_home:
            log.info(f"Replace ${{HOME}} with ${{CLAWDOCK_HOME}} in {path}", extra=log_bright)
        else:
            log.error(f"{clawdock_home_dir} not found in {path}")
    except Exception as e:
        log.error(f"Exception: OpenClaw ClawDock updates: {e}")

def _openclaw_env_vars_logging(setup_path=None):
    """
    Inject logging statements to display env vars.
    """
    if setup_path is None:
        setup_path = "./openclaw/scripts/docker/setup.sh"
    path = pathlib.Path(setup_path)
    if not path.exists():
        raise FileNotFoundError(f"{setup_path} not found")
    try:
        with open(path, "r", newline="\n") as f:
            lines = f.readlines()
        updated_lines: list[str] = []
        inject_env_logging = False
        performed_injection = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('# Injected environment variable logging.'):
                updated_lines = lines
                performed_injection = True
                break
            if stripped.startswith('upsert_env() {'):
                inject_env_logging = True
                updated_lines.append(line)
                continue
            elif stripped.startswith('echo "==> Building Docker image: $IMAGE_NAME"'):
                updated_lines.append('  echo "==> Building Docker image: $IMAGE_NAME, please wait..."\n')
                continue
            elif stripped.startswith('echo "==> Pulling Docker image: $IMAGE_NAME"'):
                updated_lines.append('  echo "==> Pulling Docker image: $IMAGE_NAME..."\n')
                continue
            # echo "==> Pulling Docker image: $IMAGE_NAME"
            if inject_env_logging:
                if stripped.startswith('tmp="$(mktemp)"'):
                    updated_lines.append(line)
                    updated_lines.append("  # Injected environment variable logging.\n")
                    updated_lines.append('  echo "==> OpenClaw setup environment variables:"\n')
                    updated_lines.append('  echo "  - ROOT_DIR: ${ROOT_DIR:-}"\n')
                    updated_lines.append('  echo "  - COMPOSE_FILE: ${COMPOSE_FILE:-}"\n')
                    updated_lines.append('  echo "  - EXTRA_COMPOSE_FILE: ${EXTRA_COMPOSE_FILE:-}"\n')
                    continue
                elif stripped.startswith('mv "$tmp" "$file"'):
                    updated_lines.append(line)
                    inject_env_logging = False
                    continue
                if stripped.startswith('if [[ "$key" == "$k" ]]; then'):
                    updated_lines.append(line)
                    updated_lines.append('          echo "  - $k: ${!k-}"\n')
                    performed_injection = True
                elif stripped.startswith('if [[ "$seen" != *" $k "* ]]; then'):
                    updated_lines.append(line)
                    updated_lines.append('      echo "  - $k: ${!k-}"\n')
                    performed_injection = True
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        with open(path, "w", newline="\n") as f:
            f.writelines(updated_lines)
        if performed_injection:
            log.info(f"OpenClaw add env vars logging in {path}", extra=log_bright)
        else:
            log.warning(f"Function upsert_env not found - skip logging injection.")
    except Exception as e:
        log.error(f"Exception: OpenClaw env vars logging: {e}")

def _openclaw_normalize(name: str):
    if not isinstance(name, str):
        raise TypeError("Model name must be a string")
    name = name.strip()
    if not name:
        raise ValueError("Model name must not be empty")
    if ":" in name:
        parts = [p for p in name.split(":") if p]
        if not parts:
            raise ValueError("Invalid ':'-separated model id")
        return parts[0]
    parts = [p for p in name.split("/") if p]
    if not parts:
        raise ValueError("Invalid '/'-separated model id")
    return parts[-1]

def _openclaw_check_service(base_url):
    """Check if model service is reachable."""
    if not base_url:
        log.error("Cannot check service, the base URL is empty")
        return False
    try:
        log.debug(f"Checking service health at {base_url}")
        r = requests.get(base_url.replace("/v1", ""), timeout=2)
        return r.status_code < 500
    except Exception as e:
        log.warning(f"Service check failed: {e}")
        return False

def _openclaw_fetch_available_models(base_url):
    """Try to fetch available models from API."""
    if not base_url:
        log.error("Cannot fetch model, the base URL is empty")
        return set()
    try:
        url = f"{base_url}/models"
        log.debug(f"Fetching models from {url}")
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            return {m.get("id") for m in data.get("data", [])}
    except Exception as e:
        log.warning(f"Could not fetch models: {e}")
    return set()

def _openclaw_build_model_entry(model_id, name):
    return {
        "id": model_id,
        "name": name,
        "reasoning": True,
        "input": ["text"],
        "cost": {
            "input": 0,
            "output": 0
        },
        "contextWindow": 400000
    }

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
                    image: open-webui-filesystem:local
                    pull_policy: never
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
    profile.remove('supabase') if 'supabase' in profile else None
    profile.remove('openclaw') if 'openclaw' in profile else None
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

    os.makedirs('./state', exist_ok=True)
    with open('./state/.operation', 'w', newline='\n') as f:
        f.write(operation + ':' + llama.lower())

    supabase = False
    openclaw = False
    open_webui = False
    # WebUI built - nothing to pull, Supabase and OpenClaw pulled with suite via include.
    if operation != 'pull':
        supabase = any(p for p in profile if p in ['supabase', 'ai-all'])
        if operation != 'pause':
            openclaw = any(p for p in profile if p in ['openclaw', 'ai-all'])
        open_webui = any(p for p in profile if p in open_webui_all_profiles)
    profile.remove('supabase') if 'supabase' in profile else None
    profile.remove('openclaw') if 'openclaw' in profile else None

    if operation == 'start' and environment:
        load_dotenv_vars(env_vars)
        if supabase:
            start_supabase(environment, False)
            log.info("Waiting for Supabase to initialize...", extra=log_bright)
            wait_with_progress(5)
        if openclaw:
            start_openclaw(environment, build=False, oc_cwd=None)
            log.info("Waiting for OpenClaw to initialize...", extra=log_bright)
            wait_with_progress(5)
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
    if openclaw:
        compose_args = ["-f", "openclaw/docker-compose.yml"]
        extra_compose = pathlib.Path("openclaw/docker-compose.extra.yml")
        if extra_compose.is_file():
            compose_args += ["-f", "openclaw/docker-compose.extra.yml"]
        openclaw_operation = ["down"] if operation == 'stop' else []
        cmd = base + compose_args + openclaw_operation
        run_command(cmd)
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

def operate_openclaw(operation, environment, oc_store, oc_cwd=None):
    """Execute OpenClaw commands using ClawDoc."""
    if not operation:
        log.error("A ClawDoc command was not specified!")
        return
    log.info(f"Running OpenClaw {operation}...")
    oc_dir = "openclaw"
    if not oc_cwd:
        base_dir = pathlib.Path(__file__).parent
        oc_cwd = os.path.join(base_dir, oc_dir)
    oc_script = os.path.normpath("scripts/clawdock/clawdock-helpers.sh")
    oc_path = os.path.normpath(os.path.join(oc_dir, oc_script))
    if not os.path.exists(oc_path):
        log.error(f"ClawDoc commands script not found at {oc_path}")
        return
    interactive_operations = {
        "clawdock-cli": "Enter a CLI",
        "clawdock-exec": "Enter a container",
        "clawdock-approve": "Enter a device pairing",
    }
    if operation in interactive_operations:
        prompt = interactive_operations[operation]
        value = (
            "request-id"
            if operation == "clawdock-approve"
            else "command"
        )
        response = input(f"{prompt} <{value}>: ").strip()
        if not response:
            log.error(f"{operation} requires a <{value}>.")
            operation = "clawdock-help"
        else:
            operation = f"{operation} {response}"
    if operation == "clawdock-update":
        clone_openclaw_repo()
        prepare_openclaw_env(environment, oc_store, oc_cwd)
    cmd = ["bash", "-c"]
    if system == 'Windows':
        cmd = ["wsl", "-e"] + cmd
        convert_line_endings(oc_path)
        oc_script = oc_script.replace("\\", "/")
    cmd_str = f"source {oc_script} && {operation}"
    oc_cmd = cmd + [cmd_str]
    run_command(oc_cmd, cwd=oc_cwd)

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

def start_openclaw(environment=None, build=False, oc_cwd=None):
    """Start the OpenClaw services."""
    if not build:
        base = ["docker", "compose", "-p", "ai-suite"]
        start = ["up", "-d", "openclaw-gateway"]
        compose_args = ["-f", "openclaw/docker-compose.yml"]
        extra_compose = pathlib.Path("openclaw/docker-compose.extra.yml")
        if extra_compose.is_file():
            compose_args += ["-f", "openclaw/docker-compose.extra.yml"]
        if environment == "public":
            compose_args += ["-f", "docker-compose.override.public.yml"]
        cmd = base + compose_args + start
        run_command(cmd)
        return
    log.info("Starting OpenClaw services...")
    oc_dir = "openclaw"
    oc_script = os.path.normpath("scripts/docker/setup.sh")
    oc_path = os.path.normpath(os.path.join(oc_dir, oc_script))
    if not os.path.exists(oc_path):
        log.error(f"OpenClaw setup script not found at {oc_path}")
        return
    cmd = ["bash", "-c"]
    if system == 'Windows':
        cmd = ["wsl", "-e"] + cmd
        convert_line_endings(oc_path)
        oc_script = oc_script.replace("\\", "/")
    oc_env_file=os.path.join(oc_dir, ".env")
    oc_env : dict[str, str] = get_dotenv_vars(oc_env_file)
    if not oc_env:
        log.error(f"OpenClaw .env file not found at {oc_env_file}")
    env = {}
    for key, val in oc_env.items():
        if val is not None:
            env[key] = val
    env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    cmd_str = f"{env_prefix} {oc_script}" if env_prefix else oc_script
    oc_cmd = cmd + [cmd_str]
    run_command(oc_cmd, cwd=oc_cwd)

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

def copy_supabase_authelia_schema():
    athelia_sh_path = os.path.join("access", "authelia", "db", "schema-authelia.sh")
    supabase_db_dir = os.path.join("supabase", "docker", "volumes", "db")
    if not os.path.exists(athelia_sh_path):
        log.error(f"File {athelia_sh_path} not found.")
        return
    convert_line_endings(athelia_sh_path)
    schema_path = os.path.join(supabase_db_dir, "schema-authelia.sh")
    shutil.copy(athelia_sh_path, schema_path)

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

def docker_compose_include(supabase, openclaw, filesystem, verbose):
    """Add or remove Supabase, OpenClaw and Filesystem include compose.yml in
       docker-compose.yml
    """
    compose_file = "docker-compose.yml"
    supabase_compose_file = "supabase/docker/docker-compose.yml"
    openclaw_compose_file = "openclaw/docker-compose.yml"
    filesystem_compose_file = "open-webui/tools/servers/filesystem/compose.yaml"
    if not os.path.exists(compose_file):
        log.error(f"Docker Compose file '{compose_file}' not found - include skipped...")
        return
    if supabase and not os.path.exists(supabase_compose_file):
        if verbose:
            log.warning(f"Include file '{supabase_compose_file}' not found.")
        supabase = False
    if openclaw and not os.path.exists(openclaw_compose_file):
        if verbose:
            log.warning(f"Include file '{openclaw_compose_file}' not found.")
        openclaw = False
    if filesystem and not os.path.exists(filesystem_compose_file):
        if verbose:
            log.warning(f"Include file '{filesystem_compose_file}' not found.")
        filesystem = False
    if verbose:
        supabase_ins = "add" if supabase else "remove"
        openclaw_ins = "add" if openclaw else "remove"
        filesystem_ins = "add" if filesystem else "remove"
        log.info(
            f"Perform {supabase_ins} Supabase, "
            f"{openclaw_ins} OpenClaw, "
            f"and {filesystem_ins} Filesystem "
            f"'include:' in {compose_file}...")
    include = supabase or openclaw or filesystem
    compose_include = "include:\n"
    supabase_include = f"  - ./{supabase_compose_file}\n"
    openclaw_include = f"  - ./{openclaw_compose_file}\n"
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

        if filesystem and filesystem_include not in content:
            if verbose:
                log.info(f"Adding include file ./{filesystem_compose_file}...")
            content = filesystem_include + content
        elif not filesystem and filesystem_include in content:
            if verbose:
                log.info(f"Removing include file ./{filesystem_compose_file}...")
            content = content.replace(filesystem_include, "")

        if openclaw and openclaw_include not in content:
            if verbose:
                log.info(f"Adding include file ./{openclaw_compose_file}...")
            content = openclaw_include + content
        elif not openclaw and openclaw_include in content:
            if verbose:
                log.info(f"Removing include file ./{openclaw_compose_file}...")
            content = content.replace(openclaw_include, "")

        if supabase and supabase_include not in content:
            if verbose:
                log.info(f"Adding include file ./{supabase_compose_file}...")
            content = supabase_include + content
        elif not supabase and supabase_include in content:
            if verbose:
                log.info(f"Removing include file ./{supabase_compose_file}...")
            content = content.replace(supabase_include, "")

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
    if not path:
        log.error("Cannot normalize path - path is empty.")
        return path

    if path.startswith('~'):
        path = os.path.expanduser(path)
    elif path.strip() == '.':
        path = os.getcwd()
    if os.name == 'nt' and path.startswith('/'):
        return path
    return os.path.abspath(path)

def get_dotenv_vars(env_file=None, force=False, auto_config=False, profile=None):
    """Load environment variables from .env file"""
    if env_file is None:
        env_file = os.path.join(".env")
    env_parent = pathlib.Path(env_file).resolve().parent
    my_parent = pathlib.Path(__file__).resolve().parent
    ai_suite_env = (env_parent == my_parent)
    valid_env_file = os.path.exists(env_file)
    if not valid_env_file:
        if os.path.exists(".env.example"):
            shutil.copy('.env.example', '.env')
            valid_env_file = os.path.exists(env_file)
            if valid_env_file:
                auto_config = str(dotenv.get_key(env_file, 'AC')).lower() == 'true'
            valid_env_file = False
            ai_suite_env = True
            if not auto_config:
                log.warning("The .env file was not found - it was created from .env.example template")
                log.critical("⚠️ IMPORTANT: Edit .env file with secure passwords and keys - exiting...")
                return {}
        else:
            log.critical("The .env.example file was not found - exiting...")
            return {}
    elif ai_suite_env:
        auto_config = str(dotenv.get_key(env_file, 'AC')).lower() == 'true'

    if ai_suite_env and not auto_config:
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
    if ai_suite_env:
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
        log.error(f"Exception: {e.stderr}.")
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
        debug_log = log_level == logging.DEBUG and not container == 'openclaw-cli'
        if debug_log:
            color = LSHF.WHITE if running else LSHF.RED
            style = LSHF.style(logging.INFO, color)
            insert = ('is', 'running.') if running else ('not', 'running!')
            raw_msg = " ".join([container, insert[0], insert[1]])
            log.debug("Container {}".format(raw_msg), extra=style)
        return running
    except subprocess.CalledProcessError as e:
        log.error(f"Exception: {e.stderr}.")
        return False

def display_service_endpoints(profile, supabase, openclaw, env_vars=None):
    """Display AI-Suite installation or operation status"""
    if not profile:
        log.error("Profile required to display service endpoints")
        return

    debug = log_level == logging.DEBUG
    if env_vars is None:
        env_vars = {}
    host = "localhost" if debug else env_vars.get('AC_DOMAIN', 'undefined')
    private = str(env_vars.get('AC_LOCAL')).lower()
    protocol = 'http' if private else 'https'
    cli_containers = ['opencode', 'openclaw-cli']
    def endpoint_url(container, endpoint):
        if container in cli_containers:
            return f'{endpoint}'
        return f'{protocol}://{container}.{host}:{endpoint}'

    # This dictionary holds a list of touples (container, Module Name, Endpoint)
    # grouped by module - aka profile argument
    ai_suite_modules = {
        'n8n': [
            ('n8n',                 'n8n',            '5678'),
            ('mcp-gateway',         'MCP Gateway',    '8060/'),
            ('qdrant',              'QDrant',         '6333/dashboard'),
            ('postgres',            'PostgreSQL',     '5432/'),
            ('supabase-kong',       'Supabase',       '8000'),
            ('supabase-analytics',  'Logflare',       '4000/dashboard'),
            ('redis',               'Redis',          '6379/'),
            ('n8n-runner',          'n8n Runner',           ''),
            ('n8n-worker',          'n8n Worker',           ''),
            ('n8n-worker-runner',   'n8n Worker Runner',    '')
        ],
        'n8n-all': [
            ('n8n',                 'n8n',                    '5678'),
            ('open-webui',          'Open WebUI',             '8080/'),
            ('open-webui-filesystem','Open WebUI Filesystem', '8091/docs'),
            ('mcp-gateway',         'MCP Gateway',            '8060/'),
            ('open-webui-mcpo',     'Open WebUI MCPO',        '8090/'),
            ('qdrant',              'QDrant',                 '6333/dashboard'),
            ('postgres',            'PostgreSQL',             '5432/'),
            ('supabase-kong',       'Supabase',               '8000'),
            ('supabase-analytics',  'Logflare',               '4000/dashboard'),
            ('redis',               'Redis',                  '6379/'),
            ('n8n-runner',          'n8n Runner',           ''),
            ('n8n-worker',          'n8n Worker',           ''),
            ('n8n-worker-runner',   'n8n Worker Runner',    '')
        ],
        'opencode': [
            ('opencode',            'Opencode', './opencode/run_opencode_docker.py'),
            ('mcp-gateway',         'MCP Gateway',            '8060/')
        ],
        'open-webui': [
            ('open-webui',          'Open WebUI',             '8080/'),
            ('mcp-gateway',         'MCP Gateway',            '8060/'),
            ('open-webui-mcpo',     'Open WebUI MCPO',        '8090/'),
            ('open-webui-filesystem','Open WebUI Filesystem', '8091/docs')
        ],
        'open-webui-mcpo': [
            ('mcp-gateway',         'MCP Gateway',     '8060/'),
            ('open-webui-mcpo',     'Open WebUI MCPO', '8090/')
        ],
        'openclaw': [
            ('openclaw-gateway',    'OpenClaw Control UI', '18789/'),
            ('openclaw-cli',        'OpenClaw CLI',        'openclaw-cli')
        ],
        'flowise': [
            ('flowise',             'Flowise',         '3001/')
        ],
        'supabase': [
            ('supabase-kong',       'Supabase',        '8000'),
            ('supabase-analytics',  'Logflare',        '4000/dashboard'),
            ('supabase-pooler',     'Supavisor',       '6543'),
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
            ('langfuse-web',        'Langfuse Web',    '3000/'),
            ('langfuse-worker',     'Langfuse Worker', '3030/'),
            ('clickhouse',          'ClickHouse',      '8123/'),
            ('postgres',            'PostgreSQL',      '5432/'),
            ('redis',               'Redis',           '6379/'),
            ('minio',               'MinIO',           '9001/')
        ],
        'searxng': [
            ('searxng',             'SearXNG',         '8081/')
        ],
        'neo4j': [
            ('neo4j',               'Neo4j',           '7473/')
        ],
        'caddy': [
            ('caddy',               'Caddy',           '443/'),
            ('authelia',             'Authelia',       '9091/')
        ],
        'nginx': [
            ('nginx',               'Nginx',           '443/'),
            ('authelia',             'Authelia',       '9091/')
        ],
        'cpu': [
            ('ollama',              'Ollama',          '11434/')
        ],
        'gpu-nvidia': [
            ('ollama',              'Ollama',          '11434/')
        ],
        'gpu-amd': [
            ('ollama',              'Ollama',          '11434/')
        ],
        'cpp-cpu': [
            ('llamacpp',            'LLaMA.cpp',       '8040')
        ],
        'cpp-gpu-nvidia': [
            ('llamacpp',            'LLaMA.cpp',       '8040')
        ],
        'cpp-gpu-amd': [
            ('llamacpp',            'LLaMA.cpp',       '8040')
        ]
    }

    module_list = []
    container_list = []
    module_names = set()
    proxy_in_profile = any(p in profile for p in ('caddy', 'nginx'))
    if supabase is None:
        supabase = any(p for p in profile if p in ['supabase', 'ai-all'])
    if openclaw is None:
        openclaw = any(p for p in profile if p in ['openclaw', 'ai-all'])

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
        if not openclaw and 'openclaw-' in container:
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
        if not docker_container_is_running(container) \
        and not container == 'openclaw-cli'
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
    for container, module_name, endpoint in module_list:
        if not endpoint:
            continue
        emoji = '🚀' if container in cli_containers else '🔗'
        module_prefix = LSHF.prefix(LSHF.GREEN)
        apoint_prefix = LSHF.prefix(LSHF.BLUE)
        url = endpoint_url(container, endpoint)
        if container in failed_container_list:
            emoji = '❌'
            module_prefix = LSHF.prefix(LSHF.YELLOW, italic=True)
            apoint_prefix = LSHF.prefix(LSHF.RED, italic=True)
        endpoint_prefix = ("{}• {:23s}{}{} {}{}").format(
            module_prefix, module_name + ":", LSHF.suffix(), emoji,
            apoint_prefix, url)
        endpoint_style = {'prefix': endpoint_prefix, 'suffix': LSHF.suffix()}
        endpoint_style.update({'purge_msg':'True'})
        raw_msg = ("• {:23s}{} {}").format(module_name + ":", emoji, url)
        log.info(raw_msg, extra=endpoint_style)
    if not started_ok:
        log.info("")
        msg = "This Docker container is not running:"
        if len(failed_container_list) > 1:
            msg = "These Docker containers are not running:"
        log.info(msg, extra=info_style)
        for container, module_name, __ in module_list:
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

def setup_ai_suite_ac_auto_config(prompt_store, oc_store, env_vars=None):
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
    if prompt and oc_store:
        onboard = oc_store['onboard']
        response = input(f"Perform OpenClaw onboarding? y/n: (n)").strip()
        oc_store['onboard'] = True if (response and response.lower() == 'y') else onboard
        env_vars["OPENCLAW_ONBOARDING"] = "1" if oc_store['onboard'] else "0"
        sandbox = oc_store['sandbox']
        response = input(f"Enable OpenClaw sandbox? y/n: (y)").strip()
        oc_store['sandbox'] = False if (response and response.lower() == 'n') else sandbox
        env_vars["OPENCLAW_DOCKER_SANDBOX"] = "1" if oc_store['sandbox'] else "0"
        local_image = oc_store['local-image']
        response = input(f"Enable OpenClaw build local image? y/n: (y)").strip()
        oc_store['local-image'] = False if (response and response.lower() == 'n') else local_image
        env_vars["OPENCLAW_DOCKER_LOCAL_IMAGE"] = "1" if oc_store['local-image'] else "0"
    response = None
    public = False

    # AC - bool
    ac_env_vars = [f'AC="{str(ac).lower()}"']
    # AC_SUDO_USER - str
    default = env_vars.get('AC_SUDO_USER', sudo_user())
    if prompt:
        non_root = "non-root"
        if system == "Windows":
            non_root = " ".join(["WSL", non_root])
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
        password = getpass.getpass(f"Enter proxy user password or skip to auto-generate (required: ***): ")
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
    local = 'localhost' if log_level == logging.DEBUG else 'local.pc'
    default = env_vars.get('AC_DOMAIN', 'ai-suite.fr' if public else local)
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
    ac_script = os.path.normpath(os.path.join("access", "auto_config.sh"))
    if not os.path.exists(ac_script):
        log.error(f"Auto-configure script not found at {ac_script}")
        return
    if system == 'Windows':
        convert_line_endings(ac_script)
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
    cmd_msg = cmd + [f'env {" ".join(cmd_msg)} {ac_script}']
    raw_msg = " ".join([log_run_cmd, " ".join(cmd_msg)])
    log.info(raw_msg, extra=LSHF.style(header=log_run_cmd, msg=" ".join(cmd_msg)))
    cmd = cmd + [f'env {" ".join(ac_env_vars)} {ac_script}']
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
    server_profiles = ['supabase', 'openclaw', 'flowise', 'searxng', 'langfuse', 'neo4j']
    subdomain_profiles = n8n_profiles + open_webui_profiles + server_profiles + \
                         llama_host_profiles
    proxy_profiles = ['caddy', 'nginx']
    auto_config_profiles = ['manual-configuration', 'no_auto_config']
    profiles = agent_all_profiles + open_webui_utils_profiles + server_profiles + \
               llama_host_profiles + llama_docker_profiles + proxy_profiles + \
               auto_config_profiles
    managemant_operations = ['stop', 'stop-llama', 'start', 'pause', 'unpause']
    data_operations = ['backup-data', 'restore-data']
    installation_operations = ['update', 'install']
    managemant_and_data_operations = managemant_operations + data_operations
    clawdock_operations = ['clawdock-start', 'clawdock-stop', 'clawdock-restart',
                           'clawdock-status', 'clawdock-logs']
    clawdock_access = ['clawdock-shell', 'clawdock-cli', 'clawdock-exec']
    clawdock_ui_devices = ['clawdock-dashboard', 'clawdock-devices', 'clawdock-approve']
    clawdock_configuration = ['clawdock-fix-token']
    clawdock_maintenance = ['clawdock-update', 'clawdock-rebuild', 'clawdock-clean']
    clawdock_utilities = ['clawdock-token', 'clawdock-token', 'clawdock-cd', 'clawdock-config',
                          'clawdock-show-config', 'clawdock-workspace', 'clawdock-help']
    openclaw_operations = clawdock_operations + clawdock_access + clawdock_ui_devices + \
                          clawdock_configuration + clawdock_maintenance + clawdock_utilities
    operations = managemant_and_data_operations + installation_operations + openclaw_operations
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
                openclaw                                    OpenClaw AI assistant
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

              - Configuration:
                manual-configuration no_auto_config         Override automatic configuration

            environment arguments:
              private public                                self-hosted network options

            operation arguments:
              update install                                installation options
              stop stop-llama start pause unpause           operation options
              backup-data restore-data                      volume mount data options
              clawdock-help clawdock-<command>              OpenClaw operations, access, maintenance and utilities

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

            - Install functional modules OpenClaw, n8n and OpenCode...
              ...with {llama} running on the Host:
              python {file} --profile openclaw, n8n opencode

              ...with Ollama CPU running in Docker:
              python {file} --profile openclaw, n8n opencode cpu

              ...with LLaMA.cpp AMD GPU in Docker and on production environment:
              python {file} --profile openclaw, n8n opencode cpp-gpu-amd --environment public

            - Perform (stop, start, pause, unpause) operation...
              ...to stop n8n and opencode:
              python {file} --profile openclaw, n8n opencode --operation stop

              ...to stop n8n, opencode and {llama} running on the Host:
              python {file} --profile openclaw, n8n opencode --operation stop-llama

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

            - Perform OpenClaw clawdock operation...
              ...to show all available clawdock commands with examples
              python {file} --operation clawdock-help
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
                        help='Docker container, volumes and image management arguments along with argument to stop'
                              f'{llama} running on Host and OpenClaw clawdock arguments.')
    parser.add_argument('-l', '--log', type=str.upper, choices=log_levels, default='INFO',
                        help='Enable stream (console) logging and set log level. File logging is always '
                             'enabled at DEBUG and is not affected by this argument (default: INFO)')

    args = parser.parse_args()

    # Detect default profile - no arguments specified
    default_profile = False if args.profile else True
    args.profile = [] if default_profile else args.profile

    # Setup logging
    global log, log_level, log_bright, log_run_cmd
    log_level = logging.NOTSET
    log_bright = None
    log_run_cmd = "Running command:"
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

    # Install missing tools
    prompt_store = {'p':True} # Set False to bypass auto-configure prompts when debugging etc...
    install_tools = False
    if prompt_store['p']:
        if missing_tools:
            msg = f"Install missing tools? y/n: (n)"
            install_tools = True if input(msg).strip().lower() == "y" else False
    if install_tools:
        log.info("Installing required tools before continuing...")
        if 'Python' in missing_tools:
            if os.getenv("DEBUG_PY"):
                log.warning("Debug mode detected - update Python skipped.")
            else:
                log.info(f"Updating Python...")
                python_ensure_compatible_version()
                me = os.path.basename(sys.argv[0])
                log.info(f"Running {me} with compatible Python version.", extra=log_bright)
                missing_tools.remove('Python')
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
    ac_auto_config = not any(p for p in args.profile if p in auto_config_profiles)
    env_vars = get_dotenv_vars(auto_config=ac_auto_config, profile=args.profile)
    if not env_vars:
        log.critical("No environment variables detected")
        sys.exit(1)

    # Set build (update, install) status
    build = args.operation in ['update', 'install']

    # Setup Supabase repository if using Supabase
    if any(p for p in args.profile if p == 'supabase'):
        if not any(p for p in args.profile if p in n8n_all_profiles):
            log.warning("Profile argument 'supabase' requires argument in "
                       f"{n8n_all_profiles} - removing 'supabase'...")
            args.profile.remove('supabase')
    supabase = \
        any(p for p in args.profile if p in ['supabase', 'ai-all'])
    if supabase:
        mod_env_vars.update({'POSTGRES_HOST': 'db'})
        if build:
            clone_supabase_repo()
        copy_supabase_authelia_schema()
        convert_supabase_pooler_line_endings()

    # Setup OpenClaw repository if using OpenClaw
    openclaw = \
        any(p for p in args.profile if p in ['openclaw', 'ai-all'])
    oc_cwd = None
    oc_store = {}
    oc_release = None
    if openclaw:
        oc_env_vars = {
            "OPENCLAW_RELEASE": "commit",
            "OPENCLAW_ONBOARDING": "0",
            "OPENCLAW_DOCKER_SANDBOX": "1",
            "OPENCLAW_DOCKER_LOCAL_IMAGE": "1",
            "OPENCLAW_KEEP_LOCAL_UPDATES": "0"
        }
        for key, var in oc_env_vars.items():
            if key not in env_vars or env_vars[key] in (None, ""):
                env_vars[key] = var
                set_dotenv_var(env_file, key, var, None)
        oc_store = {
            "onboard": env_vars["OPENCLAW_ONBOARDING"] == "1",
            "sandbox": env_vars["OPENCLAW_DOCKER_SANDBOX"] == "1",
            "local-image": env_vars["OPENCLAW_DOCKER_LOCAL_IMAGE"] == "1"
        }
        oc_release = {
            "release": env_vars["OPENCLAW_RELEASE"],
            "preserve": env_vars["OPENCLAW_KEEP_LOCAL_UPDATES"] == "1"
        }
        if build:
            clone_openclaw_repo(oc_release)

    # Setup Open WebUI Functions and Tools Filesystem repository
    open_webui = \
        any(p for p in args.profile if p in open_webui_all_profiles)

    # Automatic configuration
    ac_env_vars = []
    if ac_auto_config:
        accepted = True
        rejected = False
        response = None
        replay = False
        attempt = 1
        max_attempts = 3
        ac_env_vars = setup_ai_suite_ac_auto_config(prompt_store, oc_store, env_vars)
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
                    ac_env_vars = setup_ai_suite_ac_auto_config(prompt_store, oc_store, env_vars)
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
    base_dir = pathlib.Path(__file__).parent
    if openclaw:
        oc_cwd = os.path.join(base_dir, "openclaw")
        prepare_openclaw_env(args.environment, oc_store, oc_cwd)
    if ac_auto_config:
        log.info("Configure proxy, identity and access management...")
        # AC_SUDO_PASSWORD - stdin
        sudo_password = None
        if not is_root_user():
            msg = "Enter sudo password for elevated tasks or skip for prompt: "
            sudo_password = getpass.getpass(msg)
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
                    user_database = os.path.join("access", "authelia", "db", "users_database.yml")
                    os.remove(user_database) if os.path.exists(user_database) else None
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
        # OpenClaw sandbox and build local image
        if openclaw and (oc_store['sandbox'] or oc_store['local-image']):
            ac_env_vars.append(f'AC_OPENCLAW_LOCAL_IMAGE={str(True).lower()}')
        # Miscellaneous environment variables
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
        elif args.operation in openclaw_operations:
            operate_openclaw(args.operation, args.environment, oc_store, oc_cwd)
            sys.exit(0)
        elif args.operation in data_operations:
            docker_volume_data(args.operation)
            sys.exit(0)
        if default_profile:
            args.profile = ['ai-all']
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
            docker_compose_include(supabase, openclaw, open_webui, False)
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

    # Setup OpenClaw configuration
    if openclaw:
        prepare_openclaw_config(oc_cwd, env_vars)

    # Setup Open WebUI Functions and Tools Filesystem repos
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
    docker_compose_include(supabase, openclaw, open_webui, True)

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
        wait_with_progress(5)

    # Start OpenClaw
    if openclaw:
        start_openclaw(args.environment, build, oc_cwd)
        # Give OpenClaw some time to initialize
        log.info("Waiting for OpenClaw to initialize...", extra=log_bright)
        wait_with_progress(5)

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
    display_service_endpoints(args.profile, supabase, openclaw, env_vars)

    os.makedirs('./state', exist_ok=True)
    with open('./state/.operation', 'w', newline='\n') as f:
        f.write('start' + ':' + llama.lower())

if __name__ == "__main__":
    main()
