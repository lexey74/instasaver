Бот для скачивания с Инсты
===========

## Бот для скачивания постов (видео, картинки и текст) из Instagram.

temp каталог используется для временного сохранения файлов. После отправки в телеграм, каталог очищается.

Логи пишутся в bot.log

Для начала работы бота надо установить вебхук: curl -X POST "https://api.telegram.org/bot<ТОКЕН>/setWebhook" -d "url=https://mcontrol.XXXX.co/bot1/"

Проверить, установлен ли Webhook: curl -X POST "https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo"

Перезапустите пользовательский systemd и включите службу:
```
systemctl --user daemon-reload
systemctl --user enable is.service
systemctl --user start is.service
```

Проверьте статус службы:
```
systemctl --user status is.service
```
