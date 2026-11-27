"""Rephrase complete wheel-service instructions while retaining their constraints."""

import re


_STATEMENTS = tuple((re.compile(pattern), wording) for pattern, wording in (
    (
        r"Loosen each (?P<nuts>wheel nut) (?P<turns>[1-9][0-9]{0,2} complete turns?)\.",
        r"Loosen every \g<nuts> by \g<turns>.",
    ),
    (
        r"Using a (?P<brush>wire brush) or (?P<wire_wheel>wire wheel), clean the (?P<rotor>rotor) "
        r"to the (?P<wheel>wheel) or (?P<drum>brake drum) to (?P<hub>wheel hub) contact area\.",
        r"Clean with a \g<brush> or a \g<wire_wheel> where the \g<rotor> contacts the \g<wheel> "
        r"or where the \g<drum> contacts the \g<hub>.",
    ),
    (
        r"Using the (?P<tool>appropriate special tool), clean the contact areas "
        r"of the (?P<wheel>wheel) to (?P<brakes>brake rotor or brake drum)\.",
        r"Clean where the \g<wheel> meets the \g<brakes> with the \g<tool>.",
    ),
    (
        r"Using the (?P<tool>appropriate special tool \([0-9]{1,4}\)), "
        r"clean the surface around the (?P<studs>wheel studs)\.",
        r"Clean around the \g<studs> with the \g<tool>.",
    ),
    (
        r"Clean the threads of the (?P<stud>wheel stud)s\. "
        r"If the threads are damaged, replace the (?P=stud)\.",
        r"Clean the threads on each \g<stud>. Replace any stud with damage to its threads.",
    ),
    (
        r"After cleaning all the contact areas, use (?P<cleaner>brake clean or denatured alcohol) "
        r"to remove all the (?P<oil>penetrating oil), (?P<dirt>dirt) and (?P<debris>debris) "
        r"from the (?P<parts>wheel nuts, brake rotor or brake drum)\.",
        r"Once all contact areas are clean, remove any remaining \g<oil>, \g<dirt>, and \g<debris> "
        r"from the \g<parts> using \g<cleaner>.",
    ),
    (
        r"Inspect and clean the contact area of the (?P<part>wheel)\. "
        r"Refer to (?P<section>Wheel Mounting Surface Check)\.",
        r"Check the \g<part>'s mating surface and clean it. See \g<section>.",
    ),
    (
        r"Apply a (?P<amount>small amount of lubricant) to the inner diameter of "
        r"the (?P<hole>wheel hub pilot hole \([0-9]{1,4}\)) where it contacts (?:the with )?"
        r"the (?P<flange>wheel bearing/hub flange)\.",
        r"Use a \g<amount> on the inner diameter of the \g<hole>, "
        r"at the contact surface with the \g<flange>.",
    ),
    (
        r"Install the (?P<part>tire and wheel assembly)\.",
        r"Fit the \g<part>.",
    ),
    (
        r"Install the (?P<part>wheel (?:center cap|cap nuts)), if required\.",
        r"When required, install the \g<part>.",
    ),
    (
        r"Remove the (?P<support>support) and lower the (?P<vehicle>vehicle)\.",
        r"Lower the \g<vehicle> after removing the \g<support>.",
    ),
))


def recast_wheel_service_passage(text):
    for pattern, wording in _STATEMENTS:
        if match := pattern.fullmatch(text):
            return match.expand(wording)
    return None
