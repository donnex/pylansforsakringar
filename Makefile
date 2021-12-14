
tests:
	pytest

coverage_base:
	coverage run -m pytest

coverage: coverage_base
	coverage report
	coverage xml

coverage_html: coverage_base
	coverage html


.PHONY: tests coverage_base coverage coverage_html
