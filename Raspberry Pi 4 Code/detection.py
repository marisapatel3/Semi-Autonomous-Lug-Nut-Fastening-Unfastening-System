#!/usr/bin/env python3
"""
detection.py

Detection Script for Camera Vision and Detection System

This script handles detecting the center coordinates of the bolt faces in the captured image, and converting those coordinates from pixels to real-world measurements in mm

This script:
1. Load the latest captured image
2. Convert the image to grayscale
3. Applies Gaussian Blur the image to reduce noise
4. Threshold the image to isolate dark regions
5. Find contours of the dark regions
6. Filter contours by size and circularity so only bolt-like shapes remain
7. Compute the center of each detected bolt
8. Convert pixel coordinates into real-world millimeter coordinates
9. Save outputs:
   - JSON file
   - TXT file
   - Debug image
"""

import cv2
import numpy as np
import sys
import json
import math

# -------------------------------------------------------------------------
# File Paths for input and outputs
# -------------------------------------------------------------------------
LATEST_IMAGE_PATH = "/home/may-pi/capstoneS12_cameravision/latest_capture.jpg"  # Input image captured by camera_capture.py
OUTPUT_JSON_PATH = "/home/may-pi/capstoneS12_cameravision/lug_coordinates.json" # Output .json file with both pixel and real-world coordinates
OUTPUT_TXT_PATH = "/home/may-pi/capstoneS12_cameravision/lug_coordinates.txt"   # Output .txt file with real-world coordinates
DEBUG_IMAGE_PATH = "/home/may-pi/capstoneS12_cameravision/debug_detection.jpg"  # Debug image

# -------------------------------------------------------------------------
# Actual Diameter of the bolt face in mm
# -------------------------------------------------------------------------
BOLT_DIAMETER_MM = 5.0

# -------------------------------------------------------------------------
# Detection parameters
# -------------------------------------------------------------------------
MIN_AREA = 80         # Minimum contour area (to avoid small noise)
MAX_AREA = 3000       # Maximum contour area (to avoid holes, shadows, other large noise)
MIN_CIRCULARITY = 0.6 # Minimum circularity - how close to a perfect circle (to ensure contour is roughly circular, like a bolt face)

# -------------------------------------------------------------------------
# Function to loads the OpenCV image
# -------------------------------------------------------------------------
def load_image(path):
    print(f"Loading image from: {path}.")
    image = cv2.imread(path) # Reads image from this path

    if image is None:
        print("[ERROR] Failed to load image.")
        return None

    print(f"[OK] Image loaded ({image.shape[1]}x{image.shape[0]}).")
    return image

