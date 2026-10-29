"""Read a run log for which backend produced it and what went wrong in it.

Nothing in a PNG or a frame report says which backend drew it, and a binary
whose validation layer never loaded is silent in exactly the way a clean run
is, so both are read from the log rather than assumed.
"""

import re

VULKAN = "vulkan"
DIRECTX = "directx"
METAL = "metal"
UNKNOWN = "unknown"

# Ordered: the tracing target is the strongest signal, since the default
# subscriber prints the emitting module path on every line.
_BACKEND_MARKERS = (
    (VULKAN, ("concinnity_device::vulkan", "[Vulkan]")),
    (DIRECTX, ("concinnity_device::directx", "d3d12")),
    (METAL, ("concinnity_device::metal",)),
)

# Metal's validation layer prints this at framework init. It is the layer
# saying it loaded, not something it found.
_METAL_LAYER_BANNER = "Metal API Validation Enabled"

# The proof each backend leaves that its validation layer really came up.
_LAYER_PROOF = {
    VULKAN: ("vulkan validation layer: enabled", "VK_LAYER_KHRONOS_validation"),
    DIRECTX: ("d3d12 debug layer: enabled",),
    METAL: (_METAL_LAYER_BANNER,),
}

# MoltenVK complains about blitting a presented image during teardown on every
# exit, so it is filtered to keep a real finding from being lost in it.
_KNOWN_EXIT_NOISE = re.compile(r"vkCmdBlitImage.*presented|swapchain image.*acquire")

_ADDRESS = re.compile(r"0x[0-9a-f]+")
_ASSERTION = re.compile(r"render graph \((vulkan|directx)\):|assertion .*failed", re.I)
_PANIC = re.compile(r"panicked at ")


def detect_backend(text):
    for backend, markers in _BACKEND_MARKERS:
        if any(marker in text for marker in markers):
            return backend
    return UNKNOWN


def layer_loaded(text, backend):
    """True when the log proves the layer loaded, None when it cannot say."""
    proof = _LAYER_PROOF.get(backend, ())
    if not proof:
        return None
    return any(marker in text for marker in proof)


def findings(text, backend):
    """Validation output, one raw line per message."""
    lines = text.splitlines()
    if backend == VULKAN:
        return [line for line in lines if "[Vulkan]" in line and not _KNOWN_EXIT_NOISE.search(line)]
    if backend == DIRECTX:
        return [line for line in lines if "ERROR d3d12" in line or "WARN d3d12" in line]
    if backend == METAL:
        return [
            line
            for line in lines
            if _METAL_LAYER_BANNER not in line
            and (
                "Metal API Validation" in line
                or "validateComputeFunctionArguments" in line
                or "failed assertion" in line
            )
        ]
    return []


def collapse(lines, limit=20):
    """Group findings by shape so N reports of one message read as one row.

    Handles differ per occurrence, so they are masked before grouping.
    """
    counts = {}
    for line in lines:
        shape = _ADDRESS.sub("ADDR", line).split("[Vulkan] ")[-1].strip()
        counts[shape] = counts.get(shape, 0) + 1
    ranked = sorted(((n, shape) for shape, n in counts.items()), reverse=True)
    return ranked[:limit]


def assertions(text):
    """Engine-side debug assertions, which outrank any layer message."""
    return [line for line in text.splitlines() if _ASSERTION.search(line)]


def panics(text):
    return [line for line in text.splitlines() if _PANIC.search(line)]
