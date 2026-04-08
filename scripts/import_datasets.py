"""
AquaSense AI — Public Dataset Importer
======================================
Downloads and organises public labeled image datasets into:
  dataset/<issue_type>/   (e.g. dataset/turbid_water/, dataset/wilting/)

Sources used (all free, no login required except Kaggle):
  - HuggingFace Datasets Hub  (plant disease, algae, water quality)
  - Kaggle Datasets            (PlantVillage, water leak, irrigation)
  - Direct GitHub/URL          (EuroSAT satellite, misc)

Usage:
  python scripts/import_datasets.py                  # all categories
  python scripts/import_datasets.py --category crop_health
  python scripts/import_datasets.py --limit 200      # max images per issue type
  python scripts/import_datasets.py --dry-run        # show what would be downloaded

Kaggle setup (one time):
  1. Go to https://www.kaggle.com/settings/account → Create New Token
  2. Save the downloaded kaggle.json to C:/Users/<you>/.kaggle/kaggle.json
"""

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

# Load .env so KAGGLE_API_TOKEN is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("import_datasets")

# ── Repo root & dataset directory ─────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "dataset"

# ── Issue type → folder mapping ───────────────────────────────────────────────
ALL_ISSUES = [
    # Water quality
    "turbid_water", "algae_bloom", "contamination",
    "salinity_stress", "pathogen_risk",
    # Irrigation system
    "clogged_emitter", "pipe_leak", "broken_sprinkler",
    "pressure_problem", "pipe_damage", "filter_blockage",
    # Field & soil
    "dry_patch", "waterlogging", "runoff",
    "soil_erosion", "uneven_distribution",
    # Crop health
    "wilting", "overwatering_symptoms",
    "nutrient_deficiency", "disease_pressure",
]

CATEGORIES = {
    "water_quality":     ["turbid_water", "algae_bloom", "contamination", "salinity_stress", "pathogen_risk"],
    "irrigation_system": ["clogged_emitter", "pipe_leak", "broken_sprinkler", "pressure_problem", "pipe_damage", "filter_blockage"],
    "field_soil":        ["dry_patch", "waterlogging", "runoff", "soil_erosion", "uneven_distribution"],
    "crop_health":       ["wilting", "overwatering_symptoms", "nutrient_deficiency", "disease_pressure"],
}

