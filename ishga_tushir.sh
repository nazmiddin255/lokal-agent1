#!/usr/bin/env bash
# Local_model1 ni ishga tushirish: server + brauzer.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PY=".venv/bin/python"
URL="http://127.0.0.1:5000"

if [ ! -x "$PY" ]; then
  echo "Xato: .venv topilmadi ($PWD/.venv)"; exit 1
fi

if ! curl -s -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ogohlantirish: Ollama javob bermayapti (http://localhost:11434). 'ollama serve' ishlayaptimi?"
fi

# server allaqachon ishlayotgan bo'lsa — faqat brauzerni och
if curl -s -m 2 "$URL/api/holat" >/dev/null 2>&1; then
  echo "Server allaqachon ishlayapti: $URL"
  xdg-open "$URL" >/dev/null 2>&1 &
  exit 0
fi

"$PY" server.py &
PID=$!
trap 'kill $PID 2>/dev/null' INT TERM

for _ in $(seq 1 30); do
  if curl -s -m 1 "$URL/api/holat" >/dev/null 2>&1; then break; fi
  sleep 0.3
done
xdg-open "$URL" >/dev/null 2>&1 &
echo "Tayyor: $URL   (to'xtatish: Ctrl+C)"
wait $PID
