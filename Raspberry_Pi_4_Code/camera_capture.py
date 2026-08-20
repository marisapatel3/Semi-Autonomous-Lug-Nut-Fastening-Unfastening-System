#!/usr/bin/env python3
"""
camera_capture.py

Camera Capture Script for Camera Vision and Detection System

This script handles capturing the image that will be used for bolt detection

The script does the following:
1. Sends camera setting commands to the ESP32-CAM
2. Prints the live stream URL for the user to open manually
3. Waits for the user to position the tire hub
4. Captures a still image when the user presses ENTER
5. Saves the captured image to the Raspberry Pi

"""

import requests
import cv2
import numpy as np
import sys
import subprocess
import time
from datetime import datetime

# -------------------------------------------------------------------------
# ESP32-CAM Configuration: IP Address and URLs for stream, capture, and control
# -------------------------------------------------------------------------
ESP32_IP = "10.42.0.149"
ESP32_STREAM_URL = f"http://{ESP32_IP}"          # URL for live stream
ESP32_CAPTURE_URL = f"http://{ESP32_IP}/capture" # URL used to capture a still image
ESP32_CONTROL_URL = f"http://{ESP32_IP}/control" # URL used to send camera setting commands

# -------------------------------------------------------------------------
# Storing Image Captured from ESP32-CAM
# -------------------------------------------------------------------------
IMAGE_SAVE_DIR = "/home/may-pi/capstoneS12_cameravision/captured_images" # Directory to save all captured images with timestamps
LATEST_IMAGE_PATH = "/home/may-pi/capstoneS12_cameravision/latest_capture.jpg" # Path to save the latest captured image (overwritten each time)

# -------------------------------------------------------------------------
# Desired Camera Settings to be sent to the ESP32-CAM
# -------------------------------------------------------------------------
# These will be applied every time script runs
CAMERA_SETTINGS = {
    'framesize': 9,      # Image resolution: UXGA (1600x1200)
    'quality': 8,        # JPEG quality (lower is better)
    'brightness': -1,    # Brightness range: -2 to 2
    'contrast': 1,       # Contrast range: -2 to 2
    'saturation': 0,     # Saturation range: -2 to 2
    'aec': 1,            # Auto exposure control ON
    'aec2': 1,           # Secondary auto exposure control ON
    'ae_level': 0,       # Auto exposure level
    'agc': 1,            # Auto gain control ON
    'awb': 1,            # Auto white balance ON
    'awb_gain': 1,       # Auto white balance gain ON
    'wb_mode': 0,        # White balance mode (0=auto)
    'dcw': 0,            # Downsize enable OFF (no downsampling)
    'bpc': 1,            # Black pixel correction ON
    'wpc': 1,            # White pixel correction ON
    'raw_gma': 1,        # Raw gamma correction ON
    'lenc': 1,           # Lens correction ON
    'special_effect': 0, # No special effect
    'led_intensity': 160  # LED flash brightness level
}

# -------------------------------------------------------------------------
# Crop settings for cropping the captured image to focus on the tire hub area
# -------------------------------------------------------------------------
CROP_X1_PERCENT = 0.20 # Crop left 20% of the image
CROP_X2_PERCENT = 0.80 # Crop right 80% of the image
CROP_Y1_PERCENT = 0.10 # Crop top 10% of the image
CROP_Y2_PERCENT = 0.90 # Crop bottom 90% of the image

# -------------------------------------------------------------------------
# Sending the Camera Settings to the ESP32-CAM via HTTP control commands
# Configuring the ESP32-CAM with new settings
# -------------------------------------------------------------------------
def configure_camera_settings():
    """
    The ESP32-CAM web server accepts camera setting changes through HTTP URLs
    in this format: http://ESP32_IP/control?var=SETTING_NAME&val=SETTING_VALUE
    Returns: True if settings applied successfully
    """
    print("Configuring camera settings...")

    try:
        # Loops through each camera setting in CAMERA_SETTINGS
        for setting, value in CAMERA_SETTINGS.items():
            url = f"{ESP32_CONTROL_URL}?var={setting}&val={value}" # Creates URL for each setting
            response = requests.get(url, timeout=5) # Sends the HTTP request to the ESP32-CAM

            # Printing if each setting was applied successfully based on HTTP response
            if response.status_code != 200:
                print(f"[FAIL] {setting}={value}.")
            else:
                print(f"[OK] {setting}={value}.")

        print("[OK] Camera settings configured!")
        return True

    except Exception as e:
        print(f"[WARNING] Could not configure all settings: {e}.")
        return False

# -------------------------------------------------------------------------
# Function to Open Live Stream Browser Window
# -------------------------------------------------------------------------
def show_stream_instructions():
    """
    Prints the ESP32-CAM live stream URL for the user to open manually
    Returns: Always returns True after printing the instructions
    """
    # The '#stream' part opens the stream view in the ESP32-CAM web interface
    stream_url = f"{ESP32_STREAM_URL}/#stream"

    print("\n" + "=" * 60)
    print("OPEN THIS URL IN YOUR BROWSER:")
    print(f"  {stream_url}")
    print("=" * 60)
    print("Once the browser stream is open, position the tire and return here.\n")

    return True

