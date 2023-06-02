import inspect

from state_machine.models import Event, State, InvalidStateTransition
from state_machine.orm import get_adaptor
from statemachine import StateMachine, State
import json
from neo4j import GraphDatabase

_temp_callback_cache = None

def get_callback_cache():
    global _temp_callback_cache
    if _temp_callback_cache is None:
        _temp_callback_cache = dict()
    return _temp_callback_cache

def get_function_name(frame):
    return inspect.getouterframes(frame)[1][3]

def before(before_what):
    def wrapper(func):
        frame = inspect.currentframe()
        calling_class = get_function_name(frame)

        calling_class_dict = get_callback_cache().setdefault(calling_class, {'before': {}, 'after': {}})
        calling_class_dict['before'].setdefault(before_what, []).append(func)

        return func

    return wrapper


def after(after_what):
    def wrapper(func):

        frame = inspect.currentframe()
        calling_class = get_function_name(frame)

        calling_class_dict = get_callback_cache().setdefault(calling_class, {'before': {}, 'after': {}})
        calling_class_dict['after'].setdefault(after_what, []).append(func)

        return func

    return wrapper


def acts_as_state_machine(original_class):
    adaptor = get_adaptor(original_class)
    global _temp_callback_cache
    modified_class = adaptor.modifed_class(original_class, _temp_callback_cache)
    _temp_callback_cache = None
    return modified_class

