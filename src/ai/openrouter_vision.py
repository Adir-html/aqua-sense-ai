"""
OpenRouter Vision-based agricultural irrigation analyzer.
Uses google/gemini-2.0-flash-001 via OpenRouter.
Requires: OPENROUTER_API_KEY environment variable.

Circuit breaker: after 5 consecutive failures the tier is paused for 2 minutes,
then attempts a single probe before fully re-enabling.
"""

import base64
import json
import logging
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

import requests


class QuotaExceededError(RuntimeError):
    """Raised when OpenRouter returns 429 after all retries are exhausted."""


logger = logging.getLogger(__name__)

_MODEL = "google/gemini-2.0-flash-001"

# ── Circuit breaker state ─────────────────────────────────────────────────────
_cb_lock            = threading.Lock()
_cb_failures        = 0
_cb_open_until: float = 0.0   # epoch seconds; 0 means closed (normal operation)
_CB_THRESHOLD       = 5       # consecutive failures before opening
_CB_COOLDOWN        = 120.0   # seconds to stay open before probing

_PROMPT = """\
You are a senior agronomist and irrigation engineer with 20+ years of field experience.
You specialize in drip irrigation, sprinkler systems, water quality diagnostics, and crop stress identification.

Analyze the provided agricultural image using the detailed knowledge below.

════════════════════════════════════════════════════════
 CATEGORY 1 — WATER QUALITY  (issue_category: "water_quality")
════════════════════════════════════════════════════════

turbid_water
  Visual signs: Brown, grey, or reddish-brown water that is not transparent. You cannot see
  through it. Sediment visibly suspended or settled. Water may look like muddy coffee or
  chocolate milk. Common after heavy rain, in canals fed by eroded soil, or from poor-quality
  bore water. Severity is proportional to how opaque the water appears.

algae_bloom
  Visual signs: Water surface covered with green, blue-green, yellow-green, or reddish-brown
  patches or scum. May look like spilled paint, pea soup, or a floating mat. In drip/canal
  systems look for slimy green coating inside open tanks or on emitter surfaces. In open
  channels you may see a foam ring at edges where algae accumulates. Distinct from normal
  green plants.

contamination
  Visual signs: Unusual water colour that is NOT earthy brown — e.g. orange, purple, blue,
  black, or oily rainbow sheen on surface. Visible foam that is white/grey/brown and does not
  dissipate quickly (not just splash foam). Grey or black water from organic decomposition.
  Dead fish, discoloured soil residue near water edges. Oil sheen creates an iridescent
  rainbow film on still water surface.

salinity_stress
  Visual signs: White, grey, or cream-coloured crust or powder on soil surface, especially
  around drip emitter points or along furrow edges. Salt efflorescence looks like frost or
  dried salt deposits. May also see it on inside of irrigation pipes/fittings. Soil surface
  may have a glazed, hard, or cracked appearance. Surrounding plants often show leaf tip burn
  (brown dry edges) even when soil moisture appears adequate.

pathogen_risk
  Visual signs: Dark biofilm or slime coating on irrigation tape, pipes, or tank walls (black,
  brown, or dark green slimy layer). Stagnant water with no movement showing surface film.
  Visible organic debris accumulation — leaf litter, decomposing matter — in water storage.
  Unusual smell would be indicated by context (e.g. stagnant tank). Look for turbid water
  combined with organic material and no flow movement.

════════════════════════════════════════════════════════
 CATEGORY 2 — IRRIGATION SYSTEM  (issue_category: "irrigation_system")
════════════════════════════════════════════════════════

clogged_emitter
  Visual signs: In a drip line, one or more emitter points are DRY while neighbouring emitters
  are wet — creating a distinct dry spot in an otherwise irrigated row. The emitter button may
  be discoloured (white mineral deposits = calcium clog; brown = sediment clog; black = algae
  clog). In sprinklers, a blocked nozzle creates a dark gap in the spray pattern or the head
  does not rotate. Soil directly below a clogged emitter is notably drier than soil under
  working emitters.

pipe_leak
  Visual signs: Unexpected wet or muddy area along a pipe line that is not an emitter point.
  Water pooling in a straight line pattern along a buried pipe route. Visible crack, split,
  or hole in an above-ground pipe with water spraying or dripping from it. Wet soil patch that
  does not correspond to any planned emitter or sprinkler location. Green flush of vegetation
  growing along pipe route due to constant moisture from a slow underground leak.

broken_sprinkler
  Visual signs: A sprinkler head that is cracked, leaning at an abnormal angle, knocked over,
  or physically broken. Water shooting in only one direction rather than rotating. A riser
  that has snapped and is spraying water uncontrolled in one direction. A head that is fully
  missing (stub visible with water gushing up). Uneven semicircle of wet soil showing
  incomplete rotation.

pressure_problem
  Visual signs: Sprinklers producing a very fine mist rather than normal droplets (too high
  pressure — causes runoff and drift). Sprinklers barely reaching half their normal radius with
  droopy arcs (too low pressure). Drip lines with some sections visibly swollen/ballooning
  (too high). Emitters producing an irregular dripping rather than steady slow seep. Uneven
  wet pattern across a field where some zones are clearly over-watered and others under-watered
  within the same irrigation cycle.

pipe_damage
  Visual signs: Physically visible cracked, crushed, kinked, or UV-degraded brittle pipe above
  ground. Pipe that has been run over by machinery — flattened section. Exposed pipe that has
  turned chalky white or brittle from sun exposure. Rodent or animal bite marks on soft
  poly-pipe. A pipe section that has completely separated at a joint, with both ends visible
  and wet soil between them.

filter_blockage
  Visual signs: Visible filter housing that is discoloured, bulging, or has residue around the
  casing — indicating back-pressure. Sediment or debris clearly visible inside a transparent
  filter housing. Poor flow downstream of a filter when the supply is adequate (requires
  knowing where the filter is). Discoloured flush water coming from a filter bleed valve.
  Filter screen visibly coated with brown/green sediment when inspected.

════════════════════════════════════════════════════════
 CATEGORY 3 — FIELD & SOIL  (issue_category: "field_soil")
════════════════════════════════════════════════════════

dry_patch
  Visual signs: A clearly visible area of lighter-coloured, pale, or cracked dry soil within
  a field that should be uniformly irrigated. Wilted or stressed plants specifically in that
  patch while surrounding plants are upright and healthy. Cracked soil polygons (mud cracks)
  in an area that appears to have dried out. A circular or linear dry zone corresponding to
  where a clogged emitter or broken pipe has failed. In aerial views: brown patch within
  green field.

waterlogging
  Visual signs: Standing water on the soil surface for an extended period after irrigation.
  Soil surface has a grey, bluish, or dark anaerobic appearance. Plant stems at soil level
  appear darkened or rotting. Yellowing of older lower leaves on plants in affected zone
  (nitrogen loss from anaerobic soil). In severe cases visible dark water between plant rows.
  Earthworm or insect emergence to surface (fleeing waterlogged soil). Algae growing on
  soil surface between plants.

runoff
  Visual signs: Water flowing off the field in visible channels or streams during or after
  irrigation. Erosion channels or rills forming in soil with soil being carried in the water.
  Sediment deposit or fan shape at the bottom/edge of a slope. Mud or dirty water flowing
  into paths, roads, or drains adjacent to the field. Exposed soil streaks where surface
  water has moved and removed topsoil. Irrigation water clearly leaving the root zone before
  being absorbed.

soil_erosion
  Visual signs: Visible gully or rill formation — small channels cut into soil by flowing
  water. Exposed plant roots where soil has been washed away from the base of plants. Soil
  profile exposed showing different coloured layers (topsoil removed, subsoil visible).
  Sediment deposits (delta shapes) at lower elevation points. Soil splashed onto lower leaves
  indicating raindrop or high-pressure irrigation impact. Bare patches with no topsoil where
  healthy soil should be.

uneven_distribution
  Visual signs: Clearly visible alternating wet and dry bands or patches across a field
  during or just after irrigation. Some rows or zones much darker (wetter) than others with
  no obvious reason. In overhead view: irregular patchwork of wet/dry rather than uniform
  coverage. Plants of same variety and age visibly different sizes in different zones of same
  field — stunted in under-irrigated zones. Visible pooling in some areas while others remain
  dry — pointing to design flaw or blockage pattern.

════════════════════════════════════════════════════════
 CATEGORY 4 — CROP HEALTH  (issue_category: "crop_health")
════════════════════════════════════════════════════════

wilting
  Visual signs: Leaves and stems drooping, hanging downward, losing their upright turgid
  posture. Leaf blades may roll inward along their length (especially grasses and corn) —
  a direct drought stress response. Tips of leaves curling downward. Whole plants collapsed
  at midday even if it is not abnormally hot (indicating root zone is dry despite irrigation).
  Temporary wilting in afternoon that recovers at night is early stress; permanent wilting
  that does not recover overnight is severe. Leaves appear dull rather than glossy.

overwatering_symptoms
  Visual signs: Lower older leaves turning yellow (chlorotic) and falling off while upper
  leaves remain green — classic waterlogging/overwatering pattern. Stems at soil level
  appearing dark, soft, or mushy (crown rot). Soil surface around plant base stays
  persistently dark and wet between irrigation cycles. Roots visible at soil surface appear
  dark brown or black rather than white/tan. Algae or moss growing on soil between plants.
  Plants that look wilted DESPITE soil being visibly wet (counter-intuitive — roots have
  died from anaerobic conditions and cannot take up water).

nutrient_deficiency
  Visual signs related to water quality:
  - Iron deficiency (from alkaline or high-pH water): new young leaves turn yellow but leaf
    veins stay green (interveinal chlorosis starting at top of plant).
  - Calcium deficiency (from acidic irrigation water or uneven distribution): tip burn on
    lettuce/cabbage inner leaves; blossom end rot on tomatoes (dark leathery patch on fruit
    bottom); distorted new growth.
  - Magnesium deficiency: older lower leaves show interveinal yellowing starting from leaf
    edges, spreading inward.
  - Nitrogen deficiency (from waterlogging reducing N uptake): overall pale green/yellow
    colour starting from oldest leaves, stunted growth, thin stems.
  - Boron deficiency (from water quality): distorted new growth, hollow stems, cracked fruit.

disease_pressure
  Visual signs linked to irrigation/moisture:
  - Fungal (Botrytis/grey mould): grey fuzzy mould on leaves, flowers, or fruit in humid
    conditions — associated with overwatering or poor air circulation from dense canopy
    kept wet.
  - Powdery mildew: white powdery coating on upper leaf surface — thrives in alternating
    wet/dry conditions.
  - Root rot (Phytophthora, Pythium): plants suddenly collapsing with dark water-soaked stem
    base; when root pulled it is dark brown/black and slippery rather than firm and white.
  - Bacterial: water-soaked dark spots on leaves that later turn brown and may have yellow
    halo — spread by overhead irrigation splash.
  - Damping off (seedlings): seedlings collapsing at soil level, dark pinched stem at
    ground level — caused by excessive soil moisture.

════════════════════════════════════════════════════════
 HEALTHY SYSTEM — what to look for
════════════════════════════════════════════════════════
- Water is clear and transparent; you can see through it or it appears blue/slightly green in
  storage but not murky.
- Emitters/sprinklers produce even, consistent output across the entire observed area.
- Soil moisture appears uniform across the field with no patches of ponding or dry cracking.
- Plants are upright, leaves are glossy and turgid, consistent green colour appropriate for
  species and growth stage.
- No visible leaks, breaks, or damage to pipes, fittings, or emitters.
- No salt crust, biofilm, algae, or unusual deposits on system components.

════════════════════════════════════════════════════════
 YOUR TASK
════════════════════════════════════════════════════════
Using the knowledge above, analyze only what is VISIBLE in this image.
Do NOT guess what you cannot see. If the image is not of an irrigation/agricultural context,
set status to "healthy" and note that in your message.

Respond with ONLY valid JSON (no markdown, no extra text):
{
  "status": "critical" or "warning" or "healthy",
  "issue_detected": <true or false>,
  "confidence": <float 0.0-1.0>,
  "primary_issue": "<single most important issue key from the lists above, or null>",
  "issue_category": "<'water_quality' or 'irrigation_system' or 'field_soil' or 'crop_health' or null>",
  "all_issues": ["<all detected issue keys visible in image, empty array if healthy>"],
  "severity": "<'critical', 'high', 'medium', or 'low' — null if healthy>",
  "urgency": "<'immediate', 'soon', 'monitor', or 'none'>",
  "affected_area_pct": <integer 0-100, estimated % of visible area affected>,
  "water_waste_risk": "<'high', 'medium', 'low', or 'none'>",
  "crop_impact": "<one sentence on yield/crop consequences, or null if healthy>",
  "message": "<one precise sentence describing the specific visual evidence you see>",
  "recommendation": "<one specific actionable step a farmer can take today>",
  "healthy_probability": <float 0.0-1.0>,
  "faulty_probability": <float 0.0-1.0>
}

Severity guide:
  critical = crop or system loss imminent (e.g. full clog, active large leak, severe wilting)
  high     = significant damage within 1-3 days if untreated
  medium   = productivity loss within a week if untreated
  low      = minor issue, monitor closely

Rules:
- healthy_probability + faulty_probability must sum to exactly 1.0
- confidence = probability of your chosen status classification
- primary_issue must be one of the exact key names listed above
- Be specific about what visual evidence led to your conclusion
"""


