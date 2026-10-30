#!/bin/sh
# usage: ./run.sh exp/e1_real_code_syntax.py
exec uv run -q --with tiktoken --with openai --with tree-sitter-language-pack python "$@"
