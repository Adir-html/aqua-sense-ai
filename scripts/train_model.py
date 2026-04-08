"""
AquaSense AI — ONNX Model Trainer
==================================
Fine-tunes MobileNetV3-Small (pretrained on ImageNet) for binary
faulty/normal irrigation classification, then exports to ONNX.

Usage:
  python scripts/train_model.py
  python scripts/train_model.py --epochs 15 --lr 0.0005
  python scripts/train_model.py --skip-scrape   # if normal/ images already exist

Output:
  models/model.onnx

Requirements:
  pip install torch torchvision onnx icrawler pillow
"""

import argparse
import logging
import os
import random
import shutil
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("train_model")

REPO_ROOT    = Path(__file__).resolve().parents[1]
DATASET_DIR  = REPO_ROOT / "dataset"
MODEL_DIR    = REPO_ROOT / "models"
MODEL_PATH   = MODEL_DIR / "model.onnx"
NORMAL_DIR   = DATASET_DIR / "_normal"

# ImageNet normalisation — must match preprocess.py
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

# Issue type folders = faulty class
FAULTY_FOLDERS = [
    "algae_bloom", "dry_patch", "waterlogging", "uneven_distribution",
    "disease_pressure", "pipe_leak", "pipe_damage", "broken_sprinkler",
    "clogged_emitter", "pressure_problem", "filter_blockage",
    "turbid_water", "contamination", "salinity_stress", "pathogen_risk",
    "runoff", "soil_erosion", "wilting", "overwatering_symptoms",
    "nutrient_deficiency",
]

NORMAL_QUERIES = [
    "healthy green crop field irrigation",
    "normal irrigation sprinkler working",
    "clean water irrigation drip system",
    "healthy farmland crops growing",
    "normal water pipe intact",
    "working irrigation system field",
    "healthy plants water drops",
    "clean clear water stream",
]