# -------------------------------------------------------------------------
# Function to preprocess image before detection begins
# -------------------------------------------------------------------------
def preprocess(image):
    """
    Convert to grayscale and apply Gaussianblur
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0) # Uses 7x7 kernel for blurring
    return gray, blurred

# -------------------------------------------------------------------------
# Function to detect black bolt surfaces using contour detection
# -------------------------------------------------------------------------
def detect_black_circles(gray, blurred):
    """
    Detect matte black regions using thresholding + contours
    Dark bolt faces = low grayscale values
    Use thresholding to isolate dark regions (inverted binary threshold - dark areas become white, rest becomes black)
    Finds contours of the white regions and filters by area, circularity, and radius

    Returns: List of detected bolt candidates, and the debug image
    """

    print("Detecting bolt faces...")
    # -------------------------------------------------------------------------
    # THRESHOLDING
    # -------------------------------------------------------------------------
    # Threshold (val = 100) to isolate DARK regions (black bolt faces), using inverted binary thresholding
    # Pixels darker than 100 become white (255), pixels brighter than 100 become black (0)
    _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY_INV)

    # -------------------------------------------------------------------------
    # NOISE REMOVAL
    # -------------------------------------------------------------------------
    # Remove noise using morphological opening (erosion followed by dilation) using 3x3 kernel
    kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

    # -------------------------------------------------------------------------
    # CONTOUR DETECTION
    # -------------------------------------------------------------------------
    # Find contours in the thresholded image
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bolt_candidates = [] # Storing the contours that pass all bolt filters (area, circularity, radius)

    # Loop through contours and filter by area, circularity, and radius to find bolt candidates
    for cnt in contours:
        area = cv2.contourArea(cnt) # Calculating area of contour

        if area < MIN_AREA or area > MAX_AREA: # Rejecting contours too small or large
            continue

        perimeter = cv2.arcLength(cnt, True) # Calculating perimeter
        if perimeter == 0:
            continue

        circularity = 4 * math.pi * area / (perimeter * perimeter) # Calculating circularity (how close to a perfect circle)

        if circularity < MIN_CIRCULARITY: # Rejecting contours that are not circular enough to be bolt faces
            continue

        # -------------------------------------------------------------------------
        # CENTER CALCULATION USING IMAGE MOMENTS
        # -------------------------------------------------------------------------
        # Getting centroid of contour using image moments
        M = cv2.moments(cnt)
        if M["m00"] == 0: # Skip if area is 0
            continue

        cx = int(M["m10"] / M["m00"]) # Calculating x coordinate of center
        cy = int(M["m01"] / M["m00"]) # Calculating y coordinate of center

        radius = int(math.sqrt(area / math.pi)) # Estimating radius of the bolt face based on area (assuming circular shape)

        if radius < 4 or radius > 40: # Rejecting contours that are too small or large to be bolt faces based on radius
            continue

        # If contour passed all filters, add to bolt candidates list
        bolt_candidates.append({
            "x": cx,
            "y": cy,
            "r": radius
        })

    print(f"[OK] Found {len(bolt_candidates)} bolt(s).")
    return bolt_candidates, thresh

# -------------------------------------------------------------------------
# Function to merge duplicate detections of same bolt
# -------------------------------------------------------------------------
def merge_duplicates(circles):
    if not circles: # If no circles detected, return empty list
        return []

    kept = [] # List of circles that are kept after merging duplicates

    for c in circles: # Comparing each circle with the circles already in the kept list
        duplicate = False

        for k in kept:
            dist = math.hypot(c["x"] - k["x"], c["y"] - k["y"]) # Calculating distance between centers of the two circles
            if dist < max(c["r"], k["r"]): # If distance is less than the larger radius, they are likely duplicates of the same bolt
                duplicate = True
                break

        if not duplicate: # If circle is not a duplicate of any already in the kept list, add it to the kept list
            kept.append(c)

    return kept

# -------------------------------------------------------------------------
# Function to convert from pixels to real-world millimeter coordinates
# -------------------------------------------------------------------------
def convert_to_mm(circles):
    '''
    Estimates the average bolt diameter in pixels using:
    pixels_per_mm = average_pixel_diameter / real_bolt_diameter_mm
    Uses this scale to convert to mm
    Origin (0,0) is set to the average center of all detected bolts
    Positive x = to the right, Positive y = upward

    Returns:
    coords_px      = list of pixel coordinates
    coords_mm      = list of real-world coordinates in mm
    pixels_per_mm  = conversion factor
    origin         = pixel coordinate of the origin
    '''
    coords_px = [(c["x"], c["y"]) for c in circles] # List of pixel coordinates in (x, y)

    radii = [c["r"] for c in circles] # Extracts all radii and calculates average bolt diameter in pixels
    avg_diameter_px = np.mean([2 * r for r in radii])

    pixels_per_mm = avg_diameter_px / BOLT_DIAMETER_MM # Calculation of conversion of Pixels per mm

    origin_x = np.mean([p[0] for p in coords_px]) # Defining origin as center of the detected bolts
    origin_y = np.mean([p[1] for p in coords_px])

    coords_mm = [] # Storing mm coordinates in this list

    for x, y in coords_px: # Converting from pixel coordinates to mm coordinates
        x_mm = (x - origin_x) / pixels_per_mm
        y_mm = (origin_y - y) / pixels_per_mm
        coords_mm.append((round(x_mm, 2), round(y_mm, 2)))

    return coords_px, coords_mm, pixels_per_mm, (origin_x, origin_y)

# -------------------------------------------------------------------------
# Function to save outputs in JSON file and TXT file
# -------------------------------------------------------------------------
def save_outputs(coords_px, coords_mm):
    # JSON File: Stores pixel and mm coordinates
    data = []
    for i, ((x_px, y_px), (x_mm, y_mm)) in enumerate(zip(coords_px, coords_mm)):
        data.append({
            "pixel": [x_px, y_px],
            "mm": [x_mm, y_mm]
        })

    with open(OUTPUT_JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)

    # TXT File: Stores only mm coordinates
    with open(OUTPUT_TXT_PATH, "w") as f:
        for x_mm, y_mm in coords_mm:
            f.write(f"{int(x_mm*100)} {int(y_mm*100)}\n")

    print(f"[OK] Saved TXT File: {OUTPUT_TXT_PATH}.")

# -------------------------------------------------------------------------
# Function to create a debug image
# -------------------------------------------------------------------------
def draw_debug(image, circles, origin):
    '''
    Shows detected bolts as green circles, bolt centers as green dots, origin as blue dot
    '''
    debug = image.copy()

    for c in circles:
        cv2.circle(debug, (c["x"], c["y"]), c["r"], (0, 255, 0), 2) # Detected bolt contours as green circles
        cv2.circle(debug, (c["x"], c["y"]), 3, (0, 255, 0), -1) # Center of bolt as green dot

    ox, oy = int(origin[0]), int(origin[1])
    cv2.circle(debug, (ox, oy), 5, (255, 0, 0), -1) # Origin as blue dot

    cv2.imwrite(DEBUG_IMAGE_PATH, debug) # Saving debug image to this path
    print(f"[OK] Saved debug image.")

# -------------------------------------------------------------------------
# Function for running the complete detection process
# -------------------------------------------------------------------------
def run():
    """
    Run the complete detection process.

    1. Load the latest captured image
    2. Preprocess the image
    3. Detect dark circular bolt faces
    4. Merge duplicate detections
    5. Convert detected centers from pixels to millimeters
    6. Save output files
    7. Save a debug image
    8. Print the final detected coordinates

    Returns: True if detection succeeded, False if detection failed
    """

    print("\n=== BOLT DETECTION ===\n")

    # Step 1: Load the latest captured image
    image = load_image(LATEST_IMAGE_PATH)
    if image is None:
        return False

    # Step 2: Preprocess the image (grayscale + blur)
    gray, blurred = preprocess(image)

    # Step 3: Detect dark circular bolt faces using thresholding and contour detection
    circles, thresh = detect_black_circles(gray, blurred)

    # Step 4: Merge duplicate detections of the same bolt
    circles = merge_duplicates(circles)

    # Stop if no bolts detected
    if len(circles) == 0:
        print("[ERROR] No bolts detected")
        return False

    # Step 5: Convert from pixels to mm coordinates
    coords_px, coords_mm, ppm, origin = convert_to_mm(circles)

    # Step 6: Save outputs in JSON and TXT files
    save_outputs(coords_px, coords_mm)

    # Step 7: Save a debug image
    draw_debug(image, circles, origin)

    # Step 8: Print the final detected coordinates
    print("\nDetected bolt coordinates:")
    for (px, py), (mx, my) in zip(coords_px, coords_mm):
        print(f"pixel=({px},{py})  real=({mx},{my})")

    return True

# -------------------------------------------------------------------------
# Main function to run if this script is executed directly
# -------------------------------------------------------------------------
if __name__ == "__main__":
    success = run()
    '''
    Exit codes:
    Returns 0 if successful
    Returns 1 if failure
    '''
    sys.exit(0 if success else 1)