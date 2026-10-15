# Windows Spotlight Overrider & Archiver

## Overview
A brute-force workaround for when Windows Spotlight gets stuck and stops updating, and standard fixes (PowerShell resets, registry tweaks) no longer help. Instead of relying on the Spotlight APIs, this script fetches the Bing Daily Image directly, archives it locally, overwrites the lock screen cache, and forces an immediate visual refresh.

Tested on Windows 10. 

## Features
- **Aggressive cache replacement**: Windows sometimes creates multiple or new `LockScreen_*` folders inside the hidden `SystemData` path. This script iterates through all of them and overwrites every cached image, so the update applies regardless of how Windows shuffles the folder structure.
- **Local archiving**: Downloaded images are saved to a user-specified directory, giving you full control over which daily wallpapers to keep.
- **Instant visual refresh**: Terminates `LockApp.exe` after the cache update so that the next Win + L shows the new image immediately.
- **Robust error handling**: Uses native `curl.exe` with retries, timeouts, and automatic DNS flushing (`ipconfig /flushdns`) to recover from transient network errors before failing.

## Setup & Configuration

Before scheduling, open `WindowsSpotlight.py` and configure the following paths:

1. **`DOWNLOAD_DIR`**: The local directory where Bing images and logs will be saved.
2. **`READONLY_DIR`**: The path to your Windows lock screen cache. 
   - *Note: You must replace the SID (`S-1-5-21-...`) in the path with your local machine's actual user SID.*
   - Example: `C:\ProgramData\Microsoft\Windows\SystemData\<YOUR_USER_SID>\ReadOnly`

## Task Scheduler Configuration Guide

Because the script modifies protected system directories (`SystemData`), it must run via **Windows Task Scheduler** with the highest privileges.

Follow the screenshots below to configure the task exactly as required:

### 1. General & Triggers
Ensure the task runs under the `SYSTEM` account with the highest privileges. Set triggers to run both on a daily schedule and upon workstation unlock.
![General Settings](assets/2.png)
![Triggers Overview](assets/3.png)
![Schedule Trigger](assets/4.png)
![Unlock Trigger](assets/5.png)

### 2. Actions
Set the action to start a program. 
- **Program/script**: Enter the path to your Python executable (e.g., `pythonw.exe` for silent execution without a console window).
- **Add arguments**: Enter the absolute path to your `WindowsSpotlight.py` script. *Make sure to enclose the path in double quotes `""` if it contains spaces.*
![Actions Overview](assets/7.png)
![Edit Action](assets/6.png)

### 3. Conditions & Settings
Ensure the task only runs when a network connection is available, and configure it to retry aggressively (e.g., every 1 minute up to 60 times) if the initial API call fails due to a temporary network drop upon boot.
![Conditions](assets/8.png)
![Settings](assets/9.png)

## Local Archive Result
Once running, the script will silently populate your chosen `DOWNLOAD_DIR` with high-resolution daily images, allowing you to manage your own lock screen gallery.
![Local Archive Folder](assets/1.png)