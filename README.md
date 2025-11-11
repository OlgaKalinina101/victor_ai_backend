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

Запуск: 
net start postgresql-x64-17
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d victor_db
psql -U postgres -d victor_db

SELECT * FROM music_tracks WHERE filename LIKE E'%\\xE2\\x80\\xB3%';
SELECT * FROM music_tracks WHERE filename LIKE E'%\\xE2\\x80\\xB3%';
UPDATE chat_meta SET model = 'deepseek-chat' WHERE account_id = 'test_user';

SELECT * FROM track_user_descriptions WHERE id = '38';

ngrok http 8000
uvicorn main:app --reload --host 0.0.0.0 --port 8000

Invoke-RestMethod -Method GET -Uri "http://localhost:8099/usage?account_id=test_user"

 ACPI\MSFT0001\4&215258E3&0
& "C:\Users\Alien\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse tcp:8080 tcp:8080

git remote set-url origin https://github.com/OlgaKalinina101/victor_ai_backend.git

.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

https://download.osgeo.org/postgis/windows/pg17/ - обязательно!

Перезапустить клавиатуру: 
$instanceId = "ACPI\VEN_MSFT&DEV_0001\4&2C0E0F0F&0"

Disable-PnpDevice -InstanceId $instanceId -Confirm:$false
Start-Sleep -Seconds 2
Enable-PnpDevice -InstanceId $instanceId -Confirm:$false
Write-Output "Клавиатура перезапущена."


```text
Victor_AI_Core/
├── api/
│   ├── __init__.py
│   ├── assistant.py                       #Эндпоинт assistant 
├── core
│   └── firebase/
│       ├── __init__.py
│       ├── firebase_tokens.json            #временная БД для токена
│       └──message_router.py                #роутер модель для распознавания в какой tool отправить то, что прилетело на эндпоинт
├── database
├── models/
│   ├── __init__.py
│   ├── assistant_models.py                 #состояния ассистента
│   ├── communication_enums.py              #категории сообщений, типы сообщений
│   ├── communication_models.py             # MessageMetadata, DialogContext, DialogQuestionProfile, KeyInformation
│   ├── firebase.py                         #pydantic-модель для токена firebase
│   ├── request.py                          #pydantic-модель для эндпоинта
│   ├── response.py                         #pydantic-модель для эндпоинта
│   ├── user_enums.py                       # Gender, RelationshipLevel, EventType
│   └── user_models.py                      # UserProfile и всё, что связано с пользователем
├── tests/
├── tools/
│   ├── __init__.py
│   └──chat
│       ├── __init__.py
│       └── chat_tool.py                    #вызов диалога (надо переименовать файлик как-то, чтобы не ассоциировался с чатом)
│   └── reminders
│       ├── __init__.py
│       ├── reminder_chain.py               #цепочка распознавателя напоминалок
│       ├── reminder_store.py               #запись напоминалок в бд
│       └── reminder_tool.py                #вызов цепочки напоминалок
├── .env
├── firebase_tokens.json                    
├── main.py                                 #точка входа Fast_API
├── README.md
├── reminders.json                          #временная БД напоминалок
├── requirements.txt                        #зависимости проекта
└── settings.py                             #pydantic_settings
```







