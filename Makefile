.PHONY: run install clean

run:
	uv run python -m nicode_claw

install:
	uv sync

clean:
	rm -rf tmp/ data/ __pycache__ .pytest_cache