# -------------------------------------------------------------------------
# Function to Inform to Close Live Stream Browser Window
# -------------------------------------------------------------------------
def show_browser_close_message():
    """
    Prints a reminder that the browser window can now be closed
    Returns: Always returns True
    """
    print("\n" + "=" * 60)
    print("You can now close the browser window.")
    print("=" * 60)
    return True

# -------------------------------------------------------------------------
# Function for Capturing a Still Image from the ESP32-CAM
# -------------------------------------------------------------------------
def capture_image():
    """
    Requests a still image from ESP32-CAM

    This function:
    1. Sends an HTTP request to the /capture endpoint
    2. Receives the raw JPEG image bytes
    3. Converts the bytes into a NumPy array
    4. Decodes the NumPy array into an OpenCV image

Returns: numpy.ndarray or none:
            Returns the decoded OpenCV image if successful, otherwise returns None
    """
    try:
        print(f"Capturing image from {ESP32_CAPTURE_URL}...")

        response = requests.get(ESP32_CAPTURE_URL, timeout=10) # Requests a still image

        if response.status_code == 200: # Continues if capture was successful
            image_array = np.frombuffer(response.content, dtype=np.uint8) # Converts image's raw bytes to NumPy array
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR) # Decodes the NumPy array into an OpenCV image

            if image is not None: # Checks if decoding was successful

                # Cropping image
                h, w = image.shape[:2]

                x1 = int(w * CROP_X1_PERCENT)
                x2 = int(w * CROP_X2_PERCENT)
                y1 = int(h * CROP_Y1_PERCENT)
                y2 = int(h * CROP_Y2_PERCENT)

                image = image[y1:y2, x1:x2]
                height, width = image.shape[:2]
                print(f"[OK] Captured and cropped to {width}x{height} image.")
                return image
            else:
                print("[FAIL] Could not decode image.")
                return None
        else:
            print(f"[FAIL] Capture failed (HTTP {response.status_code}).")
            return None

    except Exception as e:
        print(f"[FAIL] Error: {e}.")
        return None

# -------------------------------------------------------------------------
# Function for Saving the Captured Image to Pi's Disk
# -------------------------------------------------------------------------
def save_image(image):
    """
    Saves captured image to image directory folder and saves as latest image, latest_capture.jpg
    Returns: str: Path to saved image, or None if failed
    """
    try:
        import os
        os.makedirs(IMAGE_SAVE_DIR, exist_ok=True) # Creates image directory if not already exists

        # Saves image with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamped_path = f"{IMAGE_SAVE_DIR}/capture_{timestamp}.jpg"
        cv2.imwrite(timestamped_path, image)
        print(f"[OK] Saved: {timestamped_path}.")

        # Save as latest image (overwrites each time)
        cv2.imwrite(LATEST_IMAGE_PATH, image)
        print(f"[OK] Saved: {LATEST_IMAGE_PATH}.")

        return LATEST_IMAGE_PATH

    except Exception as e:
        print(f"[FAIL] Could not save: {e}.")
        return None

# -------------------------------------------------------------------------
# Function for running the complete capture process
# -------------------------------------------------------------------------
def run_capture():
    """
    Run the complete capture process.

    1. Print user instructions
    2. Configure the ESP32-CAM settings
    3. Print the browser stream URL
    4. Wait for the user to position the tire and press ENTER
    5. Capture the image
    6. Save the image
    7. Remind the user that the browser can now be closed

    Returns: str: Path to captured image, or None if failed
    """
    print("\n" + "="*60)
    print("ESP32-CAM IMAGE CAPTURE")
    print("="*60 + "\n")

    # Step 1: Configure camera settings
    configure_camera_settings()
    time.sleep(5)

    # Step 2: Show the live stream URL for manual opening
    show_stream_instructions()
    time.sleep(5)

    # Step 3: Wait for user to position tire
    print("\n" + "="*60)
    print("Instructions:")
    print("1. Open the live stream in your browser")
    print("2. Position the tire in front of the camera")
    print("3. Press ENTER in this terminal to capture")
    print("="*60 + "\n")

    input("Press ENTER when ready to capture (or Ctrl+C to cancel): ") # Waits for user to press ENTER to proceed

    # Step 4: Capture image
    print("\nCapturing...")
    image = capture_image()

    if image is None:
        print("\n[ERROR] Capture failed")
        show_browser_close_message()
        return None

    # Step 5: Save image
    saved_path = save_image(image)

    # Step 6: Close browser
    show_browser_close_message()

    # Final result
    if saved_path:
        print("\n" + "="*60)
        print("CAPTURE SUCCESSFUL!")
        print(f"Image ready: {saved_path}.")
        print("="*60 + "\n")
        return saved_path
    else:
        print("\n[ERROR] Could not save image.")
        return None

# -------------------------------------------------------------------------
# Main function to run if this script is executed directly
# -------------------------------------------------------------------------
if __name__ == "__main__":
    captured_path = run_capture()
    '''
    Exit codes:
    Returns 0 if successful
    Returns 1 if failure
    '''
    sys.exit(0 if captured_path else 1)