# ── Source definitions ─────────────────────────────────────────────────────────
#
# Each source entry:
#   type:         "huggingface" | "kaggle" | "url_zip" | "url_images"
#   covers:       list of issue_type keys this dataset maps to
#   label_map:    {dataset_label -> our_issue_type}  (for HF / Kaggle classification sets)
#   split:        HF dataset split to use
#   max_per_class: cap per label to avoid huge downloads
#
SOURCES = [

    # ════════════════════════════════════════════════════════════════
    # HuggingFace sources — no credentials needed, run first
    # ════════════════════════════════════════════════════════════════

    # ── CROP HEALTH ────────────────────────────────────────────────
    {
        "name":    "Beans Leaf Disease (HuggingFace)",
        "type":    "huggingface",
        "dataset": "AI-Lab-Makerere/beans",
        "split":   "train",
        "covers":  ["disease_pressure", "nutrient_deficiency"],
        "label_map": {
            "angular_leaf_spot": "disease_pressure",
            "bean_rust":         "disease_pressure",
            "healthy":           None,
        },
        "image_col": "image",
        "label_col": "labels",
    },

    # ── WATER QUALITY ─────────────────────────────────────────────
    {
        "name":    "Algae Dataset (HuggingFace)",
        "type":    "huggingface",
        "dataset": "samitizerxu/algae-wirs",
        "split":   "train",
        "covers":  ["algae_bloom"],
        "label_map": {
            "algae":     "algae_bloom",
            "Algae":     "algae_bloom",
            "algal":     "algae_bloom",
            "bloom":     "algae_bloom",
            "non_algae": None,
            "NonAlgae":  None,
            "healthy":   None,
            "clean":     None,
        },
        "image_col": "image",
        "label_col": "label",
        "fallback_all_to": "algae_bloom",
    },

    # ── FIELD & SOIL ──────────────────────────────────────────────
    {
        "name":    "EuroSAT Satellite (HuggingFace)",
        "type":    "huggingface",
        "dataset": "blanchon/EuroSAT_RGB",
        "split":   "train",
        "covers":  ["dry_patch", "waterlogging", "uneven_distribution"],
        "label_map": {
            "Annual Crop":              "dry_patch",
            "Herbaceous Vegetation":    "uneven_distribution",
            "Industrial Buildings":     None,
            "Residential Buildings":    None,
            "River":                    "waterlogging",
            "SeaLake":                  "waterlogging",
            "Forest":                   None,
            "Permanent Crop":           None,
            "Highway":                  None,
            "Pasture":                  "dry_patch",
        },
        "image_col": "image",
        "label_col": "label",
    },

    # ════════════════════════════════════════════════════════════════
    # Kaggle sources — require kaggle.json (see script header)
    # ════════════════════════════════════════════════════════════════

    {
        "name":    "Kaggle: Water Turbidity",
        "type":    "kaggle_dataset",
        "dataset": "aniketdeo/turbidity-water-dataset",
        "covers":  ["turbid_water", "contamination"],
        "folder_map": {
            "turbid":   "turbid_water",
            "dirty":    "turbid_water",
            "muddy":    "turbid_water",
            "polluted": "contamination",
            "clear":    None,
            "clean":    None,
        },
    },

    {
        "name":    "Kaggle: Soil Erosion Dataset",
        "type":    "kaggle_dataset",
        "dataset": "vishnupriyavr/soil-erosion-dataset",
        "covers":  ["soil_erosion", "runoff", "dry_patch"],
        "folder_map": {
            "eroded":     "soil_erosion",
            "erosion":    "soil_erosion",
            "runoff":     "runoff",
            "dry":        "dry_patch",
            "healthy":    None,
            "non_eroded": None,
        },
    },

    {
        "name":    "Kaggle: Flood/Waterlogging Detection",
        "type":    "kaggle_dataset",
        "dataset": "moisescristian/floods-dataset",
        "covers":  ["waterlogging", "runoff"],
        "folder_map": {
            "flooded":      "waterlogging",
            "flood":        "waterlogging",
            "non-flooded":  None,
            "no_flood":     None,
        },
    },

    {
        "name":     "Kaggle: Water Leak Detection",
        "type":     "kaggle_dataset",
        "dataset":  "ziya07/water-leak-dataset",
        "covers":   ["pipe_leak", "pipe_damage"],
        "csv_mode": True,  # tabular-only dataset, no images
        "folder_map": {},
    },

    {
        "name":    "Kaggle: Pipe Defect Detection",
        "type":    "kaggle_dataset",
        "dataset": "humansintheloop/pipes-defects-datasets",
        "covers":  ["pipe_damage", "pipe_leak", "filter_blockage"],
        "folder_map": {
            "crack":       "pipe_damage",
            "corrosion":   "pipe_damage",
            "deposit":     "filter_blockage",
            "blockage":    "filter_blockage",
            "joint":       "pipe_damage",
            "root":        "pipe_damage",
            "healthy":     None,
            "normal":      None,
        },
    },

    # ════════════════════════════════════════════════════════════════
    # Roboflow Universe — free datasets, requires ROBOFLOW_API_KEY
    # Get a free key at https://app.roboflow.com (no credit card)
    # ════════════════════════════════════════════════════════════════

    {
        "name":       "Roboflow: Pipe Leak Detection",
        "type":       "roboflow",
        "workspace":  "water-pipes-obgeb",
        "project":    "water-pipe-leakage-detection",
        "version":    1,
        "covers":     ["pipe_leak"],
        "label_map":  {
            "leak":        "pipe_leak",
            "leaking":     "pipe_leak",
            "pipe_leak":   "pipe_leak",
        },
    },

    {
        "name":       "Roboflow: Sprinkler Detection",
        "type":       "roboflow",
        "workspace":  "sprinkler-lkvsv",
        "project":    "sprinkler-detection-r6mcd",
        "version":    1,
        "covers":     ["broken_sprinkler"],
        "label_map":  {
            "broken":           "broken_sprinkler",
            "damaged":          "broken_sprinkler",
            "sprinkler":        "broken_sprinkler",
            "broken_sprinkler": "broken_sprinkler",
        },
    },

    # ════════════════════════════════════════════════════════════════
    # Web scraping — no credentials needed, uses Bing image search
    # Requires: pip install icrawler
    # ════════════════════════════════════════════════════════════════

    {
        "name":    "Web scrape: Pipe Leak",
        "type":    "web_scrape",
        "covers":  ["pipe_leak"],
        "queries": [
            {"query": "water pipe leak spraying", "issue": "pipe_leak"},
            {"query": "irrigation pipe burst leaking water", "issue": "pipe_leak"},
            {"query": "broken underground pipe leak", "issue": "pipe_leak"},
        ],
    },

    {
        "name":    "Web scrape: Pipe Damage",
        "type":    "web_scrape",
        "covers":  ["pipe_damage"],
        "queries": [
            {"query": "damaged irrigation pipe cracked", "issue": "pipe_damage"},
            {"query": "corroded water pipe rust damage", "issue": "pipe_damage"},
            {"query": "broken plastic irrigation pipe", "issue": "pipe_damage"},
        ],
    },

    {
        "name":    "Web scrape: Broken Sprinkler",
        "type":    "web_scrape",
        "covers":  ["broken_sprinkler"],
        "queries": [
            {"query": "broken sprinkler head lawn", "issue": "broken_sprinkler"},
            {"query": "damaged irrigation sprinkler flooding", "issue": "broken_sprinkler"},
            {"query": "sprinkler head cracked leaking", "issue": "broken_sprinkler"},
        ],
    },

    {
        "name":    "Web scrape: Clogged Emitter",
        "type":    "web_scrape",
        "covers":  ["clogged_emitter"],
        "queries": [
            {"query": "clogged drip irrigation emitter blocked", "issue": "clogged_emitter"},
            {"query": "blocked drip emitter mineral deposit", "issue": "clogged_emitter"},
            {"query": "irrigation nozzle clogged calcified", "issue": "clogged_emitter"},
        ],
    },

    {
        "name":    "Web scrape: Pressure Problem",
        "type":    "web_scrape",
        "covers":  ["pressure_problem"],
        "queries": [
            {"query": "low pressure irrigation sprinkler weak", "issue": "pressure_problem"},
            {"query": "irrigation system pressure gauge low", "issue": "pressure_problem"},
            {"query": "drip irrigation pressure regulator", "issue": "pressure_problem"},
        ],
    },

    {
        "name":    "Web scrape: Filter Blockage",
        "type":    "web_scrape",
        "covers":  ["filter_blockage"],
        "queries": [
            {"query": "irrigation filter clogged dirty", "issue": "filter_blockage"},
            {"query": "drip system filter blocked sediment", "issue": "filter_blockage"},
            {"query": "water filter irrigation dirty mesh", "issue": "filter_blockage"},
        ],
    },
]


