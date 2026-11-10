#!/usr/bin/env python3
"""Генерирует frontend/src/styles/legacy-colors.css.

Зачем: приложение собрано на Tailwind v4, где вся палитра задана в oklch(),
а часть утилит (полупрозрачные фоны, рамки) — через color-mix(). Браузеры без
поддержки этих функций (Chrome/Edge < 111, Safari < 16.4, Firefox < 113, старые
сборки Chromium-браузеров) отбрасывают такие значения. В результате:

  * background-color кнопок становится прозрачным,
  * color: #fff (это не oklch) остаётся белым,
  * рамки красятся в currentColor (чёрный).

Главная кнопка «Создать карточку клиента» есть в DOM, но выглядит как белый
прямоугольник на белом фоне — то есть «пропадает».

Скрипт пересчитывает палитру oklch → sRGB и собирает unlayered-блок
`@supports not (color: oklch(0% 0 0))`, который перекрывает @layer theme
только в браузерах без oklch(). В современных браузерах блок не применяется.

Запуск (из корня репозитория, после сборки фронтенда):

    cd frontend && npx vite build
    cd .. && python3 scripts/generate_legacy_colors.py

Скрипт сам находит свежий CSS в frontend/dist/assets и перезаписывает
frontend/src/styles/legacy-colors.css.
"""

from __future__ import annotations

import glob
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME = os.path.join(ROOT, "frontend", "src", "styles", "theme.css")
OUT = os.path.join(ROOT, "frontend", "src", "styles", "legacy-colors.css")

OKLCH = re.compile(r"oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)")
RGBA = re.compile(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)")
COLOR_MIX = re.compile(
    r"color-mix\(in oklab,\s*(currentcolor|var\((--[\w-]+)\))\s*([\d.]+)%\s*,\s*transparent\)"
)


def oklch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    h = math.radians(H)
    a, b = C * math.cos(h), C * math.sin(h)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_**3, m_**3, s_**3
    lin = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )

    def encode(x: float) -> int:
        x = max(0.0, min(1.0, x))
        x = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        return round(x * 255)

    return tuple(encode(c) for c in lin)  # type: ignore[return-value]


def parse_color(value: str):
    """Возвращает (r, g, b, alpha) или None."""
    v = value.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            h += "ff"
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255)
    m = OKLCH.match(v)
    if m:
        L = float(m.group(1))
        if m.group(2) == "%":
            L /= 100
        r, g, b = oklch_to_rgb(L, float(m.group(3)), float(m.group(4)))
        return r, g, b, 1.0
    m = RGBA.match(v)
    if m:
        alpha = float(m.group(4)) if m.group(4) else 1.0
        return int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3))), alpha
    return None


def fmt(color, extra_alpha: float = 1.0) -> str:
    r, g, b, a = color
    a *= extra_alpha
    if a >= 0.999:
        return "#%02x%02x%02x" % (r, g, b)
    return "rgba(%d, %d, %d, %g)" % (r, g, b, round(a, 3))


def block(src: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", src, re.S)
    return m.group(1) if m else ""


def find_built_css() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    files = glob.glob(os.path.join(ROOT, "frontend", "dist", "assets", "index-*.css"))
    if not files:
        sys.exit("Не найден frontend/dist/assets/index-*.css — сначала соберите фронтенд")
    return max(files, key=os.path.getmtime)


def main() -> None:
    css_path = find_built_css()
    css = open(css_path, encoding="utf-8").read()
    theme = open(THEME, encoding="utf-8").read()

    # 1. Палитра Tailwind: @layer theme -> :root,:host{...}
    m = re.search(r"@layer theme\{:root,:host\{(.*?)\}\}", css, re.S)
    palette = {}
    for name, val in re.findall(r"(--color-[\w-]+):([^;]+);", m.group(1) if m else ""):
        c = parse_color(val)
        if c:
            palette[name] = c

    # 2. Токены приложения из theme.css
    tokens = {}
    for name, val in re.findall(r"(--[\w-]+):\s*([^;]+);", block(theme, ":root")):
        c = parse_color(val)
        if c:
            tokens[name] = c
    dark_tokens = {}
    for name, val in re.findall(r"(--[\w-]+):\s*([^;]+);", block(theme, ".dark")):
        c = parse_color(val)
        if c:
            dark_tokens[name] = c

    used = set(re.findall(r"var\((--[\w-]+)\)", css))

    pal = {k: v for k, v in palette.items() if k in used}
    tok = {k: v for k, v in tokens.items() if k in used and k not in pal}
    dark = {k: v for k, v in dark_tokens.items() if k in used}

    # 3. Полупрозрачные утилиты, собранные через color-mix() — в старых браузерах
    #    они вообще отсутствуют в CSS (Tailwind кладёт их в @supports).
    alpha_rules = []
    for m in re.finditer(r"@supports \(color:color-mix\(in lab,red,red\)\)\{", css):
        depth, j = 1, m.end()
        while j < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        body = css[m.end() : j - 1]
        for selector, decl in re.findall(r"([^{}]+)\{([^{}]*color-mix[^{}]*)\}", body):
            selector = selector.strip()
            prop_m = re.match(r"\s*([a-z-]+):\s*color-mix", decl)
            mix_m = COLOR_MIX.search(decl)
            if not selector.startswith(".") or not prop_m or not mix_m:
                continue
            token = mix_m.group(2)
            if mix_m.group(1) == "currentcolor" or not token:
                continue
            is_dark = selector.startswith(".dark\\:")
            base = (
                (dark.get(token) if is_dark else None)
                or pal.get(token)
                or tok.get(token)
                or dark.get(token)
            )
            if not base:
                continue
            alpha = float(mix_m.group(3)) / 100
            alpha_rules.append(
                "  %s { %s: %s; }" % (selector, prop_m.group(1), fmt(base, alpha))
            )

    def rule_lines(mapping):
        return "\n".join("    %s: %s;" % (k, fmt(v)) for k, v in sorted(mapping.items()))

    out = [
        "/*",
        " * СГЕНЕРИРОВАННЫЙ ФАЙЛ — правьте scripts/generate_legacy_colors.py.",
        " *",
        " * Фолбэк цветов для браузеров без поддержки oklch()/color-mix():",
        " * Chrome/Edge < 111, Safari < 16.4, Firefox < 113, старые сборки",
        " * Chromium-браузеров (устаревшие Яндекс.Браузер, Opera, WebView и т.п.).",
        " *",
        " * Без него все цвета палитры становятся невалидными: фон кнопок — прозрачный,",
        " * текст — белым на белом, и кнопка «Создать карточку клиента» есть в DOM,",
        " * но не видна. Значения пересчитаны oklch → sRGB из палитры Tailwind,",
        " * поэтому в старых браузерах цвета выглядят так же, как в современных.",
        " *",
        " * В браузерах с поддержкой oklch() блок целиком пропускается.",
        " */",
        "@supports not (color: oklch(0% 0 0)) {",
        "  :root {",
        rule_lines(pal),
    ]
    if tok:
        out.append(rule_lines(tok))
    out.append("  }")
    if dark:
        out += ["", "  .dark {", rule_lines(dark), "  }"]
    if alpha_rules:
        out += ["", "  /* Полупрозрачные фоны и рамки (в Tailwind — через color-mix) */"]
        out += sorted(set(alpha_rules))
    out.append("}")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    print(
        "legacy-colors.css: палитра %d, токены %d, тёмная тема %d, полупрозрачные %d"
        % (len(pal), len(tok), len(dark), len(set(alpha_rules)))
    )


if __name__ == "__main__":
    main()
