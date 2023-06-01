from statemachine import StateMachine, State
import json
from neo4j import GraphDatabase

class MetaSingleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class LimitState(StateMachine, metaclass=MetaSingleton):

    base_limit = State("limit_init(0000)", initial=True)

    # первая группа состояний
    card_type = State("0010")
    place_type = State("0100")
    service_type = State("1000")
    limit_type = State("0001")

    #вторая группа состояний из типа карты

    card_place = State("0110")
    card_service = State("1010")
    card_limit = State("0011")

    #вторая группа состояний из типа лимита

    limit_place = State("0101")
    limit_service = State("1001")

    #вторая группа состояний из типа места

    place_service = State("1100")

    #третья группа состосяний из карты

    card_place_service = State("1110")
    card_service_limit = State("1011")
    card_place_limit = State("0111")
    limit_place_service = State("1101")

    #выход

    full = State("1111")

    finish = State("finish", final=True)

    #выходы из базоваго состояния

    from_base = base_limit.to(limit_type) | base_limit.to(card_type) | base_limit.to(place_type) | base_limit.to(service_type)
    from_base2 = base_limit.to(card_limit) | base_limit.to(card_place) | base_limit.to(card_service) | base_limit.to(limit_place) | base_limit.to(limit_service) | base_limit.to(place_service)
    from_base3 = base_limit.to(card_place_limit) | base_limit.to(card_place_service) | base_limit.to(card_service_limit) | base_limit.to(limit_place_service)

    #выходы из 1 во 2 группу состояний

    from_card = card_type.to(card_limit) | card_type.to(card_place) | card_type.to(card_service)
    from_limit = limit_type.to(card_limit) | limit_type.to(limit_place) | limit_type.to(limit_service)
    from_place = place_type.to(card_place) | place_type.to(limit_place) | place_type.to(place_service)
    from_service = service_type.to(card_service) | place_type.to(limit_service) | place_type.to(place_service)

    #выхоы из 2 в 3 группу состояний

    to_card_place_service = card_place.to(card_place_service) | card_service.to(card_place_service) | place_service.to(card_place_service)
    to_card_service_limit = limit_service.to(card_service_limit) | card_service.to(card_service_limit) | card_limit.to(card_service_limit)
    to_card_place_limit = card_limit.to(card_place_limit) | card_place.to(card_place_limit) | limit_place.to(card_place_limit)
    to_limit_place_service = limit_place.to(limit_place_service) | limit_service.to(limit_place_service) | place_service.to(limit_place_service)

    #выходы в полное состояние

    to_full = card_place_limit.to(full) | card_service_limit.to(full) | card_place_service.to(full) | limit_place_service.to(full)

    to_finish = full.to(finish, cond="check_all")

    def __init__(self):
        super().__init__()
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
        self.__utter_message = None
        self.__utter_faults = None
        self.__utter_first = None
        self.__utter_next = None
        self.__read_json()

    def __read_json(self):
        with open("utter_messages.json", "r") as file:
            utter = json.load(file)
            self.__uter_faults = utter["utter_messages_faults"]
            self.__utter_message = utter["utter_messages"]
            self.__utter_first = utter["utter_first"]
            self.__utter_next = utter["utter_next"]

    def resolve(self, setted_slots=None):
        if self.current_state.name == "limit_init(0000)" and setted_slots is None:
            return "Добрый день! Я отвечу на интересующие вас вопросы про лимиты на картых нашего банка. Пожалуйста, скажите мне какой картой вы пользуетесь?"

        self.set_slots(setted_slots)
        self.check_all()
        self.check_setted_slot()

    def set_slots(self, setted_slots):
        for k, v in setted_slots.items():
            self.__slots[k] = v
            self.__setted_slots.append(k)

    def check_setted_slot(self):
        for k, v in self.__slots.items():
            if v is not None:
                self.__non_checked_list.remove(k)
            if k == "card":
                self.card = v
            elif k == "limit":
                self.limit = v
            elif k == "place":
                self.place = v
            elif k == "service":
                self.place = v

    def check_card(self):
        return self.card is None

    def check_limit(self):
        return self.limit is None

    def check_place(self):
        return self.place is None

    def check_service(self):
        return self.service is None

    def check_all(self):
        return self.check_card() and self.check_limit() and self.check_place() and self.check_service()

    def __generate_utter(self):
        message = "Пожалуйста, подскажите: "

        if len(self.__setted_slots) == 0:
            message = "Пожалуйста, подскажите: Вас интересует лимит на перевод или снятие наличных, Вы используете дебетовую или кредитную карту, Вы переводите деньги через СПБ или СБОЛ, Вы получали карту в отделении нашего банка?"
        elif len(self.__setted_slots) == 3:
            for i in self.__utter_message:
                if i not in self.__setted_slots:
                    message = self.__utter_message[i]
        elif len(self.__setted_slots) == 2:
            message += self.__utter_first[self.__non_checked_list[0]]
            message += " и "
            message += self.__utter_next[self.__non_checked_list[1]]
        elif len(self.__setted_slots) == 1:
            message += self.__utter_first[self.__non_checked_list[0]]
            for i in self.__non_checked_list[1:]:
                message += ", "
                message += self.__utter_next[i]
        return message

    def __search_limit(self, tx, lst_setter, val=True):
        dicti = dict(lst_setter)
        match_card = 'MATCH (t)-[:CARD]->({name:"' + dicti['card_type'] + '"})'
        match_limit = 'Match (t)-[:LIMIT]->({name:"' + dicti['limit_type'] + '"})'
        match_place = 'Match (t)-[:PLACE]->({name:"' + dicti['place_type'] + '"})'
        match_service = 'Match (t)-[:SERVICE]->({name:"' + dicti['service_type'] + '"})'

        if val:
            if dicti['limit_value'] != 0:
                match_limit_value = f' AND t.value <={dicti["limit_type_value"]} and t.value>0'
            else:
                match_limit_value = ' AND t.value = 0'
        else:
            match_limit_value = ''
        search_limit = "Match (t:LIMITVALUE) WHERE EXISTS {" + match_card + "} AND EXISTS {" + match_limit + "} AND EXISTS {" + match_place + "} AND EXISTS  {" + match_service + "} " + match_limit_value + " return t.id, t.name LIMIT 1"

        print(search_limit)
        result = tx.run(search_limit, )

        record = result.single()

        return record

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

    def __search(self, lst_setter):
        self.__driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j"))

        with self.__driver.session() as session:
            result = session.write_transaction(
                self.__search_limit, lst_setter
            )
            try:
                limit_id = result[0]
                limit_res = True
            except TypeError:
                result = session.write_transaction(
                    self.__search_limit, lst_setter, False
                )
                limit_res = False
                limit_id = result[0]
            try:
                result_type = session.write_transaction(
                    self.__search_card_by_limit, limit_id, lst_setter
                )
                self.__driver.close()
                return limit_res, result_type[1]
            except TypeError:
                return False, None