# ── Download helpers ───────────────────────────────────────────────────────────

def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_image(img, dest: Path, name: str) -> bool:
    """Save a PIL image to dest/name. Returns True on success."""
    try:
        from PIL import Image as PILImage
        if not isinstance(img, PILImage.Image):
            img = PILImage.fromarray(img)
        img = img.convert("RGB")
        img.save(dest / name)
        return True
    except Exception as e:
        log.debug(f"Save failed {name}: {e}")
        return False


def _count_existing(issue_dir: Path) -> int:
    if not issue_dir.exists():
        return 0
    return len(list(issue_dir.glob("*.jpg")) + list(issue_dir.glob("*.png")) + list(issue_dir.glob("*.jpeg")))


def _copy_image_file(src: Path, dest_dir: Path, prefix: str = "") -> bool:
    try:
        dest = dest_dir / f"{prefix}{src.name}"
        shutil.copy2(src, dest)
        return True
    except Exception as e:
        log.debug(f"Copy failed {src}: {e}")
        return False


# ── HuggingFace downloader ─────────────────────────────────────────────────────

def download_huggingface(source: dict, limit: int, dry_run: bool) -> dict:
    """Download images from a HuggingFace dataset. Returns {issue_type: count}."""
    results = {}
    try:
        from datasets import load_dataset
    except ImportError:
        log.error("  datasets library not installed. Run: pip install datasets")
        return results

    ds_id    = source["dataset"]
    split    = source.get("split", "train")
    label_map = source.get("label_map", {})
    img_col  = source.get("image_col", "image")
    lbl_col  = source.get("label_col", "label")
    fallback = source.get("fallback_all_to")

    log.info(f"  Streaming {ds_id} [{split}]…")

    try:
        ds = load_dataset(ds_id, split=split, streaming=True)
    except Exception as e:
        log.warning(f"  Could not load {ds_id}: {e}")
        return results

    # Get label names if dataset has ClassLabel feature
    label_names = {}
    try:
        feat = ds.features.get(lbl_col)
        if hasattr(feat, "names"):
            label_names = {i: n for i, n in enumerate(feat.names)}
    except Exception:
        pass

    counts = {}   # issue_type -> count saved

    for i, row in enumerate(ds):
        # Determine issue type for this row
        raw_label = row.get(lbl_col)
        if raw_label is None:
            issue_type = fallback
        else:
            # Convert int label to name
            label_str = label_names.get(raw_label, str(raw_label)) if isinstance(raw_label, int) else str(raw_label)
            issue_type = label_map.get(label_str)
            if issue_type is None and fallback:
                issue_type = fallback
            elif issue_type is None:
                continue  # not mapped → skip

        if issue_type is None:
            continue

        # Check limit
        if counts.get(issue_type, 0) >= limit:
            # Check if all tracked types have hit their limit
            tracked = {it for it in label_map.values() if it}
            if fallback:
                tracked.add(fallback)
            if all(counts.get(t, 0) >= limit for t in tracked):
                break
            continue

        # Get image
        img = row.get(img_col)
        if img is None:
            continue

        dest_dir = _ensure_dir(DATASET_DIR / issue_type)
        if not dry_run:
            saved = _save_image(img, dest_dir, f"hf_{ds_id.replace('/','_')}_{i:06d}.jpg")
            if saved:
                counts[issue_type] = counts.get(issue_type, 0) + 1
        else:
            counts[issue_type] = counts.get(issue_type, 0) + 1

        if sum(counts.values()) % 100 == 0:
            log.info(f"    {sum(counts.values())} images so far: {counts}")

    for k, v in counts.items():
        results[k] = results.get(k, 0) + v
    return results


