.PHONY: test docs
test:
	poetry run pytest

docs:
	cd docs; poetry run sphinx-build -b html . _build; cd -
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