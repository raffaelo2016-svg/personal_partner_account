#!/usr/bin/env bash
# Показывает точки отката и возвращает к нужной.
#
# Без аргументов — список точек отката (меток restore-*) и последних коммитов.
# С аргументом — предложит вернуться к этой точке.
#
#   scripts/git-restore.sh
#   scripts/git-restore.sh restore-2026-11-06
set -euo pipefail
cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
  echo "Точки отката:"
  found=0
  while read -r t; do
    [ -n "$t" ] || continue
    found=1
    printf '  %-24s %s\n' "$t" "$(git log -1 --format='%ad  %s' --date=short "$t")"
  done < <(git tag -l 'restore-*' --sort=-creatordate)
  [ "$found" -eq 1 ] || echo "  (пока нет ни одной метки)"
  echo
  echo "Последние 10 сохранений в текущей ветке:"
  git log --oneline -10
  echo
  echo "Вернуться к точке:  scripts/git-restore.sh <метка>"
  exit 0
fi

ref="$1"
git rev-parse --verify "$ref^{commit}" >/dev/null 2>&1 || {
  echo "Метка или коммит не найдены: $ref"
  exit 1
}

echo "Выбрано: $(git log -1 --format='%h  %ad  %s' --date=short "$ref")"
echo
echo "1 — создать ветку от этой точки (безопасно, текущая работа не пострадает)"
echo "2 — откатить текущую ветку к этой точке (всё, что сделано после, уйдёт из ветки)"
read -r -p "Выберите 1 или 2: " mode

case "$mode" in
  1)
    name="restore-$(date +%Y-%m-%d-%H%M)"
    git switch -c "$name" "$ref"
    echo "Создана ветка $name. Проверьте приложение и продолжайте в ней."
    ;;
  2)
    echo "Сейчас: $(git branch --show-current) на $(git rev-parse --short HEAD)"
    read -r -p "Точно откатить? Напишите yes: " ok
    [ "$ok" = "yes" ] || { echo "Отменено."; exit 1; }
    git reset --hard "$ref"
    echo "Ветка откачена к $ref."
    echo "Отправить откат на GitHub: git push --force-with-lease"
    ;;
  *)
    echo "Неизвестный выбор — ничего не сделано."
    exit 1
    ;;
esac