# ── Kaggle downloader ─────────────────────────────────────────────────────────

def _kaggle_available() -> bool:
    """Return True only if kaggle package is installed AND credentials exist."""
    import io, contextlib, base64

    # Support KAGGLE_API_TOKEN env var (newer KGAT_... token format)
    # The kaggle library >= 1.8.0 reads this env var directly — just ensure it's set.
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if token and token.startswith("KGAT_"):
        # New-style token: library reads KAGGLE_API_TOKEN directly, no extra setup needed
        pass
    elif token:
        # Legacy style: base64-encoded {"username":...,"key":...}
        try:
            import base64
            decoded = json.loads(base64.b64decode(token).decode())
            os.environ["KAGGLE_USERNAME"] = decoded["username"]
            os.environ["KAGGLE_KEY"]      = decoded["key"]
        except Exception:
            pass

    # Also accept legacy kaggle.json file
    cred = Path.home() / ".kaggle" / "kaggle.json"
    has_token = bool(os.environ.get("KAGGLE_API_TOKEN"))
    has_env   = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    has_file  = cred.exists()
    if not has_token and not has_env and not has_file:
        return False

    try:
        import kaggle
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            kaggle.api.authenticate()
        return True
    except (Exception, SystemExit):
        return False


def download_kaggle(source: dict, limit: int, dry_run: bool) -> dict:
    """Download a Kaggle dataset and map folders to issue types."""
    results = {}

    if not _kaggle_available():
        log.warning("  Kaggle not configured — skipping. To enable: save kaggle.json to ~/.kaggle/kaggle.json")
        return results

    ds_id      = source["dataset"]
    folder_map = source.get("folder_map", {})

    if source.get("csv_mode"):
        log.info(f"  Skipping {ds_id} (tabular-only dataset, no images)")
        return results

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log.info(f"  Downloading kaggle dataset: {ds_id}…")
        try:
            import kaggle
            kaggle.api.dataset_download_files(ds_id, path=str(tmp_path), unzip=True, quiet=False)
        except BaseException as e:
            log.warning(f"  Kaggle download failed for {ds_id}: {e}")
            return results

        # Walk all image files and match to issue type by folder name
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        counts = {}

        for img_path in tmp_path.rglob("*"):
            if img_path.suffix.lower() not in image_exts:
                continue

            # Find which folder_map key matches any parent directory name
            issue_type = None
            for part in img_path.parts:
                part_lower = part.lower()
                for key, val in folder_map.items():
                    if key.lower() in part_lower:
                        issue_type = val
                        break
                if issue_type is not None:
                    break

            if issue_type is None:
                continue
            if counts.get(issue_type, 0) >= limit:
                continue

            dest_dir = _ensure_dir(DATASET_DIR / issue_type)
            if not dry_run:
                ts = f"{ds_id.replace('/','_').replace('-','_')}_{counts.get(issue_type,0):05d}"
                if _copy_image_file(img_path, dest_dir, prefix=f"kg_{ts}_"):
                    counts[issue_type] = counts.get(issue_type, 0) + 1
            else:
                counts[issue_type] = counts.get(issue_type, 0) + 1

        for k, v in counts.items():
            results[k] = results.get(k, 0) + v

    return results


