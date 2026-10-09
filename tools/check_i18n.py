"""Syntax-check the page scripts and check that every translated text has a Malay entry.

Run from the project folder:  .venv\\Scripts\\python tools\\check_i18n.py
Needs the esprima parser (development only, not in requirements.txt):  .venv\\Scripts\\python -m pip install esprima
"""
import re
from pathlib import Path

import esprima

S = Path(__file__).resolve().parent.parent / "static"
trees = {}
for name in ("i18n.js", "app.js", "payroll.js"):
    try:
        src = (S / name).read_text(encoding="utf-8")
        src = re.sub(r"catch \{", "catch (_e) {", src)             # optional catch binding: valid, too new for esprima
        src = src.replace("?.", ".").replace("??", "||")              # same for ?. and ?? (meaning is irrelevant here)
        trees[name] = esprima.parseScript(src, {"range": True})
        print("syntax ok:", name)
    except Exception as exc:
        print("SYNTAX ERROR:", name, exc)

# Malay keys: the string keys of the MS object literal
ms_keys = set()
def walk(node, fn):
    if isinstance(node, list):
        for n in node:
            walk(n, fn)
    elif hasattr(node, "type"):
        fn(node)
        for k, v in node.__dict__.items():
            if k not in ("range", "loc") and (isinstance(v, list) or hasattr(v, "type")):
                walk(v, fn)

def find_ms(node):
    if node.type == "VariableDeclarator" and getattr(node.id, "name", "") == "MS":
        for p in node.init.properties:
            ms_keys.add(p.key.value if p.key.type == "Literal" else p.key.name)
walk(trees["i18n.js"], find_ms)
print("Malay entries:", len(ms_keys))

# every t("...") / tn(n, "...", "...") with literal strings
used = []
def find_calls(node):
    if node.type == "CallExpression" and getattr(node.callee, "name", "") in ("t", "tn"):
        args = node.arguments if node.callee.name == "t" else node.arguments[1:3]
        for a in args[: (1 if node.callee.name == "t" else 2)]:
            if a.type == "Literal" and isinstance(a.value, str):
                used.append(a.value)
for name in ("app.js", "payroll.js"):
    walk(trees[name], find_calls)
# data-t texts in index.html
html = (S / "index.html").read_text(encoding="utf-8")
for m in re.finditer(r"<(\w+)([^>]*?)\sdata-t(?:\s[^>]*)?>(.*?)</\1>", html, re.S):
    text = re.sub(r"\s+", " ", m.group(3).replace("&larr;", "←")).strip()
    used.append(text)
for m in re.finditer(r'(title|aria-label)="([^"]+)"[^>]*data-t-(?:title|aria)', html):
    used.append(m.group(2))
# words looked up through variables
used += ["January", "Sun", "Working day", "benefit", "leave", "allowance", "deduction", "Day", "Type", "Hours written", "Note",
         "Clear", "Change the language"]
missing = sorted(set(u for u in used if u not in ms_keys))
print("texts used:", len(set(used)), "| missing Malay:", len(missing))
for m in missing:
    print("  MISSING:", m)
