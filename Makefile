test:
	python -m pytest -v tests

list-html:
	python -m scripts.process_pages

repo:
	python -m scripts.repo_access

img:
	python -m scripts.fetch_details

store:
	python -m scripts.store_image

clean:
	rm -rf data/html/*
	rm -f data/metadata.db*

all:
	make clean
	make repo
	make list-html
	make img
