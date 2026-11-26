"""Source-only recasts for complete diagnostic reading and referral forms."""

import re


_SCAN_READINGS = re.compile(
    r"(?P<condition>If the [a-z]+ is equipped with an? (?:[a-z]+ ){0,3}HVAC system), "
    r"go into the HVAC data with the scan tool and get the following readings:",
    re.I,
)
_DUTY_CYCLE = re.compile(r"(?P<component>A/C compressor) duty cycle", re.I)
_TEMPERATURE = re.compile(r"(?P<location>inside|outside) temperature(?P<sensor> sensor reading)?", re.I)
_CALL_PREPARATION = re.compile(
    r"(?P<label>Note: )(?P<actor>Dealers|Technicians|Operators|Staff) should always be prepared to provide "
    r"(?P<references>[a-zA-Z0-9 ()./#-]{1,100}) when calling into (?P<target>[A-Z][A-Z0-9 ]{0,30})\."
)


def scan_reading_instruction(text):
    match = _SCAN_READINGS.fullmatch(text)
    if match:
        return f"{match['condition']}, use the scan tool to open the HVAC data and collect the readings listed below:"
    return None


def recast_diagnostic_passage(text, *, reading):
    if instruction := scan_reading_instruction(text):
        return instruction
    if match := _CALL_PREPARATION.fullmatch(text):
        return (f"{match['label']}When calling into {match['target']}, {match['actor'].lower()} should always have "
                f"{match['references']} ready to provide.")
    if not reading:
        return None
    if match := _DUTY_CYCLE.fullmatch(text):
        return f"Duty cycle of the {match['component']}"
    if match := _TEMPERATURE.fullmatch(text):
        location = match["location"].casefold()
        if match["sensor"]:
            return f"Reading from the sensor for the {location} temperature"
        return f"Temperature measured {location}"
    if text.casefold() == "humidity":
        return "Moisture in the air"
    return None
