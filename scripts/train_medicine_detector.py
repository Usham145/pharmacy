from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from math import isfinite
from pathlib import Path

import yaml
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATASET_SOURCE = "https://www.kaggle.com/datasets/anshu0saini/blister-packaging"
DATASET_ROBOFLOW_SOURCE = "https://universe.roboflow.com/anshus-vision-space/meds-hvlge-hwrbw/dataset/2"


def normalize_dataset(source: Path, destination: Path) -> tuple[Path, dict[str, int], list[str]]:
    metadata_path = source / "data.yaml"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Dataset metadata was not found: {metadata_path}")
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    source_names = metadata.get("names")
    if isinstance(source_names, dict):
        source_names = [source_names[key] for key in sorted(source_names, key=lambda value: int(value))]
    if not isinstance(source_names, list) or not source_names:
        raise ValueError("Dataset data.yaml must define the source class names")

    image_counts: dict[str, int] = {}
    for split in ("train", "valid", "test"):
        source_images = source / split / "images"
        source_labels = source / split / "labels"
        if not source_images.is_dir() or not source_labels.is_dir():
            raise FileNotFoundError(f"Expected {split}/images and {split}/labels directories in {source}")

        destination_images = destination / split / "images"
        destination_labels = destination / split / "labels"
        destination_images.mkdir(parents=True, exist_ok=True)
        destination_labels.mkdir(parents=True, exist_ok=True)
        image_paths = [
            path for path in source_images.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        if not image_paths:
            raise ValueError(f"No images found in {source_images}")

        for image_path in image_paths:
            shutil.copy2(image_path, destination_images / image_path.name)
            label_path = source_labels / f"{image_path.stem}.txt"
            if not label_path.is_file():
                raise FileNotFoundError(f"Missing YOLO annotation for image: {image_path}")
            normalized_rows = []
            for line_number, row in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
                values = row.split()
                if len(values) != 5 and (len(values) < 7 or len(values) % 2 == 0):
                    raise ValueError(f"Invalid YOLO annotation at {label_path}:{line_number}")
                class_id = int(values[0])
                if not 0 <= class_id < len(source_names):
                    raise ValueError(f"Unknown source class {class_id} at {label_path}:{line_number}")
                coordinates = [float(value) for value in values[1:]]
                if not all(isfinite(value) and 0 <= value <= 1 for value in coordinates):
                    raise ValueError(f"Invalid normalized bounding box at {label_path}:{line_number}")
                if len(values) == 5:
                    center_x, center_y, box_width, box_height = coordinates
                else:
                    polygon_x = coordinates[::2]
                    polygon_y = coordinates[1::2]
                    left, right = min(polygon_x), max(polygon_x)
                    top, bottom = min(polygon_y), max(polygon_y)
                    center_x, center_y = (left + right) / 2, (top + bottom) / 2
                    box_width, box_height = right - left, bottom - top
                if box_width == 0 or box_height == 0:
                    raise ValueError(f"Bounding box has zero area at {label_path}:{line_number}")
                normalized_rows.append(
                    f"0 {center_x:.8f} {center_y:.8f} {box_width:.8f} {box_height:.8f}"
                )
            (destination_labels / label_path.name).write_text(
                "\n".join(normalized_rows) + ("\n" if normalized_rows else ""),
                encoding="utf-8",
            )
        image_counts[split] = len(image_paths)

    dataset_yaml = destination / "data.yaml"
    dataset_yaml.write_text(
        yaml.safe_dump(
            {
                "path": destination.resolve().as_posix(),
                "train": "train/images",
                "val": "valid/images",
                "test": "test/images",
                "names": ["medicine_package"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return dataset_yaml, image_counts, [str(name) for name in source_names]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune a generic medicine-package detector from YOLO-format package annotations."
    )
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Extracted Kaggle/Roboflow dataset directory")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "backend" / "models")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "pharmacy-medicine-detector-training",
    )
    parser.add_argument("--weights", default="yolov8n.pt", help="Ultralytics pretrained checkpoint")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--image-size", type=int, default=320, help="Training image size")
    parser.add_argument("--inference-size", type=int, default=640, help="ONNX export and test image size")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    if args.epochs < 1 or args.image_size < 32 or args.inference_size < 32 or args.batch_size < 1:
        parser.error("epochs and batch-size must be positive; image sizes must be at least 32")
    dataset_yaml, image_counts, source_names = normalize_dataset(
        args.dataset_dir.resolve(),
        args.work_dir.resolve() / "dataset",
    )
    training = YOLO(args.weights)
    training.train(
        data=str(dataset_yaml),
        epochs=args.epochs,
        imgsz=args.image_size,
        batch=args.batch_size,
        device=args.device,
        workers=0,
        patience=10,
        seed=42,
        project=str(args.work_dir.resolve() / "runs"),
        name="medicine-package",
        exist_ok=True,
        cache=False,
    )

    best_checkpoint = Path(training.trainer.best)
    if not best_checkpoint.is_file():
        raise FileNotFoundError(f"Training did not produce the expected best checkpoint: {best_checkpoint}")
    best_model = YOLO(str(best_checkpoint))
    test_metrics = best_model.val(
        data=str(dataset_yaml),
        split="test",
        imgsz=args.inference_size,
        device=args.device,
        workers=0,
    )
    exported_model = Path(
        best_model.export(format="onnx", imgsz=args.inference_size, opset=12, simplify=False)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "medicine_package_detector.onnx"
    shutil.copy2(exported_model, model_path)

    metric_values: dict[str, float] = {
        key: float(value)
        for key, value in test_metrics.results_dict.items()
        if isinstance(value, (int, float))
    }
    report = {
        "dataset": DATASET_SOURCE,
        "dataset_source": DATASET_ROBOFLOW_SOURCE,
        "dataset_license": "CC BY 4.0 (per the included Roboflow attribution files)",
        "kaggle_listing_license": "MIT (conflicts with the bundled CC BY 4.0 attribution)",
        "source_classes_collapsed_to": "medicine_package",
        "source_class_names": source_names,
        "images_by_split": image_counts,
        "checkpoint": args.weights,
        "training_framework_license": "AGPL-3.0 (Ultralytics)",
        "epochs_requested": args.epochs,
        "epochs_completed": training.trainer.epoch + 1,
        "training_image_size": args.image_size,
        "inference_image_size": args.inference_size,
        "batch_size": args.batch_size,
        "device": args.device,
        "test_metrics": metric_values,
        "onnx_model": str(model_path),
    }
    (args.output_dir / "medicine_package_training_metrics.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