def scrape_normal_images(target: int = 300):
    """Download normal/healthy images via Bing image search."""
    try:
        from icrawler.builtin import BingImageCrawler
    except ImportError:
        log.error("icrawler not installed. Run: pip install icrawler")
        return 0

    NORMAL_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(NORMAL_DIR.glob("*.jpg")) + list(NORMAL_DIR.glob("*.png"))
    if len(existing) >= target:
        log.info(f"  Already have {len(existing)} normal images — skipping scrape")
        return len(existing)

    per_query = max(1, (target - len(existing)) // len(NORMAL_QUERIES))
    saved = len(existing)

    import logging as _logging
    for noisy in ("icrawler", "urllib3", "requests"):
        _logging.getLogger(noisy).setLevel(_logging.ERROR)

    for query in NORMAL_QUERIES:
        if saved >= target:
            break
        log.info(f"  Bing: \"{query}\" (up to {per_query})")
        with tempfile.TemporaryDirectory() as tmp:
            try:
                crawler = BingImageCrawler(storage={"root_dir": tmp}, downloader_threads=4)
                crawler.crawl(keyword=query, max_num=per_query)
            except Exception as e:
                log.warning(f"  Crawl failed: {e}")
                continue

            image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
            for p in Path(tmp).rglob("*"):
                if p.suffix.lower() not in image_exts:
                    continue
                dest = NORMAL_DIR / f"normal_{saved:06d}{p.suffix}"
                shutil.copy2(p, dest)
                saved += 1
                if saved >= target:
                    break

    log.info(f"  Normal images total: {saved}")
    return saved


def build_dataset(max_per_class: int = 500):
    """Build a temporary train/val folder structure for torchvision ImageFolder."""
    import torch
    from torchvision import datasets, transforms
    from torch.utils.data import DataLoader, WeightedRandomSampler

    # Collect faulty images
    faulty_images = []
    for folder in FAULTY_FOLDERS:
        d = DATASET_DIR / folder
        if d.exists():
            faulty_images += list(d.glob("*.jpg")) + list(d.glob("*.jpeg")) + \
                             list(d.glob("*.png")) + list(d.glob("*.webp"))

    random.shuffle(faulty_images)
    faulty_images = faulty_images[:max_per_class]

    # Collect normal images
    normal_images = list(NORMAL_DIR.glob("*.jpg")) + list(NORMAL_DIR.glob("*.jpeg")) + \
                    list(NORMAL_DIR.glob("*.png")) + list(NORMAL_DIR.glob("*.webp"))
    random.shuffle(normal_images)
    normal_images = normal_images[:max_per_class]

    log.info(f"  Dataset: {len(faulty_images)} faulty, {len(normal_images)} normal")
    if not faulty_images or not normal_images:
        raise RuntimeError("Not enough images in either class to train.")

    # Split 80/20 train/val
    def split(lst):
        n = max(1, int(len(lst) * 0.8))
        return lst[:n], lst[n:]

    f_train, f_val = split(faulty_images)
    n_train, n_val = split(normal_images)

    # Build temp directory structure
    tmp_root = Path(tempfile.mkdtemp(prefix="aquasense_train_"))
    for split_name, pairs in [
        ("train", [(f_train, "faulty"), (n_train, "normal")]),
        ("val",   [(f_val,  "faulty"), (n_val,  "normal")]),
    ]:
        for imgs, label in pairs:
            dest = tmp_root / split_name / label
            dest.mkdir(parents=True, exist_ok=True)
            for img_path in imgs:
                try:
                    shutil.copy2(img_path, dest / img_path.name)
                except Exception:
                    pass

    transform_train = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    transform_val = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    train_ds = datasets.ImageFolder(str(tmp_root / "train"), transform=transform_train)
    val_ds   = datasets.ImageFolder(str(tmp_root / "val"),   transform=transform_val)

    # Balanced sampler for uneven classes
    labels    = [s[1] for s in train_ds.samples]
    counts    = [labels.count(i) for i in range(len(train_ds.classes))]
    weights   = [1.0 / counts[l] for l in labels]
    sampler   = WeightedRandomSampler(weights, len(weights))

    train_loader = DataLoader(train_ds, batch_size=32, sampler=sampler,  num_workers=0, pin_memory=False)
    val_loader   = DataLoader(val_ds,   batch_size=32, shuffle=False,    num_workers=0, pin_memory=False)

    log.info(f"  Classes: {train_ds.class_to_idx}")
    return train_loader, val_loader, train_ds.class_to_idx, tmp_root


def train(epochs: int = 10, lr: float = 0.001):
    try:
        import torch
        import torch.nn as nn
        from torchvision import models
    except ImportError:
        log.error("PyTorch not installed. Run: pip install torch torchvision")
        return False

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"  Device: {device}")

    train_loader, val_loader, class_to_idx, tmp_root = build_dataset()

    # Determine label order — runner.py expects index 0 = faulty, 1 = normal
    faulty_idx = class_to_idx.get("faulty", 0)
    normal_idx = class_to_idx.get("normal", 1)
    log.info(f"  Label map: faulty={faulty_idx}, normal={normal_idx}")

    # MobileNetV3-Small — tiny, fast, accurate enough for this task
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)

    # Replace classifier head for 2 classes
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, 2)
    model = model.to(device)

    # Freeze all layers except classifier for first 3 epochs, then unfreeze
    for param in model.features.parameters():
        param.requires_grad = False

    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    best_val_acc = 0.0
    best_state   = None

    for epoch in range(epochs):
        # Unfreeze all layers from epoch 3 onwards with lower LR
        if epoch == 3:
            for param in model.features.parameters():
                param.requires_grad = True
            optimizer = torch.optim.Adam(model.parameters(), lr=lr / 10)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs - epoch)
            log.info("  Unfroze backbone layers")

        # ── Train ──
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for imgs, lbls in train_loader:
            imgs, lbls = imgs.to(device), lbls.to(device)
            optimizer.zero_grad()
            out  = model(imgs)
            loss = criterion(out, lbls)
            loss.backward()
            optimizer.step()
            scheduler.step()
            train_loss    += loss.item() * imgs.size(0)
            train_correct += (out.argmax(1) == lbls).sum().item()
            train_total   += imgs.size(0)

        # ── Validate ──
        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for imgs, lbls in val_loader:
                imgs, lbls = imgs.to(device), lbls.to(device)
                out = model(imgs)
                val_correct += (out.argmax(1) == lbls).sum().item()
                val_total   += imgs.size(0)

        train_acc = train_correct / train_total if train_total else 0
        val_acc   = val_correct   / val_total   if val_total   else 0
        log.info(f"  Epoch {epoch+1}/{epochs} — loss: {train_loss/train_total:.4f}  "
                 f"train_acc: {train_acc:.3f}  val_acc: {val_acc:.3f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state   = {k: v.clone() for k, v in model.state_dict().items()}

    # Restore best weights
    if best_state:
        model.load_state_dict(best_state)
    log.info(f"  Best val accuracy: {best_val_acc:.3f}")

    # ── Export to ONNX ──
    MODEL_DIR.mkdir(exist_ok=True)
    model.eval().cpu()
    dummy = torch.zeros(1, 3, 224, 224)

    # Re-order output so index 0 = faulty, 1 = normal (matches runner.py)
    # If torchvision ImageFolder sorted "faulty" before "normal" alphabetically → correct already
    # If not, wrap with a permutation layer
    if faulty_idx != 0:
        log.info("  Reordering output to match faulty=0, normal=1")
        class ReorderedModel(torch.nn.Module):
            def __init__(self, base):
                super().__init__()
                self.base = base
            def forward(self, x):
                out = self.base(x)
                return out[:, [faulty_idx, normal_idx]]
        export_model = ReorderedModel(model)
    else:
        export_model = model

    import torch.onnx, io, contextlib
    # Suppress PyTorch's ONNX logger which uses emoji — breaks on Windows cp1252 terminals
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        torch.onnx.export(
            export_model, dummy, str(MODEL_PATH),
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        )
    log.info(f"  ONNX model saved to {MODEL_PATH}")

    # Cleanup temp dataset
    shutil.rmtree(tmp_root, ignore_errors=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",       type=int,   default=10)
    parser.add_argument("--lr",           type=float, default=0.001)
    parser.add_argument("--skip-scrape",  action="store_true")
    parser.add_argument("--normal-count", type=int,   default=300,
                        help="Number of normal images to scrape")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("AquaSense AI — Model Trainer")
    log.info("=" * 60)

    if not args.skip_scrape:
        log.info("\nStep 1: Scraping normal/healthy images…")
        scrape_normal_images(target=args.normal_count)
    else:
        log.info("\nStep 1: Skipping scrape (--skip-scrape)")

    log.info(f"\nStep 2: Training MobileNetV3-Small ({args.epochs} epochs, lr={args.lr})…")
    ok = train(epochs=args.epochs, lr=args.lr)

    if ok:
        log.info("\n✅ Done! Model saved to models/model.onnx")
        log.info("   Set MODEL_PATH=models/model.onnx in your .env (already the default)")
    else:
        log.error("\n❌ Training failed — check logs above")


if __name__ == "__main__":
    main()
