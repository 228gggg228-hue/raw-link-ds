import os
import staypresent

# Простой веб-ответ, чтобы Render видел, что сервис жив
staypresent.web.json({"status": "running", "service": "raw-link-ds"})

# Запускаем бота из bot.py на порту, который выдаёт Render
staypresent.run(
    "bot.py",
    port=int(os.getenv("PORT", 8080))
)
