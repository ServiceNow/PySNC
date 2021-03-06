.PHONY: test docs
init:
	pip install pipenv --upgrade
	pipenv install --dev

test:
	python setup.py test

docs:
	cd docs && pipenv run make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at docs/_build/html/index.html.\n\033[0m"

gh-pages:
	git checkout gh-pages
	git checkout master docs
	git reset HEAD
	cd docs && make html && cd -
	cp -rf docs/_build/html/* ./
	rm -rf ./docs
	git add -A
	git commit -m 'Generated gh-pages' && git push origin gh-pages && git checkout master

