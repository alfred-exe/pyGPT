from contextlib import suppress
from typing import Literal, Generator
from uuid import uuid4
from json import dumps, loads, decoder
from requests import exceptions
from tls_client import Session

from . import errors

class AI():
    def __init__(self, token : str, model : Literal["gpt-3.5", "gpt-4"] = "gpt-3.5", conversation_id : str = None):
        self.token = token
        self.model = model

        self.session = Session(client_identifier="chrome112")

        setattr(self.session, "url", "https://chat.openai.com")
        setattr(self.session, "token", self.token)

        self.calls = 0
        self.conversation_id = conversation_id
        self.parent_id = None
        self.conversation_mapping = { }

        self.disable_history = False

    def request(self, url : str, method : Literal["GET", "POST", "PUT", "PATCH"] = "GET", data : dict = None, json : dict = None, token : str = None, **kwargs):
        link = f"{self.session.url}{url}"

        key = token if token != None else self.session.token

        headers = {"Authorization": f"Bearer {key}"}

        if method == "GET":
            response = self.session.get(link, headers=headers, **kwargs)
        elif method == "POST":
            response = self.session.post(link, headers=headers, data=data, json=json, **kwargs)
        elif method == "PUT":
            response = self.session.put(link, headers=headers, data=data, json=json, **kwargs)
        elif method == "PATCH":
            response = self.session.patch(link, headers=headers, data=data, json=json, **kwargs)
        return response

    def __check_fields__(self, data : dict) -> bool:
        try:
            data["message"]["content"]
        except (TypeError, KeyError):
            return False
        return True

    def __send_request__(self, data : dict, auto_continue : bool = False, **kwargs) -> Generator[dict, None, None]:
        cid, pid = data["conversation_id"], data["parent_message_id"]
        message = ""
        
        response = self.request("/backend-api/conversation", "POST", data=dumps(data))

        finish_details = None
        
        for line in response.content.decode(errors="ignore").replace("\n\n", "\n").split("\n"):
            if line.lower() == "internal server error":
                raise errors.ChatGPTError("Server error")
            if not line or line is None:
                continue
            if "data: " in line:
                line = line[6:]
            if line == "[DONE]":
                break

            try:
                line = loads(line)
            except decoder.JSONDecodeError:
                continue
            if not self.__check_fields__(line):
                continue
            if line.get("message").get("author").get("role") != "assistant":
                continue

            cid = line["conversation_id"]
            pid = line["message"]["id"]
            metadata = line["message"].get("metadata", {})
            message_exists = False
            author = {}
            if line.get("message"):
                author = metadata.get("author", {}) or line["message"].get("author", {})
                if (line["message"].get("content") and line["message"]["content"].get("parts") and len(line["message"]["content"]["parts"]) > 0):
                    message_exists = True
            message : str = (line["message"]["content"]["parts"][0] if message_exists else "")
            model = metadata.get("model_slug", None)
            finish_details = metadata.get("finish_details", {"type": None})["type"]
            yield {
                "author": author,
                "message": message,
                "conversation_id": cid,
                "parent_id": pid,
                "model": model,
                "finish_details": finish_details,
                "end_turn": line["message"].get("end_turn", True),
                "recipient": line["message"].get("recipient", "all"),
                "citations": metadata.get("citations", []),
            }

        self.conversation_mapping[cid] = pid
        if pid is not None:
            self.parent_id = pid
        if cid is not None:
            self.conversation_id = cid

        if not auto_continue or not finish_details == "max_tokens":
            return

        message = message.strip("\n")
        for i in self.continue_write(conversation_id=cid, model=model, auto_continue=False):
            i["message"] = message + i["message"]
            yield i

    def continue_write(self, conversation_id : str = None, parent_id : str = "", model : str = "", auto_continue : bool = False) -> Generator[dict, None, None]:
        if parent_id and not conversation_id:
            raise errors.ChatGPTError("conversation_id must be set once parent_id is set")
        
        conversation_id = conversation_id or self.conversation_id
        parent_id = parent_id or self.parent_id or ""
        if not conversation_id and not parent_id:
            parent_id = str(uuid4())

        if conversation_id and not parent_id:
            if conversation_id not in self.conversation_mapping:
                print(f"Conversation ID {conversation_id} not found in conversation mapping, try to get conversation history for the given ID")
                with suppress(Exception):
                    history = self.get_msg_history(conversation_id)
                    self.conversation_mapping[conversation_id] = history["current_node"]
            if conversation_id in self.conversation_mapping:
                parent_id = self.conversation_mapping[conversation_id]
            else: # invalid conversation_id provided, treat as a new conversation
                conversation_id = None
                parent_id = str(uuid4())
        model = model or self.model or "text-davinci-002-render-sha"
        data = {
            "action": "continue",
            "conversation_id": conversation_id,
            "parent_message_id": parent_id,
            "model": model or self.model or ("text-davinci-002-render-paid" if self.config.get("paid") else "text-davinci-002-render-sha"),
            "history_and_training_disabled": self.disable_history,
        }
        yield from self.__send_request__(data, auto_continue=auto_continue)
            
    def post_messages(self, messages : list[dict], conversation_id : str = None, parent_id : str = None, plugin_ids : list = None, model : str = None, auto_continue : bool = False, **kwargs) -> Generator[dict, None, None]:
        if plugin_ids is None:
            plugin_ids = []
        if parent_id and not conversation_id:
            raise errors.ChatGPTError("conversation_id must be set once parent_id is set")

        if conversation_id and conversation_id != self.conversation_id:
            self.parent_id = None
        conversation_id = conversation_id or self.conversation_id
        parent_id = parent_id or self.parent_id or ""
        if not conversation_id and not parent_id:
            parent_id = str(uuid4())

        if conversation_id and not parent_id:
            if conversation_id not in self.conversation_mapping:
                try:
                    history = self.get_message_history(conversation_id)
                    self.conversation_mapping[conversation_id] = history["current_node"]
                except exceptions.HTTPError:
                    print("Conversation unavailable")
            if conversation_id in self.conversation_mapping:
                parent_id = self.conversation_mapping[conversation_id]
            else:
                print("Warning: Invalid conversation_id provided, treating as a new conversation")
                conversation_id = None
                parent_id = str(uuid4())
        model = model or ("text-davinci-002-render-sha" if self.model == "gpt-3.5" else None) or "text-davinci-002-render-sha"

        data = {
            "action": "next",
            "messages": messages,
            "conversation_id": conversation_id,
            "parent_message_id": parent_id,
            "model": model,
            "history_and_training_disabled": self.disable_history,
        }
        #plugin_ids = self.config.get("plugin_ids", []) or plugin_ids
        if len(plugin_ids) > 0 and not conversation_id:
            data["plugin_ids"] = plugin_ids

        yield from self.__send_request__(data, auto_continue=auto_continue)

    def get_conversations(self, offset : int = None, limit : int = None, encoding : str = None) -> list:
        response = self.request(f"/backend-api/conversations?{f'offset={offset}' if offset != None else ''}{f'&limit={limit}' if limit != None else ''}", "GET")

        if encoding is not None:
            response.encoding = encoding
        data = loads(response.text)
        return data["items"]

    def get_message_history(self, conversation_id: str, encoding: str = None) -> dict:
        response = self.request(f"/backend-api/conversation/{conversation_id}", "GET")

        if encoding is not None:
            response.encoding = encoding
        return response.json()

    def send_message(self, text : str, conversation_id : str = None, parent_id : str = None, plugin_ids : list = None, model : str = None, auto_continue : bool = True):
        messages = [
            {
                "id": str(uuid4()),
                "role": "user",
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": [text]},
            }
        ]

        yield from self.post_messages(messages, conversation_id, parent_id, plugin_ids, model, auto_continue)

    def generate_title(self, conversation_id : str):
        try:
            message_id = self.get_message_history(conversation_id)["current_node"]
        except exceptions.HTTPError:
            print("Conversation unavailable")
        return self.request(f"/backend-api/conversation/gen_title/{conversation_id}", "POST", json={"message_id": message_id}).json()

    def edit_title(self, conversation_id : str, title: str):
        return self.request(f"/backend-api/conversation/{conversation_id}", "PATCH", data=dumps({"title": title}))
        
    def delete_conversation(self, conversation_id : str):
        return self.request(f"/backend-api/conversation/{conversation_id}", "PATCH", data="{\"is_visible\": false}")
        
    def delete_conversations(self):
        return self.request(f"/backend-api/conversations", "PATCH", data="{\"is_visible\": false}")

    #def delete_messages(self, conversation_id : str, amount : int = 1):
        #history = self.get_message_history(conversation_id)
        #parent_id = list(history["mapping"].values())[-amount*2-2]["id"]
        #print(parent_id)
        #print(list(history["mapping"].values())[-amount*2-2]["message"]["content"]["parts"][0])
        #for _ in self.send_message(list(history["mapping"].values())[-amount*2-2]["message"]["content"]["parts"][0], conversation_id, parent_id):
        #    pass

    def reset_chat(self): # basically a new chat function
        self.conversation_id = None
        self.parent_id = str(uuid4())

    def set_custom_instructions(self, ai_instructions : str = "", user_information : str = "", enable_for_new_chats : bool = True):
        return self.request("/backend-api/user_system_messages", "POST", json={"about_model_message": ai_instructions, "about_user_message": user_information, "enabled": enable_for_new_chats})

    def get_suggested_prompts(self, limit : int = 4, offset : int = 0):
        return self.request(f"/backend-api/prompt_library/?limit={limit}&offset={offset}", "GET").json()
