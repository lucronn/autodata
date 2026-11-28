"""Recover distinct wording for complete, recognized vehicle lifting instructions."""

from hashlib import sha256
import re


_HOOD_PRECAUTION_SHA256 = "f21b60276ddf0e5646701986d9e4850876050dff025a2eb2e6a0676f35da62e4"

# Bind the precautions and illustrated locations to the complete source text.
_REVIEWED_STATEMENTS = {
    # Hoist support while removing major components.
    "f5aad5b111e54f90441e251b86e96485ecf1db7de53a35265518bcff23a9229f": (
        "If you are removing major components while the vehicle rests on a hoist, set jack stands at the end "
        "opposite the work and secure the vehicle to the hoist with straps."
    ),
    # Hood position, remote start, and risk of injury or damage.
    _HOOD_PRECAUTION_SHA256: (
        "Work under the vehicle or in its engine compartment with the hood open fully or to the secondary latch. "
        "When the hood is opened to that latch, the vehicle disables remote start through the key fob and the "
        "OnStar mobile app. If the hood is neither opened fully nor opened to its secondary latch during that work, "
        "unintended vehicle starting can cause personal injury or vehicle damage."
    ),
    # Rated capacity includes the vehicle and its contents.
    "b0c297079e0c1440cd41d3eec6cd7a610717af36da39b9af29f3326ba779e329": (
        "The combined weight of the vehicle and all of its contents must be within the rating of any lifting "
        "or jacking equipment you use."
    ),
    # Damage can affect the equipment, vehicle, and contents.
    "4303478294bb3be81036758b2842f36b06c04037e9205613df0bb2d190da77ca": (
        "Skipping the preceding steps can damage the vehicle, its contents, the lifting or jacking equipment, "
        "or any combination of them."
    ),
    # Both rear sides are available individually.
    "b96a1c95c973807898ed4bce9fb5d46668d5850af9e3197a507e2f31d0bcd324": (
        "When using these jacking points, raise only one rear side of the vehicle at a time, either left or right."
    ),
    # The rear lift point stays inboard and forward of the rear suspension.
    "cac2da56e0bc78e5ca3c8a204fd4b3b7c23d2d7e96d6390027e36d5c4b02c96d": (
        "To raise the rear of the vehicle, set the floor jack lift pad as shown on either side of the suspension "
        "cradle. The pad must be inboard and forward of the rear suspension."
    ),
    # The front lift point is the frame center shown in the illustration.
    "e1a130916af8a51eb494d611c840d2c925b9e6a68fdf982faae4efccdb0a598f": (
        "Raise the front of the vehicle with the floor jack lift pad centered on the front suspension frame, as shown."
    ),
}

_STATEMENTS = tuple((re.compile(pattern), wording) for pattern, wording in (
    (
        r"The (?P<lifting>lifting) equipment or the (?P<jacking>jacking) equipment must meet the "
        r"operational standards of the (?P=lifting) equipment or (?P=jacking) equipment manufacturer\.",
        r"Any equipment used for \g<lifting> or \g<jacking> must comply with its manufacturer's operating standards.",
    ),
    (
        r"Perform the (?P<part>vehicle) lifting or jacking procedure on a "
        r"(?P<clean>clean), (?P<hard>hard), (?P<dry>dry), (?P<level>level) surface\.",
        r"Lift or jack the \g<part> on a \g<level> surface that is \g<hard>, \g<clean>, and \g<dry>.",
    ),
    (r"Vehicle Lifting-(?P<lift>Frame Contact Lift)", r"Using a \g<lift> to Raise the Vehicle"),
    (r"(?P<end>Front|Rear) (?P<pads>Lift Pads)", r"\g<pads> at the \g<end>"),
    (r"Vehicle (?P<operation>Jacking)", r"\g<operation> the Vehicle"),
    (r"Under the (?P<assembly>Rear Suspension)", r"Beneath the \g<assembly>"),
    (r"Under the Center of the (?P<assembly>Front Suspension Frame)", r"Beneath the \g<assembly> Center"),
    (r"Supporting the Vehicle with (?P<stands>Jackstands)", r"Using \g<stands> to Support the Vehicle"),
    (
        r"Place (?P<stands>jackstands) ONLY under (?P<strong>strong) and (?P<stable>stable) "
        r"(?P<structures>vehicle structures)\.",
        r"Position \g<stands> beneath \g<structures> only where the structure is both \g<stable> and \g<strong>.",
    ),
))


def recast_reviewed_hood_precaution(text):
    if sha256(text.encode()).hexdigest() == _HOOD_PRECAUTION_SHA256:
        return _REVIEWED_STATEMENTS[_HOOD_PRECAUTION_SHA256]
    return None


def recast_vehicle_lifting_passage(text):
    if wording := _REVIEWED_STATEMENTS.get(sha256(text.encode()).hexdigest()):
        return wording
    for pattern, wording in _STATEMENTS:
        if match := pattern.fullmatch(text):
            return match.expand(wording)
    return None
