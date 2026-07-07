import duckdb
import numpy as np
import torch
from pathlib import Path
from time import perf_counter
from PIL import Image
from transformers import CLIPModel, CLIPProcessor
from loguru import logger
from config import metadata, IMG, LOGS

logger.add(LOGS / 'embeddings.log', rotation='5 MB')

MODEL_NAME = "openai/clip-vit-base-patch32"
BATCH_SIZE = 32

con = duckdb.connect(metadata)


def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    model = CLIPModel.from_pretrained(MODEL_NAME).to(device)
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    return model, processor, device


def get_pending_images():
    rows = con.execute("""
        SELECT i.url, i.path FROM images i
        LEFT JOIN embeddings e ON i.url = e.url
        WHERE i.path IS NOT NULL AND e.url IS NULL
    """).fetchall()
    return rows


def compute_batch(model, processor, device, paths):
    images = [Image.open(p).convert("RGB") for p in paths]
    inputs = processor(images=images, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy()


def main():
    start = perf_counter()
    model, processor, device = load_model()

    rows = get_pending_images()
    logger.info(f"{len(rows)} images to embed")

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        urls = [r[0] for r in batch]
        paths = [IMG / r[1] for r in batch]

        try:
            embeddings = compute_batch(model, processor, device, paths)
            con.executemany(
                "INSERT INTO embeddings (url, embedding) VALUES (?, ?) ON CONFLICT DO NOTHING",
                [(url, emb.tolist()) for url, emb in zip(urls, embeddings)]
            )
        except Exception as e:
            logger.warning(f"Batch starting at {batch_start} failed: {e}")

        done = min(batch_start + BATCH_SIZE, len(rows))
        logger.info(f"{done}/{len(rows)} ({100 * done / len(rows):.1f}%)")

    con.commit()
    total = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    elapsed = perf_counter() - start
    logger.success(f"Done. {total} embeddings stored. Finished in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