class LimitState(StateMachine):

    base_limit = State("0000", initial=True)

    # первая группа состояний
    card_type = State("0010")
    place_type = State("0100")
    service_type = State("1000")
    limit_type = State("0001")

    place_card = State("0110")
    service_card = State("1010")
    card_limit = State("0011")
    place_limit = State("0101")
    service_limit = State("1001")
    service_place = State("1100")

    service_place_card = State("1110")
    service_card_limit = State("1011")
    place_card_limit = State("0111")
    service_place_limit = State("1101")

    #выход

    full = State("1111")

    finish = State("finish")

    to_service = base_limit.to(service_type)
    to_place = base_limit.to(place_type)
    to_card = base_limit.to(card_type)
    to_limit = base_limit.to(limit_type)

    to_service_place = service_type.to(service_place) | place_type.to(service_place)
    to_service_card = service_type.to(service_card) | card_type.to(service_card)
    to_service_limit = service_type.to(service_limit) | limit_type.to(service_limit)
    to_place_card = place_type.to(place_card) | card_type.to(place_card)
    to_place_limit = place_type.to(place_limit) | limit_type.to(place_limit)
    to_card_limit = card_type.to(card_limit) | limit_type.to(card_limit)

    to_service_place_card = service_place.to(service_place_card) | service_card.to(service_place_card) | place_card.to(service_place_card)
    to_service_place_limit = service_place.to(service_place_limit) | service_limit.to(service_place_limit) | place_limit.to(service_place_limit)
    to_service_card_limit = service_card.to(service_card_limit) | service_limit.to(service_card_limit) | card_limit.to(service_card_limit)
    to_place_card_limit = place_card.to(place_card_limit) | place_limit.to(place_card_limit) | card_limit.to(place_card_limit)

    #выходы в полное состояние

    to_full = service_place_card.to(full) | service_place_limit.to(full) | service_card_limit.to(full) | place_card_limit.to(full)

    to_finish = full.to(finish, cond="check_all")
    to_base = full.to(base_limit) | finish.to(base_limit) | base_limit.to(base_limit)

    def __init__(self):
        super().__init__()
        self.reload()
        self.__utter_first = 1

    '''
    def __read_json(self):
        with open("utter_messages.json", "r") as file:
            utter = json.load(file)
            self.__uter_faults = utter["utter_messages_faults"]
            self.__utter_message = utter["utter_messages"]
            self.__utter_first = utter["utter_first"]
            self.__utter_next = utter["utter_next"]
    '''

    def resolve(self, setted_slots=None):
        if self.__utter_first:
            self.__utter_first = 0
            self.edited_slots = 0
            return False, "Добрый день! Я отвечу на интересующие вас вопросы про лимиты на картах нашего банка. Пожалуйста, скажите, какой картой вы пользуетесь?"

        if setted_slots is not None: self.set_slots(setted_slots)
        self.check_setted_slot()
        if self.check_all():
            self.to_finish
            limit_res, limit_name, value = self.__search(self.__slots)
            if limit_res:
                ans = self.limit + ' через ' + self.service + ' с ' + (self.card.lower())[:-2] + 'ой карты через ' + self.place.lower() +  " составляет " + str(value) + " рублей согласно тарифу "+limit_name+". Расскажите о следующей карте\n"
                self.reload()
                self.edited_slots = 0
                return True, ans

        #print("Setted slots len"+ str(setted_slots))
        ans = ""
        self.edited_slots = 1
        if len(setted_slots) == 0:
            self.edited_slots = 0
            ans +=  "Я Вас не понял\n"
        ans += self.__generate_utter()
        return False, ans

    def reload(self):
        self.__slots_list = ["card_type", "limit_type", "place_type", "service_type"]
        self.__non_checked_list = ["card_type", "limit_type", "place_type", "service_type"]
        self.__setted_slots = []
        self.__slots = {
            "card_type": None,
            "limit_type": None,
            "place_type": None,
            "service_type": None
        }
        self.card = None
        self.limit = None
        self.place = None
        self.service = None
        self.__utter_first = 0
        self.edited_slots = 0
        self.to_base()

    def set_slots(self, setted_slots):
        print(setted_slots)
        for k, v in setted_slots:
            self.__slots[k] = v
            self.__setted_slots.append(k)
            print(self.__slots)

    def check_setted_slot(self):
        for k, v in self.__slots.items():
            if v is not None:
                print("Trying to find", k, "in non checked slots")
                if (k in self.__non_checked_list):
                    self.__non_checked_list.remove(k)
                print("Non checked slots:", self.__non_checked_list)
                cur_state_name = self.current_state.name
                filled_inds = [int(i) for i in cur_state_name]
                print(filled_inds)
                if k == "service_type":
                    self.service = v
                    filled_inds[0] = 1
                elif k == "place_type":
                    self.place = v
                    filled_inds[1] = 1
                elif k == "card_type":
                    self.card = v
                    filled_inds[2] = 1
                elif k == "limit_type":
                    self.limit = v
                    filled_inds[3] = 1
                print(filled_inds)
                try: self.send(self.gen_new_state(filled_inds))
                except Exception: print(self.gen_new_state(filled_inds))
                print(self.current_state.name)

    def gen_new_state(self, ind):
        res = "to"
        for i in range(0, len(ind), 1):
            if (ind[i] == 1):
                if (i == 0): res = res+"_service"
                elif (i == 1): res = res+"_place"
                elif (i == 2): res = res+"_card"
                elif (i == 3): res = res+"_limit"
                else: return None
        if res == "to_service_place_card_limit": return "to_full"
        return res

    def check_card(self):
        return self.card

    def check_limit(self):
        return self.limit

    def check_place(self):
        return self.place

    def check_service(self):
        return self.service

    def check_all(self):
        return self.check_card() and self.check_limit() and self.check_place() and self.check_service()

    def __generate_utter(self):
        message = "Пожалуйста, подскажите: "

        cur_state = self.current_state.name
        for i in range(0, len(cur_state), 1):
            if cur_state[i] == "0":
                if i == 0: message += "\nКаким сервисом вы хотите воспользоваться (СБОЛ/СБП)?"
                if i == 1: message += "\nГде вы хотите воспользоваться услугами (в банке/в банкомате)?"
                if i == 2: message += "\nКакая у вас карта (кредитная/дебетовая)?"
                if i == 3: message += "\nЛимит на какое действие вы хотите узнать (перевод/платеж/снятие)?"

        return message

    def __search_limit(self, tx, lst_setter, val=True):
        dicti = dict(lst_setter)
        match_card = 'MATCH (l:Limit {card_type:"' + dicti['card_type'] + '"})\n'
        match_limit = 'MATCH (l:Limit {limit_type:"' + dicti['limit_type'] + '"})\n'
        match_place = 'MATCH (l:Limit {place_type:"' + dicti['place_type'] + '"})\n'
        match_service = 'MATCH (l:Limit {service_type:"' + dicti['service_type'] + '"})\n'

        search_limit = match_limit + match_service + match_place + match_card + 'return l.limitName, l.value;'

        print(search_limit)
        result = tx.run(search_limit, )

        record = result.single()

        return record

    '''
    def __search_card_by_limit(self, tx, limit_id, lst_setter):
        dicti = dict(lst_setter)
        match_limit = "MATCH (c)-[:LIMIT]->(t:Limit {id:" + str(limit_id) + "})"
        match_card = 'MATCH (c)-[:CARD]->({name:"' + dicti['card_type'] + '"})'
        match_place = 'Match (c)-[:PLACE]->({name:"' + dicti['place_type'] + '"})'
        match_service = 'Match (c)-[:SERVICE]->({name:"' + dicti['service_type'] + '"})'
        #query = "MATCH (c:Card)-[:TARIFF]->(t:Tariff {id:" + str(limit_id) + "})"
        query = "MATCH (c:Card) WHERE EXISTS {" + match_limit +"} AND EXISTS {" + match_card +"} AND EXISTS {" + match_service +"} AND EXISTS {" + match_place +"} return c.id, c.name LIMIT 1"
        print(query)
        result = tx.run(query)
        record = result.single()
        return record
    '''

    def __search(self, lst_setter):
        print("Search function")

        try:
            self.__driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j1"))

            with self.__driver.session() as session:
                result = session.write_transaction(
                    self.__search_limit, lst_setter
                )
                try:
                    limit_name = result[0]
                    limit_value = result[1]
                    return True, limit_name, limit_value
                except TypeError:
                    printf("Error")
                    return False, None, None
                '''
                try:
                    result_type = session.write_transaction(
                        self.__search_card_by_limit, limit_id, lst_setter
                    )
                    self.__driver.close()
                    return limit_res, result_type[1]
                except TypeError:
                    return False, None
                '''
        except Exception as e:
            print(e.args)