#!/usr/bin/env python3
"""
system_check.py

System Check Script for Camera Vision and Detection System

This script verifies that the full camera vision system is ready before image is captured or detection is attempted

The script checks that:
1. The Raspberry Pi hotspot is running
2. The ESP32-CAM is connected to the Pi's hotspot
3. The ESP32-CAM web server is responding
4. The laptop is also connected to the Pi's hotspot

If any of these is not connected properly, the rest of the system will fail
This script is used as a quick pre-check before running the system
"""

import subprocess
import sys
import time

# -------------------------------------------------------------------------
# Network Configuration: IP Addresses and MAC address
# -------------------------------------------------------------------------
PI_HOTSPOT_SSID = "S12pi4net"  # Name of the Pi's WiFi hotspot
PI_HOTSPOT_IP = "10.42.0.1"    # Pi's hotspot IP address
ESP32_IP = "10.42.0.149"       # ESP32-CAM IP address
ESP32_MAC = "f8:b3:b7:a7:dd:d8"

# -------------------------------------------------------------------------
# Printing a pass or fail message for each check
# -------------------------------------------------------------------------
def print_status(message, status):
    """
        Message: Description of what is being checked
        Status: True for success, False for failure
    """
    status_text = "[OK]" if status else "[FAIL]"
    print(f"{status_text} {message}")
    return status

# -------------------------------------------------------------------------
# Checking if the Pi's WiFi hotspot is active
# -------------------------------------------------------------------------
def check_hotspot_running():
    """
    Returns: True if hotspot is running, False otherwise
    """
    try:
        # Use command "nmcli device status"  to check if wlan0 (Pi's wifi interface) is in hotspot mode
        result = subprocess.run(
            ['nmcli', 'device', 'status'],
            capture_output=True,
            text=True,
            check=True
        )

        # Check if wlan0 shows as connected with Hotspot connection
        # Checking if 'wlan0' and 'Hotspot' is in the output for that line
        if 'wlan0' in result.stdout and 'Hotspot' in result.stdout:
            return print_status(f"Pi hotspot '{PI_HOTSPOT_SSID}' is running!", True)
        else:
            return print_status(f"Pi hotspot '{PI_HOTSPOT_SSID}' is NOT running.", False)

    except subprocess.CalledProcessError as e:
        # If the nmcli command fails, we assume hotspot is not running
        return print_status(f"Error checking hotspot status: {e}.", False)

# -------------------------------------------------------------------------
# Checking if ESP32-CAM is connected to the Pi's hotspot
# -------------------------------------------------------------------------
def check_esp32_connected():
    """
    Uses nmap to scan the hotspot network
    Returns: True if ESP32-CAM is found at expected IP, False otherwise
    """
    try:
        # Use command "sudo nmap -sn 10.42.0.0/24" to scan the hotspot network for connected devices
        result = subprocess.run(
            ['sudo', 'nmap', '-sn', '10.42.0.0/24'],
            capture_output=True,
            text=True,
            check=True
        )

        # Check if ESP32-CAM's IP address appears in scan results
        if ESP32_IP in result.stdout:
            return print_status(f"ESP32-CAM found at {ESP32_IP}!", True)
        else:
            return print_status(f"ESP32-CAM NOT found at {ESP32_IP}.", False)

    except subprocess.CalledProcessError as e:
        # If the nmap command fails, we assume ESP32 is not connected
        return print_status(f"Error scanning network: {e}", False)

# -------------------------------------------------------------------------
# Checking if ESP32-CAM's web server is responding
# -------------------------------------------------------------------------
def check_esp32_webserver():
    """
    Uses curl to test HTTP connection
    Returns: True if web server responds, False otherwise
    """
    try:
        # Use command "curl http://10.42.0.149" to try to connect to ESP32-CAM's web server with 5 second timeout
        # Opens the web server's root webpage, discards the webpage content, and checks the HTTP response code (should be 200)
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
             '--connect-timeout', '5', f'http://{ESP32_IP}'],
            capture_output=True,
            text=True,
            check=False
        )

        # Check if we got HTTP 200 response
        if result.stdout.strip() == '200':
            return print_status(f"ESP32-CAM web server is responding!", True)
        else:
            return print_status(f"ESP32-CAM web server is NOT responding (HTTP code: {result.stdout.strip()}).", False)

    except Exception as e:
        # If the curl command fails, we assume web server is not responding
        return print_status(f"Error connecting to ESP32 web server: {e}", False)

# -------------------------------------------------------------------------
# Checking if laptop is connected to the Pi's hotspot
# -------------------------------------------------------------------------
def check_laptop_connected():
    """
    Looks for devices other than ESP32-CAM on the network
    Returns: True if laptop found, False otherwise
    """
    try:
        # Use command "sudo nmap -sn 10.42.0.0/24" to scan the hotspot network again for more connected devices
        result = subprocess.run(
            ['sudo', 'nmap', '-sn', '10.42.0.0/24'],
            capture_output=True,
            text=True,
            check=True
        )

        # Counts how many hosts are up
        # We expect: Pi (10.42.0.1) + ESP32 (10.42.0.149) + Laptop = 3 devices
        host_count = result.stdout.count('Host is up')

        if host_count >= 3:
            return print_status(f"Found {host_count} devices on hotspot (includes laptop)!", True)
        elif host_count == 2:
            return print_status(f"Only 2 devices found (Pi + ESP32, laptop NOT connected).", False)
        else:
            return print_status(f"Only {host_count} device(s) found (something is wrong).", False)

    except subprocess.CalledProcessError as e:
        # If the nmap command fails, we assume laptop is not connected
        return print_status(f"Error checking for laptop connection: {e}.", False)

# -------------------------------------------------------------------------
# Function to run all checks in sequence and return overall result
# -------------------------------------------------------------------------
def run_system_check():
    """
    Run all system checks in sequence
    Returns: True if all critical checks pass, False otherwise
    """
    print("\n" + "="*60)
    print("CAMERA VISION AND DETECTION SYSTEM - SYSTEM CHECK")
    print("="*60 + "\n")

    print("REQUIRED DEVICES: Laptop, Pi, and ESP32-CAM must be connected to Pi's hotspot.\n")
    print("Checking system components...\n")

    # Checks for Pi's hotspot, ESP32-CAM connection, web server, and laptop connection
    check1 = check_hotspot_running()
    time.sleep(0.5)

    check2 = check_esp32_connected()
    time.sleep(0.5)

    check3 = check_esp32_webserver()
    time.sleep(0.5)

    check4 = check_laptop_connected()
    time.sleep(0.5)

    print("\n" + "="*60)

    # ALL checks must pass
    all_passed = check1 and check2 and check3 and check4

    if all_passed:
        print("SYSTEM CHECK PASSED - All devices connected!")
        print("="*60 + "\n")
        return True
    else:
        print("SYSTEM CHECK FAILED - Fix issues above.")
        print("="*60 + "\n")
        return False

# -------------------------------------------------------------------------
# Main function to run if this script is executed directly
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Run the system check function
    success = run_system_check()
    '''
    Exit codes:
    Returns 0 if successful
    Returns 1 if failure
    '''
    sys.exit(0 if success else 1)