def is_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _cb_is_open() -> bool:
    """Return True if the circuit breaker is open (tier should be skipped)."""
    global _cb_open_until
    with _cb_lock:
        if _cb_open_until == 0.0:
            return False
        if time.monotonic() >= _cb_open_until:
            # Cooldown expired — allow a single probe through (half-open)
            _cb_open_until = 0.0
            return False
        return True


def _cb_record_success() -> None:
    global _cb_failures, _cb_open_until
    with _cb_lock:
        _cb_failures = 0
        _cb_open_until = 0.0


def _cb_record_failure() -> None:
    global _cb_failures, _cb_open_until
    with _cb_lock:
        _cb_failures += 1
        if _cb_failures >= _CB_THRESHOLD:
            _cb_open_until = time.monotonic() + _CB_COOLDOWN
            logger.warning(
                f"OpenRouter circuit breaker OPEN after {_cb_failures} failures — "
                f"pausing for {_CB_COOLDOWN:.0f}s"
            )


def analyze(image_path: str) -> Dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    if _cb_is_open():
        raise RuntimeError("OpenRouter circuit breaker is open — skipping tier")

    img_path   = Path(image_path)
    img_b64    = base64.standard_b64encode(img_path.read_bytes()).decode("utf-8")
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".gif":  "image/gif",
        ".webp": "image/webp",
    }.get(img_path.suffix.lower(), "image/jpeg")

    logger.info(f"Sending to OpenRouter ({_MODEL}): {img_path.name}")

    payload = {
        "model": _MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
        "max_tokens": 700,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Timeout: 10s per attempt (was 30s). Max backoff cap: 3s.
    request_timeout = int(os.environ.get("OPENROUTER_TIMEOUT", "10"))

    last_err: Optional[str] = None
    for attempt in range(3):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=request_timeout,
            )
            if resp.status_code == 429:
                if attempt < 2:
                    wait = min(2 ** attempt, 3)   # cap at 3s
                    logger.warning(f"OpenRouter rate-limited — retrying in {wait}s (attempt {attempt+1}/3)")
                    time.sleep(wait)
                    continue
                _cb_record_failure()
                raise QuotaExceededError("OpenRouter API quota exceeded — please try again later")
            if resp.status_code != 200:
                _cb_record_failure()
                raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text[:300]}")
            break
        except requests.exceptions.Timeout:
            last_err = f"timeout on attempt {attempt+1}"
            logger.warning(f"OpenRouter {last_err}")
            if attempt < 2:
                wait = min(2 ** attempt, 3)
                time.sleep(wait)
    else:
        _cb_record_failure()
        raise RuntimeError(f"OpenRouter failed after 3 attempts: {last_err}")

    try:
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        _cb_record_failure()
        raise RuntimeError(f"OpenRouter returned unexpected response structure: {e} — body: {resp.text[:300]}")
    logger.debug(f"OpenRouter raw: {raw}")

    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.lstrip("json").lstrip("JSON").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _cb_record_failure()
        raise RuntimeError(f"OpenRouter returned invalid JSON: {e}")

    _cb_record_success()
    return _normalise(data)


