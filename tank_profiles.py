"""
Tank Volume Profiles
Lookup tables for non-linear tank capacity calculations

Copyright (C) 2025
SPDX-License-Identifier: GPL-3.0-or-later
"""

# 275 Gallon Vertical Oil Tank (Oval/Obround)
# Dimensions: 60" length × 27" width × 44" height
# Data source: https://www.fuelsnap.com/heating_oil_tank_charts.php
#
# This data accounts for the oval cross-section where capacity per inch
# varies due to curved top and bottom sections.

TANK_275_VERTICAL_OVAL = {
    'name': '275 Gallon Vertical Oval',
    'capacity_gallons': 275,
    'height_inches': 44,
    'width_inches': 27,
    'length_inches': 60,
    # Lookup table: depth in inches -> gallons
    'depth_inches': [
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
        11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
        21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
        31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
        41, 42, 43, 44
    ],
    'gallons': [
        2, 5, 9, 14, 19, 25, 31, 37, 44, 51,
        58, 65, 72, 80, 87, 94, 101, 108, 115, 123,
        130, 137, 144, 151, 158, 166, 173, 180, 187, 194,
        201, 209, 216, 223, 230, 236, 243, 249, 254, 260,
        265, 269, 272, 275
    ]
}


def linear_interpolate(x, x0, x1, y0, y1):
    """
    Linear interpolation between two points

    Args:
        x: Input value to interpolate
        x0: Lower bound x value
        x1: Upper bound x value
        y0: Lower bound y value
        y1: Upper bound y value

    Returns:
        float: Interpolated y value
    """
    if x1 == x0:
        return y0
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def depth_to_gallons(depth_inches, tank_profile):
    """
    Convert liquid depth to gallons using lookup table with interpolation

    Args:
        depth_inches: Measured depth of liquid in inches
        tank_profile: Tank profile dictionary with depth_inches and gallons arrays

    Returns:
        float: Volume in gallons, or None if depth is invalid
    """
    depth_table = tank_profile['depth_inches']
    gallons_table = tank_profile['gallons']

    # Validate depth range
    if depth_inches <= 0:
        return 0.0
    if depth_inches >= depth_table[-1]:
        return float(gallons_table[-1])

    # Find the two points to interpolate between
    for i in range(len(depth_table) - 1):
        if depth_inches >= depth_table[i] and depth_inches <= depth_table[i + 1]:
            # Linear interpolation between these two points
            return linear_interpolate(
                depth_inches,
                depth_table[i], depth_table[i + 1],
                gallons_table[i], gallons_table[i + 1]
            )

    # Should never reach here if depth is validated
    return None


def gallons_to_depth(gallons, tank_profile):
    """
    Convert gallons to depth using lookup table with interpolation
    (Reverse calculation - useful for testing/calibration)

    Args:
        gallons: Volume in gallons
        tank_profile: Tank profile dictionary with depth_inches and gallons arrays

    Returns:
        float: Depth in inches, or None if gallons is invalid
    """
    depth_table = tank_profile['depth_inches']
    gallons_table = tank_profile['gallons']

    # Validate gallons range
    if gallons <= 0:
        return 0.0
    if gallons >= gallons_table[-1]:
        return float(depth_table[-1])

    # Find the two points to interpolate between
    for i in range(len(gallons_table) - 1):
        if gallons >= gallons_table[i] and gallons <= gallons_table[i + 1]:
            # Linear interpolation between these two points
            return linear_interpolate(
                gallons,
                gallons_table[i], gallons_table[i + 1],
                depth_table[i], depth_table[i + 1]
            )

    # Should never reach here if gallons is validated
    return None


# Available tank profiles
TANK_PROFILES = {
    '275_vertical_oval': TANK_275_VERTICAL_OVAL,
    # Can add more tank types here in the future:
    # '330_horizontal': TANK_330_HORIZONTAL,
    # '550_vertical': TANK_550_VERTICAL,
}


def get_tank_profile(profile_name):
    """
    Get tank profile by name

    Args:
        profile_name: Name of tank profile (e.g., '275_vertical_oval')

    Returns:
        dict: Tank profile dictionary, or None if not found
    """
    return TANK_PROFILES.get(profile_name)


# Test function
def test_interpolation():
    """Test the interpolation function with known values"""
    profile = TANK_275_VERTICAL_OVAL

    print("Testing 275 Gallon Vertical Oval Tank Profile")
    print("=" * 50)

    # Test exact values from table
    test_depths = [1, 10, 22, 44]
    expected = [2, 51, 137, 275]

    print("\nExact value tests:")
    for depth, exp in zip(test_depths, expected):
        result = depth_to_gallons(depth, profile)
        status = "PASS" if result == exp else "FAIL"
        print("  {}\" -> {} gallons (expected {}) {}".format(depth, result, exp, status))

    # Test interpolated values
    print("\nInterpolation tests:")
    test_cases = [
        (1.5, 3.5),   # Between 1" (2gal) and 2" (5gal)
        (22.5, 140.5), # Between 22" (137gal) and 23" (144gal)
        (43.5, 273.5), # Between 43" (272gal) and 44" (275gal)
    ]

    for depth, expected_approx in test_cases:
        result = depth_to_gallons(depth, profile)
        print("  {}\" -> {:.1f} gallons (expected ~{:.1f})".format(
            depth, result, expected_approx))

    # Test edge cases
    print("\nEdge case tests:")
    print("  0\" -> {} gallons".format(depth_to_gallons(0, profile)))
    print("  50\" (overflow) -> {} gallons".format(depth_to_gallons(50, profile)))

    # Test reverse calculation
    print("\nReverse calculation tests:")
    test_gallons = [50, 137, 250]
    for gal in test_gallons:
        depth = gallons_to_depth(gal, profile)
        print("  {} gallons -> {:.1f}\"".format(gal, depth))


if __name__ == "__main__":
    test_interpolation()