# ── Roboflow downloader ───────────────────────────────────────────────────────

def download_roboflow(source: dict, limit: int, dry_run: bool) -> dict:
    """Download images from Roboflow Universe. Requires ROBOFLOW_API_KEY env var."""
    results = {}

    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        log.warning("  ROBOFLOW_API_KEY not set — skipping. Get a free key at https://app.roboflow.com")
        return results

    try:
        from roboflow import Roboflow
    except ImportError:
        log.warning("  roboflow package not installed. Run: pip install roboflow")
        return results

    workspace = source["workspace"]
    project   = source["project"]
    version   = source.get("version", 1)
    label_map = source.get("label_map", {})

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            rf      = Roboflow(api_key=api_key)
            proj    = rf.workspace(workspace).project(project)
            dataset = proj.version(version).download("folder", location=str(tmp_path), overwrite=True)
        except Exception as e:
            log.warning(f"  Roboflow download failed for {workspace}/{project}: {e}")
            return results

        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        counts: dict = {}

        for img_path in tmp_path.rglob("*"):
            if img_path.suffix.lower() not in image_exts:
                continue

            # Match issue type from parent folder name or label_map
            issue_type = None
            for part in img_path.parts:
                part_lower = part.lower()
                for key, val in label_map.items():
                    if key.lower() in part_lower:
                        issue_type = val
                        break
                if issue_type:
                    break

            if issue_type is None:
                continue

            existing = _count_existing(DATASET_DIR / issue_type)
            if existing + counts.get(issue_type, 0) >= limit:
                continue

            dest_dir = _ensure_dir(DATASET_DIR / issue_type)
            if not dry_run:
                if _copy_image_file(img_path, dest_dir, prefix="rf_"):
                    counts[issue_type] = counts.get(issue_type, 0) + 1
            else:
                counts[issue_type] = counts.get(issue_type, 0) + 1

        for k, v in counts.items():
            results[k] = results.get(k, 0) + v

    return results


# ── Web scrape downloader ─────────────────────────────────────────────────────

