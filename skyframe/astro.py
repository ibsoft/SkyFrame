import math
from datetime import datetime, timezone

EPOCH = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _mod2pi(angle: float) -> float:
    two_pi = 2 * math.pi
    return angle % two_pi


def _true_anomaly(M: float, e: float) -> float:
    E = M + e * math.sin(M) * (1 + e * math.cos(M))
    V = 2 * math.atan(math.sqrt((1 + e) / (1 - e)) * math.tan(0.5 * E))
    if V < 0:
        V += 2 * math.pi
    return V


def _planetary_elements(name: str, c: float) -> tuple[float, float, float, float, float, float]:
    """Return inclination, longitude of ascending node, longitude of perihelion,
    semi-major axis, eccentricity, and mean longitude (all in radians)."""
    switch = {
        "Sun": (
            (0.00005 - 46.94 * c / 3600) * math.pi / 180,
            (-11.26064 - 18228.25 * c / 3600) * math.pi / 180,
            (102.94719 + 1198.28 * c / 3600) * math.pi / 180,
            1.00000011 - 0.00000005 * c,
            0.01671022 - 0.00003804 * c,
            (_mod2pi((100.46435 + 129597740.63 * c / 3600) * math.pi / 180)),
        ),
        "Mercury": (
            (7.00487 - 23.51 * c / 3600) * math.pi / 180,
            (48.33167 - 446.3 * c / 3600) * math.pi / 180,
            (77.45645 + 573.57 * c / 3600) * math.pi / 180,
            0.38709893 + 0.00000066 * c,
            0.20563069 + 0.00002527 * c,
            _mod2pi((252.25084 + 538101628.29 * c / 3600) * math.pi / 180),
        ),
        "Venus": (
            (3.39471 - 2.86 * c / 3600) * math.pi / 180,
            (76.68069 - 996.89 * c / 3600) * math.pi / 180,
            (131.53298 - 108.8 * c / 3600) * math.pi / 180,
            0.72333199 + 0.00000092 * c,
            0.00677323 - 0.00004938 * c,
            _mod2pi((181.97973 + 210664136.06 * c / 3600) * math.pi / 180),
        ),
        "Mars": (
            (1.85061 - 25.47 * c / 3600) * math.pi / 180,
            (49.57854 - 1020.19 * c / 3600) * math.pi / 180,
            (336.04084 + 1560.78 * c / 3600) * math.pi / 180,
            1.52366231 - 0.00007221 * c,
            0.09341233 + 0.00011902 * c,
            _mod2pi((355.45332 + 68905103.78 * c / 3600) * math.pi / 180),
        ),
        "Jupiter": (
            (1.30530 - 4.15 * c / 3600) * math.pi / 180,
            (100.55615 + 1217.17 * c / 3600) * math.pi / 180,
            (14.75385 + 839.93 * c / 3600) * math.pi / 180,
            5.20336301 + 0.00060737 * c,
            0.04839266 - 0.00012880 * c,
            _mod2pi((34.40438 + 10925078.35 * c / 3600) * math.pi / 180),
        ),
        "Saturn": (
            (2.48446 + 6.11 * c / 3600) * math.pi / 180,
            (113.71504 - 1591.05 * c / 3600) * math.pi / 180,
            (92.43194 - 1948.89 * c / 3600) * math.pi / 180,
            9.53707032 - 0.00301530 * c,
            0.05415060 - 0.00036762 * c,
            _mod2pi((49.94432 + 4401052.95 * c / 3600) * math.pi / 180),
        ),
        "Uranus": (
            (0.76986 - 2.09 * c / 3600) * math.pi / 180,
            (74.22988 - 1681.40 * c / 3600) * math.pi / 180,
            (170.96424 + 1312.56 * c / 3600) * math.pi / 180,
            19.19126393 + 0.00152025 * c,
            0.04716771 - 0.00019150 * c,
            _mod2pi((313.23218 + 1542547.79 * c / 3600) * math.pi / 180),
        ),
        "Neptune": (
            (1.76917 - 3.64 * c / 3600) * math.pi / 180,
            (131.72169 - 151.25 * c / 3600) * math.pi / 180,
            (44.97135 - 844.43 * c / 3600) * math.pi / 180,
            30.06896348 - 0.00125196 * c,
            0.00858587 + 0.00002510 * c,
            _mod2pi((304.88003 + 786449.21 * c / 3600) * math.pi / 180),
        ),
        "Pluto": (
            (17.14175 + 11.07 * c / 3600) * math.pi / 180,
            (110.30347 - 37.33 * c / 3600) * math.pi / 180,
            (224.06676 - 132.25 * c / 3600) * math.pi / 180,
            39.48168677 - 0.00076912 * c,
            0.24880766 + 0.00006465 * c,
            _mod2pi((238.92881 + 522747.90 * c / 3600) * math.pi / 180),
        ),
    }
    return switch.get(name, ())