def _normalise(data: dict) -> Dict[str, Any]:
    status = str(data.get("status", "healthy")).lower()
    if status not in ("critical", "warning", "healthy"):
        status = "healthy"

    result = "normal" if status == "healthy" else "faulty"

    fp  = float(data.get("faulty_probability",  0.1 if status == "healthy" else 0.8))
    hp  = float(data.get("healthy_probability", 0.9 if status == "healthy" else 0.2))
    tot = fp + hp
    if tot > 0:
        fp /= tot; hp /= tot
    else:
        # Both values were 0 (malformed response) — default to 50/50
        fp, hp = 0.5, 0.5

    confidence = hp if status == "healthy" else fp

    severity = (data.get("severity") or "").lower() or None
    if severity and severity not in ("critical", "high", "medium", "low"):
        severity = None

    urgency = (data.get("urgency") or "none").lower()
    if urgency not in ("immediate", "soon", "monitor", "none"):
        urgency = "none"

    all_issues = data.get("all_issues", [])
    if not isinstance(all_issues, list):
        all_issues = []

    logger.info(f"Result: {status} conf={confidence:.3f} primary={data.get('primary_issue')} "
                f"urgency={urgency} affected={data.get('affected_area_pct', 0)}%")

    return {
        "result":             result,
        "status":             status,
        "confidence":         round(confidence, 4),
        "issue_detected":     status != "healthy",
        "faulty_probability": round(fp, 4),
        "normal_probability": round(hp, 4),
        "issue_type":         data.get("primary_issue") or None,
        "issue_category":     data.get("issue_category") or None,
        "all_issues":         all_issues,
        "severity":           severity,
        "urgency":            urgency,
        "affected_area_pct":  float(data.get("affected_area_pct", 0)),
        "water_waste_risk":   (data.get("water_waste_risk") or "none").lower(),
        "crop_impact":        data.get("crop_impact") or None,
        "message":            str(data.get("message", "")).strip(),
        "recommendation":     str(data.get("recommendation", "")).strip() or None,
        "model_type":         "openrouter_gemini",
    }
