#!/usr/bin/env bash
# Сохраняет текущие изменения в git и отправляет ветку на GitHub.
#
# Использование:
#   scripts/git-save.sh "кратко, что изменилось"
#
# Скрипт не сохраняет секреты и внутренние документы: они перечислены
# в .gitignore и в коммит не попадут.
set -euo pipefail
cd "$(dirname "$0")/.."

msg="${1:-}"
if [ -z "$msg" ]; then
  echo "Нужно описание изменений, например:"
  echo '  scripts/git-save.sh "добавил фильтр в список клиентов"'
  exit 1
fi

branch="$(git branch --show-current)"
if [ -z "$branch" ]; then
  echo "ОШИБКА: репозиторий не на ветке. Выполните: git switch dev"
  exit 1
fi

if [ "$branch" = "main" ]; then
  echo "ВНИМАНИЕ: вы на ветке main. Отправка в main запускает выкладку на прод."
  read -r -p "Продолжить? (y/N): " answer
  [ "$answer" = "y" ] || { echo "Отменено."; exit 1; }
fi

git add -A
if git diff --cached --quiet; then
  echo "Изменений нет — сохранять нечего."
  exit 0
fi

git commit -q -m "$msg"
git push -u origin "$branch"
echo
echo "Сохранено: $(git log --oneline -1)"