def _jupiter_system_longitudes(jd: float) -> dict[str, float]:
    # rates in degrees/day
    rates = {"system_i": 869.82, "system_ii": 870.27, "system_iii": 870.536}
    # reference longitudes at J2000 (approximate)
    offsets = {"system_i": 84.0, "system_ii": 275.0, "system_iii": 23.0}
    base_jd = 2451545.0
    delta = jd - base_jd
    return {
        key: round((offsets[key] + rates[key] * delta) % 360, 2) for key in rates
    }


def planetary_coordinates(observed_at: datetime, name: str, latitude: float | None = None, longitude: float | None = None) -> dict | None:
    if observed_at is None:
        return None
    name_clean = name.strip().title()
    params = _planetary_elements(name_clean, _centuries_since_j2000(observed_at))
    if not params:
        return None
    inclination, long_node, long_peri, mean_dist, eccentricity, mean_long = params

    me = _mod2pi(mean_long - long_peri)
    ve = _true_anomaly(me, eccentricity)
    p_planet_orbit = mean_dist * (1 - eccentricity ** 2) / (1 + eccentricity * math.cos(ve))

    mass = p_planet_orbit
    xh = mass * (
        math.cos(long_node) * math.cos(ve + long_peri - long_node)
        - math.sin(long_node) * math.sin(ve + long_peri - long_node) * math.cos(inclination)
    )
    yh = mass * (
        math.sin(long_node) * math.cos(ve + long_peri - long_node)
        + math.cos(long_node) * math.sin(ve + long_peri - long_node) * math.cos(inclination)
    )
    zh = mass * math.sin(ve + long_peri - long_node) * math.sin(inclination)

    epoch = EPOCH
    j2000 = (observed_at.replace(tzinfo=timezone.utc) - epoch).total_seconds() / 86400.0
    c = j2000 / 36525.0
    inclination_e = (0.00005 - 46.94 * c / 3600) * math.pi / 180
    long_node_e = (-11.26064 - 18228.25 * c / 3600) * math.pi / 180
    long_peri_e = (102.94719 + 1198.28 * c / 3600) * math.pi / 180
    mean_dist_e = 1.00000011 - 0.00000005 * c
    eccentricity_e = 0.01671022 - 0.00003804 * c
    mean_long_e = _mod2pi((100.46435 + 129597740.63 * c / 3600) * math.pi / 180)

    me = _mod2pi(mean_long_e - long_peri_e)
    ve = _true_anomaly(me, eccentricity_e)
    p_earth_orbit = mean_dist_e * (1 - eccentricity_e ** 2) / (1 + eccentricity_e * math.cos(ve))
    xe = p_earth_orbit * math.cos(ve + long_peri_e)
    ye = p_earth_orbit * math.sin(ve + long_peri_e)
    ze = 0.0

    xg = xh - xe
    yg = yh - ye
    zg = zh - ze

    ecl = 23.439281 * math.pi / 180
    xeq = xg
    yeq = yg * math.cos(ecl) - zg * math.sin(ecl)
    zeq = yg * math.sin(ecl) + zg * math.cos(ecl)

    ra_rad = _mod2pi(math.atan2(yeq, xeq))
    dec_rad = math.atan2(zeq, math.sqrt(xeq ** 2 + yeq ** 2))
    distance = math.sqrt(xeq ** 2 + yeq ** 2 + zeq ** 2)
    result = {
        "ra": round(math.degrees(ra_rad), 2),
        "dec": round(math.degrees(dec_rad), 2),
        "distance_au": round(distance, 4),
    }

    if latitude is not None and longitude is not None:
        lat_rad = math.radians(latitude)
        lst = _local_sidereal_time(longitude, j2000, c)
        ha = lst - math.degrees(ra_rad)
        ha = ha % 360
        ha_rad = math.radians(ha)
        dec_rad = math.radians(result["dec"])
        altitude = math.asin(
            math.sin(dec_rad) * math.sin(lat_rad)
            + math.cos(dec_rad) * math.cos(lat_rad) * math.cos(ha_rad)
        )
        azimuth = math.acos(
            (math.sin(dec_rad) - math.sin(altitude) * math.sin(lat_rad))
            / (math.cos(altitude) * math.cos(lat_rad))
        )
        altitude_deg = math.degrees(altitude)
        azimuth_deg = math.degrees(azimuth)
        if math.sin(ha_rad) > 0:
            azimuth_deg = 360 - azimuth_deg
        result.update(
            {
                "altitude": round(altitude_deg, 2),
                "azimuth": round(azimuth_deg, 2),
            }
        )
    if name_clean == "Jupiter":
        result["jupiter_systems"] = _jupiter_system_longitudes(2451545.0 + j2000)
    return result


def _centuries_since_j2000(observed_at: datetime) -> float:
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    return (observed_at - EPOCH).total_seconds() / (86400 * 36525)


def _local_sidereal_time(longitude: float, j2000: float, c: float) -> float:
    lst = (
        280.46061837
        + 360.98564736629 * j2000
        + 0.000387933 * c * c
        - c ** 3 / 38710000
        + longitude
    )
    return lst % 360
