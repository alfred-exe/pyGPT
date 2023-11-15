# pyGPT
![Tag](https://img.shields.io/github/license/alfred-exe/pyGPT)
[![Downloads](https://static.pepy.tech/badge/pyGPT-api/month)](https://pepy.tech/project/pyGPT-api)

An (unofficial) [ChatGPT](https://chat.openai.com/) API made by yoinking code from [revChatGPT](https://github.com/acheong08/ChatGPT) and adapting it to use [tls-client](https://github.com/FlorianREGAZ/Python-Tls-Client).

## Installation
```bash
pip install pyGPT-api
```

## Requirements
[`tls-client`](https://github.com/FlorianREGAZ/Python-Tls-Client)
Python >= 3.9

## Getting started
An access token is required for this package to run correctly. You can get yours [here](https://chat.openai.com/api/auth/session) or open the [chat.openai.com](https://chat.openai.com) webpage, access the developer console, and get the token from `Application` -> `Cookies` -> `__Secure-next-auth.session-token`.

Below is a basic example that will let you converse with ChatGPT as much as you'd like.
```py
from pyGPT_api import AI

ai = AI("your_token_here")
while True:
    message = ""
    for data in ai.send_message(input(" > ")):
        message = data["message"]
    print("\nChatGPT:", message, "\n")
```
