from statemachine import State, StateMachine
import json
from neo4j import GraphDatabase

class MetaSingleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
    
class TariffState(StateMachine, metaclass=MetaSingleton):
    
    base_tariff = State("tariff_init(0000)", initial=True)
    
    # Первая группа состояния
    type_1 = State("0100")
    currency_1 = State("0010")
    category_1 = State("1000")
    value_1 = State("0001")
    
    # Вторая группа состояния из category
    cat_type = State("1100")
    cat_cur = State("1010")
    cat_value = State("1001")
    
    # Вторая группа состояния из type
    type_cur = State("0110")
    type_value = State("0101")
    
    # Вторая группа состояния из currency
    cur_value = State("0011")
    
    # Третья группа состояний
    cat_type_cur = State("1110")
    cat_type_value = State("1101")
    cat_cur_value = State("1011")
    type_cur_value = State("0111")
    
    full = State("1111")
    
    finish = State("finish", final = True)
    
    #from base tariff
    from_base = base_tariff.to(type_1) | base_tariff.to(currency_1) | base_tariff.to(category_1) | base_tariff.to(value_1)
    from_base2 = base_tariff.to(cat_type) | base_tariff.to(cat_cur) | base_tariff.to(cat_value) | base_tariff.to(type_cur) | base_tariff.to(type_value) | base_tariff.to(cur_value)
    from_base3 = base_tariff.to(cat_type_cur) | base_tariff.to(cat_type_value) | base_tariff.to(cat_cur_value) | base_tariff.to(type_cur_value) |  base_tariff.to(full)
    
    # Набор переходов из 1 в 2 слота
    from_cat = category_1.to(cat_type) | category_1.to(cat_cur) | category_1.to(cat_value)
    from_type = type_1.to(cat_type) | type_1.to(type_cur) | type_1.to(type_value)
    from_cur = currency_1.to(cat_cur) | currency_1.to(type_cur) | currency_1.to(cur_value)
    from_value = value_1.to(cat_value) | value_1.to(type_value) | value_1.to(cur_value)
    
    # Набор переходов из 2 в 3 слота
    to_cat_type_cur = cat_type.to(cat_type_cur) | type_cur.to(cat_type_cur) | cat_cur.to(cat_type_cur)
    to_cat_type_value = cat_type.to(cat_type_value) | cat_value.to(cat_type_value) | type_value.to(cat_type_value)
    to_cat_cur_value = cat_cur.to(cat_cur_value) | cat_value.to(cat_cur_value) | cur_value.to(cat_cur_value)
    to_type_cur_value = type_cur.to(type_cur_value) | type_value.to(type_cur_value) | cur_value.to(type_cur_value)
    
    toFull = cat_type_cur.to(full) | cat_type_value.to(full) | cat_cur_value.to(full) | type_cur_value.to(full)
    
    toFinish = full.to(finish, cond="check_all")
    
    def __init__(self):
        self.__slots_list = ["card_category", "card_type","currency", "value"]
        self.__non_checked_list = ["card_category", "card_type","currency", "value"]
        self.__setted_slots = []
        self.__slots = {
            "card_category": None,
            "card_type": None,
            "currency": None, 
            "value": None
        }
        self.currency = None
        self.category = None
        self.type = None
        self.value = None
        self.__utter_message = None
        self.__utter_faults = None
        self.__utter_first = None
        self.__utter_next = None
        self.__read_json()
    
    
    def __read_json(self):
        with open("utter_messages.json", 'r') as f:
            utter = json.load(f)
        self.__utter_faults = utter["utter_messages_faults"]
        self.__utter_message = utter["utter_messages"]
        self.__utter_first = utter["utter_first"]
        self.__utter_next = utter["utter_next"]
        
    def resolve(self, setted_slots=None):
        if self.current_state.name == "tariff_init(0000)" and setted_slots is None:
            return "Добрый день! Я Вам помогу подобрать карту или тариф. Пожалуйста, скажите мне какую карту вы хотите и с какой платой за обслуживание?"
        
        self.set_slots(setted_slots)
        self.__check_card_type()
        self.check_setted_slot()
        
            
    def set_slots(self, setted_slots):
        for k, v in setted_slots.items():
            self.__slots[k] = v
            self.__setted_slots.append(k)
    
    def check_setted_slot(self):
        for k, v in self.__slots.items():
            if v is not None:
                self.__non_checked_list.remove(k)
            if k=='currency':
                self.currency = v
            elif k == 'card_category':
                self.category = v
            elif k == 'card_type':
                self.type = v
            else:
                self.value = v
        
            
    def check_currency(self):
        return self.currency is None
    
    def check_category(self):
        return self.category is None
    
    def check_value(self):
        return self.value is None
    
    def check_type(self):
        return self.type is None
    
    def check_all(self):
        return self.check_type() and self.check_value() and self.check_category() and self.check_currency()
    
    def __check_card_type(self):
        if self.__slots['card_type'] is not None:
            if self.__slots['card_type'] == "Зарплатная":
                self.__slots['card_category'] = "Дебетовая"
                self.__setted_slots.append('card_category')
        if self.__slots['card_category'] is not None:
            if self.__slots['card_category'] == "Кредитная":
                self.__slots['card_type'] = "Личная"
                self.__setted_slots.append('card_type')
    
    def __generate_utter(self):
        message = "Пожалуйста, подскажите: "
        
        if len(self.__setted_slots) == 0:
            message = "Пожалуйста, подскажите: Вы ищете кредитную или дебетовую карту, валюту и максимальную плату за обслуживание?"
        elif len(self.__setted_slotsted_slots) == 3:
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
    
    # База данных
    def __search_tariff(self, tx, lst_setter, val=True):
        
        dicti = dict(lst_setter)
        match_card_type = 'MATCH (t)-[:TYPE]->({name:"' + dicti['card_type'] + '"})'
        match_currency = 'Match (t)-[:CURRENCY]->({name:"' + dicti['currency'] + '"})'
        match_card_category = 'Match (t)-[:CATEGORY]->({name:"' + dicti['card_category'] + '"})'
        
        if val:
            if dicti['value'] != 0:
                match_tariff_value = f' AND t.value <={dicti["value"]} and t.value>0'
            else:
                match_tariff_value = ' AND t.value = 0'
        else:
            match_tariff_value = ''
        search_tariff = "Match (t:Tariff) WHERE EXISTS {" + match_card_type +"} AND EXISTS {" + match_currency + "} AND EXISTS {" + match_card_category + "} " + match_tariff_value + " return t.id, t.name LIMIT 1"
        
        print(search_tariff)
        result = tx.run(search_tariff,)

        record = result.single()
        
        return record
    
    def __search_card_by_tariff(self, tx, tariff_id, lst_setter):
        dicti = dict(lst_setter)
        match_tariff = "MATCH (c)-[:TARIFF]->(t:Tariff {id:" + str(tariff_id) + "})"
        match_card_type = 'MATCH (c)-[:TYPE]->({name:"' + dicti['card_type'] + '"})'
        match_currency = 'Match (c)-[:CURRENCY]->({name:"' + dicti['currency'] + '"})'
        match_card_category = 'Match (c)-[:CATEGORY]->({name:"' + dicti['card_category'] + '"})'
        query = "MATCH (c:Card)-[:TARIFF]->(t:Tariff {id:" + str(tariff_id) + "})"
        query = "MATCH (c:Card) WHERE EXISTS {" + match_tariff +"} AND EXISTS {" + match_card_type +"} AND EXISTS {" + match_currency +"} AND EXISTS {" + match_card_category +"} return c.id, c.name LIMIT 1" 
        print(query)
        result = tx.run(query)
        record = result.single()
        return record
            
    def __search(self, lst_setter):
        self.__driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j"))
        
        with self.__driver.session() as session:
            result = session.write_transaction(
                self.__search_tariff, lst_setter
            )
            try:
                tariff_id = result[0]
                tariff_res = True
            except TypeError:
                result = session.write_transaction(
                self.__search_tariff, lst_setter, False
            )
                tariff_res = False
                tariff_id = result[0]
            try:
                result_card = session.write_transaction(
                    self.__search_card_by_tariff, tariff_id, lst_setter
                )
                self.__driver.close()
                return tariff_res, result_card[1]
            except TypeError:
                return False, None