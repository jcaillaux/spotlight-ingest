test:
	python -m pytest -v tests

init-db:
	dvc repro init-db

fetch-pages:
	dvc repro fetch-pages

extract-metadata:
	dvc repro extract-metadata

fetch-details:
	dvc repro fetch-details

download-images:
	dvc repro download-images

embeddings:
	dvc repro compute-embeddings

all:
	dvc repro

clean:
	rm -rf data/html/*
	rm -f data/metadata.db*
