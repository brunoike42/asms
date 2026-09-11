import tokenize

path = r"apps\core\models.py"
try:
    with open(path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type == tokenize.STRING and (tok.end[0] - tok.start[0] > 0):
                preview = tok.string[:60].replace("\n", "\\n")
                print(f"multi-line STRING: lines {tok.start[0]}-{tok.end[0]}  -> {preview!r}")
except (tokenize.TokenizeError, SyntaxError, IndentationError) as e:
    print(f"\nTokenizer stopped with: {type(e).__name__}: {e}")