def download_web_scrape(source: dict, limit: int, dry_run: bool) -> dict:
    """Scrape images from Bing Image Search using icrawler. No credentials needed."""
    results = {}

    try:
        from icrawler.builtin import BingImageCrawler
    except ImportError:
        log.warning("  icrawler not installed — skipping. Run: pip install icrawler")
        return results

    queries   = source.get("queries", [])
    # Spread the per-type limit across queries evenly
    per_query = max(1, limit // max(len(queries), 1))

    counts: dict = {}

    for q in queries:
        query      = q["query"]
        issue_type = q["issue"]

        existing = _count_existing(DATASET_DIR / issue_type)
        already  = counts.get(issue_type, 0)
        need     = limit - existing - already
        if need <= 0:
            log.info(f"  '{issue_type}' already at limit — skipping query")
            continue

        fetch = min(per_query, need)
        log.info(f"  Bing search: \"{query}\" → {issue_type} (up to {fetch})")

        if dry_run:
            counts[issue_type] = counts.get(issue_type, 0) + fetch
            continue

        dest_dir = _ensure_dir(DATASET_DIR / issue_type)

        with tempfile.TemporaryDirectory() as tmp:
            try:
                import logging as _logging
                # Silence icrawler's noisy loggers
                for noisy in ("icrawler", "urllib3", "requests"):
                    _logging.getLogger(noisy).setLevel(_logging.ERROR)

                crawler = BingImageCrawler(
                    storage={"root_dir": tmp},
                    downloader_threads=4,
                )
                crawler.crawl(
                    keyword=query,
                    max_num=fetch,
                    file_idx_offset=0,
                )
            except Exception as e:
                log.warning(f"  Crawl failed for \"{query}\": {e}")
                continue

            image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
            saved = 0
            for img_path in Path(tmp).rglob("*"):
                if img_path.suffix.lower() not in image_exts:
                    continue
                prefix = f"web_{issue_type}_{query[:20].replace(' ','_')}_"
                if _copy_image_file(img_path, dest_dir, prefix=prefix):
                    saved += 1

            counts[issue_type] = counts.get(issue_type, 0) + saved
            log.info(f"    saved {saved} images → {issue_type}")

    for k, v in counts.items():
        results[k] = results.get(k, 0) + v

    return results


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(category_filter: Optional[str], limit: int, dry_run: bool):
    log.info("=" * 60)
    log.info("AquaSense AI — Dataset Importer")
    log.info(f"  Dataset dir : {DATASET_DIR}")
    log.info(f"  Max per type: {limit} images")
    log.info(f"  Dry run     : {dry_run}")
    log.info("=" * 60)

    # Show current counts
    log.info("\nCurrent dataset:")
    for issue in ALL_ISSUES:
        n = _count_existing(DATASET_DIR / issue)
        if n:
            log.info(f"  {issue:<30} {n} images")

    # Determine which issues to populate
    if category_filter:
        target_issues = set(CATEGORIES.get(category_filter, []))
        if not target_issues:
            log.error(f"Unknown category: {category_filter}. Choose from: {list(CATEGORIES)}")
            sys.exit(1)
    else:
        target_issues = set(ALL_ISSUES)

    log.info(f"\nTarget issue types ({len(target_issues)}): {sorted(target_issues)}\n")

    total_added = {}

    for source in SOURCES:
        # Skip if none of its covered issues are in target
        covers = set(source.get("covers", []))
        if not covers.intersection(target_issues):
            continue

        log.info(f"\n{'─'*50}")
        log.info(f"Source: {source['name']}")

        src_type = source["type"]
        if src_type == "huggingface":
            added = download_huggingface(source, limit, dry_run)
        elif src_type == "kaggle_dataset":
            added = download_kaggle(source, limit, dry_run)
        elif src_type == "roboflow":
            added = download_roboflow(source, limit, dry_run)
        elif src_type == "web_scrape":
            added = download_web_scrape(source, limit, dry_run)
        else:
            log.warning(f"  Unknown source type: {src_type}")
            added = {}

        for k, v in added.items():
            total_added[k] = total_added.get(k, 0) + v
            log.info(f"  +{v:>4}  →  {k}")

    # Final summary
    log.info(f"\n{'='*60}")
    log.info("SUMMARY — images added this run:")
    grand_total = 0
    for issue in ALL_ISSUES:
        n = total_added.get(issue, 0)
        existing = _count_existing(DATASET_DIR / issue)
        if n or existing:
            log.info(f"  {issue:<30}  +{n:<5}  (total: {existing})")
        grand_total += n
    log.info(f"\nTotal new images: {grand_total}")
    if dry_run:
        log.info("(DRY RUN — no files were written)")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Import public agricultural datasets into AquaSense AI")
    parser.add_argument("--category", choices=list(CATEGORIES), default=None,
                        help="Only import one category (default: all)")
    parser.add_argument("--limit", type=int, default=300,
                        help="Max images per issue type (default: 300)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded without saving files")
    args = parser.parse_args()
    run(args.category, args.limit, args.dry_run)


if __name__ == "__main__":
    main()
