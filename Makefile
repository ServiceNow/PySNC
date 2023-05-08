.PHONY: test docs
test:
	poetry run pytest
	poetry run mypy

docs:
	cd docs; poetry install && poetry run make clean html; cd -
	@echo "\033[95m\n\nBuild successful! View the docs homepage at docs/_build/html/index.html.\n\033[0m"

gh-pages:
	git fetch origin gh-pages
	git checkout gh-pages
	git checkout master docs
	git checkout master pysnc
	git reset HEAD
	cd docs && make html && cd -
	cp -rf docs/_build/html/* ./
	#git add -A
	#git commit -m 'Generated gh-pages' && git push origin gh-pages && git checkout master