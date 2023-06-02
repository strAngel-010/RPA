from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import json
from rasa_sdk.events import SlotSet

from state_machine import LimitState

class ActionProglang(Action):
    state_limits = LimitState()

    def name(self) -> Text:
        return "action_proglang"

    def __set_slots(self, entities):
        with open('entities.json', 'r', encoding='utf-8') as file:
            ent_dicti = json.load(file)
        lst = []
        for entity in entities:
            if entity['entity'] == 'VALUE':
                if entity['value'].isdigit():
                    lst.append((entity['entity'].lower(), int(entity['value'])))
                else:
                    lst.append((entity['entity'].lower(), 0))
                continue
            try:
                lst.append((entity['entity'].lower(), ent_dicti[entity['value'].lower()]))
            except KeyError:
                lst.append((entity['entity'].lower(), entity['value']))
        for i in lst:
            SlotSet(i[0], i[1])
        return lst

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        slot_list = ['service_type', 'place_type', 'card_type', 'limit_type', 'first_message', 'current_state']
        lst_setter = [i for i in self.__set_slots(tracker.latest_message['entities']) if i[0] in slot_list]
        needs_reload, ans = self.state_limits.resolve(lst_setter)
        if self.state_limits.edited_slots:
            dispatcher.utter_message("Отлично!")
        dispatcher.utter_message(ans)
        print(tracker.latest_message['text'])
        print(lst_setter)
        if needs_reload:
            return [SlotSet(i[0], None) for i in lst_setter]
        return [SlotSet(i[0], i[1]) for i in lst_setter]
